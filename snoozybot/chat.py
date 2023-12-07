from openai import AsyncOpenAI

from snoozybot.config.provider import get_secret_configs

chat_client: AsyncOpenAI = None


async def start():
    global chat_client
    openai_config = await get_secret_configs('secret.openai.apikey')
    api_key_secret = next(iter(openai_config.values()), None)
    chat_client = AsyncOpenAI(api_key=api_key_secret.get_secret_value() if api_key_secret else '')


async def stop():
    await chat_client.close()
