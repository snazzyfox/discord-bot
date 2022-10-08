import calendar
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

import discord
import tortoise
from tortoise.exceptions import DoesNotExist

from dingomata.decorators import slash_group, slash_subgroup

from ..config import service_config
from ..exceptions import DingomataUserError
from ..models import BotMessages, Profile
from ..utils import Random
from .base import BaseCog

_log = logging.getLogger(__name__)


class ProfileCog(BaseCog):
    """Let users set their own profile info to be displayed in server."""

    _MSG_TYPE = 'PROFILE'
    _DISCORD_IMAGE_URL = re.compile(
        r'https://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/\d+/\d+/.*\.(?:jpg|png|webp|gif)', re.IGNORECASE)
    _FRIEND_CODE_SERVICES = ['Steam', 'Nintendo Switch', 'Pokemon Go', 'Playstation Network', 'Epic Games', 'XBox',
                             'Genshin Impact']
    _MONTHS = [discord.OptionChoice(name=f'{i:02} - {calendar.month_name[i]}', value=i) for i in range(1, 13)]
    profile_admin = slash_group("profile_admin", "Manage profile cards", config_group="profile",
                                default_available=False)
    profile = slash_group("profile", "View and manage your own profile", default_available=False)
    add = slash_subgroup(profile, "add", "Add information displayed in your profile")
    remove = slash_subgroup(profile, "remove", "Remove information displayed in your profile")

    # PROFILE EDITING
    @add.command(name="birthday")
    @discord.option('month', description="Month of the birthday", choices=_MONTHS)
    @discord.option('day', description="Day of the birthday", min_value=1, max_value=31)
    async def add_birthday(self, ctx: discord.ApplicationContext, month: int, day: int) -> None:
        """Set your birthday."""
        # Test if the birthday is valid
        try:
            datetime(year=2000, month=month, day=day)
        except ValueError:
            raise DingomataUserError(f'{month}/{day} is not a valid date.')
        await self._set_profile_field(ctx.guild, ctx.author, ('birthday',), [month, day])
        await ctx.respond("Your birthday has been updated.", ephemeral=True)

    @remove.command(name="birthday")
    async def remove_birthday(self, ctx: discord.ApplicationContext) -> None:
        """Remove your birthday."""
        await self._unset_profile_field(ctx.guild, ctx.author, ('birthday',))
        await ctx.respond("I have removed your birthday.", ephemeral=True)

    @add.command(name="friendcode")
    @discord.option('service', description="Service or game this friend code is for",
                    autocomplete=discord.utils.basic_autocomplete(_FRIEND_CODE_SERVICES))
    @discord.option('code', description='Friend code you would like to add')
    async def add_friendcode(self, ctx: discord.ApplicationContext, service: str, code: str) -> None:
        """Add a new friend code."""
        await self._set_profile_field(ctx.guild, ctx.author, ('friendcode', service.strip()), code)
        await ctx.respond("Your friend code is saved.", ephemeral=True)

    @remove.command(name="friendcode")
    @discord.option('service', description="Service or game this friend code is for",
                    autocomplete=discord.utils.basic_autocomplete(_FRIEND_CODE_SERVICES))
    async def remove_friendcode(self, ctx: discord.ApplicationContext, service: str) -> None:
        """Removes a friend code."""
        await self._unset_profile_field(ctx.guild, ctx.author, ('friendcode', service.strip()))
        await ctx.respond("Your friend code has been removed.", ephemeral=True)

    @add.command(name="refsheet")
    @discord.option("name", description="Name for the ref sheet. If this name already exists, "
                                        "it will replace the existing one.")
    @discord.option("url", description="An image URL posted on Discord of the ref sheet")
    async def add_refsheet(self, ctx: discord.ApplicationContext, name: str, url: str) -> None:
        """Add a new ref sheet"""
        if not self._DISCORD_IMAGE_URL.match(url):
            raise DingomataUserError(
                "The URL does not look like a Discord image attachment. Please make sure it's an image uploaded to "
                "Discord, not a link to a message, or an image from an outside source.")
        await self._set_profile_field(ctx.guild, ctx.author, ('refsheet', name.strip()), url)
        await ctx.respond("Your ref sheet is saved.", ephemeral=True)

    @remove.command(name="refsheet")
    @discord.option("name", description="Name for the ref sheet")
    async def remove_refsheet(self, ctx: discord.ApplicationContext, name: str) -> None:
        """Removes a ref sheet."""
        await self._unset_profile_field(ctx.guild, ctx.author, ('refsheet', name.strip()))
        await ctx.respond("All done! Your ref sheet is removed.", ephemeral=True)

    async def _set_profile_field(self, guild: discord.guild, user: discord.User, field: Sequence[str], value: Any):
        """Sets a field for a user."""
        # Update the relevant field
        async with tortoise.transactions.in_transaction() as tx:
            prof, _ = await Profile.get_or_create(guild_id=guild.id, user_id=user.id, defaults={'data': {}},
                                                  using_db=tx)
            self._recursive_set_dict(prof.data, field, value)
            await prof.save(using_db=tx)
            await self._update_profile_embed(prof, tx)

    async def _unset_profile_field(self, guild: discord.guild, user: discord.User, field: Sequence[str]):
        """Removes a field for a user."""
        try:
            async with tortoise.transactions.in_transaction() as tx:
                prof = await Profile.select_for_update().using_db(tx).get(guild_id=guild.id, user_id=user.id)
                self._recursive_del_dict(prof.data, field)
                if prof.data:
                    await prof.save(using_db=tx)
                else:
                    # Delete the profile entirely if there's no data left
                    await prof.delete(using_db=tx)
                await self._update_profile_embed(prof, tx)
        except (KeyError, DoesNotExist):
            raise DingomataUserError('You do not have that particular profile item. Your profile was not changed.')

    # PROFILE PRINTING
    @profile.command()
    @discord.option('user', description="Whose profile to get. If not provided, views your own profile.")
    async def get(self, ctx: discord.ApplicationContext, user: discord.User = None) -> None:
        """Privately view a profile card."""
        user = user or ctx.author
        try:
            prof = await Profile.get(guild_id=ctx.guild.id, user_id=user.id)
            embed = self._generate_profile_embed(prof)
            await ctx.respond(embed=embed, ephemeral=True)
        except DoesNotExist:
            raise DingomataUserError(f'{user.display_name} does not have any profile information.')

    @profile.command()
    async def random(self, ctx: discord.ApplicationContext) -> None:
        """Privately get a random user's profile."""
        prof = await Profile.filter(guild_id=ctx.guild.id).annotate(
            random=Random("id")).order_by("random").limit(1).first()
        if prof:
            embed = self._generate_profile_embed(prof)
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            raise DingomataUserError("No one in this server has any profile information.")

    @profile.command()
    @discord.option('user', description="Whose profile to post. If not provided, your own profile will be posted.")
    async def post(self, ctx: discord.ApplicationContext, user: discord.User = None) -> None:
        """Post a user's profile in a channel. This post will not be updated if the user updates their
        profile in the future."""
        user = user or ctx.author
        try:
            prof = await Profile.get(guild_id=ctx.guild.id, user_id=user.id)
            embed = self._generate_profile_embed(prof)
            await ctx.respond(embed=embed)
        except DoesNotExist:
            raise DingomataUserError(f'{user.display_name} does not have any profile information.')

    @profile_admin.command()
    @discord.option('confirm', description="Type 'yes' to confirm.")
    async def repost_all(self, ctx: discord.ApplicationContext, confirm: str) -> None:
        """Delete all existing posts (if any), and repost them in the designated channel."""
        if not confirm == 'yes':
            raise DingomataUserError('You must enter "yes" after the command to confirm this operation. Any data '
                                     'deleted will not be recoverable.')
        if profile_channel_id := service_config.server[ctx.guild.id].profile.channel:
            channel = self._bot_for(ctx.guild.id).get_channel(profile_channel_id)
        else:
            raise DingomataUserError('This server is not configured for profiles. Please contact your bot manager.')
        await ctx.defer(ephemeral=True)
        # Find all existing messages and delete them
        async with tortoise.transactions.in_transaction() as tx:
            messages = await BotMessages.select_for_update().using_db(tx).filter(
                id__startswith=f'{self._MSG_TYPE}:{ctx.guild.id}:').all()
            bot = self._bot_for(ctx.guild.id)
            for message in messages:
                try:
                    discord_message = bot.get_channel(message.channel_id).get_partial_message(message.message_id)
                    await discord_message.delete()
                except discord.NotFound:
                    pass
            await BotMessages.filter(id__startswith=f'{self._MSG_TYPE}:{ctx.guild.id}:').using_db(tx).delete()

            # Repost new messages for all members who have a profile
            all_profiles = await Profile.filter(guild_id=ctx.guild.id).using_db(tx).all()
            for prof in all_profiles:
                embed = self._generate_profile_embed(prof)
                if not embed:
                    continue
                message = await channel.send(embed=embed)
                bot_message = BotMessages(
                    id=f'{self._MSG_TYPE}:{ctx.guild.id}:{prof.user_id}',
                    channel_id=profile_channel_id,
                    message_id=message.id,
                )
                await bot_message.save(using_db=tx)

    @discord.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.display_name != after.display_name or before.display_avatar.key != after.display_avatar.key:
            if prof := await Profile.get_or_none(guild_id=after.guild.id, user_id=after.id):
                async with tortoise.transactions.in_transaction() as tx:
                    await self._update_profile_embed(prof, tx)

    async def _update_profile_embed(self, prof: Profile, tx) -> None:
        if profile_channel_id := service_config.server[prof.guild_id].profile.channel:
            channel = self._bot_for(prof.guild_id).get_channel(profile_channel_id)
        else:
            raise DingomataUserError('This server is not configured for profiles. Please contact your bot manager.')
        bot_message = await BotMessages.select_for_update().using_db(tx).get_or_none(
            id=f'{self._MSG_TYPE}:{prof.guild_id}:{prof.user_id}')
        if prof.data:
            embed = self._generate_profile_embed(prof)
            if bot_message:
                await channel.get_partial_message(bot_message.message_id).edit(embed=embed)
            else:
                message = await channel.send(embed=embed)
                bot_message = BotMessages(id=f'{self._MSG_TYPE}:{message.guild.id}:{prof.user_id}',
                                          channel_id=message.channel.id, message_id=message.id)
                await bot_message.save(using_db=tx)
        elif bot_message:
            # Profile data is empty - delete the existing message
            await channel.get_partial_message(bot_message.message_id).delete()
            await bot_message.delete()

    def _generate_profile_embed(self, prof: Profile) -> Optional[discord.Embed]:
        user = self._bot_for(prof.guild_id).get_guild(prof.guild_id).get_member(prof.user_id)
        if not user:
            return None
        embed = discord.Embed(title=user.display_name)
        embed.set_thumbnail(url=user.display_avatar.url)
        if bday := prof.data.get('birthday'):
            month, day = bday
            embed.add_field(name='Birthday', value=f'{calendar.month_name[month]} {day}', inline=False)
        if codes := prof.data.get('friendcode'):
            line_len = max(len(key) for key in codes)
            lines = '\n'.join(f'{key:{line_len}} {value}' for key, value in codes.items())
            embed.add_field(name='Friend Codes', value=f'```\n{lines}\n```', inline=False)
        if refs := prof.data.get('refsheet'):
            lines = '\n'.join(f'[{name}]({url})' for name, url in refs.items())
            embed.add_field(name='Ref Sheets', value=lines, inline=False)
            embed.set_image(url=next(iter(refs.values())))
        return embed

    def _recursive_set_dict(self, d: Dict, keys: Sequence[str], value: Any):
        if len(keys) == 1:
            d[keys[0]] = value
        else:
            d = d.setdefault(keys[0], {})
            self._recursive_set_dict(d, keys[1:], value)

    def _recursive_del_dict(self, d: Dict, keys: Sequence[str]):
        if len(keys) == 1:
            del d[keys[0]]
        else:
            self._recursive_del_dict(d[keys[0]], keys[1:])
            if not d[keys[0]]:
                del d[keys[0]]
