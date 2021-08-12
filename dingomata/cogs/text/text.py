from random import randint

from discord import User
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_slash
from discord_slash.utils.manage_commands import create_option

from dingomata.config import get_guilds


class TextCommandsCog(Cog, name='Text Commands'):
    """Text commands."""

    def __init__(self, bot: Bot):
        self._bot = bot

    @cog_slash(name='tuch', description='Tuch some butts', guild_ids=get_guilds())
    async def tuch(self, ctx: SlashContext) -> None:
        await ctx.send(f'{ctx.author.mention} tuches {randint(0, 999)} butts.')

    @cog_slash(
        name='hug',
        description='Give someone a hug!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def hug(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} gives {user.mention} a great big hug!')

    @cog_slash(
        name='pat',
        description='Give someone pats!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def pat(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} gives {user.mention} all the pats!')

    @cog_slash(
        name='bonk',
        description='Give someone bonks!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bonk(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} bonks {user.mention} lightly on the head. Bad!')

    @cog_slash(
        name='bap',
        description='Give someone baps!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bap(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} rolls up a magazine and baps {user.mention} on the snoot.')

    @cog_slash(
        name='smooch',
        description='Give someone a big smooch!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def smooch(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} gives {user.mention} a lovely smooch on the cheek.')
