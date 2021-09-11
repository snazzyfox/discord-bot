from dingomata.config.models import CogConfig


class BedtimeConfig(CogConfig):
    cooldown: int = 7200
    sleep_hours: int = 6
