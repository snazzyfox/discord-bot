import discord

from .tree import tree


@tree.command()
async def ping(ctx: discord.Interaction):
    await ctx.response.send_message("pong")
