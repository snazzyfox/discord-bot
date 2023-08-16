from copy import deepcopy

import lightbulb

from dingomata.config.provider import _get_config
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('admin')


@plugin.command
@lightbulb.command("admin", description="Commands for administration of the bot.")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def admin_group(ctx: lightbulb.SlashContext) -> None:
    pass


@admin_group.child
@lightbulb.command("config", description="Commands for managing bot configs")
@lightbulb.implements(lightbulb.SlashSubGroup)
async def admin_config_group(ctx: lightbulb.SlashContext) -> None:
    pass


@admin_config_group.child
@lightbulb.command("reload", description="Reload configs from database. This will NOT restart bots.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_reload(ctx: lightbulb.SlashContext) -> None:
    _get_config.cache_clear()
    await ctx.respond('All Done.')


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
