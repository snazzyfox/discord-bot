from discord import User
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_subcommand, cog_slash
from discord_slash.utils.manage_commands import create_option, create_choice

from dingomata.config import get_guilds, get_mod_permissions


class GambaCog(Cog, name='GAMBA'):
    """Gamble with server points."""
    _GROUP_NAME = 'prediction'
    _CHOICES = [
        create_choice(name='believe', value='believe'),
        create_choice(name='doubt', value='doubt'),
    ]

    def __init__(self, bot: Bot):
        self._bot = bot

    @cog_subcommand(
        base=_GROUP_NAME,
        name='start',
        description='Start a new gamba.',
        guild_ids=get_guilds(),
        options=[
            create_option(name='name', description='Name of the prediction', option_type=str, required=True),
            create_option(name='believe', description='Name of the "believe" outcome', option_type=str, required=True),
            create_option(name='doubt', description='Name of the "doubt" outcome', option_type=str, required=True),
            create_option(name='timeout', description='Number of minutes to make predictions', option_type=int,
                          required=False)
        ],
        base_permissions=get_mod_permissions(),
        base_default_permission=False,
    )
    async def start(self, ctx: SlashContext, name: str, believe: str, doubt: str, timeout: int):
        pass

    @cog_subcommand(
        base=_GROUP_NAME,
        name='payout',
        description='Pay out the current gamba.',
        guild_ids=get_guilds(),
        options=[create_option(
            name='outcome', description='Select the outcome that won', option_type=str, required=True, choices=_CHOICES,
        )],
        base_permissions=get_mod_permissions(),
        base_default_permission=False,
    )
    async def payout(self, ctx: SlashContext, name: str, believe_outcome: str, doubt_outcome: str):
        pass

    @cog_subcommand(
        base=_GROUP_NAME,
        name='refund',
        description='Cancel the current gamba and refund all points to users.',
        guild_ids=get_guilds(),
        base_permissions=get_mod_permissions(),
        base_default_permission=False,
    )
    async def refund(self, name: str, believe_outcome: str, doubt_outcome: str):
        pass

    @cog_slash(
        name='gamba',
        description="Bet some of your server points on one of the outcomes.",
        guild_ids=get_guilds(),
        options=[
            create_option(
                name='outcome', description='Choose one of the two outcomes', option_type=str, required=True,
                choices=_CHOICES,
            ),
            create_option(
                name='points', description='Enter the number of points to be on this outcome', option_type=int,
                required=True,
            )
        ],
    )
    async def gamba(self, ctx: SlashContext, outcome: str, points: int):
        pass

    @cog_slash(
        name='balance',
        description="Check your server points balance.",
        guild_ids=get_guilds(),
    )
    async def balance(self, ctx: SlashContext):
        pass

    @cog_slash(
        name='daily',
        description="Claim your daily points.",
        guild_ids=get_guilds(),
    )
    async def daily(self, ctx: SlashContext):
        pass

    @cog_slash(
        name='give',
        description="Give some of your points to another user.",
        guild_ids=get_guilds(),
        options=[
            create_option(name='user', description='Who to give your points to', option_type=User, required=True),
            create_option(name='points', description='Number of points to give', option_type=int, required=True),
        ],
    )
    async def balance(self, ctx: SlashContext):
        pass
