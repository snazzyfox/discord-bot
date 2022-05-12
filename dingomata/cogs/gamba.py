import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import discord
import tortoise.exceptions
import tortoise.functions as func
from discord.ext.tasks import loop
from prettytable import PrettyTable
from tortoise.expressions import F, Q

from ..config import service_config
from ..decorators import slash_group
from ..exceptions import DingomataUserError
from ..models import GambaGame, GambaUser
from ..utils import View
from .base import BaseCog

_log = logging.getLogger(__name__)


class InsufficientBalanceError(DingomataUserError):
    pass


class GambaUserError(DingomataUserError):
    pass


class GameStatus(Enum):
    CANCELLED = 1
    COMPLETE = 2


class GambaView(View):
    @discord.ui.button(label="Believe with 100", style=discord.ButtonStyle.blurple, custom_id="gamba.believe.100")
    async def believe(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        total = await GambaCog.make_bet(interaction, option="believe", amount=100)
        await interaction.response.send_message(f"Success! You've bet a total of {total}.", ephemeral=True)

    @discord.ui.button(label="Doubt with 100", style=discord.ButtonStyle.red, custom_id="gamba.doubt.100")
    async def doubt(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        total = await GambaCog.make_bet(interaction, option="doubt", amount=100)
        await interaction.response.send_message(f"Success! You've bet a total of {total}.", ephemeral=True)


class GambaCog(BaseCog):
    """Gamble with server points."""

    gamba = slash_group("gamba", "Gamble your points away!")
    gamble = slash_group("gamble", "Give people the opportunity to gamble their points away!", config_group="gamba")

    def __init__(self, bot: discord.Bot) -> None:
        super().__init__(bot)
        self._views: Dict[int, View] = {}

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self.gamba_message_updater.start()
        self.gamba_message_pin.start()

    def cog_unload(self) -> None:
        self.gamba_message_updater.stop()
        self.gamba_message_pin.stop()

    # ### MOD COMMANDS ###
    @gamble.command()
    @discord.option('title', description="Title for the prediction")
    @discord.option('believe', description="Name of the 'believe' outcome")
    @discord.option('doubt', description="Name of the 'doubt' outcome")
    @discord.option('timeout', description="Number of minutes to take bets", min_value=1, max_value=10)
    async def start(self, ctx: discord.ApplicationContext, title: str, believe: str, doubt: str, timeout: int = 2,
                    ) -> None:
        """Start a new gamba."""
        if await GambaGame.filter(guild_id=ctx.guild.id).exists():
            raise GambaUserError(
                "There's already a gamba running in this server. Pay it out or refund it before starting a new one."
            )
        end_time = datetime.utcnow() + timedelta(minutes=timeout)
        game = GambaGame(guild_id=ctx.guild.id, channel_id=ctx.channel.id, title=title, option_believe=believe,
                         option_doubt=doubt, open_until=end_time, is_open=True, creator_user_id=ctx.author.id)
        _log.debug(f"New gamba: server {game.guild_id} channel {game.channel_id} open until {end_time}")
        embed = await self._generate_gamba_embed(game)
        await ctx.respond("A new gamba has started!")
        message = await ctx.channel.send(embed=embed, view=GambaView())
        game.message_id = message.id
        await game.save(force_create=True)

    @gamble.command()
    @discord.option('outcome', description="The winning outcome", choices=["believe", "doubt"])
    async def payout(self, ctx: discord.ApplicationContext, outcome: str) -> None:
        """Select an outcome for the running gamba and pay the winners."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        async with tortoise.transactions.in_transaction() as tx:
            # Check if the current user made a bet
            current_user = await GambaUser.get_or_none(guild_id=ctx.guild.id, user_id=ctx.user.id)
            if current_user and (current_user.bet_doubt or current_user.bet_believe):
                raise GambaUserError("You can't pay out yourself after placing bets, you silly cutie. Ask another mod "
                                     "to do it instead. ")
            try:
                game = await GambaGame.select_for_update().using_db(tx).get(guild_id=ctx.guild.id)
            except tortoise.exceptions.DoesNotExist as e:
                raise GambaUserError("There is no active gamba in this server.") from e
            if game.is_open:
                raise GambaUserError("Betting have not ended for this gamba yet.")

            # Compute payout ratio
            amount_believe, amount_doubt, count_believe, count_doubt = await self._get_gamba_stats(game.guild_id)
            if amount_believe == 0 or amount_doubt == 0:
                ratio = 1.0  # Everyone either won (ratio 1) or lost (ratio irrelevant)
            else:
                ratio = (amount_believe + amount_doubt) / (amount_believe if outcome == "believe" else amount_doubt)

            # Update everyone's payouts in the database
            payout = (F("bet_believe") if outcome == "believe" else F("bet_doubt")) * ratio

            participated_users = GambaUser.filter(
                Q(guild_id=ctx.guild.id) & (Q(bet_believe__gt=0) | Q(bet_doubt__gt=0)))
            await participated_users.using_db(tx).update(balance=F("balance") + payout)

            # Get everyone's information and updated points
            bets = await participated_users.all()

            # Update the embed and send a new embed
            embed = await self._generate_gamba_embed(game, GameStatus.COMPLETE)
            embed.description = (f"{amount_believe + amount_doubt} {points_name} goes to "
                                 f'{count_believe if outcome == "believe" else count_doubt} users.')
            field_id = 0 if outcome == "believe" else 0
            field = embed.fields[field_id]
            embed.set_field_at(field_id, name="☑ " + field.name, value=field.value, inline=field.inline)
            message = self._bot_for(ctx.guild.id).get_channel(game.channel_id).get_partial_message(game.message_id)
            await message.edit(embed=embed)
            await ctx.respond("Payout is complete. Users are being sent private updates about their bet results. "
                              "Do not start a new gamba until this process is complete.", ephemeral=True)

            # Send a second embed because the original message may have scrolled long past
            await ctx.channel.send(embed=embed)

            # Send DMs to all participants
            for bet in bets:
                won_amount = bet.bet_believe if outcome == "believe" else bet.bet_doubt
                user = ctx.guild.get_member(bet.user_id)
                if not user:
                    _log.warning(f"Did not send gamba result DM to {bet.user_id} because they are not in the server.")
                    continue
                if not won_amount:
                    message = "Sorry, you did not bet on the winning option. Better luck next time!"
                else:
                    message = (f"Congrats! You won {round(won_amount * ratio):,} {points_name}. "
                               f"Your total is now {bet.balance:,}.")
                try:
                    await user.send(message)
                except discord.Forbidden:
                    _log.warning(f"Failed to send gamba result DM to {user} because their DM is not open.")

            # Delete all bets and the game
            await participated_users.using_db(tx).update(bet_believe=0, bet_doubt=0)
            await game.delete(using_db=tx)

            # Notify the mod
            await ctx.respond("All members have been notified. You can start a new gamba now.", ephemeral=True)

    @gamble.command()
    async def refund(self, ctx: discord.ApplicationContext):
        """Cancel the current gamba and refund all points to users."""
        async with tortoise.transactions.in_transaction() as tx:
            try:
                game = await GambaGame.select_for_update().using_db(tx).get(guild_id=ctx.guild.id)
            except tortoise.exceptions.DoesNotExist as e:
                raise GambaUserError("There is no gamba pending in this server.") from e

            embed = await self._generate_gamba_embed(game, GameStatus.CANCELLED)
            participated_users = GambaUser.filter(
                Q(guild_id=ctx.guild.id) & (Q(bet_believe__gt=0) | Q(bet_doubt__gt=0))
            )
            await participated_users.using_db(tx).update(
                balance=F("balance") + F("bet_believe") + F("bet_doubt"),
                bet_believe=0,
                bet_doubt=0,
            )
            await self._bot_for(ctx.guild.id).get_channel(game.channel_id).get_partial_message(game.message_id).edit(
                embed=embed)
            await game.delete(using_db=tx)
            await ctx.respond("The current gamba has been cancelled and all points are refunded.", ephemeral=True)

    @loop(seconds=2)
    async def gamba_message_updater(self):
        try:
            # Find all open gambas
            now = datetime.utcnow()
            async with tortoise.transactions.in_transaction() as tx:
                games = await GambaGame.filter(is_open=True, guild_id__in=self.gamba.guild_ids).using_db(tx).all()
                for game in games:
                    view = self._views.get(game.guild_id)
                    if game.open_until < now:
                        game.is_open = False
                        if view:
                            view.stop()
                            self._views.pop(game.guild_id)
                            view = None
                    else:
                        if not view:
                            view = GambaView(timeout=(game.open_until - now).total_seconds())
                            self._views[game.guild_id] = view
                    embed = await self._generate_gamba_embed(game)
                    channel = self._bot_for(game.guild_id).get_channel(game.channel_id)
                    message = channel.get_partial_message(game.message_id)
                    await message.edit(embed=embed, view=view)
                    await game.save(using_db=tx)
        except Exception as e:
            _log.exception(e)

    @loop(seconds=15)
    async def gamba_message_pin(self):
        try:
            async with tortoise.transactions.in_transaction() as tx:
                games = await GambaGame.select_for_update().filter(
                    is_open=True, guild_id__in=self.gamba.guild_ids).using_db(tx).all()
                for game in games:
                    channel = self._bot_for(game.guild_id).get_channel(game.channel_id)
                    if channel.last_message_id != game.message_id:
                        embed = await self._generate_gamba_embed(game)
                        view = self._views.get(game.guild_id)
                        message = channel.get_partial_message(game.message_id)
                        await message.delete()
                        new_message = await channel.send(embed=embed, view=view)
                        game.message_id = new_message.id
                        await game.save(using_db=tx)
        except Exception as e:
            _log.exception(e)

    @gamble.command(name="leaderboard")
    async def mod_leaderboard(self, ctx: discord.ApplicationContext):
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        # tortoise do not support window functions
        sql = """
        SELECT user_id, balance, rank() over (order by balance desc) as rank
        FROM gamba_user
        WHERE guild_id = $1
        ORDER BY balance DESC
        LIMIT 10
        """
        conn = tortoise.Tortoise.get_connection("default")
        data = await conn.execute_query_dict(sql, [ctx.guild.id])
        table = self._generate_leaderboard_rows(ctx.guild, data)
        await ctx.respond(f"**{points_name.title()} Holder Leaderboard**\n```{table}```")

    @gamble.command(name="balance")
    @discord.option('user', description="Whose balance to check")
    async def mod_balance(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Check any user's balance"""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        balance = await self._get_balance(ctx.guild.id, user.id)
        await ctx.respond(f"{user.mention} has {balance:,} {points_name}.", ephemeral=True)

    @gamble.command()
    @discord.option('user', description="Whose points balance to modify")
    @discord.option('amount', description="Amount of points to add. Use a negative number to deduct.")
    async def change(self, ctx: discord.ApplicationContext, user: discord.User, amount: int) -> None:
        """Change a user's point balance. This action generates a public message."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        if user == ctx.author:
            await ctx.respond("Now aren't you a sneaky little cutie. Go get another mod to do this for you.")
            return
        async with tortoise.transactions.in_transaction() as tx:
            gamba_user, _ = await GambaUser.get_or_create(guild_id=ctx.guild.id, user_id=user.id, using_db=tx)
            self._change_balance(gamba_user, amount)
            await gamba_user.save(using_db=tx)
        await ctx.respond(f"{ctx.author.mention} updated {user.mention}'s {points_name} by {amount}.")

    # ### USER COMMANDS ###
    @gamba.command()
    @discord.option('amount', description="Number of points to bet")
    async def believe(self, ctx: discord.ApplicationContext, amount: int) -> None:
        """Bet on believe."""
        total = await self.make_bet(ctx, "believe", amount)
        await ctx.respond(f"Success! You've bet a total of {total}.", ephemeral=True)

    @gamba.command()
    @discord.option('amount', description="Number of points to bet")
    async def doubt(self, ctx: discord.ApplicationContext, amount: int) -> None:
        """Bet on doubt."""
        total = await self.make_bet(ctx, "doubt", amount)
        await ctx.respond(f"Success! You've bet a total of {total}.", ephemeral=True)

    @classmethod
    async def make_bet(
            cls,
            ctx: discord.ApplicationContext | discord.Interaction,
            option: str,
            amount: int,
    ) -> str:
        """Makes a bet. Returns a string that's the total number of points and point name, e.g. '200 cheddar'."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        if amount < 1:
            raise GambaUserError(f"You need to bet at least 1 {points_name}.")
        async with tortoise.transactions.in_transaction() as tx:
            try:
                game = await GambaGame.get(guild_id=ctx.guild.id)
            except tortoise.exceptions.DoesNotExist:
                raise GambaUserError("There's no gamba going on right now.")
            if not game.is_open:
                raise GambaUserError("The gamba has closed already.")
            if game.creator_user_id == ctx.user.id:
                raise GambaUserError(
                    "You can't bet on a gamba you created. This is to ensure at least one moderator "
                    "can pay out the bet when it completes."
                )
            user, _ = await GambaUser.get_or_create(guild_id=ctx.guild.id, user_id=ctx.user.id, using_db=tx)
            if (option == "doubt" and user.bet_believe) or (option == "believe" and user.bet_doubt):
                raise GambaUserError("You've already bet on the other option.")
            if option == "believe":
                user.bet_believe = (user.bet_believe or 0) + amount
            else:
                user.bet_doubt = (user.bet_doubt or 0) + amount
            cls._change_balance(user, -amount)
            if user.balance == 0:
                await ctx.respond(f"{ctx.user.mention} just went all all-in on {option}!")
            await user.save(using_db=tx)
            return user.bet_believe or user.bet_doubt

    @gamba.command(name="balance")
    async def user_balance(self, ctx: discord.ApplicationContext) -> None:
        """Check your points balance."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        balance = await self._get_balance(ctx.guild.id, ctx.author.id)
        if not balance:
            await ctx.respond(f"You have no {points_name} right now. If you haven't done so yet, use the "
                              f"`/gamba daily` command to claim your daily {points_name}.", ephemeral=True)
        else:
            await ctx.respond(f"You have {balance:,} {points_name}.", ephemeral=True)

    @gamba.command()
    async def daily(self, ctx: discord.ApplicationContext):
        """Claim your daily points."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        async with tortoise.transactions.in_transaction() as tx:
            user, _ = await GambaUser.get_or_create(guild_id=ctx.guild.id, user_id=ctx.user.id, using_db=tx)
            now = datetime.utcnow()
            if user.last_claim is None or user.last_claim < now - timedelta(days=1):
                user.balance += service_config.server[ctx.guild.id].gamba.daily_points
                user.last_claim = now
                await user.save(using_db=tx)
                await ctx.respond(
                    f"Here's your daily {points_name}! You now have {user.balance:,} {points_name}.", ephemeral=True)
            else:
                _log.debug(f"Denied daily point for {ctx.author} because their last claim was {user.last_claim}")
                sec_remaining = int((user.last_claim + timedelta(days=1) - now).total_seconds())
                await ctx.respond(
                    f"You've claimed {points_name} already in the last 24 hours. You can claim again "
                    f"in {sec_remaining // 3600} hours {sec_remaining % 3600 // 60} minutes.",
                    ephemeral=True,
                )

    @gamba.command()
    @discord.option('user', description="Who to give your points to")
    @discord.option('amount', description="Amount of points to give", min_value=1)
    async def give(self, ctx: discord.ApplicationContext, user: discord.User, amount: int) -> None:
        """Give some of your points to another user."""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        async with tortoise.transactions.in_transaction() as tx:
            current_user, _ = await GambaUser.get_or_create(guild_id=ctx.guild.id, user_id=ctx.author.id, using_db=tx)
            target_user, _ = await GambaUser.get_or_create(guild_id=ctx.guild.id, user_id=user.id, using_db=tx)
            self._change_balance(current_user, -amount)
            self._change_balance(target_user, amount)
            await current_user.save(using_db=tx)
            await target_user.save(using_db=tx)
        await ctx.respond(f"Success! You've given {amount} of your {points_name} to {user}.", ephemeral=True)

    @gamba.command(name="leaderboard")
    async def user_leaderboard(self, ctx: discord.ApplicationContext):
        """Show top users in the server and your position on the leaderboard"""
        points_name = service_config.server[ctx.guild.id].gamba.points_name
        # First figure out where the user is on the leaderboard
        # tortoise do not support window functions
        all_query = """
        SELECT user_id, balance, rank() over (order by balance desc) as rank
        FROM gamba_user
        WHERE guild_id = $1
        ORDER BY balance DESC
        """
        current_user_query = f"""
        SELECT rank
        FROM ({all_query}) a
        WHERE user_id = $2
        """  # noqa: S608
        top_query = f"SELECT * FROM ({all_query}) a WHERE rank < 10"  # noqa: S608

        conn = tortoise.Tortoise.get_connection("default")
        data = await conn.execute_query_dict(current_user_query, [ctx.guild.id, ctx.author.id])
        user_rank = data[0]["rank"] if data else None

        # Always print top 10
        data = await conn.execute_query_dict(top_query, [ctx.guild.id])
        table = self._generate_leaderboard_rows(ctx.guild, data)

        if user_rank and user_rank > 10:
            # Plus everyone near the given user
            nearby_query = f"SELECT * FROM ({all_query}) a WHERE rank BETWEEN $2 AND $3"  # noqa: S608
            data = await conn.execute_query_dict(nearby_query, [ctx.guild.id, max(11, user_rank - 3), user_rank + 3])
            table.add_row(("...", "...", "..."))
            self._generate_leaderboard_rows(ctx.guild, data, table)
        await ctx.respond(f"**{points_name.title()} Holder Leaderboard**\n```{table}```", ephemeral=True)

    @staticmethod
    async def _get_balance(guild_id: int, user_id: int) -> int:
        try:
            return (await GambaUser.get(guild_id=guild_id, user_id=user_id).only("balance")).balance
        except tortoise.exceptions.DoesNotExist:
            return 0

    @staticmethod
    def _change_balance(user: GambaUser, delta: int) -> None:
        """Change a user's balance by a given value, throwing an error if the change results in negative balance."""
        if user.balance + delta < 0:
            raise InsufficientBalanceError(f"You do not have enough points to do this. You have: {user.balance}.")
        user.balance += delta

    @staticmethod
    def _generate_leaderboard_rows(
            guild: discord.Guild,
            data: List[Dict],
            table: Optional[PrettyTable] = None,
    ) -> PrettyTable:
        if not table:
            table = PrettyTable()
            table.field_names = ["Rank", "User", "Balance"]
            table.align["Rank"] = "r"
            table.align["User"] = "l"
            table.align["Balance"] = "r"
        for row in data:
            user = guild.get_member(row["user_id"])
            username = user.display_name if user else "Unknown User"
            table.add_row((row["rank"], username, f"{row['balance']:,}"))
        return table

    @staticmethod
    async def _get_gamba_stats(guild_id: int) -> Tuple[int, int, int, int]:
        return await GambaUser.filter(guild_id=guild_id).annotate(
            amount_believe=func.Coalesce(func.Sum("bet_believe"), 0),
            amount_doubt=func.Coalesce(func.Sum("bet_doubt"), 0),
            count_believe=func.Count("bet_believe"),
            count_doubt=func.Count("bet_doubt"),
        ).first().values_list("amount_believe", "amount_doubt", "count_believe", "count_doubt")

    @classmethod
    async def _generate_gamba_embed(cls, game: GambaGame, status: Optional[GameStatus] = None) -> discord.Embed:
        points_name = service_config.server[game.guild_id].gamba.points_name
        amount_believe, amount_doubt, count_believe, count_doubt = await cls._get_gamba_stats(game.guild_id)
        if amount_believe == 0 and amount_doubt == 0:
            pct_believe = pct_doubt = 0.0
        else:
            pct_believe = amount_believe / (amount_believe + amount_doubt)
            pct_doubt = 1 - pct_believe
        if pct_believe == 0 or pct_doubt == 0:
            ratio_believe = ratio_doubt = 1
        else:
            ratio_believe, ratio_doubt = round(1 / pct_believe), round(1 / pct_doubt)
        if status == GameStatus.CANCELLED:
            description = "This gamba has been cancelled."
            color = discord.Color.dark_grey()
        elif status == GameStatus.COMPLETE:
            description = ""
            color = discord.Color.blue()
        elif game.is_open:
            time_remaining_sec = int((game.open_until - datetime.utcnow()).total_seconds())
            description = "Place your bets using the `/gamba believe` and `/gamba doubt` commands.\n"
            description += f"{time_remaining_sec // 60}:{time_remaining_sec % 60:02} left to make your predictions..."
            color = discord.Color.green()
        else:
            description = "All bets are in, waiting on results."
            color = discord.Color.orange()
        embed = discord.Embed(title=game.title, description=description, color=color)
        embed.add_field(
            name="[Believe] " + game.option_believe,
            value=f"**{pct_believe:.1%}**\n{amount_believe:,} "
                  f"{points_name}\n{count_believe:,} members\n1:{ratio_believe:.2f}",
            inline=True,
        )
        embed.add_field(
            name="[Doubt] " + game.option_doubt,
            value=f"**{pct_doubt:.1%}**\n{amount_doubt:,} "
                  f"{points_name}\n{count_doubt:,} members\n1:{ratio_doubt:.2f}",
            inline=True,
        )
        return embed
