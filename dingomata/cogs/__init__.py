from dingomata.cogs.quote import QuoteCog

from .collection import CollectionCog
from .guild_member import GuildMemberCog
from .logging import LoggingCog
from .reminder import ReminderCog
from .roles import RoleManageCog
from .text import TextCog
from .tuch import TuchCog
from .user import UserCog

all_cogs = [
    UserCog,
    CollectionCog,
    LoggingCog,
    QuoteCog,
    GuildMemberCog,
    ReminderCog,
    RoleManageCog,
    TextCog,
    TuchCog,
]

__all__ = [
    "UserCog",
    "CollectionCog",
    "LoggingCog",
    "QuoteCog",
    "ReminderCog",
    "RoleManageCog",
    "TextCog",
    "TuchCog",
    "all_cogs",
]
