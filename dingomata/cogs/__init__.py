from .bedtime.commands import BedtimeCog
from .botadmin.commands import BotAdmin
from .gamba.commands import GambaCog
from .game_code.commands import GameCodeCommands
from .moderation.commands import ModerationCommandsCog
from .poll.commands import PollCog
from .quote.commands import QuoteCog
from .roles.commands import RoleCommandsCog
from .text.commands import TextCommandsCog
from .twitch.commands import TwitchCog

all_cogs = [BedtimeCog, BotAdmin, GambaCog, GameCodeCommands, ModerationCommandsCog, PollCog, QuoteCog,
            RoleCommandsCog, TextCommandsCog, TwitchCog]

__all__ = [
    'BedtimeCog',
    'BotAdmin',
    'GambaCog',
    'GameCodeCommands',
    'ModerationCommandsCog',
    'PollCog',
    'QuoteCog',
    'RoleCommandsCog',
    'TextCommandsCog',
    'TwitchCog',
    'all_cogs',
]
