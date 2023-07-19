from functools import wraps
from time import time
from typing import Callable, Hashable, TypeVar

import discord

from dingomata.config import service_config
from dingomata.exceptions import CooldownError

F = TypeVar("F", bound=Callable)

_COOLDOWNS: dict[Hashable, float] = {}


def _is_cooldown(key: Hashable, ttl: int | None) -> float:
    global _COOLDOWNS
    if not ttl:
        return 0
    now = time()
    _COOLDOWNS = {k: v for k, v in _COOLDOWNS.items() if v > now}
    if key in _COOLDOWNS:
        return _COOLDOWNS[key] - now
    else:
        _COOLDOWNS[key] = now + ttl
        return 0.0


def _cooldown(command_group: str):
    """Decorator factory that checks cooldown before executing the command."""
    cooldown_configs = service_config.get_command_cooldowns(command_group)

    def decorator(func):
        @wraps(func)
        async def wrapped(self, ctx: discord.ApplicationContext, *args, **kwargs):
            if ctx.channel.id not in service_config.cooldown_exempt:
                remaining_time = _is_cooldown((command_group, ctx.channel.id), cooldown_configs.get(ctx.guild.id))
                if remaining_time:
                    raise CooldownError(
                        f"Command is on cooldown. You can use this command again in {remaining_time:.1f} seconds. "
                        f"You can get around this by using the bot spam channel instead.")
            return await func(self, ctx, *args, **kwargs)

        return wrapped

    return decorator


def slash(
        name: str | None = None,
        default_available: bool = True,
        config_group: str | None = None,
        cooldown: bool = False,
):
    """Wrapper for slash commands. Automatically fills in guilds and permissions from configs.

    :param name: Name of the command if not the function name
    :param default_available: If False, the command is turned off by default for all servers
    :param config_group: If given, uses command configs from this command name instead of the one in name
    :param cooldown: Whether this command is subject to cooldown.
    """

    def decorator(f: Callable):
        command_name = name or f.__name__
        config_name = config_group or command_name
        guild_ids = service_config.get_command_guilds(config_name, default=default_available)
        if cooldown:
            f = _cooldown(config_name)(f)
        if guild_ids:
            decorated = discord.slash_command(name=command_name, guild_ids=guild_ids)(f)
            return decorated
        else:
            return f  # do not register the command if no guilds

    return decorator


def message_command(
        name: str | None = None,
        default_available: bool = True,
        config_group: str | None = None,
):
    def decorator(f: Callable):
        command_name = name or f.__name__
        config_name = config_group or f.__name__
        guild_ids = service_config.get_command_guilds(config_name, default=default_available)
        if guild_ids:
            decorated = discord.message_command(name=command_name, guild_ids=guild_ids)(f)
            return decorated
        else:
            return f  # do not register the command if no guilds

    return decorator


def user_command(
        name: str | None = None,
        default_available: bool = True,
        config_group: str | None = None,
):
    def decorator(f: Callable):
        command_name = name or f.__name__
        config_name = config_group or f.__name__
        guild_ids = service_config.get_command_guilds(config_name, default=default_available)
        if guild_ids:
            decorated = discord.user_command(name=command_name, guild_ids=guild_ids)(f)
            return decorated
        else:
            return f  # do not register the command if no guilds

    return decorator


def slash_group(
        name: str,
        description: str,
        default_available: bool = True,
        config_group: str | None = None,
):
    config_name = config_group or name
    return discord.SlashCommandGroup(
        name, description,
        guild_ids=service_config.get_command_guilds(config_name, default_available),
    )


def slash_subgroup(
        group: discord.SlashCommandGroup,
        name: str,
        description: str,
):
    return group.create_subgroup(name, description, guild_ids=group.guild_ids)
