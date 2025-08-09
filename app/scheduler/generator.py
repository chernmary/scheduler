# app/scheduler/generator.py
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

# Спец-правила выходных
SPECIAL_TARGET_SET = {"Москвариум 1", "Москвариум 0", "Мультпарк"}  # «зона москвариум (кроме 3)» + мультпарк
SPECIAL_STAFF = {
    "Катя Стрижкина": {"need_target_once": True, "need_master_once": False},
    "Настя Губарева": {"need_target_once": True, "need_master_once": False},
    "Лиза Терехова":  {"need_target_once": True, "need_master_once": False},
    "Аня Стаценко":   {"need_target_once": True, "need_master_once": True},  # + обязательно «Мастер классы» 1 день
}


# --- Вспомогательные ---
def can_work_setting(es: EmployeeSetting | None, preferred_only: bool) -> bool:
    if preferred_only:
        return es is not None and es.is_allowed and es.is_preferred
    return es is None or es.is_allowed  # если настроек нет — не блокируем


def violates_pair_zone(emp_name: str, zone: str, assigned_by_zone_today: dict[str, set[str]]) -> bool:
    if emp_name not in CONFLICT_PAIR:
        return False
    other = next(iter(CONFLICT_PAIR - {emp_name}))
    return other in assigned_by_zone_today.get(zone, set())


def load_data(session: Session):
    employees = (
        session.query(Employee)
        .filter_by(is_helper=False, on_sick_leave=False)
        .all()
    )
    settings_map = {  # (emp_id, loc_id) -> setting
        (s.employee_id, s.location_id): s
        for s in session.query(EmployeeSetting).all()
    }
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings_map, locations


