from discord import Role
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.utils.manage_commands import create_option
from parsedatetime import Calendar
from sqlalchemy.ext.asyncio import AsyncEngine

from dingomata.config import service_config
from dingomata.decorators import subcommand, SubcommandBase

_calendar = Calendar()


class RoleCommandsCog(Cog, name='Role Commands'):
    """Text commands."""
    _BASE = SubcommandBase(name='roles', default_available=False)

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot

    @subcommand(name='add', base=_BASE, description='Assign yourself a role in this server', options=[
        create_option(name='role', description='Which role to assign yourself', option_type=Role, required=True),
    ])
    async def add_role(self, ctx: SlashContext, role: Role):
        if role.id in service_config.servers[ctx.guild.id].roles.self_assignable_roles:
            await ctx.author.add_roles(role, reason='Requested via bot')
            await ctx.reply(f"You've been given the {role.name} role.", hidden=True)
        else:
            await ctx.reply(f"That's not a role you can change yourself. Please ask a moderator for help.", hidden=True)

    @subcommand(name='remove', base=_BASE, description='Remove a role from yourself in this server', options=[
        create_option(name='role', description='Which role to assign yourself', option_type=Role, required=True),
    ])
    async def remove_role(self, ctx: SlashContext, role: Role):
        if role.id in service_config.servers[ctx.guild.id].roles.self_assignable_roles:
            await ctx.author.remove_roles(role, reason='Requested via bot')
            await ctx.reply(f"You've been removed from the {role.name} role.", hidden=True)
        else:
            await ctx.reply(f"That's not a role you can change yourself. Please ask a moderator for help.", hidden=True)

    @subcommand(name='list', base=_BASE, description='Show the list of roles you can add yourself.')
    async def list_roles(self, ctx: SlashContext):
        roles = service_config.servers[ctx.guild.id].roles.self_assignable_roles
        if roles:
            await ctx.reply(f"You can assign yourself the following roles: \n" + '\n'.join(
                ctx.guild.get_role(role_id).mention for role_id in roles
            ), hidden=True)
        else:
            await ctx.reply(f"This server is not configured to allow self-adding any roles. Please speak to a "
                            f"moderator if you think this is wrong.", hidden=True)
