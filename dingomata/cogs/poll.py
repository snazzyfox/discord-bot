import logging
from typing import Dict, List, Tuple

import discord
import orjson
import tortoise.functions as func
import tortoise.transactions
from discord.ext.tasks import loop

from ..decorators import slash_group
from ..exceptions import DingomataUserError
from ..models import Poll, PollEntry
from ..utils import View
from .base import BaseCog

_log = logging.getLogger(__name__)


class PollUserError(DingomataUserError):
    pass


class PollVoteButton(discord.ui.Button["PollVoteView"]):
    def __init__(self, index: int):
        self.index = index
        action_row = min((index // 5), 4)
        super(PollVoteButton, self).__init__(label=f"Vote {index + 1}",
                                             style=discord.ButtonStyle.blurple,
                                             row=action_row)

    async def callback(self, interaction: discord.Interaction):
        await PollEntry.update_or_create({"option": self.index}, guild_id=interaction.guild.id,
                                         channel_id=interaction.channel.id, user_id=interaction.user.id)
        await interaction.response.send_message(f"You've voted for option {self.index + 1}.", ephemeral=True)


class PollVoteView(View):
    def __init__(self, option_count: int):
        super(PollVoteView, self).__init__(timeout=None)
        for i in range(option_count):
            self.add_item(PollVoteButton(i))


class PollCog(BaseCog):
    """Run polls in Discord. Each channel can only have one active poll at a time."""

    poll = slash_group("poll", "Run polls in a channel.")

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)
        self._views: Dict[Tuple[int, int], PollVoteView] = {}

    @discord.Cog.listener()
    async def on_ready(self):
        self.poll_message_updater.start()
        self.poll_message_pin.start()

    def cog_unload(self):
        self.poll_message_updater.stop()
        self.poll_message_pin.stop()

    @poll.command()
    @discord.option('title', description="Title of poll")
    async def start(
            self, ctx: discord.ApplicationContext, title: str,
            option1: str, option2: str, option3: str = None, option4: str = None, option5: str = None,
            option6: str = None, option7: str = None, option8: str = None, option9: str = None, option10: str = None,
    ) -> None:
        """Start a new poll."""
        options = [o for o in (option1, option2, option3, option4, option5,
                               option6, option7, option8, option9, option10) if o]
        async with tortoise.transactions.in_transaction() as tx:
            if await Poll.filter(guild_id=ctx.guild.id, channel_id=ctx.channel.id).exists():
                raise PollUserError(
                    "There's an open poll in this channel. Close it first before creating another one."
                )
            poll = await Poll.create(guild_id=ctx.guild.id, channel_id=ctx.channel.id, title=title,
                                     options=orjson.dumps(options).decode(), is_open=True)
            _log.debug(f"New poll: server {poll.guild_id} channel {poll.channel_id}.")
            embed = await self._generate_embed(poll, options, True)
            await ctx.respond("A new poll has started!")
            view = PollVoteView(len(options))
            self._views[(ctx.guild.id, ctx.channel.id)] = view
            message = await ctx.channel.send(embed=embed, view=view)
            poll.message_id = message.id
            await poll.save(using_db=tx)

    @poll.command()
    async def end(self, ctx: discord.ApplicationContext):
        """End the poll in this channel."""
        async with tortoise.transactions.in_transaction() as tx:
            try:
                poll = await Poll.select_for_update().using_db(tx).get(guild_id=ctx.guild.id, channel_id=ctx.channel.id)
            except tortoise.exceptions.DoesNotExist as e:
                raise PollUserError("There is no poll running in this channel.") from e
            options = orjson.loads(poll.options)
            channel = self._bot_for(ctx.guild.id).get_channel(poll.channel_id)
            message = channel.get_partial_message(poll.message_id)
            embed = await self._generate_embed(poll, options, False)

            # Delete the poll data
            await poll.delete(using_db=tx)
            await PollEntry.filter(guild_id=ctx.guild.id, channel_id=ctx.channel.id).delete()

            # Post the poll results
            view = self._views.pop((ctx.guild.id, ctx.channel.id), None)
            try:
                await message.delete()
            except discord.NotFound:
                pass  # it's already gone by some other means
            if view:
                view.stop()
            await ctx.respond(embed=embed)

    @loop(seconds=2)
    async def poll_message_updater(self):
        try:
            polls = await Poll.filter(
                guild_id__in=[guild.id for guild in self._bot.guilds],
                message_id__not_isnull=True,
            )
            for poll in polls:
                channel = self._bot_for(poll.guild_id).get_channel(poll.channel_id)
                message = channel.get_partial_message(poll.message_id)
                options = orjson.loads(poll.options)
                embed = await self._generate_embed(poll, options, True)
                view = self._views.get((poll.guild_id, poll.channel_id))
                if not view:
                    view = PollVoteView(len(options))
                    self._views[(poll.guild_id, poll.channel_id)] = view
                try:
                    await message.edit(embed=embed, view=view)
                except discord.NotFound:
                    pass  # the message was deleted
        except Exception as e:
            _log.exception(e)

    @loop(seconds=15)
    async def poll_message_pin(self):
        try:
            async with tortoise.transactions.in_transaction() as tx:
                polls = await Poll.select_for_update().filter(
                    guild_id__in=[guild.id for guild in self._bot.guilds],
                    message_id__not_isnull=True,
                ).using_db(tx).all()
                for poll in polls:
                    channel = self._bot_for(poll.guild_id).get_channel(poll.channel_id)
                    if channel.last_message_id != poll.message_id:
                        options = orjson.loads(poll.options)
                        embed = await self._generate_embed(poll, options, True)
                        view = self._views.get((poll.guild_id, poll.channel_id))
                        message = channel.get_partial_message(poll.message_id)
                        await message.delete()
                        new_message = await channel.send(embed=embed, view=view)
                        poll.message_id = new_message.id
                        await poll.save(using_db=tx)
        except Exception as e:
            _log.exception(e)

    @staticmethod
    async def _generate_embed(poll: Poll, options: List[str], is_open: bool) -> discord.Embed:
        counts = dict(await PollEntry.filter(guild_id=poll.guild_id, channel_id=poll.channel_id)
                      .annotate(count=func.Count("user_id")).group_by("option").values_list("option", "count"))
        total_votes = sum(counts.values())
        max_count = max(counts.values(), default=0)
        embed = discord.Embed(title=poll.title, description="Vote for your choice below.",
                              color=discord.Color.green() if is_open else discord.Color.dark_red())
        for i, option in enumerate(options):
            votes = counts.get(i, 0)
            pct = votes / total_votes if votes else 0
            name = f"[{i + 1}] {option}"
            if not is_open and votes > 0 and votes == max_count:
                name = "🏆 " + name
            embed.add_field(name=name, value=f"**{votes} votes** ({pct:.0%})", inline=True)
        return embed
