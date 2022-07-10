import logging
import re
from datetime import timedelta
from enum import Enum
from typing import List, Optional, Set, Tuple

import discord
from cachetools import TTLCache
from unidecode import unidecode

from dingomata.cogs.base import BaseCog
from dingomata.config.bot import service_config
from dingomata.utils import View

_log = logging.getLogger(__name__)


class AutomodAction(Enum):
    BAN = 'ban'
    KICK = 'kick'
    ALLOW = 'undo'


class AutomodActionView(View):
    def __init__(self):
        self.action: Optional[AutomodAction] = None
        self.confirmed_by: Optional[discord.Member] = None
        super().__init__(timeout=None)

    @discord.ui.select(placeholder='Select an action', options=[
        discord.SelectOption(label='Ban', description='Ban the user from this server', emoji="🔨",
                             value=AutomodAction.BAN.value),
        discord.SelectOption(label='Kick', description='Kick the user from this server without ban', emoji='🥾',
                             value=AutomodAction.KICK.value),
        discord.SelectOption(label='Allow', description='This was a false detection.',
                             emoji='✅', value=AutomodAction.ALLOW.value)
    ])
    async def select(self, select: discord.ui.Select, interaction: discord.Interaction) -> None:
        if interaction.user.guild_permissions.ban_members:
            self.action = AutomodAction(select.values[0])
            self.confirmed_by = interaction.user
            self.stop()
        else:
            await interaction.response.send_message("You can't do this, you're not a mod.", ephemeral=True)


