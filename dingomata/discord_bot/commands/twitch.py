import logging
import string
from collections import defaultdict
from datetime import timedelta

import hikari
import lightbulb
import twitchio

from dingomata.config import values
from dingomata.config.provider import get_secret_configs
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('twitch')
twitch: twitchio.Client = None  # type: ignore
_LAST_KNOWN_STREAM_ID: dict[str, int] = {}
logger = logging.getLogger(__name__)


@plugin.listener(hikari.StartedEvent)
async def on_started(event: hikari.StartedEvent):
    global twitch
    _twitch_client_id_secret = await get_secret_configs('secret.twitch.client_id_secret')
    _twitch_client_id, _twitch_client_secret = next(iter(_twitch_client_id_secret.values())).get_secret_value().split()
    twitch = twitchio.Client.from_client_credentials(_twitch_client_id, _twitch_client_secret)
    logger.info('Started twitchIO client.')


async def _check_twitch_stream_live(logins: list[str]) -> list[twitchio.Stream]:
    # Returns list of streams went from offline to online.
    # Does not return streamers whose status went from unknown to online.
    if not logins:
        return []
    streams = await twitch.fetch_streams(user_logins=logins, type='live')
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


async def _generate_stream_embed(stream: twitchio.Stream, guild_id: int, user: twitchio.User) -> hikari.Embed:
    embed = hikari.Embed(
        title=stream.title,
        description=stream.game_name,
        url='https://www.twitch.tv/' + stream.user.name,
    )
    embed.set_author(name=stream.user.name)
    embed.set_image(await values.twitch_online_notif_image_url.get_value(guild_id)
                    or stream.thumbnail_url.format(width=640, height=400))
    embed.timestamp = stream.started_at
    if stream.tags:
        embed.set_footer(text=', '.join(stream.tags))
    embed.set_thumbnail(user.profile_image)
    return embed


@plugin.periodic_task(timedelta(minutes=5))
async def twitch_online_notif(app: lightbulb.BotApp):
    # Get the channels to check for each guild
    login_guilds = defaultdict(set)
    for guild in app.default_enabled_guilds:
        if await values.twitch_online_notif_enabled.get_value(guild):
            logins = await values.twitch_online_notif_logins.get_value(guild)
            for login in logins or []:
                login_guilds[login.lower()].add(guild)

    # Check which streams went from offline to online on twitch
    started_streams = await _check_twitch_stream_live(list(login_guilds.keys()))
    if not started_streams:
        return
    # Generate embeds and send
    logger.info('Found newly started twitch streams: %s, sending notifications...', started_streams)
    users: list[twitchio.User] = await twitch.fetch_users(ids=[stream.user.id for stream in started_streams])
    for stream in started_streams:
        user = next(u for u in users if u.id == stream.user.id)
        for guild in login_guilds[stream.user.name.lower()]:
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


load, unload = plugin.export_extension()
