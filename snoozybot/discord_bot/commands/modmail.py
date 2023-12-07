import hikari
import lightbulb

from snoozybot.config.values import report_channel_id, report_message
from snoozybot.exceptions import UserError
from snoozybot.utils import LightbulbPlugin

plugin = LightbulbPlugin('modmail')


@plugin.command
@lightbulb.option("comment", description="Any additional comments you would like to add", required=False)
@lightbulb.option("screenshot", description="A screenshot showing the user's unwanted behavior.",
                  type=hikari.Attachment)
@lightbulb.option("reason", description="Why you are reporting the user", choices=[
    "DM without consent (including scams)",
    "Unwanted behavior in DMs",
    "Inappropriate behavior in server",
    "Inappropriate behavior outside discord",
])
@lightbulb.option("user", description="The user you want to report", type=hikari.User)
@lightbulb.command("report", description="Report unwanted activity to server moderators privately",
                   ephemeral=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def report(ctx: lightbulb.ApplicationContext) -> None:
    channel_id = await report_channel_id.get_value(ctx.guild_id)
    if not channel_id:
        raise UserError('Sorry, this server was not set up to use this report command. Please get in touch with an '
                        'online moderator directly.')
    attachment: hikari.Attachment = ctx.options.screenshot
    if not attachment.media_type.startswith('image/'):
        raise UserError('The screenshot you uploaded does not appear to be a valid image. Please try again and make '
                        'sure to attach an image, preferably in PNG format).')
    log_channel: hikari.TextableChannel = ctx.get_guild().get_channel(channel_id)
    embed = hikari.Embed(
        title='User Report Received',
    )
    embed.add_field('Sent by', ctx.user.mention, inline=True)
    embed.add_field('Report against', ctx.options.user.mention, inline=True)
    embed.add_field('Reason', ctx.options.reason)
    embed.add_field('Additional comments', ctx.options.comment or '(None provided)')
    embed.set_image(ctx.options.screenshot)
    message = await report_message.get_value(ctx.guild_id)
    await log_channel.send(message, embed=embed, user_mentions=True, role_mentions=True)
    await ctx.respond('Thank you for filing a report and keeping the community safe! Your report has been sent to the '
                      'mods. They will review your report and take appropriate action. They may reach out to you '
                      'privately if they need more information.')


load, unload = plugin.export_extension()
