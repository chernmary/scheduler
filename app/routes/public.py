from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Shift, Location, Employee

router = APIRouter()

@router.get("/schedule")
def get_public_schedule(db: Session = Depends(get_db)):
    rows = (
        db.query(Shift, Location, Employee)
          .join(Location, Shift.location_id == Location.id)
          .outerjoin(Employee, Shift.employee_id == Employee.id)
          .filter(Shift.status == "published")
          .order_by(Shift.date.asc(), Location.order.asc())
          .all()
    )
    return [
        {
            "date": s.date,
            "location": loc.name,
            "employee": emp.full_name if emp else None
        } for (s, loc, emp) in rows
    ]
