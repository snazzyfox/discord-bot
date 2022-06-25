import logging

import discord

from dingomata.cogs.base import BaseCog
from dingomata.config import service_config
from dingomata.decorators import slash_group

_log = logging.getLogger(__name__)


class RoleListDropdown(discord.ui.Select):
    def __init__(self, bot: discord.Bot, guild: discord.Guild):
        role_options = service_config.server[guild.id].self_assign_roles.__root__
        self._bot = bot
        options = [
            discord.SelectOption(label=guild.get_role(opt.id).name, value=str(opt.id),
                                 description=opt.description, emoji=opt.emoji)
            for opt in role_options
        ]
        super().__init__(
            placeholder="Select a role to give or remove from yourself.",
            options=options,
            min_values=0,
            custom_id=f"roles:{guild.id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values:
            selected_role_id = int(self.values[0])
            if role := interaction.user.get_role(selected_role_id):
                # User has role, remove it
                await interaction.user.remove_roles(role, reason='Requested via bot dropdown')
                await interaction.response.send_message(f"You have removed the {role.name} role.", ephemeral=True)
            else:
                role = interaction.guild.get_role(selected_role_id)
                await interaction.user.add_roles(role, reason='Requested via bot dropdown')
                await interaction.response.send_message(f"You have added the {role.name} role.", ephemeral=True)
        else:
            await interaction.response.defer()


class RoleListView(discord.ui.View):
    def __init__(self, bot: discord.Bot, guild: discord.Guild):
        super().__init__(timeout=None)
        self.add_item(RoleListDropdown(bot, guild))


class RolePickerCog(BaseCog):
    roles = slash_group(name="roles", description='Manage roles')

    @roles.command()
    async def post_list(self, ctx: discord.ApplicationContext):
        await ctx.channel.send(view=RoleListView(self._bot, ctx.guild))
        await ctx.respond("All done.", ephemeral=True)

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        if not any(isinstance(view, RoleListView) for view in self._bot.persistent_views):
            for guild in self._bot.guilds:
                self._bot.add_view(RoleListView(self._bot, guild))
