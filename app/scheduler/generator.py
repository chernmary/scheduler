import random
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

# --- Константы ---
WEEKEND_ONLY_LOCATIONS = {"Луномосик", "Авиапарк", "Москвариум 3"}  # работают только сб/вс
CONFLICT_PAIR = {"Катя Стрижкина", "Аня Стаценко"}                  # нельзя в один день в одном zone

# Лимиты
SOFT_WEEK_TARGET = 4
HARD_WEEK_CAP = 5
SOFT_STREAK_TARGET = 2
HARD_STREAK_CAP = 3

# Спец-правила выходных
SPECIAL_TARGET_SET = {"Москвариум 1", "Москвариум 0", "Мультпарк"}
SPECIAL_STAFF = {
    "Катя Стрижкина": {"need_target_once": True, "need_master_once": False},
    "Настя Губарева": {"need_target_once": True, "need_master_once": False},
    "Лиза Терехова":  {"need_target_once": True, "need_master_once": False},
    "Аня Стаценко":   {"need_target_once": True, "need_master_once": True},  # 1 раз Мастер классы
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
        weekend_only_emp[e.id] = all(n in WEEKEND_ONLY_LOCATIONS for n in names)

    return employees, settings_map, locations, weekend_only_emp

# --- Генерация черновика ---
def generate_schedule(start: date, weeks: int = 2, persist: bool = True):
    """
    Генерирует DRAFT-график на 'weeks' недель, начиная с 'start' (обычно ближайший понедельник).
    Внутри каждой недели порядок дней: суббота/воскресенье -> будни.
    Каждый запуск даёт новый вариант за счёт случайного порядка кандидатов.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)
        emp_id_by_name = {e.full_name: e.id for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # Чистим СТАРЫЙ ЧЕРНОВИК за этот диапазон
        session.query(Shift).filter(
            Shift.date.in_(dates),
            Shift.status == "draft"
        ).delete(synchronize_session=False)
        session.commit()

        week_count = defaultdict(int)            # (emp_id, week_idx) -> count
        total_2w = defaultdict(int)              # emp_id -> count
        prev_streak = defaultdict(int)           # emp_id -> streak длина
        used_loc_week = defaultdict(set)         # (emp_id, week_idx) -> {loc_id}
        special_done_target = defaultdict(set)   # name -> {week_idx}
        special_done_master = defaultdict(set)   # "Аня Стаценко" -> {week_idx}

        # Обход по неделям
        for week_start_idx in range(0, total_days, 7):
            week_dates = dates[week_start_idx:week_start_idx + 7]
            # Сначала выходные, потом будни
            sorted_week_dates = sorted(week_dates, key=lambda d: 0 if d.weekday() in (5, 6) else 1)

            for day in sorted_week_dates:
                week_idx = (day - start).days // 7
                weekday = day.weekday()

                assigned_today_ids: set[int] = set()
                assigned_by_zone_today: dict[str, set[str]] = defaultdict(set)

                # Два прохода: сначала только preferred, потом все allowed
                for preferred_pass in (True, False):
                    for loc in locations:
                        # точки только для выходных
                        if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                            continue

                        zone = loc.zone

                        # Собираем пул кандидатов
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

                        if not pool:
                            continue

                        chosen_emp = None

                        # Спец-правила выходных
                        if weekday in (5, 6):
                            # 1) Стаценко — 1 раз Мастер классы в неделю
                            if loc.name == "Мастер классы" and week_idx not in special_done_master["Аня Стаценко"]:
                                for emp, es, w, s_now in pool:
                                    if emp.full_name == "Аня Стаценко":
                                        chosen_emp = emp
                                        special_done_master["Аня Стаценко"].add(week_idx)
                                        break

                            # 2) Target-точки — распределить по людям с need_target_once
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

                        # Обычный скоринг
                        if chosen_emp is None:
                            def soft_ok(it):
                                emp, es, w, s_now = it
                                if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                    return False
                                return (w < SOFT_WEEK_TARGET) and (s_now < SOFT_STREAK_TARGET)

                            soft_pool = [it for it in pool if soft_ok(it)]
                            use_pool = soft_pool if soft_pool else pool

                            # 🎲 лёгкая случайность — каждый запуск даёт разные варианты
                            random.shuffle(use_pool)

                            def score(it):
                                emp, es, w, s_now = it
                                pen = 0
                                # бонус за приоритет
                                if es and getattr(es, "is_preferred", False):
                                    pen -= 40
                                # баланс по неделе/стрик/двух неделям
                                pen -= (max(0, SOFT_WEEK_TARGET - w)) * 25
                                if w >= SOFT_WEEK_TARGET:
                                    pen += (w - SOFT_WEEK_TARGET + 1) * 30
                                if s_now >= SOFT_STREAK_TARGET:
                                    pen += (s_now - SOFT_STREAK_TARGET + 1) * 35
                                if loc.id in used_loc_week[(emp.id, week_idx)]:
                                    pen += 50
                                pen += total_2w[emp.id]
                                # маленький рандом, чтобы «лучшие» иногда менялись местами
                                pen += random.randint(0, 9)
                                return pen

                            use_pool.sort(key=score)
                            chosen_emp = use_pool[0][0]

                        # Запись черновика
                        if persist:
                            session.add(Shift(
                                location_id=loc.id,
                                date=day,
                                employee_id=chosen_emp.id,
                                status="draft",
                            ))

                        assigned_today_ids.add(chosen_emp.id)
                        assigned_by_zone_today[zone].add(chosen_emp.full_name)
                        week_count[(chosen_emp.id, week_idx)] += 1
                        total_2w[chosen_emp.id] += 1
                        used_loc_week[(chosen_emp.id, week_idx)].add(loc.id)

                # обновляем стрики по завершении дня
                new_streak = defaultdict(int)
                for e in employees:
                    new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
                prev_streak = new_streak

        if persist:
            session.commit()
            return None, dates
        else:
            # превью для не-персиста (если нужно)
            return [], dates
    finally:
        session.close()
