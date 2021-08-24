from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base

GambaModel = declarative_base()


class GambaUser(GambaModel):
    __tablename__ = "gamba_user"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    balance = Column(Integer, nullable=False, default=0)
    last_claim = Column(DateTime, nullable=True)


class GambaGame(GambaModel):
    __tablename__ = "gamba_game"

    guild_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    title = Column(String, nullable=False)
    option_a = Column(String, nullable=False)
    option_b = Column(String, nullable=False)
    open_until = Column(DateTime, nullable=False)
    is_open = Column(Boolean, nullable=False, default=True)
    # Separate variable to track whether the game is open to account for bot message update delays
    message_id = Column(BigInteger, nullable=True)
    creator_user_id = Column(BigInteger, nullable=False)
    # Creator can't make bets to avoid when all mods make a bet and nobody can pay out


class GambaBet(GambaModel):
    __tablename__ = "gamba_bet"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    option_a = Column(Integer, nullable=True)
    option_b = Column(Integer, nullable=True)
