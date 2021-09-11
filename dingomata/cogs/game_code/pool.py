from logging import getLogger
from random import sample
from typing import List, Optional, Tuple

from discord import Member
from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import GamePool, GamePoolEntry, EntryStatus, GameMode
from dingomata.config.config import service_config
from ...exceptions import DingomataUserError

_log = getLogger(__name__)


class MemberPoolStateError(DingomataUserError):
    """Error because the pool is in the wrong state (open/closed)"""
    pass


class MemberRoleError(DingomataUserError):
    """Error raised when a member doesn't have the right player roles to join the pool."""
    pass


class NoGamePoolError(DingomataUserError):
    pass


class MemberPool:
    def __init__(self, guild_id: int, session: sessionmaker, track_played: bool) -> None:
        self._guild_id = guild_id
        self._player_roles = service_config.servers[guild_id].game_code.player_roles
        self._session = session
        self._track_played = track_played
        self._pool: Optional[GamePool] = None

    async def open(self, title: str, mode: GameMode) -> None:
        await self._require_pool_status(False)
        async with self._session() as session:
            async with session.begin():
                pool = GamePool(guild_id=self._guild_id, is_open=True, title=title, mode=mode.value)
                await session.merge(pool)
                self._pool = pool
                await session.commit()

    async def close(self, check_status: bool = False) -> None:
        if check_status:
            await self._require_pool_status(True)
        pool = await self._get_pool()
        pool.is_open = False
        async with self._session() as session:
            async with session.begin():
                await session.merge(pool)
                await session.commit()

    async def clear(self, status: EntryStatus = EntryStatus.ELIGIBLE) -> None:
        await self._finalize_pick()
        async with self._session() as session:
            async with session.begin():
                statement = delete(GamePoolEntry).filter(GamePoolEntry.guild_id == self._guild_id,
                                                         GamePoolEntry.status == status.value)
                await session.execute(statement)
                await session.commit()

    async def pick(self, count: int) -> List[int]:
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

    async def set_message(self, channel_id: int, message_id: int) -> None:
        """Stores the message ID for the current pool."""
        async with self._session() as session:
            async with session.begin():
                pool = await self._get_pool()
                pool.message_id = message_id
                pool.channel_id = channel_id
                await session.merge(pool)

    async def get_message(self) -> Tuple[int, int]:
        pool = await self._get_pool()
        return pool.channel_id, pool.message_id

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
        await self._require_pool_status(True)
        pool = await self._get_pool()
        entry = GamePoolEntry(guild_id=self._guild_id, user_id=member.id, weight=weight,
                              status=EntryStatus.ELIGIBLE.value)
        async with self._session() as session:
            async with session.begin():
                try:
                    if pool.mode == GameMode.ANYONE.value:
                        await session.merge(entry)
                    else:
                        session.add(entry)
                        await session.commit()
                except IntegrityError as exc:
                    raise MemberPoolStateError(f"You're already in the pool or were in an earlier game.") from exc

    async def remove_member(self, member: Member) -> None:
        await self._require_pool_status(True)
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

    async def _get_pool(self) -> GamePool:
        if not self._pool:
            async with self._session() as session:
                statement = select(GamePool).filter(GamePool.guild_id == self._guild_id)
                self._pool = (await session.execute(statement)).scalar()
        if not self._pool:
            raise NoGamePoolError(f'There is no open game pool right now.')
        return self._pool

    async def is_open(self) -> bool:
        try:
            pool = await self._get_pool()
            return pool.is_open
        except NoGamePoolError:
            return False

    async def members(self, status: EntryStatus) -> List[int]:
        statement = select(GamePoolEntry.user_id).filter(GamePoolEntry.guild_id == self._guild_id,
                                                         GamePoolEntry.status == status.value)
        async with self._session() as session:
            data = await session.execute(statement)
            return [row.user_id for row in data]

    async def title(self) -> str:
        pool = await self._get_pool()
        return pool.title

    async def _require_pool_status(self, pool_open: bool = True) -> None:
        if await self.is_open() != pool_open:
            raise MemberPoolStateError(f'Pool must be {"open" if pool_open else "closed"} to do this.')
