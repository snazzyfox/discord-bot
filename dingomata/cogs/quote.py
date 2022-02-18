import re
from hashlib import md5

import discord
import tortoise.exceptions

from dingomata.decorators import message_command, slash, slash_group
from dingomata.exceptions import DingomataUserError

from ..models import Quote
from ..utils import Random


class QuoteCog(discord.Cog):
    """Text commands."""

    _NEXT_BUTTON = "quote_next"
    _NON_ALPHANUM = re.compile(r"[^\w]")

    quotes = slash_group("quotes", "Manage quotes", mod_only=True, config_group="quote")

    def __init__(self, bot: discord.Bot):
        self._bot = bot

    @quotes.command()
    async def add(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who said it?"),
            content: discord.Option(str, "What did they say?"),
    ) -> None:
        """Add a new quote."""
        qid = await self._add_quote(ctx.guild, ctx.author, user, content)
        await ctx.respond(f"Quote has been added. New quote ID is {qid}.", ephemeral=True)

    @message_command(name="Add Quote", config_group="quote", mod_only=True)
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
        if quoted_user == self._bot.user:
            raise DingomataUserError("Don't quote me on that.")
        # Compute a digest of the quote message to prevent duplicates.
        digest = md5(self._NON_ALPHANUM.sub("", content.lower()).encode()).hexdigest()
        try:
            quote = await Quote.create(guild_id=guild.id, user_id=quoted_user.id, added_by=source_user.id,
                                       content=content, content_digest=digest)
            return quote.id
        except tortoise.exceptions.IntegrityError as e:
            raise DingomataUserError("This quote already exists.") from e

    @quotes.command()
    async def find(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Find quotes by a particular user", required=False) = None,
            search: discord.Option(str, "Find quotes including this phrase", required=False) = None,
    ) -> None:
        """Find existing quotes."""
        query = Quote.all().limit(11)
        if user:
            query = query.filter(user_id=user.id)
        if search:
            query = query.filter(content__icontains=search.strip())

        results = await query
        if results:
            embed = discord.Embed()
            for quote in results[:10]:
                embed.add_field(name=f"[{quote.id}] {self._bot.get_user(quote.user_id).display_name}",
                                value=quote.content, inline=False)
            if len(results) > 10:
                embed.description = "Only the first 10 quotes are displayed, but more are available. " \
                                    "Enter a more specific search query to find more quotes."
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond(f"{user.display_name} has no quotes.", ephemeral=True)

    @quotes.command()
    async def get(self, ctx: discord.ApplicationContext, quote_id: discord.Option(int, "ID of quote to post")) -> None:
        """Get a specific quote and post it publicly."""
        try:
            quote = await Quote.get(id=quote_id)
            user = self._bot.get_user(quote.user_id)
            await ctx.respond(f"{user.display_name} said:\n>>> {quote.content}")
        except tortoise.exceptions.IntegrityError as e:
            raise DingomataUserError(f"Quote ID {quote_id} does not exist.") from e

    @quotes.command()
    async def delete(
            self, ctx: discord.ApplicationContext, quote_id: discord.Option(int, "ID of quote to delete")
    ) -> None:
        """Delete a quote."""
        deleted_count = await Quote.filter(id=quote_id).delete()
        if deleted_count:
            await ctx.respond(f"Deleted quote with ID {id}.", ephemeral=True)
        else:
            raise DingomataUserError(f"Quote ID {quote_id} does not exist.")

    @slash(cooldown=True)
    async def quote(
            self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "User to get quotes for")
    ) -> None:
        """Print a random quote from a user."""
        quote = await self._get_quote(ctx.guild.id, user.id)
        await ctx.respond(f"{user.display_name} said: \n>>> " + quote)

    # ### Shortcut commands for specific servers
    @slash(cooldown=True, default_available=False)
    async def whiskey(self, ctx: discord.ApplicationContext) -> None:
        """What does the Dingo say?"""
        quote = await self._get_quote(178042794386915328, 178041504508542976)
        await ctx.respond(quote)

    @slash(cooldown=True, default_available=False)
    async def corgi(self, ctx: discord.ApplicationContext) -> None:
        quote = await self._get_quote(768208778780475447, 168916479306235914)
        await ctx.respond(quote)

    async def _get_quote(self, guild_id: int, user_id: int) -> str:
        quote = await Quote.filter(guild_id=guild_id, user_id=user_id).annotate(
            random=Random("id")).order_by("random").only("content").first()
        if quote:
            return quote.content
        else:
            raise DingomataUserError(f"{self._bot.get_user(user_id).display_name} has no quotes.")
