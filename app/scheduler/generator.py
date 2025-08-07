# file: app/scheduler/generator.py

from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.database.models import Employee, EmployeeSetting, Location, Shift

# 1) Вспомогалка: русские названия дней недели
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def format_day(d: date) -> str:
    """ dd.mm Дд """
    return f"{d.day:02d}.{d.month:02d} {WEEKDAYS[d.weekday()]}"

def load_data(session: Session):
    """Загружаем из базы всех сотрудников, их настройки и локации"""
    employees = session.query(Employee).filter_by(is_helper=False, on_sick_leave=False).all()
    settings = {s.employee_id: s for s in session.query(EmployeeSetting).all()}
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations

def can_work(es: EmployeeSetting, loc_id: int, day: date) -> bool:
    """Проверяем, разрешено ли сотруднику es работать на location_id в день day"""
    # недоступные дни
    if hasattr(es, "unavailable_days") and es.unavailable_days:
        if day.isoformat() in es.unavailable_days.split(","):
            return False
    # запрещённые локации
    if hasattr(es, "restricted_locations") and es.restricted_locations:
        if str(loc_id) in es.restricted_locations.split(","):
            return False
    return True

def generate_schedule(start: date, weeks: int = 2):
    """Генерация расписания и сохранение его в базу данных"""
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        shifts_count_week = defaultdict(int)
        shifts_count_2weeks = defaultdict(int)

        total_days = weeks * 7
        for offset in range(total_days):
            today = start + timedelta(days=offset)
            week_index = offset // 7

            for loc in locations:
                candidates = []
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
                    candidates.append((emp, es))

                candidates.sort(key=lambda pair: pair[1].is_preferred, reverse=True)

                if loc.zone == "main_building":
                    assigned_today = session.query(Shift).filter_by(date=today).all()
                    forbidden = {"Катя Стрижкина", "Аня Стаценко"}
                    assigned_names = {a.employee.full_name for a in assigned_today}
                    if forbidden & assigned_names:
                        candidates = [c for c in candidates if c[0].full_name not in forbidden]

                if candidates:
                    chosen, _ = candidates[0]
                    new_shift = Shift(
                        employee_id=chosen.id,
                        location_id=loc.id,
                        date=today,
                        is_template=False
                    )
                    session.add(new_shift)
                    shifts_count_week[(chosen.id, week_index)] += 1
                    shifts_count_2weeks[chosen.id] += 1

        session.commit()
        print(f"\n✅ График с {format_day(start)} успешно создан и сохранён в базе!\n")
    finally:
        session.close()

if __name__ == "__main__":
    generate_schedule(date(2025, 8, 18), weeks=2)
