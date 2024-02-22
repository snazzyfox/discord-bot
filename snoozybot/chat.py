import google.generativeai as genai
from openai import AsyncOpenAI

from snoozybot.config.provider import get_secret_configs

_openai_clients: dict[int, AsyncOpenAI] = {}


async def start():
    openai_keys = await get_secret_configs('secret.openai.apikey')
    for guild, api_key in openai_keys.items():
        chat_client = AsyncOpenAI(api_key=api_key.get_secret_value())
        _openai_clients[guild] = chat_client
    gemini_keys = await get_secret_configs('secret.gemini.apikey')
    genai.configure(api_key=next(iter(gemini_keys.values())).get_secret_value())


async def stop():
    for chat_client in _openai_clients.values():
        await chat_client.close()


def get_openai(guild_id: int) -> AsyncOpenAI:
    return _openai_clients[guild_id]
