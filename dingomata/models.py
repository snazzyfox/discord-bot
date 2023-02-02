from enum import IntEnum

from tortoise import Model, fields

from dingomata.utils import DatetimeField, TimeField


class Bedtime(Model):
    user_id = fields.BigIntField(unique=True, null=False)
    bedtime = TimeField(null=False)
    timezone = fields.TextField(null=False)
    last_notified = DatetimeField(null=True)


class GambaUser(Model):
    class Meta:
        table = "gamba_user"
        unique_together = (("guild_id", "user_id"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    balance = fields.IntField(null=False, default=0)
    bet_believe = fields.IntField(null=False, default=0)
    bet_doubt = fields.IntField(null=False, default=0)
    last_claim = DatetimeField(null=True)


class GambaGame(Model):
    class Meta:
        table = "gamba_game"

    guild_id = fields.BigIntField(unique=True, null=False)
    channel_id = fields.BigIntField(null=False)
    title = fields.TextField(null=False)
    option_believe = fields.TextField(null=False)
    option_doubt = fields.TextField(null=False)
    open_until = DatetimeField(null=False)
    is_open = fields.BooleanField(null=False, default=True)
    # Separate variable to track whether the game is open to account for bot message update delays
    message_id = fields.BigIntField(null=True)
    creator_user_id = fields.BigIntField(null=False)
    # Creator can't make bets to avoid when all mods make a bet and nobody can pay out


class Quote(Model):
    class Meta:
        table = "quotes"
        unique_together = (("guild_id", "user_id", "content_digest"),)

    id = fields.IntField(pk=True)
    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    added_by = fields.BigIntField(null=False)
    content = fields.TextField(null=False)
    content_digest = fields.CharField(32, null=False)


class Tuch(Model):
    class Meta:
        table = "tuch"
        unique_together = (("guild_id", "user_id"),)
        indexes = (("guild_id", "max_butts"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    max_butts = fields.IntField(default=0, null=False)
    total_butts = fields.IntField(default=0, null=False)
    total_tuchs = fields.IntField(default=0, null=False)


class Collect(Model):
    class Meta:
        table = "collect"
        unique_together = (("guild_id", "user_id", "target_user_id"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    target_user_id = fields.BigIntField(null=False)


class Poll(Model):
    class Meta:
        table = "poll"
        unique_together = (("guild_id", "channel_id"),)

    guild_id = fields.BigIntField(null=False)
    channel_id = fields.BigIntField(null=False)
    title = fields.TextField(null=False)
    options = fields.TextField(null=False)
    message_id = fields.BigIntField(null=True)


class PollEntry(Model):
    class Meta:
        table = "poll_entry"
        unique_together = (("guild_id", "channel_id", "user_id"),)

    guild_id = fields.BigIntField(null=False)
    channel_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    option = fields.IntField(null=False)


class GamePool(Model):
    class Meta:
        table = "game_pool"

    guild_id = fields.BigIntField(unique=True, null=False)
    is_accepting_entries = fields.BooleanField(null=False, default=False)
    title = fields.TextField(null=False)
    mode = fields.SmallIntField(null=False)
    channel_id = fields.BigIntField(null=False)
    message_id = fields.BigIntField(null=False)


class GamePoolEntry(Model):
    class Meta:
        table = "game_pool_entry"
        unique_together = (("guild_id", "user_id"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    status = fields.SmallIntField(null=False)
    weight = fields.IntField()


class BotMessage(Model):
    class Meta:
        table = "bot_messages"

    id = fields.TextField(pk=True)
    channel_id = fields.BigIntField(null=False)
    message_id = fields.BigIntField(null=False)


class Profile(Model):
    class Meta:
        table = "profiles"
        unique_together = (("guild_id", "user_id"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    data = fields.JSONField(null=False)


class MessageMetric(Model):
    class Meta:
        table = "message_metrics"
        unique_together = (("guild_id", "user_id"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    message_count = fields.IntField(null=False, default=1)
    distinct_days = fields.IntField(null=False, default=1)
    last_distinct_day_boundary = fields.DatetimeField(null=False, auto_now_add=True)


class TaskType(IntEnum):
    REMOVE_ROLE = 0
    REMINDER = 1


class ScheduledTask(Model):
    class Meta:
        table = "scheduled_tasks"
        indexes = (('guild_id', 'task_type', 'process_after'),)

    guild_id = fields.BigIntField(null=False)
    task_type = fields.IntEnumField(TaskType, null=False)
    process_after = fields.DatetimeField(null=False)
    payload = fields.JSONField(null=False)
