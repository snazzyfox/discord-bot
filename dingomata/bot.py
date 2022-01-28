import logging

import discord
import tortoise

from .cogs import all_cogs
from .config import service_config
from .exceptions import DingomataUserError

log = logging.getLogger(__name__)

bot = discord.Bot(intents=discord.Intents(guilds=True, messages=True, members=True))

for cog in all_cogs:
    bot.add_cog(cog(bot))


async def init():
    await tortoise.Tortoise.init(
        modules={"models": ["dingomata.models"]},
        db_url=service_config.database_url.get_secret_value(),
    )
    await tortoise.Tortoise.generate_schemas()


def run():
    bot.loop.create_task(init())
    bot.run(service_config.token.get_secret_value())


@bot.event
async def on_ready():
    log.info("Bot is now up and running.")


@bot.event
async def on_disconnect():
    log.info("Bot has disconnected.")


@bot.slash_command()
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond("Pong!")


@bot.listen()
async def on_interaction(interaction: discord.Interaction):
    if interaction.guild:
        location = f"{interaction.guild.name}/#{interaction.channel.name}"
    else:
        location = "DM"
    log.info(f"Received {interaction.type.name} from {interaction.user} at {location}: {interaction.data}")


@bot.listen()
async def on_application_command_error(ctx: discord.ApplicationContext, exc: Exception):
    if isinstance(exc, discord.ApplicationCommandInvokeError):
        exc = exc.original  # Don't care about the wrapped exception
    if isinstance(exc, DingomataUserError):
        await ctx.respond(f"Error: {exc}", ephemeral=True)
        log.warning(f"{exc.__class__.__name__}: {exc}")
    else:
        log.exception(exc, exc_info=exc)
