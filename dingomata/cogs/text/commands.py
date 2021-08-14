from random import randint, random, choice

from discord import User
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_slash
from discord_slash.utils.manage_commands import create_option

from ...config import get_guilds


class TextCommandsCog(Cog, name='Text Commands'):
    """Text commands."""

    def __init__(self, bot: Bot):
        self._bot = bot

    @cog_slash(name='tuch', description='Tuch some butts. You assume all risks.', guild_ids=get_guilds())
    async def tuch(self, ctx: SlashContext) -> None:
        if random() < 0.95:
            await ctx.send(f'{ctx.author.mention} tuches {randint(0, 999)} butts. So much floof!')
        else:
            await ctx.send(f"{ctx.author.mention} tuches {choice(ctx.channel.members).mention}'s butt, OwO")

    @cog_slash(
        name='hug',
        description='Give someone a hug!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def hug(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.mention} is lonely and can't stop hugging themselves.")
        else:
            await ctx.send(f'{ctx.author.mention} gives {user.mention} a great big hug!')

    @cog_slash(
        name='pat',
        description='Give someone pats!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def pat(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.mention} gives themselves a pat on the back!')
        else:
            await ctx.send(f'{ctx.author.mention} gives {user.mention} all the pats!')

    @cog_slash(
        name='bonk',
        description='Give someone bonks!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bonk(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.mention} tries to bonk themselves. They appear to really enjoy it.")
        elif user == self._bot.user:
            await ctx.send(f"How dare you.")
        else:
            adj = choice(['lightly', 'gently', 'aggressively'])
            await ctx.send(f'{ctx.author.mention} bonks {user.mention} {adj} on the head. Bad!')

    @cog_slash(
        name='bap',
        description='Give someone baps!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bap(self, ctx: SlashContext, user: User) -> None:
        thing = choice(['magazine', 'newspaper', 'mousepad', 'phonebook', 'pancake', 'pillow'])
        if ctx.author == user:
            await ctx.send(f"Aw, don't be so rough on yourself.")
        elif user == self._bot.user:
            await ctx.send(f"{user.mention} rolls up a magazine and baps {ctx.author.mention} on the snoot.")
        else:
            await ctx.send(f'{ctx.author.mention} rolls up a magazine and baps {user.mention} on the snoot.')

    @cog_slash(
        name='boop',
        description='Give someone a boop!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def boop(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.mention} walkes into a glass door and end up booping themselves.")
        else:
            await ctx.send(f"{ctx.author.mention} gently boops {user.mention}'s snoot. Aaaaaa!")

    @cog_slash(
        name='smooch',
        description='Give someone a big smooch!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def smooch(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.mention} tries to smooch themselves... How is that possible?')
        else:
            location = choice(['cheek', 'head', 'booper', 'snoot', 'face', 'lips', 'tail', 'neck', 'paws', 'beans',
                               'ears', 'you-know-what'])
            adj = choice(['lovely', 'sweet', 'affectionate', 'delightful', 'friendly', 'warm', 'wet'])
            await ctx.send(f'{ctx.author.mention} gives {user.mention} a {adj} smooch on the {location}.')

    @cog_slash(
        name='smooth',
        description="This was supposed to be smooch but I'm leaving it",
        guild_ids=get_guilds())
    async def smooth(self, ctx: SlashContext) -> None:
        await ctx.send(f'{ctx.author.mention} takes a sip of their drink. Smoooooth.')

    @cog_slash(name='cuddle', guild_ids=get_guilds(),
               description="Give a cutie some cuddles",
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def cuddle(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} pulls {user.mention} into their arm for a long cuddle.')

    @cog_slash(name='snug', guild_ids=get_guilds(),
               description="Give someone some snuggles",
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def snug(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.mention} snuggles the heck out of {user.mention}!')

    @cog_slash(
        name='tuck',
        description='Tuck someone into bed!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def tuck(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.mention} gets into bed and rolls up into a cozy burrito.')
        elif user.bot:
            await ctx.send(f'{ctx.author.mention} rolls {user.mention} up in a blanked. The bot overheats.')
        else:
            await ctx.send(f'{ctx.author.mention} takes a blanket and rolls {user.mention} into a burrito before '
                           f'tucking them into bed. Sweet dreams!')

    @cog_slash(
        name='bodycheck',
        description='Bam!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bodycheck(self, ctx: SlashContext, user: User) -> None:
        if user.bot:
            await ctx.send(f"{ctx.author.mention} tries to ram {user.mention}, but misses because they're a bot.")
        else:
            await ctx.send(f'{ctx.user.mention} gets absolutely RAMMED into the boards by {ctx.author.mention}. '
                           f'It is very effective!')

    @cog_slash(name='scream', description='AAAAA', guild_ids=get_guilds())
    async def scream(self, ctx: SlashContext) -> None:
        await ctx.send('A' * randint(1, 35) + '!')

    @cog_slash(name='banger', description='Such a jam!', guild_ids=get_guilds())
    async def banger(self, ctx: SlashContext) -> None:
        await ctx.send('⚠🎶 Banger Alert! 🎶⚠')

    @cog_slash(name='neo', description='The red and black wolf', guild_ids=get_guilds())
    async def neo(self, ctx: SlashContext) -> None:
        await ctx.send('Neo is *so* cute, awwwwww!')
