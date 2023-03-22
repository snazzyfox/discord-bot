import logging
from datetime import datetime, timedelta
from typing import Tuple

import discord
import tortoise
from discord.ext.tasks import loop
from tortoise import Tortoise

from dingomata.cogs.base import BaseCog
from dingomata.config.bot import service_config
from dingomata.config.cogs import ManagedRoleConfig
from dingomata.decorators import slash_group, slash_subgroup, user_command
from dingomata.exceptions import DingomataUserError
from dingomata.models import MessageMetric, ScheduledTask, TaskType

_log = logging.getLogger(__name__)


class RoleListDropdown(discord.ui.Select):
    __slots__ = ('_member',)

    def __init__(self, member: discord.Member):
        guild = member.guild
        role_options = [guild.get_role(role.id) for role in service_config.server[guild.id].role_manage.roles]
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in role_options]
        super().__init__(
            placeholder="Select a role",
            options=options,
            min_values=1,
            max_values=1,
        )
        self._member = member

    async def callback(self, interaction: discord.Interaction):
        role = self._member.guild.get_role(int(self.values[0]))
        config = next(rule for rule in service_config.server[self._member.guild.id].role_manage.roles
                      if rule.id == role.id)
        if role in self._member.roles:
            # Check that the user does not already have that role
            await interaction.response.send_message(
                f'{self._member.display_name} already has the {role.name} role.',
                ephemeral=True,
            )
        elif reason := await self._member_eligible(config):
            await interaction.response.send_message(
                f'{self._member.display_name} is not eligible for role {role.name} because {reason}',
                ephemeral=True,
            )
        else:
            await self._member.add_roles(role, reason=f'Requested by {interaction.user} via bot')
            response = f'Role {role.name} has been added to {self._member.display_name}. '
            if config.remove_after_hours:
                expiration = datetime.now() + timedelta(hours=config.remove_after_hours)
                await ScheduledTask(guild_id=self._member.guild.id, task_type=TaskType.REMOVE_ROLE,
                                    process_after=expiration, payload={'role': role.id, 'user': self._member.id}).save()
                response += f'It will be automatically removed around <t:{int(expiration.timestamp())}:f>.'
            await interaction.response.send_message(response, ephemeral=True)
        self.view.stop()

    async def _member_eligible(self, config: ManagedRoleConfig) -> str | None:
        joined = self._member.joined_at
        if joined + timedelta(days=config.min_days) > datetime.now(tz=joined.tzinfo):
            return f'member has not yet been in the server for {config.min_days} days.'
        metrics, _ = await MessageMetric.get_or_create(guild_id=self._member.guild.id, user_id=self._member.id)
        if metrics.distinct_days < config.min_active_days or metrics.message_count < config.min_messages:
            return 'member does not meet the minimum activity requirement.'
        return None


class RoleSelectView(discord.ui.View):
    __slots__ = ('result',)

    def __init__(self, member: discord.Member):
        super().__init__()
        self.add_item(RoleListDropdown(member))


