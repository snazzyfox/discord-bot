from functools import wraps
from time import time
from typing import Callable, Dict, Hashable, Optional, TypeVar

import discord

from dingomata.config import service_config
from dingomata.exceptions import CooldownError

F = TypeVar("F", bound=Callable)

_COOLDOWNS: Dict[Hashable, float] = {}


def _is_cooldown(key: Hashable, ttl: Optional[int]) -> float:
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
        name: Optional[str] = None,
        mod_only: bool = False,
        default_available: bool = True,
        config_group: Optional[str] = None,
        cooldown: bool = False,
):
    """Wrapper for slash commands. Automatically fills in guilds and permissions from configs.

    :param mod_only: Set permissions to only allow mod users
    :param default_available: If False, the command is turned off by default for all servers
    :param config_group: If given, uses command configs from this command name instead of the one in name
    :param cooldown: Whether this command is subject to cooldown.
    """

    def decorator(f: Callable):
        command_name = name or f.__name__
        config_name = config_group or command_name
        perms = service_config.mod_permissions if mod_only else service_config.get_command_permissions(config_name)
        guild_ids = service_config.get_command_guilds(config_name, default=default_available)
        if cooldown:
            f = _cooldown(config_name)(f)
        if guild_ids:
            decorated = discord.slash_command(name=command_name, guild_ids=guild_ids, permissions=perms,
                                              default_permission=not perms)(f)
            return decorated
        else:
            return f  # do not register the command if no guilds

    return decorator


def message_command(
        name: Optional[str] = None,
        mod_only: bool = False,
        default_available: bool = True,
        config_group: Optional[str] = None,
):
    def decorator(f: Callable):
        command_name = name or f.__name__
        config_name = config_group or f.__name__
        perms = service_config.mod_permissions if mod_only else service_config.get_command_permissions(config_name)
        guild_ids = service_config.get_command_guilds(config_name, default=default_available)
        if guild_ids:
            decorated = discord.message_command(name=command_name, guild_ids=guild_ids, permissions=perms,
                                                default_permission=not perms)(f)
            return decorated
        else:
            return f  # do not register the command if no guilds

    return decorator


def slash_group(
        name: str,
        description: str,
        mod_only: bool = False,
        default_available: bool = True,
        config_group: Optional[str] = None,
):
    config_name = config_group or name
    perms = service_config.mod_permissions if mod_only else service_config.get_command_permissions(config_name)
    return discord.SlashCommandGroup(
        name, description,
        guild_ids=service_config.get_command_guilds(config_name, default_available),
        default_permission=not perms,  # if no permission set, open to everyone
        permissions=perms,
    )
