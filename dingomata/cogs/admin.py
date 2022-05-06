import logging

import discord

from ..decorators import slash
from ..exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class AdminCog(discord.Cog):
    """Remind users to go to bed."""

    def __init__(self, bot: discord.Bot):
        self._bot = bot

    @slash(default_available=False)
    @discord.option('channel', description="Channel ID to send message to")
    @discord.option('message', description="Content of message to send")
    async def echo(self, ctx: discord.ApplicationContext, channel: str, message: str) -> None:
        """Say something in a specific channel."""
        ch = self._bot.get_channel(int(channel))
        if not ch:
            raise DingomataUserError("Channel ID invalid.")
        else:
            await ch.send(message)
            await ctx.respond("Done", ephemeral=True)
