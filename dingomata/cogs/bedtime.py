import logging
from datetime import datetime, timedelta
from functools import cache
from random import choice
from typing import Dict, Optional

import discord
import parsedatetime
import pytz
from tortoise.exceptions import DoesNotExist

from ..config import service_config
from ..decorators import slash_group
from ..exceptions import DingomataUserError
from ..models import Bedtime
from .base import BaseCog

_log = logging.getLogger(__name__)
_calendar = parsedatetime.Calendar()


class BedtimeSpecificationError(DingomataUserError):
    """Error specifying bedtime due to invalid time or zone"""

    pass


class BedtimeCog(BaseCog):
    """Remind users to go to bed."""

    bedtime = slash_group(name="bedtime", description="Get a reminder to go to bed when you're up late.")
    _BEDTIME_KWDS = {"bed", "sleep", "bye", "cya", "see y", "night", "nini", "nite", "comf"}
    _CACHE: Dict[int, Bedtime] = {}

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

    @bedtime.command()
    @discord.option('time', description="Your usual bedtime, for example 11:00pm, or 23:00")
    @discord.option('timezone', description="Your timezone",
                    autocomplete=discord.utils.basic_autocomplete(pytz.common_timezones))
    async def set(self, ctx: discord.ApplicationContext, time: str, timezone: str) -> None:
        """Set a bedtime. I will remind you to go to bed when you chat after this time."""
        # Convert user timezone to UTC
        try:
            tz = pytz.timezone(timezone.strip())  # test if timezone is valid
        except pytz.UnknownTimeZoneError as e:
            raise BedtimeSpecificationError(
                f"Could not set your bedtime because timezone {timezone} is not recognized. Please use one of the "
                f'"TZ Database Name"s listed here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'
            ) from e
        datetime_obj, parse_status = _calendar.parseDT(time, tzinfo=tz)
        if parse_status != 2:
            raise BedtimeSpecificationError(
                f"Can't interpret {time} as a valid time. Try using something like '11:00pm', '23:00', '11pm'"
            )
        time_obj = datetime_obj.time()
        await Bedtime.update_or_create({"bedtime": time_obj, "timezone": str(tz)}, user_id=ctx.author.id)
        self._CACHE.pop(ctx.author.id, None)

        await ctx.respond(f"Done! I've saved your bedtime as {time_obj} {tz}.", ephemeral=True)

    @bedtime.command()
    async def off(self, ctx: discord.ApplicationContext) -> None:
        """Clears your existing bed time."""
        deleted_count = await Bedtime.filter(user_id=ctx.author.id).delete()
        if deleted_count:
            self._CACHE.pop(ctx.author.id, None)
            await ctx.respond("Done! I've removed your bedtime preferences.", ephemeral=True)
        else:
            await ctx.respond("You did not have a bedtime set.", ephemeral=True)

    @bedtime.command()
    async def get(self, ctx: discord.ApplicationContext) -> None:
        """Get your current bed time."""
        try:
            bedtime = await Bedtime.get(user_id=ctx.author.id)
            await ctx.respond(f"Your current bedtime is {bedtime.bedtime} in {bedtime.timezone}.", ephemeral=True)
        except DoesNotExist:
            await ctx.respond("You do not have a bedtime set.", ephemeral=True)

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """On any message the bot can read, determine if it's past the user's bedtime, and send a reminder if so."""
        if (not message.guild
                or message.guild.id not in self.bedtime.guild_ids
                or any(kwd in message.content.lower() for kwd in self._BEDTIME_KWDS)):
            return
        # Grab the user's bedtime
        result = await self._get_bedtime(message.author.id)
        utcnow = datetime.utcnow()
        # Do nothing if the user don't have a bedtime set or if they're in cooldown
        if not result:
            _log.debug(f"User {message.author.id} does not have a bedtime set.")
            return
        elif result.last_notified and utcnow < (result.last_notified + self._cooldown_for_guild(message.guild.id)):
            _log.debug(f"User {message.author.id} was last notified at {result.last_notified}, still in cooldown.")
            return

        # Find the nearest bedtime before current time in user's timezone, either earlier today or yesterday.
        # Not comparing in UTC because bedtime can change due to DST
        tz = pytz.timezone(result.timezone)
        now_tz = datetime.now(tz)
        bedtime = tz.localize(datetime.combine(now_tz.date(), result.bedtime))
        if now_tz.time() < result.bedtime:
            bedtime -= timedelta(days=1)
        _log.debug(f"User {message.author.id} has bedtime {bedtime}; it is currently {now_tz}")

        sleep_hours = service_config.server[message.guild.id].bedtime.sleep_hours
        try:
            if now_tz < bedtime + timedelta(hours=sleep_hours):
                if now_tz < bedtime + timedelta(hours=sleep_hours / 2):
                    # First half of bed time interval
                    text = choice([
                        "go to bed! It's past your bedtime now.",
                        "don't stay up too late. Good sleep is important for your health!",
                        "go to sleep now, so you're not miserable in the morning.",
                        "it's time to go to bed! Unless you're an owl, then go to sleep standing up.",
                        "sleep! NOW!",
                        "your eyes are getting very heavy. You are going into a deep slumber. **Now sleep.**",
                        "go to sleep! Everyone will still be here tomorrow. You can talk to them then.",
                        f"it's now {int((now_tz - bedtime).total_seconds() / 60)} minutes after your bedtime.",
                    ])
                else:
                    # Second half of bed time interval
                    text = choice([
                        "go back to bed! You're up way too early.",
                        "aren't you awake early today. Maybe consider catching up on those sleep hours?",
                        "you're awake! You were trying to cross the border...",
                        "you're finally awake.... You were trying to sleep, right? Walked right into this "
                        "discord server, same as us, and that furry over there.",
                    ])
                await message.channel.send(f"Hey {message.author.mention}, {text}")
                result.last_notified = utcnow  # type: ignore
                await result.save(update_fields=["last_notified"])
                _log.debug(f"Bedtime notified: {message.author}")
        except discord.Forbidden:
            _log.warning(f"Failed to notify {message.author} in {message.guild} about bedtime. The bot doesn't "
                         f"have permissions to post there.")

    @staticmethod
    @cache
    def _cooldown_for_guild(guild_id: int) -> timedelta:
        return timedelta(minutes=service_config.server[guild_id].bedtime.cooldown_minutes)

    async def _get_bedtime(self, user_id: int) -> Optional[Bedtime]:
        if user_id in self._CACHE:
            return self._CACHE[user_id]
        else:
            bedtime = await Bedtime.get_or_none(user_id=user_id)
            self._CACHE[user_id] = bedtime
            return bedtime
