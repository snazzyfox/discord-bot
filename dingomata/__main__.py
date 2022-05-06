import asyncio
import logging
import sys

from dingomata.bot import run
from dingomata.config.bot import get_logging_config

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    get_logging_config()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
