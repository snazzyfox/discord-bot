import logging

import discord

from ..decorators import slash
from ..exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class AdminCog(discord.Cog):
    """Remind users to go to bed."""

    def __init__(self, bot: discord.Bot):
        self._bot = bot

    @slash(default_available=False, mod_only=True)
    async def echo(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(str, "Channel ID to send message to"),
        message: discord.Option(str, "Content of message to send"),
    ):
        """Say something in a specific channel."""
        ch = self._bot.get_channel(int(channel))
        if not ch:
            raise DingomataUserError("Channel ID invalid.")
        else:
            await ch.send(message)
            await ctx.respond("Done", ephemeral=True)
