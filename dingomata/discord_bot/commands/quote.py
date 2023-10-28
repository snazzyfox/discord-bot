import re
from hashlib import md5

import hikari
import lightbulb
import tortoise

from dingomata.database.fields import Random
from dingomata.database.models import Quote
from dingomata.exceptions import UserError
from dingomata.utils import CooldownManager, LightbulbPlugin, UserGuildBucket

plugin = LightbulbPlugin('quote')
_NON_ALPHANUM = re.compile(r"\W")


@plugin.command
@lightbulb.add_checks(lightbulb.has_role_permissions(hikari.Permissions.MANAGE_MESSAGES))
@lightbulb.command("quotes", description="Manage quotes")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def quotes_group(ctx: lightbulb.ApplicationContext) -> None:
    pass


@quotes_group.child
@lightbulb.option("content", description="What did they say?")
@lightbulb.option("user", description="Who said it?", type=hikari.Member)
@lightbulb.command("add", description="Add a new quote", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def quotes_add(ctx: lightbulb.SlashContext) -> None:
    qid = await _add_quote(ctx, ctx.options.user, ctx.options.content)
    await ctx.respond(f"Quote has been added. New quote ID is {qid}.")


@plugin.command
@lightbulb.command("Add Quote", description="Add this as a new quote", ephemeral=True)
@lightbulb.implements(lightbulb.MessageCommand)
async def quotes_add_context_menu(ctx: lightbulb.MessageContext) -> None:
    message: hikari.PartialMessage = ctx.options.target
    qid = await _add_quote(ctx, message.author, message.content)
    await ctx.respond(f"Quote has been added. New quote ID is {qid}.")


async def _add_quote(ctx: lightbulb.ApplicationContext, quoted_user: hikari.User, content: str) -> int:
    if quoted_user == ctx.bot.get_me():
        raise UserError("Don't quote me on that.")
    # Compute a digest of the quote message to prevent duplicates.
    digest = md5(_NON_ALPHANUM.sub("", content.lower()).encode(), usedforsecurity=False).hexdigest()
    try:
        quote = await Quote.create(guild_id=ctx.guild_id, user_id=quoted_user.id, added_by=ctx.author.id,
                                   content=content, content_digest=digest)
        return quote.id
    except tortoise.exceptions.IntegrityError as e:
        raise UserError("This quote already exists.") from e


@quotes_group.child
@lightbulb.option("user", description="Find quotes by a particular user", type=hikari.Member, default=None)
@lightbulb.option("search", description="Find quotes including this phrase", default=None)
@lightbulb.command("find", description="Find existing quotes.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def quotes_find(ctx: lightbulb.SlashContext) -> None:
    """Find existing quotes."""
    query = Quote.filter(guild_id=ctx.guild_id).limit(11)
    if ctx.options.user:
        query = query.filter(user_id=ctx.options.user.id)
    if ctx.options.search:
        query = query.filter(content__icontains=ctx.options.search.strip())

    results = await query
    if results:
        embed = hikari.Embed()
        for quote in results[:10]:
            embed.add_field(name=f"[{quote.id}] {ctx.get_guild().get_member(quote.user_id).display_name}",
                            value=quote.content, inline=False)
        if len(results) > 10:
            embed.description = "Only the first 10 quotes are displayed, but more are available. " \
                                "Enter a more specific search query to find more quotes."
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("Your search found no quotes.")


@quotes_group.child
@lightbulb.option("quote_id", description="ID of quote to post", type=int)
@lightbulb.command("get", description="Get a specific quote by ID and post it publicly.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def quotes_get(ctx: lightbulb.SlashContext) -> None:
    try:
        quote = await Quote.get(guild_id=ctx.guild_id, id=ctx.options.quote_id)
        user = ctx.get_guild().get_member(quote.user_id)
        await ctx.respond(f"{user.display_name} said:\n>>> {quote.content}")
    except tortoise.exceptions.DoesNotExist as e:
        raise UserError(f"Quote ID {ctx.options.quote_id} does not exist.") from e


@quotes_group.child
@lightbulb.option("quote_id", description="ID of quote to post", type=int)
@lightbulb.command("delete", description="Delete a quote by ID.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def delete(ctx: lightbulb.SlashContext) -> None:
    deleted_count = await Quote.filter(guild_id=ctx.guild_id, id=ctx.options.quote_id).delete()
    if deleted_count:
        await ctx.respond(f"Deleted quote with ID {ctx.options.quote_id}.")
    else:
        raise UserError(f"Quote ID {ctx.options.quote_id} does not exist.")


@plugin.command
@lightbulb.add_cooldown(10, 2, UserGuildBucket, cls=CooldownManager)
@lightbulb.option("user", description="User to get quotes for", type=hikari.Member)
@lightbulb.command("quote", description="Get a random quote for someone.")
@lightbulb.implements(lightbulb.SlashCommand)
async def quote(ctx: lightbulb.SlashContext) -> None:
    quote = await _get_quote(ctx.guild_id, ctx.options.user.id)
    name = ctx.options.user.display_name if isinstance(ctx.options.user, hikari.Member) else ctx.options.user.username
    await ctx.respond(f"{name} said: \n>>> " + quote)


# ### Shortcut commands for specific servers
@plugin.command
@lightbulb.add_cooldown(10, 2, UserGuildBucket, cls=CooldownManager)
@lightbulb.command("whiskey", description="What does the dingo say?", guilds=(178042794386915328,))
@lightbulb.implements(lightbulb.SlashCommand)
async def quote_whiskey(ctx: lightbulb.SlashContext) -> None:
    quote = await _get_quote(ctx.guild_id, 178041504508542976)
    await ctx.respond(quote)


@plugin.command
@lightbulb.add_cooldown(10, 2, UserGuildBucket, cls=CooldownManager)
@lightbulb.command("corgi", description="What does the corgi say?", guilds=(768208778780475447,))
@lightbulb.implements(lightbulb.SlashCommand)
async def quote_corgi(ctx: lightbulb.SlashContext) -> None:
    quote = await _get_quote(ctx.guild_id, 168916479306235914)
    await ctx.respond(quote)


async def _get_quote(guild_id: int, user_id: int) -> str:
    quote = await Quote.filter(guild_id=guild_id, user_id=user_id).annotate(
        random=Random("id")).order_by("random").only("content").first()
    if quote:
        return quote.content
    else:
        raise UserError("This user has no quotes.")

load, unload = plugin.export_extension()
