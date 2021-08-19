import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from discord import User, Embed, Color, Forbidden
from discord.ext import tasks
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_subcommand
from discord_slash.utils.manage_commands import create_option, create_choice
from sqlalchemy import func, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import rank

from .models import GambaUser, GambaModel, GambaGame, GambaBet
from ...config import get_guilds, get_mod_permissions, get_guild_config
from ...exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class InsufficientBalanceError(DingomataUserError):
    pass


class NonpositivePointsError(DingomataUserError):
    pass


class GambaUserError(DingomataUserError):
    pass


# These really should just be a one-time dict but the slash library mutates input dicts...
_BASE_MOD_COMMAND = dict(base='gamble', guild_ids=get_guilds(), base_default_permission=False)
_BASE_USER_COMMAND = dict(base='gamba', guild_ids=get_guilds())


class GameStatus(Enum):
    CANCELLED = 1
    COMPLETE = 2


class GambaCog(Cog, name='GAMBA'):
    """Gamble with server points."""
    _CHOICES = [
        create_choice(name='believe', value='a'),
        create_choice(name='doubt', value='b'),
    ]

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(GambaModel.metadata.create_all)
            self.gamba_message_updater.start()

    def cog_unload(self):
        self.gamba_message_updater.stop()

    # ### MOD COMMANDS ###
    @cog_subcommand(
        name='start',
        description='Start a new gamba.',
        options=[
            create_option(name='title', description='Title for the prediction', option_type=str, required=True),
            create_option(name='believe', description='Name of the "believe" outcome', option_type=str, required=True),
            create_option(name='doubt', description='Name of the "doubt" outcome', option_type=str, required=True),
            create_option(name='timeout', description='Number of minutes to take bets (up to 10); defaults to 1.',
                          option_type=int, required=False)
        ],
        base_permissions=get_mod_permissions(),
        **_BASE_MOD_COMMAND,
    )
    async def start(self, ctx: SlashContext, title: str, believe: str, doubt: str, timeout: int = 2):
        if not 0 < timeout <= 10:
            raise GambaUserError(f"Timeout must between 1 and 10 minutes.")
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaGame).filter(GambaGame.guild_id == ctx.guild.id)
                existing = (await session.execute(stmt)).scalar()
                _log.debug(f"Existing gamba game for {ctx.guild.id}: {existing}")
                if existing:
                    raise GambaUserError(
                        f"There's already a gamba running in {self._bot.get_channel(existing.channel_id)} right now: "
                        f"{existing.title}. You must pay it out or refund it before starting another one.")
                end_time = datetime.utcnow() + timedelta(minutes=timeout)
                game = GambaGame(guild_id=ctx.guild.id, channel_id=ctx.channel.id, title=title, option_a=believe,
                                 option_b=doubt, open_until=end_time, is_open=True, creator_user_id=ctx.author.id)
                _log.debug(f"New gamba: server {game.guild_id} channel {game.channel_id} open until {end_time}")
                embed = await self._generate_gamba_embed(game)
                message = await ctx.channel.send(embed=embed)
                game.message_id = message.id
                session.add(game)
                await session.commit()
                await ctx.reply(f'A new gamba has been started!')

    @tasks.loop(seconds=2)
    async def gamba_message_updater(self):
        # Find all open gambas
        now = datetime.utcnow()
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaGame).filter(GambaGame.is_open.is_(True), GambaGame.message_id.isnot(None))
                games = (await session.execute(stmt)).scalars()
                for game in games:
                    if game.open_until < now:
                        game.is_open = False
                        await session.commit()
                    message = self._bot.get_channel(game.channel_id).get_partial_message(game.message_id)
                    embed = await self._generate_gamba_embed(game)
                    await message.edit(embed=embed)

    async def _generate_gamba_embed(self, game: GambaGame, status: Optional[GameStatus] = None) -> Embed:
        points_name = get_guild_config(game.guild_id).gamba.points_name
        async with self._session() as session:
            async with session.begin():
                # Get the amounts for each side
                stmt = select(
                    func.coalesce(func.sum(GambaBet.option_a), 0).label('amount_a'),
                    func.coalesce(func.sum(GambaBet.option_b), 0).label('amount_b'),
                    func.count(GambaBet.option_a).label('count_a'),
                    func.count(GambaBet.option_b).label('count_b'),
                ).filter(GambaBet.guild_id == game.guild_id)
                points = (await session.execute(stmt)).first()
                if not points or (points.amount_a == 0 and points.amount_b == 0):
                    amount_a = amount_b = count_a = count_b = pct_a = pct_b = 0
                else:
                    amount_a, amount_b = points.amount_a, points.amount_b
                    count_a, count_b = points.count_a, points.count_b
                    pct_a = round(amount_a / (amount_a + amount_b) * 100, 1)
                    pct_b = round(100 - pct_a, 1)
                if pct_a == 0 or pct_b == 0:
                    ratio_a = ratio_b = 1
                else:
                    ratio_a, ratio_b = round(100 / pct_a, 2), round(100 / pct_b, 2)
                if status == GameStatus.CANCELLED:
                    description = 'This gamba has been cancelled.'
                    color = Color.dark_grey()
                elif status == GameStatus.COMPLETE:
                    color = Color.blue()
                elif game.is_open:
                    time_left = relativedelta(game.open_until, datetime.utcnow()).normalized()
                    description = 'Place your bets using the `/gamba believe` and `/gamba doubt` commands.\n'
                    description += f'{time_left.minutes} minutes {time_left.seconds} seconds left...'
                    color = Color.green()
                else:
                    description = 'All bets are in, waiting on results...'
                    color = Color.orange()
                embed = Embed(title=game.title, description=description, color=color)
                embed.add_field(
                    name='[Believe] ' + game.option_a,
                    value=f'**{pct_a}%**\n{amount_a:,} {points_name}\n{count_a:,} members\n1:{ratio_a:.2f}',
                    inline=True
                )
                embed.add_field(
                    name='[Doubt] ' + game.option_b,
                    value=f'**{pct_b}%**\n{amount_b:,} {points_name}\n{count_b:,} members\n1:{ratio_b:.2f}',
                    inline=True
                )
        return embed

    @cog_subcommand(
        name='payout',
        description='Pay out the current gamba.',
        options=[create_option(
            name='outcome', description='Select the outcome that won', option_type=str, required=True, choices=_CHOICES,
        )],
        **_BASE_MOD_COMMAND,
    )
    async def payout(self, ctx: SlashContext, outcome: str):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        async with self._session() as session:
            async with session.begin():
                # Check if the current user made a bet
                user = (await session.execute(select(GambaBet.user_id).filter(
                    GambaBet.guild_id == ctx.guild.id, GambaBet.user_id == ctx.author.id)
                )).scalar()
                if user:
                    raise GambaUserError(f"You can't pay out yourself after placing bets. Ask another mod to "
                                         f"do this instead. The mod who started the gamba can always pay out since "
                                         f"they cannot bet.")
                game = (await session.execute(select(GambaGame).filter(GambaGame.guild_id == ctx.guild.id))).scalar()
                if game.is_open:
                    raise GambaUserError(f"Betting have not ended for this gamba yet.")

                # Compute payout ratio
                stmt = select(
                    func.coalesce(func.sum(GambaBet.option_a), 0).label('amount_a'),
                    func.coalesce(func.sum(GambaBet.option_b), 0).label('amount_b'),
                    func.count(GambaBet.option_a).label('count_a'),
                    func.count(GambaBet.option_b).label('count_b'),
                ).filter(GambaBet.guild_id == game.guild_id)
                totals = (await session.execute(stmt)).first()
                if totals.amount_a == 0 or totals.amount_b == 0:
                    ratio = 1  # Everyone either won (ratio 1) or lost (ratio irrelevant)
                elif outcome == 'a':
                    ratio = (totals.amount_a + totals.amount_b) / totals.amount_a
                else:
                    ratio = (totals.amount_a + totals.amount_b) / totals.amount_b

                # Update everyone's payouts in the database
                payout = (GambaBet.option_a if outcome == 'a' else GambaBet.option_b) * ratio
                await session.execute(update(GambaUser).filter(
                    GambaUser.guild_id == ctx.guild.id,
                    GambaUser.guild_id == GambaBet.guild_id,
                    GambaUser.user_id == GambaBet.user_id,
                ).values({
                    GambaUser.balance: GambaUser.balance + func.coalesce(payout, 0)
                }).execution_options(synchronize_session="fetch"))

                # Get everyone's information and updated points
                bets = await session.execute(
                    select(GambaBet.option_a, GambaBet.option_b, GambaUser.user_id, GambaUser.balance).join(
                        GambaUser, and_(GambaBet.guild_id == GambaUser.guild_id, GambaBet.user_id == GambaUser.user_id)
                    ).filter(GambaBet.guild_id == ctx.guild_id)
                )

                # Update the embed and send a new embed
                embed = await self._generate_gamba_embed(game, GameStatus.CANCELLED)
                embed.description = f'{totals.amount_a + totals.amount_b} {points_name} goes to ' \
                                    f'{totals.count_a if outcome == "a" else totals.count_b} users.'
                message = self._bot.get_channel(game.channel_id).get_partial_message(game.message_id)
                await message.edit(embed=embed)
                await ctx.reply('Payout is complete. Users are being sent private updates about their bet results. '
                                'Please do not start a new gamba until this process is complete.', hidden=True)

                # Send DMs to all participants
                for bet in bets:
                    won_amount = bet.option_a if outcome == 'a' else bet.option_b
                    user = self._bot.get_user(bet.user_id)
                    if not user:
                        _log.warning(f'Did not send a gamba result DM to {bet.user_id} because they do not seem '
                                     f'to be in the server anymore.')
                        continue
                    if not won_amount:
                        message = "Sorry, you did not bet on the winning option. Better luck next time!"
                    else:
                        message = f"Congrats! You won {round(won_amount * ratio):,} {points_name}. " \
                                  f"Your total is now {bet.balance:,}."
                    try:
                        await user.send(message)
                    except Forbidden:
                        _log.warning(f"Failed to send a gamba result DM to {user} because their DM is not open.")

                # Delete all bets and the game
                await session.execute(delete(GambaBet).filter(GambaBet.guild_id == ctx.guild.id))
                await session.execute(delete(GambaGame).filter(GambaGame.guild_id == ctx.guild.id))
                await session.commit()

                # Notify the mod
                await ctx.reply('All members have been notified. You can start a new gamba now.', hidden=True)

    @cog_subcommand(
        name='refund',
        description='Cancel the current gamba and refund all points to users.',
        **_BASE_MOD_COMMAND,
    )
    async def refund(self, ctx: SlashContext):
        async with self._session() as session:
            async with session.begin():
                game = (await session.execute(select(GambaGame).filter(GambaGame.guild_id == ctx.guild.id))).scalar()
                embed = await self._generate_gamba_embed(game, GameStatus.CANCELLED)

                await session.execute(update(GambaUser).filter(
                    GambaUser.guild_id == ctx.guild.id,
                    GambaUser.guild_id == GambaBet.guild_id,
                    GambaUser.user_id == GambaBet.user_id,
                ).values({
                    GambaUser.balance: GambaUser.balance + GambaBet.option_a + GambaBet.option_b
                }).execution_options(synchronize_session="fetch"))
                await session.execute(delete(GambaBet).filter(GambaBet.guild_id == ctx.guild.id))
                await session.delete(game)
                await self._bot.get_channel(game.channel_id).get_partial_message(game.message_id).edit(embed=embed)
                await ctx.reply(f'The current gamba has been cancelled and all points are refunded.', hidden=True)

    @cog_subcommand(
        name='leaderboard',
        description="Post a message with the top users by credits.",
        **_BASE_MOD_COMMAND,
    )
    async def mod_leaderboard(self, ctx: SlashContext):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaUser.user_id, GambaUser.balance,
                              rank().over(order_by=GambaUser.balance.desc()).label('rank')).filter(
                    GambaUser.guild_id == ctx.guild.id).order_by(GambaUser.balance.desc()).limit(10)
                users = await session.execute(stmt)
                table = self._generate_leaderboard_table(users)
                await ctx.reply(f'**{points_name.title()} Holder Leaderboard**\n```{table}```')

    @cog_subcommand(
        name='balance',
        description="Check any user's balance.",
        options=[
            create_option(name='user', description='Amount of points to bet', option_type=User, required=True),
        ],
        **_BASE_MOD_COMMAND,
    )
    async def mod_balance(self, ctx: SlashContext, user: User):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        balance = await self._get_balance(ctx.guild.id, user.id)
        await ctx.reply(f'{user.mention} has {balance:,} {points_name}.', hidden=True)

    @cog_subcommand(
        name='add',
        description="Add to a user's point balance. This action generates a public message.",
        options=[
            create_option(name='user', description='Whose points to modify.', option_type=User, required=True),
            create_option(name='amount', description='Amount of points to add.', option_type=int, required=True),
        ],
        **_BASE_MOD_COMMAND,
    )
    async def mod_add(self, ctx: SlashContext, user: User, amount: int):
        await self._mod_transact(ctx, user, amount, True)

    @cog_subcommand(
        name='deduct',
        description="Remove from a user's point balance. This action generates a public message.",
        options=[
            create_option(name='user', description='Whose points to modify.', option_type=User, required=True),
            create_option(name='amount', description='Amount of points to deduct.', option_type=int, required=True),
        ],
        **_BASE_MOD_COMMAND,
    )
    async def mod_deduct(self, ctx: SlashContext, user: User, amount: int):
        await self._mod_transact(ctx, user, amount, False)

    async def _mod_transact(self, ctx: SlashContext, user: User, amount: int, add: bool):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        if amount <= 0:
            raise NonpositivePointsError(f"You need to specify a positive amount.")
        if user == ctx.author:
            await ctx.reply(f"Now aren't you a sneaky little cutie. Go get another mod to do this for you.")
            return
        try:
            await self._change_point_amount(ctx.guild.id, user.id, amount if add else -amount)
        except InsufficientBalanceError as e:
            raise InsufficientBalanceError(f"{user} doesn't have enough {points_name} for this. They have {e.args[0]}")
        if add:
            await ctx.reply(f"{ctx.author.mention} added {amount} {points_name} to {user.mention}.")
        else:
            await ctx.reply(f"{ctx.author.mention} deducted {amount} {points_name} from {user.mention}.")

    @cog_subcommand(
        name='believe',
        description='Bet on believe.',
        options=[
            create_option(name='amount', description='Amount of points to bet', option_type=int, required=True),
        ],
        **_BASE_USER_COMMAND,
    )
    async def believe(self, ctx: SlashContext, amount: int):
        await self._make_bet(ctx, 'a', amount)

    @cog_subcommand(
        name='doubt',
        description='Bet on doubt.',
        options=[
            create_option(name='amount', description='Amount of points to bet', option_type=int, required=True),
        ],
        **_BASE_USER_COMMAND,
    )
    async def doubt(self, ctx: SlashContext, amount: int):
        await self._make_bet(ctx, 'b', amount)

    async def _make_bet(self, ctx: SlashContext, option: str, amount: int):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        if amount < 1:
            raise GambaUserError(f"You need to bet at least 1 {points_name}.")
        async with self._session() as session:
            async with session.begin():
                game = (await session.execute(select(GambaGame).filter(GambaGame.guild_id == ctx.guild.id))).scalar()
                if not game:
                    raise GambaUserError(f"There's no gamba going on right now.")
                if game.creator_user_id == ctx.author.id:
                    raise GambaUserError(f"You can't bet on a gamba you created. This is to ensure at least one "
                                         f"moderator can pay out the bet when it completes.")
                stmt = select(GambaBet).filter(GambaBet.guild_id == ctx.guild.id, GambaBet.user_id == ctx.author.id)
                bet = (await session.execute(stmt)).scalar()
                if not bet:
                    bet = GambaBet(guild_id=ctx.guild.id, user_id=ctx.author.id, option_a=None, option_b=None)
                if (option == 'a' and bet.option_b) or (option == 'b' and bet.option_a):
                    raise GambaUserError(f"You've already bet on the other option.")
                if option == 'a':
                    bet.option_a = (bet.option_a or 0) + amount
                else:
                    bet.option_b = (bet.option_b or 0) + amount
                balance = await self._change_point_amount(ctx.guild.id, ctx.author.id, -amount)
                if balance == 0:
                    await ctx.reply(f'{ctx.author.mention} just went all all-in on '
                                    f'{"believe" if option == "a" else "doubt"}!')
                await session.merge(bet)
                await session.commit()
                await ctx.reply(f"You've successfully made the bet. You've bet a total of "
                                f"{bet.option_a or bet.option_b} {points_name}.", hidden=True)

    @cog_subcommand(name='balance', description='Check your points balance.', **_BASE_USER_COMMAND)
    async def user_balance(self, ctx: SlashContext):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        balance = await self._get_balance(ctx.guild.id, ctx.author.id)
        if not balance:
            await ctx.reply(f"You have no {points_name} right now. If you haven't done so yet, use the `/daily` "
                            f"command to claim your daily {points_name}.", hidden=True)
        else:
            await ctx.reply(f"You have {balance:,} {points_name}.", hidden=True)
        pass

    @cog_subcommand(name='daily', description="Claim your daily points.", **_BASE_USER_COMMAND)
    async def daily(self, ctx: SlashContext):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaUser).filter(GambaUser.guild_id == ctx.guild.id, GambaUser.user_id == ctx.author.id)
                user = (await session.execute(stmt)).scalar()
                if not user:
                    user = GambaUser(guild_id=ctx.guild.id, user_id=ctx.author.id, balance=0)
                now = datetime.utcnow()
                if not user.last_claim or user.last_claim < now - timedelta(days=1):
                    user.balance += get_guild_config(ctx.guild.id).gamba.daily_points
                    user.last_claim = now
                    await session.merge(user)
                    await session.commit()
                    await ctx.reply(f"Here's your daily {points_name}! You now have {user.balance:,} {points_name}.",
                                    hidden=True)
                else:
                    _log.debug(f'Denied daily point for {ctx.author} because their last claim was {user.last_claim}')
                    time_remaining = relativedelta(user.last_claim + timedelta(days=1), now).normalized()
                    await ctx.reply(f"You've claimed {points_name} already in the last 24 hours. You can claim again "
                                    f"in {time_remaining.hours} hours {time_remaining.minutes} minutes.", hidden=True)

    @cog_subcommand(
        name='give',
        description="Give some of your points to another user.",
        options=[
            create_option(name='user', description='Who to give your points to', option_type=User, required=True),
            create_option(name='amount', description='Number of points to give', option_type=int, required=True),
        ],
        **_BASE_USER_COMMAND,
    )
    async def give(self, ctx: SlashContext, user: User, amount: int):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        if amount <= 0:
            raise NonpositivePointsError(f"Well that's just not nice, is it? You need to enter a positive number "
                                         f"of {points_name} to give.")
        await self._change_point_amount(ctx.guild.id, ctx.author.id, -amount)
        await self._change_point_amount(ctx.guild.id, user.id, amount)
        await ctx.reply(f"Success! You've given {amount} of your {points_name} to {user}.", hidden=True)

    @cog_subcommand(
        name='leaderboard',
        description="Show the top users and your position on the leaderboard",
        **_BASE_USER_COMMAND,
    )
    async def user_leaderboard(self, ctx: SlashContext):
        points_name = get_guild_config(ctx.guild.id).gamba.points_name
        # First figure out where the user is on the leaderboard
        async with self._session() as session:
            async with session.begin():
                subquery = select(GambaUser.user_id, GambaUser.balance,
                                  rank().over(order_by=GambaUser.balance.desc()).label('rank')).filter(
                    GambaUser.guild_id == ctx.guild.id).order_by(GambaUser.balance.desc()).subquery()
                stmt = select(subquery.c.rank).filter(subquery.c.user_id == ctx.author.id)
                user_rank = (await session.execute(stmt)).scalar()

                if not user_rank or user_rank < 15:
                    # Only print top 10
                    query = select(subquery).filter(subquery.c.rank < 15)
                    data = (await session.execute(query))
                    table = self._generate_leaderboard_table(data)
                else:
                    # Print everyone near the top
                    query = select(subquery).limit(10)
                    data = (await session.execute(query))
                    table = self._generate_leaderboard_table(data)
                    # Plus everyone near the given user
                    query = select(subquery).filter(subquery.c.rank.between(user_rank - 3, user_rank + 3))
                    data = (await session.execute(query))
                    table += '\n...\n' + self._generate_leaderboard_table(data)
                await ctx.reply(f'**{points_name.title()} Holder Leaderboard**\n```{table}```', hidden=True)

    async def _get_balance(self, guild_id: int, user_id: str) -> int:
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaUser.balance).filter(
                    GambaUser.guild_id == guild_id, GambaUser.user_id == user_id)
                return (await session.execute(stmt)).scalar() or 0

    async def _change_point_amount(self, guild_id: int, user_id: int, amount: int) -> int:
        """Change a user's point amount by a given value. Returns the user's new balance."""
        async with self._session() as session:
            async with session.begin():
                stmt = select(GambaUser).filter(GambaUser.guild_id == guild_id, GambaUser.user_id == user_id)
                user = (await session.execute(stmt)).scalar()
                if not user:
                    _log.debug(f"{user_id} is a new user, creating with zero balance.")
                    user = GambaUser(guild_id=guild_id, user_id=user_id, balance=0)
                if user.balance + amount < 0:
                    raise InsufficientBalanceError(user.balance)
                user.balance += amount
                _log.debug(f"Changed point balance for {user_id} to {user.balance}")
                await session.merge(user)
                await session.commit()
                return user.balance

    def _generate_leaderboard_table(self, data: List) -> str:
        result = ''
        for row in data:
            user = self._bot.get_user(row.user_id)
            username = user.display_name if user else "Unknown User"
            result += f'{row.rank:4} {username:24} {row.balance:,}\n'
        return result
