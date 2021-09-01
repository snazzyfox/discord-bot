from typing import Optional

from discord import User, Guild, Embed
from discord.ext.commands import Bot, Cog, cooldown
from discord.ext.commands.cooldowns import BucketType
from discord_slash import SlashContext, ContextMenuType, MenuContext
from discord_slash.cog_ext import cog_slash, cog_context_menu, cog_subcommand
from discord_slash.utils.manage_commands import create_option
from sqlalchemy import func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import QuoteModel, TextQuote
from ...config import get_guilds, get_mod_permissions
from ...exceptions import DingomataUserError

_BASE_MOD_COMMAND = dict(base='quotes', guild_ids=get_guilds(), base_default_permission=False)


class QuoteCog(Cog, name='Quotes'):
    """Text commands."""
    _NEXT_BUTTON = 'quote_next'

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @Cog.listener()
    async def on_ready(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(QuoteModel.metadata.create_all)

    @cog_slash(name='whiskey', description="What does the Dingo say?", guild_ids=[178042794386915328])
    @cooldown(1, 5.0, BucketType.member)
    async def whiskey(self, ctx: SlashContext) -> None:
        quote = await self._get_quote(178042794386915328, 178041504508542976)
        if quote is None:
            await ctx.reply('There are no quotes for this user.', hidden=True)
        else:
            await ctx.reply(quote)

    @cog_slash(name='quote', description="Get a quote from a user", guild_ids=get_guilds())
    @cooldown(1, 5.0, BucketType.member)
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

    @cog_subcommand(name='add', description="Add a new quote",
                    options=[
                        create_option(name='user', option_type=User, required=True, description='Who said it?'),
                        create_option(name='content', option_type=str, required=True, description='What did they say?'),
                    ],
                    **_BASE_MOD_COMMAND,
                    )
    async def add(self, ctx: SlashContext, user: User, content: str) -> None:
        qid = await self._quote_add(ctx.guild, ctx.author, user, content)
        await ctx.reply(f'Quote has been added. New quote ID is {qid}.', hidden=True)

    @cog_context_menu(target=ContextMenuType.MESSAGE, name="Add Quote", guild_ids=get_guilds(),
                      default_permission=False, permissions=get_mod_permissions())
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

    @cog_subcommand(name='find', description="Find existing quotes",
                    options=[
                        create_option(name='user', option_type=User, required=False,
                                      description='Find quotes by a particular user'),
                        create_option(name='search', option_type=str, required=False,
                                      description='Find quotes including this exact phrase'),
                    ],
                    **_BASE_MOD_COMMAND,
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
                    await ctx.send(f'{user.display_name} has no quotes.')

    @cog_subcommand(name='delete', description="Delete a quote by ID",
                    options=[
                        create_option(name='id', option_type=int, required=True, description='Quote ID to delete'),
                    ],
                    base_permissions=get_mod_permissions(),
                    **_BASE_MOD_COMMAND,
                    )
    async def delete(self, ctx: SlashContext, id: int) -> None:
        async with self._session() as session:
            async with session.begin():
                stmt = delete(TextQuote).filter(TextQuote.guild_id == ctx.guild.id, TextQuote.id == id)
                await session.execute(stmt)
                await session.commit()
        await ctx.reply(f'Deleted quote with ID {id}.', hidden=True)
