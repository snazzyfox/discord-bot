import logging.config
from collections import ChainMap
from functools import cache
from pathlib import Path
from typing import Optional, Dict, List, Any, Set

import yaml
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_permission
from pydantic import BaseSettings, SecretStr, BaseModel, Field, validator

_CONFIG_DIR = Path('config')
_LOGGING_CONFIG = _CONFIG_DIR / 'logging.cfg'
_DEFAULT_CONFIG = _CONFIG_DIR / 'server_defaults.yaml'
_SERVER_CONFIG_DIR = _CONFIG_DIR / 'servers'

_logger = logging.getLogger(__name__)


class CommonGuildConfig(BaseModel):
    """Configs used across all cogs."""
    guild_id: int
    mod_roles: List[int] = []
    no_ping_users: Set[int] = []


class GameCodeConfig(BaseModel):
    """Config for random user selector"""
    player_roles: Dict[Optional[int], int]
    exclude_played: bool


class BedtimeConfig(BaseModel):
    cooldown: int = 7200
    sleep_hours: int = 6


class GambaConfig(BaseModel):
    points_name: str = 'points'
    daily_points: int = 1000


class GuildConfig(BaseModel):
    common: CommonGuildConfig
    game_code: GameCodeConfig
    bedtime: BedtimeConfig
    gamba: GambaConfig


class BotConfig(BaseSettings):
    token: SecretStr = Field(..., env='token')
    database_url: SecretStr = Field(..., env='database_Url')
    command_prefix: str = Field('\\', min_length=1, max_length=1)  # This is unused

    @validator('database_url', pre=True)
    def translate_postgres(cls, v: Any):
        if isinstance(v, str) and v.startswith('postgres://'):
            return v.replace('postgres://', 'postgresql+asyncpg://')
        return v

    class Config:
        env_prefix = 'dingomata'
        env_file = '.env'


@cache
def _get_all_configs() -> Dict[int, GuildConfig]:
    result: Dict[int, GuildConfig] = {}
    _logger.debug(f'Reading default configs from {_DEFAULT_CONFIG}')
    defaults = yaml.safe_load(_DEFAULT_CONFIG.open())
    for server_config_file in _SERVER_CONFIG_DIR.iterdir():
        _logger.debug(f'Reading guild config for {server_config_file}')
        server_config_data = yaml.safe_load(server_config_file.open())
        keys = set(defaults) | set(server_config_data)
        merged = {key: ChainMap(server_config_data.get(key, {}), defaults.get(key, {})) for key in keys}
        server_config = GuildConfig.parse_obj(merged)
        result[server_config.common.guild_id] = server_config
    return result


def get_guild_config(guild_id: int) -> GuildConfig:
    return _get_all_configs()[guild_id]


def has_guild_config(guild_id: int) -> bool:
    return guild_id in _get_all_configs()


def get_guilds() -> List[int]:
    return list(_get_all_configs().keys())


def get_mod_permissions():
    return {guild_id: [
        create_permission(role, SlashCommandPermissionType.ROLE, True) for role in guild_config.common.mod_roles
    ] + [
        create_permission(749862270129143880, SlashCommandPermissionType.USER, True)  # Bot owner
    ] for guild_id, guild_config in _get_all_configs().items()}


def get_logging_config():
    logging.config.fileConfig(_LOGGING_CONFIG, disable_existing_loggers=False)
    _logger.debug('Loaded logging config.')


def load_configs():
    _get_all_configs.cache_clear()
    _get_all_configs()
