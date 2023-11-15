import asyncio
import logging
import sys

import dingomata.chat as chat
import dingomata.database.lifecycle as database
import dingomata.discord_bot.lifecycle as discord_bot
from dingomata.config.env import envConfig
from dingomata.utils import get_client_session

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if envConfig.short_logs:
    logging.basicConfig(format="%(levelname)-4s %(name)s: %(message)s", level="INFO", stream=sys.stdout)


async def run():
    await database.start()
    await chat.start()
    try:
        await discord_bot.start()
    finally:
        await discord_bot.stop()
        await chat.stop()
        await database.stop()
        await get_client_session().close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
