from datetime import date, timedelta, datetime
import sys

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule  # теперь умеет persist=False

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

def log(*args):
    print("[VIEW]", *args, file=sys.stdout, flush=True)

def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"

def nearest_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7)

def make_dates_block(start: date, days: int = 14):
    all_days = [start + timedelta(d) for d in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]
    raw = [d.isoformat() for d in all_days]
    return all_days, pretty, raw


@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request, start: str | None = Query(None)):
    """Показываем 14 дней начиная с ?start=YYYY-MM-DD, иначе — ближайший понедельник."""
    db = SessionLocal()
    try:
        if start:
            try:
                start_date = datetime.fromisoformat(start).date()
            except ValueError:
                start_date = nearest_monday(date.today())
        else:
            start_date = nearest_monday(date.today())

        dates, pretty, raw = make_dates_block(start_date, days=14)

        locations = db.query(Location).order_by(Location.order).all()
        locations_map = {loc.name: loc.id for loc in locations}

        shifts = db.query(Shift).filter(Shift.date.between(dates[0], dates[-1])).all()

        idx = {(s.location_id, s.date): (s.employee.full_name if s.employee else "") for s in shifts}
        table = {loc.name: [idx.get((loc.id, d), "") for d in dates] for loc in locations}

        employees = db.query(Employee).order_by(Employee.full_name).all()

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
                # дополнительные флаги не используются шаблоном пока
                "is_preview": False,
                "readonly": False,
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
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    db = SessionLocal()
    try:
        the_date = datetime.fromisoformat(date_str).date()
        shift = db.query(Shift).filter(Shift.location_id == location_id, Shift.date == the_date).one_or_none()
        if shift is None:
            shift = Shift(location_id=location_id, date=the_date)
            db.add(shift)

        shift.employee_id = int(employee_id) if employee_id else None
        db.commit()
        log("update", f"{the_date} loc={location_id} -> emp={shift.employee_id}")
        # вернёмся на тот же диапазон
        start_param = (the_date - timedelta(days=the_date.weekday())).isoformat()
        return RedirectResponse(url=f"/schedule?start={start_param}", status_code=302)
    finally:
        db.close()


@router.post("/schedule/generate")
def schedule_generate(request: Request):
    """
    Предпросмотр: генерируем на 2 недели от ближайшего понедельника, НИЧЕГО не пишем в БД,
    сразу показываем этот диапазон в том же шаблоне.
    ВАЖНО: селекты пока рабочие — если менять, уйдёт запись. На следующем шаге сделаем кнопку «Сохранить»
    и заблокируем селекты в режиме предпросмотра.
    """
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    start = nearest_monday(date.today())

    # Получаем предпросмотр (persist=False) и список дат
    preview, dates_list = generate_schedule(start, weeks=2, persist=False)
    log("generate_preview", start.isoformat(), "weeks=2", f"slots={len(preview)}")

    # Соберём данные для шаблона из предпросмотра
    dates, pretty, raw = make_dates_block(start, days=14)

    # Нам нужны локации и сотрудники для заголовков/селектов
    db = SessionLocal()
    try:
        locations = db.query(Location).order_by(Location.order).all()
        employees = db.query(Employee).order_by(Employee.full_name).all()
        locations_map = {loc.name: loc.id for loc in locations}

        # Пустая таблица: на каждую локацию — 14 ячеек
        table = {loc.name: ["" for _ in dates] for loc in locations}
        index_by_date = {d: i for i, d in enumerate(dates)}  # дата -> индекс колонки

        # Заполним из предпросмотра
        for item in preview:
            d = item["date"]
            loc_id = item["location_id"]
            emp_name = item["employee_name"] or ""
            if d in index_by_date:
                col = index_by_date[d]
                # найдём имя локации
                loc_name = next((l.name for l in locations if l.id == loc_id), None)
                if loc_name is not None:
                    table[loc_name][col] = emp_name

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
                "is_preview": True,   # пока шаблон это не использует, но пригодится следующим шагом
                "readonly": True,     # аналогично
            },
        )
    finally:
        db.close()
