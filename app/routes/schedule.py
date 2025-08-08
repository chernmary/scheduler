from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Employee, Location, Schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/schedule", response_class=HTMLResponse)
def show_schedule(request: Request, error: str = None):
    db: Session = SessionLocal()

    # Загружаем сотрудников и локации
    employees = db.query(Employee).all()
    locations = db.query(Location).all()

    # Заглушка для примера (сюда вставишь логику получения графика из БД)
    schedule_data = {loc.name: [""] * 14 for loc in locations}

    # Список дат в формате дд.мм день недели
    dates = []  # Тут твоя генерация дат
    raw_dates = []  # "Сырой" формат для формы

    # Карта {имя_локации: id}
    locations_map = {loc.name: loc.id for loc in locations}

    # Проверка, админ ли пользователь
    is_admin = request.cookies.get("auth") == "admin_logged_in"

    return templates.TemplateResponse(
        "schedule.html",
        {
            "request": request,
            "schedule_data": schedule_data,
            "dates": dates,
            "raw_dates": raw_dates,
            "employees": employees,
            "locations_map": locations_map,
            "is_admin": is_admin,
            "error": error is not None
        }
    )


@router.post("/schedule/update")
def update_schedule(
    request: Request,
    date_str: str = Form(...),
    location_id: int = Form(...),
    employee_id: int = Form(...)
):
    # Проверяем авторизацию
    if request.cookies.get("auth") != "admin_logged_in":
        return RedirectResponse(url="/schedule", status_code=302)

    db: Session = SessionLocal()

    # Обновляем или создаём запись графика
    schedule_entry = (
        db.query(Schedule)
        .filter(Schedule.date == date_str, Schedule.location_id == location_id)
        .first()
    )
    if schedule_entry:
        schedule_entry.employee_id = employee_id
    else:
        new_entry = Schedule(
            date=date_str,
            location_id=location_id,
            employee_id=employee_id
        )
        db.add(new_entry)

    db.commit()

    return RedirectResponse(url="/schedule", status_code=302)


@router.post("/schedule/generate")
def generate_schedule(request: Request):
    if request.cookies.get("auth") != "admin_logged_in":
        return RedirectResponse(url="/schedule", status_code=302)

    # Здесь будет логика автогенерации графика
    return RedirectResponse(url="/schedule", status_code=302)
