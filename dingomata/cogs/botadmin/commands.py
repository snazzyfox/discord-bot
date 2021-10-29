import logging

from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.utils.manage_commands import create_option
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...decorators import slash
from ...exceptions import DingomataUserError

_log = logging.getLogger(__name__)


class BotAdmin(Cog, name='Bot Admin'):
    """Remind users to go to bed."""

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @slash(name='echo', default_available=False, mod_only=True, options=[
        create_option(name='channel', option_type=str, description='Channel ID', required=True),
        create_option(name='message', option_type=str, description='Message', required=True),
    ])
    async def echo(self, ctx: SlashContext, channel: str, message: str):
        ch = self._bot.get_channel(int(channel))
        if not ch:
            raise DingomataUserError('Channel ID invalid.')
        else:
            await ch.send(message)
            await ctx.reply('Done', hidden=True)
