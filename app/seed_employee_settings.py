from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Employee, Location, EmployeeSetting

db: Session = SessionLocal()

# Удалим старые настройки, если сидер запускается повторно
db.query(EmployeeSetting).delete()

# Получаем все локации и превращаем в словарь по названию
locations = {loc.name: loc.id for loc in db.query(Location).all()}
employees = {emp.full_name: emp.id for emp in db.query(Employee).all()}

settings_data = [
    {"name": "Алиса Бойцова", "restricted": ["Мастер классы"]},

    {
        "name": "Аня Стаценко",
        "preferred": ["Мастер классы"],
        "allowed": ["Москвариум 1", "Москвариум 0", "Москвариум 3", "Мультпарк", "Мастер классы"]
    },

    {"name": "Виктория Молчанова", "restricted": ["Луномосик", "Авиапарк"]},

    {"name": "Катя Пискарева", "restricted": ["Луномосик", "Мастер классы", "Прекрасный помогатор"]},

    {
        "name": "Катя Стрижкина",
        "preferred": ["Москвариум 1", "Москвариум 0", "Мультпарк"],
        "allowed": ["Москвариум 1", "Москвариум 0", "Мультпарк", "Авиапарк"]
    },

    {"name": "Кристина Колосова", "restricted": ["Луномосик", "Мастер классы", "Прекрасный помогатор"]},

    {"name": "Лиза Терехова"},  # Без ограничений

    {"name": "Мария Савельева"},  # Без ограничений

    {
        "name": "Настя Губарева",
        "preferred": ["Мастер классы"],
        "restricted": ["Луномосик", "Авиапарк"]
    },

    {
        "name": "Полина Колисниченко",
        "preferred": ["Мастер классы", "Прекрасный помогатор"],
        "note": "На больничном до ноября"
    },

    {"name": "Саша Попова", "allowed": ["Луномосик"]},

    {
        "name": "София Баринова",
        "allowed": ["Прекрасный помогатор", "Луномосик", "Авиапарк", "Мультпарк"]
    },
]

for setting in settings_data:
    emp_id = employees.get(setting["name"])
    if not emp_id:
        continue

    allowed_ids = set(locations.values())  # По умолчанию разрешены все

    if "allowed" in setting:
        allowed_ids = {locations[loc] for loc in setting["allowed"]}

    if "restricted" in setting:
        restricted_ids = {locations[loc] for loc in setting["restricted"]}
        allowed_ids -= restricted_ids

    for loc_id in allowed_ids:
        db.add(EmployeeSetting(
            employee_id=emp_id,
            location_id=loc_id,
            is_allowed=True,
            is_preferred=(loc_id in {locations.get(loc) for loc in setting.get("preferred", [])})
        ))

    for loc in setting.get("restricted", []):
        loc_id = locations.get(loc)
        if loc_id not in allowed_ids:
            db.add(EmployeeSetting(
                employee_id=emp_id,
                location_id=loc_id,
                is_allowed=False,
                is_preferred=False
            ))

db.commit()
db.close()
