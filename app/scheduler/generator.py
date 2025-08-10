import logging
import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional, Dict, Set, Tuple, List

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Employee, EmployeeSetting, Location, Shift

logger = logging.getLogger("scheduler")

WEEKEND_ONLY_LOCATIONS: Set[str] = {"Луномосик", "Авиапарк", "Москвариум 3"}
CONFLICT_PAIR: Set[str] = {"Катя Стрижкина", "Аня Стаценко"}

SOFT_WEEK_TARGET = 4
HARD_WEEK_CAP = 5
SOFT_STREAK_TARGET = 2
HARD_STREAK_CAP = 3

SPECIAL_TARGET_SET: Set[str] = {"Москвариум 1", "Москвариум 0", "Мультпарк"}
SPECIAL_STAFF: Dict[str, dict] = {
    "Катя Стрижкина": {"need_target_once": True,  "need_master_once": False},
    "Настя Губарева": {"need_target_once": True,  "need_master_once": False},
    "Лиза Терехова":  {"need_target_once": True,  "need_master_once": False},
    "Аня Стаценко":   {"need_target_once": True,  "need_master_once": True},
    "Алиса Бойцова":  {"forbid_weekend": {"Москвариум 0", "Москвариум 1"}},
}

def can_work_setting(es: Optional[EmployeeSetting], preferred_only: bool) -> bool:
    if preferred_only:
        return es is not None and es.is_allowed and getattr(es, "is_preferred", False)
    return es is None or es.is_allowed

def violates_pair_zone(emp_name: str, zone: str, by_zone_today: Dict[str, Set[str]]) -> bool:
    if emp_name not in CONFLICT_PAIR:
        return False
    others = CONFLICT_PAIR - {emp_name}
    return any(o in by_zone_today.get(zone, set()) for o in others)

def load_data(session: Session):
    employees: List[Employee] = (
        session.query(Employee).filter(Employee.is_active == True).order_by(Employee.full_name).all()
    )
    locations: List[Location] = session.query(Location).order_by(Location.order).all()
    settings = session.query(EmployeeSetting).all()

    settings_map: Dict[Tuple[int, int], EmployeeSetting] = {(s.employee_id, s.location_id): s for s in settings}

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

    logger.info("Data loaded: employees=%d, locations=%d, settings=%d", len(employees), len(locations), len(settings))
    return employees, settings_map, locations, weekend_only_emp

def generate_schedule(start: date, weeks: int = 2, persist: bool = True):
    logger.info("generate_schedule: start=%s weeks=%s persist=%s", start.isoformat(), weeks, persist)
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]
        logger.info("Dates range: %s .. %s (%d days)", dates[0].isoformat(), dates[-1].isoformat(), len(dates))

        if persist:
            deleted = session.query(Shift).filter(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
                Shift.status == "draft",
            ).delete(synchronize_session=False)
            session.commit()
            logger.info("Old drafts deleted: %s", deleted)

        week_count: Dict[Tuple[int, int], int] = defaultdict(int)
        total_2w: Dict[int, int] = defaultdict(int)
        prev_streak: Dict[int, int] = defaultdict(int)
        used_loc_week: Dict[Tuple[int, int], Set[int]] = defaultdict(set)
        special_done_target: Dict[str, Set[int]] = defaultdict(set)
        special_done_master: Dict[str, Set[int]] = defaultdict(set)

        total_created = 0

        for wstart in range(0, total_days, 7):
            week_dates = dates[wstart:wstart + 7]
            sorted_week_dates = sorted(week_dates, key=lambda d: 0 if d.weekday() in (5, 6) else 1)

            for day in sorted_week_dates:
                week_idx = (day - start).days // 7
                weekday = day.weekday()

                assigned_today_ids: Set[int] = set()
                assigned_by_zone_today: Dict[str, Set[str]] = defaultdict(set)

                for loc in locations:
                    if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                        continue

                    zone = loc.zone
                    chosen_emp: Optional[Employee] = None

                    for preferred_pass in (True, False):
                        if chosen_emp is not None:
                            break

                        pool: List[Tuple[Employee, Optional[EmployeeSetting], int, int]] = []
                        for emp in employees:
                            es = settings_map.get((emp.id, loc.id))
                            if not can_work_setting(es, preferred_only=preferred_pass):
                                continue
                            if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                continue
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

                        if weekday in (5, 6):
                            if (loc.name == "Мастер классы"
                                and SPECIAL_STAFF.get("Аня Стаценко", {}).get("need_master_once")
                                and week_idx not in special_done_master["Аня Стаценко"]):
                                cand = next((e for (e, es, w, s) in pool if e.full_name == "Аня Стаценко"), None)
                                if cand:
                                    chosen_emp = cand
                                    special_done_master["Аня Стаценко"].add(week_idx)

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

                        if chosen_emp is None:
                            def soft_ok(item) -> bool:
                                emp, es, w, s_now = item
                                if weekday not in (5, 6) and weekend_only_emp.get(emp.id, False):
                                    return False
                                return (w < SOFT_WEEK_TARGET) and (s_now < SOFT_STREAK_TARGET)

                            soft_pool = [it for it in pool if soft_ok(it)]
                            use_pool = soft_pool if soft_pool else pool
                            random.shuffle(use_pool)

                            def score(item) -> int:
                                emp, es, w, s_now = item
                                pen = 0
                                if es and getattr(es, "is_preferred", False):
                                    pen -= 40
                                if w < SOFT_WEEK_TARGET:
                                    pen -= (SOFT_WEEK_TARGET - w) * 25
                                if w >= SOFT_WEEK_TARGET:
                                    pen += (w - SOFT_WEEK_TARGET + 1) * 30
                                if s_now >= SOFT_STREAK_TARGET:
                                    pen += (s_now - SOFT_STREAK_TARGET + 1) * 35
                                if loc.id in used_loc_week[(emp.id, week_idx)]:
                                    pen += 50
                                pen += total_2w[emp.id]
                                pen += random.randint(0, 9)
                                return pen

                            chosen_emp = min(use_pool, key=score)[0]

                    if chosen_emp is not None:
                        if persist:
                            session.add(Shift(
                                location_id=loc.id,
                                date=day,
                                employee_id=chosen_emp.id,
                                status="draft",
                            ))
                            total_created += 1

                        assigned_today_ids.add(chosen_emp.id)
                        assigned_by_zone_today[zone].add(chosen_emp.full_name)
                        week_count[(chosen_emp.id, week_idx)] += 1
                        total_2w[chosen_emp.id] += 1
                        used_loc_week[(chosen_emp.id, week_idx)].add(loc.id)

                new_streak: Dict[int, int] = defaultdict(int)
                for e in employees:
                    new_streak[e.id] = (prev_streak[e.id] + 1) if (e.id in assigned_today_ids) else 0
                prev_streak = new_streak

        if persist:
            session.commit()
            logger.info("Generation finished, created draft shifts: %d", total_created)
            return None, dates
        else:
            return [], dates

    except Exception:
        logger.exception("generate_schedule failed")
        raise
    finally:
        session.close()
