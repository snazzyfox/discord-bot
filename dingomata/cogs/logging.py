import logging
from typing import List

import discord

from dingomata.config.bot import service_config

_log = logging.getLogger(__name__)


class LoggingCog(discord.Cog):
    """Message logging."""

    def __init__(self, bot: discord.Bot):
        self._bot = bot

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
        log_channel = service_config.server[message.guild.id].logging.log_channel
        if log_channel:
            embed = discord.Embed(title='Message deleted.')
            embed.add_field(name='Channel', value=message.channel.mention)
            embed.add_field(name='Author', value=message.author.mention)
            embed.add_field(name='Sent At', value=f'<t:{int(message.created_at.timestamp())}:f>')
            embed.add_field(name='Content', value=message.content, inline=False)
            await self._bot.get_channel(log_channel).send(embed=embed)
