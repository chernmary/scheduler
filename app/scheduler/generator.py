# file: app/scheduler/generator.py

from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from app.database.database import SessionLocal, init_db
from app.database.models import Employee, EmployeeSetting, Location, Shift

# 1) Вспомогалка: русские названия дней недели
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def format_day(d: date) -> str:
    """ dd.mm Дд """
    return f"{d.day:02d}.{d.month:02d} {WEEKDAYS[d.weekday()]}"

def load_data(session: Session):
    """Загружаем из базы всех сотрудников, их настройки и локации"""
    employees = session.query(Employee).all()
    settings = {s.employee_id: s for s in session.query(EmployeeSetting).all()}
    locations = session.query(Location).order_by(Location.order).all()
    return employees, settings, locations

def can_work(es: EmployeeSetting, loc_id: int, day: date) -> bool:
    """Проверяем, разрешено ли сотруднику es работать на location_id в день day"""
    # недоступные дни
    if es.unavailable_days:
        if day.isoformat() in es.unavailable_days.split(","):
            return False
    # запрещённые локации
    if es.restricted_locations:
        if str(loc_id) in es.restricted_locations.split(","):
            return False
    # проверяем максимум смен в неделю и в 2 недели
    # (этот подсчёт будет сделан позже в generate)
    return True

def generate_schedule(start: date, weeks: int = 2):
    """Основная функция — генерит расписание на weeks недель, начиная с start"""
    init_db()  # создаём таблицы (если ещё не созданы)
    session = SessionLocal()
    try:
        employees, settings_map, locations = load_data(session)

        # Структуры для учёта сколько смен у каждого сотрудника:
        shifts_count_week = defaultdict(int)
        shifts_count_2weeks = defaultdict(int)

        # Результат: словарь date → list of (Location, Employee)
        schedule = defaultdict(list)

        total_days = weeks * 7
        for offset in range(total_days):
            today = start + timedelta(days=offset)
            week_index = offset // 7  # 0 или 1

            # для каждой локации пытаемся найти сотрудника
            for loc in locations:
                # ищем кандидатов:
                candidates = []
                for emp in employees:
                    es = settings_map.get(emp.id)
                    if not es:
                        continue
                    # 1. можно ли по дню и локации?
                    if not can_work(es, loc.id, today):
                        continue
                    # 2. не превышены ли макс. смены?
                    max_w = es.max_shifts_per_week or 0
                    max_2w = es.max_shifts_per_2weeks or 0
                    if shifts_count_week[(emp.id, week_index)] >= max_w:
                        continue
                    if shifts_count_2weeks[emp.id] >= max_2w:
                        continue
                    candidates.append((emp, es))

                # сортируем: сначала предпочитающие, потом остальные
                candidates.sort(key=lambda pair: pair[1].is_preferred, reverse=True)

                # спец-правило: в Main Building нельзя ставить одновременно Стрижкину и Стаценко
                # (это проверка на «если сегодня уже назначена другая»)
                if loc.zone == "main_building":
                    # если уже назначен кто-то из двух — пропускаем обоих
                    assigned_today = [e.full_name for _, e in schedule[today]]
                    forbidden = {"Катя Стрижкина", "Аня Стаценко"}
                    if forbidden & set(assigned_today):
                        candidates = [c for c in candidates
                                      if c[0].full_name not in forbidden]

                # выбираем первого кандидата (если есть)
                if candidates:
                    chosen, _ = candidates[0]
                    schedule[today].append((loc, chosen))
                    # обновляем счётчики
                    shifts_count_week[(chosen.id, week_index)] += 1
                    shifts_count_2weeks[chosen.id] += 1

        # Печатаем результат
        print(f"\n📅 График с {format_day(start)} на {weeks*7} дней:\n")
        for d in sorted(schedule):
            print(f"{format_day(d)}:")
            for loc, emp in schedule[d]:
                print(f"   • {loc.name}: {emp.full_name}")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    # по умолчанию стартуем с понедельника 18 августа 2025
    generate_schedule(date(2025, 8, 18), weeks=2)

