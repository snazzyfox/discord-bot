import logging
from typing import Hashable

import hikari
import lightbulb

from dingomata.config.provider import get_config
from dingomata.config.values import ConfigKey

log = logging.getLogger(__name__)


class UserGuildBucket(lightbulb.Bucket):
    """
    User Guild. All cooldowns and concurrency limits will be applied per user per guild.
    This allows each bot to track cooldowns separately per guild for the same user.
    """

    __slots__ = ()

    @classmethod
    def extract_hash(cls, context: lightbulb.context.base.Context) -> Hashable:
        return context.guild_id, context.author.id


class CooldownManager(lightbulb.CooldownManager):
    """An extension of lightbulb's cooldown manager that accouns for cooldown-exempt channels."""

    async def add_cooldown(self, context: lightbulb.context.base.Context) -> None:
        if context.channel_id in await get_config(context.guild_id, ConfigKey.COOLDOWN__EXEMPT_CHANNELS):
            return None
        return await super().add_cooldown(context)


async def mention_if_needed(ctx: lightbulb.ApplicationContext, member: hikari.Member) -> str:
    """Return a user's mention string, or display name if they're in the no-ping list"""
    no_pings: list[int] = await get_config(ctx.guild_id, ConfigKey.ROLES__NO_PINGS)
    if member and member.id in no_pings or any(role in no_pings for role in member.role_ids):
        return member.display_name
    else:
        return member.mention


class LightbulbPlugin(lightbulb.Plugin):
    """Extension of lightbulb plugin where we ignore commands that do not belong in a bot."""

    def create_commands(self) -> None:
        self._raw_commands: list[lightbulb.CommandLike]
        for command in self._raw_commands:
            if command.guilds:
                command.guilds = set(command.guilds) & set(self.app.default_enabled_guilds)
        self._raw_commands = [command for command in self._raw_commands if command.guilds != set()]
        super().create_commands()
