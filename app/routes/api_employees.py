from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

# ⚠️ Предполагается, что в проекте есть get_db, который возвращает SQLAlchemy Session.
# Если у вас другой способ, поправьте импорт ниже.
from app.database import get_db

router = APIRouter()

@router.get("/employees")
def list_employees(
    role: str = Query("main", pattern="^(main|helper)$", description="Фильтр: main или helper"),
    db: Session = Depends(get_db)
):
    """
    Возвращает список сотрудников по роли.
    Ожидаемая таблица employees с полями:
    id, full_name, phone, telegram, birth_date, medbook_expiry, notes, role
    """
    query = text("""        SELECT id, full_name, phone, telegram, birth_date, medbook_expiry, notes
        FROM employees
        WHERE role = :role
        ORDER BY full_name
    """)
    rows = db.execute(query, {"role": role}).mappings().all()
    return [dict(r) for r in rows]
