from sqlalchemy import Column, BigInteger, Time, String, DateTime
from sqlalchemy.orm import declarative_base

BedtimeModel = declarative_base()


class Bedtime(BedtimeModel):
    __tablename__ = "bedtime"

    user_id = Column(BigInteger, primary_key=True)
    bedtime = Column(Time, nullable=False)
    timezone = Column(String, nullable=False)
    last_notified = Column(DateTime, nullable=True)
