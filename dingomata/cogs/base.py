import discord


class BaseCog(discord.Cog):
    """An extension of discord.Cog that works better with multiple bots."""
    _BOTS: dict[int, discord.Bot] = {}
    __slots__ = '_bot',

    def __init__(self, bot: discord.Bot) -> None:
        self._bot = bot

    @classmethod
    def _bot_for(cls, guild_id: int) -> discord.Bot:
        """Fetch discord_bot object for a specific guild.

        This is necessary to get around limitations imposed by pycord syntax where command objects are static
        class objects and cannot be reused for multiple bots importing the same cog. This should always be preferred
        over accessing self._bot directly.
        """
        return cls._BOTS[guild_id]

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        """Register the passed in discord_bot under all servers it has access to so that it can be fetched later."""
        for guild in self._bot.guilds:
            self._BOTS[guild.id] = self._bot
