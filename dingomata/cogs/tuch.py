import logging
from random import betavariate, choice, random

import discord
import tortoise.transactions
from prettytable import PrettyTable
from tortoise import functions as func

from ..decorators import slash
from ..models import Tuch
from .base import BaseCog

_log = logging.getLogger(__name__)


class TuchCog(BaseCog):
    """Tuch some butts."""

    @slash(cooldown=True)
    async def tuch(self, ctx: discord.ApplicationContext) -> None:
        """Tuch some butts. You assume all risks."""
        if random() < 0.95:
            number = int(betavariate(1.5, 3) * ctx.guild.member_count)
            await ctx.respond(f"{ctx.author.display_name} tuches {number} butts. So much floof!")
        else:
            number = 1
            await ctx.respond(
                f"{ctx.author.display_name} tuches {choice(ctx.channel.members).display_name}'s butt, " f"OwO"
            )
        async with tortoise.transactions.in_transaction() as tx:
            tuch, _ = await Tuch.get_or_create(guild_id=ctx.guild.id, user_id=ctx.author.id, using_db=tx)
            tuch.max_butts = max(tuch.max_butts, number)
            tuch.total_butts += number
            tuch.total_tuchs += 1
            await tuch.save(using_db=tx)

    @slash(config_group="tuch", cooldown=True)
    async def tuchboard(self, ctx: discord.ApplicationContext) -> None:
        """Show statistics about tuches."""
        total_tuchs, total_butts = await Tuch.filter(guild_id=ctx.guild.id).annotate(
            total_tuchs=func.Sum("total_tuchs"), total_butts=func.Sum("total_butts"),
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

        conn = tortoise.Tortoise.get_connection("default")
        data = await conn.execute_query_dict(query, [ctx.guild.id])
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
