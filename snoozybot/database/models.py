from enum import IntEnum

from tortoise import Model, fields

from snoozybot.database.fields import DatetimeField, TimeField


class Config(Model):
    class Meta:
        table = "configs"
        unique_together = (('guild_id', 'config_key'),)

    guild_id = fields.BigIntField(null=False)
    config_key = fields.TextField(null=False)
    config_value = fields.JSONField(null=False)


class User(Model):
    class Meta:
        table = "users"

    user_id = fields.BigIntField(pk=True, generated=False)
    timezone = fields.TextField(null=True)
    bedtime = TimeField(null=True)
    last_bedtime_notified = DatetimeField(null=True)


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


class GuildMember(Model):
    class Meta:
        table = "guild_members"
        unique_together = (("guild_id", "user_id"),)
        indexes = (("guild_id", "next_birthday_utc"),)

    guild_id = fields.BigIntField(null=False)
    user_id = fields.BigIntField(null=False)
    profile_data = fields.JSONField(null=False, default={})
    birthday_month = fields.SmallIntField(null=True)
    birthday_day = fields.SmallIntField(null=True)
    next_birthday_utc = fields.DatetimeField(null=True)


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
