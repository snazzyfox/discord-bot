import datetime
from typing import Any

from pypika_tortoise import CustomFunction
from tortoise import Model
from tortoise.expressions import Function
from tortoise.fields import Field


class TimeField(Field, datetime.time):
    """
    Tortoise field for Time fields without dates.
    """

    skip_to_python_if_native = True
    SQL_TYPE = "TIME"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # needed to make mypy go shut

    def to_python_value(self, value: Any) -> datetime.time | None:
        if value is not None and not isinstance(value, datetime.time):
            value = datetime.time.fromisoformat(value)
        self.validate(value)
        return value

    def to_db_value(
            self, value: datetime.time | str | None, instance: type[Model] | Model
    ) -> datetime.time | None:
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

    def to_python_value(self, value: Any) -> datetime.datetime | None:
        if value is not None and not isinstance(value, datetime.datetime):
            value = datetime.datetime.fromisoformat(value)
        self.validate(value)
        return value

    def to_db_value(
            self, value: datetime.datetime | str | None, instance: type[Model] | Model
    ) -> datetime.datetime | None:
        if value is not None and not isinstance(value, datetime.datetime):
            value = datetime.datetime.fromisoformat(value)
        self.validate(value)
        return value


class Random(Function):
    database_func = CustomFunction("random")
