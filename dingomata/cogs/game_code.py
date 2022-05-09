import logging
import random
from enum import Enum
from typing import Dict

import discord
import tortoise.functions as func
import tortoise.transactions

from ..config import service_config
from ..decorators import slash_group
from ..exceptions import DingomataUserError
from ..models import GamePool, GamePoolEntry
from ..utils import View
from .base import BaseCog

log = logging.getLogger(__name__)


class EntryStatus(Enum):
    ELIGIBLE = 1
    SELECTED = 2
    PLAYED = 3


class GameMode(Enum):
    NEW_PLAYERS_ONLY = 1
    ANYONE = 2


class LeaveButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        self._guild_id = guild_id
        super().__init__(label="Leave", style=discord.ButtonStyle.red, custom_id=f"gamecode.leave:{guild_id}")

    async def callback(self, interaction: discord.Interaction) -> None:
        async with tortoise.transactions.in_transaction() as tx:
            # Make sure there's an open pool
            if not await GamePool.filter(guild_id=self._guild_id, is_accepting_entries=True).using_db(tx).exists():
                raise DingomataUserError("The game is not accepting entries at this time.")
            # Delete the entry only if they're in eligible status
            deleted_count = await GamePoolEntry.filter(
                guild_id=self._guild_id, user_id=interaction.user.id, status=EntryStatus.ELIGIBLE.value,
            ).using_db(tx).delete()
            if not deleted_count:
                raise DingomataUserError("You have not entered into the game.")
        await interaction.message.edit(content="You have left the game.", view=None)


class LeaveView(View):
    def __init__(self, guild_id: int):
        super(LeaveView, self).__init__(timeout=None)
        self.add_item(LeaveButton(guild_id))


class JoinButton(discord.ui.Button):
    def __init__(self, guild_id: int, leave_view: LeaveView):
        self._guild_id = guild_id
        self._leave_view = leave_view
        super().__init__(label="Join", style=discord.ButtonStyle.green, custom_id=f"gamecode.join:{guild_id}")

    async def callback(self, interaction: discord.Interaction) -> None:
        # Compute the player's weight
        _player_roles = service_config.server[self._guild_id].game_code.player_roles
        if not _player_roles:
            weight = 1
        else:
            roles = [role.id for role in interaction.user.roles] + [0]
            weight = max(_player_roles.get(role, 0) for role in roles)
        if weight == 0:
            raise DingomataUserError("You cannot join this pool because you do not have the necessary roles.")

        # Make sure there's an open pool
        async with tortoise.transactions.in_transaction() as tx:
            if not await GamePool.filter(guild_id=self._guild_id, is_accepting_entries=True).using_db(tx).exists():
                raise DingomataUserError("The game is not accepting entries at this time.")

        # Create a new entry
        try:
            await GamePoolEntry.create(guild_id=self._guild_id, user_id=interaction.user.id, weight=weight,
                                       status=EntryStatus.ELIGIBLE.value)
        except tortoise.exceptions.IntegrityError as e:
            raise DingomataUserError("You're already in the pool or have already played in an earlier game.") from e

        try:
            await interaction.user.send("You've joined the game. I'll send you your super secret message here if "
                                        "you're selected. If you no longer wish to play, click the button below.",
                                        view=self._leave_view)
            await interaction.response.send_message("You've successfully joined the pool. Good luck!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Failed to join the game because I can't DM you. Please update "
                                                    "your server privacy settings to allow DMs, so that I can send "
                                                    "you your secret message if you're selected.", ephemeral=True)


class JoinView(View):
    def __init__(self, guild_id: int, leave_view: LeaveView):
        """
        :param guild_id: The server ID this view (button) is for
        :param leave_view: The LeaveView object that correspond to the same server. This is required in order to send
            persistent buttons to the user in DMs instead of in the server.
        """
        super(JoinView, self).__init__(timeout=None)
        self.add_item(JoinButton(guild_id, leave_view))


