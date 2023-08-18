import logging
from copy import deepcopy
from datetime import datetime

import hikari
import lightbulb
import tortoise.transactions
from lightbulb.ext import tasks
from parsedatetime import parsedatetime

from dingomata.database.models import ScheduledTask, TaskType
from dingomata.exceptions import UserError
from dingomata.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('reminder')
_calendar = parsedatetime.Calendar()


@plugin.command
@lightbulb.command("reminder", description="Remind me about something later.")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def reminder_group(ctx: lightbulb.SlashContext) -> None:
    pass


@reminder_group.child
@lightbulb.add_checks(lightbulb.bot_has_guild_permissions(hikari.Permissions.SEND_MESSAGES))
@lightbulb.option("about", description="What I should remind you about.")
@lightbulb.option("time", description="How much later you want the reminder. For example, 10 minutes or 2 days.")
@lightbulb.command(
    "set",
    description="Set a new reminder. I'll send you a reminder in this channel around the time you ask for.",
    ephemeral=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def reminder_set(ctx: lightbulb.SlashContext) -> None:
    time, parse_status = _calendar.parseDT(ctx.options.time)
    if parse_status != 2:
        raise UserError(f'"{ctx.options.time!r} is not a valid relative time. '
                        f'Try something like "3 minutes" or "2 days"')
    if time <= datetime.now():
        raise UserError("You need to specify a time in the future.")
    async with tortoise.transactions.in_transaction() as tx:
        task = ScheduledTask(guild_id=ctx.guild_id, task_type=TaskType.REMINDER, process_after=time,
                             payload={'channel': ctx.channel_id, 'user': ctx.user.id, 'reason': ctx.options.about})
        await task.save(using_db=tx)
        await ctx.respond(f"All set. I will remind you in this channel about {ctx.options.about} "
                          f"around <t:{int(time.timestamp())}:f>. Your reminder ID is {task.pk} in case you want "
                          f"to cancel it later.")


@reminder_group.child
@lightbulb.option("id", description="Which reminder to cancel", type=int)
@lightbulb.command("cancel", description="Cancel an existing reminder.", ephemeral=True)
async def cancel(ctx: lightbulb.SlashContext) -> None:
    deleted_count = await ScheduledTask.filter(
        pk=ctx.options.id,
        guild_id=ctx.guild_id,
        task_type=TaskType.REMINDER,
        payload__contains={'user': ctx.user.id}
    ).delete()
    if deleted_count:
        await ctx.respond("I have cancelled that reminder.")
    else:
        raise UserError("That's not a valid reminder ID you can delete.")


@reminder_group.child
@lightbulb.command("list", description="List your existing reminders.", ephemeral=True)
async def list(ctx: lightbulb.SlashContext) -> None:
    reminders = await ScheduledTask.filter(
        guild_id=ctx.guild_id, task_type=TaskType.REMINDER, payload__contains={'user': ctx.user.id}
    ).all()
    if reminders:
        rows = (f'[{r.pk}] <t:{int(r.process_after.timestamp())}:f> {r.payload["reason"]}' for r in reminders)
        await ctx.respond("You have these reminders:\n" + '\n'.join(rows))
    else:
        await ctx.respond("You do not have any reminders.")


@tasks.task(m=1, auto_start=True, pass_app=True)
async def check_and_send_reminder(app: lightbulb.BotApp):
    async with tortoise.transactions.in_transaction() as tx:
        db_records = await ScheduledTask.select_for_update().using_db(tx).filter(
            guild_id__in=app.default_enabled_guilds,
            task_type=TaskType.REMINDER,
            process_after__lte=datetime.now(),
        ).all()
        for task in db_records:
            member = app.cache.get_member(task.guild_id, task.payload['user'])
            channel = app.cache.get_guild_channel(task.payload['channel'])
            try:
                await channel.send(f"Hey {member.mention}! Here's your reminder for "
                                   f"{task.payload['reason']}.")
            except hikari.ClientHTTPResponseError as e:
                logger.exception(f'Scheduled Task: Failed to send reminder message {task}; {e}')
            await task.delete(using_db=tx)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))
    tasks.load(bot)


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
