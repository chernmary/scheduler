from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Shift, Location
from app.scheduler.generator import generate_schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# 🔹 Функция форматирования дат
def format_day(d: date) -> str:
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return d.strftime("%d.%m") + " " + days[d.weekday()]


# 🔹 Определяем ближайший понедельник
def get_next_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


@router.get("/schedule", response_class=HTMLResponse)
async def show_schedule(request: Request):
    session = SessionLocal()
    try:
        start_date = get_next_monday()

        # Проверяем, есть ли смены с этой даты
        existing_shifts = session.query(Shift).filter(Shift.date >= start_date).first()
        if not existing_shifts:
            generate_schedule(start=start_date)

        # Загружаем график
        shifts = session.query(Shift).all()
        locations = session.query(Location).order_by(Location.order).all()

        schedule = {}
        dates = sorted(list({s.date for s in shifts}))
        formatted_dates = [format_day(d) for d in dates]

        for loc in locations:
            schedule[loc.name] = []
            for d in dates:
                shift = next(
                    (s for s in shifts if s.location_id == loc.id and s.date == d),
                    None
                )
                schedule[loc.name].append(
                    shift.employee.full_name if shift and shift.employee else ""
                )

        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "schedule": schedule,
                "dates": formatted_dates
            }
        )
    finally:
        session.close()


@router.post("/schedule")
async def regenerate_schedule(request: Request):
    start = get_next_monday()
    generate_schedule(start=start)
    return RedirectResponse(url="/schedule", status_code=303)
