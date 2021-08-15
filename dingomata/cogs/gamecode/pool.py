from random import sample
from typing import List

from discord import Member
from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import GamePool, GamePoolEntry, EntryStatus
from ...config import get_guild_config
from ...exceptions import DingomataUserError


class MemberPoolStateError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class MemberRoleError(DingomataUserError):
    """Error raised when a member doesn't have the right player roles to join the pool."""
    pass


class MemberPool:
    def __init__(self, guild_id: int, session: sessionmaker, track_played: bool) -> None:
        self._guild_id = guild_id
        self._player_roles = get_guild_config(guild_id).game_code.player_roles
        self._session = session
        self._track_played = track_played

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

    async def clear(self, status: EntryStatus = EntryStatus.ELIGIBLE) -> None:
        await self._require_pool_status(False)
        await self._finalize_pick()
        async with self._session() as session:
            async with session.begin():
                statement = delete(GamePoolEntry).filter(GamePoolEntry.guild_id == self._guild_id,
                                                         GamePoolEntry.status == status.value)
                await session.execute(statement)
                await session.commit()

    async def ban_user(self, user_id: int):
        async with self._session() as session:
            async with session.begin():
                entry = GamePoolEntry(guild_id=self._guild_id, user_id=user_id, weight=0,
                                      status=EntryStatus.BANNED.value)
                await session.merge(entry)
                await session.commit()

    async def pick(self, count: int) -> List[int]:
        await self._close()
        async with self._session() as session:
            async with session.begin():
                await self._finalize_pick()
                statement = select(GamePoolEntry.user_id, GamePoolEntry.weight).filter(
                    GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.status == EntryStatus.ELIGIBLE.value)
                members = (await session.execute(statement)).all()
                if count > len(members):
                    raise MemberPoolStateError(
                        f'Cannot pick more member than there are in the pool. The pool has '
                        f'{await self.size(EntryStatus.ELIGIBLE)} eligible members in it.')
                # turn into parallel lists for sampling
                population, weights = zip(*((member.user_id, member.weight) for member in members))
                picked_user_ids = sample(population=population, k=count, counts=weights)
                # Change their status
                statement = update(GamePoolEntry).filter(
                    GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.user_id.in_(picked_user_ids)
                ).values({GamePoolEntry.status: EntryStatus.SELECTED.value})
                await session.execute(statement)
                await session.commit()
        return picked_user_ids

    async def _finalize_pick(self):
        async with self._session() as session:
            async with session.begin():
                if self._track_played:
                    stmt = update(GamePoolEntry).filter(
                        GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.status == EntryStatus.SELECTED.value
                    ).values({GamePoolEntry.status: EntryStatus.PLAYED.value})
                else:
                    stmt = delete(GamePoolEntry).filter(
                        GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.status == EntryStatus.SELECTED.value
                    )
                await session.execute(stmt)
                await session.commit()

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
        entry = GamePoolEntry(guild_id=self._guild_id, user_id=member.id, weight=weight,
                              status=EntryStatus.ELIGIBLE.value)
        async with self._session() as session:
            async with session.begin():
                try:
                    session.add(entry)
                    await session.commit()
                except IntegrityError as exc:
                    raise MemberPoolStateError(f"You can't join this pool. You've either already joined, or have "
                                               f"been selected already.") from exc

    async def remove_member(self, member: Member) -> None:
        async with self._session() as session:
            async with session.begin():
                statement = delete(GamePoolEntry).filter(
                    GamePoolEntry.guild_id == self._guild_id, GamePoolEntry.user_id == member.id,
                    GamePoolEntry.status == EntryStatus.ELIGIBLE.value
                )
                await session.execute(statement)
                await session.commit()

    async def size(self, status: EntryStatus) -> int:
        async with self._session() as session:
            stmt = select(func.count()).filter(GamePoolEntry.guild_id == self._guild_id,
                                               GamePoolEntry.status == status.value)
            return await session.scalar(stmt)

    async def is_open(self) -> bool:
        statement = select(GamePool.is_open).filter(GamePool.guild_id == self._guild_id)
        async with self._session() as session:
            result = (await session.execute(statement)).scalars().one_or_none()
            return result or False

    async def members(self, status: EntryStatus) -> List[int]:
        statement = select(GamePoolEntry.user_id).filter(GamePoolEntry.guild_id == self._guild_id,
                                                         GamePoolEntry.status == status.value)
        async with self._session() as session:
            data = await session.execute(statement)
            return [row.user_id for row in data]

    async def title(self) -> str:
        statement = select(GamePool.title).filter(GamePool.guild_id == self._guild_id)
        async with self._session() as session:
            result = (await session.execute(statement)).scalars().one_or_none()
            return result or ''

    async def _require_pool_status(self, pool_open: bool = True) -> None:
        if await self.is_open() != pool_open:
            raise MemberPoolStateError(f'Pool must be {"open" if pool_open else "closed"} to do this.')
