import logging

import discord
import tortoise.transactions
from tortoise import functions as func

from ..decorators import slash_group
from ..models import Collect
from ..utils import mention_if_needed
from .base import BaseCog

_log = logging.getLogger(__name__)


class CollectionCog(BaseCog):
    """Collect some cuties."""
    collection = slash_group("collection", "Collect some cuties!")

    @collection.command()
    @discord.option('user', description="Who to collect")
    async def add(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Collect a cutie!"""
        try:
            await Collect.create(guild_id=ctx.guild.id, user_id=ctx.author.id, target_user_id=user.id)
            count, = await Collect.filter(guild_id=ctx.guild.id, user_id=ctx.author.id).annotate(
                count=func.Count("target_user_id")).first().values_list("count")
            await ctx.respond(f"{ctx.author.display_name} collects {mention_if_needed(ctx, user)}. "
                              f"They now have {count} cutie(s) in their collection!")
        except tortoise.exceptions.IntegrityError:
            await ctx.respond(f"You have already collected {user.display_name}.", ephemeral=True)

    @collection.command()
    @discord.option('user', description="Who to discard")
    async def remove(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Remove a cutie from your collection D:"""
        deleted_count = await Collect.filter(
            guild_id=ctx.guild.id, user_id=ctx.author.id, target_user_id=user.id).delete()
        if deleted_count:
            await ctx.respond(
                f"{ctx.author.display_name} has removed {mention_if_needed(ctx, user)} from their collection.")
        else:
            await ctx.respond(f"{user.display_name} is not in your collection.", ephemeral=True)

    @collection.command()
    async def show(self, ctx: discord.ApplicationContext) -> None:
        """Show your collection to the world!"""
        collected = await Collect.filter(guild_id=ctx.guild.id, user_id=ctx.user.id).only("target_user_id")
        await ctx.respond(
            f"{ctx.author.display_name} has a collection of {len(collected)} cutie(s). "
            "Their collection includes: "
            + ", ".join(self._bot_for(ctx.guild.id).get_user(c.target_user_id).display_name for c in collected)
        )
