from random import sample
from typing import Set, Dict, List

from discord import Member

from dingomata.config import get_config_value, ConfigurationKey
from dingomata.exceptions import DingomataUserError


class MemberPoolStateError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class MemberRoleError(DingomataUserError):
    """Error raised when a member doesn't have the right player roles to join the pool."""
    pass


class MemberPool:
    def __init__(self) -> None:
        self._members: Dict[Member] = {}
        self._picked_users: Set[Member] = set()
        self._is_open = False

        # Turn the id:weight,id:weight etc string into a dictionary
        self._disallowed_roles = set()
        self._player_roles = {}
        for role_weight in (get_config_value(ConfigurationKey.SECURITY_PLAYER_ROLES) or '').split(','):
            if ':' in role_weight:
                split = role_weight.split(':')
                role = -1 if split[0] == '*' else int(split[0])
                weight = int(split[1])
            else:
                role = -1 if role_weight == '*' else int(role_weight)
                weight = 1
            if weight == 0:
                self._disallowed_roles.add(role)
            else:
                self._player_roles[role] = weight

    def open(self) -> None:
        self._require_pool_status(False)
        self._is_open = True

    def close(self) -> None:
        self._require_pool_status(True)
        self._is_open = False

    def clear(self) -> None:
        self._require_pool_status(False)
        self._members = set()
        self._picked_users = set()

    def pick(self, count: int) -> List[Member]:
        self._is_open = False
        if count > len(self._members):
            raise MemberPoolStateError(f'Cannot pick more member than there are in the pool. The pool has {self.size} '
                                       f'members in it.')
        population, weights = zip(*self._members.items())  # turn into parallel lists for sampling
        self._picked_users = sample(population=population, k=count, counts=weights)
        return self._picked_users

    def _get_member_weight(self, member: Member) -> int:
        roles = [role.id for role in member.roles] + [-1]
        if any(role in self._disallowed_roles for role in roles):
            return 0
        elif not self._player_roles:
            return 1
        else:
            return max(self._player_roles.get(role, 0) for role in roles)

    def add_member(self, member: Member) -> None:
        weight = self._get_member_weight(member)
        if weight == 0:
            raise MemberRoleError(f'You cannot join this pool because you do not have the right roles.')
        self._members[member] = weight

    def remove_member(self, member: Member) -> None:
        del self._members[member]

    @property
    def size(self) -> int:
        return len(self._members)

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def members(self) -> List[Member]:
        return list(self._members)

    def _require_pool_status(self, pool_open: bool = True) -> None:
        if self._is_open != pool_open:
            raise MemberPoolStateError(f'Pool must be {"open" if pool_open else "closed"} to do this.')
