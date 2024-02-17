import asyncio
import logging
import string
from collections import defaultdict
from datetime import timedelta

import hikari
import lightbulb
from aiohttp import ClientSession

from snoozybot.config import values
from snoozybot.config.provider import get_secret_configs
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('youtube')
_LAST_KNOWN_VIDEO: dict[str, str] = {}
logger = logging.getLogger(__name__)


class Youtube:
    def __init__(self) -> None:
        self.__api_key: str | None = None
        self._client = ClientSession()

    def set_api_key(self, key: str) -> None:
        self.__api_key = key

    async def get_latest_video(self, playlist_id: str) -> tuple[str, str, str] | None:
        async with self._client.get('https://youtube.googleapis.com/youtube/v3/playlistItems', params={
            'part': 'snippet',
            'playlistId': playlist_id,
            'maxResults': 1,
            'key': self.__api_key,
        }) as resp:
            resp.raise_for_status()
            data = await resp.json()
            items = data['items']
            if not items:
                return None
            return (
                items[0]['snippet']['channelTitle'],
                items[0]['snippet']['resourceId']['videoId'],
                items[0]['snippet']['publishedAt'],
            )

    async def close(self):
        await self._client.close()

    @property
    def is_ready(self):
        return self.__api_key is not None


youtube = Youtube()


@plugin.listener(hikari.StartedEvent)
async def on_started(event: hikari.StartedEvent):
    api_key_config = await get_secret_configs('secret.youtube.api_key')
    api_key = next(iter(api_key_config.values())).get_secret_value()
    youtube.set_api_key(api_key)
    logger.info('Started youtube client.')
    await youtube_notif(event.app)


@plugin.listener(hikari.StoppedEvent)
async def on_stopped(event: hikari.StoppedEvent):
    await youtube.close()


async def _check_and_notify_youtube(playlist_id: str, guilds: set[int], app: lightbulb.BotApp):
    video = await youtube.get_latest_video(playlist_id)
    if not video:
        return
    video_channel, video_id, timestamp = video
    if playlist_id not in _LAST_KNOWN_VIDEO:
        # New video
        _LAST_KNOWN_VIDEO[playlist_id] = timestamp
        logger.info('Found initial video %s for playlist %s', video_id, playlist_id)
    elif _LAST_KNOWN_VIDEO[playlist_id] < timestamp:
        # New video to notify
        logger.info('Found new youtube video %s in playlist %s, sending notifications...', video_id, playlist_id)
        _LAST_KNOWN_VIDEO[playlist_id] = timestamp
        for guild in guilds:
            channel_id = await values.youtube_notif_channel_id.get_value(guild)
            channel = app.cache.get_guild_channel(channel_id)
            if isinstance(channel, hikari.TextableChannel):
                content_template = await values.youtube_notif_title_template.get_value(guild) or ''
                video_url = 'https://youtu.be/' + video_id
                content = string.Template(content_template).safe_substitute({
                    'channel': video_channel, 'url': video_url,
                })
                await channel.send(content=content, user_mentions=True, role_mentions=True, mentions_everyone=True)
                logger.info('Sent youtube notification to guild %s channel %s', guild, channel_id)
            else:
                logger.error('Did not send a youtube notification for guild %s channel %s: invalid channel ID',
                             guild, channel)


@plugin.periodic_task(timedelta(minutes=10))
async def youtube_notif(app: lightbulb.BotApp):
    # Get the channels to check for each guild
    if youtube.is_ready:
        playlist_guilds = defaultdict(set)
        for guild in app.default_enabled_guilds:
            if await values.youtube_notif_enabled.get_value(guild):
                playlists = await values.youtube_notif_playlist_ids.get_value(guild) or []
                for playlist in playlists:
                    playlist_guilds[playlist].add(guild)

        try:
            # Check which accounts had a new post
            await asyncio.gather(*(
                _check_and_notify_youtube(playlist, guilds, app=app) for playlist, guilds in playlist_guilds.items()
            ))
        except Exception:
            logger.exception('Failed to process youtube notifications.')


load, unload = plugin.export_extension()
