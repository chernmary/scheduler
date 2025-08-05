
from pydantic import BaseModel
from datetime import date
from typing import List, Optional

class UnavailablePeriod(BaseModel):
    start_date: date
    end_date: date

class Employee(BaseModel):
    id: Optional[int]
    full_name: str
    birth_date: Optional[date]
    phone_number: Optional[str]
    telegram_nick: Optional[str]
    max_shifts_per_week: int = 6
    tags: List[str] = []
    passport_expiry: Optional[date]
    medbook_expiry: Optional[date]
    unavailable_periods: List[UnavailablePeriod] = []

class ScheduleTemplate(BaseModel):
    name: str
    data: dict
