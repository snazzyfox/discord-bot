import asyncio
import logging

import discord

from dingomata.cogs.base import BaseCog
from dingomata.config.bot import service_config

_log = logging.getLogger(__name__)


class LoggingCog(BaseCog):
    """Message logging."""

    @discord.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild and service_config.server[message.guild.id].logging.message_deleted:
            await self._log_message('Message deleted', message)

    @discord.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        if service_config.server[messages[0].guild.id].logging.message_deleted:
            for message in messages:
                await self._log_message('Message deleted', message)

    @discord.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.guild and service_config.server[after.guild.id].logging.message_edited:
            if before.content != after.content:
                # This also triggers for embed add/changes, pins, etc
                await self._log_message('Message edited', before, after)

    async def _log_message(self, title: str, message: discord.Message, edited: discord.Message | None = None) -> None:
        """Send a message to the log channel with the deleted message."""
        if message.author.bot or not message.content:
            return
        log_channel = service_config.server[message.guild.id].logging.log_channel
        if log_channel:
            embed = discord.Embed(title=title, color=discord.Color.yellow())
            embed.add_field(name='Channel', value=message.channel.mention)
            embed.add_field(name='Author', value=message.author.mention)
            embed.add_field(name='Sent At', value=f'<t:{int(message.created_at.timestamp())}:f>')
            embed.add_field(name='Message URL (for T&S Reports)', value=message.jump_url)
            embed.add_field(name='Content', value=message.clean_content, inline=False)
            if edited:
                embed.add_field(name='Changed to', value=edited.clean_content, inline=False)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await self._bot_for(message.guild.id).get_channel(log_channel).send(embed=embed)

    @discord.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if service_config.server[guild.id].logging.user_banned:
            if log_channel := service_config.server[guild.id].logging.log_channel:
                try:
                    await asyncio.sleep(1)  # Wait a second for discord audit logs to catch up
                    audits = guild.audit_logs(limit=20, action=discord.AuditLogAction.ban)
                    async for audit in audits:
                        if audit.target == user:
                            embed = discord.Embed(title=f'{user.display_name} was banned.', color=discord.Color.red())
                            embed.add_field(name='User', value=user.mention)
                            embed.add_field(name='Banned by', value=audit.user)
                            embed.add_field(name='Reason', value=audit.reason)
                            embed.set_thumbnail(url=user.display_avatar.url)
                            await self._bot_for(guild.id).get_channel(log_channel).send(embed=embed)
                            return
                except discord.Forbidden:
                    _log.warning(f'User {user} was banned from guild {guild}, but no notification was sent because '
                                 f'the bot is missing permissions.')
