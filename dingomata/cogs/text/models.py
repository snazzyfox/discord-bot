from sqlalchemy import Column, String, Integer, BigInteger, Index
from sqlalchemy.orm import declarative_base

TextModel = declarative_base()


class TextQuote(TextModel):
    __tablename__ = "text_quote"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    content = Column(String, nullable=False)

    __table_args__ = (
        Index('text_quote_guild_user_idx', guild_id, user_id),
    )


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
