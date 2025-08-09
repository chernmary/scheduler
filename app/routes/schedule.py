from datetime import date, timedelta, datetime
import sys

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete  # <— нужно для очистки диапазона при сохранении

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule  # persist=True/False (+ respect_existing)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

def log(*args):
    print("[VIEW]", *args, file=sys.stdout, flush=True)

def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"

def nearest_monday(today: date) -> date:
    # всегда следующий понедельник (если сегодня понедельник — берём через 7 дней)
    days = (7 - today.weekday()) % 7
    return today + timedelta(days=days or 7)

def make_dates_block(start: date, days: int = 14):
    all_days = [start + timedelta(d) for d in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]
    raw = [d.isoformat() for d in all_days]
    return all_days, pretty, raw

@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/schedule", status_code=302)
    resp.delete_cookie("auth")  # реально очищаем куку админа
    return resp

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
                "is_preview": False,
                "readonly": False,
                "start_iso": start_date.isoformat(),
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
        start_param = (the_date - timedelta(days=the_date.weekday())).isoformat()
        return RedirectResponse(url=f"/schedule?start={start_param}", status_code=302)
    finally:
        db.close()

@router.post("/schedule/generate")
def schedule_generate(request: Request):
    """
    Предпросмотр: генерируем на 2 недели от ближайшего понедельника, НИЧЕГО не пишем в БД,
    полностью игнорируем старые записи (respect_existing=False), и показываем результат.
    """
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    start = nearest_monday(date.today())

    # ЧИСТЫЙ предпросмотр (без учёта старых смен)
    preview, _ = generate_schedule(start, weeks=2, persist=False, respect_existing=False)
    log("generate_preview", start.isoformat(), "weeks=2", f"slots={len(preview)}")

    dates, pretty, raw = make_dates_block(start, days=14)

    db = SessionLocal()
    try:
        locations = db.query(Location).order_by(Location.order).all()
        employees = db.query(Employee).order_by(Employee.full_name).all()
        locations_map = {loc.name: loc.id for loc in locations}

        # Собираем таблицу из предпросмотра
        table = {loc.name: ["" for _ in dates] for loc in locations}
        index_by_date = {d: i for i, d in enumerate(dates)}
        loc_name_by_id = {l.id: l.name for l in locations}

        for item in preview:
            d = item["date"]
            loc_id = item["location_id"]
            emp_name = item["employee_name"] or ""
            if d in index_by_date and loc_id in loc_name_by_id:
                table[loc_name_by_id[loc_id]][index_by_date[d]] = emp_name

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
                "is_preview": True,   # показываем плашки предпросмотра в шаблоне
                "readonly": False,    # ВАЖНО: в предпросмотре можно редактировать
                "start_iso": start.isoformat(),  # понадобится для /schedule/save
            },
        )
    finally:
        db.close()

@router.post("/schedule/save")
async def schedule_save(
    request: Request,
    start_iso: str = Form(...),
):
    """
    Сохраняем текущий предпросмотр:
    1) чистим все Shift в выбранном 14-дневном диапазоне,
    2) записываем то, что выбрано в селектах (имена полей: emp_<YYYY-MM-DD>_<location_id>).
    """
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    try:
        start_date = datetime.fromisoformat(start_iso).date()
    except ValueError:
        start_date = nearest_monday(date.today())

    dates, _, _ = make_dates_block(start_date, days=14)
    form = await request.form()

    db = SessionLocal()
    try:
        locations = db.query(Location).order_by(Location.order).all()
        loc_ids = [l.id for l in locations]

        # 1) удаляем старые записи этого диапазона
        db.execute(
            delete(Shift).where(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
            )
        )

        # 2) добавляем выбранные в селектах
        new_objects = []
        for d in dates:
            d_iso = d.isoformat()
            for loc_id in loc_ids:
                key = f"emp_{d_iso}_{loc_id}"
                val = form.get(key, "")
                if not val:
                    continue
                try:
                    emp_id = int(val)
                except ValueError:
                    continue
                new_objects.append(Shift(date=d, location_id=loc_id, employee_id=emp_id))

        if new_objects:
            db.add_all(new_objects)

        db.commit()
        return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)
    finally:
        db.close()
