from typing import Optional

from dingomata.config import CogConfig


class ModerationConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    text: str = ''
    log_channel: Optional[int] = None
    mute_role: Optional[int] = None
