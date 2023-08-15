import logging
import hikari
import lightbulb

from dingomata.config.provider import get_config
from dingomata.config.values import ConfigKey

log = logging.getLogger(__name__)


#
#
# class View(discord.ui.View):
#     async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
#         if isinstance(error, DingomataUserError):
#             await interaction.response.send_message(f"Error: {error}", ephemeral=True)
#             log.warning(f"{error.__class__.__name__}: {error}")
#         else:
#             await super(View, self).on_error(error, item, interaction)


async def mention_if_needed(ctx: lightbulb.ApplicationContext, member: hikari.Member) -> str:
    """Return a user's mention string, or display name if they're in the no-ping list"""
    no_pings: list[int] = await get_config(ctx.guild_id, ConfigKey.ROLES__NO_PINGS)
    if member and member.id in no_pings or any(role in no_pings for role in member.role_ids):
        return member.display_name
    else:
        return member.mention
