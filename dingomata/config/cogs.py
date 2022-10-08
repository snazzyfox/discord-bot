from typing import Dict, List, Optional

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
    max_channels_per_min: int = 0


class GambaConfig(CogConfig):
    points_name: str = "points"
    daily_points: int = 1000


class GameCodeConfig(CogConfig):
    player_roles: Dict[int, int] = {0: 1}


class LoggingConfig(CogConfig):
    log_channel: Optional[int] = None  #: If none, all logging disabled
    message_deleted: bool = False
    user_banned: bool = False


class TwitterRule(BaseModel):
    filter: str
    channel: int
    message: str = ''


class TwitterConfig(BaseModel):
    rules: List[TwitterRule] = []


class SelfAssignRole(BaseModel):
    id: int
    # name should be read from discord so not configured here
    description: str = ""
    emoji: str  #: Must be a single unicode emoji supported by discord


class RolePickerConfig(BaseModel):
    __root__: List[SelfAssignRole] = []


class ProfileConfig(BaseModel):
    channel: int = 0
