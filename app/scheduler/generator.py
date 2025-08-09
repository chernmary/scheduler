# app/scheduler/generator.py
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

# Локации, работающие только по выходным (сб=5, вс=6)
WEEKEND_ONLY = {"Луномосик", "Авиапарк", "Москвариум 3"}

# Конфликтная пара (нельзя в один день в одном zone)
CONFLICT_PAIR = {"Катя Стрижкина", "Аня Стаценко"}

# мягкие/жёсткие лимиты
SOFT_WEEK_TARGET = 4
HARD_WEEK_CAP   = 5
SOFT_STREAK_TARGET = 2
HARD_STREAK_CAP    = 3


def load_data(session: Session):
    employees = (
        session.query(Employee)
        .filter_by(is_helper=False, on_sick_leave=False)
        .all()
    )
    # (employee_id, location_id) -> setting
    settings_map = {
        (s.employee_id, s.location_id): s
        for s in session.query(EmployeeSetting).all()
    }
    # для быстрой проверки «сотрудник только выходные»
    allowed_by_emp = defaultdict(set)
    for (emp_id, loc_id), s in settings_map.items():
        if s.is_allowed:
            allowed_by_emp[emp_id].add(loc_id)

    locations = session.query(Location).order_by(Location.order).all()
    loc_by_id = {l.id: l for l in locations}

    # признак: у сотрудника все разрешённые локации — из WEEKEND_ONLY
    weekend_only_emp = {}
    for emp in employees:
        allowed_ids = allowed_by_emp.get(emp.id, set())
        if not allowed_ids:
            weekend_only_emp[emp.id] = False
            continue
        names = {loc_by_id[i].name for i in allowed_ids if i in loc_by_id}
        weekend_only_emp[emp.id] = len(names) > 0 and all(n in WEEKEND_ONLY for n in names)

    return employees, settings_map, locations, weekend_only_emp


def can_work(es: EmployeeSetting | None, preferred_only: bool) -> bool:
    if preferred_only:
        return es is not None and es.is_allowed and es.is_preferred
    # если настроек нет — считаем, что можно (чтобы не «глохнуть»)
    return es is None or es.is_allowed


def violates_pair_zone(emp_name: str, zone: str, assigned_by_zone_today: dict[str, set[str]]) -> bool:
    if emp_name not in CONFLICT_PAIR:
        return False
    other = next(iter(CONFLICT_PAIR - {emp_name}))
    return other in assigned_by_zone_today.get(zone, set())


def score_candidate(emp_id: int, week_idx: int, week_count, streak_now: int,
                    prefer_balance: bool, total_2w_count: int) -> int:
    """
    Чем МЕНЬШЕ — тем лучше.
    prefer_balance=True даёт сильный приоритет тем, у кого < 4 смен за неделю.
    """
    w = week_count[(emp_id, week_idx)]
    s = streak_now
    score = 0

    # — приоритет недобора к 4
    if prefer_balance:
        if w < SOFT_WEEK_TARGET:
            score -= (SOFT_WEEK_TARGET - w) * 20  # мощный бонус за недобор

    # — штрафы за выход за мягкие рамки (но ещё в пределах жёстких)
    if w >= SOFT_WEEK_TARGET:
        score += (w - SOFT_WEEK_TARGET + 1) * 10  # 4->10, 5->20
    if s >= SOFT_STREAK_TARGET:
        score += (s - SOFT_STREAK_TARGET + 1) * 7  # 2->7, 3->14

    # лёгкий выравнивающий фактор
    score += w + total_2w_count
    return score


