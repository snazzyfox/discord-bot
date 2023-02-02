from .admin import AdminCog
from .automod import AutomodCog
from .bedtime import BedtimeCog
from .collection import CollectionCog
from .gamba import GambaCog
from .game_code import GameCodeCog
from .logging import LoggingCog
from .poll import PollCog
from .profile import ProfileCog
from .quote import QuoteCog
from .reminder import ReminderCog
from .role_manage import RoleManageCog
from .role_picker import RolePickerCog
from .text import TextCog
from .tuch import TuchCog

all_cogs = [
    AdminCog,
    AutomodCog,
    BedtimeCog,
    CollectionCog,
    GambaCog,
    GameCodeCog,
    LoggingCog,
    PollCog,
    QuoteCog,
    ProfileCog,
    ReminderCog,
    RolePickerCog,
    RoleManageCog,
    TextCog,
    TuchCog,
]

__all__ = [
    "BedtimeCog",
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
    "RolePickerCog",
    "TextCog",
    "TuchCog",
    "all_cogs",
]
