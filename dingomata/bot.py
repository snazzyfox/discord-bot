import asyncio
import logging

import discord
from discord import Intents
from discord.ext import commands
from discord.ext.commands import CommandInvokeError, CheckFailure
from discord_slash import SlashContext, ComponentContext
from discord_slash.client import SlashCommand
from discord_slash.error import CheckFailure as SlashCheckFailure
from sqlalchemy.ext.asyncio import create_async_engine

from .cogs import BedtimeCog, GambaCog, TextCommandsCog, GameCodeSenderCommands
from .config import BotConfig
from .exceptions import DingomataUserError

log = logging.getLogger(__name__)
discord.VoiceClient.warn_nacl = False  # Disable warning for no voice support since it's a text bot

bot_config = BotConfig()
bot = commands.Bot(
    command_prefix=bot_config.command_prefix,
    intents=Intents(guilds=True, messages=True, dm_messages=True, members=True)
)
slash = SlashCommand(bot, sync_commands=True)

engine = create_async_engine(bot_config.database_url.get_secret_value())

bot.add_cog(GameCodeSenderCommands(bot, engine))
bot.add_cog(BedtimeCog(bot, engine))
bot.add_cog(GambaCog(bot, engine))
bot.add_cog(TextCommandsCog(bot))


def run():
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.start(bot_config.token.get_secret_value()))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
    finally:
        loop.run_until_complete(_stop_bot())
        loop.close()


async def _stop_bot():
    await engine.dispose()


@bot.event
async def on_ready():
    log.info(f'Bot is now up and running.')


@bot.event
async def on_disconnect():
    log.info(f'Bot has disconnected.')


@bot.event
async def on_slash_command(ctx: SlashContext):
    log.info(f'Received slash command {ctx.command} {ctx.subcommand_name} from {ctx.author} at {ctx.channel}')


@bot.event
async def on_component_callback(ctx: ComponentContext):
    log.info(f'Received component callback from {ctx.author} at {ctx.channel}')


@bot.event
async def on_slash_command_error(ctx: SlashContext, exc: Exception):
    if isinstance(exc, (CheckFailure, SlashCheckFailure)):
        log.warning(f'Ignored a message from {ctx.author} in guild {ctx.guild or "DM"} '
                    f'because a check failed: {exc.args}')
        return
    if isinstance(exc, CommandInvokeError):
        exc = exc.original
    if isinstance(exc, DingomataUserError):
        await ctx.reply(f"You can't do that. {exc}", hidden=True)
        log.warning(f'{exc.__class__.__name__}: {exc}')
    else:
        log.exception(exc)


@bot.event
async def on_component_callback_error(ctx: ComponentContext, exc: Exception):
    if isinstance(exc, DingomataUserError):
        await ctx.reply(f"You can't do that. {exc}", hidden=True)
        log.warning(f'{exc.__class__.__name__}: {exc}')
    else:
        log.exception(exc)
