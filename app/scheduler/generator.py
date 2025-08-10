def generate_schedule(start: date, weeks: int = 2, persist: bool = True):
    init_db()
    session = SessionLocal()
    try:
        employees, settings_map, locations, weekend_only_emp = load_data(session)
        emp_by_id = {e.id: e for e in employees}
        emp_id_by_name = {e.full_name: e.id for e in employees}

        total_days = weeks * 7
        dates = [start + timedelta(days=i) for i in range(total_days)]

        # 💡 Очищаем все смены на этот диапазон, чтобы сгенерировать с нуля
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
                    if loc.name in WEEKEND_ONLY_LOCATIONS and weekday not in (5, 6):
                        continue

                    zone = loc.zone
                    shift_obj = None

                    pool: list[tuple[Employee, EmployeeSetting | None, int, int]] = []
                    for emp in employees:
                        es = settings_map.get((emp.id, loc.id))
                        if not can_work_setting(es, preferred_only=preferred_pass):
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
                        if not persist:
                            preview_output.append({"date": day, "location_id": loc.id, "employee_name": None})
                        continue

                    chosen_emp: Employee | None = None

                    if weekday in (5, 6):
                        if loc.name == "Мастер классы" and week_idx not in special_done_master["Аня Стаценко"]:
                            for emp, es, w, s_now in pool:
                                if emp.full_name == "Аня Стаценко":
                                    chosen_emp = emp
                                    special_done_master["Аня Стаценко"].add(week_idx)
                                    break
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
