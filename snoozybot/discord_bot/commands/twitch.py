import asyncio
import logging
import string
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import hikari
import lightbulb
import twitchio

from snoozybot.config import values
from snoozybot.config.provider import get_secret_configs
from snoozybot.utils import LightbulbPlugin, get_client_session

plugin = LightbulbPlugin('twitch')
twitch: twitchio.Client = None  # type: ignore
_LAST_KNOWN_STREAM_ID: dict[str, int] = {}
logger = logging.getLogger(__name__)


@plugin.listener(hikari.StartingEvent)
async def on_started(event: hikari.StartingEvent):
    global twitch
    _twitch_client_id_secret = await get_secret_configs('secret.twitch.client_id_secret')
    _twitch_client_id, _twitch_client_secret = next(iter(_twitch_client_id_secret.values())).get_secret_value().split()
    twitch = twitchio.Client.from_client_credentials(_twitch_client_id, _twitch_client_secret)
    logger.info('Started twitchIO client.')


async def _get_guild_notify_logins(guild: int) -> list[str]:
    logins = await values.twitch_online_notif_logins.get_value(guild) or []
    if team_name := await values.twitch_online_notif_team.get_value(guild):
        team = await twitch.fetch_teams(team_name=team_name)
        logins.extend(user.name for user in team.users)
    return logins


async def _check_twitch_stream_live(logins: list[str]) -> list[twitchio.Stream]:
    # Returns list of streams went from offline to online.
    # Does not return streamers whose status went from unknown to online.
    if not logins:
        return []
    batches = await asyncio.gather(*(
        twitch.fetch_streams(user_logins=logins[i:i + 100], type='live')
        for i in range(0, len(logins), 100)
    ))
    streams = [s for b in batches for s in b]
    results = []
    for stream in streams:
        user = stream.user.name.lower()
        if user not in _LAST_KNOWN_STREAM_ID:
            _LAST_KNOWN_STREAM_ID[user] = stream.id
        elif _LAST_KNOWN_STREAM_ID[user] != stream.id:
            _LAST_KNOWN_STREAM_ID[user] = stream.id
            results.append(stream)
    # Add in list of streamers known not to be live
    for user in set(logins) - {stream.user.name.lower() for stream in streams}:
        _LAST_KNOWN_STREAM_ID[user] = -1
    return results


async def _get_stream_preview_image(url: str, stream_started_at: datetime) -> bytes | None:
    """
    Download stream preview image from twitch.
    This image is cached behind cloudfront CDN. This function downloads the image for up to 5 times in 30-second
    intervals until the received image's timestamp ("date" http header) is AFTER the stream's start time.
    """
    for _ in range(20):
        async with get_client_session().get(url, allow_redirects=False) as resp:
            # Disallow redirects; redirects go to the 404 image.
            if 'date' not in resp.headers:
                continue  # bad response?
            image_date = parsedate_to_datetime(resp.headers['date'])
            if image_date > stream_started_at:
                # thumbnail is generated after stream start time. Can be used.
                image_data = await resp.read()
                return image_data
            else:
                # thumbnail is older than stream; it's old. Wait and try again.
                logger.debug('Image at %s has date %s, which is older than stream start time %s. Retrying later.',
                             url, image_date, stream_started_at)
                await asyncio.sleep(30)
    logger.info('Stream thumbnail still stale after all retries, sending without image: %s', url)
    return None


async def _generate_stream_embed(stream: twitchio.Stream, guild_id: int, user: twitchio.User) -> hikari.Embed:
    embed = hikari.Embed(
        title=stream.title,
        description=stream.game_name,
        url='https://www.twitch.tv/' + stream.user.name,
    )
    embed.set_author(name=stream.user.name)
    image_url = (await values.twitch_online_notif_image_url.get_value(guild_id)
                 or stream.thumbnail_url.format(width=720, height=400))
    image_data = await _get_stream_preview_image(image_url, stream.started_at)
    if image_data:
        embed.set_image(hikari.Bytes(image_data, 'stream_preview.jpg', mimetype='image/jpeg'))
    embed.timestamp = stream.started_at
    if stream.tags:
        embed.set_footer(text=', '.join(stream.tags))
    embed.set_thumbnail(user.profile_image)
    return embed


async def _process_stream_notif(stream: twitchio.Stream, user: twitchio.User, guild: int, app: lightbulb.BotApp):
    embed = await _generate_stream_embed(stream, guild, user)
    content_template = string.Template(await values.twitch_online_notif_title_template.get_value(guild) or '')
    content = content_template.safe_substitute({'channel': stream.user.name, 'game': stream.game_name})
    channel_id = await values.twitch_online_notif_channel_id.get_value(guild)
    channel = app.cache.get_guild_channel(channel_id)
    if isinstance(channel, hikari.TextableChannel):
        await channel.send(content=content, embed=embed, user_mentions=True, role_mentions=True,
                           mentions_everyone=True)
        logger.info('Sent stream live notification to guild %s channel %s for twitch channel %s',
                    guild, channel_id, stream.user.id)
    else:
        logger.error('Did not send a stream live notification for guild %s channel %s: invalid channel ID',
                     guild, channel)


@plugin.periodic_task(timedelta(minutes=5))
async def twitch_online_notif(app: lightbulb.BotApp):
    # Get the channels to check for each guild
    login_guilds = defaultdict(set)
    for guild in app.default_enabled_guilds:
        if await values.twitch_online_notif_enabled.get_value(guild):
            logins = await _get_guild_notify_logins(guild)
            for login in logins or []:
                login_guilds[login.lower()].add(guild)

    try:
        # Check which streams went from offline to online on twitch
        started_streams = await _check_twitch_stream_live(list(login_guilds.keys()))
        if not started_streams:
            return
        # Generate embeds and send
        logger.info('Found newly started twitch streams: %s, sending notifications...', started_streams)
        users: list[twitchio.User] = await twitch.fetch_users(ids=[stream.user.id for stream in started_streams])
        await asyncio.gather(*(
            _process_stream_notif(
                stream=stream,
                user=next(u for u in users if u.id == stream.user.id),
                guild=guild,
                app=app,
            ) for stream in started_streams for guild in login_guilds[stream.user.name.lower()]))
    except Exception:
        # Consume the exception so that the periodic task continues.
        logger.exception('Failed to process twitch online notifications.')


load, unload = plugin.export_extension()
