# app/routes/schedule.py
from datetime import date, timedelta, datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule  # поправь импорт, если путь другой

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Сокращения дней недели по-русски: 0=понедельник ... 6=воскресенье
RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"


def nearest_monday(today: date) -> date:
    """Ближайший понедельник (вперёд, включая сегодня если сегодня пн)."""
    return today + timedelta(days=(7 - today.weekday()) % 7)


def make_dates_block(start: date, days: int = 14):
    """Собираем списки дат: красивые подписи и ISO для форм."""
    all_days = [start + timedelta(d) for d in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]
    raw = [d.isoformat() for d in all_days]
    return all_days, pretty, raw


@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request):
    """Отображает график на 2 недели от ближайшего понедельника."""
    db = SessionLocal()
    try:
        start = nearest_monday(date.today())
        dates, pretty, raw = make_dates_block(start, days=14)

        # Локации (сохраняем порядок по id; при желании — по отдельному полю order)
        locations = db.query(Location).order_by(Location.id).all()
        locations_map = {loc.name: loc.id for loc in locations}

        # Все смены за период
        shifts = (
            db.query(Shift)
            .filter(Shift.date.between(dates[0], dates[-1]))
            .all()
        )

        # Индекс: (location_id, date) -> имя сотрудника
        idx = {
            (s.location_id, s.date): (s.employee.full_name if s.employee else "")
            for s in shifts
        }

        # Таблица: { "Локация": ["Имя", ..., "Имя"] }
        table = {
            loc.name: [idx.get((loc.id, d), "") for d in dates]
            for loc in locations
        }

        employees = db.query(Employee).order_by(Employee.full_name).all()

        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "dates": pretty,         # красивый заголовок колонок: "18.08 пн"
                "raw_dates": raw,        # ISO для форм: "2025-08-18"
                "schedule": table,       # данные ячеек
                "employees": employees,  # список сотрудников для <select>
                "locations_map": locations_map,  # имя локации -> id
                "is_admin": is_admin(request),
            },
        )
    finally:
        db.close()


@router.post("/schedule/update")
def schedule_update(
