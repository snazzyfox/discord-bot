import asyncio
import logging
import string
from collections import defaultdict
from datetime import timedelta

import hikari
import lightbulb
from atproto import AsyncClient

from snoozybot.config import values
from snoozybot.config.provider import get_secret_configs
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('bluesky')
client = AsyncClient()
_LAST_KNOWN_POST_TIME: dict[str, str] = {}
logger = logging.getLogger(__name__)


@plugin.listener(hikari.StartedEvent)
async def on_started(event: hikari.StartedEvent):
    _bsky_secret = await get_secret_configs('secret.bsky.credentials')
    _bsky_username, _bsky_password = next(iter(_bsky_secret.values())).get_secret_value().split()
    await client.login(_bsky_username, _bsky_password)
    logger.info('Started bluesky client.')
    await bsky_post_notif(event.app)  # it runs before login finishes


async def _check_and_notify_bsky_posts(user: str, guilds: set[int], app: lightbulb.BotApp):
    resp = await client.get_author_feed(user, filter="posts_no_replies", limit=1)
    post = resp.feed[0]
    # This is the latest non-reply post
    post_time = post.post.record.created_at
    if user not in _LAST_KNOWN_POST_TIME:
        # Dont know what the previous post was. Store the current but dont notify.
        _LAST_KNOWN_POST_TIME[user] = post_time
        logger.info('Found initial bsky post from %s', user)
    elif _LAST_KNOWN_POST_TIME[user] < post_time:
        _, post_id = post.post.uri.rsplit('/', 1)
        # This is a new post
        logger.info('Found new bsky post: %s, sending notifications...', post_id)
        _LAST_KNOWN_POST_TIME[user] = post_time
        for guild in guilds:
            channel_id = await values.bsky_post_notif_channel_id.get_value(guild)
            channel = app.cache.get_guild_channel(channel_id)
            if isinstance(channel, hikari.TextableChannel):
                content_template = await values.bsky_post_notif_title_template.get_value(guild) or ''
                post_url = f'https://bsky.app/profile/{post.post.author.handle}/post/{post_id}'
                content = string.Template(content_template).safe_substitute({
                    'handle': post.post.author.handle, 'display': post.post.author.display_name, 'url': post_url,
                })
                await channel.send(content=content, user_mentions=True, role_mentions=True, mentions_everyone=True)
                logger.info('Sent bsky notification to guild %s channel %s', guild, channel_id)
            else:
                logger.error('Did not send a bsky notification for guild %s channel %s: invalid channel ID',
                             guild, channel)


@plugin.periodic_task(timedelta(minutes=10))
async def bsky_post_notif(app: lightbulb.BotApp):
    # Get the channels to check for each guild
    if client.me:
        user_guilds = defaultdict(set)
        for guild in app.default_enabled_guilds:
            if await values.bsky_post_notif_enabled.get_value(guild):
                users = await values.bsky_post_notif_users.get_value(guild) or []
                for user in users:
                    user_guilds[user].add(guild)

        try:
            # Check which accounts had a new post
            await asyncio.gather(*(
                _check_and_notify_bsky_posts(did, guilds, app=app) for did, guilds in user_guilds.items()
            ))
        except Exception:
            # Consume the exception so that the periodic task continues.
            logger.exception('Failed to process bluesky notifications.')


load, unload = plugin.export_extension()
