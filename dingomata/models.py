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


class BotMessages(Model):
    class Meta:
        table = "bot_messages"
        unique_together = (('message_type', 'guild_id', 'message_seq_num'),)

    message_type = fields.TextField(null=False)
    guild_id = fields.BigIntField(null=False)
    message_seq_num = fields.IntField(null=False)
    channel_id = fields.BigIntField(null=False)
    message_id = fields.BigIntField(null=False)


class RefSheet(Model):
    class Meta:
        table = "ref_sheets"
        indexes = (("guild_id", "user_id"), ("guild_id", "url"))

    guild_id = fields.BigIntField(null=False)
    name = fields.TextField(null=True)
    user_id = fields.BigIntField(null=False)
    url = fields.CharField(256, null=False)
    added_by = fields.BigIntField(null=False)
