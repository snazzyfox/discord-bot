import logging
from datetime import datetime, timedelta
from random import choice

import hikari
import lightbulb
import parsedatetime
import pytz
import tortoise
import tortoise.transactions

from snoozybot.database.models import User
from snoozybot.exceptions import UserError
from snoozybot.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('bedtime')

_BEDTIME_CACHE: dict[int, User] = {}
_BEDTIME_COOLDOWN = timedelta(minutes=20)
_SLEEP_TIME = timedelta(hours=6)
_calendar = parsedatetime.Calendar()


@plugin.command
@lightbulb.command("bedtime", "Get a reminder to go to bed when you're up late.")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def bedtime_group(ctx: lightbulb.SlashContext):
    pass


@bedtime_group.child
@lightbulb.option("time", description="Your usual bedtime, for example 11:00pm, or 23:00")
@lightbulb.command("set", "Set a bedtime. I'll remind you to go to bed when you chat after this time.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def bedtime_set(ctx: lightbulb.SlashContext) -> None:
    """Set a bedtime. I will remind you to go to bed when you chat after this time."""
    # Convert user timezone to UTC
    time = ctx.options.time
    async with tortoise.transactions.in_transaction() as tx:
        try:
            user = await User.select_for_update().using_db(tx).get(user_id=ctx.user.id)
            tz = pytz.timezone(user.timezone)
        except tortoise.exceptions.DoesNotExist:
            raise UserError(
                "You don't have a timezone set. I can only remind you of bedtime if I know what "
                "time zone you are in. You can set one with the /timezone command.")
        datetime_obj, parse_status = _calendar.parseDT(time, tzinfo=tz)
        if parse_status != 2:
            raise UserError(
                f"I can't interpret {time} as a valid time. Try using something like '11:00pm', '23:00', '11pm'"
            )
        time_obj = datetime_obj.time()
        user.bedtime = time_obj
        await user.save(using_db=tx)
        _BEDTIME_CACHE.pop(ctx.author.id, None)
    await ctx.respond(f"Done! I've saved your bedtime as {time_obj} {tz}.")


@bedtime_group.child
@lightbulb.command('off', description="Removes your bedtime.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def bedtime_off(ctx: lightbulb.SlashContext) -> None:
    await User.update_or_create({"bedtime": None}, user_id=ctx.user.id)
    _BEDTIME_CACHE.pop(ctx.author.id, None)
    await ctx.respond("Done! I've removed your bedtime.")


@bedtime_group.child
@lightbulb.command(name='get', description="Get your current bedtime.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def bedtime_get(ctx: lightbulb.SlashContext) -> None:
    user = await User.get_or_none(user_id=ctx.user)
    if not user or not user.bedtime:
        raise UserError("You do not have a bedtime set.")
    await ctx.respond(f"Your current bedtime is {user.bedtime} in {user.timezone}.")


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_message(event: hikari.GuildMessageCreateEvent) -> None:
    """On any message, determine if it's past the user's bedtime, and send a reminder if so."""
    message = event.message
    # Grab the user's bedtime
    db_record = await _get_bedtime(message.author.id)
    utcnow = datetime.utcnow()
    # Do nothing if the user don't have a bedtime set or if they're in cooldown
    if not db_record or not db_record.bedtime:
        logger.debug(f"User {message.author.id} does not have a bedtime set.")
        return
    elif db_record.last_bedtime_notified and utcnow < db_record.last_bedtime_notified + _BEDTIME_COOLDOWN:
        logger.debug(
            f"User {message.author.id} was last notified at {db_record.last_bedtime_notified}, still in cooldown.")
        return

    # Find the nearest bedtime before current time in user's timezone, either earlier today or yesterday.
    # Not comparing in UTC because bedtime can change due to DST
    tz = pytz.timezone(db_record.timezone)
    now_tz = datetime.now(tz)
    bedtime = tz.localize(datetime.combine(now_tz.date(), db_record.bedtime))
    if now_tz.time() < db_record.bedtime:
        bedtime -= timedelta(days=1)
    logger.debug(f"User {message.author.id} has bedtime {bedtime}; it is currently {now_tz}")
    try:
        if now_tz < bedtime + _SLEEP_TIME:
            if now_tz < bedtime + _SLEEP_TIME / 2:
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
            await message.respond(f"Hey {message.author.mention}, {text}")
            db_record.last_bedtime_notified = utcnow  # type: ignore
            await db_record.save(update_fields=["last_bedtime_notified"])
            logger.debug(f"Bedtime notified: {message.author.id}")
    except hikari.ForbiddenError:
        logger.warning(f"Failed to notify {message.author} in {message.guild} about bedtime. The bot doesn't "
                       f"have permissions to post there.")


async def _get_bedtime(user_id: int) -> User | None:
    if user_id in _BEDTIME_CACHE:
        return _BEDTIME_CACHE[user_id]
    else:
        user = await User.get_or_none(user_id=user_id)
        _BEDTIME_CACHE[user_id] = user
        return user


load, unload = plugin.export_extension()
