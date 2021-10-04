import logging
from datetime import datetime, timedelta
from random import choice
from typing import Optional, Dict

import pytz
import parsedatetime
from discord import Message, Forbidden
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.utils.manage_commands import create_option
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from dingomata.config import service_config
from .models import BedtimeModel, Bedtime
from ...decorators import subcommand
from ...exceptions import DingomataUserError

_log = logging.getLogger(__name__)
_calendar = parsedatetime.Calendar()


class BedtimeSpecificationError(DingomataUserError):
    """Error specifying bedtime due to invalid time or zone"""
    pass


class BedtimeCog(Cog, name='Bedtime'):
    """Remind users to go to bed."""
    _GUILDS = service_config.get_command_guilds('bedtime')
    _BASE_COMMAND = dict(base='bedtime', guild_ids=_GUILDS)
    _BEDTIME_CACHE: Dict[int, Bedtime] = {}
    _BEDTIME_KWDS = {'bed', 'sleep', 'bye', 'cya', 'see y', 'night', 'nini', 'nite'}

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(BedtimeModel.metadata.create_all)

    @subcommand(
        name='set',
        description='Set your own bed time.',
        options=[
            create_option(name='time', description='When do you go to sleep? e.g. 12:00am',
                          option_type=str, required=True),
            create_option(name='timezone', description='Time zone you are in', option_type=str, required=True),
        ],
        **_BASE_COMMAND,
    )
    async def bedtime_set(self, ctx: SlashContext, time: str, timezone: str) -> None:
        # Convert user timezone to UTC
        try:
            tz = pytz.timezone(timezone.strip())  # test if timezone is valid
        except pytz.UnknownTimeZoneError as e:
            raise BedtimeSpecificationError(
                f'Could not set your bedtime because timezone {timezone} is not recognized. Please use one of the '
                f'"TZ Database Name"s listed here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'
            ) from e
        datetime_obj, parse_status = _calendar.parseDT(time, tzinfo=tz)
        if parse_status != 2:
            raise BedtimeSpecificationError(
                f"Can't interpret {time} as a valid time. Try using something like '11:00pm', '23:00', '11pm'")
        time_obj = datetime_obj.time()
        bedtime = Bedtime(user_id=ctx.author.id, bedtime=time_obj, timezone=str(tz))
        async with self._session() as session:
            async with session.begin():
                await session.merge(bedtime)
                await session.commit()
                self._BEDTIME_CACHE.pop(ctx.author.id, None)
        await ctx.reply(f"Done! I've saved your bedtime as {time_obj} {tz}.", hidden=True)

    @subcommand(name='off', description='Clears your bed time.', **_BASE_COMMAND)
    async def bedtime_off(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                statement = delete(Bedtime).filter(Bedtime.user_id == ctx.author.id)
                await session.execute(statement)
                await session.commit()
                self._BEDTIME_CACHE.pop(ctx.author.id, None)
        await ctx.reply("Done! I've removed your bedtime preferences.", hidden=True)

    @subcommand(name='get', description='Get your current bed time.', **_BASE_COMMAND)
    async def bedtime_get(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(Bedtime).filter(Bedtime.user_id == ctx.author.id)
                bedtime = (await session.execute(stmt)).scalar()
                if bedtime:
                    await ctx.reply(f'Your current bedtime is {bedtime.bedtime} in {bedtime.timezone}', hidden=True)
                else:
                    await ctx.reply('You do not have a bedtime set.', hidden=True)

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not message.guild or message.guild.id not in self._GUILDS \
                or any(kwd in message.content.lower() for kwd in self._BEDTIME_KWDS):
            return
        async with self._session() as session:
            async with session.begin():
                # Grab the user's bedtime
                result = await self._get_bedtime(session, message.author.id)
                utcnow = datetime.utcnow()
                # Do nothing if the user dont have a bedtime set or if they're in cooldown
                if not result:
                    _log.debug(f'User {message.author.id} does not have a bedtime set.')
                    return
                elif result.last_notified and utcnow < result.last_notified + \
                        timedelta(minutes=service_config.servers[message.guild.id].bedtime.cooldown_minutes):
                    _log.debug(f'User {message.author.id} was last notified at {result.last_notified}, still in '
                               f'cooldown.')
                    return

                # Find the nearest bedtime before current time in user's timezone, either earlier today or yesterday.
                # Not comparing in UTC because bedtime can change due to DST
                tz = pytz.timezone(result.timezone)
                now_tz = datetime.now(tz)
                bedtime = tz.localize(datetime.combine(now_tz.date(), result.bedtime))
                if now_tz.time() < result.bedtime:
                    bedtime -= timedelta(days=1)
                _log.debug(f'User {message.author.id} has bedtime {bedtime}; it is currently {now_tz}')

                sleep_hours = service_config.servers[message.guild.id].bedtime.sleep_hours
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
                        result.last_notified = utcnow
                        await session.commit()
                        self._BEDTIME_CACHE[message.author.id] = result
                        _log.info(f'Notified {message.author} about bedtime.')
                except Forbidden:
                    _log.warning(f'Failed to notify {message.author} in {message.guild} about bedtime. The '
                                 f"bot doesn't have permissions to post there.")

    async def _get_bedtime(self, session, user_id: int) -> Optional[Bedtime]:
        if user_id in self._BEDTIME_CACHE:
            return self._BEDTIME_CACHE[user_id]
        else:
            statement = select(Bedtime).filter(Bedtime.user_id == user_id)
            bedtime = (await session.execute(statement)).scalar()
            self._BEDTIME_CACHE[user_id] = bedtime
            return bedtime