def generate_schedule(start: date, weeks: int = 2):
    """
    Генерация по дням с балансировкой и спец-правилами выходных.
    Не перетирает существующие смены, соблюдает жёсткие ограничения.
    """
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)
        emp_by_id = {e.id: e for e in employees}
        emp_id_by_name = {e.full_name: e.id for e in employees}
        loc_by_id = {l.id: l for l in locations}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # Уже существующие смены в диапазоне — уважаем
        existing = {
            (s.location_id, s.date): s
            for s in session.query(Shift).filter(Shift.date.in_(dates)).all()
        }

        # Счётчики
        week_count = defaultdict(int)           # (emp_id, week_idx) -> кол-во смен в неделе
        total_2w = defaultdict(int)             # emp_id -> всего за период
        prev_streak = defaultdict(int)          # серия к началу дня (сколько подряд уже шёл)
        used_loc_week = defaultdict(set)        # (emp_id, week_idx) -> set(loc_id) для перемешивания

        # Трекинг спец-правил: на какой неделе условие выполнено
        special_done_target = defaultdict(set)  # name -> set(week_idx) для target-назн.
        special_done_master = defaultdict(set)  # name -> set(week_idx) для «Мастер классы»

        rows_before = session.query(Shift).count()

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            weekday = day.weekday()  # 0-пн .. 6-вс

            # Кто уже стоит сегодня (учесть существующие)
            assigned_today_ids = set()
            assigned_by_zone_today = defaultdict(set)  # zone -> set(full_name)

            for loc in locations:
                s = existing.get((loc.id, day))
                if s and s.employee_id:
                    emp = emp_by_id.get(s.employee_id)
                    if emp:
                        assigned_today_ids.add(emp.id)
                        assigned_by_zone_today[loc.zone].add(emp.full_name)
                        week_count[(emp.id, week_idx)] += 1
                        total_2w[emp.id] += 1
                        used_loc_week[(emp.id, week_idx)].add(loc.id)
                        # учтём серию: если вчера работал — серия продолжится ниже
            # --- два прохода: preferred -> allowed ---
            for preferred_pass in (True, False):
                for loc in locations:
                    # Выходные-точки — только сб/вс
                    if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                        continue

                    # если слот уже заполнен — пропускаем
                    if (loc.id, day) in existing and existing[(loc.id, day)].employee_id is not None:
                        continue

                    zone = loc.zone
                    shift_obj = existing.get((loc.id, day))  # None/пустой/заполненный

                    # Собираем пул кандидатов, проходящих базовые фильтры
                    pool = []
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work_setting(es, preferred_only=preferred_pass):
                            continue
                        if emp.id in assigned_today_ids:                # 1 смена/день
                            continue
                        if violates_pair_zone(emp.full_name, zone, assigned_by_zone_today):
                            continue
                        w = week_count[(emp.id, week_idx)]
                        s = prev_streak[emp.id]
                        if w >= HARD_WEEK_CAP or s >= HARD_STREAK_CAP:  # жёсткие лимиты
                            continue
                        pool.append((emp, es, w, s))

                    if not pool:
                        # создаём «пустой» слот (если его ещё нет), чтобы видно было в UI
                        if shift_obj is None:
                            shift_obj = Shift(location_id=loc.id, date=day, employee_id=None)
                            session.add(shift_obj)
                            existing[(loc.id, day)] = shift_obj
                        continue

                    # --- Спец-приоритеты на выходных ---
                    chosen_emp = None
                    if weekday in (5, 6):
                        # Стаценко на «Мастер классы»: обяз. 1 день в неделю
                        if loc.name == "Мастер классы":
                            if "Аня Стаценко" in SPECIAL_STAFF and week_idx not in special_done_master["Аня Стаценко"]:
                                for emp, es, w, s in pool:
                                    if emp.full_name == "Аня Стаценко":
                                        chosen_emp = emp
                                        special_done_master["Аня Стаценко"].add(week_idx)
                                        break

                        # Для 4 сотрудников: один выходной в целевых локациях
                        if chosen_emp is None and loc.name in SPECIAL_TARGET_SET:
                            for name, rules in SPECIAL_STAFF.items():
                                if rules.get("need_target_once") and week_idx not in special_done_target[name]:
                                    emp_id = emp_id_by_name.get(name)
                                    if emp_id:
                                        for emp, es, w, s in pool:
                                            if emp.id == emp_id:
                                                chosen_emp = emp
                                                special_done_target[name].add(week_idx)
                                                break
                                    if chosen_emp is not None:
                                        break

                    # --- Балансировка и перемешивание, если спец-правила не выбрали кандидата ---
                    if chosen_emp is None:
                        def score(item):
                            emp, es, w, s = item
                            penalty = 0
                            # сильный приоритет тем, у кого недобор до 4 на неделе
                            if w < SOFT_WEEK_TARGET:
                                penalty -= (SOFT_WEEK_TARGET - w) * 20
                            # штрафы за выход за soft-рамки (но в пределах hard)
                            if w >= SOFT_WEEK_TARGET:
                                penalty += (w - SOFT_WEEK_TARGET + 1) * 10   # 4->10, 5->20
                            if s >= SOFT_STREAK_TARGET:
                                penalty += (s - SOFT_STREAK_TARGET + 1) * 40  # 2->40, 3->80
                            # перемешивание локаций в неделю
                            if loc.id in used_loc_week[(emp.id, week_idx)]:
                                penalty += 15  # не хотим ставить в ту же точку на этой неделе
                            # лёгкое выравнивание по общему числу на 2 нед.
                            penalty += total_2w[emp.id]
                            return penalty

                        pool.sort(key=score)
                        chosen_emp = pool[0][0]

                    # --- Записываем назначение ---
                    if shift_obj is None:
                        shift_obj = Shift(location_id=loc.id, date=day, employee_id=chosen_emp.id)
                        session.add(shift_obj)
                        existing[(loc.id, day)] = shift_obj
                    else:
                        shift_obj.employee_id = chosen_emp.id

                    assigned_today_ids.add(chosen_emp.id)
                    assigned_by_zone_today[zone].add(chosen_emp.full_name)
                    week_count[(chosen_emp.id, week_idx)] += 1
                    total_2w[chosen_emp.id] += 1
                    used_loc_week[(chosen_emp.id, week_idx)].add(loc.id)

                    # отметим, если Стаценко стоит в «Мастер классы» (на всякий)
                    if weekday in (5, 6) and chosen_emp.full_name == "Аня Стаценко" and loc.name == "Мастер классы":
                        special_done_master["Аня Стаценко"].add(week_idx)
                    if weekday in (5, 6) and loc.name in SPECIAL_TARGET_SET and chosen_emp.full_name in SPECIAL_STAFF:
                        special_done_target[chosen_emp.full_name].add(week_idx)

            # --- Обновляем серии к следующему дню ---
            new_streak = defaultdict(int)
            for e in employees:
                new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
            prev_streak = new_streak

        session.flush()
        rows_after = session.query(Shift).count()
        session.commit()
        return None, dates
    finally:
        session.close()
