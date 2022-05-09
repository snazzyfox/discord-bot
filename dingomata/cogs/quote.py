import re
from hashlib import md5

import discord
import tortoise.exceptions

from dingomata.decorators import message_command, slash, slash_group
from dingomata.exceptions import DingomataUserError

from ..models import Quote
from ..utils import Random
from .base import BaseCog


class QuoteCog(BaseCog):
    """Text commands."""

    _NEXT_BUTTON = "quote_next"
    _NON_ALPHANUM = re.compile(r"[^\w]")

    quotes = slash_group("quotes", "Manage quotes", config_group="quote")

    @quotes.command()
    @discord.option('user', description="Who said it?")
    @discord.option('content', description="What did they say?")
    async def add(self, ctx: discord.ApplicationContext, user: discord.User, content: str) -> None:
        """Add a new quote."""
        qid = await self._add_quote(ctx.guild, ctx.author, user, content)
        await ctx.respond(f"Quote has been added. New quote ID is {qid}.", ephemeral=True)

    @message_command(name="Add Quote", config_group="quote")
    async def add_quote_menu(self, ctx: discord.ApplicationContext, message: discord.Message) -> None:
        qid = await self._add_quote(ctx.guild, ctx.author, message.author, message.content)
        await ctx.respond(f"Quote has been added. New quote ID is {qid}.", ephemeral=True)

    async def _add_quote(
            self,
            guild: discord.Guild,
            source_user: discord.User,
            quoted_user: discord.User,
            content: str,
    ) -> int:
        if quoted_user == self._bot_for(guild.id).user:
            raise DingomataUserError("Don't quote me on that.")
        # Compute a digest of the quote message to prevent duplicates.
        digest = md5(self._NON_ALPHANUM.sub("", content.lower()).encode(), usedforsecurity=False).hexdigest()
        try:
            quote = await Quote.create(guild_id=guild.id, user_id=quoted_user.id, added_by=source_user.id,
                                       content=content, content_digest=digest)
            return quote.id
        except tortoise.exceptions.IntegrityError as e:
            raise DingomataUserError("This quote already exists.") from e

    @quotes.command()
    @discord.option('user', description="Find quotes by a particular user")
    @discord.option('search', description="Find quotes including this phrase")
    async def find(self, ctx: discord.ApplicationContext, user: discord.User = None, search: str = None) -> None:
        """Find existing quotes."""
        query = Quote.filter(guild_id=ctx.guild.id).limit(11)
        if user:
            query = query.filter(user_id=user.id)
        if search:
            query = query.filter(content__icontains=search.strip())

        results = await query
        if results:
            embed = discord.Embed()
            for quote in results[:10]:
                embed.add_field(name=f"[{quote.id}] {self._bot_for(ctx.guild.id).get_user(quote.user_id).display_name}",
                                value=quote.content, inline=False)
            if len(results) > 10:
                embed.description = "Only the first 10 quotes are displayed, but more are available. " \
                                    "Enter a more specific search query to find more quotes."
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("Your search found no quotes.", ephemeral=True)

    @quotes.command()
    @discord.option('quote_id', description="ID of quote to post")
    async def get(self, ctx: discord.ApplicationContext, quote_id: int) -> None:
        """Get a specific quote and post it publicly."""
        try:
            quote = await Quote.get(guild_id=ctx.guild.id, id=quote_id)
            user = self._bot_for(ctx.guild.id).get_user(quote.user_id)
            await ctx.respond(f"{user.display_name} said:\n>>> {quote.content}")
        except tortoise.exceptions.IntegrityError as e:
            raise DingomataUserError(f"Quote ID {quote_id} does not exist.") from e

    @quotes.command()
    @discord.option('quote_id', description="ID of quote to delete")
    async def delete(self, ctx: discord.ApplicationContext, quote_id: int) -> None:
        """Delete a quote."""
        deleted_count = await Quote.filter(guild_id=ctx.guild.id, id=quote_id).delete()
        if deleted_count:
            await ctx.respond(f"Deleted quote with ID {id}.", ephemeral=True)
        else:
            raise DingomataUserError(f"Quote ID {quote_id} does not exist.")

    @slash(cooldown=True)
    @discord.option('user', description="User to get quotes for")
    async def quote(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Print a random quote from a user."""
        quote = await self._get_quote(ctx.guild.id, user.id)
        await ctx.respond(f"{user.display_name} said: \n>>> " + quote)

    # ### Shortcut commands for specific servers
    @slash(cooldown=True, default_available=False)
    async def whiskey(self, ctx: discord.ApplicationContext) -> None:
        """What does the Dingo say?"""
        quote = await self._get_quote(ctx.guild.id, 178041504508542976)
        await ctx.respond(quote)

    @slash(cooldown=True, default_available=False)
    async def corgi(self, ctx: discord.ApplicationContext) -> None:
        quote = await self._get_quote(ctx.guild.id, 168916479306235914)
        await ctx.respond(quote)

    async def _get_quote(self, guild_id: int, user_id: int) -> str:
        quote = await Quote.filter(guild_id=guild_id, user_id=user_id).annotate(
            random=Random("id")).order_by("random").only("content").first()
        if quote:
            return quote.content
        else:
            raise DingomataUserError(f"{self._bot_for(guild_id).get_user(user_id).display_name} has no quotes.")
