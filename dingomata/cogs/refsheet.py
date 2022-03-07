import logging
import re
from itertools import groupby
from typing import List

import discord
import tortoise.exceptions

from dingomata.decorators import slash_group
from dingomata.exceptions import DingomataUserError

from ..models import RefSheet, RefSheetMessages
from ..utils import Random

_log = logging.getLogger(__name__)


class RefSheetCog(discord.Cog):
    """Ref sheet list."""

    _DISCORD_IMAGE_URL = re.compile(
        r'https://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/\d+/\d+/.*\.(?:jpg|png|webp|gif)', re.IGNORECASE)
    ref_admin = slash_group("ref_admin", "Manage ref sheets", mod_only=True, config_group="ref",
                            default_available=False)
    ref = slash_group("ref", "Manage and look at ref sheets", default_available=False)

    def __init__(self, bot: discord.Bot):
        self._bot = bot

    @ref.command()
    async def get(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, description="Whose ref to get", required=True),
            id_: discord.Option(int, name='id', description="Which specific ref to get", required=False, default=None),
    ) -> None:
        """Get someone's ref sheet."""
        query = RefSheet.filter(guild_id=ctx.guild.id, user_id=user.id)
        if id_:
            query = query.filter(id=id_)
        refs = await query.all()
        await self._send_get_response(ctx, refs)

    @ref.command()
    async def random(self, ctx: discord.ApplicationContext) -> None:
        """Get a random ref sheet from a user on this server."""
        result = await RefSheet.filter(guild_id=ctx.guild.id).annotate(
            random=Random("id")).order_by("random").limit(1).all()
        await self._send_get_response(ctx, result)

    async def _send_get_response(self, ctx: discord.ApplicationContext, refs: List[RefSheet]) -> None:
        if not refs:
            raise DingomataUserError('There are no ref sheets matching your query.')
        embeds = [self._make_ref_embed(ctx, ref) for ref in refs]
        await ctx.respond(embeds=embeds, ephemeral=True)

    @staticmethod
    def _make_ref_embed(ctx: discord.ApplicationContext, ref: RefSheet) -> discord.Embed:
        ref_user = ctx.guild.get_member(ref.user_id)
        title = f'#{ref.id} - {ref_user.display_name if ref_user else ref.user_id}'
        if ref.name:
            title += f' ({ref.name})'
        embed = discord.Embed(title=title).set_image(url=ref.url)
        return embed

    @ref.command()
    async def add(
            self,
            ctx: discord.ApplicationContext,
            url: discord.Option(str, description="URL to your ref sheet. Must be an image URL posted on Discord."),
            name: discord.Option(str, description="Name for this ref sheet", required=False),
    ) -> None:
        """Add a new ref sheet for yourself."""
        return await self._add_ref(ctx, ctx.user, url, name)

    @ref_admin.command(name="add")
    async def admin_add(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, description="User to add ref sheet for"),
            url: discord.Option(str, description="URL to your ref sheet. Must be an image URL posted on Discord."),
            name: discord.Option(str, description="Name for this ref sheet", required=False),
    ) -> None:
        """Add a new ref sheet for a given user."""
        return await self._add_ref(ctx, user, url, name)

    async def _add_ref(self, ctx: discord.ApplicationContext, user: discord.User, url: str, name: str) -> None:
        # Check that the URL is a discord image embed - disallow other sources bc they can get deleted or changed.
        if not self._DISCORD_IMAGE_URL.match(url):
            raise DingomataUserError(
                "The URL does not look like a Discord image attachment. Please make sure it's an image uploaded to "
                "Discord, not a link to a message, or an image from an outside source.")
        if len(name) > 32:
            raise DingomataUserError("Your character's name is too powerful! Please keep it under 32 letters.")
        # Limit 10 refs per user - max number of images per message
        existing_image_count = await RefSheet.filter(guild_id=ctx.guild.id, user_id=user.id).count()
        if existing_image_count >= 10:
            raise DingomataUserError(
                "This user already has 10 ref sheets. Due to Discord limitations we can only store 10 refs per user. "
                "Please remove one before adding more.")
        # Actually add the ref
        try:
            ref = await RefSheet.create(guild_id=ctx.guild.id, user_id=user.id, added_by=ctx.user.id, url=url,
                                        name=name)
        except tortoise.exceptions.IntegrityError:
            raise DingomataUserError("This ref sheet has already been added.")
        await ctx.respond(f"Your ref has been added! Its ID is {ref.id}", ephemeral=True)
        await self._update_list(ctx)

    @ref.command()
    async def remove(
            self,
            ctx: discord.ApplicationContext,
            id_: discord.Option(int, name="id", description="Which specific ref to delete"),
    ) -> None:
        """Remove one of your own ref sheets."""
        ref = await RefSheet.get_or_none(guild_id=ctx.guild.id, id=id_)
        if not ref:
            raise DingomataUserError("There is no ref sheet with that ID.")
        elif ref.user_id != ctx.user.id:
            raise DingomataUserError("You cannot delete that ref because it doesn't belong to you.")
        await ref.delete()
        await ctx.respond("This ref has been removed.", ephemeral=True)
        await self._update_list(ctx)

    @ref_admin.command(name="remove")
    async def admin_remove(
            self,
            ctx: discord.ApplicationContext,
            id_: discord.Option(int, name="id", description="Which specific ref to delete"),
    ) -> None:
        """Remove a ref sheet."""
        ref = await RefSheet.get_or_none(guild_id=ctx.guild.id, id=id_)
        if not ref:
            raise DingomataUserError("There is no ref sheet with that ID.")
        await ref.delete()
        await ctx.respond("This ref has been removed.", ephemeral=True)
        await self._update_list(ctx)

    @ref_admin.command()
    async def post_list(self, ctx: discord.ApplicationContext) -> None:
        """Post a list of all refs on this server. Deletes the existing list if there is one."""
        # Delete the existing message if there is one
        async with tortoise.transactions.in_transaction() as tx:
            old_messages = await RefSheetMessages.filter(guild_id=ctx.guild.id).all()
            for msg in old_messages:
                try:
                    channel = ctx.guild.get_channel(msg.channel_id)
                    message = channel.get_partial_message(msg.message_id)
                    await message.delete()
                    await msg.delete(tx)
                except (discord.NotFound, discord.Forbidden):
                    pass  # don't worry if the channel or message is gone
            embeds = await self._make_list_embeds(ctx)
            for i, embed in enumerate(embeds):
                new_message = await ctx.channel.send(embed=embed)
                print(i, new_message.id)
                msg = RefSheetMessages(
                    guild_id=ctx.guild.id,
                    message_seq_num=i,
                    channel_id=new_message.channel.id,
                    message_id=new_message.id,
                )
                await msg.save(using_db=tx)
            await ctx.respond('All done!', ephemeral=True)

    async def _update_list(self, ctx: discord.ApplicationContext) -> None:
        messages = await RefSheetMessages.filter(guild_id=ctx.guild.id).order_by('message_seq_num').all()
        if messages:
            embeds = await self._make_list_embeds(ctx)
            if len(messages) != len(embeds):
                await ctx.send("The total number of pages needed to display the ref list has changed. Please ask a "
                               "moderator to regenerate the list.")
                return
            for msg, embed in zip(messages, embeds):
                try:
                    channel = ctx.guild.get_channel(msg.channel_id)
                    message = channel.get_partial_message(msg.message_id)
                    await message.edit(embed=embed)
                except (discord.NotFound, discord.Forbidden) as e:
                    _log.warning("Failed to edit message for ref sheet list: " + str(e))

    @staticmethod
    async def _make_list_embeds(ctx: discord.ApplicationContext) -> List[discord.Embed]:
        # Write the new list
        refs = await RefSheet.filter(guild_id=ctx.guild.id).order_by("user_id").all()
        lines = []
        for user_id, refs in groupby(refs, key=lambda ref: ref.user_id):
            user = ctx.guild.get_member(user_id)
            links = ', '.join(f'[{ref.name or ("Unnamed" + str(i + 1))}]({ref.url})' for i, ref in enumerate(refs))
            lines.append(f'{user.display_name if user else user_id} {links}')
        lines.sort()  # by username instead of id

        # Divide the lines into groups of 4096 bytes (max size per embed)
        embed_chunks = []
        chunk = ''
        for line in lines:
            if len(line) + len(chunk) + 1 >= 4096:  # extra 1 for linebreak
                embed_chunks.append(chunk)
                chunk = line
            else:
                chunk += '\n' + line
        embed_chunks.append(chunk)

        # Turn them into embeds
        embeds = [discord.Embed(description=chunk) for chunk in embed_chunks]
        embeds[0].title = 'Table of Cuties'
        return embeds