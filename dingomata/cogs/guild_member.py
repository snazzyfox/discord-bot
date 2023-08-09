import calendar
import logging
import re
from datetime import datetime
from typing import Any, Sequence

import discord
import pytz
import tortoise
from discord.ext.tasks import loop
from tortoise.exceptions import DoesNotExist

from dingomata.database.models import BotMessage, GuildMember, User
from dingomata.decorators import slash_group, slash_subgroup

from .._config import service_config
from ..exceptions import DingomataUserError
from ..utils import Random
from .base import BaseCog

_log = logging.getLogger(__name__)


class GuildMemberCog(BaseCog):
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

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self.birthday_reminder.start()

    def cog_unload(self) -> None:
        self.birthday_reminder.stop()

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
        next_birthday = await self._get_next_birthday_utc(ctx.user.id, month, day)
        await GuildMember.update_or_create({
            "birthday_month": month, "birthday_day": day, "next_birthday_utc": next_birthday,
        }, guild_id=ctx.guild.id, user_id=ctx.user.id)
        await ctx.respond("I have saved your birthday.", ephemeral=True)

    @remove.command(name="birthday")
    async def remove_birthday(self, ctx: discord.ApplicationContext) -> None:
        """Remove your birthday."""
        with tortoise.transactions.in_transaction() as tx:
            member = await GuildMember.select_for_update().using_db(tx).get_or_none(
                guild_id=ctx.guild.id, user_id=ctx.user.id)
            if member:
                member.birthday_month = None
                member.birthday_day = None
                member.next_birthday_utc = None
                await member.save(using_db=tx)
            await ctx.respond("I have removed your birthday.", ephemeral=True)

    @add.command(name="friendcode")
    @discord.option('service', description="Service or game this friend code is for",
                    autocomplete=discord.utils.basic_autocomplete(_FRIEND_CODE_SERVICES))
    @discord.option('code', description='Friend code you would like to add')
    async def add_friendcode(self, ctx: discord.ApplicationContext, service: str, code: str) -> None:
        """Add a new friend code."""
        await self._set_profile_field(ctx.guild, ctx.user, ('friendcode', service.strip()), code)
        await ctx.respond("Your friend code is saved.", ephemeral=True)

    @remove.command(name="friendcode")
    @discord.option('service', description="Service or game this friend code is for",
                    autocomplete=discord.utils.basic_autocomplete(_FRIEND_CODE_SERVICES))
    async def remove_friendcode(self, ctx: discord.ApplicationContext, service: str) -> None:
        """Removes a friend code."""
        await self._unset_profile_field(ctx.guild, ctx.user, ('friendcode', service.strip()))
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
        await self._set_profile_field(ctx.guild, ctx.user, ('refsheet', name.strip()), url)
        await ctx.respond("Your ref sheet is saved.", ephemeral=True)

    @remove.command(name="refsheet")
    @discord.option("name", description="Name for the ref sheet")
    async def remove_refsheet(self, ctx: discord.ApplicationContext, name: str) -> None:
        """Removes a ref sheet."""
        await self._unset_profile_field(ctx.guild, ctx.user, ('refsheet', name.strip()))
        await ctx.respond("All done! Your ref sheet is removed.", ephemeral=True)

    async def _set_profile_field(self, guild: discord.guild, user: discord.User, field: Sequence[str], value: Any):
        """Sets a field for a user."""
        # Update the relevant field
        async with tortoise.transactions.in_transaction() as tx:
            prof, _ = await GuildMember.get_or_create(guild_id=guild.id, user_id=user.id, defaults={'data': {}},
                                                      using_db=tx)
            self._recursive_set_dict(prof.profile_data, field, value)
            await prof.save(using_db=tx)
            await self._update_profile_embed(prof, tx)

    async def _unset_profile_field(self, guild: discord.guild, user: discord.User, field: Sequence[str]):
        """Removes a field for a user."""
        try:
            async with tortoise.transactions.in_transaction() as tx:
                prof = await GuildMember.select_for_update().using_db(tx).get(guild_id=guild.id, user_id=user.id)
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
            prof = await GuildMember.get(guild_id=ctx.guild.id, user_id=user.id)
            embed = self._generate_profile_embed(prof)
            await ctx.respond(embed=embed, ephemeral=True)
        except DoesNotExist:
            raise DingomataUserError(f'{user.display_name} does not have any profile information.')

    @profile.command()
    async def random(self, ctx: discord.ApplicationContext) -> None:
        """Privately get a random user's profile."""
        prof = await GuildMember.filter(guild_id=ctx.guild.id).annotate(
            random=Random("id")).order_by("random").limit(1).first()
        if prof:
            embed = self._generate_profile_embed(prof)
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            raise DingomataUserError("No one in this server has any profile information.")

    @profile.command()
    async def next_birthdays(self, ctx: discord.ApplicationContext) -> None:
        """Get the next few birthdays coming up in this server."""
        today = datetime.now(pytz.utc).replace(hour=0, minute=0, second=0)
        # Get profiles with birthday after today
        members = await GuildMember.filter(
            guild_id=ctx.guild.id,
            next_birthday_utc__gte=today,
        ).order_by('next_birthday_utc').limit(10)
        if not members:
            raise DingomataUserError('No one on this server has a birthday set.')
        else:
            embed = discord.Embed()
            for member in members:
                days_till_next = (member.next_birthday_utc - today).days
                if 0 <= days_till_next < 1:
                    relative_time = '**Today!**'
                else:
                    relative_time = f'in {days_till_next} days'
                embed.add_field(
                    name=ctx.guild.get_member(member.user_id).display_name,
                    value=f"{calendar.month_name[member.birthday_month]} {member.birthday_day} ({relative_time})",
                    inline=False,
                )
            await ctx.respond("Upcoming birthdays in this server: ", embed=embed)

    @profile.command()
    @discord.option('user', description="Whose profile to post. If not provided, your own profile will be posted.")
    async def post(self, ctx: discord.ApplicationContext, user: discord.User = None) -> None:
        """Post a user's profile in a channel. This post will not be updated if the user updates their
        profile in the future."""
        user = user or ctx.author
        try:
            prof = await GuildMember.get(guild_id=ctx.guild.id, user_id=user.id)
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
        if profile_channel_id := service_config.server[ctx.guild.id].member.profile_channel:
            channel = self._bot_for(ctx.guild.id).get_channel(profile_channel_id)
        else:
            raise DingomataUserError('This server is not configured for profiles. Please contact your discord_bot manager.')
        await ctx.defer(ephemeral=True)
        # Find all existing messages and delete them
        async with tortoise.transactions.in_transaction() as tx:
            messages = await BotMessage.select_for_update().using_db(tx).filter(
                id__startswith=f'{self._MSG_TYPE}:{ctx.guild.id}:').all()
            bot = self._bot_for(ctx.guild.id)
            for message in messages:
                try:
                    discord_message = bot.get_channel(message.channel_id).get_partial_message(message.message_id)
                    await discord_message.delete()
                except discord.NotFound:
                    pass
            await BotMessage.filter(id__startswith=f'{self._MSG_TYPE}:{ctx.guild.id}:').using_db(tx).delete()

            # Repost new messages for all members who have a profile
            all_profiles = await GuildMember.filter(guild_id=ctx.guild.id).using_db(tx).all()
            for prof in all_profiles:
                embed = self._generate_profile_embed(prof)
                if not embed:
                    continue
                message = await channel.send(embed=embed)
                bot_message = BotMessage(
                    id=f'{self._MSG_TYPE}:{ctx.guild.id}:{prof.user_id}',
                    channel_id=profile_channel_id,
                    message_id=message.id,
                )
                await bot_message.save(using_db=tx)
        await ctx.respond('All done!', ephemeral=True)

    @discord.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.display_name != after.display_name or before.display_avatar.key != after.display_avatar.key:
            if prof := await GuildMember.get_or_none(guild_id=after.guild.id, user_id=after.id):
                async with tortoise.transactions.in_transaction() as tx:
                    await self._update_profile_embed(prof, tx)

    async def _update_profile_embed(self, prof: GuildMember, tx) -> None:
        if profile_channel_id := service_config.server[prof.guild_id].member.profile_channel:
            channel = self._bot_for(prof.guild_id).get_channel(profile_channel_id)
        else:
            raise DingomataUserError('This server is not configured for profiles. Please contact your discord_bot manager.')
        bot_message = await BotMessage.select_for_update().using_db(tx).get_or_none(
            id=f'{self._MSG_TYPE}:{prof.guild_id}:{prof.user_id}')
        if prof.profile_data:
            embed = self._generate_profile_embed(prof)
            if bot_message:
                await channel.get_partial_message(bot_message.message_id).edit(embed=embed)
            else:
                message = await channel.send(embed=embed)
                bot_message = BotMessage(id=f'{self._MSG_TYPE}:{message.guild.id}:{prof.user_id}',
                                         channel_id=message.channel.id, message_id=message.id)
                await bot_message.save(using_db=tx)
        elif bot_message:
            # Profile data is empty - delete the existing message
            await channel.get_partial_message(bot_message.message_id).delete()
            await bot_message.delete()

    def _generate_profile_embed(self, prof: GuildMember) -> discord.Embed | None:
        user = self._bot_for(prof.guild_id).get_guild(prof.guild_id).get_member(prof.user_id)
        if not user:
            return None
        embed = discord.Embed(title=user.display_name)
        embed.set_thumbnail(url=user.display_avatar.url)
        if prof.birthday_month and prof.birthday_day:
            embed.add_field(name='Birthday', value=f'{calendar.month_name[prof.birthday_month]} {prof.birthday_day}',
                            inline=False)
        if codes := prof.profile_data.get('friendcode'):
            lines = '\n'.join(f'**{key}**: {value}' for key, value in codes.items())
            embed.add_field(name='Friend Codes', value=lines, inline=False)
        if refs := prof.profile_data.get('refsheet'):
            lines = '\n'.join(f'[{name}]({url})' for name, url in refs.items())
            embed.add_field(name='Ref Sheets', value=lines, inline=False)
            embed.set_image(url=next(iter(refs.values())))
        return embed

    def _recursive_set_dict(self, d: dict, keys: Sequence[str], value: Any):
        if len(keys) == 1:
            d[keys[0]] = value
        else:
            d = d.setdefault(keys[0], {})
            self._recursive_set_dict(d, keys[1:], value)

    def _recursive_del_dict(self, d: dict, keys: Sequence[str]):
        if len(keys) == 1:
            del d[keys[0]]
        else:
            self._recursive_del_dict(d[keys[0]], keys[1:])
            if not d[keys[0]]:
                del d[keys[0]]

    @staticmethod
    async def _get_next_birthday_utc(user_id: int, month: int, day: int) -> datetime:
        # Get current date in user's timezone
        user = await User.get_or_none(user_id=user_id)
        if not user or not user.timezone:
            raise DingomataUserError("You have not set a timezone for yourself. Please set a timezone with /timezone "
                                     "first so I can properly understand your birthday.")
        tz = pytz.timezone(user.timezone)
        today = datetime.now(tz)
        # Determine if next birthday is in current year or next year
        if today.month > month or (today.month == month and today.day >= day):
            next_birthday_year = today.year + 1
        else:
            next_birthday_year = today.year
        birthday_local = tz.normalize(tz.localize(datetime(next_birthday_year, month, day)))
        # Convert back to utc
        birthday_utc = birthday_local.astimezone(pytz.utc)
        return birthday_utc

    # Automatic Birthday Notification
    @loop(hours=1)
    async def birthday_reminder(self):
        async with tortoise.transactions.in_transaction() as tx:
            members = GuildMember.select_for_update().using_db(tx).filter(
                guild_id__in=[guild.id for guild in self._bot.guilds],
                next_birthday_utc__lte=datetime.now(pytz.utc),
            )
            async for member in members:
                guild = self._bot.get_guild(member.guild_id)
                user = guild.get_member(member.user_id)
                if service_config.server[member.guild_id].member.birthday_channel:
                    channel = guild.get_channel(service_config.server[member.guild_id].member.birthday_channel)
                    try:
                        member.next_birthday_utc = await self._get_next_birthday_utc(
                            member.user_id, member.birthday_month, member.birthday_day)
                        await channel.send(f"🎂 **Happy birthday, {user.mention}!** 🎂")
                    except DingomataUserError:
                        _log.warning(f'Birthday: did not send birthday note for {member} '
                                     'because they do not have a timezone.')
                    except discord.HTTPException:
                        _log.exception(f'Birthday: Failed to send birthday message for {member}.')
                await member.save(using_db=tx)
