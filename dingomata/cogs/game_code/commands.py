import logging
from typing import Dict

from discord import Embed, Color, Forbidden, HTTPException, User
from discord.ext.commands import Cog, Bot
from discord_slash import SlashContext, ComponentContext
from discord_slash.cog_ext import cog_component
from discord_slash.model import ButtonStyle
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils.manage_components import create_actionrow, create_button
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .models import GamecodeModel, EntryStatus, GameMode
from .pool import MemberPool, MemberRoleError
from ...config import service_config
from ...decorators import subcommand
from ...exceptions import DingomataUserError

log = logging.getLogger(__name__)


class GameCodeCommands(Cog, name='Game Code Sender'):
    """RNG-based Game Code distributor."""
    _JOIN_BUTTON = 'game_join'
    _LEAVE_BUTTON = 'game_leave'
    _GUILDS = service_config.get_command_guilds('game')
    _BASE_COMMAND = dict(base='game', guild_ids=_GUILDS, base_default_permission=False)

    def __init__(self, bot: Bot, engine: AsyncEngine):
        """Initialize application state."""
        self._bot = bot
        self._pools: Dict[int, MemberPool] = {}
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(GamecodeModel.metadata.create_all)

    @cog_component(components=_JOIN_BUTTON)
    async def join(self, ctx: ComponentContext) -> None:
        guild_id = ctx.guild.id
        pool = self._pool_for_guild(guild_id)
        try:
            await pool.add_member(ctx.author)
            log.info(f"Joined successfully: {ctx.author}")
            await ctx.author.send("You're in the pool! I'll send you your super secret message if you're selected.")
            action_row = create_actionrow(create_button(label='Leave', style=ButtonStyle.secondary,
                                                        custom_id=self._LEAVE_BUTTON))
            await ctx.send(f"You've successfully joined the pool for {await pool.title()}. Good luck!",
                           components=[action_row], hidden=True)
        except Forbidden:
            await ctx.reply(f"Join request failed because I can't DM you. Please update your server privacy "
                            f"settings to allow DMs, so that I can send you your secret message if you're "
                            f"selected.", hidden=True)
        except MemberRoleError as e:
            await ctx.reply(str(e), hidden=True)
            log.warning(f"Rejected join request from {ctx.author}: missing roles.")

    @cog_component(components=_LEAVE_BUTTON)
    async def leave(self, ctx: ComponentContext) -> None:
        guild_id = ctx.guild.id
        pool = self._pool_for_guild(guild_id)
        if await pool.is_open():
            await pool.remove_member(ctx.author)
            await ctx.edit_origin(content=f"You've successfully left the pool for {await pool.title()}.",
                                  components=[])
            log.info(f"Member removed from pool: {ctx.author}")
        else:
            await ctx.reply(f'The pool is currently closed. You have not been added.', hidden=True)
            log.info(f"Rejected leave request from {ctx.author}: pool closed")

    @subcommand(
        name='open',
        description='Open a new game pool for people to join.',
        options=[
            create_option(name='title', description='Name of the game to start', option_type=str, required=True),
            create_option(name='allow', description='Who can join the game', option_type=str, required=False,
                          choices=[create_choice(name='anyone', value='anyone'),
                                   create_choice(name='new players only', value='new')])
        ],
        **_BASE_COMMAND,
        base_permissions=service_config.mod_permissions,
    )
    async def open(self, ctx: SlashContext, *, title: str, allow: str = 'new') -> None:
        pool = self._pool_for_guild(ctx.guild.id)
        await ctx.defer(hidden=True)
        await pool.clear(EntryStatus.SELECTED)  # First clear off old players
        await pool.open(title, GameMode.ANYONE if allow == 'anyone' else GameMode.NEW_PLAYERS_ONLY)
        embed = Embed(title=f'Now accepting players for {title}!',
                      description='Click on Join to get in the pool! Make sure you allow DMs on this server so you can '
                                  "receive the game code if you're selected.",
                      color=Color.gold(),
                      )
        action_row = create_actionrow(
            create_button(label='Join', style=ButtonStyle.primary, custom_id=self._JOIN_BUTTON))
        # noinspection PyArgumentList
        message = await ctx.channel.send(embed=embed, components=[action_row])
        log.debug(f"Sent interaction message {message.id}, saving message ID")
        await pool.set_message(ctx.channel.id, message.id)
        await ctx.reply('Pool is now open.', hidden=True)
        log.info(f'Game pool opened for: {title}')

    @subcommand(name='close', description='Close the open pool.', **_BASE_COMMAND)
    async def close(self, ctx: SlashContext) -> None:
        pool = self._pool_for_guild(ctx.guild.id)
        await pool.close(True)
        embed = Embed(
            title=f'Pool for {await pool.title()} is now closed.',
            description=f'Total Entries: {await pool.size(EntryStatus.ELIGIBLE)}',
            color=Color.dark_red())
        channel_id, message_id = await pool.get_message()
        message = self._bot.get_channel(channel_id).get_partial_message(message_id)
        # noinspection PyArgumentList
        await message.edit(embed=embed, components=[])
        await ctx.reply('Pool has been closed.', hidden=True)
        log.info(f'Pool closed')

    @subcommand(
        name='pick',
        description='Pick users randomly from the pool and send them a DM.',
        options=[
            create_option(name='count', description='Number of users to pick', option_type=int, required=True),
            create_option(name='message', description='Message to DM to selected users', option_type=str, required=True)
        ],
        **_BASE_COMMAND,
    )
    async def pick(self, ctx: SlashContext, count: int, *, message: str) -> None:
        """Randomly pick users from the pool and send them a DM.

        If the pool is open, it will be closed automatically.

        If the bot is configured to exclude selected users from future pools, they will be added to the exclusion
        list after they're picked.
        """
        if count < 1:
            raise DingomataUserError(f'You have to pick at least one user.')

        await ctx.defer(hidden=True)
        pool = self._pool_for_guild(ctx.guild.id)
        await pool.close()
        size = await pool.size(EntryStatus.ELIGIBLE)
        picked_users = [ctx.guild.get_member(user) for user in await pool.pick(count)]
        log.info(f'Picked users: {", ".join(str(user) for user in picked_users)}')
        embed = Embed(title=f"Congratulations! Check for your game code in DM's!",
                      description=f'Total entries: {size}\n',
                      color=Color.blue())
        embed.add_field(name='Selected Users', value='\n'.join(user.display_name for user in picked_users))
        await ctx.channel.send(embed=embed)  # Don't reply to the command - that exposes the secret message!
        for user in picked_users:
            await self._send_dm(ctx, message, user)
        await ctx.reply('All done!', hidden=True)

    @subcommand(
        name='resend',
        description='Send a DM to all existing picked users.',
        options=[
            create_option(name='message', description='Message to DM to selected users', option_type=str, required=True)
        ],
        **_BASE_COMMAND,
    )
    async def resend(self, ctx: SlashContext, *, message: str) -> None:
        await ctx.defer(hidden=True)
        pool = self._pool_for_guild(ctx.guild.id)
        users = [ctx.guild.get_member(user) for user in await pool.members(EntryStatus.SELECTED)]
        for user in users:
            await self._send_dm(ctx, message, user)
        await ctx.reply(f'All done!', hidden=True)

    async def _send_dm(self, ctx: SlashContext, message: str, user: User) -> None:
        try:
            await user.send(message)
            log.info(f'Sent a DM to {user}.')
        except Forbidden:
            await ctx.reply(f'Failed to DM {user.mention}. Their DM is probably not open. Use the resend command '
                            f'to try again, or issue another pick command to pick more members.', hidden=True)
            log.warning(f'Failed to DM {user}. DM not open?')
        except HTTPException as e:
            await ctx.reply(f'Failed to DM {user}. You may want to resend the message. {e}', hidden=True)
            log.exception(e)

    @subcommand(
        name='reset',
        description='Reset the list of people who were selected before so they can play again.',
        **_BASE_COMMAND,
    )
    async def reset(self, ctx: SlashContext) -> None:
        pool = self._pool_for_guild(ctx.guild.id)
        await pool.clear(EntryStatus.PLAYED)
        await ctx.reply('All done!', hidden=True)

    def _pool_for_guild(self, guild_id: int) -> MemberPool:
        if guild_id not in self._pools:
            self._pools[guild_id] = MemberPool(
                guild_id, self._session, track_played=service_config.servers[guild_id].game_code.exclude_played,
            )
        return self._pools[guild_id]
