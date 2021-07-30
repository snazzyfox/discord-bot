import logging

import discord
from discord import Intents
from discord.ext import commands
from discord.ext.commands import Context, CheckFailure, CommandInvokeError

from dingomata.cog import DingomataCommands
from dingomata.config import get_config_value, ConfigurationKey
from dingomata.exceptions import DingomataUserError

log = logging.getLogger(__name__)
discord.VoiceClient.warn_nacl = False  # Disable warning for no voice support since it's a text bot

GUILD_ID = int(get_config_value(ConfigurationKey.SECURITY_SERVER_ID))
MOD_ROLE_IDS = {int(item) for item in get_config_value(ConfigurationKey.SECURITY_MOD_ROLE_IDS).split()}
MOD_CHANNEL_IDS = {int(item) for item in get_config_value(ConfigurationKey.SECURITY_MOD_CHANNEL_IDS).split()}

bot = commands.Bot(
    command_prefix=get_config_value(ConfigurationKey.BOT_COMMAND_PREFIX),
    intents=Intents(guilds=True, messages=True, dm_messages=True, typing=True, guild_reactions=True)
)
bot.add_cog(DingomataCommands(bot))


@bot.listen()
async def on_ready():
    log.info(f'Bot is ready.')


@bot.listen()
async def on_disconnect():
    log.info(f'Bot has disconnected.')


@bot.listen()
async def on_command_error(ctx: Context, exc: Exception):
    if isinstance(exc, CheckFailure):
        log.warning(f'Ignored a message from {ctx.author} in guild {ctx.guild or "DM"} '
                    f'because a check failed: {exc.args}')
    elif isinstance(exc, CommandInvokeError) and isinstance(exc.original, DingomataUserError):
        await ctx.reply(f"You can't do that. {exc.original}")
        log.warning(f'{exc.__class__.__name__}: {exc}')
    else:
        log.exception(exc)


@bot.before_invoke
async def log_command(ctx: Context) -> None:
    log.info(f'Received command {ctx.command} from {ctx.author} at {ctx.channel}')


@bot.check_once
async def check_guild(ctx: Context):
    if not ctx.guild:
        await ctx.send(f'You can only run this command from a server, not from DMs.')
        raise CheckFailure('Messaged received via DM.')
    if ctx.guild.id != GUILD_ID:
        await ctx.reply(f'You cannot use this bot in this server.')
        raise CheckFailure(f'Received message from server {ctx.guild}, which is not the server set in the config file.')
    return True


@bot.check_once
async def check_mod_permission(ctx: Context):
    if ctx.author.guild_permissions.administrator or any(role.id in MOD_ROLE_IDS for role in ctx.author.roles):
        return True
    else:
        await ctx.reply(f'You do not have permissions to do this. Bonk. This incident will be reported.')
        raise CheckFailure(f'Member {ctx.author} sent "{ctx.message.content}" in {ctx.channel}, but the user does not '
                           f'have any valid mod roles.')


@bot.check_once
async def check_mod_channel(ctx: Context):
    if ctx.channel.id in MOD_CHANNEL_IDS or not MOD_CHANNEL_IDS:
        return True
    else:
        await ctx.reply(f"You can't do that in this channel.")
        raise CheckFailure(f'Member {ctx.author} sent "{ctx.message.content} in {ctx.channel}, but bot messages are '
                           f'not allowed there.')
