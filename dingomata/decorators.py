from functools import wraps
from time import time
from typing import Callable, TypeVar, List, Optional, Dict, Hashable

from discord_slash.cog_ext import cog_slash, cog_subcommand, cog_context_menu
from discord_slash.context import InteractionContext

from dingomata.config import service_config
from dingomata.exceptions import CooldownError

F = TypeVar('F', bound=Callable)

_COOLDOWNS = {}


def _is_cooldown(key: Hashable, ttl: int) -> int:
    global _COOLDOWNS
    if not ttl:
        return 0
    now = time()
    _COOLDOWNS = {k: v for k, v in _COOLDOWNS.items() if v > now}
    if key in _COOLDOWNS:
        return _COOLDOWNS[key] - now
    else:
        _COOLDOWNS[key] = now + ttl
        return 0


def _cooldown(command_group: str):
    """Decorator factory that checks cooldown before executing the command."""
    cooldown_configs = service_config.get_command_cooldowns(command_group)

    def decorator(func):
        @wraps(func)
        async def wrapped(self, ctx: InteractionContext, *args, **kwargs):
            if ctx.channel.id not in service_config.cooldown_exempt:
                remaining_time = _is_cooldown(
                    (command_group, ctx.channel.id, ctx.author.id),
                    cooldown_configs.get(ctx.guild.id))
                if remaining_time:
                    raise CooldownError(f'Command is on cooldown. You can use this command again in '
                                        f'{remaining_time:.1f} seconds. You may be able to get around this by using '
                                        f'the command in the bot spam channel.')
            return await func(self, ctx, *args, **kwargs)
        return wrapped
    return decorator


def _compose_decorators(*decorators):
    def decorator(func):
        for dec in reversed(decorators):
            func = dec(func)
        return func

    return decorator


def slash(name: str, group: Optional[str] = None, mod_only: bool = False, default_available: bool = True,
          guild_ids: Optional[List[int]] = None, permissions: Optional[Dict[int, List]] = None, cooldown: bool = False,
          **kwargs):
    """Wrapper for slash commands. Automatically fills in guilds and permissions from configs.

    :param name: Name of the command
    :param group: If given, uses command configs from this command name instead of the one in name
    :param mod_only: Set permissions to only allow mod users
    :param default_available: If False, the command is turned off by default for all servers
    :param guild_ids: Same as guild_ids in upstream lib. If empty filled by decorator.
    :param permissions: Same as permissions in upstream lib. If empty filled by decorator.
    :param cooldown: Whether this command is subject to cooldown.
    """
    group_name = group or name
    guild_ids = guild_ids or service_config.get_command_guilds(group_name, default=default_available)
    if not permissions:
        if mod_only:
            permissions = service_config.mod_permissions
        else:
            permissions = service_config.get_command_permissions(group_name)
    if permissions:
        kwargs['permissions'] = permissions
        kwargs['default_permission'] = False
    if guild_ids:
        decorator = cog_slash(name=name, guild_ids=guild_ids, **kwargs)
        if cooldown:
            decorator = _compose_decorators(decorator, _cooldown(group_name))
        return decorator
    else:
        return lambda func: func  # do not register the command if no guilds


class SubcommandBase:
    def __init__(self, name: str, group: Optional[str] = None, mod_only: bool = False, default_available: bool = True,
                 guild_ids: Optional[List[int]] = None, permissions: Optional[Dict[int, List]] = None):
        self.name = name
        group_name = group or name
        self.guild_ids = guild_ids or service_config.get_command_guilds(group_name, default=default_available)
        self.permissions = permissions or (
            service_config.mod_permissions if mod_only else service_config.get_command_permissions(group_name))
        self.registered = False


def subcommand(name: str, base: SubcommandBase, cooldown: bool = False, **kwargs):
    """Wrapper for subcommands. Automatically fills in guilds and permissions from configs."""
    if base.guild_ids:
        if base.registered:
            return cog_subcommand(base=base.name, base_default_permission=not base.permissions,
                                  name=name, guild_ids=base.guild_ids, **kwargs)
        else:
            # bug in interactions lib - can only pass permission list once or they get concat'd
            base.registered = True
            return cog_subcommand(base=base.name, base_permissions=base.permissions,
                                  base_default_permission=not base.permissions,
                                  name=name, guild_ids=base.guild_ids, **kwargs)
    else:
        return lambda func: func


def context_menu(name: str, group: Optional[str] = None, mod_only: bool = False, default_available: bool = True,
                 guild_ids: Optional[List[int]] = None, permissions: Optional[Dict[int, List]] = None, **kwargs):
    group_name = group or name
    guild_ids = guild_ids or service_config.get_command_guilds(group_name, default=default_available)
    if not permissions:
        if mod_only:
            permissions = service_config.mod_permissions
            kwargs['default_permission'] = False
        else:
            permissions = service_config.get_command_permissions(group_name)
    if permissions:
        kwargs['permissions'] = permissions
    if guild_ids:
        return cog_context_menu(name=name, guild_ids=guild_ids, **kwargs)
    else:
        return lambda func: func
