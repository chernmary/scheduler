
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Shift, Assignment, Employee
from datetime import date, timedelta

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def public_schedule(db: Session = Depends(get_db)):
    today = date.today()
    end = today + timedelta(days=14)
    shifts = db.query(Shift).filter(Shift.date >= today, Shift.date <= end).all()
    output = []
    for shift in shifts:
        output.append({
            "date": shift.date.strftime("%Y-%m-%d"),
            "location": shift.location,
            "type": shift.shift_type,
            "employees": [a.employee.full_name for a in shift.assignments]
        })
    return output
