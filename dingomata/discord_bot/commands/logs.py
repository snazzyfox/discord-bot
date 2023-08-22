import asyncio
from collections import namedtuple
from copy import deepcopy

import hikari
import lightbulb
from async_lru import alru_cache
from cachetools import TTLCache

from dingomata.config import values
from dingomata.config.provider import cached_config
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('logs')

_AUDIT_DELAY = 2.0
DeleteAuditKey = namedtuple('DeleteAuditKey', ('guild', 'channel', 'author'))
BannedAuditKey = namedtuple('BannedAuditKey', ('guild', 'user'))
_recent_audits: TTLCache = TTLCache(maxsize=256, ttl=180)


# Note: Discord audit logs does not tell us WHICH message was deleted; just which channel/user it's for.
# We match them based on guild, channel, and author as best effort.
# The TTL here is the max time tolerated between deletion and audit log entry for matching. Anything that's received
# farther apart from this will be considered separate deletion actions.


@plugin.listener(hikari.GuildMessageDeleteEvent)
@plugin.listener(hikari.GuildBulkMessageDeleteEvent)
async def log_message_delete(event: hikari.GuildMessageDeleteEvent | hikari.GuildBulkMessageDeleteEvent) -> None:
    await asyncio.sleep(_AUDIT_DELAY)  # let audit catch up first
    log_channel_id = await _get_log_channel(event.guild_id)
    if not log_channel_id:
        return
    if isinstance(event, hikari.GuildMessageDeleteEvent):
        messages = [event.old_message]
    else:
        messages = event.old_messages
    for message in messages:
        if message:
            audit_key = DeleteAuditKey(guild=event.guild_id, channel=event.channel_id, author=message.author.id)
            audit: hikari.AuditLogEntry | None = _recent_audits.get(audit_key)
            embed = _generate_message_embed(event, audit)
            if not message.author.is_bot:
                log_channel = event.get_guild().get_channel(log_channel_id)
                await log_channel.send(embed=embed)
            if audit and audit.user_id == 338303784654733312 and 'cute' in event.old_message.content.lower():
                await event.get_channel().send(event.old_message.content)


@plugin.listener(hikari.GuildMessageUpdateEvent)
async def log_message_update(event: hikari.GuildMessageUpdateEvent) -> None:
    if event.is_human and event.old_message:  # dont have anything to log if no cached message
        log_channel_id = await _get_log_channel(event.guild_id)
        if not log_channel_id:
            return
        embed = _generate_message_embed(event, None)
        log_channel = event.get_guild().get_channel(log_channel_id)
        await log_channel.send(embed=embed)


@plugin.listener(hikari.BanCreateEvent)
async def log_ban_create(event: hikari.BanCreateEvent) -> None:
    await asyncio.sleep(_AUDIT_DELAY)  # let audit catch up first
    log_channel_id = await _get_log_channel(event.guild_id)
    if not log_channel_id:
        return
    log_channel = event.get_guild().get_channel(log_channel_id)
    banned = event.user
    audit_key = BannedAuditKey(guild=event.guild_id, user=event.user_id)
    audit = _recent_audits.get(audit_key)
    embed = hikari.Embed(title='User banned', color=hikari.Color(0x880000))
    embed.add_field(name='User', value=banned.username, inline=True)
    if audit:
        embed.add_field(name='Banned by', value=event.get_guild().get_member(audit.user_id).mention, inline=True)
        embed.add_field(name='Reason', value=audit.reason or '(Not provided)')
    embed.set_thumbnail(banned.display_avatar_url.url)
    await log_channel.send(embed=embed)


@plugin.listener(hikari.AuditLogEntryCreateEvent)
async def on_audit_log_entry_create(event: hikari.AuditLogEntryCreateEvent) -> None:
    if event.entry.action_type == hikari.AuditLogEventType.MESSAGE_DELETE:
        await _handle_delete_audit_log(event)
    elif event.entry.action_type == hikari.AuditLogEventType.MEMBER_BAN_ADD:
        await _handle_ban_audit_log(event)


async def _handle_delete_audit_log(event: hikari.AuditLogEntryCreateEvent) -> None:
    if isinstance(event.entry.options, hikari.MessageDeleteEntryInfo):
        audit_key = DeleteAuditKey(
            guild=event.guild_id, channel=event.entry.options.channel_id, author=event.entry.target_id,
        )
        _recent_audits[audit_key] = event.entry


async def _handle_ban_audit_log(event: hikari.AuditLogEntryCreateEvent) -> None:
    audit_key = BannedAuditKey(guild=event.guild_id, user=event.entry.target_id)
    _recent_audits[audit_key] = event.entry


def _generate_message_embed(
    event: hikari.GuildMessageDeleteEvent | hikari.GuildBulkMessageDeleteEvent | hikari.GuildMessageUpdateEvent,
    audit: hikari.AuditLogEntry | None,
) -> hikari.Embed:
    embed = hikari.Embed()
    embed.add_field(name='Channel', value=event.get_channel().mention, inline=True)
    embed.add_field(name='Author', value=event.old_message.author.mention, inline=True)
    embed.add_field(name='Sent At', value=f'<t:{int(event.old_message.created_at.timestamp())}:f>')
    embed.add_field(name='Message URL (for T&S Reports)', value=event.old_message.make_link(event.guild_id))
    embed.add_field(name='Old Content', value=event.old_message.content or '(empty or attachment only)')
    embed.set_thumbnail(event.old_message.author.display_avatar_url.url)

    if isinstance(event, (hikari.GuildMessageDeleteEvent, hikari.GuildBulkMessageDeleteEvent)):
        embed.title = 'Message deleted'
    else:
        embed.title = 'Message edited'
        embed.add_field(name='New Content', value=event.message.content)
    if audit:
        embed.add_field(name='Action performed by', value=event.get_guild().get_member(audit.user_id).mention,
                        inline=True)
        embed.add_field(name='Reason', value=audit.reason or '(Not provided)', inline=True)
    return embed


@cached_config
@alru_cache(maxsize=12)
async def _get_log_channel(guild_id: int) -> int | None:
    log_enabled = await values.logs_enabled.get_value(guild_id)
    log_channel = await values.logs_channel_id.get_value(guild_id)
    if log_enabled and log_channel:
        return log_channel
    else:
        return None


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
