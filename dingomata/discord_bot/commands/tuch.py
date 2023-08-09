from random import random, betavariate, choice

import lightbulb
import tortoise.transactions
from lightbulb import BotApp
from prettytable import PrettyTable
from tortoise import connections
from tortoise.functions import Sum

from dingomata.database.models import Tuch

plugin = lightbulb.Plugin('tuch')


@plugin.command
@lightbulb.command(name='tuch', description="Tuch some butts. You assume all risks.")
@lightbulb.implements(lightbulb.SlashCommand)
async def tuch(ctx: lightbulb.SlashContext) -> None:
    if random() < 0.95:
        number = int(betavariate(1.5, 3) * ctx.get_guild().member_count)
        await ctx.respond(f"{ctx.member.display_name} tuches {number} butts. So much floof!")
    else:
        number = 1
        await ctx.respond(
            f"{ctx.member.display_name} tuches {choice(ctx.get_channel().members).display_name}'s butt, " f"OwO"
        )
    async with tortoise.transactions.in_transaction() as tx:
        tuch, _ = await Tuch.get_or_create(guild_id=ctx.guild.id, user_id=ctx.author.id, using_db=tx)
        tuch.max_butts = max(tuch.max_butts, number)
        tuch.total_butts += number
        tuch.total_tuchs += 1
        await tuch.save(using_db=tx)


@plugin.command
@lightbulb.command(name='tuchboard', description="Show statistics about tuches.")
@lightbulb.implements(lightbulb.SlashCommand)
async def tuchboard(ctx: lightbulb.SlashContext) -> None:
    """Show statistics about tuches."""
    total_tuchs, total_butts = await Tuch.filter(guild_id=ctx.guild.id).annotate(
        total_tuchs=Sum("total_tuchs"), total_butts=Sum("total_butts"),
    ).first().values_list("total_tuchs", "total_butts")
    message = (
        f"Total butts tuched: {total_butts or 0:,}\n"
        f"Total number of times tuch was used: {total_tuchs or 0:,}\n"
        f"Total butts in server: {ctx.guild.member_count:,}\n"
    )
    # manual query bc no window function support
    query = """
    SELECT *
    FROM (
        SELECT user_id, max_butts, total_butts, rank() over (order by max_butts desc) as rank
        FROM tuch
        WHERE guild_id = $1
    ) a
    WHERE rank <= 10
    """

    connection = connections.get("default")
    data = await connection.execute_query_dict(query, [ctx.guild.id])
    table = PrettyTable()
    table.field_names = ("Rank", "User", "Max Butts", "Total Butts")
    table.align["Rank"] = "r"
    table.align["User"] = "l"
    table.align["Max Butts"] = "r"
    table.align["Total Butts"] = "r"
    for row in data:
        user = ctx.guild.get_member(row["user_id"])
        username = user.display_name if user else "Unknown User"
        table.add_row((row["rank"], username, row["max_butts"], row["total_butts"]))
    message += "```\n" + table.get_string() + "\n```"
    await ctx.respond(message)


def load(bot: BotApp):
    bot.add_plugin(plugin)


def unload(bot: BotApp):
    bot.remove_plugin(plugin)
