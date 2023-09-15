import asyncio
import logging
from datetime import datetime, timedelta

import hikari
import lightbulb
import tortoise
import tortoise.transactions
from async_lru import alru_cache
from hikari import undefined
from lightbulb.ext import tasks

from dingomata.config import values
from dingomata.config.provider import cached_config
from dingomata.database.models import MessageMetric, ScheduledTask, TaskType
from dingomata.exceptions import UserError
from dingomata.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('roles')
_MOD_DROPDOWN_PREFIX = 'roles:mod_assign:'
_SELF_DROPDOWN_PREFIX = 'roles:self_assign:'
_enabled_guilds = (768208778780475447, 970811039635628072)


@plugin.command
@lightbulb.command("roles", description="Manage roles", guilds=_enabled_guilds)
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def roles_group(ctx: lightbulb.SlashContext) -> None:
    pass


@roles_group.child
@lightbulb.command("dropdown", description="Manage role dropdowns")
@lightbulb.implements(lightbulb.SlashSubGroup)
async def roles_dropdown_group(ctx: lightbulb.SlashContext) -> None:
    pass


@plugin.command
@lightbulb.command("Assign Role", description="Add a role for a user.", guilds=_enabled_guilds, ephemeral=True)
@lightbulb.implements(lightbulb.UserCommand)
async def assign_role(ctx: lightbulb.UserContext) -> None:
    component = ctx.app.rest.build_message_action_row()
    dropdown = component.add_text_menu(
        _MOD_DROPDOWN_PREFIX + str(ctx.options.target.id),
        placeholder='Select a role to add',
        min_values=1,
    )
    mod_addable_roles = await values.roles_mod_add.get_value(ctx.guild_id) or []
    for role_id in mod_addable_roles:
        role = ctx.app.cache.get_role(role_id)
        dropdown.add_option(role.name, str(role.id))
    await ctx.respond(
        content=f'Select a role to add for {ctx.options.target.display_name}',
        component=component,
    )


@roles_dropdown_group.child
@lightbulb.option('emoji', description='Optional emoji to show next to the role', type=str, default=None)
@lightbulb.option('description', description='Optional description of the role to add as an option', type=str,
                  default=None)
