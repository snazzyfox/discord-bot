from typing import Dict, Optional
from dingomata.config import CogConfig


class GameCodeConfig(CogConfig):
    """Config for random user selector"""
    player_roles: Dict[Optional[int], int] = {None: 1}
    exclude_played: bool = False
