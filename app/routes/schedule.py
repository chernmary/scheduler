# app/routes/schedule.py
from datetime import date, timedelta, datetime
import sys

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule  # если путь иной — поправь

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

def log(*args):
    print("[VIEW]", *args, file=sys.stdout, flush=True)

def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"

def nearest_monday(today: date) -> date:
    # ближайший понедельник вперёд (если сегодня понедельник — сегодня)
    return today + timedelta(days=(7 - today.weekday()) % 7)

def make_dates_block(start: date, days: int = 14):
    all_days = [start + timedelta(d) for d in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]   # для заголовков колонок
    raw = [d.isoformat() for d in all_days]                                   # для скрытых полей форм
    return all_days, pretty, raw


@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request):
    """Страница графика на 2 недели от ближайшего понедельника."""
    db = SessionLocal()
    try:
        start = nearest_monday(date.today())
        dates, pretty, raw = make_dates_block(start, days=14)

        locations = db.query(Location).order_by(Location.order).all()
        locations_map = {loc.name: loc.id for loc in locations}

        shifts = (
            db.query(Shift)
            .filter(Shift.date.between(dates[0], dates[-1]))
            .all()
        )

        # Индекс (location_id, date) -> имя сотрудника (или "")
        idx = {(s.location_id, s.date): (s.employee.full_name if s.employee else "") for s in shifts}

        # Таблица для шаблона: { "Локация": ["Имя/пусто", ...] }
        table = {loc.name: [idx.get((loc.id, d), "") for d in dates] for loc in locations}

        employees = db.query(Employee).order_by(Employee.full_name).all()

        # короткие логи в Render
        log("range", raw[0], "->", raw[-1], "| locations:", len(locations), "employees:", len(employees), "shifts:", len(shifts))

        return templates.TemplateResponse(
            "schedule.html",
            {
                "request": request,
                "dates": pretty,
                "raw_dates": raw,
                "schedule": table,
                "employees": employees,
                "locations_map": locations_map,
                "is_admin": is_admin(request),
            },
        )
    finally:
        db.close()


@router.post("/schedule/update")
def schedule_update(
    request: Request,
    date_str: str = Form(...),
    location_id: int = Form(...),
    employee_id: str = Form(""),
):
    """Обновление одной ячейки (select -> submit). Только для админа."""
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    db = SessionLocal()
    try:
        the_date = datetime.fromisoformat(date_str).date()

        shift = (
            db.query(Shift)
            .filter(Shift.location_id == location_id, Shift.date == the_date)
            .one_or_none()
        )
        if shift is None:
            shift = Shift(location_id=location_id, date=the_date)
            db.add(shift)

        # пустое значение => очистка сотрудника
        if employee_id == "" or employee_id is None:
            shift.employee_id = None
        else:
            shift.employee_id = int(employee_id)

        db.commit()
        log("update", f"{the_date} loc={location_id} -> emp={shift.employee_id}")
        return RedirectResponse(url="/schedule", status_code=302)
    finally:
        db.close()


@router.post("/schedule/generate")
def schedule_generate(request: Request):
    """Генерация графика на 2 недели от ближайшего понедельника. Только для админа."""
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    today = date.today()
    start = nearest_monday(today)
    generate_schedule(start, weeks=2)
    log("generate_called", start.isoformat(), "weeks=2")

    return RedirectResponse(url="/schedule", status_code=302)