class RoleManageCog(BaseCog):
    """Role management."""
    _counting_query = """
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
"""
    __slots__ = '_connection',
    _INTERACTION_ID = 'self_assign_role'
    roles = slash_group(name="roles", description='Manage roles')
    dropdown = slash_subgroup(roles, name="dropdown", description='Manage role dropdowns')

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)
        self._connection: tortoise.BaseDBAsyncClient = None

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self._connection = Tortoise.get_connection("default")
        self.auto_role_removal.start()

    @discord.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.is_component() and interaction.custom_id == self._INTERACTION_ID:
            if values := interaction.data.get('values'):
                selected_role_id = int(values[0])
                if role := interaction.user.get_role(selected_role_id):
                    # User has role, remove it
                    await interaction.user.remove_roles(role, reason='Requested via bot dropdown')
                    await interaction.response.send_message(f"You have removed the {role.name} role.",
                                                            ephemeral=True)
                else:
                    role = interaction.guild.get_role(selected_role_id)
                    await interaction.user.add_roles(role, reason='Requested via bot dropdown')
                    await interaction.response.send_message(f"You have added the {role.name} role.", ephemeral=True)
            else:
                # nothing selected in dropdown
                await interaction.response.defer()

    def cog_unload(self) -> None:
        self.auto_role_removal.stop()

    # User role assignment
    @user_command(name="Assign Role", default_available=False, config_group="roles")
    async def add(self, ctx: discord.ApplicationContext, member: discord.Member) -> None:
        """Add a role to a user."""
        view = RoleSelectView(member)
        interaction = await ctx.respond(f'Select a role to add for {member.display_name}:', view=view, ephemeral=True)
        await view.wait()
        await interaction.delete_original_response()

    @dropdown.command(name='create')
    @discord.option('title', description='Title text for the dropdown')
    @discord.option('role', description='The first role to add as an option')
    @discord.option('description', description='Optional description of the role to add as an option', type=str)
    @discord.option('emoji', description='Optional emoji to show next to the role', type=str)
    async def dropdown_create(self, ctx: discord.ApplicationContext, title: str, role: discord.Role,
                              description: str | None = None, emoji: str | None = None) -> None:
        """Create a new role dropdown in the current channel."""
        if role >= ctx.user.top_role:
            raise DingomataUserError('You can only add roles below your highest role to the list. If you need to add '
                                     'something higher, please ask a user with higher access.')
        view = discord.ui.View(timeout=None)
        dropdown = discord.ui.Select(placeholder=title, options=[], min_values=0, custom_id=self._INTERACTION_ID)
        dropdown.add_option(label=role.name, description=description, value=str(role.id), emoji=emoji)
        view.add_item(dropdown)
        try:
            message = await ctx.channel.send(view=view)
        except discord.HTTPException as e:
            if 'Invalid emoji' in e.text:
                raise DingomataUserError(f'{emoji} is not a valid emoji.')
            raise
        await ctx.respond(f'Done. The sent message URL is: `{message.jump_url}`. You can use it to add more options '
                          f'to the dropdown. You can also get this url by right clicking the message and choosing '
                          f'"Copy Messgae Link".', ephemeral=True)

    @dropdown.command(name='add')
    @discord.option('dropdown_url', description='Message URL to a message with dropdown')
    @discord.option('role', description='The role to add to the dropdown')
    @discord.option('description', description='Optional description of the role to add as an option', type=str)
    @discord.option('emoji', description='Optional emoji to show next to the role', type=str)
    async def dropdown_add(self, ctx: discord.ApplicationContext, dropdown_url: str, role: discord.Role,
                           description: str | None = None, emoji: str | None = None) -> None:
        """Add a role to an existing role dropdown."""
        message, view, dropdown = await self._get_existing_dropdown(ctx, dropdown_url)
        if role >= ctx.user.top_role:
            raise DingomataUserError('You can only add roles below your highest role to the list. If you need to add '
                                     'something higher, please ask a user with higher access.')

        # Make sure the role is not already one of the options
        if any(int(option.value) == role.id for option in dropdown.options):
            raise DingomataUserError('This role is already an option in the dropdown.')
        if len(dropdown.options) >= 25:
            raise DingomataUserError('Discord only allows up to 25 options per dropdown. Please create a new dropdown.')

        # Actually add it to the dropdown
        dropdown.add_option(label=role.name, value=str(role.id), description=description, emoji=emoji)
        try:
            await message.edit(view=view)
        except discord.HTTPException as e:
            if 'Invalid emoji' in e.text:
                raise DingomataUserError(f'{emoji} is not a valid emoji.')
            raise
        await ctx.respond(f'Role {role} has been added to the dropdown.', ephemeral=True)

    @dropdown.command(name='remove')
    @discord.option('dropdown_url', description='Message URL to a message with dropdown')
    @discord.option('role', description='The role to remove from the dropdown')
    async def dropdown_remove(self, ctx: discord.ApplicationContext, dropdown_url: str, role: discord.Role) -> None:
        """Remove a role from a dropdown."""
        message, view, old_dropdown = await self._get_existing_dropdown(ctx, dropdown_url)
        if role >= ctx.user.top_role:
            raise DingomataUserError('You can only change roles below your highest role in the list. If you need to '
                                     'modify something higher, please ask a user with higher access.')

        if not any(int(option.value) == role.id for option in old_dropdown.options):
            raise DingomataUserError('This role is not one of the options in the dropdown.')

        # There's no function to remove options from a select. Build a new one instead
        new_dropdown = discord.ui.Select(
            placeholder=old_dropdown.placeholder,
            options=[option for option in old_dropdown.options if int(option.value) != role.id],
            min_values=old_dropdown.min_values,
            custom_id=self._INTERACTION_ID)

        view.remove_item(old_dropdown)
        view.add_item(new_dropdown)
        await message.edit(view=view)
        await ctx.respond(f'Role {role} has been removed from the dropdown.', ephemeral=True)

    async def _get_existing_dropdown(self, ctx: discord.ApplicationContext, message_url: str,
                                     ) -> Tuple[discord.Message, discord.ui.View, discord.ui.Select]:
        # Input data checks
        try:
            guild_id, channel_id, message_id = message_url[29:].split('/')
        except ValueError:
            raise DingomataUserError('The dropdown URL you provided does not appear to be a valid message link.')
        if int(guild_id) != ctx.guild.id:
            raise DingomataUserError('The dropdown URL does not appear to link to a message I have access to edit.')
        channel = ctx.guild.get_channel(int(channel_id))
        if not channel:
            raise DingomataUserError('The dropdown URL does not appear to link to a message I have access to edit.')
        try:
            message = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            raise DingomataUserError('The dropdown URL does not appear to link to a message I have access to edit.')
        if message.author != ctx.bot.user:
            raise DingomataUserError('The dropdown URL does not appear to link to a message I have access to edit.')

        # Grab the original view
        view = discord.ui.View.from_message(message)
        dropdown = view.get_item(self._INTERACTION_ID)
        if not isinstance(dropdown, discord.ui.Select):
            raise DingomataUserError('There does not appear to be a role selection dropdown in this message.')
        return message, view, dropdown

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """If the user is missing any roles that require metrics, log those metrics."""
        if (
                message.guild and isinstance(message.author, discord.Member)
                and any(message.author.get_role(role.id) is None
                        and (role.min_messages or role.min_days or role.min_active_days)
                        for role in service_config.server[message.guild.id].role_manage.roles)
                and message.clean_content
        ):
            await self._connection.execute_query(self._counting_query, [message.guild.id, message.author.id])

    @loop(minutes=5)
    async def auto_role_removal(self):
        async with tortoise.transactions.in_transaction() as tx:
            tasks = await ScheduledTask.select_for_update().using_db(tx).filter(
                guild_id__in=[guild.id for guild in self._bot.guilds],
                task_type=TaskType.REMOVE_ROLE,
                process_after__lte=datetime.now(),
            ).all()
            for task in tasks:
                guild = self._bot.get_guild(task.guild_id)
                member = guild.get_member(task.payload['user'])
                role = guild.get_role(task.payload['role'])
                try:
                    await member.remove_roles(role, reason='Automatic role expiration')
                except discord.HTTPException:
                    _log.exception(f'Scheduled Task: Failed to remove role {task}')
                await task.delete(using_db=tx)
