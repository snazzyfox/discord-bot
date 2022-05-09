import logging

import discord

from ..decorators import slash
from ..exceptions import DingomataUserError
from .base import BaseCog

_log = logging.getLogger(__name__)


class AdminCog(BaseCog):
    """Remind users to go to bed."""

    @slash(default_available=False)
    @discord.option('channel', description="Channel ID to send message to")
    @discord.option('message', description="Content of message to send")
    async def echo(self, ctx: discord.ApplicationContext, channel: str, message: str) -> None:
        """Say something in a specific channel."""
        ch = self._bot_for(ctx.guild.id).get_channel(int(channel))
        if not ch:
            raise DingomataUserError("Channel ID invalid.")
        else:
            await ch.send(message)
            await ctx.respond("Done", ephemeral=True)
