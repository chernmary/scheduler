# app/scheduler/generator.py
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift


def load_data(session: Session):
    """Грузим данные из БД и готовим индекс настроек по (employee_id, location_id)."""
    employees = (
        session.query(Employee)
        .filter_by(is_helper=False, on_sick_leave=False)
        .all()
    )
    settings_map = {
        (s.employee_id, s.location_id): s
        for s in session.query(EmployeeSetting).all()
    }
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings_map, locations


def can_work(es: EmployeeSetting, preferred_only: bool = False) -> bool:
    """Проверка допусков/предпочтений: сначала preferred, потом allowed."""
    if es is None:
        return False
    if not es.is_allowed:
        return False
    if preferred_only and not es.is_preferred:
        return False
    return True


def generate_schedule(start: date, weeks: int = 2):
    """
    Генерирует расписание на N недель, начиная с `start`.
    Правила:
      - не перезатираем уже существующие смены (ручные правки уважаем);
      - сначала пытаемся ставить на preferred-локации, затем — на allowed;
      - если никто не подходит, создаём пустой слот (employee_id=None);
      - учитываем лимиты, если заданы на уровне EmployeeSetting:
        max_shifts_per_week / max_shifts_per_2weeks.
    Возвращает (schedule_dict, dates_list).
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]
        emp_by_id = {e.id: e for e in employees}

        # Лимиты: (emp_id, week_idx) -> cnt и emp_id -> cnt за 2 недели
        shifts_count_week = defaultdict(int)
        shifts_count_2w = defaultdict(int)

        # Уже существующие смены в диапазоне — не трогаем
        existing = {
            (s.location_id, s.date): s
            for s in session.query(Shift).filter(Shift.date.in_(dates)).all()
        }

        # Для отображения (loc.name -> [emp_name per day])
        schedule = {loc.name: [] for loc in locations}

        for offset, day in enumerate(dates):
            week_idx = offset // 7

            for loc in locations:
                # Если смена уже есть — уважаем
                if (loc.id, day) in existing:
                    s = existing[(loc.id, day)]
                    emp_name = s.employee.full_name if s.employee else ""
                    schedule[loc.name].append(emp_name)
                    continue

                assigned_id = None

                # 1) Пытаемся preferred
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

                # 2) Если не нашли — allowed
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

                # 3) Записываем в БД и в отображение
                if assigned_id:
                    session.add(Shift(employee_id=assigned_id, location_id=loc.id, date=day))
                    schedule[loc.name].append(emp_by_id[assigned_id].full_name)
                    shifts_count_week[(assigned_id, week_idx)] += 1
                    shifts_count_2w[assigned_id] += 1
                else:
                    # Пустая смена (нужен nullable=True для Shift.employee_id)
                    session.add(Shift(employee_id=None, location_id=loc.id, date=day))
                    schedule[loc.name].append("")

        session.commit()
        return schedule, dates
    finally:
        session.close()
