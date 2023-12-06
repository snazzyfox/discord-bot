import asyncio
import logging
from collections import defaultdict

import hikari
import lightbulb

from snoozybot.exceptions import UserError
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('count_votes')
logger = logging.getLogger(__name__)


@plugin.command
@lightbulb.option(name='limit', description="Max number of results to show.",
                  default=None, type=int, required=False, min_value=1)
@lightbulb.option(name='max_votes', description="Votes from anyon who voted more than this many times is disqualified.",
                  default=None, type=int, required=False, min_value=1)
@lightbulb.option(name='emote', description="The emote (on the post, not comments) to accept as votes.",
                  type=hikari.Emoji)
@lightbulb.option(name='channel', description="The channel to count votes for. This must be a forum channel.",
                  type=hikari.GuildChannel)
@lightbulb.command(name='count_votes',
                   description="Count votes in a forum channel. Each post should be a submitted idea.",
                   ephemeral=True,
                   auto_defer=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def vote_count(ctx: lightbulb.SlashContext) -> None:
    guild = ctx.get_guild()
    channel = guild.get_channel(ctx.options.channel)

    if not isinstance(channel, hikari.GuildForumChannel):
        raise UserError('The channel you selected is not a forum channel. Only forum channels can have votes tallied.')

    # Pull all posts and reactions
    archived_threads: list[hikari.GuildPublicThread]
    all_active_threads, archived_threads = await asyncio.gather(
        ctx.app.rest.fetch_active_threads(guild),
        ctx.app.rest.fetch_public_archived_threads(channel),
    )
    channel_threads = [thread for thread in all_active_threads if thread.parent_id == channel.id
                       ] + archived_threads

    # Fetch list of users who voted on each channel
    thread_voters: dict[hikari.GuildThreadChannel, set[hikari.User]] = defaultdict(set)
    voter_threads: dict[hikari.User, set[hikari.GuildThreadChannel]] = defaultdict(set)
    for thread in channel_threads:
        async for user in ctx.app.rest.fetch_reactions_for_emoji(thread, thread.id, emoji=ctx.options.emote):
            thread_voters[thread].add(user)
            voter_threads[user].add(thread)
    total_disqualified = 0
    if ctx.options.max_votes:
        for user, threads in voter_threads.items():
            if len(threads) > ctx.options.max_votes:
                # Too many votes, disqualified
                logger.info(f'Disqualified {user} because they had {len(threads)} votes.')
                total_disqualified += 1
                for thread in threads:
                    thread_voters[thread].remove(user)

    # Make final count
    counts = sorted(thread_voters.items(), key=lambda t: len(t[1]), reverse=True)
    if ctx.options.limit:
        counts = counts[:ctx.options.limit]
    message = '\n'.join(f'{len(users)}: {thread.name}' for thread, users in counts)
    if not message:
        message = 'No entries qualified based on the rules you set.'
    if total_disqualified:
        message += f'\n({total_disqualified} users were disqualified because they voted too many times)'
    await ctx.respond(message)


load, unload = plugin.export_extension()
