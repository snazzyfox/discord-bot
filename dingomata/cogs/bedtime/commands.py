import logging
from datetime import datetime, timedelta
from random import random

import pytz
from dateutil.parser import parse as parse_datetime, ParserError
from discord import Message, Forbidden
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_slash, cog_subcommand
from discord_slash.utils.manage_commands import create_option
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .models import BedtimeModel, Bedtime
from ...config import get_guilds, get_guild_config
from ...exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class BedtimeSpecificationError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class BedtimeCog(Cog, name='Bedtime'):
    """Remind users to go to bed."""
    _BASE_COMMAND = dict(base='bedtime', guild_ids=get_guilds())

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(BedtimeModel.metadata.create_all)

    @cog_subcommand(
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
            tzname = str(pytz.timezone(timezone.strip()))  # test if timezone is valid
        except pytz.UnknownTimeZoneError as e:
            raise BedtimeSpecificationError(
                f'Could not set your bedtime because timezone {timezone} is not recognized. Please use one of the '
                f'"TZ Database Name"s listed here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones')
        try:
            time_obj = parse_datetime(time).time()
        except ParserError:
            raise BedtimeSpecificationError(
                f"Can't interpret {time} as a valid time. Try using something like '11:00pm', '23:00', '11pm'")
        bedtime = Bedtime(user=ctx.author.id, bedtime=time_obj, timezone=tzname)
        async with self._session() as session:
            async with session.begin():
                await session.merge(bedtime)
                await session.commit()
        await ctx.reply(f"Done! I've saved your bedtime as {time_obj} {tzname}.", hidden=True)

    @cog_subcommand(
        name='off',
        description='Clears your bed time.',
        **_BASE_COMMAND,
    )
    async def bedtime_off(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                statement = delete(Bedtime).filter(Bedtime.user == ctx.author.id)
                await session.execute(statement)
                await session.commit()
        await ctx.reply(f"Done! I've removed your bedtime preferences.", hidden=True)

    @cog_subcommand(name='get', description='Get your current bed time.', **_BASE_COMMAND)
    async def bedtime_get(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(Bedtime).filter(Bedtime.user == ctx.author.id)
                bedtime = (await session.execute(stmt)).scalar()
                if bedtime:
                    await ctx.reply(f'Your current bedtime is {bedtime.bedtime} in {bedtime.timezone}', hidden=True)
                else:
                    await ctx.reply('You do not have a bedtime set.', hidden=True)

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not message.guild or message.guild.id not in get_guilds():
            return
        async with self._session() as session:
            async with session.begin():
                # Grab the user's bedtime
                statement = select(Bedtime).filter(Bedtime.user == message.author.id)
                result = (await session.execute(statement)).scalars().one_or_none()

                # Do nothing if the user dont have a bedtime set or if they're in cooldown
                if not result:
                    _log.debug(f'User {message.author.id} does not have a bedtime set. Skipping.')
                    return
                elif result.last_notified and datetime.utcnow() < result.last_notified + \
                        timedelta(minutes=get_guild_config(message.guild.id).bedtime.cooldown):
                    _log.debug(f'User {message.author.id} was last notified at {result.last_notified}, still in '
                               f'cooldown. Skipping.')
                    return

                # Find the nearest bedtime before current time in user's timezone, either earlier today or yesterday.
                # Not comparing in UTC because bedtime can change due to DST
                tz = pytz.timezone(result.timezone)
                now_tz = datetime.now(tz)
                bedtime = tz.localize(datetime.combine(now_tz.date(), result.bedtime))
                if now_tz.time() < result.bedtime:
                    bedtime -= timedelta(days=1)
                _log.debug(f'User {message.author.id} has bedtime {bedtime}; it is currently {now_tz}')

                sleep_hours = get_guild_config(message.guild.id).bedtime.sleep_hours
                if bedtime > now_tz - timedelta(hours=sleep_hours):
                    try:
                        if random() < 0.2:
                            await message.channel.send(message.author.mention)
                            await message.channel.send("https://cdn.discordapp.com/attachments/178042794386915328/"
                                                       "875595133414961222/unknown-8.png")
                        else:
                            await message.channel.send(f"Hey {message.author.mention}, go to bed! It's past your "
                                                       f"bedtime now. ")
                        result.last_notified = datetime.utcnow()
                        await session.commit()
                        _log.info(f'Notified {message.author} about bedtime.')
                    except Forbidden:
                        _log.warning(f'Failed to notify {message.author} in {message.guild} about bedtime. The '
                                     f"bot doesn't have permissions to post there.")
