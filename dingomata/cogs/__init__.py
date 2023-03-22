from .admin import AdminCog
from .automod import AutomodCog
from .collection import CollectionCog
from .gamba import GambaCog
from .game_code import GameCodeCog
from .guild_member import GuildMemberCog
from .logging import LoggingCog
from .poll import PollCog
from .quote import QuoteCog
from .reminder import ReminderCog
from .roles import RoleManageCog
from .text import TextCog
from .tuch import TuchCog
from .user import UserCog

all_cogs = [
    AdminCog,
    AutomodCog,
    UserCog,
    CollectionCog,
    GambaCog,
    GameCodeCog,
    LoggingCog,
    PollCog,
    QuoteCog,
    GuildMemberCog,
    ReminderCog,
    RoleManageCog,
    TextCog,
    TuchCog,
]

__all__ = [
    "UserCog",
    "AdminCog",
    "AutomodCog",
    "CollectionCog",
    "GambaCog",
    "GameCodeCog",
    "LoggingCog",
    "PollCog",
    "QuoteCog",
    "ReminderCog",
    "RoleManageCog",
    "TextCog",
    "TuchCog",
    "all_cogs",
]
