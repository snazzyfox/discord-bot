import asyncio
import logging

import discord
from discord import Intents
from discord.ext import commands
from discord.ext.commands import CommandInvokeError, CheckFailure, CommandOnCooldown
from discord_slash import SlashContext, ComponentContext
from discord_slash.client import SlashCommand
from discord_slash.error import CheckFailure as SlashCheckFailure
from sqlalchemy.ext.asyncio import create_async_engine

from .cogs import all_cogs
from dingomata.config.config import service_config
from .exceptions import DingomataUserError

log = logging.getLogger(__name__)
discord.VoiceClient.warn_nacl = False  # Disable warning for no voice support since it's a text bot

bot = commands.Bot(
    command_prefix=service_config.command_prefix,
    intents=Intents(guilds=True, messages=True, dm_messages=True, members=True)
)
slash = SlashCommand(bot, sync_commands=True, delete_from_unused_guilds=True)

engine = create_async_engine(service_config.database_url.get_secret_value())

for cog in all_cogs:
    bot.add_cog(cog(bot, engine))


def run():
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.start(service_config.token.get_secret_value()))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
    finally:
        loop.run_until_complete(_stop_bot())
        loop.close()


async def _stop_bot():
    await engine.dispose()


@bot.event
async def on_ready():
    log.info('Bot is now up and running.')


@bot.event
async def on_disconnect():
    log.info('Bot has disconnected.')


@bot.event
async def on_slash_command(ctx: SlashContext):
    log.info(f'Received slash command {ctx.command} {ctx.subcommand_name} from {ctx.author} at {ctx.channel}')


@bot.event
async def on_component_callback(ctx: ComponentContext, callback):
    log.info(f'Received component callback {ctx.component_id} from {ctx.author} at {ctx.channel}')


@bot.event
async def on_slash_command_error(ctx: SlashContext, exc: Exception):
    if isinstance(exc, (CheckFailure, SlashCheckFailure)):
        log.warning(f'Ignored a message from {ctx.author} in guild {ctx.guild or "DM"} '
                    f'because a check failed: {exc.args}')
        return
    if isinstance(exc, CommandInvokeError):
        exc = exc.original
    if isinstance(exc, (DingomataUserError, CommandOnCooldown)):
        await ctx.reply(f"Error handling command: {exc}", hidden=True)
        log.warning(f'{exc.__class__.__name__}: {exc}')
    else:
        log.exception(exc, exc_info=exc)


@bot.event
async def on_component_callback_error(ctx: ComponentContext, exc: Exception):
    if isinstance(exc, DingomataUserError):
        await ctx.reply(f"Error handling command: {exc}", hidden=True)
        log.warning(f'{exc.__class__.__name__}: {exc}')
    else:
        log.exception(exc, exc_info=exc)
