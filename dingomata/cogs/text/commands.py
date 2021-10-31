import re
from datetime import datetime
from random import betavariate, random, choice, randint

import pytz
from discord import User, Message
from discord.ext.commands import Bot, Cog, cooldown
from discord.ext.commands.cooldowns import BucketType
from discord_slash import SlashContext
from discord_slash.utils.manage_commands import create_option
from parsedatetime import Calendar
from prettytable import PrettyTable
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import TextModel, TextTuchLog, TextCollect
from ...config import service_config
from ...decorators import slash
from ...exceptions import DingomataUserError

_calendar = Calendar()


class TextCommandsCog(Cog, name='Text Commands'):
    """Text commands."""

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self._BOT_NAME_REGEX: re.Pattern = None

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(TextModel.metadata.create_all)
            self._BOT_NAME_REGEX = re.compile(f'\b{self._bot.user.display_name}\b', re.IGNORECASE)

    @slash(name='tuch', description='Tuch some butts. You assume all risks.')
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
                stmt = select(TextTuchLog).filter(TextTuchLog.guild_id == ctx.guild.id,
                                                  TextTuchLog.user_id == ctx.author.id)
                tuch = (await session.execute(stmt)).scalar()
                if not tuch:
                    tuch = TextTuchLog(guild_id=ctx.guild.id, user_id=ctx.author.id, max_butts=number,
                                       total_butts=number,
                                       total_tuchs=1)
                else:
                    tuch.max_butts = max(tuch.max_butts, number)
                    tuch.total_butts += number
                    tuch.total_tuchs += 1
                await session.merge(tuch)
                await session.commit()

    @slash(name='tuchboard', description='Statistics about tuches', group='tuch')
    @cooldown(1, 30.0, BucketType.guild)
    async def tuchboard(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(
                    func.sum(TextTuchLog.total_tuchs).label('total_tuchs'),
                    func.sum(TextTuchLog.total_butts).label('total_butts'),
                ).filter(TextTuchLog.guild_id == ctx.guild.id)
                master_stats = (await session.execute(stmt)).first()
                message = (f'Total butts tuched: {master_stats.total_butts:,}\n'
                           f'Total number of times tuch was used: {master_stats.total_tuchs:,}\n'
                           f'Total butts in server: {ctx.guild.member_count:,}\n')
                subquery = select(TextTuchLog.user_id, TextTuchLog.max_butts, TextTuchLog.total_butts,
                                  func.rank().over(order_by=TextTuchLog.max_butts.desc()).label('rank')).filter(
                    TextTuchLog.guild_id == ctx.guild.id).subquery()
                stmt = select(subquery.c.user_id, subquery.c.max_butts, subquery.c.rank, subquery.c.total_butts,
                              ).filter(subquery.c.rank <= 10)
                data = await session.execute(stmt)
                table = PrettyTable()
                table.field_names = ('Rank', 'User', 'Max Butts', 'Total Butts')
                table.align['Rank'] = 'r'
                table.align['User'] = 'l'
                table.align['Max Butts'] = 'r'
                table.align['Total Butts'] = 'r'
                for row in data:
                    user = ctx.guild.get_member(row.user_id)
                    username = user.display_name if user else "Unknown User"
                    table.add_row((row.rank, username, row.max_butts, row.total_butts))
                message += '```\n' + table.get_string() + '\n```'
                await ctx.reply(message)

    @slash(name='collect', description='Add a cutie to your collection.',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    async def collect(self, ctx: SlashContext, user: User) -> None:
        async with self._session() as session:
            try:
                async with session.begin():
                    col = TextCollect(guild_id=ctx.guild.id, user_id=ctx.author.id, target_user_id=user.id)
                    session.add(col)
                    await session.commit()
                async with session.begin():
                    stmt = select(func.count()).filter(TextCollect.guild_id == ctx.guild.id,
                                                       TextCollect.user_id == ctx.author.id)
                    total = await session.scalar(stmt)
                    await ctx.reply(f'{ctx.author.display_name} collects {self._mention(ctx, user)}. '
                                    f'They now have {total} cutie(s) in their collection!')
            except IntegrityError:
                await ctx.reply(f'You have already collected {user.display_name}.', hidden=True)

    @slash(name='discard', description='Remove a cutie from your collection D:',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    async def discard(self, ctx: SlashContext, user: User) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(TextCollect).filter(TextCollect.guild_id == ctx.guild.id,
                                                  TextCollect.user_id == ctx.author.id,
                                                  TextCollect.target_user_id == user.id)
                col = await session.scalar(stmt)
                if col:
                    await session.delete(col)
                    await ctx.reply(f'{ctx.author.display_name} has removed {self._mention(ctx, user)} from their '
                                    f'collection.')
                else:
                    await ctx.reply(f'{user.display_name} is not in your collection.', hidden=True)

    @slash(name='collection', description='Show your collection!', group='collect')
    async def collection(self, ctx: SlashContext) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = select(TextCollect).filter(TextCollect.guild_id == ctx.guild.id,
                                                  TextCollect.user_id == ctx.author.id)
                cols = list((await session.execute(stmt)).scalars())
                await ctx.reply(f'{ctx.author.display_name} has a collection of {len(cols)} cutie(s). '
                                f'Their collection includes: ' +
                                ', '.join(self._bot.get_user(c.target_user_id).display_name for c in cols))

    @slash(name='hug', description='Give someone a hug!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def hug(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} is lonely and can't stop hugging themselves.")
        elif random() < 0.98:
            adj = choice(['great big', 'giant', 'big bear', 'friendly', 'loving', 'nice warm', 'floofy', 'free',
                          'suplex and a', 'rambunctious', 'therapeutic', 'heavenly', 'tender', 'dazzling', 'joyous',
                          'tremendous', 'remarkable', 'magical', 'kind', 'delightful', 'satisfying', 'cheerful'])
            await ctx.send(f'{ctx.author.display_name} gives {self._mention(ctx, user)} a {adj} hug!')
        else:
            await ctx.send(f'{ctx.author.display_name} wants to give {self._mention(ctx, user)} a hug, but then '
                           f'remembers social distancing is still a thing.')

    @slash(name='pat', description='Give someone pats!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def pat(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.display_name} gives themselves a pat on the back!')
        else:
            await ctx.send(f'{ctx.author.display_name} gives {self._mention(ctx, user)} all the pats!')

    @slash(name='bonk', description='Give someone bonks!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def bonk(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} tries to bonk themselves. They appear to really enjoy it.")
        elif user == self._bot.user:
            await ctx.send("How dare you.")
        else:
            adj = choice(['lightly', 'gently', 'aggressively', 'frantically', 'twice', 'heavily', 'loudly',
                          'deliberately', 'dutifully', 'mortally', 'politely', 'weakly', 'violently', 'noisily',
                          'swiftly', 'repeatedly', 'fiercely', 'kiddingly', 'judgmentally', 'mockingly'])
            await ctx.send(f'{ctx.author.display_name} bonks {self._mention(ctx, user)} {adj} on the head. Bad!')

    @slash(name='bap', description='Give someone baps!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def bap(self, ctx: SlashContext, user: User) -> None:
        thing = choice(['magazine', 'newspaper', 'mousepad', 'phonebook', 'pancake', 'pillow', 'pizza', 'towel'])
        if ctx.author == user:
            await ctx.send("Aw, don't be so rough on yourself.")
        elif user == self._bot.user:
            await ctx.send(f"{user.mention} rolls up a {thing} and baps {ctx.author.mention} on the snoot.")
        else:
            await ctx.send(f'{ctx.author.display_name} rolls up a {thing} and baps {self._mention(ctx, user)} on '
                           f'the snoot.')

    @slash(name='boop', description='Give someone a boop!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def boop(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f"{ctx.author.display_name} walks into a glass door and end up booping themselves.")
        else:
            adv = choice(['lightly', 'gently', 'lovingly', 'aggressively', 'kindly', 'tenderly'])
            await ctx.send(f"{ctx.author.display_name} {adv} boops {self._mention(ctx, user)}'s snoot. Aaaaaa!")

    @slash(name='smooch', description='Give someone a big smooch!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def smooch(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(f'{ctx.author.display_name} tries to smooch themselves... How is that possible?')
        else:
            location = choice(['cheek', 'head', 'booper', 'snoot', 'face', 'lips', 'tail', 'neck', 'paws', 'beans',
                               'ears', 'tummy', 'shoulder', 'forehead', 'eyeball', 'arms'])
            adj = choice(['lovely', 'sweet', 'affectionate', 'delightful', 'friendly', 'warm', 'wet', 'loud'])
            message = f'{ctx.author.display_name} gives {self._mention(ctx, user)} a {adj} smooch on the {location}.'
            if user == self._bot.user:
                message += ' Bzzzt. A shocking experience.'
            await ctx.send(message)

    @slash(name='cuddle', description="Give a cutie some cuddles",
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def cuddle(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(
                f"{ctx.author.display_name} can't find anyone to cuddle, so they decided to pull their tail in front "
                f"and cuddle it instead.")
        else:
            await ctx.send(
                f'{ctx.author.display_name} pulls {self._mention(ctx, user)} into their arm for a long cuddle.')

    @slash(name='snug', description="Give someone some snuggles",
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
    async def snug(self, ctx: SlashContext, user: User) -> None:
        if ctx.author == user:
            await ctx.send(
                f"{ctx.author.display_name} can't find a hot werewolf boyfriend to snuggle, so they decide to snuggle "
                f"a daki with themselves on it.")
        else:
            await ctx.send(f'{ctx.author.display_name} snuggles the heck out of {self._mention(ctx, user)}!')

    @slash(name='tuck', description='Tuck someone into bed!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
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

    @slash(name='tacklehug', description='Bam!',
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 10.0, BucketType.member)
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

    @slash(name='scream', description='Scream!')
    @cooldown(1, 5.0, BucketType.member)
    async def scream(self, ctx: SlashContext) -> None:
        char = choice(['A'] * 20 + ['🅰', '🇦 '])
        await ctx.send(char * randint(1, 35) + '!')

    @slash(name='awoo', description='Howl!')
    @cooldown(1, 5.0, BucketType.member)
    async def awoo(self, ctx: SlashContext) -> None:
        await ctx.send('Awoo' + 'o' * randint(0, 25) + '!')

    @slash(name='cute', description="So cute!",
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 20.0, BucketType.member)
    async def cute(self, ctx: SlashContext, user: User) -> None:
        if user == self._bot.user:
            await ctx.reply('No U.')
        else:
            phrase = choice(['Such a cutie! :-3', 'How cute!', "I can't get over how cute they are!",
                             "I can't believe they're so cute!", "Why are they so cute?", "*melts to their cuteness*"])
            await ctx.reply(f"Aww, Look at {self._mention(ctx, user)}... {phrase}")

    @slash(name='roll', description="Roll a die.",
           options=[create_option(name='sides', description='Number of sides (default 6)', option_type=int,
                                  required=False)],
           )
    @cooldown(1, 5.0, BucketType.member)
    async def roll(self, ctx: SlashContext, sides: int = 6) -> None:
        if sides <= 1:
            await ctx.reply(f"{ctx.author.display_name} tries to roll a {sides}-sided die, but created a black hole "
                            f"instead, because it can't possibly exist. ")
        elif random() < 0.01:
            await ctx.reply(f"{ctx.author.display_name} rolls a... darn it. It bounced down the stairs into the "
                            f"dungeon.")
        else:
            await ctx.reply(f"{ctx.author.display_name} rolls a {randint(1, sides)} on a d{sides}.")

    @slash(name='8ball', description="Shake a magic 8 ball.")
    @cooldown(1, 5.0, BucketType.member)
    async def eightball(self, ctx: SlashContext) -> None:
        await ctx.reply(choice([
            'As I see it, yes.',
            'Ask again later.',
            'Better not tell you now.',
            'Cannot predict now.',
            'Concentrate and ask again.',
            "Don't count on it.",
            'It is certain.',
            'It is decidedly so.',
            'Most likely.',
            'My reply is no.',
            'My sources say no.',
            'Outlook good.',
            'Outlook not so good.',
            'Reply hazy, try again.',
            'Signs point to yes.',
            'Very doubtful.',
            'Without a doubt.',
            'Yes, definitely.',
            'Yes.',
            'You may rely on it.',
        ]))

    @slash(name='flip', description="Flip a coin.")
    @cooldown(1, 5.0, BucketType.member)
    async def flip(self, ctx: SlashContext) -> None:
        if random() < 0.99:
            await ctx.reply(f"It's {choice(['heads', 'tails'])}.")
        else:
            await ctx.reply("It's... hecc, it went under the couch.")

    @slash(name='snipe', description="It's bloody murderrrr",
           options=[create_option(name='user', description='Target user', option_type=User, required=True)],
           )
    @cooldown(1, 60.0, BucketType.member)
    async def snipe(self, ctx: SlashContext, user: User) -> None:
        if user == self._bot.user:
            await ctx.reply(f"{ctx.author.display_name} dares to snipe {self._mention(ctx, user)}. The rifle "
                            "explodes, taking their paws with it.")
        elif user == ctx.author:
            result = "BANG! The gun goes." if random() < 1 / 6 else "Whew, it's a blank."
            await ctx.reply(f"{ctx.author.display_name} plays Russian Roulette with a revolver. {result}")
        elif (prob := random()) < 0.50:
            reason = choice([
                'they get distracted and went to chase a squirrel instead',
                'they only have a knife in the gun fight',
                'they went to watch stream and forgot about it all',
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

    @slash(
        name='localtime',
        description='Display a time you enter for everyone as their local time.',
        options=[
            create_option(name='time', description='A particular date and/or time, e.g. 2020/01/01 00:00:00',
                          option_type=str, required=True),
            create_option(name='timezone', description='Time zone you are in', option_type=str, required=True),
        ],
    )
    async def localtime(self, ctx: SlashContext, time: str, timezone: str) -> None:
        try:
            tz = pytz.timezone(timezone.strip())
        except pytz.UnknownTimeZoneError as e:
            raise DingomataUserError(
                f'Could not set your bedtime because timezone {timezone} is not recognized. Please use one of the '
                f'"TZ Database Name"s listed here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'
            ) from e
        time_obj, status = _calendar.parseDT(time, datetime.utcnow().astimezone(tz), tzinfo=tz)
        if status != 3:
            raise DingomataUserError(
                f"Can't interpret {time} as a valid date/time. Try using something like `today 5pm`, or for a "
                f"full date, `2021-12-20 01:05`")
        await ctx.reply(f'{time} in {tz} is <t:{int(time_obj.timestamp())}:f> your local time.')

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if (message.guild and message.guild.id in service_config.get_command_guilds('replies')
                and (self._bot.user in message.mentions or self._BOT_NAME_REGEX.search(message.content))
                and message.author != self._bot.user):
            for reply in service_config.servers[message.guild.id].text.replies:
                if reply.regex.search(message.content):
                    await message.reply(choice(reply.responses))
                    break  # Stop after first match

    @staticmethod
    def _mention(ctx: SlashContext, user: User) -> str:
        """Return a user's mention string, or display name if they're in the no-ping list"""
        no_pings = service_config.servers[ctx.guild.id].text.no_pings
        member = ctx.guild.get_member(user.id)
        if member and member.id in no_pings or any(role.id in no_pings for role in member.roles):
            return user.display_name
        else:
            return user.mention
