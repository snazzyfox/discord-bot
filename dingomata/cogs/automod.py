import logging
import re
from typing import Set

import discord
from unidecode import unidecode

from dingomata.config.bot import service_config
from dingomata.decorators import slash_group

_log = logging.getLogger(__name__)


class AutomodCog(discord.Cog):
    """Message filtering."""

    _URL_REGEX = re.compile(r"\bhttps?://(?!twitch\.tv/|tenor\.com/view/|youtube\.com/|youtu\.be/)")
    _SCAM_KEYWORD_REGEX = re.compile(r"\b(?:free gift(?:s|ed)?|nitro|subscription)", re.IGNORECASE)

    roles = slash_group(name="roles", description="Add or remove roles for yourself.")

    def __init__(self, bot: discord.Bot):
        self._bot = bot

        #: Message IDs that are already being deleted - skip to avoid double posting
        self._processing_message_ids: Set[int] = set()

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._check_likely_discord_scam(message)

    @discord.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self._check_likely_discord_scam(after)

    async def _check_likely_discord_scam(self, message: discord.Message):
        if message.id in self._processing_message_ids or not message.guild:
            return  # It's already in the process of being deleted.
        reasons = []
        if message.guild.default_role.mention in message.content or "@everyone" in message.content:
            reasons.append("Mentions at-everone")
        if bool(self._URL_REGEX.search(message.content)):
            reasons.append("Includes URL")
        if match := self._SCAM_KEYWORD_REGEX.search(unidecode(message.content)):
            reasons.append(f"Message content includes scam keyword(s): {match.group()}")
        if match := self._search_embeds(self._SCAM_KEYWORD_REGEX, message):
            reasons.append(f"Embed content includes scam keyword(s): {match.group()}")

        if len(reasons) >= 2 and not self._is_mod(message.author):
            # Consider the message scam likely if two matches
            self._processing_message_ids.add(message.id)
            _log.info(
                f"Detected message from {message.author} as scam. Reason: {reasons}. "
                f"Original message: {message.content}"
            )
            log_channel = service_config.server[message.guild.id].automod.log_channel
            actions = []

            mute_role = service_config.server[message.guild.id].roles.mute
            if mute_role:
                _log.info(f"Added role {mute_role} to {message.author}")
                try:
                    role = message.guild.get_role(mute_role)
                    await message.author.add_roles(role, reason="Scam message detected.")
                    actions.append(f"Added role {role.mention}")
                except Exception as e:
                    _log.exception(e)

            try:
                await message.delete()
                actions.append("Deleted message")
            except Exception as e:
                _log.exception(e)
                actions.append(f"Failed to delete message: {e}")

            if log_channel:
                embed = discord.Embed(title="Scam message detected.")
                embed.add_field(name="User", value=message.author.mention, inline=True)
                embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                embed.add_field(name="Reason(s)", value="\n".join(reasons), inline=False)
                embed.add_field(name="Action(s) taken", value="\n".join(actions), inline=False)
                embed.add_field(name="Original Message", value=message.content, inline=False)
                await self._bot.get_channel(log_channel).send(
                    content=service_config.server[message.guild.id].automod.text_prefix,
                    embed=embed,
                )
            self._processing_message_ids.discard(message.id)

    @staticmethod
    def _search_embeds(regex: re.Pattern, message: discord.Message):
        matches = (
            (embed.title and regex.search(unidecode(embed.title)))
            or (embed.description and regex.search(unidecode(embed.description)))
            for embed in message.embeds
        )
        return next(matches, None)

    @staticmethod
    def _is_mod(user: discord.Member):
        guild = user.guild.id
        return any(role.id in service_config.server[guild].roles.mods for role in user.roles)

    @roles.command()
    async def add(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Role to add")) -> None:
        """Assign yourself a role in this server"""
        if role.id in service_config.server[ctx.guild.id].roles.self_assign:
            await ctx.author.add_roles(role, reason="Requested via bot")
            await ctx.respond(f"You've been given the {role.name} role.", ephemeral=True)
        else:
            await ctx.respond("You cannot change that role yourself. Please ask a moderator for help.", ephemeral=True)

    @roles.command()
    async def remove(
            self,
            ctx: discord.ApplicationContext,
            role: discord.Option(discord.Role, "Role to remove"),
    ) -> None:
        """Remove a role from yourself in this server"""
        if role.id in service_config.server[ctx.guild.id].roles.self_assignable_roles:
            await ctx.author.remove_roles(role, reason="Requested via bot")
            await ctx.respond(f"You've been removed from the {role.name} role.", ephemeral=True)
        else:
            await ctx.respond("You cannot change that role yourself. Please ask a moderator for help.", ephemeral=True)

    @roles.command()
    async def list_roles(self, ctx: discord.ApplicationContext):
        """Show the list of roles you can add yourself."""
        roles = service_config.server[ctx.guild.id].roles.self_assignable_roles
        if roles:
            await ctx.respond(
                "You can assign yourself the following roles: \n"
                + "\n".join(ctx.guild.get_role(role_id).mention for role_id in roles),
                ephemeral=True,
            )
        else:
            await ctx.respond(
                "This server is not configured to allow self-adding any roles. Please speak to a "
                "moderator if you think this is wrong.",
                ephemeral=True,
            )
