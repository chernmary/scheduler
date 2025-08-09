from app.database import SessionLocal
from app.models import Employee, EmployeeSetting, Location

def norm_name(s: str) -> str:
    return s.replace("ё", "е").replace("Ё", "Е").strip()

def _to_set(csv_or_none: str | None):
    if not csv_or_none:
        return set()
    return {x.strip() for x in csv_or_none.split(",") if x.strip()}

def seed_employee_settings():
    db = SessionLocal()
    try:
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
            # ВАЖНО: имя можно писать с Е, нормализуем ниже
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
                "preferred_locations": "Мастер классы,Прекрасный помогатор",
                "restricted_locations": None,
            },
            "Саша Попова": {
                "preferred_locations": "Луномосик",
                "restricted_locations": "Москвариум 1,Москвариум 0,Мастер классы,Прекрасный помогатор,Мультпарк,Авиапарк,Москвариум 3",
            },
            # 🔧 Исправлено: Баринова НЕ допущена в Москвариумы, МК и Мультпарк
            "София Баринова": {
                "preferred_locations": "Прекрасный помогатор,Луномосик,Авиапарк",
                "restricted_locations": "Москвариум 1,Москвариум 0,Москвариум 3,Мастер классы,Мультпарк",
            },
        }

        employees = db.query(Employee).all()
        locations = db.query(Location).all()

        # нормализованный словарь конфигов (ё=е)
        cfg_by_name = {norm_name(k): v for k, v in settings_data.items()}
        loc_names = {l.name for l in locations}  # на всякий случай

        for emp in employees:
            cfg = cfg_by_name.get(norm_name(emp.full_name))
            # перезаписываем настройки сотрудника (не копим старые)
            db.query(EmployeeSetting).filter(EmployeeSetting.employee_id == emp.id).delete()

            preferred = _to_set(cfg["preferred_locations"]) if cfg else set()
            restricted = _to_set(cfg["restricted_locations"]) if cfg else set()

            for loc in locations:
                is_allowed = (loc.name not in restricted) if cfg else True
                is_preferred = (loc.name in preferred) if cfg else False

                db.add(EmployeeSetting(
                    employee_id=emp.id,
                    location_id=loc.id,
                    is_allowed=is_allowed,
                    is_preferred=is_preferred,
                ))

        db.commit()
        print("[SEED_SETTINGS] OK: employee_settings filled (overwritten)")
    finally:
        db.close()
