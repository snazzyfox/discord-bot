import asyncio
import datetime
import logging
import typing
from copy import deepcopy
from typing import Hashable

import aiohttp
import hikari
import lightbulb
import lightbulb.ext.tasks

from snoozybot.config import values

log = logging.getLogger(__name__)
_LightbulbExtensionHook = typing.Callable[[lightbulb.BotApp], None]
_TaskFunc = typing.Callable[[lightbulb.BotApp], typing.Awaitable]


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

    async def add_cooldown(self, context: lightbulb.context.base.Context | hikari.Event) -> None:
        cooldown_channels = await values.cooldown_exempt_channels.get_value(context.guild_id)
        if cooldown_channels and context.channel_id in cooldown_channels:
            return None
        return await super().add_cooldown(context)


async def mention_if_needed(ctx: lightbulb.ApplicationContext, member: hikari.Member) -> str:
    """Return a user's mention string, or display name if they're in the no-ping list"""
    no_pings = await values.roles_no_pings.get_value(ctx.guild_id)
    if no_pings and (
        member.id in no_pings
        or any(role in no_pings for role in member.role_ids)
    ):
        return member.display_name
    else:
        return member.mention


class LightbulbPlugin(lightbulb.Plugin):
    """Extension of lightbulb plugin where we ignore commands that do not belong in a bot."""
    __slots__ = ['_periodic_tasks', '_raw_commands']

    def __init__(self, name: str):
        super().__init__(name=name)
        self._periodic_tasks: list[_TaskFunc] = []

    def create_commands(self) -> None:
        self._raw_commands: list[lightbulb.CommandLike]
        for command in self._raw_commands:
            if command.guilds:
                command.guilds = set(command.guilds) & set(self.app.default_enabled_guilds)
        self._raw_commands = [command for command in self._raw_commands if command.guilds != set()]
        super().create_commands()

    def export_extension(self) -> tuple[_LightbulbExtensionHook, _LightbulbExtensionHook]:
        """Shorthand to help create the load and unload methods for an extension.

        Use this like so in an extension: load, unload = plugin.export_extension()
        """

        def load(bot: lightbulb.BotApp):
            bot.add_plugin(deepcopy(self))
            for task in self._periodic_tasks:
                bot.subscribe(hikari.events.StartedEvent, self._register_task(task, bot))

        def unload(bot: lightbulb.BotApp):
            bot.remove_plugin(self.name)

        return load, unload

    def periodic_task(self, interval: datetime.timedelta) -> typing.Callable[[_TaskFunc], _TaskFunc]:
        """A 2nd order decorator that replaces lightbulb.ext.tasks, since it's hardcoded to support a single
        bot instance."""
        seconds = interval.total_seconds()

        def decorator(func: _TaskFunc) -> _TaskFunc:
            async def decorated(app: lightbulb.BotApp) -> None:
                while True:
                    await asyncio.gather(
                        func(app),
                        asyncio.sleep(seconds),
                    )

            self._periodic_tasks.append(decorated)
            return decorated

        return decorator

    @staticmethod
    def _register_task(task: _TaskFunc, bot: lightbulb.BotApp) -> typing.Callable:
        async def _start(_: hikari.events.StartedEvent):
            return bot.create_task(task(bot))

        return _start


client_session: aiohttp.ClientSession = None


def get_client_session():
    global client_session
    if not client_session:
        client_session = aiohttp.ClientSession()
    return client_session
