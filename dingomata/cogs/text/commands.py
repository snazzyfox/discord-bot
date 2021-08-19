from pathlib import Path
from random import betavariate, random, choice, randint

import yaml
from discord import User
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_slash
from discord_slash.utils.manage_commands import create_option
from prettytable import PrettyTable
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import TextModel, Quote, TuchLog
from ...config import get_guilds, get_guild_config, get_mod_permissions


class TextCommandsCog(Cog, name='Text Commands'):
    """Text commands."""

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(TextModel.metadata.create_all)

    @cog_slash(name='tuch', description='Tuch some butts. You assume all risks.', guild_ids=get_guilds())
    async def tuch(self, ctx: SlashContext) -> None:
        if random() < 0.95:
            number = int(betavariate(1.5, 3) * ctx.guild.member_count)
            await ctx.send(f'{ctx.author.display_name} tuches {number} butts. So much floof!')
        else:
            number = 1
            await ctx.send(f"{ctx.author.display_name} tuches {choice(ctx.channel.members).display_name}'s "
                           f"butt, OwO")
        async with self._session() as session:
            async with session.begin():
                stmt = select(TuchLog).filter(TuchLog.guild_id == ctx.guild.id, TuchLog.user_id == ctx.author.id)
                tuch = (await session.execute(stmt)).scalar()
                if not tuch:
                    tuch = TuchLog(guild_id=ctx.guild.id, user_id=ctx.author.id, max_butts=number, total_butts=number,
                                   total_tuchs=1)
                else:
                    tuch.max_butts = max(tuch.max_butts, number)
                    tuch.total_butts += number
                    tuch.total_tuchs += 1
                await session.merge(tuch)
                await session.commit()

    @cog_slash(name='tuchboard', description='Statistics about tuches', guild_ids=get_guilds())
    async def tuchboard(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(
                    func.sum(TuchLog.total_tuchs).label('total_tuchs'),
                    func.sum(TuchLog.total_butts).label('total_butts'),
                ).filter(TuchLog.guild_id == ctx.guild.id)
                master_stats = (await session.execute(stmt)).first()
                message = (f'Total butts tuched: {master_stats.total_butts:,}\n'
                           f'Total number of times tuch was used: {master_stats.total_tuchs:,}\n')
                subquery = select(TuchLog.user_id, TuchLog.max_butts,
                                  func.rank().over(order_by=TuchLog.max_butts.desc()).label('rank')).filter(
                    TuchLog.guild_id == ctx.guild.id).subquery()
                stmt = select(subquery.c.user_id, subquery.c.max_butts, subquery.c.rank).filter(subquery.c.rank <= 10)
                data = await session.execute(stmt)
                table = PrettyTable()
                table.field_names = ('Rank', 'User', 'Max Butts Tuched')
                table.align['Rank'] = 'r'
                table.align['User'] = 'l'
                table.align['Max Butts Tuched'] = 'r'
                for row in data:
                    user = ctx.guild.get_member(row.user_id)
                    username = user.display_name if user else "Unknown User"
                    table.add_row((row.rank, username, row.max_butts))
                message += '```\n' + table.get_string() + '\n```'
                await ctx.reply(message)

    @cog_slash(
        name='hug',
        description='Give someone a hug!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def hug(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} is lonely and can't stop hugging themselves.")
        elif random() < 0.98:
            adj = choice(['great big', 'giant', 'big bear', 'friendly', 'loving', 'nice warm', 'floofy', 'free',
                          'suplex and a'])
            await ctx.send(f'{ctx.author.display_name} gives {self._mention(ctx, user)} a {adj} hug!')
        else:
            await ctx.send(f'{ctx.author.display_name} wants to give {self._mention(ctx, user)} a hug, but then '
                           f'remembers social distancing is still a thing.')

    @cog_slash(
        name='pat',
        description='Give someone pats!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def pat(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.display_name} gives themselves a pat on the back!')
        else:
            await ctx.send(f'{ctx.author.display_name} gives {self._mention(ctx, user)} all the pats!')

    @cog_slash(
        name='bonk',
        description='Give someone bonks!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def bonk(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} tries to bonk themselves. They appear to really enjoy it.")
        elif user == self._bot.user:
            await ctx.send(f"How dare you.")
        else:
            adj = choice(['lightly', 'gently', 'aggressively'])
            await ctx.send(f'{ctx.author.display_name} bonks {self._mention(ctx, user)} {adj} on the head. Bad!')

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
            await ctx.send(f"{user.mention} rolls up a {thing} and baps {ctx.author.mention} on the snoot.")
        else:
            await ctx.send(f'{ctx.author.display_name} rolls up a {thing} and baps {self._mention(ctx, user)} on '
                           f'the snoot.')

    @cog_slash(
        name='boop',
        description='Give someone a boop!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def boop(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} walkes into a glass door and end up booping themselves.")
        else:
            adv = choice(['lightly', 'gently', 'lovingly', 'aggressively', 'kindly', 'tenderly'])
            await ctx.send(f"{ctx.author.display_name} {adv} boops {self._mention(ctx, user)}'s snoot. Aaaaaa!")

    @cog_slash(
        name='smooch',
        description='Give someone a big smooch!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def smooch(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.display_name} tries to smooch themselves... How is that possible?')
        else:
            location = choice(['cheek', 'head', 'booper', 'snoot', 'face', 'lips', 'tail', 'neck', 'paws', 'beans',
                               'ears', 'you-know-what'])
            adj = choice(['lovely', 'sweet', 'affectionate', 'delightful', 'friendly', 'warm', 'wet'])
            message = f'{ctx.author.display_name} gives {self._mention(ctx, user)} a {adj} smooch on the {location}.'
            if user == self._bot.user:
                message += ' Bzzzt. A shocking experience.'
            await ctx.send(message)

    @cog_slash(
        name='smooth',
        description="This was supposed to be smooch but I'm leaving it",
        guild_ids=get_guilds())
    async def smooth(self, ctx: SlashContext) -> None:
        await ctx.send(f'{ctx.author.display_name} takes a sip of their drink. Smoooooth.')

    @cog_slash(name='cuddle', guild_ids=get_guilds(),
               description="Give a cutie some cuddles",
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def cuddle(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.display_name} pulls {self._mention(ctx, user)} into their arm for a long cuddle.')

    @cog_slash(name='snug', guild_ids=get_guilds(),
               description="Give someone some snuggles",
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def snug(self, ctx: SlashContext, user: User) -> None:
        await ctx.send(f'{ctx.author.display_name} snuggles the heck out of {self._mention(ctx, user)}!')

    @cog_slash(
        name='tuck',
        description='Tuck someone into bed!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def tuck(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.display_name} gets into bed and rolls up into a cozy burrito.')
        elif user.bot:
            await ctx.send(f'{ctx.author.display_name} rolls {self._mention(ctx, user)} up in a blanket. The bot '
                           f'overheats.')
        else:
            shell = choice(['cozy blanket', 'tortilla', 'pancake', 'comforter', 'piece of toast', 'beach towel'])
            product = choice(['burrito', 'purrito', 'tasty snacc', 'hotdog', 'crepe', 'swiss roll'])
            await ctx.send(f'{ctx.author.display_name} takes a {shell} and rolls {self._mention(ctx, user)} into a '
                           f'{product} before tucking them into bed. Sweet dreams!')

    @cog_slash(
        name='tacklehug',
        description='Bam!',
        guild_ids=get_guilds(),
        options=[create_option(name='user', description='Target user', option_type=User, required=True)],
    )
    async def tacklehug(self, ctx: SlashContext, user: User) -> None:
        if user == ctx.author:
            await ctx.send(f'{ctx.author.display_name} trips over and somehow tackles themselves. Oh wait, they tied '
                           f'both their shoes together.')
        else:
            ending = choice(['to the ground!', 'to the floor!', 'off a cliff. Oops!', 'into a tree. *Thud*',
                             'into the grass.', 'into a lake. *splash*', ])
            message = f'{ctx.author.display_name} tacklehugs {self._mention(ctx, user)} {ending}'
            if user.bot:
                message += ' The bot lets out some sparks and burns their beans.'
            await ctx.send(message)

    @cog_slash(name='scream', description='Scream!', guild_ids=get_guilds())
    async def scream(self, ctx: SlashContext) -> None:
        char = choice(['A'] * 20 + ['🅰', '🇦 '])
        await ctx.send(char * randint(1, 35) + '!')

    @cog_slash(name='awoo', description='Howl!', guild_ids=get_guilds())
    async def awoo(self, ctx: SlashContext) -> None:
        await ctx.send('Awoo' + 'o' * randint(0, 25) + '!')

    @cog_slash(name='banger', description='Such a jam!', guild_ids=get_guilds())
    async def banger(self, ctx: SlashContext) -> None:
        await ctx.send('⚠🎶 Banger Alert! 🎶⚠')

    @cog_slash(name='sip', description='Sip on a drink!', guild_ids=get_guilds())
    async def sip(self, ctx: SlashContext) -> None:
        if random() < 0.5:
            await ctx.send((' glug' * randint(2, 8)).strip().capitalize() + '.')
        else:
            await ctx.send('Slu' + 'r' * randint(1, 20) + 'p.')

    @cog_slash(name='dingomata', description='I better see some /banger', guild_ids=get_guilds())
    async def dingomata(self, ctx: SlashContext) -> None:
        await ctx.reply('https://www.youtube.com/watch?v=yMbSiF-6FBs')

    @cog_slash(name='cute', description="So cute!", guild_ids=get_guilds(),
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def cute(self, ctx: SlashContext, user: User) -> None:
        if user == self._bot.user:
            await ctx.reply('No U.')
        else:
            phrase = choice(['Such a cutie! :-3', 'How cute!', "I can't get over how cute they are!",
                             "I can't believe they're so cute!", "Why are they so cute?", "*melts to their cuteness*"])
            await ctx.reply(f"Aww, Look at {self._mention(ctx, user)}... {phrase}")

    @cog_slash(name='roll', description="Roll a die.", guild_ids=get_guilds(),
               options=[create_option(name='sides', description='Number of sides (default 6)', option_type=int,
                                      required=False)],
               )
    async def roll(self, ctx: SlashContext, sides: int = 6) -> None:
        if sides <= 1:
            await ctx.reply(f"{ctx.author.display_name} tries to roll a {sides}-sided die, but created a black hole "
                            f"instead, because it can't possibly exist. ")
        elif random() < 0.01:
            await ctx.reply(f"{ctx.author.display_name} rolls a... darn it. It bounced down the stairs into the "
                            f"dungeon.")
        else:
            await ctx.reply(f"{ctx.author.display_name} rolls a {randint(1, sides)} on a d{sides}.")

    @cog_slash(name='flip', description="Flip a coin.", guild_ids=get_guilds())
    async def flip(self, ctx: SlashContext) -> None:
        if random() < 0.99:
            await ctx.reply(f"It's {choice(['heads', 'tails'])}.")
        else:
            await ctx.reply(f"It's... hecc, it went under the couch.")

    @cog_slash(name='whiskey', description="What does the Dingo say?", guild_ids=get_guilds())
    async def whiskey(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(Quote.content).order_by(func.random()).limit(1)
                quote = (await session.execute(stmt)).scalar()
                if quote is None:
                    await ctx.reply('There are no quotes.', hidden=True)
                else:
                    await ctx.reply(quote)

    @cog_slash(name='whiskey_add', description="Add a new quote", guild_ids=get_guilds(),
               permissions=get_mod_permissions(), default_permission=False,
               options=[create_option(name='content', option_type=str, required=True, description='Quote content')])
    async def whiskey_add(self, ctx: SlashContext, content: str) -> None:
        async with self._session() as session:
            async with session.begin():
                quote = Quote(content=content)
                session.add(quote)
                await session.commit()
                await ctx.reply('Done', hidden=True)

    @cog_slash(name='snipe', description="It's bloody murderrrr", guild_ids=get_guilds(),
               options=[create_option(name='user', description='Target user', option_type=User, required=True)],
               )
    async def snipe(self, ctx: SlashContext, user: User) -> None:
        if user == self._bot.user:
            await ctx.reply(f"{ctx.author.display_name} dares to snipe {self._mention(ctx, user)}. The rifle explodes, "
                            f"taking their paws with it.")
        elif user == ctx.author:
            result = "BANG! The gun goes." if random() < 1 / 6 else "Whew, it's a blank."
            await ctx.reply(f"{ctx.author.display_name} plays Russian Roulette with a revolver. {result}")
        elif (prob := random()) < 0.50:
            reason = choice([
                'they get distracted and went to chase a squirrel instead',
                'they only have a knife in the gun fight',
                'they watched the Dingomata while waiting and was heard',
                'they fall out of the tree while waiting',
                'the rifle turns out to be a water gun',
                'they totally forget to shoot because they were browsing furry art',
                'they spend all night awooing to a full moon',
            ])
            await ctx.reply(f"{ctx.author.display_name} tries to snipe {self._mention(ctx, user)}, but {reason}.")
        elif prob < 0.975:
            reason = choice([
                'forgot gravity existed', 'failed to account for wind', "didn't clean the scope", 'got too tipsy',
                "can't concentrate", "had too much coffee", "are pepega at shooting"
            ])
            action = choice(['misses completely', 'botches it', 'foxes it up', 'borks it', "it's a ruff shot"])
            await ctx.reply(f"{ctx.author.display_name} takes a shot at {self._mention(ctx, user)}, but they "
                            f"{reason} and {action}. The bullet ricochets and scares {user.display_name} away.")
        elif prob < 0.995:
            location = choice(['bean', 'arm', 'leg', 'thigh', 'fingy', 'paw', 'shoulder'])
            await ctx.reply(f"{ctx.author.display_name} takes a shot at {self._mention(ctx, user)} and hits their "
                            f"{location}. {user.display_name} runs away.")
        else:
            location = choice(['chest', 'head', 'tums'])
            await ctx.reply(f"{ctx.author.display_name} takes a shot at {self._mention(ctx, user)} and hits their "
                            f"{location}. {user.display_name} is ded. F.")

    @staticmethod
    def _mention(ctx: SlashContext, user: User) -> str:
        """Return a user's mention string, or display name if they're in the no-ping list"""
        no_ping_users = get_guild_config(ctx.guild.id).common.no_ping_users
        if user.id in no_ping_users:
            return user.display_name
        else:
            return user.mention
