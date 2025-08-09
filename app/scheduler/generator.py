from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

# Локации, которые работают только по выходным (сб=5, вс=6)
WEEKEND_ONLY = {"Луномосик", "Авиапарк", "Москвариум 3"}

# Конфликтная пара сотрудников
CONFLICT_PAIR = {"Катя Стрижкина", "Аня Стаценко"}

def load_data(session: Session):
    employees = session.query(Employee).filter_by(is_helper=False, on_sick_leave=False).all()
    settings = defaultdict(list)
    for s in session.query(EmployeeSetting).all():
        settings[s.employee_id].append(s)
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations

def can_work(employee, settings_list, location: Location, day: date, week_idx, shifts_count_week, shifts_count_2w, assigned_today, last_zones_today):
    # Уже работает в этот день
    if employee.id in assigned_today:
        return False

    # Конфликтная пара в одной зоне
    if employee.full_name in CONFLICT_PAIR:
        for other_id in assigned_today:
            other_name = assigned_today[other_id]
            if other_name in CONFLICT_PAIR and location.zone in last_zones_today:
                return False

    # Выходные локации в будни
    if location.name in WEEKEND_ONLY and day.weekday() not in (5, 6):
        return False

    # Лимиты
    max_w = getattr(employee, "max_shifts_per_week", None) or 4
    max_2w = getattr(employee, "max_shifts_per_2weeks", None) or 10**6
    if shifts_count_week[(employee.id, week_idx)] >= max_w:
        return False
    if shifts_count_2w[employee.id] >= max_2w:
        return False

    # Последовательные смены
    if employee.id in assigned_today.get("streak_block", set()):
        return False

    # Проверка по allowed/preferred
    allowed_locs = [s.location_id for s in settings_list if s.is_allowed]
    if location.id not in allowed_locs:
        return False

    return True

def generate_schedule(start: date, weeks: int = 2):
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        emp_by_id = {e.id: e for e in employees}
        shifts_count_week = defaultdict(int)
        shifts_count_2w = defaultdict(int)

        existing = {(s.location_id, s.date): s for s in session.query(Shift).filter(Shift.date.in_(dates)).all()}
        schedule = {loc.name: [] for loc in locations}

        # Подсчёт последовательных смен
        last_work_day = defaultdict(lambda: None)
        streak_count = defaultdict(int)

        for offset, day in enumerate(dates):
            week_idx = offset // 7
            assigned_today = {}
            last_zones_today = set()

            for loc in locations:
                if (loc.id, day) in existing:
                    emp_name = existing[(loc.id, day)].employee.full_name if existing[(loc.id, day)].employee else ""
                    schedule[loc.name].append(emp_name)
                    if emp_name:
                        emp_obj = next((e for e in employees if e.full_name == emp_name), None)
                        if emp_obj:
                            assigned_today[emp_obj.id] = emp_name
                            last_zones_today.add(loc.zone)
                    continue

                # Формируем кандидатов
                preferred = []
                allowed = []
                for emp in employees:
                    es_list = settings_map.get(emp.id, [])
                    if not es_list:
                        continue
                    if can_work(emp, es_list, loc, day, week_idx, shifts_count_week, shifts_count_2w, assigned_today, last_zones_today):
                        loc_ids_pref = [s.location_id for s in es_list if s.is_preferred]
                        if loc.id in loc_ids_pref:
                            preferred.append(emp)
                        else:
                            allowed.append(emp)

                # Сортировка кандидатов по нагрузке
                preferred.sort(key=lambda e: (shifts_count_week[(e.id, week_idx)], shifts_count_2w[e.id]))
                allowed.sort(key=lambda e: (shifts_count_week[(e.id, week_idx)], shifts_count_2w[e.id]))

                assigned_id = None
                if preferred:
                    assigned_id = preferred[0].id
                elif allowed:
                    assigned_id = allowed[0].id

                if assigned_id:
                    session.add(Shift(employee_id=assigned_id, location_id=loc.id, date=day))
                    assigned_today[assigned_id] = emp_by_id[assigned_id].full_name
                    last_zones_today.add(loc.zone)
                    shifts_count_week[(assigned_id, week_idx)] += 1
                    shifts_count_2w[assigned_id] += 1
                    schedule[loc.name].append(emp_by_id[assigned_id].full_name)

                    # Обновляем streak
                    if last_work_day[assigned_id] == day - timedelta(days=1):
                        streak_count[assigned_id] += 1
                    else:
                        streak_count[assigned_id] = 1
                    last_work_day[assigned_id] = day

                    # Блокировка, если streak >= 3
                    if streak_count[assigned_id] >= 3:
                        assigned_today.setdefault("streak_block", set()).add(assigned_id)
                else:
                    schedule[loc.name].append("")

        session.commit()
        return schedule, dates
    finally:
        session.close()
