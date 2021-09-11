from .bedtime.commands import BedtimeCog
from .botadmin.commands import BotAdmin
from .gamba.commands import GambaCog
from .game_code.commands import GameCodeCommands
from .quote.commands import QuoteCog
from .text.commands import TextCommandsCog
from .twitch.commands import TwitchCog

all_cogs = [BedtimeCog, BotAdmin, GambaCog, GameCodeCommands, QuoteCog, TextCommandsCog, TwitchCog]

__all__ = [
    'BedtimeCog',
    'BotAdmin',
    'GambaCog',
    'GameCodeCommands',
    'QuoteCog',
    'TextCommandsCog',
    'TwitchCog',
    'all_cogs',
]
