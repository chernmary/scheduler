from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

# --- Константы проекта ---
WEEKEND_ONLY_LOCATIONS = {"Луномосик", "Авиапарк", "Москвариум 3"}  # только сб/вс
CONFLICT_PAIR = {"Катя Стрижкина", "Аня Стаценко"}                  # нельзя в один день в одном zone

# Мягкие/жёсткие лимиты
SOFT_WEEK_TARGET = 4
HARD_WEEK_CAP = 5
SOFT_STREAK_TARGET = 2
HARD_STREAK_CAP = 3

# Спец-цели на выходных
SPECIAL_TARGET_SET = {"Москвариум 1", "Москвариум 0", "Мультпарк"}
SPECIAL_STAFF = {
    "Катя Стрижкина": {"need_target_once": True, "need_master_once": False},
    "Настя Губарева": {"need_target_once": True, "need_master_once": False},
    "Лиза Терехова":  {"need_target_once": True, "need_master_once": False},
    "Аня Стаценко":   {"need_target_once": True, "need_master_once": True},  # + 1 день Мастер классы
    "Алиса Бойцова":  {"forbid_weekend": {"Москвариум 0", "Москвариум 1"}},
}

# --- Утилиты ---
def can_work_setting(es: EmployeeSetting | None, preferred_only: bool) -> bool:
    if preferred_only:
        return es is not None and es.is_allowed and es.is_preferred
    return es is None or es.is_allowed

def violates_pair_zone(emp_name: str, zone: str, by_zone_today: dict[str, set[str]]) -> bool:
    if emp_name not in CONFLICT_PAIR:
        return False
    other = next(iter(CONFLICT_PAIR - {emp_name}))
    return other in by_zone_today.get(zone, set())

def load_data(session: Session):
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

    allowed_by_emp = defaultdict(set)
    for (emp_id, loc_id), s in settings_map.items():
        if s.is_allowed:
            allowed_by_emp[emp_id].add(loc_id)
    loc_by_id = {l.id: l for l in locations}
    weekend_only_emp: dict[int, bool] = {}
    for e in employees:
        ids = allowed_by_emp.get(e.id, set())
        if not ids:
            weekend_only_emp[e.id] = False
            continue
        names = {loc_by_id[i].name for i in ids if i in loc_by_id}
        weekend_only_emp[e.id] = len(names) > 0 and all(n in WEEKEND_ONLY_LOCATIONS for n in names)

    return employees, settings_map, locations, weekend_only_emp

