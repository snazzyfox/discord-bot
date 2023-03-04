import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import wraps
from typing import Callable, Dict, List, Optional, Set, Tuple

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


@dataclass
class AutomodRule:
    severity: float
    timeout: bool
    message: str
    eval: Callable[[discord.Message], bool]


class AutomodActionView(View):
    __slots__ = 'action', 'confirmed_by'

    def __init__(self) -> None:
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


_RULES: List[AutomodRule] = []


def _rule(name: str, severity: float, timeout: bool, reason: str):
    def decorator(func: Callable[[discord.Message], bool]):
        @wraps(func)
        def decorated(message: discord.Message) -> bool:
            if service_config.server[message.guild.id].automod.rules.get(name, True):
                return func(message)
            return False

        _RULES.append(AutomodRule(severity=severity, timeout=timeout, message=reason, eval=decorated))
        return decorated

    return decorator


@_rule(name='everyone', severity=0.8, timeout=True, reason='Attempts to mention at-everyone or at-here')
def _rule_mention_everyone(message: discord.Message) -> bool:
    return message.mention_everyone or '@everyone' in message.content or '@here' in message.content


_URL_REGEX = re.compile(r"\bhttps?://(?!(?:[^/]+\.)?(?:twitch\.tv/|tenor\.com/view/|youtube\.com/|youtu\.be/))")


@_rule(name='url', severity=0.4, timeout=True, reason='Includes a link')
def _rule_url(message: discord.Message) -> bool:
    return bool(_URL_REGEX.search(message.content))


_SCAM_REGEX = re.compile(r"\b(?:nitro|subscriptions?)\b", re.IGNORECASE)


@_rule(name='scam', severity=0.6, timeout=True, reason='Includes a scam keyword')
def _rule_scam(message: discord.Message) -> bool:
    return bool(_SCAM_REGEX.search(message.content)) or any(
        (embed.title and _SCAM_REGEX.search(unidecode(embed.title)))
        or (embed.description and _SCAM_REGEX.search(unidecode(embed.description)))
        for embed in message.embeds
    )


_UNDERAGE_REGEX = re.compile(r"\bI(?:am|'m)\s+(?:(?:[1-9]|1[1-7])(?!'|/|\.\d)|a minor)\b", re.IGNORECASE)


@_rule(name='age', severity=1.0, timeout=False, reason='Potentially underage')
def _rule_age(message: discord.Message) -> bool:
    return bool(_UNDERAGE_REGEX.search(message.content))


_SPAM_CACHE: TTLCache[Tuple[int, int], discord.TextChannel] = TTLCache(maxsize=1024, ttl=60)


@_rule(name='repeat', severity=1.0, timeout=True, reason='Repeated message spam in multiple channels.')
def _rule_repeated_spam(message: discord.Message) -> bool:
    if max_channels := service_config.server[message.guild.id].automod.max_channels_per_min:
        key = (message.guild.id, message.author.id)
        channels = _SPAM_CACHE.get(key) or set()
        channels.add(message.channel)
        _SPAM_CACHE[key] = channels
        return len(channels) >= max_channels
    return False


class AutomodCog(BaseCog):
    """Message filtering."""
    __slots__ = '_processing_message_ids',

    _JOIN_CACHES: Dict[int, TTLCache[int, None]] = {
        guild_id: TTLCache(maxsize=64, ttl=config.automod.raid_window_hours * 3600)
        for guild_id, config in service_config.server.items()
    }

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

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._check_raid_join(member)

    async def _check_message(self, message: discord.Message) -> None:
        if (
                message.id in self._processing_message_ids  # It's already in the process of being deleted.
                or message.is_system()  # Discord system message
                or not isinstance(message.author, discord.Member) or not message.guild  # DM
        ):
            return
        message.content = unidecode(message.content)
        timeout = False
        reasons = []
        score = 0.0
        for rule in _RULES:
            if rule.eval(message):
                timeout = timeout or rule.timeout
                reasons.append(rule.message)
                score += rule.severity
        if score >= 1.0:
            if message.author.guild_permissions.manage_messages:
                _log.info(f'Message from {message.author} matched automod rules {reasons}, but no action was taken '
                          f'because they have mod permissions: {message.guild}/#{message.channel}: {message.content}')
            elif timeout:
                await self._timeout_user(message, reasons)
            elif reasons:
                await self._notify_mods(message, reasons, ['Notified mods'])

    async def _check_raid_join(self, member: discord.Member) -> None:
        guild_id = member.guild.id
        self._JOIN_CACHES[guild_id][member.id] = None
        recent_joins = len(self._JOIN_CACHES[guild_id])
        settings = service_config.server[guild_id].automod
        if recent_joins >= settings.raid_min_users and 0 not in self._JOIN_CACHES[guild_id]:
            # user id 0 is cooldown timer so we dont notify multiple times in same window
            self._JOIN_CACHES[guild_id][0] = None
            embed = discord.Embed(
                title='⚠️ Possible raid detected.',
                description=f"A total of {recent_joins} users has joined this server in the last "
                            f"{settings.raid_window_hours} hour(s), which is above the configured limit of "
                            f"{settings.raid_min_users} users. This may be an indication of a raid. \n\n"
                            f"Please manually check the profiles of the last few users who joined the server to make "
                            f"sure they appear legitimate. If several suspicious accounts joined, consider monitoring "
                            f"the server closely, kicking/banning these users, or possibly pausing invites. \n\n"
                            f"This is only a warning; no action was taken. You will not be warned again in the "
                            f"next {settings.raid_window_hours} hour(s). If this warning is triggered frequently, "
                            f"consider changing bot settings.",
            )
            await self._bot_for(guild_id).get_channel(settings.log_channel).send(
                content=service_config.server[guild_id].automod.text_prefix,
                embed=embed)

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
