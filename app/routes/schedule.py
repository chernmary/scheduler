from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.scheduler.generator import generate_schedule
from app.models import Shift, Location, Employee

router = APIRouter()

def next_monday(today: date | None = None) -> date:
    if today is None:
        today = date.today()
    shift = (7 - today.weekday()) % 7
    return today if shift == 0 else today + timedelta(days=shift)

@router.post("/schedule/generate_draft")
def generate_draft(db: Session = Depends(get_db)):
    start = next_monday()
    generate_schedule(start=start, weeks=2, persist=True)
    return {"status": "draft_created", "start": str(start)}

@router.post("/schedule/publish")
def publish_schedule(db: Session = Depends(get_db)):
    # берём даты из драфта
    draft_dates = [d for (d,) in db.query(Shift.date).filter(Shift.status == "draft").distinct().all()]
    if not draft_dates:
        raise HTTPException(400, "Нет черновика для публикации")

    # чистим прошлую публикацию на эти даты
    db.query(Shift).filter(Shift.status == "published", Shift.date.in_(draft_dates)).delete(synchronize_session=False)

    # переносим draft -> published
    drafts = db.query(Shift).filter(Shift.status == "draft").all()
    for s in drafts:
        s.status = "published"

    db.commit()
    return {"status": "published", "days": len(draft_dates)}

@router.get("/schedule/draft")
def get_draft(db: Session = Depends(get_db)):
    rows = (
        db.query(Shift, Location, Employee)
          .join(Location, Shift.location_id == Location.id)
          .outerjoin(Employee, Shift.employee_id == Employee.id)
          .filter(Shift.status == "draft")
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
