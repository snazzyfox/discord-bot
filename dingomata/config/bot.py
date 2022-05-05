import logging.config
import os
from functools import cached_property
from typing import Dict, List, Optional, Set

import pydantic
import toml
from pydantic import BaseModel, BaseSettings, Field, FilePath, SecretStr

from . import cogs

_LOGGING_CONFIG = "config/logging.cfg"

_logger = logging.getLogger(__name__)


class CooldownConfig(BaseModel):
    exempt: Set[int] = set()  # Channels that are exempt from cooldown
    defualt_seconds: int = 30  # Global command cooldown period for this server


class CommandConfig(BaseModel):
    enabled: Optional[bool] = None
    cooldown_seconds: Optional[int] = None


class RoleConfig(BaseModel):
    no_pings: List[int] = []
    self_assign: List[int] = []


class GuildConfig(BaseModel):
    """Per-guild configs"""

    id: int
    roles: RoleConfig = RoleConfig()
    cooldown: CooldownConfig = CooldownConfig()
    commands: Dict[str, CommandConfig] = {}

    bedtime: cogs.BedtimeConfig = cogs.BedtimeConfig()
    automod: cogs.AutomodConfig = cogs.AutomodConfig()
    gamba: cogs.GambaConfig = cogs.GambaConfig()
    game_code: cogs.GameCodeConfig = cogs.GameCodeConfig()
    logging: cogs.LoggingConfig = cogs.LoggingConfig()

    class Config:
        keep_untouched = (cached_property,)
        extra = "forbid"

    def command_enabled(self, command: str, default: bool) -> bool:
        if command in self.commands:
            enabled = self.commands[command].enabled
            return enabled if enabled is not None else default
        else:
            return default

    def command_cooldown_seconds(self, command: str) -> int:
        cmd_config = self.commands.get(command)
        if cmd_config:
            return cmd_config.cooldown_seconds or self.cooldown.defualt_seconds
        else:
            return self.cooldown.defualt_seconds


class ServiceConfig(BaseSettings):
    token: SecretStr = Field(..., env="token")
    database_url: SecretStr = Field(..., env="database_Url")
    config_file: FilePath = Field('config/config.toml', env="config_file")

    class Config:
        env_prefix = "dingomata"
        env_file = os.environ.get("ENV_FILE", ".env")
        keep_untouched = (cached_property,)
        extra = "forbid"

    @cached_property
    def server(self) -> Dict[int, GuildConfig]:
        config_data = toml.load(self.config_file.open())
        config_list = pydantic.parse_obj_as(List[GuildConfig], config_data["server"])
        return {server.id: server for server in config_list}

    @cached_property
    def cooldown_exempt(self) -> Set[int]:
        return {channel for config in self.server.values() for channel in config.cooldown.exempt}

    def get_command_guilds(self, command: str, default: bool = True) -> List[int]:
        return [server for server, config in self.server.items() if config.command_enabled(command, default)]

    def get_command_cooldowns(self, command: str) -> Dict[int, int]:
        return {server: config.command_cooldown_seconds(command) for server, config in self.server.items()}


def get_logging_config():
    logging.config.fileConfig(_LOGGING_CONFIG, disable_existing_loggers=False)
    _logger.debug("Loaded logging config.")


service_config = ServiceConfig()
