from app.database.models import Location
from app.database.database import SessionLocal
from sqlalchemy.exc import IntegrityError


def seed_locations():
    session = SessionLocal()

    locations_data = [
    {"name": "Москвариум 1", "order": 1, "zone": "main_building"},
    {"name": "Москвариум 0", "order": 2, "zone": "main_building"},
    {"name": "Мастер классы", "order": 3, "zone": "main_building"},
    {"name": "Прекрасный помогатор", "order": 4, "zone": "main_building"},
    {"name": "Мультпарк", "order": 5, "zone": "multpark"},
    {"name": "Авиапарк", "order": 6, "zone": "aviapark"},
    {"name": "Москвариум 3", "order": 7, "zone": "main_building"},
    {"name": "Луномосик", "order": 8, "zone": "lunosik"},
]


    for loc in locations_data:
        existing = session.query(Location).filter_by(name=loc["name"]).first()
        if not existing:
            session.add(Location(**loc))

    try:
        session.commit()
        print("Локации успешно добавлены!")
    except IntegrityError:
        session.rollback()
        print("Ошибка при добавлении локаций.")
    finally:
        session.close()

