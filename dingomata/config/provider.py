import logging
import typing
from functools import cached_property

import pydantic
from async_lru import _LRUCacheWrapper, alru_cache
from pydantic import SecretStr

from ..database.models import Config

_CT = typing.TypeVar('_CT')
_CacheT = typing.TypeVar('_CacheT', bound=_LRUCacheWrapper)
_caches: list[_LRUCacheWrapper] = []
logger = logging.getLogger(__name__)


class ConfigValue(typing.Generic[_CT]):
    def __init__(self, key: str, default: _CT | None = None, has_specifier: bool = False):
        self._key = key
        self._default = default
        self._has_specifier = has_specifier

    def _full_key(self, specifier: str | None) -> str:
        if self._has_specifier and specifier is None:
            raise ValueError(f'Config key {self._key!r} must be used with a specifier.')
        elif not self._has_specifier and specifier is not None:
            raise ValueError(f'Config key {self._key!r} must be used without a specifier.')
        if specifier:
            return self._key + ':' + specifier
        else:
            return self._key

    @cached_property
    def _validator(self) -> pydantic.TypeAdapter:
        if not hasattr(self, '__orig_class__'):
            self.__orig_class__ = self.__class__[type(self._default)]  # type: ignore
        return pydantic.TypeAdapter(typing.get_args(self.__orig_class__)[0])

    @property
    def key(self) -> str:
        return self._key

    async def get_value(self, guild_id: int, specifier: str | None = None) -> _CT | None:
        key = self._full_key(specifier)
        stored_value: _CT = await get_config(guild_id, key)
        return stored_value if stored_value is not None else self._default

    async def set_value(self, guild_id: int, value: _CT | None = None, json: str = '',
                        specifier: str | None = None) -> None:
        key = self._full_key(specifier)
        if value:
            validated = self._validator.validate_python(value)
        else:
            validated = self._validator.validate_json(json)
        await Config.update_or_create({'config_value': validated}, guild_id=guild_id, config_key=key)
        # invalidate cache
        get_config.cache_invalidate(guild_id, key)


async def get_secret_configs(key: str) -> dict[int, SecretStr]:
    value = Config.filter(config_key=key).only('guild_id', 'config_value')
    return {row.guild_id: SecretStr(row.config_value) async for row in value}


@alru_cache(ttl=3600)
async def get_config(guild_id: int, key: str) -> typing.Any:
    value = await Config.get_or_none(guild_id=guild_id, config_key=key).only('config_value')
    if value is None:
        value = await Config.get_or_none(guild_id=0, config_key=key).only('config_value')
    logger.info('Read guild %s config %s from database.', guild_id, key)
    return value.config_value if value is not None else None


def cached_config(cached: _CacheT) -> _CacheT:
    """
    A decorator that registers a function (that uses alru_cache) as dependent on a cached config, so that it can be
    properly invalidated when a config needs to be invalidated due to user request.
    """
    global _caches
    _caches.append(cached)
    return cached


def clear_config_caches():
    get_config.cache_clear()
    for cache in _caches:
        logger.info('Clearing cache: %s, info %s', cache.__qualname__, cache.cache_info())
        cache.cache_clear()
