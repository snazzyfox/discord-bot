from openai import AsyncOpenAI

from snoozybot.config.provider import get_secret_configs

_chat_clients: dict[int, AsyncOpenAI] = {}


async def start():
    api_keys = await get_secret_configs('secret.openai.apikey')
    for guild, api_key in api_keys.items():
        chat_client = AsyncOpenAI(api_key=api_key.get_secret_value())
        _chat_clients[guild] = chat_client


async def stop():
    for chat_client in _chat_clients.values():
        await chat_client.close()


def get_openai(guild_id: int) -> AsyncOpenAI:
    return _chat_clients[guild_id]
