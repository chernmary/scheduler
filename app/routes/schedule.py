from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.scheduler.generator import generate_schedule
from datetime import date, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/schedule", response_class=HTMLResponse)
async def show_schedule(request: Request):
    schedule, dates = generate_schedule(start_date=date(2025, 8, 18))
    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "schedule": schedule,
        "dates": dates
    })

@router.post("/schedule")
async def regenerate_schedule(request: Request):
    # дата ближайшего понедельника
    today = date.today()
    start = today - timedelta(days=today.weekday()) + timedelta(days=7 if today.weekday() > 0 else 0)
    generate_schedule(start_date=start)
    return RedirectResponse(url="/schedule", status_code=303)