@lightbulb.option('role', description='The first role to add as an option', type=hikari.Role)
@lightbulb.option('title', description='Title text for the dropdown')
@lightbulb.command('create', description="Create a new role dropdown in the current channel.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def roles_dropdown_create(ctx: lightbulb.SlashContext) -> None:
    if ctx.options.role.position >= ctx.member.get_top_role().position:
        raise UserError('You can only add roles below your highest role to the list. If you need to add '
                        'something higher, please ask a user with higher access.')
    component = ctx.app.rest.build_message_action_row()
    dropdown = component.add_text_menu(
        _SELF_DROPDOWN_PREFIX + str(ctx.options.role.id),
        placeholder=ctx.options.title,
        min_values=0,
    )
    dropdown.add_option(
        ctx.options.role.name, str(ctx.options.role.id),
        description=ctx.options.description or undefined.UNDEFINED,
        emoji=ctx.options.emoji or undefined.UNDEFINED,
    )
    try:
        channel: hikari.GuildTextChannel = ctx.get_channel()
        message = await channel.send(component=component)
    except hikari.ForbiddenError:
        raise UserError("I don't have permissions to post in this channel.")
    except hikari.ClientHTTPResponseError as e:
        if 'Invalid emoji' in e.message:
            raise UserError(f'{ctx.options.emoji} is not a valid emoji.')
        raise
    await ctx.respond(f'Done. The sent message URL is: `{message.make_link(channel.guild_id)}`. '
                      f'You can use it to add more options to the dropdown. You can also get this url by right '
                      f'clicking the message and choosing Copy Messgae Link".')


@roles_dropdown_group.child
@lightbulb.option('emoji', description='Optional emoji to show next to the role', type=str, default=None)
@lightbulb.option('description', description='Optional description of the role to add as an option', type=str,
                  default=None)
@lightbulb.option('dropdown_url', description='URL to an existing message with dropdown')
@lightbulb.option('role', description='The role to add as an option', type=hikari.Role)
@lightbulb.command('add', description="Add a role to an existing role dropdown.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def roles_dropdown_add(ctx: lightbulb.SlashContext) -> None:
    if ctx.options.role.position >= ctx.member.get_top_role().position:
        raise UserError('You can only add roles below your highest role to the list. If you need to add '
                        'something higher, please ask a user with higher access.')

    # Extract existing options
    message, dropdown = await _get_existing_dropdown(ctx, ctx.options.dropdown_url)
    # Make sure the role is not already one of the options
    if any(int(option.value) == ctx.options.role.id for option in dropdown.options):
        raise UserError('This role is already an option in the dropdown.')
    if len(dropdown.options) >= 25:
        raise UserError('Discord only allows up to 25 options per dropdown. Please create a new dropdown.')

    component = ctx.app.rest.build_message_action_row()
    new_dropdown = component.add_text_menu(
        _SELF_DROPDOWN_PREFIX + str(ctx.options.role.id),
        placeholder=dropdown.placeholder,
        min_values=dropdown.min_values,
    )
    for option in dropdown.options:
        new_dropdown.add_option(
            option.label, option.value, description=option.description or undefined.UNDEFINED,
            emoji=option.emoji or undefined.UNDEFINED,
        )
    new_dropdown.add_option(
        ctx.options.role.name, str(ctx.options.role.id),
        description=ctx.options.description or undefined.UNDEFINED,
        emoji=ctx.options.emoji or undefined.UNDEFINED,
    )
    try:
        await message.edit(component=component)
    except hikari.ClientHTTPResponseError as e:
        if 'Invalid emoji' in e.message:
            raise UserError(f'{ctx.options.emoji!r} is not a valid emoji.')
        raise
    await ctx.respond(f'Role {ctx.options.role.name} has been added to the dropdown.')


@roles_dropdown_group.child
@lightbulb.option('dropdown_url', description='URL to an existing message with dropdown')
@lightbulb.option('role', description='The role to remove as an option', type=hikari.Role)
@lightbulb.command('remove', description="Add a role to an existing role dropdown.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def roles_dropdown_remove(ctx: lightbulb.SlashContext) -> None:
    if ctx.options.role.position >= ctx.member.get_top_role().position:
        raise UserError('You can only add roles below your highest role to the list. If you need to add '
                        'something higher, please ask a user with higher access.')

    # Extract existing options
    message, dropdown = await _get_existing_dropdown(ctx, ctx.options.dropdown_url)
    # Make sure the role is one of the options
    if not any(int(option.value) == ctx.options.role.id for option in dropdown.options):
        raise UserError('This role is not one of the options in the dropdown.')
    if len(dropdown.options) <= 1:
        raise UserError('This is the last item in the dropdown. Add another one first, or delete the entire dropdown.')

    component = ctx.app.rest.build_message_action_row()
    new_dropdown = component.add_text_menu(
        _SELF_DROPDOWN_PREFIX + str(ctx.options.role.id),
        placeholder=dropdown.placeholder,
        min_values=dropdown.min_values,
    )
    for option in dropdown.options:
        if int(option.value) != ctx.options.role.id:
            new_dropdown.add_option(
                option.label, option.value, description=option.description or undefined.UNDEFINED,
                emoji=option.emoji or undefined.UNDEFINED,
            )
    try:
        await message.edit(component=component)
    except hikari.ClientHTTPResponseError as e:
        if 'Invalid emoji' in e.message:
            raise UserError(f'{ctx.options.emoji!r} is not a valid emoji.')
        raise
    await ctx.respond(f'Role {ctx.options.role.name} has been removed from the dropdown.')


async def _get_existing_dropdown(
    ctx: lightbulb.SlashContext, message_url: str,
) -> tuple[hikari.Message, hikari.TextSelectMenuComponent]:
    # Input data checks
    try:
        guild_id, channel_id, message_id = message_url[29:].split('/')
    except ValueError:
        raise UserError('The dropdown URL you provided does not appear to be a valid message link.')
    try:
        if int(guild_id) != ctx.guild_id:
            raise ValueError()
        channel: hikari.GuildTextChannel = ctx.get_guild().get_channel(int(channel_id))
        if not channel:
            raise ValueError()
        try:
            message = await channel.fetch_message(int(message_id))
        except hikari.NotFoundError:
            raise ValueError()
        if message.author.id != ctx.bot.get_me().id:
            raise ValueError()
    except ValueError:
        raise UserError('The dropdown URL does not appear to link to a message I have access to edit.')
    if (
        len(message.components) != 1
        or len(row := message.components[0].components) != 1
        or not isinstance(dropdown := row[0], hikari.TextSelectMenuComponent)
        or not dropdown.custom_id.startswith(_SELF_DROPDOWN_PREFIX)
    ):
        raise UserError('The dropdown URL does not appear to point to a message with a self-add role dropdown.')
    return message, dropdown


@cached_config
@alru_cache(24)
async def _get_managed_tracked_roles(guild_id: int) -> set[int]:
    managed_roles = await values.roles_mod_add.get_value(guild_id) or []
    tracked_roles = set()
    for role in managed_roles:
        if (
            await values.roles_mod_add_min_messages.get_value(guild_id, str(role))
            or await values.roles_mod_add_min_days_active.get_value(guild_id, str(role))
            or await values.roles_mod_add_min_days_in_guild.get_value(guild_id, str(role))
        ):
            tracked_roles.add(role)
    return tracked_roles


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_message(event: hikari.GuildMessageCreateEvent) -> None:
    """If the user is missing any roles that require metrics, log those metrics."""
    if event.guild_id not in _enabled_guilds:
        return
    tracked = await _get_managed_tracked_roles(event.guild_id)
    if (
        tracked
        and event.member
        and event.content
        and any(role_id not in event.member.role_ids for role_id in tracked)
    ):
        connection = tortoise.Tortoise.get_connection("default")
        await connection.execute_query("""
INSERT INTO message_metrics (guild_id, user_id, message_count, distinct_days, last_distinct_day_boundary)
VALUES ($1, $2, 1, 1, CURRENT_TIMESTAMP)
ON CONFLICT (guild_id, user_id) DO UPDATE SET
message_count = message_metrics.message_count + 1,
distinct_days = CASE
  WHEN CURRENT_TIMESTAMP - message_metrics.last_distinct_day_boundary > INTERVAL '1 day'
  THEN message_metrics.distinct_days + 1
  ELSE message_metrics.distinct_days END,
last_distinct_day_boundary = CASE
  WHEN CURRENT_TIMESTAMP - message_metrics.last_distinct_day_boundary > INTERVAL '1 day'
  THEN CURRENT_TIMESTAMP
  ELSE message_metrics.last_distinct_day_boundary END;
""", [event.guild_id, event.member.id])


@plugin.listener(hikari.InteractionCreateEvent)
async def on_component_interaction(event: hikari.InteractionCreateEvent) -> None:
    # Handle dropdown
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    if event.interaction.custom_id.startswith(_MOD_DROPDOWN_PREFIX):
        user_id = int(event.interaction.custom_id.removeprefix(_MOD_DROPDOWN_PREFIX))
        member = event.interaction.get_guild().get_member(user_id)
        role_id = int(event.interaction.values[0])
        role = event.interaction.get_guild().get_role(role_id)
        if role_id in member.role_ids:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                f'{member.display_name} already has the {role.name} role.',
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        elif role.position > event.interaction.member.get_top_role().position:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                "You cannot give someone access to a role that's higher than your top role.",
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        elif reason := await _member_ineligible_reason(member, role_id):
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                f"{member.display_name} is not eligible for role {role.name} because {reason}.",
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        else:
            await member.add_role(role, reason=f'Requested by {event.interaction.member.display_name} via bot.')
            response = f'Role {role.name} has been added to {member.display_name}. '
            if remove_after := await values.roles_mod_add_remove_after_hours.get_value(
                event.interaction.guild_id,
                str(role_id)
            ):
                expiration = datetime.now() + timedelta(hours=remove_after)
                await ScheduledTask(
                    guild_id=member.guild_id,
                    task_type=TaskType.REMOVE_ROLE,
                    process_after=expiration,
                    payload={'role': role.id, 'user': member.id}
                ).save()
                response += f'It will be automatically removed around <t:{int(expiration.timestamp())}:f>.'
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                response,
                flags=hikari.MessageFlag.EPHEMERAL,
            )
    elif event.interaction.custom_id.startswith(_SELF_DROPDOWN_PREFIX):
        if event.interaction.values:
            role_id = int(event.interaction.values[0])
            if role_id in event.interaction.member.role_ids:
                # User has role, remove it
                role = event.interaction.get_guild().get_role(role_id)
                await event.interaction.member.remove_role(role_id, reason="Requested via bot")
                await event.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE,
                    f"You have removed the {role.name} role.",
                    flags=hikari.MessageFlag.EPHEMERAL,
                )
            else:
                # User doesn't have role, add it
                role = event.interaction.get_guild().get_role(role_id)
                await event.interaction.member.add_role(role_id, reason="Requested via bot")
                await event.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE,
                    f"You have add the {role.name} role.",
                    flags=hikari.MessageFlag.EPHEMERAL,
                )
        else:
            await event.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def _member_ineligible_reason(member: hikari.Member, desired_role_id: int) -> str | None:
    """Returns the reason why someone's not eligible, or None if eligible."""
    min_days = await values.roles_mod_add_min_days_in_guild.get_value(member.guild_id, str(desired_role_id))
    if min_days and member.joined_at + timedelta(days=min_days) > datetime.now(tz=member.joined_at.tzinfo):
        logger.info('Refused to assign role: guild %s, member %s, role %s. Joined time %s failed min_days %s',
                    member.guild_id, member.id, desired_role_id, member.joined_at, min_days)
        return f'member has not yet been in the server for {min_days} days.'
    metrics, _ = await MessageMetric.get_or_create(guild_id=member.guild_id, user_id=member.id)
    min_active, min_messages = await asyncio.gather(
        values.roles_mod_add_min_days_active.get_value(member.guild_id, str(desired_role_id)),
        values.roles_mod_add_min_messages.get_value(member.guild_id, str(desired_role_id)),
    )
    if metrics.distinct_days < (min_active or 0) or metrics.message_count < (min_messages or 0):
        logger.info('Refused to assign role: guild %s, member %s, role %s. Metrics %s failed '
                    'min_active_days %s, min_messages %s',
                    member.guild_id, member.id, desired_role_id, metrics, min_active, min_messages)
        return 'Member does not meet the minimum activity requirement.'
    return None


@tasks.task(m=5, auto_start=True, pass_app=True)
async def auto_role_removal(app: lightbulb.BotApp):
    async with tortoise.transactions.in_transaction() as tx:
        records = await ScheduledTask.select_for_update().using_db(tx).filter(
            guild_id__in=app.default_enabled_guilds,
            task_type=TaskType.REMOVE_ROLE,
            process_after__lte=datetime.now(),
        ).all()
        for task in records:
            member = app.cache.get_member(task.guild_id, task.payload['user'])
            try:
                await member.remove_role(task.payload['role'], reason='Automatic role expiration')
                logger.info('Scheduled Task: Removed role %s', task)
            except hikari.ClientHTTPResponseError:
                logger.exception('Scheduled Task: Failed to remove role %s', task)
            await task.delete(using_db=tx)


load, unload = plugin.export_extension()
