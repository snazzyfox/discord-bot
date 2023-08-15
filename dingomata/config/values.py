from enum import Enum


class ConfigKey(str, Enum):
    ROLES__NO_PINGS = 'roles.no_pings'
    LOGS__ENABLED = 'logs.enabled'
    LOGS__CHANNEL_ID = 'logs.channel_id'


class SecretConfigKey(str, Enum):
    DISCORD_TOKEN = 'secret.discord.token'  # noqa: S105


defaults = {
    ConfigKey.LOGS__ENABLED: False
}
