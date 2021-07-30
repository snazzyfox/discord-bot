import logging

from dingomata.bot import bot
from dingomata.config import get_logging_config, ConfigurationKey, get_config_value

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    get_logging_config()
    logger.debug('Logging config has been loaded.')
    bot.run(get_config_value(ConfigurationKey.BOT_TOKEN))
