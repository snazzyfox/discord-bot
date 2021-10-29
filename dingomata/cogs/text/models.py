from sqlalchemy import Column, Integer, BigInteger, Index
from sqlalchemy.orm import declarative_base

TextModel = declarative_base()


class TextTuchLog(TextModel):
    __tablename__ = "text_tuch"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    max_butts = Column(Integer)
    total_butts = Column(Integer)
    total_tuchs = Column(Integer)

    __table_args__ = (
        Index('text_tuch_guild_max_butts_idx', guild_id, max_butts.desc()),
    )


class TextCollect(TextModel):
    __tablename__ = "text_collect"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    target_user_id = Column(BigInteger, primary_key=True)
