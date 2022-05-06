import datetime
import logging
from typing import Any, Optional, Type

import discord.ui
from pypika import CustomFunction
from tortoise import Model
from tortoise.expressions import Function
from tortoise.fields import Field

from dingomata.config import service_config
from dingomata.exceptions import DingomataUserError

log = logging.getLogger(__name__)


class TimeField(Field, datetime.time):
    """
    Tortoise field for Time fields without dates.
    """

    skip_to_python_if_native = True
    SQL_TYPE = "TIME"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # needed to make mypy go shut

    def to_python_value(self, value: Any) -> Optional[datetime.time]:
        if value is not None and not isinstance(value, datetime.time):
            value = datetime.time.fromisoformat(value)
        self.validate(value)
        return value

    def to_db_value(
            self, value: datetime.time | str | None, instance: Type[Model] | Model
    ) -> Optional[datetime.time]:
        if value is not None and not isinstance(value, datetime.time):
            value = datetime.time.fromisoformat(value)
        self.validate(value)
        return value


class DatetimeField(Field, datetime.datetime):
    """
    Tortoise field for timezone-naive datetimes.
    """

    skip_to_python_if_native = True
    SQL_TYPE = "TIMESTAMP"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # needed to make mypy go shut

    def to_python_value(self, value: Any) -> Optional[datetime.datetime]:
        if value is not None and not isinstance(value, datetime.datetime):
            value = datetime.datetime.fromisoformat(value)
        self.validate(value)
        return value

    def to_db_value(
            self, value: datetime.datetime | str | None, instance: Type[Model] | Model
    ) -> Optional[datetime.datetime]:
        if value is not None and not isinstance(value, datetime.datetime):
            value = datetime.datetime.fromisoformat(value)
        self.validate(value)
        return value


class Random(Function):
    database_func = CustomFunction("random")


class View(discord.ui.View):
    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if isinstance(error, DingomataUserError):
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)
            log.warning(f"{error.__class__.__name__}: {error}")
        else:
            await super(View, self).on_error(error, item, interaction)


def mention_if_needed(ctx: discord.ApplicationContext, user: discord.User) -> str:
    """Return a user's mention string, or display name if they're in the no-ping list"""
    no_pings = service_config.server[ctx.guild.id].roles.no_pings
    member = ctx.guild.get_member(user.id)
    if member and member.id in no_pings or any(role.id in no_pings for role in member.roles):
        return user.display_name
    else:
        return user.mention
