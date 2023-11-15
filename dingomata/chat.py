from openai import AsyncOpenAI

from dingomata.config.provider import get_secret_configs

chat_client: AsyncOpenAI = None


async def start():
    global chat_client
    openai_config = await get_secret_configs('secret.openai.apikey')
    chat_client = AsyncOpenAI(api_key=next(iter(openai_config.values())).get_secret_value())


async def stop():
    await chat_client.close()
