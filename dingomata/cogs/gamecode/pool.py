from random import sample
from typing import Set, Dict, List

from discord import Member

from dingomata.config import get_guild_config
from dingomata.exceptions import DingomataUserError


class MemberPoolStateError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class MemberRoleError(DingomataUserError):
    """Error raised when a member doesn't have the right player roles to join the pool."""
    pass


class MemberPool:
    def __init__(self, guild_id: int) -> None:
        self._members: Dict[Member] = {}
        self._picked_users: Set[Member] = set()
        self._is_open = False
        self._player_roles = get_guild_config(guild_id).game_code.player_roles

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
        if not self._player_roles:
            return 1
        else:
            roles = [role.id for role in member.roles] + [None]
            return max(self._player_roles.get(role, 0) for role in roles)

    def add_member(self, member: Member) -> None:
        weight = self._get_member_weight(member)
        if weight == 0:
            raise MemberRoleError(f'You cannot join this pool because you do not have the necessary roles.')
        self._members[member] = weight

    def remove_member(self, member: Member) -> None:
        self._members.pop(member, None)

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
