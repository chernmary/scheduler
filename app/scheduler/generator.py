from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

def load_data(session: Session):
    employees = session.query(Employee).filter_by(is_helper=False, on_sick_leave=False).all()
    settings = {s.employee_id: s for s in session.query(EmployeeSetting).all()}
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations

def can_work(es: EmployeeSetting, location_id: int, day: date) -> bool:
    if es is None:
        return False
    # здесь твоя логика допусков/предпочтений (сократил для примера):
    if hasattr(es, "allowed_location_id") and es.allowed_location_id:
        if es.allowed_location_id != location_id:
            return False
    return True

def generate_schedule(start: date, weeks: int = 2):
    """
    Генерирует расписание на N недель начиная с start
    и сохраняет в БД НОВЫЕ слоты, не затирая уже существующие (ручные правки).
    Возвращает (schedule, dates) для удобства.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # Быстрые индексы
        emp_by_id = {e.id: e for e in employees}

        # счётчики ограничений (если у тебя есть поля max_shifts_per_week / max_shifts_per_2weeks — будут учтены)
        from collections import defaultdict
        shifts_count_week = defaultdict(int)    # (emp_id, week_idx) -> cnt
        shifts_count_2w   = defaultdict(int)    # emp_id -> cnt

        # заполняем расписание в памяти и параллельно пишем в БД, если пусто
        schedule = {loc.name: [] for loc in locations}

        # заранее подгрузим уже существующие слоты в диапазоне — чтобы не затирать ручные правки
        existing = {(s.location_id, s.date): s for s in session.query(Shift).filter(Shift.date.in_(dates)).all()}

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            for loc in locations:
                # если уже есть смена (в т.ч. ручная) — уважаем её и не перегенерируем
                if (loc.id, day) in existing:
                    emp_name = existing[(loc.id, day)].employee.full_name if existing[(loc.id, day)].employee else ""
                    schedule[loc.name].append(emp_name)
                    continue

                assigned_id = None
                for emp in employees:
                    es = settings_map.get(emp.id)
                    if not can_work(es, loc.id, day):
                        continue

                    max_w  = getattr(es, "max_shifts_per_week", None) or 10**6
                    max_2w = getattr(es, "max_shifts_per_2weeks", None) or 10**6
                    if shifts_count_week[(emp.id, week_idx)] >= max_w:
                        continue
                    if shifts_count_2w[emp.id] >= max_2w:
                        continue

                    assigned_id = emp.id
                    break

                if assigned_id:
                    session.add(Shift(employee_id=assigned_id, location_id=loc.id, date=day))
                    schedule[loc.name].append(emp_by_id[assigned_id].full_name)
                    shifts_count_week[(assigned_id, week_idx)] += 1
                    shifts_count_2w[assigned_id] += 1
                else:
                    schedule[loc.name].append("")

        session.commit()
        return schedule, dates
    finally:
        session.close()
