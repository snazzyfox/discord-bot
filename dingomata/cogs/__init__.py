from .admin import AdminCog
from .automod import AutomodCog
from .bedtime import BedtimeCog
from .collection import CollectionCog
from .gamba import GambaCog
from .game_code import GameCodeCog
from .poll import PollCog
from .quote import QuoteCog
from .refsheet import RefSheetCog
from .text import TextCog
from .tuch import TuchCog

all_cogs = [
    AdminCog,
    AutomodCog,
    BedtimeCog,
    CollectionCog,
    GambaCog,
    GameCodeCog,
    PollCog,
    QuoteCog,
    RefSheetCog,
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
    "PollCog",
    "QuoteCog",
    "RefSheetCog",
    "TextCog",
    "TuchCog",
    "all_cogs",
]
