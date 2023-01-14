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
    raid_min_users: int = 5
    raid_window_hours: float = 2


class GambaConfig(CogConfig):
    points_name: str = "points"
    daily_points: int = 1000


class GameCodeConfig(CogConfig):
    player_roles: Dict[int, int] = {0: 1}


class LoggingConfig(CogConfig):
    log_channel: Optional[int] = None  #: If none, all logging disabled
    message_deleted: bool = False
    message_edited: bool = False
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


class ManagedRoleConfig(BaseModel):
    id: int
    remove_after_hours: int = 0  #: auto remove the role after this many hours of it being applied
    min_messages: int = 0  #: min number of messages in chat, not including embed/link/image only
    min_days: int = 0  #: min number of days since the member joined
    min_active_days: int = 0  #: min number of days the member is active in chat


class RoleManageConfig(BaseModel):
    roles: List[ManagedRoleConfig] = []
