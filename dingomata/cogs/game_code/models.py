from enum import Enum

from sqlalchemy import Column, BigInteger, String, Boolean, Integer
from sqlalchemy.orm import declarative_base

GamecodeModel = declarative_base()


class EntryStatus(Enum):
    ELIGIBLE = 1
    SELECTED = 2
    PLAYED = 3


class GameMode(Enum):
    NEW_PLAYERS_ONLY = 1
    ANYONE = 2


class GamePool(GamecodeModel):
    __tablename__ = "game_pool"

    guild_id = Column(BigInteger, primary_key=True)
    is_open = Column(Boolean, nullable=False, default=False)
    title = Column(String, nullable=False)
    mode = Column(Integer, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)


class GamePoolEntry(GamecodeModel):
    __tablename__ = "game_pool_entry"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    status = Column(Integer, nullable=False)
    weight = Column(Integer)
