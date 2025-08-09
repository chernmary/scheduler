from app.models import Employee
from app.database import SessionLocal
from sqlalchemy.exc import IntegrityError

def seed_employees():
    session = SessionLocal()

    # Эталонный список сотрудников (актуальные на сегодня)
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
        {"full_name": "Настя Губарева", "is_helper": False, "on_sick_leave": False},
    ]

    try:
        # Список имён в базе
        existing_names = {emp.full_name for emp in session.query(Employee).all()}
        # Список имён из эталонного сида
        target_names = {emp["full_name"] for emp in employees_data}

        # 1. Добавляем новых и обновляем существующих
        for emp_data in employees_data:
            emp = session.query(Employee).filter_by(full_name=emp_data["full_name"]).first()
            if not emp:
                session.add(Employee(**emp_data))
            else:
                emp.is_helper = emp_data["is_helper"]
                emp.on_sick_leave = emp_data["on_sick_leave"]

        # 2. Удаляем тех, кто есть в базе, но отсутствует в эталоне
        to_delete = existing_names - target_names
        if to_delete:
            session.query(Employee).filter(Employee.full_name.in_(to_delete)).delete(synchronize_session=False)

        session.commit()
        print(f"[seed_employees] Синхронизация завершена. "
              f"Добавлено/обновлено: {len(employees_data)}, удалено: {len(to_delete)}")
    except IntegrityError as e:
        session.rollback()
        print("[seed_employees] Ошибка при синхронизации:", e)
    finally:
        session.close()
