from sqlalchemy import Column, String, Integer, BigInteger
from sqlalchemy.orm import declarative_base

TextModel = declarative_base()


class Quote(TextModel):
    __tablename__ = "quote"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)


class TuchLog(TextModel):
    __tablename__ = "tuch"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    max_butts = Column(Integer)
    total_butts = Column(Integer)
    total_tuchs = Column(Integer)
