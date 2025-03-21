import asyncio
import logging
import math

import hikari
import lightbulb
from hikari.impl.config import CacheSettings
from pydantic import SecretStr

from snoozybot.config.env import envConfig
from snoozybot.config.provider import get_secret_configs
from snoozybot.exceptions import UserError

logger = logging.getLogger(__name__)

_bots: list[lightbulb.BotApp] = []

bot_intents = (
    hikari.Intents.GUILDS
    | hikari.Intents.GUILD_MESSAGES
    | hikari.Intents.MESSAGE_CONTENT
    | hikari.Intents.GUILD_MEMBERS
    | hikari.Intents.GUILD_MODERATION
    | hikari.Intents.GUILD_PRESENCES
)
cache_settings = CacheSettings(max_messages=3000)


def create_bot(token: SecretStr, guilds: set[int]) -> lightbulb.BotApp:
    bot = lightbulb.BotApp(
        token=token.get_secret_value(),
        logs=envConfig.log_level,
        banner=None,
        intents=bot_intents,
        cache_settings=cache_settings,
    )
    bot.default_enabled_guilds = guilds
    bot.load_extensions_from('snoozybot/discord_bot/commands')

    @bot.listen()
    async def on_error(event: lightbulb.CommandErrorEvent) -> None:
        if isinstance(event.exception, UserError):
            await event.context.respond(
                'Error: ' + str(event.exception),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            logger.warning(f"{event.exception.__class__.__name__}: {event.exception}")
        elif isinstance(event.exception.__cause__, UserError):
            await event.context.respond(
                'Error: ' + str(event.exception.__cause__),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            logger.warning(f"{event.exception.__cause__.__class__.__name__}: {event.exception.__cause__}")
        elif isinstance(event.exception, lightbulb.CommandIsOnCooldown):
            await event.context.respond(
                f'This command is on cooldown. You can use this command again in '
                f'{math.ceil(event.exception.retry_after)} seconds here, or you can use it in the bot spam channel '
                f'if there is one.',
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            logger.warning(f"{event.exception.__class__.__name__}: {event.exception}")
        elif isinstance(event.exception, lightbulb.CheckFailure):
            await event.context.respond(
                'Error: ' + str(event.exception),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            logger.warning(f"{event.exception.__class__.__name__}: {event.exception}")
        else:
            raise event.exception

    @bot.listen()
    async def on_interaction(event: lightbulb.CommandInvocationEvent) -> None:
        logger.info("Command %s invoked by %s in guild %s, channel %s, params: %s",
                    event.command.name, event.context.author, event.context.get_guild().name,
                    event.context.get_channel().name,
                    ', '.join('%s=%s' % i for i in event.context.options.items()))

    return bot


async def _start_bot(b: lightbulb.BotApp):
    try:
        return await b.start(check_for_updates=False)
    except RuntimeError:
        logger.exception(f'FAILED TO START BOT FOR GUILDS {b.default_enabled_guilds}')
        raise


async def start() -> None:
    global _bots
    logger.info('Starting discord bots...')

    # Get tokens from config store
    tokens_config = await get_secret_configs('secret.discord.token')

    # Group guilds by token - some guilds may share the same bot
    grouped: dict[SecretStr, set[int]] = {}
    for guild_id, token in tokens_config.items():
        grouped.setdefault(token, set()).add(guild_id)

    # Prepare one bot for each group
    for token, guilds in grouped.items():
        logger.info(f'Creating discord bot for guilds {guilds}')
        bot = create_bot(token, guilds)
        _bots.append(bot)

    await asyncio.gather(*(_start_bot(bot) for bot in _bots))
    await asyncio.gather(*(bot.join() for bot in _bots))


async def stop():
    global _bots
    logger.info('Closing connections on all discord bots...')
    await asyncio.gather(*(bot.close() for bot in _bots))
