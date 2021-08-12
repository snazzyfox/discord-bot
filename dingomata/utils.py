from discord.ext.commands import Context


async def respond_done(ctx: Context) -> None:
    ctx.message.add_reaction('✅')
