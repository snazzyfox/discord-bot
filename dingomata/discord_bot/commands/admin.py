from copy import deepcopy

import lightbulb

from dingomata.config.provider import _get_config, get_config
from dingomata.config.values import ConfigKey
from dingomata.exceptions import UserError
from dingomata.utils import LightbulbPlugin

plugin = LightbulbPlugin('admin')


@plugin.command
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("admin", description="Commands for administration of the bot.")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def admin_group(ctx: lightbulb.SlashContext) -> None:
    pass


@admin_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("config", description="Commands for managing bot configs")
@lightbulb.implements(lightbulb.SlashSubGroup)
async def admin_config_group(ctx: lightbulb.SlashContext) -> None:
    pass


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("reload", description="Reload configs from database. This will NOT restart bots.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_reload(ctx: lightbulb.SlashContext) -> None:
    _get_config.cache_clear()
    await ctx.respond('All Done.')


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("key", description="The config key to get")
@lightbulb.option("specifier", description="The specifier for this config", default=None)
@lightbulb.command("get", description="Get a certain config value.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_get(ctx: lightbulb.SlashContext) -> None:
    try:
        key = ConfigKey(ctx.options.key)
        config_value = await get_config(ctx.guild_id, key, ctx.options.specifier)
        await ctx.respond(f'`{config_value}`')

    except KeyError:
        raise UserError("That's not a valid config key.")


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
