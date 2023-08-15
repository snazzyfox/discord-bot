import asyncio
import logging

import hikari
import lightbulb
from pydantic import SecretStr

from dingomata.config.provider import get_secret_config
from dingomata.config.values import SecretConfigKey
from dingomata.exceptions import UserError

logger = logging.getLogger(__name__)

_bots: list[lightbulb.BotApp] = []

bot_intents = (
    hikari.Intents.GUILDS
    | hikari.Intents.GUILD_MESSAGES
    | hikari.Intents.MESSAGE_CONTENT
    | hikari.Intents.GUILD_MEMBERS
    | hikari.Intents.GUILD_MODERATION
)


def create_bot(token: SecretStr, guilds: set[int]) -> lightbulb.BotApp:
    bot = lightbulb.BotApp(token=token.get_secret_value(), banner=None, intents=bot_intents)
    bot.default_enabled_guilds = guilds
    bot.load_extensions_from('dingomata/discord_bot/commands')

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
        else:
            raise event.exception

    return bot


async def start() -> None:
    global _bots
    logger.info('Starting discord bots...')

    # Get tokens from config store
    tokens_config = await get_secret_config(SecretConfigKey.DISCORD_TOKEN)

    # Group guilds by token - some guilds may share the same bot
    grouped: dict[SecretStr, set[int]] = {}
    for guild_id, token in tokens_config.items():
        grouped.setdefault(token, set()).add(guild_id)

    # Prepare one bot for each group
    for token, guilds in grouped.items():
        logger.info(f'Creating bot for guilds {guilds}')
        bot = create_bot(token, guilds)
        _bots.append(bot)

    await asyncio.gather(*(bot.start(check_for_updates=False) for bot in _bots))
    await asyncio.gather(*(bot.join() for bot in _bots))


async def stop():
    global _bots
    logger.info('Closing connections on all discord bots...')
    await asyncio.gather(*(bot.close() for bot in _bots))
