import logging
from io import BytesIO

import hikari
import lightbulb
import petpetgif
import petpetgif.petpet

from snoozybot.exceptions import UserError
from snoozybot.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('petpet')


@plugin.command
@lightbulb.option("user", description="The user whose profile pic to get.", type=hikari.User)
@lightbulb.command("petpet", "Create a petpet image with anyone's profile image.")
@lightbulb.implements(lightbulb.SlashCommand)
async def petpet(ctx: lightbulb.SlashContext):
    # Get the user's pfp
    url: hikari.URL = ctx.options.user.display_avatar_url
    if not url:
        raise UserError(f'{ctx.options.user} does not seem to have a profile picture.')
    image_data = BytesIO(await url.read())
    output = BytesIO()
    petpetgif.petpet.make(image_data, output)
    output.seek(0)  # so it uploads
    await ctx.respond(attachment=output)


load, unload = plugin.export_extension()
