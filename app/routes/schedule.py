# app/routes/schedule.py
from datetime import date, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Shift, Location, Employee
# если у тебя другой путь к генератору, поправь импорт ниже
from app.scheduler.generator import generate_schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"

@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request):
    db = SessionLocal()
    try:
        # 14 дней, начиная с сегодня
        start = date.today()
        days = [start + timedelta(days=i) for i in range(14)]
        # локации
        locations = db.query(Location).order_by(Location.id).all()
        # смены за период
        shifts = (
            db.query(Shift)
              .filter(Shift.date.between(days[0], days[-1]))
              .all()
        )
        # индекс для быстрого доступа
        idx = {(s.location_id, s.date): s.employee.full_name if s.employee else "" for s in shifts}
        table = {loc.name: [idx.get((loc.id, d), "") for d in days] for loc in locations}

        employees = db.query(Employee).order_by(Employee.full_name).all()

        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "dates": days,
                "schedule": table,
                "employees": employees,
                "is_admin": is_admin(request),
            },
        )
    finally:
        db.close()

@router.post("/schedule/generate")
def schedule_generate(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)
    today = date.today()
    # ближайший понедельник
    start = today + timedelta(days=(7 - today.weekday()) % 7)
    generate_schedule(start, weeks=2)
    return RedirectResponse(url="/schedule", status_code=302)
