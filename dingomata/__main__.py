import logging

from dingomata.bot import run
from dingomata.config import get_logging_config, load_configs

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    get_logging_config()
    load_configs()
    run()
