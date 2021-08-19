from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import declarative_base

TextModel = declarative_base()


class Quote(TextModel):
    __tablename__ = "quote"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)

