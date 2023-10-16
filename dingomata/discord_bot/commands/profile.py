import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Sequence

import hikari
import lightbulb
import pytz
import tortoise.transactions

from dingomata.config import values
from dingomata.database.fields import Random
from dingomata.database.models import GuildMember, User
from dingomata.exceptions import UserError
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('profile')
logger = logging.getLogger(__name__)
_MONTHS = [hikari.CommandChoice(name=f'{i:02} - {calendar.month_name[i]}', value=i) for i in range(1, 13)]
_FRIEND_CODE_SERVICES = ['Steam', 'Nintendo Switch', 'Pokemon Go', 'Playstation Network', 'Epic Games', 'XBox',
                         'Genshin Impact']
_DISCORD_IMAGE_URL = re.compile(
    r'https://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/\d+/\d+/.*\.(?:jpg|png|webp|gif)', re.IGNORECASE)


@plugin.command
@lightbulb.command("profile", description="Edit profile cards")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def profile_group(ctx: lightbulb.SlashContext) -> None:
    pass


@profile_group.child
@lightbulb.command("add", description="Add profile information")
@lightbulb.implements(lightbulb.SlashSubGroup)
async def profile_add_group(ctx: lightbulb.SlashContext) -> None:
    pass


@profile_group.child
@lightbulb.command("remove", description="Remove profile information")
@lightbulb.implements(lightbulb.SlashSubGroup)
async def profile_remove_group(ctx: lightbulb.SlashContext) -> None:
    pass


