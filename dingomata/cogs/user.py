import logging
from datetime import datetime, timedelta
from functools import cache
from random import choice
from typing import Dict, Optional

import discord
import parsedatetime
import pytz
import tortoise.exceptions

from ..config import service_config
from ..decorators import slash, slash_group
from ..exceptions import DingomataUserError
from ..models import User
from .base import BaseCog

_log = logging.getLogger(__name__)
_calendar = parsedatetime.Calendar()


class UserCog(BaseCog):
    """Remind users to go to bed."""

    bedtime = slash_group(name="bedtime", description="Get a reminder to go to bed when you're up late.")
    timezone_g = slash_group(name="timezone", description="Manage how the bot interprets time for you.")
    _BEDTIME_KWDS = {"bed", "sleep", "bye", "cya", "see y", "night", "nini", "nite", "comf"}
    _CACHE: Dict[int, User] = {}

    @timezone_g.command(name='set')
    @discord.option('timezone', description="Your timezone",
                    autocomplete=discord.utils.basic_autocomplete(pytz.common_timezones))
    async def timezone_set(self, ctx: discord.ApplicationContext, timezone: str) -> None:
        """Set your timezone. Applies in all servers with this bot."""
        try:
            timezone = timezone.strip()
            tz = pytz.timezone(timezone)  # test if timezone is valid
        except pytz.UnknownTimeZoneError as e:
            raise DingomataUserError(
                f"Could not set your bedtime because timezone {timezone} is not recognized. Please use one of the "
                f'"TZ Database Name"s listed here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'
            ) from e
        await User.update_or_create({"timezone": str(tz)}, user_id=ctx.user.id)
        await ctx.respond(f"Done! Your timezone is now set to {str(tz)}.", ephemeral=True)

    @timezone_g.command(name='get')
    async def timezone_get(self, ctx: discord.ApplicationContext) -> None:
        """Get your current timezone."""
        user = await User.get_or_none(user_id=ctx.user.id)
        if user and user.timezone:
            await ctx.respond(f'Your current timezone is {user.timezone}.', ephemeral=True)
        else:
            raise DingomataUserError('You do not have a timezone set.')

    @bedtime.command(name='set')
    @discord.option('time', description="Your usual bedtime, for example 11:00pm, or 23:00")
    async def bedtime_set(self, ctx: discord.ApplicationContext, time: str) -> None:
        """Set a bedtime. I will remind you to go to bed when you chat after this time."""
        # Convert user timezone to UTC
        async with tortoise.transactions.in_transaction() as tx:
            try:
                user = await User.select_for_update().using_db(tx).get(user_id=ctx.user.id)
                tz = pytz.timezone(user.timezone)
            except tortoise.exceptions.DoesNotExist:
                raise DingomataUserError(
                    "You don't have a timezone set. I can only remind you of bedtime if I know what "
                    "time zone you are in. You can set one with the /timezone command.")
            datetime_obj, parse_status = _calendar.parseDT(time, tzinfo=tz)
            if parse_status != 2:
                raise DingomataUserError(
                    f"I can't interpret {time} as a valid time. Try using something like '11:00pm', '23:00', '11pm'"
                )
            time_obj = datetime_obj.time()
            user.bedtime = time_obj
            await user.save(using_db=tx)
            self._CACHE.pop(ctx.author.id, None)
        await ctx.respond(f"Done! I've saved your bedtime as {time_obj} {tz}.", ephemeral=True)

    @bedtime.command(name='off')
    async def bedtime_off(self, ctx: discord.ApplicationContext) -> None:
        """Clears your existing bed time."""
        await User.update_or_create({"bedtime": None}, user_id=ctx.user.id)
        self._CACHE.pop(ctx.author.id, None)
        await ctx.respond("Done! I've removed your bedtime.", ephemeral=True)

    @bedtime.command(name='get')
    async def bedtime_get(self, ctx: discord.ApplicationContext) -> None:
        """Get your current bed time."""
        user = await User.get_or_none(user_id=ctx.user)
        if not user or not user.bedtime:
            raise DingomataUserError("You do not have a bedtime set.")
        await ctx.respond(f"Your current bedtime is {user.bedtime} in {user.timezone}.", ephemeral=True)

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
        if not result or not result.bedtime:
            _log.debug(f"User {message.author.id} does not have a bedtime set.")
            return
        elif result.last_bedtime_notified and utcnow < (
                result.last_bedtime_notified + self._cooldown_for_guild(message.guild.id)):
            _log.debug(
                f"User {message.author.id} was last notified at {result.last_bedtime_notified}, still in cooldown.")
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
                result.last_bedtime_notified = utcnow  # type: ignore
                await result.save(update_fields=["last_notified"])
                _log.debug(f"Bedtime notified: {message.author}")
        except discord.Forbidden:
            _log.warning(f"Failed to notify {message.author} in {message.guild} about bedtime. The bot doesn't "
                         f"have permissions to post there.")

    @staticmethod
    @cache
    def _cooldown_for_guild(guild_id: int) -> timedelta:
        return timedelta(minutes=service_config.server[guild_id].bedtime.cooldown_minutes)

    async def _get_bedtime(self, user_id: int) -> Optional[User]:
        if user_id in self._CACHE:
            return self._CACHE[user_id]
        else:
            user = await User.get_or_none(user_id=user_id)
            self._CACHE[user_id] = user
            return user

    @slash()
    @discord.option('time', description="A date and/or time, e.g. 2020/01/01 00:00:00")
    @discord.option('timezone', description="Time this time is in. If not provided, uses your personal timezone.",
                    autocomplete=discord.utils.basic_autocomplete(pytz.common_timezones), type=str)
    async def localtime(self, ctx: discord.ApplicationContext, time: str, timezone: str | None = None) -> None:
        """Convert time between timezones."""
        if timezone:
            try:
                tz = pytz.timezone(timezone.strip())
            except pytz.UnknownTimeZoneError as e:
                raise DingomataUserError(
                    f'{timezone} is not a recognized timezone. Please use one of the "TZ Database Name"s listed here: '
                    f"https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
                ) from e
        else:
            user = await User.get_or_none(user_id=ctx.user.id)
            if user and user.timezone:
                tz = pytz.timezone(user.timezone)
            else:
                raise DingomataUserError("You did not provide a timezone and have not set your personal timezone. "
                                         "Please provide one when using the command, or set your personal timezone "
                                         "using /timezone.")
        time_obj, status = _calendar.parseDT(time, datetime.utcnow().astimezone(tz), tzinfo=tz)
        if status != 3:
            raise DingomataUserError(
                f"Can't interpret {time} as a valid date/time. Try using something like `today 5pm`, or for a "
                f"full date, `2021-12-20 01:05`"
            )
        await ctx.respond(
            f"{time} in {tz} is <t:{int(time_obj.timestamp())}:f> your local time. You can use the following text in a "
            f"message to make discord display it to everyone else in their own local time: "
            f"`<t:{int(time_obj.timestamp())}:f>`", ephemeral=True)
