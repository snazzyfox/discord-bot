import logging
import re

from discord import Message, Embed, Member
from discord.ext.commands import Bot, Cog
from sqlalchemy.ext.asyncio import AsyncEngine

from dingomata.config.config import service_config

_log = logging.getLogger(__name__)


class ModerationCommandsCog(Cog, name='Moderation'):
    """Message filtering."""
    _URL_REGEX = re.compile(r'\bhttps?://(?!twitch\.tv/)')
    _SCAM_KEYWORD_REGEX = re.compile(r'\b(?:nitro|subscription)', re.IGNORECASE)

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot

        #: Message IDs that are already being deleted - skip to avoid double posting
        self._processing_message_ids = set()

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self._check_likely_discord_scam(message)

    @Cog.listener()
    async def on_message_edit(self, before: Message, after: Message) -> None:
        await self._check_likely_discord_scam(after)

    async def _check_likely_discord_scam(self, message: Message):
        if message.id in self._processing_message_ids:
            return   # It's already in the process of being deleted.
        reasons = []
        if message.guild.default_role.mention in message.content or '@everyone' in message.content:
            reasons.append('Mentions at-everone')
        if bool(self._URL_REGEX.search(message.content)):
            reasons.append('Includes URL')
        if match := self._SCAM_KEYWORD_REGEX.search(message.content):
            reasons.append(f'Message content includes scam keyword(s): {match.group()}')
        if match := self._search_embeds(self._SCAM_KEYWORD_REGEX, message):
            reasons.append(f'Embed content includes scam keyword(s): {match.group()}')

        if len(reasons) >= 2 and not self._is_mod(message.author):
            # Consider the message scam likely if two of the three matches
            self._processing_message_ids.add(message.id)
            _log.info(f'Detected message from {message.author} as scam. Reason: {reasons}. '
                      f'Original message: {message.content}')
            log_channel = service_config.servers[message.guild.id].moderation.log_channel
            actions = []

            mute_role = service_config.servers[message.guild.id].moderation.mute_role
            if mute_role:
                _log.info(f'Added role {mute_role} to {message.author}')
                try:
                    role = message.guild.get_role(mute_role)
                    await message.author.add_roles(role, reason='Likely scam message detected.')
                    actions.append(f'Added role {role.mention}')
                except Exception as e:
                    _log.exception(e)

            try:
                await message.delete()
                actions.append('Deleted message')
            except Exception as e:
                _log.exception(e)
                actions.append(f'Failed to delete message: {e}')

            if log_channel:
                embed = Embed(
                    title='Likely scam message detected.'
                )
                embed.add_field(name='User', value=message.author.mention, inline=True)
                embed.add_field(name='Channel', value=message.channel.mention, inline=True)
                embed.add_field(name='Reason(s)', value='\n'.join(reasons), inline=False)
                embed.add_field(name='Action(s) taken', value='\n'.join(actions), inline=False)
                embed.add_field(name='Original Message', value=message.content, inline=False)
                await self._bot.get_channel(log_channel).send(embed=embed)
            self._processing_message_ids.discard(message.id)

    @staticmethod
    def _search_embeds(regex: re.Pattern, message: Message):
        matches = (
            (embed.title and regex.search(embed.title)) or (embed.description and regex.search(embed.description))
            for embed in message.embeds
        )
        return next(matches, None)

    @staticmethod
    def _is_mod(user: Member):
        guild = user.guild.id
        return user.id in service_config.servers[guild].mod_users or \
            any(role.id in service_config.servers[guild].mod_roles for role in user.roles)
