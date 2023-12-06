import tortoise

from ..config.env import envConfig
from . import models


async def start():
    await tortoise.Tortoise.init(
        modules={"models": [models]},
        db_url=envConfig.database_url.get_secret_value(),
    )
    await tortoise.Tortoise.generate_schemas()


async def stop():
    await tortoise.Tortoise.close_connections()
