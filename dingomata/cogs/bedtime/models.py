from sqlalchemy import Column, Integer, BigInteger, Time, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Bedtime(Base):
    __tablename__ = "bedtime"

    user = Column(BigInteger, primary_key=True)
    bedtime = Column(Time, nullable=False)
    timezone = Column(String, nullable=False)
    last_notified = Column(DateTime, nullable=True)