class GameCodeCog(BaseCog):
    """Randomly send game codes to people who join a game."""

    game = slash_group("game", "Manage game codes")

    def __init__(self, bot: discord.Bot):
        """Initialize application state."""
        super().__init__(bot)
        self._join_views: Dict[int, JoinView] = {}
        self._leave_views: Dict[int, LeaveView] = {}

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self._leave_views = {guild: LeaveView(guild) for guild in self.game.guild_ids}
        self._join_views = {guild: JoinView(guild, self._leave_views[guild]) for guild in self.game.guild_ids}
        for view in self._join_views.values():
            self._bot.add_view(view)
        for view in self._leave_views.values():
            self._bot.add_view(view)

    @game.command()
    @discord.option('title', description="Name of the game to start")
    @discord.option('allow', description="Who can join the game", choices=[
        discord.OptionChoice("Anyone", GameMode.ANYONE.value),
        discord.OptionChoice("New Players Only", GameMode.NEW_PLAYERS_ONLY.value),
    ])
    async def open(self, ctx: discord.ApplicationContext, title: str, allow: int = GameMode.NEW_PLAYERS_ONLY.value,
                   ) -> None:
        """Open a new game pool for people to join."""
        await ctx.defer(ephemeral=True)
        async with tortoise.transactions.in_transaction() as tx:
            # Check there's no open pool
            exists = await GamePool.select_for_update().using_db(tx).filter(
                guild_id=ctx.guild.id, is_accepting_entries=True).exists()
            if exists:
                raise DingomataUserError("There is already an open game pool in this server.")
            # Mark players from previous rounds as played
            await GamePoolEntry.filter(guild_id=ctx.guild.id, status=EntryStatus.SELECTED.value).using_db(tx).update(
                status=EntryStatus.PLAYED.value)
            # Forget about everyone who hasn't played
            await GamePoolEntry.filter(guild_id=ctx.guild.id, status=EntryStatus.ELIGIBLE.value).using_db(tx).delete()

            # Open a new pool
            embed = discord.Embed(
                title=f"Now accepting players for {title}!",
                description="Click on Join to get in the pool! Make sure you allow DMs on this server so you "
                            "can receive the game code if you're selected.",
                color=discord.Color.gold(),
            )
            message = await ctx.channel.send(embed=embed, view=self._join_views[ctx.guild.id])

            await GamePool.update_or_create(
                {
                    'is_accepting_entries': True, 'title': title, 'mode': allow, 'channel_id': ctx.channel.id,
                    'message_id': message.id, 'guild_id': ctx.guild.id
                },
                using_db=tx)
            await ctx.respond("Pool is now open.", ephemeral=True)
            log.debug(f"Game pool opened: {title}")

    @game.command()
    async def close(self, ctx: discord.ApplicationContext) -> None:
        """Stop accepting more entries for the currently open game."""
        try:
            async with tortoise.transactions.in_transaction() as tx:
                pool: GamePool = await GamePool.select_for_update().using_db(tx).get(
                    guild_id=ctx.guild.id, is_accepting_entries=True)
                pool.is_accepting_entries = False
                await pool.save(using_db=tx)

        except tortoise.exceptions.DoesNotExist as e:
            raise DingomataUserError("There is no open pool in this server.") from e

        user_count, = await self._eligible_entries(pool).annotate(
            count=func.Count("user_id")).first().values_list("count")

        embed = discord.Embed(title=f"Pool for {pool.title} is now closed.", description=f"Total Entries: {user_count}",
                              color=discord.Color.dark_red())
        message = self._bot_for(ctx.guild.id).get_channel(pool.channel_id).get_partial_message(pool.message_id)
        await message.edit(embed=embed, view=None)
        await ctx.respond("Pool has been closed.", ephemeral=True)

    @game.command()
    @discord.option('count', description="Number of users to pick", min_value=1)
    @discord.option('message', description="Message to send to picked users")
    async def pick(self, ctx: discord.ApplicationContext, count: int, message: str) -> None:
        """Pick random eligible users from the pool and send them a DM."""
        await ctx.defer(ephemeral=True)
        try:
            async with tortoise.transactions.in_transaction() as tx:
                pool: GamePool = await GamePool.select_for_update().using_db(tx).get(guild_id=ctx.guild.id)
                pool.is_accepting_entries = False
                await pool.save(using_db=tx)
        except tortoise.exceptions.DoesNotExist as e:
            raise DingomataUserError("There is no open pool in this server.") from e

        eligible_users = await self._eligible_entries(pool)

        # Remove users who are not in the discord server.
        users = [(user, ctx.guild.get_member(user.user_id)) for user in eligible_users]
        users = [(pool_user, discord_user) for pool_user, discord_user in users if discord_user]
        user_count = len(users)
        if count > user_count:
            raise DingomataUserError(
                f"Cannot pick more member than there are in the pool. The pool has {user_count} eligible users."
            )
        # turn into parallel lists for sampling
        population, weights = zip(*((user, user[0].weight) for user in users))
        picked_users = random.sample(population=population, k=count, counts=weights)
        picked_user_ids = [pool_user.user_id for pool_user, _ in picked_users]

        # Change their status in database
        await GamePoolEntry.filter(guild_id=ctx.guild.id, user_id__in=picked_user_ids).update(
            status=EntryStatus.SELECTED.value)

        log.debug(f'Picked users: {", ".join(str(user) for _, user in picked_users)}')
        embed = discord.Embed(title="Congratulations! Check for your game code in DM's!",
                              description=f"Total entries: {user_count}\n", color=discord.Color.blue())
        embed.add_field(name="Selected Users", value="\n".join(user.display_name for _, user in picked_users))
        await ctx.channel.send(embed=embed)  # Don't reply to the command - that exposes the secret message!
        for _, user in picked_users:
            await self._send_dm(ctx, message, user)
        await ctx.respond("All done!", ephemeral=True)

    @game.command()
    @discord.option('message', description="Message to send")
    async def resend(self, ctx: discord.ApplicationContext, message: str) -> None:
        """Send a DM to all existing picked users."""
        await ctx.defer(ephemeral=True)
        entries = await GamePoolEntry.filter(guild_id=ctx.guild.id, status=EntryStatus.SELECTED.value)
        users = [ctx.guild.get_member(user.user_id) for user in entries]
        for user in users:
            if user is not None:
                await self._send_dm(ctx, message, user)
        await ctx.respond("All done!", ephemeral=True)

    @game.command()
    async def reset(self, ctx: discord.ApplicationContext) -> None:
        """Clear the pool and allow everyone to play again."""
        await GamePoolEntry.filter(guild_id=ctx.guild.id).delete()
        await ctx.respond("All done!", ephemeral=True)

    @staticmethod
    def _eligible_entries(pool: GamePool):
        mode = GameMode(pool.mode)
        if mode == GameMode.NEW_PLAYERS_ONLY:
            return GamePoolEntry.filter(status=EntryStatus.ELIGIBLE.value)
        elif mode == GameMode.ANYONE:
            return GamePoolEntry.filter(status__ne=EntryStatus.SELECTED.value)

    @staticmethod
    async def _send_dm(ctx: discord.ApplicationContext, message: str, user: discord.Member) -> None:
        try:
            await user.send(message)
            log.debug(f"Sent a DM to {user}: {message}")
        except discord.Forbidden:
            await ctx.respond(f"Failed to DM {user.mention}. Their DM is probably not open. Use the resend command "
                              f"to try again, or issue another pick command to pick more members.", ephemeral=True)
            log.warning(f"Failed to DM {user}. DM not open?")
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to DM {user}. You may want to resend the message. {e}", ephemeral=True)
            log.exception(e)