def generate_schedule(start: date, weeks: int = 2):
    """
    По дням:
      — 1 смена/день/сотрудник; зоны-конфликты; only-weekend точки;
      — сначала preferred, затем allowed;
      — мягкое выравнивание до 4/нед и 2 подряд, допускаем 5 и 3 при нехватке.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)
        emp_by_id = {e.id: e for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # уже существующие смены
        existing = {
            (s.location_id, s.date): s
            for s in session.query(Shift).filter(Shift.date.in_(dates)).all()
        }

        # счётчики
        week_count = defaultdict(int)   # (emp_id, week_idx) -> cnt
        total_2w  = defaultdict(int)    # emp_id -> cnt (внутри диапазона)
        prev_streak = defaultdict(int)  # серия к началу дня

        rows_before = session.query(Shift).count()

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            weekday = day.weekday()

            assigned_today_ids = set()                 # кто уже стоит сегодня
            assigned_by_zone_today = defaultdict(set)  # zone -> set(full_name)

            # учтём уже существующие назначения на этот день
            for loc in locations:
                s = existing.get((loc.id, day))
                if s and s.employee_id:
                    emp = emp_by_id.get(s.employee_id)
                    if emp:
                        assigned_today_ids.add(emp.id)
                        assigned_by_zone_today[loc.zone].add(emp.full_name)
                        week_count[(emp.id, week_idx)] += 1
                        total_2w[emp.id] += 1

            # два прохода: preferred -> allowed
            for preferred_pass in (True, False):
                for loc in locations:
                    # пропустим выходные-точки в будни
                    if loc.name in WEEKEND_ONLY and weekday not in (5, 6):
                        continue

                    # если слот уже занят человеком — пропускаем
                    if (loc.id, day) in existing and existing[(loc.id, day)].employee_id is not None:
                        continue

                    zone = loc.zone
                    shift_obj = existing.get((loc.id, day))

                    # собираем валидных кандидатов
                    pool = []
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work(es, preferred_only=preferred_pass):
                            continue
                        # 1 смена в день
                        if emp.id in assigned_today_ids:
                            continue
                        # конфликт пары по зоне
                        if violates_pair_zone(emp.full_name, zone, assigned_by_zone_today):
                            continue
                        # жёсткие отсеки
                        w = week_count[(emp.id, week_idx)]
                        s = prev_streak[emp.id]
                        if w >= HARD_WEEK_CAP:
                            continue
                        if s >= HARD_STREAK_CAP:
                            continue

                        pool.append((emp, es, w, s))

                    if not pool:
                        # создаём пустой слот, если его не было (для UI)
                        if shift_obj is None:
                            shift_obj = Shift(location_id=loc.id, date=day, employee_id=None)
                            session.add(shift_obj)
                            existing[(loc.id, day)] = shift_obj
                        continue

                    # на буднях усиливаем балансировку только для тех, кто НЕ weekend-only
                    prefer_balance = not all([
                        weekday not in (5, 6),           # это будний день
                        # и кандидат — чисто "выходной" сотрудник
                    ])

                    # оценка и выбор лучшего
                    def _score(item):
                        emp, es, w, s = item
                        pb = prefer_balance and not weekend_only_emp.get(emp.id, False)
                        return score_candidate(emp.id, week_idx, week_count, s, pb, total_2w[emp.id])

                    pool.sort(key=_score)
                    chosen = pool[0][0]

                    # записываем
                    if shift_obj is None:
                        shift_obj = Shift(location_id=loc.id, date=day, employee_id=chosen.id)
                        session.add(shift_obj)
                        existing[(loc.id, day)] = shift_obj
                    else:
                        shift_obj.employee_id = chosen.id

                    assigned_today_ids.add(chosen.id)
                    assigned_by_zone_today[zone].add(emp_by_id[chosen.id].full_name)
                    week_count[(chosen.id, week_idx)] += 1
                    total_2w[chosen.id] += 1

                # конец прохода preferred/allowed

            # обновляем серии к следующему дню
            new_streak = defaultdict(int)
            for e in employees:
                new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
            prev_streak = new_streak

        session.flush()
        rows_after = session.query(Shift).count()
        session.commit()
        # можно оставить print-лог, если нужно
        # print("[GEN] done", rows_after - rows_before, "new shifts")
        return None, dates
    finally:
        session.close()
