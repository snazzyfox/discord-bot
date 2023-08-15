import asyncio
from collections import namedtuple
from copy import deepcopy

import hikari
import lightbulb
from async_lru import alru_cache
from cachetools import TTLCache
from lightbulb import BotApp

from dingomata.config.provider import get_config
from dingomata.config.values import ConfigKey

plugin = lightbulb.Plugin('logging')

DeleteAuditKey = namedtuple('DeleteAuditKey', ('guild', 'channel', 'author'))
_recent_audits = TTLCache(maxsize=256, ttl=180)


# Note: Discord audit logs does not tell us WHICH message was deleted; just which channel/user it's for.
# We match them based on guild, channel, and author as best effort.
# The TTL here is the max time tolerated between deletion and audit log entry for matching. Anything that's received
# farther apart from this will be considered separate deletion actions.

class LogsNotConfigured(Exception):
    """Exception class that allows early stop in log processing if logs is not turned on."""
    pass


@plugin.set_error_handler
async def plugin_error_handler(event: lightbulb.CommandErrorEvent):
    return isinstance(event.exception, LogsNotConfigured)


@plugin.listener(hikari.GuildMessageDeleteEvent)
@plugin.listener(hikari.GuildBulkMessageDeleteEvent)
async def log_message_delete(event: hikari.GuildMessageDeleteEvent | hikari.GuildBulkMessageDeleteEvent) -> None:
    await asyncio.sleep(1)  # let audit catch up first
    log_channel_id = await _get_log_channel(event.guild_id)
    if isinstance(event, hikari.GuildMessageDeleteEvent):
        messages = [event.old_message]
    else:
        messages = event.old_messages
    for message in messages:
        if message and not message.author.is_bot:
            audit_key = DeleteAuditKey(guild=event.guild_id, channel=event.channel_id, author=message.author.id)
            audit: hikari.AuditLogEntryCreateEvent | None = _recent_audits.get(audit_key)
            embed = _generate_message_embed(event, audit)
            log_channel = event.get_guild().get_channel(log_channel_id)
            await log_channel.send(embed=embed)


@plugin.listener(hikari.GuildMessageUpdateEvent)
async def log_message_update(event: hikari.GuildMessageUpdateEvent) -> None:
    if event.is_human:
        log_channel_id = await _get_log_channel(event.guild_id)
        embed = _generate_message_embed(event, None)
        log_channel = event.get_guild().get_channel(log_channel_id)
        await log_channel.send(embed=embed)


@plugin.listener(hikari.AuditLogEntryCreateEvent)
async def on_audit_log_entry_create(event: hikari.AuditLogEntryCreateEvent) -> None:
    if event.entry.action_type == hikari.AuditLogEventType.MESSAGE_DELETE:
        await _handle_delete_audit_log(event)
    elif event.entry.action_type == hikari.AuditLogEventType.MEMBER_BAN_ADD:
        await _handle_ban_audit_log(event)


async def _handle_delete_audit_log(event: hikari.AuditLogEntryCreateEvent) -> None:
    # See if this audit event corresponds to an existing error message
    if isinstance(event.entry.options, hikari.MessageDeleteEntryInfo):
        audit_key = DeleteAuditKey(
            guild=event.guild_id, channel=event.entry.options.channel_id, author=event.entry.target_id,
        )
        _recent_audits[audit_key] = event.entry


async def _handle_ban_audit_log(event: hikari.AuditLogEntryCreateEvent) -> None:
    log_channel_id = await _get_log_channel(event.guild_id)
    log_channel = event.get_guild().get_channel(log_channel_id)
    banned = event.get_guild().get_member(event.entry.target_id)
    embed = hikari.Embed(title='User banned', color=hikari.Color(0x880000))
    embed.add_field(name='User', value=banned.mention, inline=True)
    embed.add_field(name='Banned by', value=event.get_guild().get_member(event.entry.user_id).mention, inline=True)
    embed.add_field(name='Reason', value=event.entry.reason or '(Not provided)')
    embed.set_thumbnail(banned.display_avatar_url.url)
    await log_channel.send(embed=embed)


def _generate_message_embed(
        event: hikari.GuildMessageDeleteEvent | hikari.GuildBulkMessageDeleteEvent | hikari.GuildMessageUpdateEvent,
        audit: hikari.AuditLogEntry | None,
) -> hikari.Embed:
    embed = hikari.Embed()
    embed.add_field(name='Channel', value=event.get_channel().mention, inline=True)
    embed.add_field(name='Author', value=event.old_message.author.mention, inline=True)
    embed.add_field(name='Sent At', value=f'<t:{int(event.old_message.created_at.timestamp())}:f>')
    embed.add_field(name='Message URL (for T&S Reports)', value=event.old_message.make_link(event.guild_id))
    embed.add_field(name='Old Content', value=event.old_message.content)
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


@alru_cache(maxsize=12)
async def _get_log_channel(guild_id: int) -> int:
    log_enabled: bool = await get_config(guild_id, ConfigKey.LOGS__ENABLED)
    if log_enabled:
        return await get_config(guild_id, ConfigKey.LOGS__CHANNEL_ID)
    raise LogsNotConfigured()


def load(bot: BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: BotApp):
    bot.remove_plugin(plugin.name)
