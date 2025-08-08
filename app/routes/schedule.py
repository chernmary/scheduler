from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.scheduler.generator import generate_schedule
from datetime import date, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/schedule", response_class=HTMLResponse)
async def show_schedule(request: Request):
    from app.database import SessionLocal
    from app.models import Shift

    session = SessionLocal()
    try:
        start_date = date(2025, 8, 18)
        existing_shifts = session.query(Shift).filter(Shift.date >= start_date).first()

        if not existing_shifts:
            from app.scheduler.generator import generate_schedule
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
                schedule[loc.name].append(shift.employee.full_name if shift else "")

        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "schedule": schedule,
            "dates": formatted_dates
        })
    finally:
        session.close()


@router.post("/schedule")
async def regenerate_schedule(request: Request):
    # дата ближайшего понедельника
    today = date.today()
    start = today - timedelta(days=today.weekday()) + timedelta(days=7 if today.weekday() > 0 else 0)
    generate_schedule(start_date=start)
    return RedirectResponse(url="/schedule", status_code=303)
