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
_KNOWN_PLAYLIST_VIDEOS: dict[str, set[str]] = {}
logger = logging.getLogger(__name__)


class Youtube:
    def __init__(self) -> None:
        self.__api_key: str | None = None
        self._client = ClientSession()

    def set_api_key(self, key: str) -> None:
        self.__api_key = key

    async def _get_youtube_api(self, resource: str, params: dict) -> dict:
        async with self._client.get('https://youtube.googleapis.com/youtube/v3/' + resource, params=params, headers={
            'X-Goog-Api-Key': self.__api_key,
        }) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_all_playlist_videos(self, playlist_id: str) -> list[str]:
        ids: list[str] = []
        page_token: str | None = ''
        while page_token is not None:
            data = await self._get_youtube_api('playlistItems', {
                'part': 'id', 'playlistId': playlist_id, 'maxResults': 50})
            ids.extend(item['id'] for item in data['items'])
            page_token = data.get('nextPageToken')
        return ids

    async def get_playlist_video_details(self, playlist_item_ids: list[str]) -> list[tuple[str, str]]:
        data = await self._get_youtube_api('playlistItems', {
            'part': 'snippet', 'id': ','.join(playlist_item_ids), 'maxResults': 50})
        return [(item['snippet']['channelTitle'], item['snippet']['resourceId']['videoId']) for item in data['items']]

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
    logger.info('Checking new youtube videos for guild %s, playlist %s', guilds, playlist_id)
    all_videos: set[str] = set(await youtube.get_all_playlist_videos(playlist_id))
    if playlist_id not in _KNOWN_PLAYLIST_VIDEOS:
        # First load of playlist; keep for later reference
        _KNOWN_PLAYLIST_VIDEOS[playlist_id] = all_videos
        logger.info('Initial load: %d videos in playlist %s', len(all_videos), playlist_id)
    elif new_videos := all_videos - _KNOWN_PLAYLIST_VIDEOS[playlist_id]:
        # There are new videos to notify
        logger.info('Found new youtube videos %s in playlist %s, sending notifications...', new_videos, playlist_id)
        _KNOWN_PLAYLIST_VIDEOS[playlist_id] = all_videos

        for video_channel, video_id in await youtube.get_playlist_video_details(list(new_videos)):
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
