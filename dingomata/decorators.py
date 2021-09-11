from typing import Callable, TypeVar, List

from discord_slash.cog_ext import cog_slash, cog_subcommand, cog_context_menu

F = TypeVar('F', bound=Callable)


def _wrap(func: F) -> F:
    def wrapped(guild_ids: List[int], **kwargs):
        if guild_ids:
            return func(guild_ids=guild_ids, **kwargs)
        else:
            return lambda func: func
    return wrapped


slash = _wrap(cog_slash)
subcommand = _wrap(cog_subcommand)
context_menu = _wrap(cog_context_menu)
