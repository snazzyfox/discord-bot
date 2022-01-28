import asyncio
import logging
import platform

from dingomata.bot import run
from dingomata.config.bot import get_logging_config

logger = logging.getLogger(__name__)
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    get_logging_config()
    run()
