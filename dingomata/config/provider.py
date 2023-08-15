from typing import Any

import hikari
from async_lru import alru_cache
from pydantic import SecretStr

from ..database.models import Config
from ..exceptions import UserError
from .values import ConfigKey, SecretConfigKey, defaults


def _guild_id_of(guildable: hikari.Guild | int | None) -> int:
    if isinstance(guildable, hikari.Guild):
        return guildable.id
    elif isinstance(guildable, int):
        return guildable
    elif guildable is None:
        return 0


async def get_secret_config(key: SecretConfigKey) -> dict[int, SecretStr]:
    value = Config.filter(config_key=key.value).only('guild_id', 'config_value')
    return {row.guild_id: SecretStr(row.config_value) async for row in value}


async def get_config(guild: hikari.Guild | int | None, key: ConfigKey) -> Any:
    guild_id = _guild_id_of(guild)
    config_value = await _get_config(guild_id, key)

    if key.startswith('secret.'):
        raise UserError("Shhh, that's a secret.")
    else:
        return config_value


@alru_cache(maxsize=256)
async def _get_config(guild_id: int, key: ConfigKey) -> Any:
    """Gets the config value as stored in the database as a string."""
    value = await Config.get_or_none(guild_id=guild_id, config_key=key.value).only('config_value')
    return value.config_value if value else defaults.get(key)

# async def set_config(guild: _Guildable | discord.Guild | int | None,
#                      key: str,
#                      value: str | int | list[str] | list[int],
#                      mode: Literal['append', 'replace']) -> None:
#     guild_id = _guild_id_of(guild)
#     match mode:
#         case 'append':
#
#         case 'replace':
