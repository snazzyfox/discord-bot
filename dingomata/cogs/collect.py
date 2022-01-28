import logging

import discord
import tortoise.transactions
from tortoise import functions as func

from ..decorators import slash
from ..models import Collect
from ..utils import mention_if_needed

_log = logging.getLogger(__name__)


class CollectCog(discord.Cog):
    """Collect some cuties."""

    def __init__(self, bot: discord.Bot):
        self._bot = bot

    @slash(cooldown=True)
    async def collect(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to collect"),
    ) -> None:
        try:
            await Collect.create(guild_id=ctx.guild.id, user_id=ctx.author.id, target_user_id=user.id)
            count = await Collect.filter(guild_id=ctx.guild.id, user_id=ctx.author.id).annotate(
                count=func.Count("target_user_id")).only("count").first().values_list()
            await ctx.respond(f"{ctx.author.display_name} collects {mention_if_needed(ctx, user)}. "
                              f"They now have {count} cutie(s) in their collection!")
        except tortoise.exceptions.IntegrityError:
            await ctx.respond(f"You have already collected {user.display_name}.", ephemeral=True)

    @slash(cooldown=True)
    async def discard(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to collect"),
    ) -> None:
        """Remove a cutie from your collection D:"""
        deleted_count = await Collect.filter(
            guild_id=ctx.guild.id, user_id=ctx.author.id, target_user_id=user.id).delete()
        if deleted_count:
            await ctx.respond(
                f"{ctx.author.display_name} has removed {mention_if_needed(ctx, user)} from their collection.")
        else:
            await ctx.respond(f"{user.display_name} is not in your collection.", ephemeral=True)

    @slash(cooldown=True)
    async def collection(self, ctx: discord.ApplicationContext) -> None:
        """Show your collection to the world!"""
        collected = await Collect.filter(guild_id=ctx.guild.id, user_id=ctx.user.id).only("target_user_id")
        await ctx.respond(
            f"{ctx.author.display_name} has a collection of {len(collected)} cutie(s). "
            "Their collection includes: "
            + ", ".join(self._bot.get_user(c.target_user_id).display_name for c in collected)
        )
