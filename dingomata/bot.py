import asyncio
import logging

import discord
import tortoise

from .cogs import all_cogs
from .config import service_config
from .exceptions import DingomataUserError

log = logging.getLogger(__name__)


class Dingomata(discord.Bot):
    async def sync_commands(self) -> None:
        """Specialized to only register commands to guilds relevant to the bot."""
        commands = self.pending_application_commands
        registered_guild_commands = {}
        for guild in self.guilds:
            guild_id = guild.id
            guild_commands = [cmd for cmd in commands if cmd.guild_ids is not None and guild_id in cmd.guild_ids]
            registered_guild_commands[guild_id] = await self.register_commands(guild_commands, guild_id=guild_id)

        for _, commands in registered_guild_commands.items():
            for i in commands:
                cmd = next((cmd for cmd in self.pending_application_commands if cmd.name == i["name"]
                            and cmd.type == i["type"]
                            and cmd.guild_ids is not None
                            and int(i["guild_id"]) in cmd.guild_ids), None)
                if not cmd:
                    # command has not been added yet
                    continue
                cmd.id = i["id"]
                self._application_commands[cmd.id] = cmd


def create_bot():
    bot = Dingomata(
        intents=discord.Intents(guilds=True, messages=True, message_content=True, members=True),
        max_messages=4096
    )
    for cog in all_cogs:
        bot.add_cog(cog(bot))

    @bot.listen()
    async def on_ready():
        log.info(f'Bot connected: "{bot.user}" {[guild.name for guild in bot.guilds]}.')

    @bot.listen()
    async def on_disconnect():
        log.info(f'Bot disconnected: "{bot.user}"')

    @bot.listen()
    async def on_interaction(interaction: discord.Interaction):
        if interaction.guild:
            location = f"{interaction.guild.name}/#{interaction.channel.name}"
        else:
            location = "DM"
        log.info(f"Interaction: {bot.user.name} {interaction.type.name} {interaction.data.get('name')} "
                 f"{interaction.user} {location} ({interaction.data.get('options')})")

    @bot.listen()
    async def on_application_command_error(ctx: discord.ApplicationContext, exc: Exception):
        if isinstance(exc, discord.ApplicationCommandInvokeError):
            exc = exc.original  # Don't care about the wrapped exception
        if isinstance(exc, DingomataUserError):
            await ctx.respond(f"Error: {exc}", ephemeral=True)
            log.warning(f"{exc.__class__.__name__}: {exc}")
        else:
            log.exception(exc, exc_info=exc)

    return bot


async def run():
    await tortoise.Tortoise.init(
        modules={"models": ["dingomata.models"]},
        db_url=service_config.database_url.get_secret_value(),
    )
    await tortoise.Tortoise.generate_schemas()
    tokens = service_config.token.get_secret_value().split(',')
    bots = [create_bot() for _ in tokens]
    try:
        await asyncio.wait([bot.start(token) for bot, token in zip(bots, tokens)])
    finally:
        log.info("Disconnecting bots...")
        await asyncio.wait([bot.close() for bot in bots if not bot.is_closed()])
