import logging
from typing import List

import discord

from dingomata.cogs.base import BaseCog
from dingomata.config.bot import service_config

_log = logging.getLogger(__name__)


class LoggingCog(BaseCog):
    """Message logging."""

    @discord.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if service_config.server[message.guild.id].logging.message_deleted:
            await self._log_deleted_message(message)

    @discord.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]) -> None:
        if service_config.server[messages[0].guild.id].logging.message_deleted:
            for message in messages:
                await self._log_deleted_message(message)

    async def _log_deleted_message(self, message: discord.Message) -> None:
        """Send a message to the log channel with the deleted message."""
        if message.author.bot:
            return
        log_channel = service_config.server[message.guild.id].logging.log_channel
        if log_channel:
            embed = discord.Embed(title='Message deleted.')
            embed.add_field(name='Channel', value=message.channel.mention)
            embed.add_field(name='Author', value=message.author.mention)
            embed.add_field(name='Sent At', value=f'<t:{int(message.created_at.timestamp())}:f>')
            embed.add_field(name='Content', value=message.clean_content, inline=False)
            await self._bot_for(message.guild.id).get_channel(log_channel).send(embed=embed)
