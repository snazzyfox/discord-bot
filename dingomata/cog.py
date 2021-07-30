import logging
from typing import Optional, List, Set

from discord import Embed, Color, Message, Member, Reaction, Guild, TextChannel, NotFound, Forbidden, HTTPException
from discord.ext.commands import Cog, Context, group, Command, Bot

from dingomata.config import get_config_value, ConfigurationKey
from dingomata.pool import MemberPool, MemberRoleError

log = logging.getLogger(__name__)
GUILD_ID = int(get_config_value(ConfigurationKey.SECURITY_SERVER_ID))
PLAYER_CHANNEL_ID = int(get_config_value(ConfigurationKey.MESSAGE_PLAYER_CHANNEL))
EXCLUDE_SELECTED = (get_config_value(ConfigurationKey.SECURITY_EXCLUDE_SELECTED).lower() or 'false') == 'true'
_CHECKMARK = '✅'


class DingomataCommands(Cog, name='Dingomata'):
    """Main commands for the dingomata."""

    def __init__(self, bot: Bot):
        """Initialize application state."""
        self._bot = bot
        self._guild: Guild = None
        self._channel: TextChannel = None
        self._pool = MemberPool()
        self._title = ''
        self._current_message: Optional[Message] = None
        self._picked_users: List[Member] = []
        self._previously_selected_users: Set[Member] = set()

    @Cog.listener()
    async def on_ready(self) -> None:
        try:
            self._guild = next(guild for guild in self._bot.guilds if guild.id == GUILD_ID)
            self._channel = await self._bot.fetch_channel(PLAYER_CHANNEL_ID)
        except StopIteration:
            log.error(
                f'Failed to start. Bot is configured to run for server ID "{GUILD_ID}" but the bot has not joined '
                f'a server with this ID.')
        except NotFound:
            log.error(f'Failed to start. Bot is configured to send messages to channel "{PLAYER_CHANNEL_ID}", but this '
                      f'channel ID either does not exist or is not visible to the bot.')

    @Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, member: Member) -> None:
        if reaction.message == self._current_message and member != self._bot.user and reaction.emoji == _CHECKMARK:
            if self._pool.is_open:
                if member in self._previously_selected_users:
                    await member.send('You cannot join this pool because you were recently selected.')
                    return
                try:
                    await member.send(get_config_value(ConfigurationKey.MESSAGE_JOINED).format(title=self._title))
                except Forbidden:
                    # 403 means they don't have DM open. Can't add them into the pool because they wont receive the code
                    log.warning(f"Member not added to pool because their DM is not open: {member}")
                    return
                try:
                    self._pool.add_member(member)
                    log.info(f"Member added to pool: {member}")
                except MemberRoleError as e:
                    await member.send(str(e))
                    log.warning(f"Member {member} attempted to join but was rejected because they're missing roles.")
            else:
                await member.send(f'The pool is currently closed. You have not been added.')
                log.info(f"Member not added to pool because it is closed: {member}")

    @Cog.listener()
    async def on_reaction_remove(self, reaction: Reaction, member: Member) -> None:
        if reaction.message == self._current_message and member != self._bot.user and reaction.emoji == _CHECKMARK:
            if self._pool.is_open:
                try:
                    self._pool.remove_member(member)
                    await member.send(get_config_value(ConfigurationKey.MESSAGE_LEFT).format(title=self._title))
                except Forbidden:
                    # We don't care for removals
                    pass
                log.info(f"Member removed from pool: {member}")
            else:
                await member.send(f'The pool is currently closed. You have not been added.')
                log.info(f"Member not added to pool because it is closed: {member}")

    @Command
    async def open(self, ctx: Context, title: str = '') -> None:
        """Opens the pool for entry."""
        self._pool.open()
        self._title = title
        embed = Embed(title=get_config_value(ConfigurationKey.MESSAGE_OPENED).format(title=title),
                      description=get_config_value(ConfigurationKey.MESSAGE_OPENED_SUB).format(title=title),
                      color=Color.gold(),
                      )
        self._current_message = await self._channel.send(embed=embed)
        await self._current_message.add_reaction(_CHECKMARK)
        await ctx.message.add_reaction(_CHECKMARK)

    @Command
    async def close(self, ctx: Context) -> None:
        """Closes the open pool.

        Members can no longer enter the pool once it's closed.
        """
        self._pool.close()
        embed = Embed(description=get_config_value(ConfigurationKey.MESSAGE_CLOSED).format(title=self._title),
                      color=Color.dark_red())
        await self._current_message.edit(embed=embed)
        await ctx.message.reply(f'Submission closed. Received {self._pool.size} entries.')
        await ctx.message.add_reaction(_CHECKMARK)

    @Command
    async def pick(self, ctx: Context, count: int, *, message: str) -> None:
        """Randomly pick users from the pool and send them a DM.

        If the bot is configured to exclude selected users from future pools, they will be added to the exclusion
        list after they're picked.
        """
        self._picked_users = self._pool.pick(count)
        if EXCLUDE_SELECTED:
            self._previously_selected_users.update(self._picked_users)
        embed = Embed(title=get_config_value(ConfigurationKey.MESSAGE_PICKED_ANNOUNCE).format(title=self._title),
                      description=f'Total entries: {self._pool.size}\n'
                                  + '\n'.join(user.display_name for user in self._picked_users),
                      color=Color.blue())
        await self._channel.send(embed=embed)
        await self.resend(ctx, message=message)

    @Command
    async def resend(self, ctx: Context, *, message: str) -> None:
        """Send a message to everyone who was last picked.

        This is useful if you need to resend a message due to a network issue, or if you need to provide additional
        info to the same set of members.
        """
        for user in self._picked_users:
            try:
                await user.send(message)
            except Forbidden:
                await ctx.message.reply(f'Failed to DM {user}. Their DM is probably not open. Use the resend command '
                                        f'to try sending again, or issue another pick command to pick more members.')
            except HTTPException as e:
                await ctx.message.reply(f'Failed to DM {user}. You may want to resend the message. {e}')
        await ctx.message.add_reaction(_CHECKMARK)

    @Command
    async def list(self, ctx: Context) -> None:
        """Show a list of all users currently in the pool.

        This list can be long.
        """
        await ctx.reply('\n'.join(member.display_name for member in self._pool.members))

    @group(invoke_without_command=True)
    async def clear(self, ctx: Context) -> None:
        """Clear state about the pool."""
        await ctx.send_help('clear')

    @clear.command('pool')
    async def clear_pool(self, ctx: Context) -> None:
        """Removes all users from the pool.

        This resets the pool so that everyone can enter again. If you don't clear the pool before opening it again,
        all existing users (who have not been selected) will remain in the pool.
        """
        self._pool.clear()
        await ctx.message.add_reaction(_CHECKMARK)

    @clear.command('selected')
    async def clear_selected(self, ctx: Context) -> None:
        """Clears the list of users who previously played.

        This makes everyone elibible to be added to the pool again.
        """
        self._previously_selected_users = set()
        await ctx.message.add_reaction(_CHECKMARK)
