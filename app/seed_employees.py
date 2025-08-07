from app.models import Employee
from app.database import SessionLocal
from sqlalchemy.exc import IntegrityError


def seed_employees():
    session = SessionLocal()

    employees_data = [
        {"full_name": "Саша Попова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "София Баринова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Полина Колисниченко", "is_helper": False, "on_sick_leave": True},
        {"full_name": "Катя Стрижкина", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Аня Стаценко", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Катя Пискарёва", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Вика Молчанова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Лиза Терехова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Кристина Колосова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Алиса Бойцова", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Маша Савельева", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Юля Мелентьева", "is_helper": False, "on_sick_leave": False},
        {"full_name": "Настя Губарева", "is_helper": False, "on_sick_leave": False},
    ]

    for emp in employees_data:
        existing = session.query(Employee).filter_by(full_name=emp["full_name"]).first()
        if not existing:
            session.add(Employee(**emp))

    try:
        session.commit()
        print("Сотрудники успешно добавлены!")
    except IntegrityError:
        session.rollback()
        print("Ошибка при добавлении сотрудников.")
    finally:
        session.close()
