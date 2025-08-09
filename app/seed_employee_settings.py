# app/seed_employee_settings.py
from app.database import SessionLocal
from app.models import Employee, EmployeeSetting, Location

def _to_set(csv_or_none: str | None):
    if not csv_or_none:
        return set()
    return {s.strip() for s in csv_or_none.split(",") if s.strip()}

def seed_employee_settings():
    db = SessionLocal()
    try:
        # Имя -> конфиг (текущая структура из твоего сида)
        settings_data = {
            "Алиса Бойцова": {
                "preferred_locations": None,
                "restricted_locations": "Мастер классы",
            },
            "Аня Стаценко": {
                "preferred_locations": "Мастер классы",
                "restricted_locations": "Луномосик,Авиапарк",
            },
            "Виктория Молчанова": {
                "preferred_locations": None,
                "restricted_locations": "Луномосик,Авиапарк",
            },
            "Катя Пискарева": {
                "preferred_locations": None,
                "restricted_locations": "Луномосик,Мастер классы,Прекрасный помогатор",
            },
            "Катя Стрижкина": {
                "preferred_locations": "Москвариум 1,Москвариум 0,Мультпарк",
                "restricted_locations": None,
            },
            "Кристина Колосова": {
                "preferred_locations": None,
                "restricted_locations": "Луномосик,Мастер классы,Прекрасный помогатор",
            },
            "Лиза Терехова": {
                "preferred_locations": None,
                "restricted_locations": None,
            },
            "Мария Савельева": {
                "preferred_locations": None,
                "restricted_locations": None,
            },
            "Настя Губарева": {
                "preferred_locations": "Мастер классы",
                "restricted_locations": "Луномосик,Авиапарк",
            },
            "Полина Колисниченко": {
                # на больничном — можешь вообще не создавать ей настроек,
                # но оставим пустые, чтобы логика была единообразной
                "preferred_locations": "Мастер классы,Прекрасный помогатор",
                "restricted_locations": None,
            },
            "Саша Попова": {
                "preferred_locations": "Луномосик",
                "restricted_locations": "Москвариум 1,Москвариум 0,Мастер классы,Прекрасный помогатор,Мультпарк,Авиапарк,Москвариум 3",
            },
            "София Баринова": {
                "preferred_locations": "Прекрасный помогатор,Луномосик,Авиапарк",
                "restricted_locations": None,
            },
        }

        employees = db.query(Employee).all()
        locations = db.query(Location).all()
        loc_by_name = {l.name.strip(): l for l in locations}

        # очистку существующих настроек НЕ делаю; если надо — раскомментируй:
        # db.query(EmployeeSetting).delete()

        for emp in employees:
            cfg = settings_data.get(emp.full_name)  # ⚠️ именно full_name
            preferred = _to_set(cfg["preferred_locations"]) if cfg else set()
            restricted = _to_set(cfg["restricted_locations"]) if cfg else set()

            for loc in locations:
                # is_allowed: всё, что не в restricted
                is_allowed = (loc.name not in restricted) if cfg else True
                # is_preferred: только те, что явно перечислены в preferred
                is_preferred = (loc.name in preferred) if cfg else False

                db.add(EmployeeSetting(
                    employee_id=emp.id,
                    location_id=loc.id,
                    is_allowed=is_allowed,
                    is_preferred=is_preferred,
                ))

        db.commit()
        print("[SEED_SETTINGS] OK: employee_settings filled")
    finally:
        db.close()
