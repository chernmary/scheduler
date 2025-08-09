# app/routes/schedule.py
from datetime import date, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule  # поправь путь, если у тебя другой

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def is_admin(request: Request) -> bool:
    """Проверка, вошёл ли администратор."""
    return request.cookies.get("auth") == "admin_logged_in"

@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request):
    """Отображает график работы."""
    db = SessionLocal()
    try:
        start_date = date.today()
        dates = [start_date + timedelta(days=i) for i in range(14)]

        locations = db.query(Location).order_by(Location.id).all()
        shifts = (
            db.query(Shift)
              .filter(Shift.date.between(dates[0], dates[-1]))
              .all()
        )

        # (location_id, date) -> имя сотрудника
        shift_index = {
            (s.location_id, s.date): s.employee.full_name if s.employee else ""
            for s in shifts
        }

        schedule_data = {
            loc.name: [shift_index.get((loc.id, d), "") for d in dates]
            for loc in locations
        }

        employees = db.query(Employee).order_by(Employee.full_name).all()

        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "dates": dates,
                "schedule": schedule_data,
                "employees": employees,
                "is_admin": is_admin(request),
            },
        )
    finally:
        db.close()

@router.post("/schedule/generate")
def schedule_generate(request: Request):
    """Генерация нового графика (только для админа)."""
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    today = date.today()
    # ближайший понедельник
    start = today + timedelta(days=(7 - today.weekday()) % 7)
    generate_schedule(start, weeks=2)

    return RedirectResponse(url="/schedule", status_code=302)
