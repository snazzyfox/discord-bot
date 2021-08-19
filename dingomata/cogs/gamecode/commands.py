import logging
from typing import List, Set, Dict

from discord import Embed, Color, Member, Forbidden, HTTPException, User
from discord.ext.commands import Cog, Bot
from discord_slash import SlashContext, ComponentContext
from discord_slash.cog_ext import cog_subcommand, cog_component
from discord_slash.model import SlashCommandPermissionType, ButtonStyle
from discord_slash.utils.manage_commands import create_option, create_permission
from discord_slash.utils.manage_components import create_actionrow, create_button
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .models import GamecodeModel, EntryStatus
from .pool import MemberPool, MemberRoleError
from ...config import get_guild_config, get_guilds, get_mod_permissions
from ...exceptions import DingomataUserError

log = logging.getLogger(__name__)


_BASE_COMMAND = dict(base='game', guild_ids=get_guilds(), base_default_permission=False)


class GameCodeSenderCommands(Cog, name='Game Code Sender'):
    """RNG-based Game Code distributor."""
    _JOIN_BUTTON = 'game_join'
    _LEAVE_BUTTON = 'game_leave'

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
        if await pool.is_open():
            try:
                await pool.add_member(ctx.author)
                log.info(f"Joined successfully: {ctx.author}")
                await ctx.author.send("You're in the pool! I'll send you your super secret message if you're selected.")
                action_row = create_actionrow(create_button(label='Leave', style=ButtonStyle.secondary,
                                                            custom_id=self._LEAVE_BUTTON))
                await ctx.send(get_guild_config(guild_id).game_code.message_joined.format(title=await pool.title()),
                               components=[action_row], hidden=True)
            except Forbidden:
                await ctx.reply(f"Join request failed because I can't DM you. Please update your server privacy "
                                f"settings to allow DMs, so that I can send you your secret message if you're "
                                f"selected.", hidden=True)
            except MemberRoleError as e:
                await ctx.reply(str(e), hidden=True)
                log.warning(f"Rejected join request from {ctx.author}: missing roles.")
        else:
            await ctx.reply(f"You can't join the pool, it's not open right now.", hidden=True)
            log.info(f"Rejected join request from {ctx.author}: pool closed")

    @cog_component(components=_LEAVE_BUTTON)
    async def leave(self, ctx: ComponentContext) -> None:
        guild_id = ctx.guild.id
        pool = self._pool_for_guild(guild_id)
        if await pool.is_open():
            await pool.remove_member(ctx.author)
            await ctx.edit_origin(
                content=get_guild_config(ctx.guild.id).game_code.message_left.format(title=await pool.title()),
                components=[],
            )
            log.info(f"Member removed from pool: {ctx.author}")
        else:
            await ctx.reply(f'The pool is currently closed. You have not been added.', hidden=True)
            log.info(f"Rejected unjoin request from {ctx.author}: pool closed")

    @cog_subcommand(
        name='open',
        description='Open a new game pool for people to join.',
        options=[
            create_option(name='title', description='Name of the game to start', option_type=str, required=True),
        ],
        **_BASE_COMMAND,
        base_permissions=get_mod_permissions(),  # This can only be used once to work around dedupe issues in the lib
    )
    async def open(self, ctx: SlashContext, *, title: str = '') -> None:
        await self._pool_for_guild(ctx.guild.id).open(title)
        embed = Embed(title=get_guild_config(ctx.guild.id).game_code.message_opened.format(title=title),
                      description=get_guild_config(ctx.guild.id).game_code.message_opened_subtitle.format(title=title),
                      color=Color.gold(),
                      )
        action_row = create_actionrow(create_button(label='Join', style=ButtonStyle.primary,
                                                    custom_id=self._JOIN_BUTTON))
        await ctx.send(embed=embed, components=[action_row])
        log.info(f'Pool opened with title: {title}')

    @cog_subcommand(name='close', description='Close the open pool.', **_BASE_COMMAND)
    async def close(self, ctx: SlashContext) -> None:
        pool = self._pool_for_guild(ctx.guild.id)
        await pool.close()
        embed = Embed(
            title=get_guild_config(ctx.guild.id).game_code.message_closed.format(title=await pool.title()),
            description=f'Total Entries: {await pool.size(EntryStatus.ELIGIBLE)}',
            color=Color.dark_red())
        await ctx.send(embed=embed)
        log.info(f'Pool closed')

    @cog_subcommand(
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

        pool = self._pool_for_guild(ctx.guild.id)
        size = await pool.size(EntryStatus.ELIGIBLE)
        picked_users = [ctx.guild.get_member(user) for user in await pool.pick(count)]
        log.info(f'Picked users: {", ".join(str(user) for user in picked_users)}')
        embed = Embed(title=get_guild_config(ctx.guild.id).game_code.message_picked_announce.format(
            title=await pool.title()),
            description=f'Total entries: {size}\n' + '\n'.join(user.display_name for user in picked_users),
            color=Color.blue())
        await ctx.send(embed=embed)
        for user in picked_users:
            await self._send_dm(ctx, message, user)
        await ctx.reply('All done!', hidden=True)

    @cog_subcommand(
        name='resend',
        description='Send a DM to all users picked in the previous pool.',
        options=[
            create_option(name='message', description='Message to DM to selected users', option_type=str, required=True)
        ],
        **_BASE_COMMAND,
    )
    async def resend(self, ctx: SlashContext, *, message: str) -> None:
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

    @cog_subcommand(
        name='clear',
        description='Clear the current pool.',
        **_BASE_COMMAND,
    )
    async def clear(self, ctx: SlashContext) -> None:
        await self._pool_for_guild(ctx.guild.id).clear(EntryStatus.SELECTED)
        await ctx.reply('All done!', hidden=True)

    @cog_subcommand(
        name='clear_played',
        description='Clear the list of people who were selected before so they become eligible again.',
        **_BASE_COMMAND,
    )
    async def clear_played(self, ctx: SlashContext) -> None:
        pool = self._pools.get(ctx.guild.id)
        if pool:
            await pool.clear(EntryStatus.PLAYED)
        await ctx.reply('All done!', hidden=True)

    @cog_subcommand(name='ban', description='Ban a user from joining.',
                    options=[
                        create_option(name='user', description='Who to ban', option_type=User, required=True),
                    ],
                    **_BASE_COMMAND)
    async def clear_pool(self, ctx: SlashContext, user: User) -> None:
        await self._pool_for_guild(ctx.guild.id).ban_user(user)
        await ctx.reply('All done!', hidden=True)

    def _pool_for_guild(self, guild_id: int) -> MemberPool:
        if guild_id not in self._pools:
            self._pools[guild_id] = MemberPool(
                guild_id, self._session, track_played=get_guild_config(guild_id).game_code.exclude_selected,
            )
        return self._pools[guild_id]
