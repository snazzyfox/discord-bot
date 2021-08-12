from random import sample
from typing import List, Optional

from discord import Member
from sqlalchemy import delete, func
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from dingomata.cogs.gamecode.models import GamePool, GamePoolEntry
from dingomata.config import get_guild_config
from dingomata.exceptions import DingomataUserError


class MemberPoolStateError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class MemberRoleError(DingomataUserError):
    """Error raised when a member doesn't have the right player roles to join the pool."""
    pass


class MemberPool:
    def __init__(self, guild_id: int, session: sessionmaker) -> None:
        self._guild_id = guild_id
        self._player_roles = get_guild_config(guild_id).game_code.player_roles
        self._session = session

    async def open(self, title: str) -> None:
        await self._require_pool_status(False)
        pool = GamePool(guild_id=self._guild_id, is_open=True, title=title)
        async with self._session() as session:
            async with session.begin():
                await session.merge(pool)
                await session.commit()

    async def close(self) -> None:
        await self._require_pool_status(True)
        await self._close()

    async def _close(self) -> None:
        pool = GamePool(guild_id=self._guild_id, is_open=False)
        async with self._session() as session:
            async with session.begin():
                await session.merge(pool)
                await session.commit()

    async def clear(self) -> None:
        await self._require_pool_status(False)
        async with self._session() as session:
            async with session.begin():
                statement = delete(GamePoolEntry).filter(GamePoolEntry.guild_id == self._guild_id)
                await session.execute(statement)
                await session.commit()

    async def pick(self, count: int) -> List[Member]:
        await self._close()
        async with self._session() as session:
            async with session.begin():
                statement = select(GamePoolEntry.user_id, GamePool.weight).filter(
                    GamePoolEntry.guild_id == self._guild_id)
                members = (await session.execute(statement)).scalars()
            if count > len(members):
                raise MemberPoolStateError(
                    f'Cannot pick more member than there are in the pool. The pool has {await self.size()} '
                    f'members in it.')
            # turn into parallel lists for sampling
            population, weights = zip(*((member.user_id, member.weight) for member in members))
            picked = sample(population=population, k=count, counts=weights)
        return picked

    def _get_member_weight(self, member: Member) -> int:
        if not self._player_roles:
            return 1
        else:
            roles = [role.id for role in member.roles] + [None]
            return max(self._player_roles.get(role, 0) for role in roles)

    async def add_member(self, member: Member) -> None:
        weight = self._get_member_weight(member)
        if weight == 0:
            raise MemberRoleError(f'You cannot join this pool because you do not have the necessary roles.')
        entry = GamePoolEntry(guild_id=self._guild_id, user_id=member.id, weight=weight)
        async with self._session() as session:
            async with session.begin():
                await session.merge(entry)
                await session.commit()

    async def remove_member(self, member: Member) -> None:
        async with self._session() as session:
            async with session.begin():
                statement = delete(GamePoolEntry).filter(
                    GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.user_id == member.id)
                await session.execute(statement)
                await session.commit()

    async def size(self) -> int:
        async with self._session() as session:
            stmt = select(func.count()).filter(GamePoolEntry.guild_id == self._guild_id)
            return session.scalar(stmt)

    async def is_open(self) -> bool:
        statement = select(GamePool.is_open).filter(GamePool.guild_id == self._guild_id)
        async with self._session() as session:
            result = (await session.execute(statement)).scalars().one_or_none()
            return result or False

    async def members(self) -> List[int]:
        statement = select(GamePoolEntry.user_id).filter(GamePoolEntry.guild_id == self._guild_id)
        async with self._session() as session:
            result = (await session.execute(statement)).scalars()
            return [entry.user_id for entry in result]

    async def title(self) -> str:
        statement = select(GamePool.title).filter(GamePool.guild_id == self._guild_id)
        async with self._session() as session:
            result = (await session.execute(statement)).scalars().one_or_none()
            return result or ''

    async def _require_pool_status(self, pool_open: bool = True) -> None:
        if await self.is_open() != pool_open:
            raise MemberPoolStateError(f'Pool must be {"open" if pool_open else "closed"} to do this.')
