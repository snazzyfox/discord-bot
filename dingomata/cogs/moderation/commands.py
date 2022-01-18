import logging
import re

from discord import Message, Embed, Member
from discord.ext.commands import Bot, Cog
from sqlalchemy.ext.asyncio import AsyncEngine

from dingomata.config.config import service_config

_log = logging.getLogger(__name__)


class ModerationCommandsCog(Cog, name='Moderation'):
    """Message filtering."""
    _URL_REGEX = re.compile(r'\bhttps?://')
    _SCAM_KEYWORD_REGEX = re.compile(r'\bfree|gift|nitro|subscription', re.IGNORECASE)

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self._check_likely_discord_scam(message)

    @Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        await self._check_likely_discord_scam(after)

    async def _check_likely_discord_scam(self, message: Message):
        reasons = []
        if message.guild.default_role.mention in message.content or '@everyone' in message.content:
            reasons.append('Mentions at-everone')
        if bool(self._URL_REGEX.search(message.content)):
            reasons.append('Includes URL')
        if self._SCAM_KEYWORD_REGEX.search(message.content):
            reasons.append('Message content includes scam keyword(s)')
        if self._search_embeds(self._SCAM_KEYWORD_REGEX, message):
            reasons.append('Embed content includes scam keyword(s)')

        if len(reasons) >= 2 and not self._is_mod(message.author):
            # Consider the message scam likely if two of the three matches
            _log.info(f'Deleting message from {message.author}. Reason: {reasons}. '
                      f'Original message: {message.content}')
            log_channel = service_config.servers[message.guild.id].moderation.log_channel
            if log_channel:
                embed = Embed(
                    title='Likely scam message detected.'
                )
                embed.add_field(name='User', value=message.author.mention, inline=True)
                embed.add_field(name='Channel', value=message.channel.mention, inline=True)
                embed.add_field(name='Reason(s)', value=', '.join(reasons))
                embed.add_field(name='Original Message', value=message.content)
                try:
                    await self._bot.get_channel(log_channel).send(embed=embed)
                except Exception as e:
                    _log.exception(e)
            mute_role = service_config.servers[message.guild.id].moderation.mute_role
            if mute_role:
                _log.info(f'Adding role {mute_role} to {message.author}')
                try:
                    await message.author.add_roles(message.guild.get_role(mute_role),
                                                   reason='Likely scam message detected.')
                except Exception as e:
                    _log.exception(e)

            await message.delete()

    @staticmethod
    def _search_embeds(regex: re.Pattern, message: Message):
        return any((embed.title and regex.search(embed.title))
                   or (embed.description and regex.search(embed.description))
                   for embed in message.embeds)

    @staticmethod
    def _is_mod(user: Member):
        guild = user.guild.id
        return user.id in service_config.servers[guild].mod_users or \
            any(role.id in service_config.servers[guild].mod_roles for role in user.roles)
