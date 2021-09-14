from dingomata.config.models import CogConfig


class BedtimeConfig(CogConfig):
    cooldown_minutes: int = 30
    sleep_hours: int = 6