# --- Основное ---
def generate_schedule(start: date, weeks: int = 2, persist: bool = True):
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)
        emp_by_id = {e.id: e for e in employees}
        emp_id_by_name = {e.full_name: e.id for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # 💡 КЛЮЧЕВОЕ: чистим все смены в диапазоне дат — новая генерация с нуля
        session.query(Shift).filter(Shift.date.in_(dates)).delete(synchronize_session=False)
        session.commit()

        existing: dict[tuple[int, date], Shift] = {}

        week_count = defaultdict(int)
        total_2w = defaultdict(int)
        prev_streak = defaultdict(int)
        used_loc_week = defaultdict(set)
        special_done_target = defaultdict(set)
        special_done_master = defaultdict(set)

        preview_output = []

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            weekday = day.weekday()

            assigned_today_ids: set[int] = set()
            assigned_by_zone_today: dict[str, set[str]] = defaultdict(set)

            for preferred_pass in (True, False):
                for loc in locations:
                    # локации, которые работают только по выходным
                    if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                        continue

                    zone = loc.zone
                    shift_obj = None

                    # сформировать пул кандидатов
                    pool: list[tuple[Employee, EmployeeSetting | None, int, int]] = []
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work_setting(es, preferred_only=preferred_pass):
                            continue

                        # персональные запреты на выходных
                        if weekday in (5, 6):
                            rules = SPECIAL_STAFF.get(emp.full_name, {})
                            if loc.name in rules.get("forbid_weekend", set()):
                                continue

                        if emp.id in assigned_today_ids:
                            continue
                        if violates_pair_zone(emp.full_name, zone, assigned_by_zone_today):
                            continue

                        w = week_count[(emp.id, week_idx)]
                        s_now = prev_streak[emp.id]
                        if w >= HARD_WEEK_CAP or s_now >= HARD_STREAK_CAP:
                            continue

                        pool.append((emp, es, w, s_now))

                    # если никого нельзя — оставляем пусто
                    if not pool:
                        if not persist:
                            preview_output.append({"date": day, "location_id": loc.id, "employee_name": None})
                        continue

                    chosen_emp: Employee | None = None

                    # выходные — мягкие спец-правила
                    if weekday in (5, 6):
                        # Аня Стаценко — один раз Мастер классы в неделю
                        if loc.name == "Мастер классы" and week_idx not in special_done_master["Аня Стаценко"]:
                            for emp, es, w, s_now in pool:
                                if emp.full_name == "Аня Стаценко":
                                    chosen_emp = emp
                                    special_done_master["Аня Стаценко"].add(week_idx)
                                    break
                        # “целевые” точки — распределяем по людям, кому нужно «раз в неделю»
                        if chosen_emp is None and loc.name in SPECIAL_TARGET_SET:
                            for name, rules in SPECIAL_STAFF.items():
                                if not rules.get("need_target_once"):
                                    continue
                                if week_idx in special_done_target[name]:
                                    continue
                                eid = emp_id_by_name.get(name)
                                if not eid:
                                    continue
                                for emp, es, w, s_now in pool:
                                    if emp.id == eid:
                                        chosen_emp = emp
                                        special_done_target[name].add(week_idx)
                                        break
                                if chosen_emp is not None:
                                    break

                    # обычный скоринг
                    if chosen_emp is None:
                        def soft_ok(it):
                            emp, es, w, s_now = it
                            if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                return False
                            return (w < SOFT_WEEK_TARGET) and (s_now < SOFT_STREAK_TARGET)

                        soft_pool = [it for it in pool if soft_ok(it)]
                        use_pool = soft_pool if soft_pool else pool

                        def score(it):
                            emp, es, w, s_now = it
                            pen = 0
                            # небольшой бонус за приоритетную локацию из настроек
                            if es and getattr(es, "is_preferred", False):
                                pen -= 40
                            # штрафы/бонусы за баланс
                            pen -= (max(0, SOFT_WEEK_TARGET - w)) * 25
                            if w >= SOFT_WEEK_TARGET:
                                pen += (w - SOFT_WEEK_TARGET + 1) * 30
                            if s_now >= SOFT_STREAK_TARGET:
                                pen += (s_now - SOFT_STREAK_TARGET + 1) * 35
                            if loc.id in used_loc_week[(emp.id, week_idx)]:
                                pen += 50
                            pen += total_2w[emp.id]
                            return pen

                        use_pool.sort(key=score)
                        chosen_emp = use_pool[0][0]

                    # записываем результат
                    if persist:
                        shift_obj = Shift(location_id=loc.id, date=day, employee_id=chosen_emp.id)
                        session.add(shift_obj)
                    else:
                        preview_output.append({
                            "date": day,
                            "location_id": loc.id,
                            "employee_name": chosen_emp.full_name
                        })

                    assigned_today_ids.add(chosen_emp.id)
                    assigned_by_zone_today[zone].add(chosen_emp.full_name)
                    week_count[(chosen_emp.id, week_idx)] += 1
                    total_2w[chosen_emp.id] += 1
                    used_loc_week[(chosen_emp.id, week_idx)].add(loc.id)

                    if weekday in (5, 6) and chosen_emp.full_name == "Аня Стаценко" and loc.name == "Мастер классы":
                        special_done_master["Аня Стаценко"].add(week_idx)
                    if weekday in (5, 6) and loc.name in SPECIAL_TARGET_SET and chosen_emp.full_name in SPECIAL_STAFF:
                        special_done_target[chosen_emp.full_name].add(week_idx)

            # обновляем «полосы» подряд
            new_streak = defaultdict(int)
            for e in employees:
                new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
            prev_streak = new_streak

        if persist:
            session.flush()
            session.commit()
            return None, dates
        else:
            return preview_output, dates
    finally:
        session.close()
