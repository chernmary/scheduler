from sqlalchemy import Column, Integer, String, Date, Text
from datetime import date
from app.database import Base

# ДОБАВИТЬ В СУЩЕСТВУЮЩИЙ models.py

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(Date, default=date.today)
    action = Column(String)
    user = Column(String)
    details = Column(Text)
