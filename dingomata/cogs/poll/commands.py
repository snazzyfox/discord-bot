import json
import logging
from typing import List

from discord import Embed, Color
from discord.ext import tasks
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext, ButtonStyle, ComponentContext
from discord_slash.cog_ext import cog_component
from discord_slash.utils.manage_commands import create_option
from discord_slash.utils.manage_components import create_actionrow, create_button
from sqlalchemy import func, delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import PollModel, Poll, PollEntry
from ...config import service_config
from ...decorators import subcommand
from ...exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class PollUserError(DingomataUserError):
    pass


_VOTE_BUTTON_PREFIX = 'poll.vote'


class PollCog(Cog, name='POLL'):
    """Run polls in Discord. Each channel can only have one active poll at a time."""
    _GUILDS = service_config.get_command_guilds('guild')
    _BASE_MOD_COMMAND = dict(base='poll', guild_ids=_GUILDS, base_default_permission=False)
    _MAX_OPTIONS = 5
    _BUTTONS = [
        create_button(label=f'Vote {i + 1}', style=ButtonStyle.blue, custom_id=f'{_VOTE_BUTTON_PREFIX}{i}')
        for i in range(_MAX_OPTIONS)
    ]

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(PollModel.metadata.create_all)
            self.poll_message_updater.start()

    def cog_unload(self):
        self.poll_message_updater.stop()

    # ### MOD COMMANDS ###
    @subcommand(
        name='start',
        description='Start a new poll.',
        options=[
            create_option(name='title', description='Title for the poll', option_type=str, required=True),
            *(create_option(name=f'option{i + 1}', description=f'Poll Option #{i + 1}', option_type=str,
                            required=i < 1)  # at least 1 option required
              for i in range(_MAX_OPTIONS))
        ],
        base_permissions=service_config.mod_permissions,
        **_BASE_MOD_COMMAND,
    )
    async def start(self, ctx: SlashContext, title: str, **kwargs):
        options = (kwargs.get(f'option{i}') for i in range(self._MAX_OPTIONS))
        options = [o for o in options if o]
        async with self._session() as session:
            async with session.begin():
                stmt = select(Poll).filter(Poll.guild_id == ctx.guild.id, Poll.channel_id == ctx.channel.id)
                existing = (await session.execute(stmt)).scalar()
                _log.debug(f"Existing poll for {ctx.guild.id}: {existing}")
                if existing:
                    raise PollUserError(
                        "There's an open poll in this channel. Close it first before creating another one."
                    )
                poll = Poll(guild_id=ctx.guild.id, channel_id=ctx.channel.id, title=title, options=json.dumps(options),
                            is_open=True)
                _log.debug(f"New poll: server {poll.guild_id} channel {poll.channel_id} ")
                embed = await self._generate_embed(poll, options)
                await ctx.reply('A new poll has started!')
                message = await ctx.channel.send(
                    embed=embed, components=[create_actionrow(*self._BUTTONS[:len(options)])])
                poll.message_id = message.id
                session.add(poll)
                await session.commit()

    @tasks.loop(seconds=5)
    async def poll_message_updater(self):
        try:
            async with self._session() as session:
                async with session.begin():
                    stmt = select(Poll).filter(Poll.message_id.isnot(None), Poll.guild_id.in_(self._GUILDS))
                    polls = (await session.execute(stmt)).scalars()
                    for poll in polls:
                        channel = self._bot.get_channel(poll.channel_id)
                        message = channel.get_partial_message(poll.message_id)
                        options = json.loads(poll.options)
                        embed = await self._generate_embed(poll, options)
                        if poll.is_open:
                            action_row = [create_actionrow(*self._BUTTONS[:len(options)])]
                        else:
                            action_row = None
                            await session.delete(poll)
                            await session.execute(delete(PollEntry).filter(
                                PollEntry.guild_id == poll.guild_id, PollEntry.channel_id == poll.channel_id))
                        if channel.last_message_id == poll.message_id:
                            await message.edit(embed=embed, components=action_row)
                        else:
                            new_message = await channel.send(embed=embed, components=action_row)
                            poll.message_id = new_message.id
                            await message.delete()
                    await session.commit()
        except Exception as e:
            _log.exception(e)

    async def _generate_embed(self, poll: Poll, options: List[str]) -> Embed:
        async with self._session() as session:
            async with session.begin():
                # Get the poll results
                stmt = select(PollEntry.option, func.count('*').label('count')).filter(
                    PollEntry.guild_id == poll.guild_id, PollEntry.channel_id == poll.channel_id
                ).group_by(PollEntry.option)
                counts = dict((await session.execute(stmt)).fetchall())
                total_votes = sum(counts.values())
                max_count = max(counts.values(), default=0)
                embed = Embed(title=poll.title, description='Vote for your choice below.',
                              color=Color.green() if poll.is_open else Color.dark_red())
                for i, option in enumerate(options):
                    votes = counts.get(i, 0)
                    pct = votes / total_votes if votes else 0
                    name = f'[{i + 1}] {option}'
                    if not poll.is_open and votes > 0 and votes == max_count:
                        name = '🏆 ' + name
                    embed.add_field(name=name, value=f'**{votes} votes** ({pct:.0%})', inline=True)
        return embed

    @subcommand(
        name='end',
        description='End the current poll.',
        **_BASE_MOD_COMMAND,
    )
    async def end(self, ctx: SlashContext):
        async with self._session() as session:
            async with session.begin():
                stmt = select(Poll).filter(Poll.guild_id == ctx.guild.id, Poll.channel_id == ctx.channel.id)
                poll = (await session.execute(stmt)).scalar()
                if not poll:
                    raise PollUserError("There is no poll running in this channel.")
                poll.is_open = False
                await session.commit()
                await ctx.reply('Poll ended.', hidden=True)

    @cog_component(components=_BUTTONS)
    async def vote(self, ctx: ComponentContext):
        option = int(ctx.component_id[-1])
        async with self._session() as session:
            async with session.begin():
                entry = PollEntry(guild_id=ctx.guild.id, channel_id=ctx.channel.id, user_id=ctx.author.id,
                                  option=option)
                await session.merge(entry)
                await ctx.reply(f"You've voted for option {option + 1}.", hidden=True)
