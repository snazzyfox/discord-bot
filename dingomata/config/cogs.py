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
    scam_filter: bool = False
    age_filter: bool = False


class GambaConfig(CogConfig):
    points_name: str = "points"
    daily_points: int = 1000


class GameCodeConfig(CogConfig):
    player_roles: Dict[int, int] = {0: 1}


class LoggingConfig(CogConfig):
    log_channel: Optional[int] = None  #: If none, all logging disabled
    message_deleted: bool = False
    user_banned: bool = False
