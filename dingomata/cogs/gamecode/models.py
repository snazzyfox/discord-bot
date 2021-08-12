from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, Integer
from sqlalchemy.orm import declarative_base

GamecodeModel = declarative_base()


class GamePool(GamecodeModel):
    __tablename__ = "game_pool"

    guild_id = Column(BigInteger, primary_key=True)
    is_open = Column(Boolean, nullable=False, default=False)
    title = Column(String, nullable=False)


class GamePoolEntry(GamecodeModel):
    __tablename__ = "game_pool_entry"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    weight = Column(Integer)
