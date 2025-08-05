
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import date, timedelta
from app.database import SessionLocal
from app.models import Shift, Assignment
from openpyxl import Workbook

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/admin/export")
def export_schedule(db: Session = Depends(get_db)):
    start = date.today()
    end = start + timedelta(days=14)
    shifts = db.query(Shift).filter(Shift.date >= start, Shift.date <= end).all()

    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "Локация", "Смена", "Сотрудники"])
    for shift in shifts:
        emp_names = ", ".join(a.employee.full_name for a in shift.assignments)
        ws.append([shift.date.strftime("%d.%m"), shift.location, shift.shift_type, emp_names])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              headers={"Content-Disposition": "attachment; filename=schedule.xlsx"})
