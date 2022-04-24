from os import environ
from sys import argv

import discord
from dotenv import load_dotenv

load_dotenv(environ.get('ENV_FILE', '.env'))
client = discord.Client()


async def send_message(channel_id: int, message: str):
    await client.wait_until_ready()
    channel = client.get_channel(channel_id)
    await channel.send(message)
    await client.close()


client.loop.create_task(send_message(int(argv[1]), argv[2]))
client.run(environ['TOKEN'])
