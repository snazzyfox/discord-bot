import logging

import discord
import tortoise

from dingomata.cogs.base import BaseCog
from dingomata.config import service_config
from dingomata.decorators import slash_group
from dingomata.models import BotMessages

_log = logging.getLogger(__name__)


class RoleListDropdown(discord.ui.Select):
    __slots__ = '_bot',

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
    _MSG_TYPE = 'ROLE_PICKER'
    roles = slash_group(name="roles", description='Manage roles')

    @roles.command()
    async def post_list(self, ctx: discord.ApplicationContext):
        async with tortoise.transactions.in_transaction() as tx:
            bot_message = await BotMessages.get_or_none(id=f'{self._MSG_TYPE}:{ctx.guild.id}')
            if bot_message:
                # Delete and repost
                try:
                    message = ctx.guild.get_channel(bot_message.channel_id).get_partial_message(bot_message.message_id)
                    await message.delete()
                except discord.NotFound:
                    pass  # already deleted externally
            new_message = await ctx.channel.send(view=RoleListView(self._bot, ctx.guild))
            bot_message = BotMessages(
                id=f'{self._MSG_TYPE}:{ctx.guild.id}',
                channel_id=new_message.channel.id,
                message_id=new_message.id,
            )
            await bot_message.save(using_db=tx)
        await ctx.respond("All done.", ephemeral=True)

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        known_messages = await BotMessages.filter(id__startswith=f'{self._MSG_TYPE}:').all()
        for bot_message in known_messages:
            guild_id = int(bot_message.id.split(':', 1)[1])
            if guild := self._bot.get_guild(guild_id):
                try:
                    message = self._bot.get_channel(bot_message.channel_id).get_partial_message(bot_message.message_id)
                    await message.edit(view=RoleListView(self._bot, guild))
                except discord.NotFound:
                    pass

    @discord.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        # Rewrite the dropdown if a role gets updated
        if bot_message := await BotMessages.get_or_none(id=f'{self._MSG_TYPE}:{after.guild.id}'):
            try:
                message = self._bot.get_channel(bot_message.channel_id).get_partial_message(bot_message.message_id)
                await message.edit(view=RoleListView(self._bot, after.guild))
            except discord.NotFound:
                pass
