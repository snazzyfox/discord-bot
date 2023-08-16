from typing import Any

from async_lru import alru_cache
from pydantic import SecretStr

from ..database.models import Config
from ..exceptions import UserError
from .values import ConfigKey, SecretConfigKey, defaults


async def get_secret_configs(key: SecretConfigKey) -> dict[int, SecretStr]:
    value = Config.filter(config_key=key.value).only('guild_id', 'config_value')
    return {row.guild_id: SecretStr(row.config_value) async for row in value}


async def get_config(guild_id: int, key: ConfigKey, ident: str | None = None) -> Any:
    if key.value.startswith('secret.'):
        raise UserError("Shhh, that's a secret.")
    config_value = await _get_config(guild_id, key, ident)
    return config_value


@alru_cache(maxsize=256)
async def _get_config(guild_id: int, key: ConfigKey, ident: str | None = None) -> Any:
    """Gets the config value as stored in the database."""
    config_key = key.value
    if ident:
        config_key += ':' + ident
    value = await Config.get_or_none(guild_id=guild_id, config_key=config_key).only('config_value')
    if value is None:
        value = await Config.get_or_none(guild_id=0, config_key=config_key).only('config_value')
    return value.config_value if value is not None else defaults.get(key)
