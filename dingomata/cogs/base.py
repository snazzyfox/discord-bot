from typing import Dict

import discord


class BaseCog(discord.Cog):
    """An extension of discord.Cog that works better with multiple bots."""
    _BOTS: Dict[int, discord.Bot] = {}

    def __init__(self, bot: discord.Bot) -> None:
        self._bot = bot

    def _bot_for(self, guild_id: int) -> discord.Bot:
        """Fetch bot object for a specific guild.

        This is necessary to get around limitations imposed by pycord syntax where command objects are static
        class objects and cannot be reused for multiple bots importing the same cog. This should always be preferred
        over accessing self._bot directly.
        """
        return self._BOTS[guild_id]

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        """Register the passed in bot under all servers it has access to so that it can be fetched later."""
        for guild in self._bot.guilds:
            self._BOTS[guild.id] = self._bot
