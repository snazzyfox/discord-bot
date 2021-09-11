import logging

from dingomata.bot import run
from dingomata.config.config import get_logging_config

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    get_logging_config()
    run()