class AutomodCog(BaseCog):
    """Message filtering."""

    _URL_REGEX = re.compile(r"\bhttps?://(?!(?:[^/]+\.)?(?:twitch\.tv/|tenor\.com/view/|youtube\.com/|youtu\.be/))")
    _SCAM_KEYWORD_REGEX = re.compile(r"nitro|subscription", re.IGNORECASE)
    _UNDERAGE_REGEX = re.compile(r"\bI(?:am|'m)\s+(?:(?:[1-9]|1[1-7])(?!'|/|\.\d)|a minor)\b", re.IGNORECASE)
    _BLOCK_LIST = re.compile(r'\b(?:' + '|'.join([
        r'cozy\.tv', 'groypers', 'burn in hell'
    ]) + r')\b', re.IGNORECASE)
    _TTL: TTLCache[Tuple[int, int], discord.TextChannel] = TTLCache(maxsize=1024, ttl=60)

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

        #: Message IDs that are already being deleted - skip to avoid double posting
        self._processing_message_ids: Set[int] = set()

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._check_message(message)

    @discord.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self._check_message(after)

    async def _check_message(self, message: discord.Message) -> None:
        if message.id in self._processing_message_ids or not message.guild:
            return  # It's already in the process of being deleted.
        message.content = unidecode(message.content)
        timeout_reasons = (
            self._check_likely_discord_scam(message)
            + self._check_blocklist(message)
            + self._check_repeated_spam(message)
        )
        notify_reasons = self._check_underage(message)
        if timeout_reasons:
            await self._timeout_user(message, timeout_reasons + notify_reasons)
        elif notify_reasons:
            await self._notify_mods(message, notify_reasons, ['Notified mods'])

    def _check_likely_discord_scam(self, message: discord.Message) -> List[str]:
        if not service_config.server[message.guild.id].automod.scam_filter:
            return []
        reasons = []
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.manage_messages:
            return []
        if message.mention_everyone or "@everyone" in message.content:
            reasons.append("Mentions at-everyone")
        if bool(self._URL_REGEX.search(message.content)):
            reasons.append("Includes URL")
        if match := self._SCAM_KEYWORD_REGEX.search(message.content):
            reasons.append(f"Message content includes scam keyword(s): {match.group()}")
        if match := self._search_embeds(self._SCAM_KEYWORD_REGEX, message):
            reasons.append(f"Embed content includes scam keyword(s): {match.group()}")

        if len(reasons) >= 2:
            return reasons
        else:
            return []

    def _check_blocklist(self, message: discord.Message) -> List[str]:
        if match := self._BLOCK_LIST.search(message.content):
            return [f'Message content includes blocked term: {match.group()}']
        else:
            return []

    def _check_underage(self, message: discord.Message) -> List[str]:
        if not service_config.server[message.guild.id].automod.age_filter:
            return []
        if match := self._UNDERAGE_REGEX.search(message.content):
            return [f'Possibly underage user: {match.group()}']
        else:
            return []

    def _check_repeated_spam(self, message: discord.Message) -> List[str]:
        if max_channels := service_config.server[message.guild.id].automod.max_channels_per_min:
            key = (message.guild.id, message.author.id)
            channels = self._TTL.get(key) or set()
            channels.add(message.channel)
            self._TTL[key] = channels
            if len(channels) >= max_channels:
                return [f'Posted a message in {len(channels)} channels '
                        f'({", ".join(channel.mention for channel in channels)}) in under 1 minute.']
        return []

    async def _timeout_user(self, message: discord.Message, reasons: List[str]):
        # Consider the message scam likely if two matches
        self._processing_message_ids.add(message.id)
        _log.info(
            f"Detected message from {message.author} as scam. Reason: {reasons}. "
            f"Original message: {message.content}"
        )
        actions = []
        try:
            await message.author.timeout_for(timedelta(days=1), reason="Potential scam message.")
            actions.append("Timed out user for 1 day: pending mod review")
        except Exception as e:
            _log.exception(e)
            actions.append(f"Failed to time out user: {e}")
        try:
            await message.delete()
            actions.append("Deleted message")
        except discord.NotFound:
            actions.append("Deleted message")  # It's already been deleted previously
        except Exception as e:
            _log.exception(e)
            actions.append(f"Failed to delete message: {e}")
        await self._notify_mods(message, reasons, actions, True)
        self._processing_message_ids.discard(message.id)

    async def _notify_mods(self, message: discord.Message, reasons: List[str], actions: List[str],
                           is_timed_out: bool = False) -> None:
        log_channel = service_config.server[message.guild.id].automod.log_channel
        if log_channel:
            reasons_str = "\n".join(reasons)
            embed = discord.Embed(title="Automod detected a possibly problematic message.")
            embed.add_field(name="User", value=message.author.display_name, inline=True)
            embed.add_field(name="Channel", value=message.channel.name, inline=True)
            embed.add_field(name="Reason(s)", value=reasons_str, inline=False)
            embed.add_field(name="Action(s) taken", value="\n".join(actions), inline=False)
            embed.add_field(name="Original Message", value=message.content, inline=False)
            view = AutomodActionView()
            notify_message = await self._bot_for(message.guild.id).get_channel(log_channel).send(
                content=service_config.server[message.guild.id].automod.text_prefix,
                embed=embed, view=view
            )
            await view.wait()
            if view.confirmed_by:
                if view.action is AutomodAction.BAN:
                    await message.author.ban(reason=f'{reasons_str}, confirmed by {view.confirmed_by.display_name}')
                    actions.append(f'Banned user, confirmed by {view.confirmed_by.display_name}')
                elif view.action is AutomodAction.KICK:
                    await message.author.kick(reason=f'{reasons_str}, confirmed by {view.confirmed_by.display_name}')
                    actions.append(f'Kicked user, confirmed by {view.confirmed_by.display_name}')
                elif view.action is AutomodAction.ALLOW:
                    if is_timed_out:
                        await message.author.remove_timeout(
                            reason=f'False detection, reviewed by {view.confirmed_by.display_name}')
                        actions.append(f'Timeout removed, reviewed by {view.confirmed_by.display_name}')
                    else:
                        actions.append(f'Allowed, reviewed by {view.confirmed_by.display_name}')
                embed.set_field_at(3, name="Action(s) taken", value="\n".join(actions))
                await notify_message.edit(embed=embed, view=None)

    @staticmethod
    def _search_embeds(regex: re.Pattern, message: discord.Message):
        matches = (
            (embed.title and regex.search(unidecode(embed.title)))
            or (embed.description and regex.search(unidecode(embed.description)))
            for embed in message.embeds
        )
        return next(matches, None)
