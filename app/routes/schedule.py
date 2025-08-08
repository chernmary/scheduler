from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Employee, Location, Schedule
from datetime import datetime, timedelta
from fastapi import Depends

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Проверка: админ или нет (по куке)
def is_admin_user(request: Request) -> bool:
    return request.cookies.get("is_admin") == "true"

@router.get("/schedule")
def show_schedule(request: Request, db: Session = Depends(get_db)):
    # Получаем все даты
    start_date = datetime.now().date()
    dates = [(start_date + timedelta(days=i)).strftime("%d.%m %A") for i in range(14)]
    raw_dates = [(start_date + timedelta(days=i)).isoformat() for i in range(14)]

    # Получаем список локаций
    locations = db.query(Location).all()
    locations_map = {loc.name: loc.id for loc in locations}

    # Получаем сотрудников
    employees = db.query(Employee).all()

    # Заполняем график (пока пустыми ячейками)
    schedule_data = {loc.name: [""] * len(dates) for loc in locations}

    is_admin = is_admin_user(request)

    return templates.TemplateResponse(
        "schedule.html",
        {
            "request": request,
            "dates": dates,
            "raw_dates": raw_dates,
            "locations_map": locations_map,
            "employees": employees,
            "schedule_data": schedule_data,
            "is_admin": is_admin
        }
    )

@router.post("/schedule/update")
def update_schedule(
    request: Request,
    date_str: str = Form(...),
    location_id: int = Form(...),
    employee_id: int = Form(...),
    db: Session = Depends(get_db)
):
    if not is_admin_user(request):
        return RedirectResponse(url="/schedule", status_code=303)

    # Находим или создаём запись в графике
    schedule_entry = db.query(Schedule).filter_by(date=date_str, location_id=location_id).first()
    if schedule_entry:
        schedule_entry.employee_id = employee_id
    else:
        schedule_entry = Schedule(date=date_str, location_id=location_id, employee_id=employee_id)
        db.add(schedule_entry)

    db.commit()
    return RedirectResponse(url="/schedule", status_code=303)

@router.post("/schedule/generate")
def generate_schedule(request: Request, db: Session = Depends(get_db)):
    if not is_admin_user(request):
        return RedirectResponse(url="/schedule", status_code=303)

    # Здесь будет логика генерации графика
    print("Генерация графика...")
    return RedirectResponse(url="/schedule", status_code=303)
