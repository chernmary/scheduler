# file: app/scheduler/generator.py

from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def format_day(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d} {WEEKDAYS[d.weekday()]}"

def load_data(session: Session):
    employees = session.query(Employee).filter_by(is_helper=False, on_sick_leave=False).all()
    settings = {s.employee_id: s for s in session.query(EmployeeSetting).all()}
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations

def can_work(es: EmployeeSetting, loc_id: int, day: date) -> bool:
    if hasattr(es, "unavailable_days") and es.unavailable_days:
        if day.isoformat() in es.unavailable_days.split(","):
            return False
    if hasattr(es, "restricted_locations") and es.restricted_locations:
        if str(loc_id) in es.restricted_locations.split(","):
            return False
    return True

def generate_schedule(start: date, weeks: int = 2):
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        shifts_count_week = defaultdict(int)
        shifts_count_2weeks = defaultdict(int)

        schedule = defaultdict(list)
        dates = [format_day(start + timedelta(days=i)) for i in range(weeks * 7)]

        total_days = weeks * 7
        for offset in range(total_days):
            today = start + timedelta(days=offset)
            week_index = offset // 7

            for loc in locations:
                for emp in employees:
                    es = settings_map.get(emp.id)
                    if not es:
                        continue
                    if not can_work(es, loc.id, today):
                        continue
                    max_w = es.max_shifts_per_week or 0
                    max_2w = es.max_shifts_per_2weeks or 0
                    if shifts_count_week[(emp.id, week_index)] >= max_w:
                        continue
                    if shifts_count_2weeks[emp.id] >= max_2w:
                        continue
                    # назначаем сотрудника на смену (заполняем schedule)
                    schedule[loc.name].append(emp.full_name)
                    shifts_count_week[(emp.id, week_index)] += 1
                    shifts_count_2weeks[emp.id] += 1
                    break  # переходим к следующей локации

        return schedule, dates

    finally:
        session.close()
