import logging
from datetime import datetime, timedelta

import discord
import tortoise
from discord.ext.tasks import loop
from tortoise import Tortoise

from dingomata.cogs.base import BaseCog
from dingomata.config.bot import service_config
from dingomata.config.cogs import ManagedRoleConfig
from dingomata.decorators import user_command
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
        if config.min_days and joined + timedelta(days=config.min_days) > datetime.now(tz=joined.tzinfo):
            return f'member has not yet been in the server for {config.min_days} days.'
        metrics = await MessageMetric.get_or_none(guild_id=self._member.guild.id, user_id=self._member.id)
        if (
                not metrics
                or metrics.distinct_days < config.min_active_days
                or metrics.message_count < config.min_messages
        ):
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

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)
        self._connection: tortoise.BaseDBAsyncClient = None

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self._connection = Tortoise.get_connection("default")
        self.auto_role_removal.start()

    def cog_unload(self) -> None:
        self.auto_role_removal.stop()

    @user_command(name="Assign Role", default_available=False, config_group="roles")
    async def add(self, ctx: discord.ApplicationContext, member: discord.Member) -> None:
        """Add a role to a user."""
        view = RoleSelectView(member)
        interaction = await ctx.respond(f'Select a role to add for {member.display_name}:', view=view, ephemeral=True)
        await view.wait()
        await interaction.delete_original_response()

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """If the user is missing any roles that require metrics, log those metrics."""
        if (
                message.guild
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
                await member.remove_roles(role, reason='Automatic role expiration')
                await task.delete(using_db=tx)
