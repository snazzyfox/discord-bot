from .admin import AdminCog
from .automod import AutomodCog
from .bedtime import BedtimeCog
from .gamba import GambaCog
from .game_code import GameCodeCog
from .quote import QuoteCog
from .text import TextCog
from .tuch import TuchCog

all_cogs = [
    AdminCog,
    AutomodCog,
    BedtimeCog,
    GambaCog,
    GameCodeCog,
    QuoteCog,
    TextCog,
    TuchCog,
]

__all__ = [
    "BedtimeCog",
    "AdminCog",
    "AutomodCog",
    "GambaCog",
    "GameCodeCog",
    "QuoteCog",
    "TextCog",
    "TuchCog",
    "all_cogs",
]
