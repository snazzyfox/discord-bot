from typing import Optional

from discord import User, Guild, Embed
from discord.ext.commands import Bot, Cog, cooldown
from discord.ext.commands.cooldowns import BucketType
from discord_slash import SlashContext, ContextMenuType, MenuContext
from discord_slash.utils.manage_commands import create_option
from sqlalchemy import func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import QuoteModel, TextQuote
from ...decorators import slash, subcommand, context_menu, SubcommandBase
from ...exceptions import DingomataUserError


class QuoteCog(Cog, name='Quotes'):
    """Text commands."""
    _NEXT_BUTTON = 'quote_next'
    _BASE = SubcommandBase(name='quotes', group='quote', mod_only=True)

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(QuoteModel.metadata.create_all)

    @slash(name='whiskey', description="What does the Dingo say?", default_available=False, cooldown=True)
    async def whiskey(self, ctx: SlashContext) -> None:
        quote = await self._get_quote(178042794386915328, 178041504508542976)
        if quote is None:
            await ctx.reply('There are no quotes for this user.', hidden=True)
        else:
            await ctx.reply(quote)

    @slash(name='corgi', description="What does the Corgi say?", default_available=False, cooldown=True)
    async def corgi(self, ctx: SlashContext) -> None:
        quote = await self._get_quote(768208778780475447, 168916479306235914)
        if quote is None:
            await ctx.reply('There are no quotes for this user.', hidden=True)
        else:
            await ctx.reply(quote)

    @slash(name='quote', description="Get a quote from a user", group='quote', cooldown=True)
    async def quote(self, ctx: SlashContext, user: User) -> None:
        quote = await self._get_quote(ctx.guild.id, user.id)
        if quote is None:
            await ctx.reply('There are no quotes for this user.', hidden=True)
        else:
            await ctx.reply(f'{user.display_name} said: \n>>> ' + quote)

    async def _get_quote(self, guild_id: int, user_id: int) -> Optional[str]:
        async with self._session() as session:
            async with session.begin():
                stmt = select(TextQuote.content).filter(
                    TextQuote.guild_id == guild_id,
                    TextQuote.user_id == user_id
                ).order_by(func.random()).limit(1)
                quote = (await session.execute(stmt)).scalar()
                return quote

    @subcommand(name='add', description="Add a new quote",
                options=[
                    create_option(name='user', option_type=User, required=True, description='Who said it?'),
                    create_option(name='content', option_type=str, required=True, description='What did they say?'),
                ],
                base=_BASE,
                )
    async def add(self, ctx: SlashContext, user: User, content: str) -> None:
        qid = await self._quote_add(ctx.guild, ctx.author, user, content)
        await ctx.reply(f'Quote has been added. New quote ID is {qid}.', hidden=True)

    @context_menu(target=ContextMenuType.MESSAGE, name="Add Quote", group='quote', mod_only=True)
    async def add_menu(self, ctx: MenuContext) -> None:
        qid = await self._quote_add(ctx.guild, ctx.author, ctx.target_message.author, ctx.target_message.content)
        await ctx.send(f'Quote has been added. New quote ID is {qid}.', hidden=True)

    async def _quote_add(self, guild: Guild, source_user: User, quoted_user: User, content: str) -> int:
        if quoted_user == self._bot.user:
            raise DingomataUserError("Don't quote me on that.")
        async with self._session() as session:
            async with session.begin():
                quote = TextQuote(guild_id=guild.id, user_id=quoted_user.id, content=content.strip(),
                                  added_by=source_user.id)
                try:
                    session.add(quote)
                    await session.commit()
                    return quote.id
                except IntegrityError as e:
                    raise DingomataUserError("This quote already exists.") from e

    @subcommand(name='find', description="Find existing quotes",
                options=[
                    create_option(name='user', option_type=User, required=False,
                                  description='Find quotes by a particular user'),
                    create_option(name='search', option_type=str, required=False,
                                  description='Find quotes including this exact phrase'),
                ],
                base=_BASE
                )
    async def find(self, ctx: SlashContext, user: Optional[User] = None, search: Optional[str] = None) -> None:
        async with self._session() as session:
            async with session.begin():
                query = select(TextQuote).filter(TextQuote.guild_id == ctx.guild.id).order_by(TextQuote.id).limit(11)
                if user:
                    query = query.filter(TextQuote.user_id == user.id)
                if search and (phrase := search.strip().lower()):
                    query = query.filter(func.lower(TextQuote.content).contains(phrase, autoescape=True))
                results = (await session.execute(query)).scalars().all()
                if results:
                    embed = Embed()
                    for quote in results[:10]:
                        embed.add_field(
                            name=f'[{quote.id}] {self._bot.get_user(quote.user_id).display_name}',
                            value=quote.content, inline=False,
                        )

                    if len(results) > 10:
                        embed.description = (
                            'Only the first 10 quotes are displayed, but more are available. Enter a more specific '
                            'search query to find more quotes.')
                    await ctx.send(embed=embed, hidden=True)
                else:
                    await ctx.send(f'{user.display_name} has no quotes.', hidden=True)

    @subcommand(name='get', description="Get a specific quote and post it publicly.",
                options=[
                    create_option(name='quote_id', option_type=int, required=True,
                                  description='ID of quote to post'),
                ],
                base=_BASE,
                )
    async def get(self, ctx: SlashContext, quote_id: int) -> None:
        async with self._session() as session:
            async with session.begin():
                query = select(TextQuote).filter(TextQuote.guild_id == ctx.guild.id, TextQuote.id == quote_id)
                quote = (await session.execute(query)).scalar()
                if quote:
                    user = self._bot.get_user(quote.user_id)
                    await ctx.send(f'{user.display_name} said:\n>>> {quote.content}')
                else:
                    await ctx.send(f'Quote ID {quote_id} does not exist.', hidden=True)

    @subcommand(name='delete', description="Delete a quote by ID", base=_BASE,
                options=[create_option(name='id', option_type=int, required=True, description='Quote ID to delete')])
    async def delete(self, ctx: SlashContext, id: int) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = delete(TextQuote).filter(TextQuote.guild_id == ctx.guild.id, TextQuote.id == id)
                await session.execute(stmt)
                await session.commit()
        await ctx.reply(f'Deleted quote with ID {id}.', hidden=True)
