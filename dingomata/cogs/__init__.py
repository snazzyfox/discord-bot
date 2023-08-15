from dingomata.cogs.quote import QuoteCog

from .guild_member import GuildMemberCog
from .roles import RoleManageCog
from .text import TextCog

all_cogs = [
    QuoteCog,
    GuildMemberCog,
    RoleManageCog,
    TextCog,
]

__all__ = [
    "QuoteCog",
    "RoleManageCog",
    "TextCog",
    "all_cogs",
]
