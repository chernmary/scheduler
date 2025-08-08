from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.scheduler.generator import generate_schedule
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Shift, Location  # ✅ Добавлен импорт Location

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ✅ Добавлена функция форматирования дат (раньше была неизвестна)
def format_day(d: date) -> str:
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return d.strftime("%d.%m") + " " + days[d.weekday()]


@router.get("/schedule", response_class=HTMLResponse)
async def show_schedule(request: Request):
    session = SessionLocal()
    try:
        start_date = date(2025, 8, 18)
        existing_shifts = session.query(Shift).filter(Shift.date >= start_date).first()

        if not existing_shifts:
            generate_schedule(start=start_date)

        # Загружаем график из базы
        shifts = session.query(Shift).all()
        locations = session.query(Location).order_by(Location.order).all()

        schedule = {}
        dates = sorted(list({s.date for s in shifts}))
        formatted_dates = [format_day(d) for d in dates]

        for loc in locations:
            schedule[loc.name] = []
            for d in dates:
                shift = next((s for s in shifts if s.location_id == loc.id and s.date == d), None)
                schedule[loc.name].append(shift.employee.full_name if shift and shift.employee else "")

        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "schedule": schedule,
            "dates": formatted_dates
        })
    finally:
        session.close()


@router.post("/schedule")
async def regenerate_schedule(request: Request):
    today = date.today()
    start = today - timedelta(days=today.weekday()) + timedelta(days=7 if today.weekday() > 0 else 0)
    generate_schedule(start_date=start)
    return RedirectResponse(url="/schedule", status_code=303)
