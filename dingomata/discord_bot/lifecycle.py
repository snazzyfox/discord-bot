import asyncio
import logging

import lightbulb
from pydantic import SecretStr

from dingomata.config.provider import get_secret_config

logger = logging.getLogger(__name__)

_bots: list[lightbulb.BotApp] = []


def prepare_bot(bot: lightbulb.BotApp, guild_ids: set[int]):
    bot.default_enabled_guilds = guild_ids
    logger.info('Bot application commands will be registered for guilds %s', guild_ids)
    bot.load_extensions_from('dingomata/discord_bot/commands')


async def start() -> None:
    global _bots
    logger.info('Starting discord bots...')

    # Get tokens from config store
    tokens_config = await get_secret_config('secret.discord.token')

    # Group guilds by token - some guilds may share the same bot
    grouped: dict[SecretStr, set[int]] = {}
    for guild_id, token in tokens_config.items():
        grouped.setdefault(token, set()).add(guild_id)

    # Prepare one bot for each group
    for token, guilds in grouped.items():
        bot = lightbulb.BotApp(token.get_secret_value(), banner=None, logs='DEBUG')
        prepare_bot(bot, guilds)
        _bots.append(bot)

    await asyncio.gather(*(bot.start(check_for_updates=False) for bot in _bots))
    await asyncio.gather(*(bot.join() for bot in _bots))


async def stop():
    global _bots
    logger.info('Closing connections on all discord bots...')
    await asyncio.gather(*(bot.close() for bot in _bots))
