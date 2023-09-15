import logging

import hikari

from dingomata.config import values
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('auto_unarchive')
logger = logging.getLogger(__name__)


@plugin.listener(hikari.GuildThreadUpdateEvent)
async def on_thread_update(event: hikari.GuildThreadUpdateEvent) -> None:
    if event.thread.is_archived and not event.thread.is_locked:
        monitored_channels = await values.auto_unarchive_channels.get_value(event.guild_id)
        if monitored_channels and event.thread.parent_id in monitored_channels:
            await event.thread.edit(archived=False)
            logger.info('Unarchived just-archived thread: guild %s, channel %s, thread %s', event.guild_id,
                        event.thread.parent_id, event.thread_id)


load, unload = plugin.export_extension()
