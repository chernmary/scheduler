# app/scheduler/generator.py
from datetime import date, timedelta
from collections import defaultdict
import sys

from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift


# --- лог в Render ---
def log(*args):
    print("[GEN]", *args, file=sys.stdout, flush=True)


# --- конфликтная пара и зона ---
BAD_PAIR = {"Катя Стрижкина", "Аня Стаценко"}  # точные full_name из БД


def load_data(session: Session):
    employees = (
        session.query(Employee)
        .filter_by(is_helper=False, on_sick_leave=False)
        .all()
    )
    # индексация настроек по (employee_id, location_id)
    settings_map = {
        (s.employee_id, s.location_id): s
        for s in session.query(EmployeeSetting).all()
    }
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings_map, locations


def can_work(es: EmployeeSetting, preferred_only: bool = False) -> bool:
    """preferred-проход: нужен es с is_allowed и is_preferred.
       allowed-проход: если настроек нет — считаем, что можно (иначе генератор затыкается)."""
    if preferred_only:
        return es is not None and es.is_allowed and es.is_preferred
    return es is None or es.is_allowed


def week_limit(es: EmployeeSetting | None) -> int:
    """Макс. смен в неделю: берём из настроек, иначе 4."""
    return getattr(es, "max_shifts_per_week", None) or 4


def violates_pair_zone_conflict(emp_name: str, zone: str, assigned_today_by_zone: dict[str, set[str]]) -> bool:
    """Запрещаем Стрижкину и Стаценко работать в ОДНОМ zone в ОДИН день."""
    if emp_name not in BAD_PAIR:
        return False
    other = next(iter(BAD_PAIR - {emp_name}))
    return other in assigned_today_by_zone.get(zone, set())


def generate_schedule(start: date, weeks: int = 2):
    """
    Генерация по дням, соблюдаем:
      - 1 смена в день на человека
      - лимит по неделе (по умолчанию 4, либо из настроек)
      - ≤3 подряд (стараемся держать ≤2; приоритет тем, у кого серия меньше)
      - Стрижкина/Стаценко не в одном zone в один день
      - сначала preferred, затем allowed
      - существующие смены не трогаем
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)
        emp_by_id = {e.id: e for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]
        log("start", start.isoformat(), "days", total_days, "emps", len(employees), "locs", len(locations))

        # Уже существующие смены в диапазоне — уважаем
        existing = {
            (s.location_id, s.date): s
            for s in session.query(Shift).filter(Shift.date.in_(dates)).all()
        }

        rows_before = session.query(Shift).count()

        # Трекеры
        week_count = defaultdict(int)   # (emp_id, week_idx) -> cnt
        prev_streak = defaultdict(int)  # серия к началу дня (для приоритета)

        # Пройдёмся по дням
        for offset, day in enumerate(dates):
            week_idx = offset // 7

            # Кто уже стоит сегодня (из существующих записей)
            assigned_today = set[int]()
            assigned_today_by_zone: dict[str, set[str]] = defaultdict(set)
            for loc in locations:
                s = existing.get((loc.id, day))
                if s and s.employee_id:
                    emp = emp_by_id.get(s.employee_id)
                    if emp:
                        assigned_today.add(emp.id)
                        assigned_today_by_zone[loc.zone].add(emp.full_name)
                        week_count[(emp.id, week_idx)] += 1

            # Делаем два прохода: сначала preferred, потом allowed
            for preferred_pass in (True, False):
                for loc in locations:
                    # если слот уже заполнен человеком — пропускаем
                    if (loc.id, day) in existing and existing[(loc.id, day)].employee_id is not None:
                        continue

                    zone = loc.zone
                    shift_obj = existing.get((loc.id, day))  # может быть None или пустой

                    # Собираем список кандидатов, которые проходят фильтры
                    candidates = []
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work(es, preferred_only=preferred_pass):
                            continue
                        # 1 смена в день
                        if emp.id in assigned_today:
                            continue
                        # лимит по неделе
                        if week_count[(emp.id, week_idx)] >= week_limit(es):
                            continue
                        # серия подряд: максимум 3
                        if prev_streak[emp.id] >= 3:
                            continue
                        # конфликт пары в зоне
                        if violates_pair_zone_conflict(emp.full_name, zone, assigned_today_by_zone):
                            continue

                        candidates.append((emp, es))

                    if not candidates:
                        # если слота нет — создадим пустой, чтобы видно было в UI
                        if shift_obj is None:
                            shift_obj = Shift(location_id=loc.id, date=day, employee_id=None)
                            session.add(shift_obj)
                            existing[(loc.id, day)] = shift_obj
                        continue

                    # «Мягкий» выбор: сначала меньше недельных смен, потом короче серия
                    candidates.sort(
                        key=lambda pair: (week_count[(pair[0].id, week_idx)], prev_streak[pair[0].id])
                    )
                    chosen = candidates[0][0]  # Employee

                    # Записываем
                    if shift_obj is None:
                        shift_obj = Shift(location_id=loc.id, date=day, employee_id=chosen.id)
                        session.add(shift_obj)
                        existing[(loc.id, day)] = shift_obj
                    else:
                        shift_obj.employee_id = chosen.id  # был пустой — заполнили

                    assigned_today.add(chosen.id)
                    assigned_today_by_zone[zone].add(chosen.full_name)
                    week_count[(chosen.id, week_idx)] += 1

            # Обновим серии к началу следующего дня: кто стоял сегодня — серия +1, иначе 0
            new_streak = defaultdict(int)
            for e in employees:
                new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today) else 0
            prev_streak = new_streak

        session.flush()
        rows_after = session.query(Shift).count()
        session.commit()
        log("done", "rows_before", rows_before, "rows_after", rows_after, "added", rows_after - rows_before)

        return None, dates
    finally:
        session.close()
