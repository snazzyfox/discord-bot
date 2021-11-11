from typing import Set

from dingomata.config import CogConfig


class RoleConfig(CogConfig):
    #: List of role IDs that users can self-assign
    self_assignable_roles: Set[int] = []
