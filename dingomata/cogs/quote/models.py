from sqlalchemy import Column, String, Integer, BigInteger, Index
from sqlalchemy.orm import declarative_base

QuoteModel = declarative_base()


class TextQuote(QuoteModel):
    __tablename__ = "text_quote"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    added_by = Column(BigInteger, nullable=False)
    content = Column(String, nullable=False)

    __table_args__ = (
        Index('text_quote_unique_idx', guild_id, user_id, content, unique=True),
    )
