from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.scheduler.generator import generate_schedule
from datetime import date

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
