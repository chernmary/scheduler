from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta

from sqlalchemy import and_
from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def format_day(d: date) -> str:
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return d.strftime("%d.%m") + " " + days[d.weekday()]

def next_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())

def two_week_range() -> list[date]:
    start = next_monday()
    return [start + timedelta(days=i) for i in range(14)]

def archive_past_week(session: SessionLocal, start_curr: date):
    """
    Переносит прошедшую неделю в архив:
    - копирует старые Shift (дата < start_curr) в таблицу archived_shifts
    - удаляет их из активных
    """
    from app.models import ArchivedShift  # таблица архива (см. ниже про миграцию)
    last_week_end = start_curr - timedelta(days=1)
    last_week_start = last_week_end - timedelta(days=6)

    old = session.query(Shift).filter(
        and_(Shift.date >= last_week_start, Shift.date <= last_week_end)
    ).all()
    if not old:
        return

    for s in old:
        session.add(ArchivedShift(
            employee_id=s.employee_id,
            location_id=s.location_id,
            date=s.date
        ))
        session.delete(s)
    session.commit()

@router.get("/schedule", response_class=HTMLResponse)
async def show_schedule(request: Request):
    session = SessionLocal()
    try:
        dates = two_week_range()
        locations = session.query(Location).order_by(Location.order).all()
        shifts = session.query(Shift).filter(Shift.date.in_(dates)).all()

        schedule = {}
        for loc in locations:
            row = []
            for d in dates:
                s = next((x for x in shifts if x.location_id == loc.id and x.date == d), None)
                row.append(s.employee.full_name if s and s.employee else "")
            schedule[loc.name] = row

        return templates.TemplateResponse(
            "schedule.html",
            {"request": request, "schedule": schedule, "dates": [format_day(d) for d in dates]}
        )
    finally:
        session.close()

@router.post("/schedule")
async def regenerate_schedule(request: Request):
    session = SessionLocal()
    try:
        start = next_monday()
        # 1) генерируем на 2 недели (не перезаписывая ручные правки)
        generate_schedule(start=start, weeks=2)
        # 2) архивируем прошедшую неделю
        archive_past_week(session, start_curr=start)
        return RedirectResponse(url="/schedule", status_code=303)
    finally:
        session.close()

# Ручная правка одной ячейки (простая форма/запрос из интерфейса)
@router.post("/schedule/update")
async def update_cell(
    request: Request,
    date_str: str = Form(...),
    location_id: int = Form(...),
    employee_id: int | None = Form(None),
):
    session = SessionLocal()
    try:
        y, m, d = map(int, date_str.split("-"))
        day = date(y, m, d)

        shift = session.query(Shift).filter_by(location_id=location_id, date=day).first()
        if not shift:
            # если слота не было — создадим
            shift = Shift(location_id=location_id, date=day, employee_id=employee_id)
            session.add(shift)
        else:
            shift.employee_id = employee_id
        session.commit()
        return RedirectResponse(url="/schedule", status_code=303)
    finally:
        session.close()
