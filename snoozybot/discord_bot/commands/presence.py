import logging
import string

import hikari
from cachetools import TTLCache

from snoozybot.config import values
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('presence')
logger = logging.getLogger(__name__)
_recent_notifs: TTLCache = TTLCache(maxsize=256, ttl=600)


@plugin.listener(hikari.GuildAvailableEvent)
async def on_guild_available(event: hikari.GuildAvailableEvent):
    # We don't know if someone's status need changing after a disconnect to recompute everyone
    for presence in event.presences.values():
        if presence.activities is not None:
            await _process_presence(presence, event.members[presence.user_id])


@plugin.listener(hikari.PresenceUpdateEvent)
async def on_presence_update(event: hikari.PresenceUpdateEvent):
    await _process_presence(event.presence, None)


async def _process_presence(presence: hikari.MemberPresence, member: hikari.Member | None):
    streaming_role = await values.presence_streaming_role.get_value(presence.guild_id)
    if not streaming_role:
        return
    logger.debug(f'Received presence update for user {presence.user_id} in guild {presence.guild_id}: {presence}')
    streams = [activity for activity in presence.activities
               if activity.type == hikari.ActivityType.STREAMING and activity.url]
    member = member or await presence.fetch_member()
    cache_key = (presence.guild_id, member.id)
    if streams and streaming_role not in member.role_ids:
        # add role
        await member.add_role(streaming_role)
        logger.info(f'Set streaming role for user {member} in guild {member.guild_id}.')
        # send message
        channel_id = await values.presence_streaming_notif_channel_id.get_value(presence.guild_id)
        if channel_id and cache_key not in _recent_notifs:
            template = await values.presence_streaming_notif_title_template.get_value(presence.guild_id) or ''
            text = string.Template(template).safe_substitute({'mention': member.mention, 'user': member.display_name})
            text_content, embeds = await _get_presence_message(streams)
            channel: hikari.TextableGuildChannel = member.get_guild().get_channel(channel_id)
            await channel.send(content=text + '\n' + text_content, embeds=embeds)
            logger.info(f'Sent going live message for user {member} to guild {member.guild_id}, channel {channel_id}.')
    elif presence.activities is not None and streaming_role in member.role_ids:
        # remove role
        await member.remove_role(streaming_role)
        logger.info(f'Removed streaming role for user {member} in guild {member.guild_id}')
    _recent_notifs[cache_key] = 0  # value doesnt matter


async def _get_presence_message(streams: list[hikari.RichActivity]) -> tuple[str, list[hikari.Embed]]:
    text = ''
    embeds: list[hikari.Embed] = []
    for stream in streams:
        if stream.url and stream.url.startswith('https://www.twitch.tv/'):
            # import here cuz this might not be ready at module load time
            from snoozybot.discord_bot.commands.twitch import (
                _generate_stream_embed,
                twitch,
            )

            # Twitch default embeds are poop. Generate it myself
            twitch_username = stream.url[22:]
            twitch_streams = await twitch.fetch_streams(user_logins=[twitch_username])
            twitch_users = await twitch.fetch_users(names=[twitch_username])
            if twitch_streams and twitch_users:
                embeds.append(await _generate_stream_embed(twitch_streams[0], -1, twitch_users[0]))
            else:
                logger.warning(f'No stream at {stream.url}. Sending text instead.')
                text += stream.url + '\n'
        elif stream.url:
            text += stream.url + '\n'
    return text, embeds

load, unload = plugin.export_extension()
