from app.database.database import SessionLocal
from app.database.models import Employee, EmployeeSetting

def seed_employee_settings():
    db = SessionLocal()

    settings_data = {
        "Алиса Бойцова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": "Мастер классы",
            "notes": None
        },
        "Аня Стаценко": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": "Мастер классы",
            "restricted_locations": "Луномосик,Авиапарк",
            "notes": "Не ставить вместе со Стрижкиной в зоне main_building"
        },
        "Виктория Молчанова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": "Луномосик,Авиапарк",
            "notes": None
        },
        "Катя Пискарева": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": "Луномосик,Мастер классы,Прекрасный помогатор",
            "notes": None
        },
        "Катя Стрижкина": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": "Москвариум 1,Москвариум 0,Мультпарк",
            "restricted_locations": None,
            "notes": "Редко (раз в 2 месяца) можно ставить в Авиапарк. Не ставить вместе со Стаценко в зоне main_building"
        },
        "Кристина Колосова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": "Луномосик,Мастер классы,Прекрасный помогатор",
            "notes": None
        },
        "Лиза Терехова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": None,
            "notes": None
        },
        "Мария Савельева": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": None,
            "restricted_locations": None,
            "notes": None
        },
        "Настя Губарева": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": "Мастер классы",
            "restricted_locations": "Луномосик,Авиапарк",
            "notes": None
        },
        "Полина Колисниченко": {
            "max_shifts_per_week": 0,
            "unavailable_days": "2025-08-01,2025-08-31",
            "preferred_locations": "Мастер классы,Прекрасный помогатор",
            "restricted_locations": None,
            "notes": "Больничный — не ставим в график до осени"
        },
        "Саша Попова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": "Луномосик",
            "restricted_locations": "Москвариум 1,Москвариум 0,Мастер классы,Прекрасный помогатор,Мультпарк,Авиапарк,Москвариум 3",
            "notes": None
        },
        "София Баринова": {
            "max_shifts_per_week": 4,
            "unavailable_days": None,
            "preferred_locations": "Прекрасный помогатор,Луномосик,Авиапарк",
            "restricted_locations": None,
            "notes": "Иногда можно ставить в Мультпарк"
        }
    }

    all_employees = db.query(Employee).all()

    for employee in all_employees:
        config = settings_data.get(employee.name)
        if config:
            setting = EmployeeSetting(
                employee_id=employee.id,
                max_shifts_per_week=config["max_shifts_per_week"],
                max_shifts_per_2weeks=None,
                unavailable_days=config["unavailable_days"],
                preferred_locations=config["preferred_locations"],
                restricted_locations=config["restricted_locations"],
                notes=config["notes"]
            )
            db.add(setting)

    db.commit()
    db.close()
