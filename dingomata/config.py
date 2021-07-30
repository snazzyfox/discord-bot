import os
import logging.config
from configparser import ConfigParser
from enum import Enum
from typing import Optional

_CONFIG_FILE = 'dingomata.cfg'
_CONFIG: Optional[ConfigParser] = None


class ConfigurationKey(Enum):
    BOT_TOKEN = ('bot', 'token')
    BOT_COMMAND_PREFIX = ('bot', 'command_prefix')
    SECURITY_SERVER_ID = ('security', 'server_id')
    SECURITY_MOD_ROLE_IDS = ('security', 'mod_roles')
    SECURITY_MOD_CHANNEL_IDS = ('security', 'mod_channels')
    SECURITY_PLAYER_ROLES = ('security', 'player_roles')
    SECURITY_EXCLUDE_SELECTED = ('security', 'exclude_selected_players')
    MESSAGE_PLAYER_CHANNEL = ('message', 'player_channel')
    MESSAGE_OPENED = ('message', 'opened')
    MESSAGE_OPENED_SUB = ('message', 'opened_subtext')
    MESSAGE_JOINED = ('message', 'joined')
    MESSAGE_LEFT = ('message', 'left')
    MESSAGE_CLOSED = ('message', 'closed')
    MESSAGE_PICKED_ANNOUNCE = ('message', 'picked_announce')


def get_config_value(key: ConfigurationKey) -> Optional[str]:
    global _CONFIG
    env_key = 'DINGOMATA_' + '_'.join(k.upper() for k in key.value)
    if env_key in os.environ:
        logging.debug(f'Got config value for {key} from environment variable {env_key}')
        return os.environ[env_key]
    if not _CONFIG:
        try:
            with open(_CONFIG_FILE, 'r') as f:
                logging.debug(f'Loaded config file')
                _CONFIG = ConfigParser()
                _CONFIG.read_file(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Unable to read configuration {key} because the environment variable {env_key} is "
                                    f"not found, and a configuration file does not exist.") from e
    return _CONFIG.get(*key.value, fallback=None)


def get_logging_config():
    logging.config.fileConfig(_CONFIG_FILE, disable_existing_loggers=False)
