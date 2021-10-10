from sqlalchemy import Column, Integer, BigInteger, String
from sqlalchemy.orm import declarative_base

PollModel = declarative_base()


class Poll(PollModel):
    __tablename__ = "poll"

    guild_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    options = Column(String, nullable=False)
    message_id = Column(BigInteger, nullable=True)


class PollEntry(PollModel):
    __tablename__ = "poll_entry"

    guild_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    option = Column(Integer, nullable=False)
