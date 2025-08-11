from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app.models import Employee

router = APIRouter()

class EmployeeIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    is_helper: bool = False
    on_sick_leave: bool = False

class EmployeeOut(BaseModel):
    id: int
    full_name: str
    on_sick_leave: bool

# ---- Список
@router.get("/employees", response_model=List[EmployeeOut])
def list_employees(
    is_helper: Optional[bool] = Query(None, description="True = хелперы, False = основные, None = все"),
    db: Session = Depends(get_db)
):
    q = db.query(Employee)
    if is_helper is not None:
        q = q.filter(Employee.is_helper == is_helper)
    rows = q.order_by(Employee.full_name.asc()).all()
    return [EmployeeOut(id=r.id, full_name=r.full_name, on_sick_leave=r.on_sick_leave) for r in rows]

# ---- Создать
@router.post("/employees", status_code=201)
def create_employee(payload: EmployeeIn, db: Session = Depends(get_db)):
    name = (payload.full_name or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="ФИО слишком короткое (минимум 2 символа)")

    obj = Employee(
        full_name=name,
        is_helper=payload.is_helper,
        on_sick_leave=payload.on_sick_leave,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # вернём ПРИЧИНУ конфликта (обычно уникальный индекс по full_name)
        raise HTTPException(status_code=409, detail=f"Конфликт при сохранении сотрудника: {str(e.orig)}")
    db.refresh(obj)
    return {"id": obj.id}

# ---- Получить одного (нужно фронту для редактирования/перемещения)
@router.get("/employees/{emp_id}", response_model=EmployeeOut)
def get_employee(emp_id: int, db: Session = Depends(get_db)):
    obj = db.query(Employee).get(emp_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return EmployeeOut(id=obj.id, full_name=obj.full_name, on_sick_leave=obj.on_sick_leave)

# ---- Обновить
@router.put("/employees/{emp_id}")
def update_employee(emp_id: int, payload: EmployeeIn, db: Session = Depends(get_db)):
    obj = db.query(Employee).get(emp_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    obj.full_name = (payload.full_name or "").strip()
    obj.is_helper = payload.is_helper
    obj.on_sick_leave = payload.on_sick_leave

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Конфликт при обновлении сотрудника: {str(e.orig)}")
    return {"ok": True}

# ---- Удалить
@router.delete("/employees/{emp_id}", status_code=204)
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    obj = db.query(Employee).get(emp_id)
    if obj:
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # крайне редко, но вернём текст если FK мешает
            raise HTTPException(status_code=409, detail=f"Конфликт при удалении сотрудника: {str(e.orig)}")
    return

# ---- В хелперы
@router.post("/employees/{emp_id}/to-helper")
def to_helper(emp_id: int, db: Session = Depends(get_db)):
    obj = db.query(Employee).get(emp_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    obj.is_helper = True
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Конфликт при переводе сотрудника: {str(e.orig)}")
    return {"ok": True}

# ---- В основные
@router.post("/helpers/{emp_id}/to-main")
def to_main(emp_id: int, db: Session = Depends(get_db)):
    obj = db.query(Employee).get(emp_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    obj.is_helper = False
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Конфликт при переводе сотрудника: {str(e.orig)}")
    return {"ok": True}
