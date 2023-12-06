import lightbulb

from snoozybot.config import provider, values
from snoozybot.exceptions import UserError
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('admin')

all_configs = [v for v in values.__dict__.values() if
               isinstance(v, values.ConfigValue) and not v.key.startswith('secret.')]


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
    provider.clear_config_caches()
    await ctx.respond('All Done.')


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("specifier", description="The specifier for this config", default=None)
@lightbulb.option("key", description="The config key to get")
@lightbulb.command("get", description="Get a certain config value.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_get(ctx: lightbulb.SlashContext) -> None:
    key = next((c for c in all_configs if c.key == ctx.options.key), None)
    if key is None:
        raise UserError("That's not a valid config key.")
    try:
        config_value = await key.get_value(ctx.guild_id, ctx.options.specifier)
        config_str = str(config_value)
        if len(config_str) > 1997:
            raise UserError("This config value is too long to be displayed via Discord. Edit it manually.")
    except ValueError as e:
        raise UserError(str(e))
    await ctx.respond(f'`{config_str}`')


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("value", description="The value to set for this config")
@lightbulb.option("specifier", description="The specifier for this config", default=None)
@lightbulb.option("key", description="The config key to set")
@lightbulb.command("set", description="Set a certain config value.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_set(ctx: lightbulb.SlashContext) -> None:
    key = next((c for c in all_configs if c.key == ctx.options.key), None)
    if key is None:
        raise UserError("That's not a valid config key.")
    try:
        await key.set_value(ctx.guild_id, json=ctx.options.value, specifier=ctx.options.specifier)
    except ValueError as e:
        raise UserError("That's not a valid value for this config: " + str(e))
    await ctx.respond("Config value set.")


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("value", description="The value to set for this config")
@lightbulb.option("specifier", description="The specifier for this config", default=None)
@lightbulb.option("key", description="The config key to set")
@lightbulb.command("append", description="Append a value to a list config.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_append(ctx: lightbulb.SlashContext) -> None:
    key = next((c for c in all_configs if c.key == ctx.options.key), None)
    if key is None:
        raise UserError("That's not a valid config key.")
    try:
        value = await key.get_value(ctx.guild_id, ctx.options.specifier)
    except ValueError:
        # Config doesn't exist
        value = []
    if not isinstance(value, list):
        raise UserError("This config value is not a list type. Use \"set\" instead.")
    value.append(ctx.options.value)
    try:
        await key.set_value(ctx.guild_id, value=value, specifier=ctx.options.specifier)
    except ValueError as e:
        raise UserError("That's not a valid value for this config: " + str(e))
    await ctx.respond("Config value set.")


@admin_config_group.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("list", description="List all configs.", ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def admin_config_list(ctx: lightbulb.SlashContext) -> None:
    await ctx.respond('\n'.join('- ' + conf.key for conf in all_configs))


load, unload = plugin.export_extension()
