from datetime import date, timedelta, datetime
from collections import defaultdict

from fastapi import APIRouter, Request, Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Shift, Location, Employee

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def period_dates(start: date, days: int = 7):
    all_days = [start + timedelta(i) for i in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]
    raw = [d.isoformat() for d in all_days]
    return all_days, pretty, raw

@router.get("/admin/archive", response_class=HTMLResponse)
def archive_list(request: Request):
    db: Session = SessionLocal()
    try:
        rows = db.query(Shift.date).filter(Shift.status == "archived").all()
        counter = defaultdict(int)
        for (d,) in rows:
            counter[week_monday(d)] += 1
        weeks = sorted(counter.items(), key=lambda x: x[0], reverse=True)
        return templates.TemplateResponse(
            "archive_list.html",
            {"request": request, "weeks": [{"start": k.isoformat(), "count": v} for k, v in weeks]},
        )
    finally:
        db.close()

@router.get("/admin/archive/{week_start}", response_class=HTMLResponse)
def archive_week(request: Request, week_start: str = Path(...)):
    db: Session = SessionLocal()
    try:
        start_date = datetime.fromisoformat(week_start).date()
        dates, pretty, raw = period_dates(start_date, days=7)
        locations = db.query(Location).order_by(Location.order).all()
        locations_map = {loc.name: loc.id for loc in locations}
        shifts = db.query(Shift).filter(
            Shift.status == "archived",
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).all()
        idx = {(s.location_id, s.date): (s.employee.full_name if s.employee else "") for s in shifts}
        table = {loc.name: [idx.get((loc.id, d), "") for d in dates] for loc in locations}
        employees = db.query(Employee).order_by(Employee.full_name).all()
        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "dates": pretty,
                "raw_dates": raw,
                "schedule": table,
                "employees": employees,
                "locations_map": locations_map,
                "is_admin": False,
                "readonly": True,
                "start_iso": start_date.isoformat(),
            },
        )
    finally:
        db.close()
