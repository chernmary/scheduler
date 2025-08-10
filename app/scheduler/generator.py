import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional, Dict, Set, Tuple, List

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

# --- Константы и правила ---

# Локации, которые работают только по выходным (сб/вс)
WEEKEND_ONLY_LOCATIONS: Set[str] = {"Луномосик", "Авиапарк", "Москвариум 3"}

# Пара, которой нельзя работать в один день в одной зоне
CONFLICT_PAIR: Set[str] = {"Катя Стрижкина", "Аня Стаценко"}

# Мягкие/жесткие лимиты
SOFT_WEEK_TARGET = 4
HARD_WEEK_CAP = 5
SOFT_STREAK_TARGET = 2
HARD_STREAK_CAP = 3

# Спец-цели на выходных
SPECIAL_TARGET_SET: Set[str] = {"Москвариум 1", "Москвариум 0", "Мультпарк"}
SPECIAL_STAFF: Dict[str, dict] = {
    "Катя Стрижкина": {"need_target_once": True,  "need_master_once": False},
    "Настя Губарева": {"need_target_once": True,  "need_master_once": False},
    "Лиза Терехова":  {"need_target_once": True,  "need_master_once": False},
    "Аня Стаценко":   {"need_target_once": True,  "need_master_once": True},   # + 1 выходной «Мастер классы»
    "Алиса Бойцова":  {"forbid_weekend": {"Москвариум 0", "Москвариум 1"}},    # персональные запреты на выходных
}

# --- Вспомогательные функции ---

def can_work_setting(es: Optional[EmployeeSetting], preferred_only: bool) -> bool:
    """Фильтр по настройкам: preferred-проход — только is_preferred; иначе — любой allowed (или отсутствие записи)."""
    if preferred_only:
        return es is not None and es.is_allowed and getattr(es, "is_preferred", False)
    return es is None or es.is_allowed

def violates_pair_zone(emp_name: str, zone: str, by_zone_today: Dict[str, Set[str]]) -> bool:
    """Запрещаем одновременную работу конфликтной пары в одной зоне."""
    if emp_name not in CONFLICT_PAIR:
        return False
    others = CONFLICT_PAIR - {emp_name}
    present = by_zone_today.get(zone, set())
    return any(o in present for o in others)

