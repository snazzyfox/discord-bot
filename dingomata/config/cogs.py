from typing import Dict, Optional

from pydantic import BaseModel


class CogConfig(BaseModel):
    class Config:
        extra = "forbid"


class BedtimeConfig(CogConfig):
    cooldown_minutes: int = 30
    sleep_hours: int = 6


class AutomodConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    text_prefix: str = ""
    log_channel: Optional[int] = None


class GambaConfig(CogConfig):
    points_name: str = "points"
    daily_points: int = 1000


class GameCodeConfig(CogConfig):
    player_roles: Dict[int, int] = {0: 1}
