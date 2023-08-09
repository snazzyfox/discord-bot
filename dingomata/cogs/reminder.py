import logging
from datetime import datetime

import discord
import parsedatetime
import tortoise
from discord.ext.tasks import loop

from dingomata.database.models import ScheduledTask, TaskType

from ..decorators import slash_group
from ..exceptions import DingomataUserError
from .base import BaseCog

_log = logging.getLogger(__name__)
_calendar = parsedatetime.Calendar()


class ReminderCog(BaseCog):
    """Custom reminders."""

    reminder = slash_group("reminder", description="Make the discord_bot remind you to do something.")

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        self.reminder_loop.start()

    def cog_unload(self) -> None:
        self.reminder_loop.stop()

    @reminder.command()
    @discord.option('in',
                    description="How much later you want the reminder. For example, 10 minutes or 2 days.",
                    parameter_name='in_')
    @discord.option('about', description="What to get reminded about.")
    async def set(self, ctx: discord.ApplicationContext, in_: str, about: str) -> None:
        """Set a new reminder. I will send you a reminder in this channel around this time."""
        time, parse_status = _calendar.parseDT(in_)
        if parse_status != 2:
            raise DingomataUserError(f'"{in_} is not a valid relative time. Try something like "3 minutes" or "2 days"')
        if time <= datetime.now():
            raise DingomataUserError("You need to specify a time in the future.")
        if not ctx.channel.can_send():
            raise DingomataUserError("I don't have permissions to send you messages in this channel. Please run this "
                                     "command in a different channel.")
        async with tortoise.transactions.in_transaction() as tx:
            task = ScheduledTask(guild_id=ctx.guild.id, task_type=TaskType.REMINDER, process_after=time,
                                 payload={'channel': ctx.channel.id, 'user': ctx.user.id, 'reason': about})
            await task.save(using_db=tx)
            await ctx.respond(f"All set. I will remind you in this channel about {about} "
                              f"around <t:{int(time.timestamp())}:f>. Your reminder ID is {task.pk} in case you want "
                              f"to cancel it later.", ephemeral=True)

    @reminder.command()
    @discord.option('id', description="Which reminder to cancel", parameter_name="id_")
    async def cancel(self, ctx: discord.ApplicationContext, id_: int) -> None:
        """Cancel an existing reminder."""
        deleted_count = await ScheduledTask.filter(
            pk=id_,
            guild_id=ctx.guild.id,
            task_type=TaskType.REMINDER,
            payload__contains={'user': ctx.user.id}
        ).delete()
        if deleted_count:
            await ctx.respond("I have cancelled that reminder.", ephemeral=True)
        else:
            raise DingomataUserError("That's not a valid reminder ID you can delete.")

    @reminder.command()
    async def list(self, ctx: discord.ApplicationContext) -> None:
        """List your existing reminders."""
        reminders = await ScheduledTask.filter(
            guild_id=ctx.guild.id, task_type=TaskType.REMINDER, payload__contains={'user': ctx.user.id}
        ).all()
        if reminders:
            rows = (f'[{r.pk}] <t:{int(r.process_after.timestamp())}:f> {r.payload["reason"]}' for r in reminders)
            await ctx.respond("You have these reminders:\n" + '\n'.join(rows), ephemeral=True)
        else:
            await ctx.respond("You do not have any reminders.", ephemeral=True)

    @loop(minutes=1)
    async def reminder_loop(self):
        async with tortoise.transactions.in_transaction() as tx:
            tasks = await ScheduledTask.select_for_update().using_db(tx).filter(
                guild_id__in=[guild.id for guild in self._bot.guilds],
                task_type=TaskType.REMINDER,
                process_after__lte=datetime.now(),
            ).all()
            for task in tasks:
                guild = self._bot.get_guild(task.guild_id)
                member = guild.get_member(task.payload['user'])
                channel = guild.get_channel(task.payload['channel'])
                try:
                    await channel.send(f"Hey {member.mention}! Here's your reminder about "
                                       f"{task.payload['reason']}.")
                except discord.HTTPException:
                    _log.exception(f'Scheduled Task: Failed to send reminder message {task}')
                await task.delete(using_db=tx)