def load_data(session: Session):
    employees: List[Employee] = (
        session.query(Employee).filter(Employee.is_active == True).order_by(Employee.full_name).all()
    )
    locations: List[Location] = session.query(Location).order_by(Location.order).all()

    # карта настроек (employee_id, location_id) -> EmployeeSetting
    settings = session.query(EmployeeSetting).all()
    settings_map: Dict[Tuple[int, int], EmployeeSetting] = {}
    for s in settings:
        settings_map[(s.employee_id, s.location_id)] = s

    # вычислим список «только выходные» по allowed-локациям сотрудника
    by_emp_allowed: Dict[int, List[int]] = defaultdict(list)
    for s in settings:
        if s.is_allowed:
            by_emp_allowed[s.employee_id].append(s.location_id)

    loc_by_id = {l.id: l for l in locations}
    weekend_only_emp: Dict[int, bool] = {}
    for e in employees:
        ids = by_emp_allowed.get(e.id, [])
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
    Внутри каждой недели порядок дней: сначала выходные (сб/вс), затем будни.
    Возвращает (None, dates) при persist=True.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)
        emp_id_by_name = {e.full_name: e.id for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # очистка старых черновиков за диапазон
        session.query(Shift).filter(
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
            Shift.status == "draft",
        ).delete(synchronize_session=False)
        session.commit()

        # счётчики и состояния
        week_count: Dict[Tuple[int, int], int] = defaultdict(int)   # (emp_id, week_idx) -> кол-во смен в неделе
        total_2w: Dict[int, int] = defaultdict(int)                 # emp_id -> кол-во смен за период
        prev_streak: Dict[int, int] = defaultdict(int)              # emp_id -> серия подряд дней
        used_loc_week: Dict[Tuple[int, int], Set[int]] = defaultdict(set)  # (emp_id, week_idx) -> уже работал на loc_id
        special_done_target: Dict[str, Set[int]] = defaultdict(set) # name -> {week_idx}
        special_done_master: Dict[str, Set[int]] = defaultdict(set) # name -> {week_idx}

        # обход по неделям
        for wstart in range(0, total_days, 7):
            week_dates = dates[wstart:wstart + 7]
            # сначала выходные, потом будни
            sorted_week_dates = sorted(week_dates, key=lambda d: 0 if d.weekday() in (5, 6) else 1)

            for day in sorted_week_dates:
                week_idx = (day - start).days // 7
                weekday = day.weekday()

                assigned_today_ids: Set[int] = set()
                assigned_by_zone_today: Dict[str, Set[str]] = defaultdict(set)

                # по всем локациям в этот день — максимум 1 назначение на локацию
                for loc in locations:
                    # локация работает только по выходным
                    if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                        continue

                    zone = loc.zone
                    chosen_emp: Optional[Employee] = None

                    # два прохода: preferred -> allowed
                    for preferred_pass in (True, False):
                        if chosen_emp is not None:
                            break

                        # собираем пул кандидатов
                        pool: List[Tuple[Employee, Optional[EmployeeSetting], int, int]] = []
                        for emp in employees:
                            es = settings_map.get((emp.id, loc.id))
                            if not can_work_setting(es, preferred_only=preferred_pass):
                                continue

                            # запрет строго «только выходные» — не ставим человека в будни
                            if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                continue

                            # персональные запреты на выходных
                            if weekday in (5, 6):
                                rules = SPECIAL_STAFF.get(emp.full_name, {})
                                if loc.name in rules.get("forbid_weekend", set()):
                                    continue

                            # ограничения на день/зону
                            if emp.id in assigned_today_ids:
                                continue
                            if violates_pair_zone(emp.full_name, zone, assigned_by_zone_today):
                                continue

                            # недельные/серийные лимиты
                            w = week_count[(emp.id, week_idx)]
                            s_now = prev_streak[emp.id]
                            if w >= HARD_WEEK_CAP or s_now >= HARD_STREAK_CAP:
                                continue

                            pool.append((emp, es, w, s_now))

                        if not pool:
                            continue

                        # приоритеты только на выходных
                        if weekday in (5, 6):
                            # 1) «Мастер классы» — 1 раз в неделю для Ани Стаценко
                            if (loc.name == "Мастер классы"
                                and SPECIAL_STAFF.get("Аня Стаценко", {}).get("need_master_once")
                                and week_idx not in special_done_master["Аня Стаценко"]):
                                cand = next((e for (e, es, w, s) in pool if e.full_name == "Аня Стаценко"), None)
                                if cand:
                                    chosen_emp = cand
                                    special_done_master["Аня Стаценко"].add(week_idx)

                            # 2) Target-точки — по 1 выходному в неделю для отмеченных
                            if chosen_emp is None and loc.name in SPECIAL_TARGET_SET:
                                for name, rules in SPECIAL_STAFF.items():
                                    if not rules.get("need_target_once"):
                                        continue
                                    if week_idx in special_done_target[name]:
                                        continue
                                    cand = next((e for (e, es, w, s) in pool if e.full_name == name), None)
                                    if cand:
                                        chosen_emp = cand
                                        special_done_target[name].add(week_idx)
                                        break

                        # обычный скоринг, если приоритет не выбрал
                        if chosen_emp is None:
                            def soft_ok(item) -> bool:
                                emp, es, w, s_now = item
                                # «только выходные» дополнительно фильтруем (подстраховка)
                                if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                    return False
                                return (w < SOFT_WEEK_TARGET) and (s_now < SOFT_STREAK_TARGET)

                            soft_pool = [it for it in pool if soft_ok(it)]
                            use_pool = soft_pool if soft_pool else pool
                            random.shuffle(use_pool)

                            def score(item) -> int:
                                emp, es, w, s_now = item
                                pen = 0
                                # бонус за предпочитаемую локацию
                                if es and getattr(es, "is_preferred", False):
                                    pen -= 40
                                # стремимся добрать до мягкой цели
                                if w < SOFT_WEEK_TARGET:
                                    pen -= (SOFT_WEEK_TARGET - w) * 25
                                if w >= SOFT_WEEK_TARGET:
                                    pen += (w - SOFT_WEEK_TARGET + 1) * 30
                                if s_now >= SOFT_STREAK_TARGET:
                                    pen += (s_now - SOFT_STREAK_TARGET + 1) * 35
                                # не повторяем одну и ту же локацию в рамках недели
                                if loc.id in used_loc_week[(emp.id, week_idx)]:
                                    pen += 50
                                # выравнивание общего баланса за 2 недели
                                pen += total_2w[emp.id]
                                # лёгкая рандомизация
                                pen += random.randint(0, 9)
                                return pen

                            chosen_emp = min(use_pool, key=score)[0]

                    # фиксируем назначение (ровно одно на локацию за день)
                    if chosen_emp is not None:
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

                # конец дня — обновляем серии подряд
                new_streak: Dict[int, int] = defaultdict(int)
                for e in employees:
                    new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
                prev_streak = new_streak

        if persist:
            session.commit()
            return None, dates
        else:
            # можно вернуть предпросмотр без записи в БД
            preview = []  # заполни при необходимости
            return preview, dates

    finally:
        session.close()