@profile_add_group.child
@lightbulb.option("day", description="Day of the birthday", type=int, min_value=1, max_value=31)
@lightbulb.option("month", description="Month of the birthday", type=int, choices=_MONTHS)
@lightbulb.command(name="birthday", description="Set your birthday.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_add_birthday(ctx: lightbulb.SlashContext) -> None:
    """Set your birthday."""
    # Test if the birthday is valid
    month, day = ctx.options.month, ctx.options.day
    try:
        datetime(year=2000, month=month, day=day)
    except ValueError:
        raise UserError(f'{month}/{day} is not a valid date.')
    next_birthday = await _get_next_birthday_utc(ctx.user.id, month, day)
    await GuildMember.update_or_create({
        "birthday_month": month, "birthday_day": day, "next_birthday_utc": next_birthday,
    }, guild_id=ctx.guild_id, user_id=ctx.user.id)
    await ctx.respond("I have saved your birthday.")


@profile_remove_group.child
@lightbulb.command(name="birthday", description="Remove your birthday.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_remove_birthday(ctx: lightbulb.SlashContext) -> None:
    """Remove your birthday."""
    with tortoise.transactions.in_transaction() as tx:
        member = await GuildMember.select_for_update().using_db(tx).get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.user.id)
        if member:
            member.birthday_month = None
            member.birthday_day = None
            member.next_birthday_utc = None
            await member.save(using_db=tx)
        await ctx.respond("I have removed your birthday.")


@profile_group.child
@lightbulb.command("next_birthdays", description="Show the next upcoming birthdays in this server.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def next_birthdays(ctx: lightbulb.SlashContext) -> None:
    today = datetime.now(pytz.utc).replace(hour=0, minute=0, second=0)
    # Get profiles with birthday after today
    members = await GuildMember.filter(
        guild_id=ctx.guild_id,
        next_birthday_utc__gte=today,
    ).order_by('next_birthday_utc').limit(10)
    if not members:
        raise UserError('No one on this server has a birthday set.')
    else:
        embed = hikari.Embed()
        for member in members:
            days_till_next = (member.next_birthday_utc - today).days
            if 0 <= days_till_next < 1:
                relative_time = '**Today!**'
            else:
                relative_time = f'in {days_till_next} days'
            embed.add_field(
                name=ctx.get_guild().get_member(member.user_id).display_name,
                value=f"{calendar.month_name[member.birthday_month]} {member.birthday_day} ({relative_time})",
                inline=False,
            )
        await ctx.respond("Upcoming birthdays in this server: ", embed=embed)


@profile_add_group.child
@lightbulb.option('code', description='Friend code you would like to add')
@lightbulb.option('service', description="Service or game this friend code is for", choices=_FRIEND_CODE_SERVICES)
@lightbulb.command(name="friend_code", description="Add your friend code.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_add_friend_code(ctx: lightbulb.SlashContext) -> None:
    await _set_profile_field(ctx.get_guild(), ctx.user, ('friendcode', ctx.options.service), ctx.options.code)
    await ctx.respond("Your friend code is saved.")


@profile_remove_group.child
@lightbulb.option('service', description="Service or game this friend code is for", choices=_FRIEND_CODE_SERVICES)
@lightbulb.command(name="friend_code", description="Remove one of your friend codes.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_remove_friend_code(ctx: lightbulb.SlashContext) -> None:
    """Removes a friend code."""
    await _unset_profile_field(ctx.get_guild(), ctx.user, ('friendcode', ctx.options.service))
    await ctx.respond("Your friend code has been removed.")


@profile_add_group.child
@lightbulb.option("url", description="An image URL posted on Discord of the ref sheet")
@lightbulb.option("name", description="Name for the ref sheet. If this name already exists, "
                                      "it will replace the existing one.")
@lightbulb.command(name="refsheet", description="Add a new ref sheet", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_add_refsheet(ctx: lightbulb.SlashContext) -> None:
    if not _DISCORD_IMAGE_URL.match(ctx.options.url):
        raise UserError(
            "The URL does not look like a Discord image attachment. Please make sure it's an image uploaded to "
            "Discord, not a link to a message, or an image from an outside source.")
    await _set_profile_field(ctx.get_guild(), ctx.user, ('refsheet', ctx.options.name.strip()), ctx.options.url)
    await ctx.respond("Your ref sheet is saved.")


@profile_remove_group.child
@lightbulb.option("name", description="Name for the ref sheet")
@lightbulb.command(name="refsheet", description="Remove one of your ref sheets.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_remove_refsheet(ctx: lightbulb.SlashContext) -> None:
    """Removes a ref sheet."""
    await _unset_profile_field(ctx.get_guild(), ctx.user, ('refsheet', ctx.options.name.strip()))
    await ctx.respond("All done! Your ref sheet is removed.")


async def _set_profile_field(guild: hikari.Guild, user: hikari.User, field: Sequence[str], value: Any):
    """Sets a field for a user."""
    # Update the relevant field
    async with tortoise.transactions.in_transaction() as tx:
        prof, _ = await GuildMember.get_or_create(guild_id=guild.id, user_id=user.id, defaults={'data': {}},
                                                  using_db=tx)
        _recursive_set_dict(prof.profile_data, field, value)
        await prof.save(using_db=tx)


async def _unset_profile_field(guild: hikari.Guild, user: hikari.User, field: Sequence[str]):
    """Removes a field for a user."""
    try:
        async with tortoise.transactions.in_transaction() as tx:
            prof = await GuildMember.select_for_update().using_db(tx).get(guild_id=guild.id, user_id=user.id)
            _recursive_del_dict(prof.data, field)
            if prof.data:
                await prof.save(using_db=tx)
            else:
                # Delete the profile entirely if there's no data left
                await prof.delete(using_db=tx)
    except (KeyError, tortoise.exceptions.DoesNotExist):
        raise UserError('You do not have that particular profile item. Your profile was not changed.')


# PROFILE PRINTING
@profile_group.child
@lightbulb.option("user", description="Whose profile to get. If not provided, views your own profile.",
                  type=hikari.Member, default=None)
@lightbulb.command("get", description="Privately view a profile card.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_get(ctx: lightbulb.SlashContext) -> None:
    user = ctx.options.user or ctx.author
    try:
        prof = await GuildMember.get(guild_id=ctx.guild_id, user_id=user.id)
        embed = _generate_profile_embed(ctx.get_guild(), prof)
        await ctx.respond(embed=embed)
    except tortoise.exceptions.DoesNotExist:
        raise UserError(f'{user.display_name} does not have any profile information.')


@profile_group.child
@lightbulb.command("random", description="Privately view a random profile card from this server.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_random(ctx: lightbulb.SlashContext) -> None:
    prof = await GuildMember.filter(guild_id=ctx.guild_id).annotate(
        random=Random("id")).order_by("random").limit(1).first()
    if prof:
        embed = _generate_profile_embed(ctx.get_guild(), prof)
        await ctx.respond(embed=embed)
    else:
        raise UserError("No one in this server has any profile information.")


@profile_group.child
@lightbulb.option("user", description="Whose profile to post. If not provided, your own profile will be posted.",
                  type=hikari.Member, default=None)
@lightbulb.command("post", description="Post a user's profile card publicly.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def profile_post(ctx: lightbulb.SlashContext) -> None:
    user = ctx.options.user or ctx.author
    try:
        prof = await GuildMember.get(guild_id=ctx.guild_id, user_id=user.id)
        embed = _generate_profile_embed(ctx.get_guild(), prof)
        await ctx.respond(embed=embed)
    except tortoise.exceptions.DoesNotExist:
        raise UserError(f'{user.display_name} does not have any profile information.')


def _generate_profile_embed(guild: hikari.Guild, prof: GuildMember) -> hikari.Embed | None:
    user = guild.get_member(prof.user_id)
    if not user:
        return None
    embed = hikari.Embed(title=user.display_name)
    embed.set_thumbnail(user.display_avatar_url.url)
    if prof.birthday_month and prof.birthday_day:
        embed.add_field(name='Birthday', value=f'{calendar.month_name[prof.birthday_month]} {prof.birthday_day}',
                        inline=False)
    if codes := prof.profile_data.get('friendcode'):
        lines = '\n'.join(f'**{key}**: {value}' for key, value in codes.items())
        embed.add_field(name='Friend Codes', value=lines, inline=False)
    if refs := prof.profile_data.get('refsheet'):
        lines = '\n'.join(f'[{name}]({url})' for name, url in refs.items())
        embed.add_field(name='Ref Sheets', value=lines, inline=False)
        embed.set_image(next(iter(refs.values())))
    return embed


# BIRTHDAYS
async def _get_next_birthday_utc(user_id: int, month: int, day: int) -> datetime:
    # Get current date in user's timezone
    user = await User.get_or_none(user_id=user_id)
    if not user or not user.timezone:
        raise UserError("You have not set a timezone for yourself. Please set a timezone with /timezone "
                        "first so I can properly understand your birthday.")
    tz = pytz.timezone(user.timezone)
    today = datetime.now(tz)
    # Determine if next birthday is in current year or next year
    if today.month > month or (today.month == month and today.day >= day):
        next_birthday_year = today.year + 1
    else:
        next_birthday_year = today.year
    birthday_local = tz.normalize(tz.localize(datetime(next_birthday_year, month, day)))
    # Convert back to utc
    birthday_utc = birthday_local.astimezone(pytz.utc)
    return birthday_utc


# Automatic Birthday Notification
@plugin.periodic_task(timedelta(minutes=15))
async def birthday_reminder(app: lightbulb.BotApp):
    async with tortoise.transactions.in_transaction() as tx:
        members = GuildMember.select_for_update().using_db(tx).filter(
            guild_id__in=app.default_enabled_guilds,
            next_birthday_utc__lte=datetime.now(pytz.utc),
        )
        async for member in members:
            channel_id = await values.profile_birthday_channel.get_value(member.guild_id)
            if not channel_id:
                continue
            user = app.cache.get_member(member.guild_id, member.user_id)
            channel = app.cache.get_guild_channel(channel_id)
            if not user or not channel:
                continue
            try:
                member.next_birthday_utc = await _get_next_birthday_utc(
                    member.user_id, member.birthday_month, member.birthday_day)
                await channel.send(f"🎂 **Happy birthday, {user.mention}!** 🎂", user_mentions=True)
            except UserError:
                logger.warning(f'Birthday: did not send birthday note for {member} '
                               'because they do not have a timezone.')
            except hikari.ClientHTTPResponseError:
                logger.exception(f'Birthday: Failed to send birthday message for {member}.')
            await member.save(using_db=tx)


def _recursive_set_dict(d: dict, keys: Sequence[str], value: Any):
    if len(keys) == 1:
        d[keys[0]] = value
    else:
        d = d.setdefault(keys[0], {})
        _recursive_set_dict(d, keys[1:], value)


def _recursive_del_dict(d: dict, keys: Sequence[str]):
    if len(keys) == 1:
        del d[keys[0]]
    else:
        _recursive_del_dict(d[keys[0]], keys[1:])
        if not d[keys[0]]:
            del d[keys[0]]


load, unload = plugin.export_extension()
