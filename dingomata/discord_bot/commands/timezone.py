import logging
from copy import deepcopy
from datetime import datetime
from itertools import islice

import hikari
import lightbulb
import pytz
from parsedatetime import parsedatetime

from dingomata.database.models import User
from dingomata.exceptions import UserError
from dingomata.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('timezone')
_AUTOCOMPLETE_COUNT = 10
_calendar = parsedatetime.Calendar()


@plugin.command
@lightbulb.command("timezone", "Manage how this bot interprets time for you.")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def timezone_group(ctx: lightbulb.SlashContext):
    pass


@timezone_group.child
@lightbulb.option("timezone", description="Your timezone.", autocomplete=True)
@lightbulb.command("set", "Set your timezone. Applies in all servers with this discord bot.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def timezone_set(ctx: lightbulb.SlashContext):
    timezone = ctx.options.timezone.strip()
    tz = _parse_timezone(timezone)
    await User.update_or_create({"timezone": str(tz)}, user_id=ctx.user.id)
    await ctx.respond(f"Done! Your timezone is now set to {str(tz)}.")


@timezone_group.child
@lightbulb.command("get", "Get your current timezone.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def timezone_get(ctx: lightbulb.SlashContext):
    user = await User.get_or_none(user_id=ctx.user.id)
    if user and user.timezone:
        await ctx.respond(f'Your current timezone is {user.timezone}.')
    else:
        raise UserError('You do not have a timezone set.')


@plugin.command
@lightbulb.option('timezone', description="Time this time is in. If not provided, uses your personal timezone.",
                  autocomplete=True, default=None)
@lightbulb.option('time', description="A date and/or time, e.g. 2020/01/01 00:00:00")
@lightbulb.command("localtime", description="Convert time between timezones.", ephemeral=True)
async def localtime(ctx: lightbulb.SlashContext) -> None:
    if ctx.options.timezone:
        tz = _parse_timezone(ctx.options.timezone)
    else:
        user = await User.get_or_none(user_id=ctx.user.id)
        if user and user.timezone:
            tz = _parse_timezone(user.timezone)
        else:
            raise UserError("You did not provide a timezone and have not set your personal timezone. "
                            "Please provide one when using the command, or set your personal timezone "
                            "using /timezone.")
    time = ctx.options.time
    time_obj, status = _calendar.parseDT(time, datetime.utcnow().astimezone(tz), tzinfo=tz)
    if status != 3:
        raise UserError(
            f"Can't interpret {time!r} as a valid date/time. Try using something like `today 5pm`, or for a "
            f"full date, `2021-12-20 01:05`"
        )
    await ctx.respond(
        f"{time} in {tz} is <t:{int(time_obj.timestamp())}:f> your local time. You can use the following text in a "
        f"message to make discord display it to everyone else in their own local time: "
        f"`<t:{int(time_obj.timestamp())}:f>`")


@timezone_set.autocomplete("timezone")
@localtime.autocomplete("timezone")
async def timezone_set_timezone_autocomplete(
        option: hikari.AutocompleteInteractionOption,
        interaction: hikari.AutocompleteInteraction,
) -> list[str]:
    user_text: str = option.value.lower()
    prefix_iter = (tz for tz in pytz.common_timezones if tz.lower().startswith(user_text))
    prefix_found = list(islice(prefix_iter, _AUTOCOMPLETE_COUNT))
    if len(prefix_found) >= 10:
        return prefix_found
    infix_iter = (tz for tz in pytz.common_timezones if user_text in tz.lower() and tz not in prefix_found)
    infix_found = list(islice(infix_iter, _AUTOCOMPLETE_COUNT - len(prefix_found)))
    return prefix_found + infix_found


def _parse_timezone(tz: str) -> pytz.BaseTzInfo:
    try:
        return pytz.timezone(tz.strip())
    except pytz.UnknownTimeZoneError as e:
        raise UserError(
            f'{tz!r} is not a recognized timezone. Please use one of the "TZ Database Name"s listed here: '
            f"https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ) from e


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
