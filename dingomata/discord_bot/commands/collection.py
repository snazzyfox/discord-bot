import hikari
import lightbulb
import tortoise.transactions
from tortoise.functions import Count

from dingomata.database.models import Collect
from dingomata.utils import LightbulbPlugin, mention_if_needed

plugin = LightbulbPlugin('collection')


@plugin.command
@lightbulb.command("collection", description="Collect some cuties!")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def collection_group(ctx: lightbulb.SlashContext) -> None:
    pass


@collection_group.child
@lightbulb.option("user", description="Who to collect", type=hikari.Member)
@lightbulb.command("add", description="Collect a cutie!")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def collection_add(ctx: lightbulb.SlashContext) -> None:
    if ctx.options.user.id == ctx.bot.get_me().id:
        await Collect.filter(guild_id=ctx.guild_id, user_id=ctx.author.id).delete()
        await ctx.respond(f"{ctx.member.display_name} collects {ctx.options.user.display_name}. Unfortunately, they "
                          f"forgor to unplug the bot, who overheats and catches the shelf on fire. The entire "
                          f"collection is engulfed in flames.")
    else:
        try:
            await Collect.create(guild_id=ctx.guild_id, user_id=ctx.author.id, target_user_id=ctx.options.user.id)
            count, = await Collect.filter(guild_id=ctx.guild_id, user_id=ctx.author.id).annotate(
                count=Count("target_user_id")).first().values_list("count")
            await ctx.respond(f"{ctx.member.display_name} collects {await mention_if_needed(ctx, ctx.options.user)}. "
                              f"They now have {count} cutie(s) in their collection!")
        except tortoise.exceptions.IntegrityError:
            await ctx.respond(f"You have already collected {ctx.options.user.display_name}.",
                              flags=hikari.MessageFlag.EPHEMERAL)


@collection_group.child
@lightbulb.option('user', description="Who to discard", type=hikari.Member)
@lightbulb.command("remove", description="Remove a cutie from your collection D:")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def collection_remove(ctx: lightbulb.SlashContext) -> None:
    deleted_count = await Collect.filter(
        guild_id=ctx.guild_id, user_id=ctx.author.id, target_user_id=ctx.options.user.id).delete()
    if deleted_count:
        await ctx.respond(
            f"{ctx.member.display_name} has removed {await mention_if_needed(ctx, ctx.options.user)} "
            f"from their collection.")
    else:
        await ctx.respond(f"{ctx.options.user.display_name} is not in your collection.",
                          flags=hikari.MessageFlag.EPHEMERAL)


@collection_group.child
@lightbulb.command("show", description="Show your collection to the world!")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def collection_show(ctx: lightbulb.SlashContext) -> None:
    collected = await Collect.filter(guild_id=ctx.guild_id, user_id=ctx.user.id).only("target_user_id")
    guild = ctx.get_guild()
    collected_users = (guild.get_member(c.target_user_id) for c in collected)
    if len(collected):
        await ctx.respond(
            f"{ctx.member.display_name} has a collection of {len(collected)} cutie(s). "
            "Their collection includes: "
            + ", ".join(c.display_name for c in collected_users if c)
        )
    else:
        await ctx.respond(
            f"{ctx.member.display_name} doesn't have a collection of cutie(s). Better late than never!"
        )

load, unload = plugin.export_extension()
