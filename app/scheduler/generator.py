from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift


def load_data(session: Session):
    employees = session.query(Employee).filter_by(is_helper=False, on_sick_leave=False).all()
    # Собираем настройки в структуру: (employee_id, location_id) -> EmployeeSetting
    settings = {
        (s.employee_id, s.location_id): s
        for s in session.query(EmployeeSetting).all()
    }
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations


def can_work(es: EmployeeSetting, preferred_only=False) -> bool:
    if es is None:
        return False
    if not es.is_allowed:
        return False
    if preferred_only and not es.is_preferred:
        return False
    return True


def generate_schedule(start: date, weeks: int = 2):
    """
    Генерация графика на N недель начиная с `start`.
    Сначала пытаемся заполнить preferred-локации,
    затем — любые из allowed. Если никто не подходит, оставляем слот пустым.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        emp_by_id = {e.id: e for e in employees}
        shifts_count_week = defaultdict(int)   # (emp_id, week_idx) -> cnt
        shifts_count_2w = defaultdict(int)     # emp_id -> cnt

        schedule = {loc.name: [] for loc in locations}

        existing = {
            (s.location_id, s.date): s
            for s in session.query(Shift).filter(Shift.date.in_(dates)).all()
        }

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            for loc in locations:
                if (loc.id, day) in existing:
                    emp_name = existing[(loc.id, day)].employee.full_name if existing[(loc.id, day)].employee else ""
                    schedule[loc.name].append(emp_name)
                    continue

                assigned_id = None

                # 1. Пробуем preferred
                for emp in employees:
                    es = settings_map.get((emp.id, loc.id))
                    if not can_work(es, preferred_only=True):
                        continue
                    max_w = getattr(es, "max_shifts_per_week", None) or 10**6
                    max_2w = getattr(es, "max_shifts_per_2weeks", None) or 10**6
                    if shifts_count_week[(emp.id, week_idx)] >= max_w:
                        continue
                    if shifts_count_2w[emp.id] >= max_2w:
                        continue
                    assigned_id = emp.id
                    break

                # 2. Если не нашли — пробуем allowed
                if not assigned_id:
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work(es, preferred_only=False):
                            continue
                        max_w = getattr(es, "max_shifts_per_week", None) or 10**6
                        max_2w = getattr(es, "max_shifts_per_2weeks", None) or 10**6
                        if shifts_count_week[(emp.id, week_idx)] >= max_w:
                            continue
                        if shifts_count_2w[emp.id] >= max_2w:
                            continue
                        assigned_id = emp.id
                        break

                # 3. Записываем смену
                if assigned_id:
                    session.add(Shift(employee_id=assigned_id, location_id=loc.id, date=day))
                    schedule[loc.name].append(emp_by_id[assigned_id].full_name)
                    shifts_count_week[(assigned_id, week_idx)] += 1
                    shifts_count_2w[assigned_id] += 1
                else:
                    # Пустая смена для ручного заполнения
                    session.add(Shift(employee_id=None, location_id=loc.id, date=day))
                    schedule[loc.name].append("")

        session.commit()
        return schedule, dates
    finally:
        session.close()
