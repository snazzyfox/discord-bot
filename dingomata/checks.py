from discord.ext.commands import Context, CheckFailure, check

from dingomata.config import get_guild_config, has_guild_config


def check_role():
    async def predicate(ctx: Context) -> bool:
        roles = get_guild_config(ctx.guild.id)
        if ctx.author.guild_permissions.administrator or any(role.id in roles for role in ctx.author.roles):
            return True
        else:
            await ctx.reply(f'You do not have permissions to do this. Bonk. This incident will be reported.')
            raise CheckFailure(f'Member {ctx.author} sent "{ctx.message.content}" in {ctx.channel}, but the user does '
                               f'not have the necessary roles.')

    return check(predicate)
#
#
# def check_channel(configKey: GuildConfigKey):
#     async def predicate(ctx: Context) -> bool:
#         channel_ids = get_split_id(ctx.guild.id, configKey)
#         if ctx.channel.id in channel_ids or not channel_ids:
#             return True
#         else:
#             await ctx.reply(f"You can't do that in this channel.")
#             raise CheckFailure(f'Member {ctx.author} sent "{ctx.message.content} in {ctx.channel}, but that command '
#                                f'cannot be used there.')
#
#     return check(predicate)


async def check_guild(ctx: Context) -> bool:
    if has_guild_config(ctx.guild.id):
        return True
    else:
        raise CheckFailure(f'Ignoring message from server {ctx.guild} because it\'s not one of the configured servers.')
