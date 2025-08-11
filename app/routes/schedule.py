import logging
import traceback
from datetime import date, timedelta, datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.database import SessionLocal
from app.models import Shift, Location, Employee
from app.scheduler.generator import generate_schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger("scheduler.view")

RU_WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"


def next_monday(d: date) -> date:
    offs = (7 - d.weekday()) % 7
    return d + timedelta(days=offs or 7)


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def period_dates(start: date, days: int = 14):
    all_days = [start + timedelta(i) for i in range(days)]
    pretty = [d.strftime("%d.%m ") + RU_WD[d.weekday()] for d in all_days]
    raw = [d.isoformat() for d in all_days]
    return all_days, pretty, raw


def week_range(d: date):
    start = week_monday(d)
    end = start + timedelta(days=6)
    return start, end


def weekly_rollover(db: Session, now_dt: datetime):
    tz = ZoneInfo("Europe/Berlin")
    now = now_dt.astimezone(tz)
    if now.weekday() != 6 or now.hour < 16:
        return
    w_start, w_end = week_range(now.date())

    updated = db.query(Shift).filter(
        Shift.status == "published",
        Shift.date >= w_start,
        Shift.date <= w_end,
    ).update({"status": "archived"}, synchronize_session=False)

    db.query(Shift).filter(
        Shift.status == "draft",
        Shift.date >= w_start,
        Shift.date <= w_end,
    ).delete(synchronize_session=False)

    if updated:
        db.commit()


@router.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request, start: Optional[str] = Query(None)):
    db: Session = SessionLocal()
    try:
        weekly_rollover(db, datetime.now(ZoneInfo("Europe/Berlin")))

        today = date.today()
        if start:
            try:
                start_date = datetime.fromisoformat(start).date()
            except ValueError:
                start_date = week_monday(today)
        else:
            start_date = week_monday(today)

        dates, pretty, raw = period_dates(start_date, days=14)
        has_any_current = db.query(Shift).filter(
            Shift.status.in_(["draft", "published"]),
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).first() is not None

        locations = db.query(Location).order_by(Location.order).all()
        locations_map = {loc.name: loc.id for loc in locations}

        has_draft = db.query(Shift).filter(
            Shift.status == "draft",
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).first() is not None

        if is_admin(request):
            basis_status = "draft" if has_draft else "published"
            shifts = db.query(Shift).filter(
                Shift.status == basis_status,
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
            ).all()
        else:
            shifts = db.query(Shift).filter(
                Shift.status == "published",
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
            ).all()

        idx = {(s.location_id, s.date): (s.employee.full_name if s.employee else "") for s in shifts}
        table = {loc.name: [idx.get((loc.id, d), "") for d in dates] for loc in locations}
        employees = db.query(Employee).order_by(Employee.full_name).all()

        next_week_start = start_date + timedelta(days=7)
        next_week_end = next_week_start + timedelta(days=6)
        has_any_next = db.query(Shift).filter(
            Shift.date >= next_week_start,
            Shift.date <= next_week_end,
            Shift.status.in_(["draft", "published"]),
        ).first() is not None

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
                "start_iso": start_date.isoformat(),
                "readonly": not is_admin(request),
                "is_preview": is_admin(request) and has_draft,
                "can_generate_next": is_admin(request) and (not has_any_next),
                "is_empty_schedule": is_admin(request) and (not has_any_current),
            },
        )
    finally:
        db.close()


@router.post("/schedule/begin_edit", name="schedule_begin_edit")
async def schedule_begin_edit(request: Request, start_iso: str = Form(...)):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    try:
        start_date = datetime.fromisoformat(start_iso).date()
    except ValueError:
        start_date = week_monday(date.today())

    dates, _, _ = period_dates(start_date, days=14)
    db: Session = SessionLocal()
    try:
        pubs = db.query(Shift).filter(
            Shift.status == "published",
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).all()

        if not pubs:
            try:
                generate_schedule(start_date, weeks=2, persist=True)
            except Exception:
                logger.exception("Generation during begin_edit FAILED")
                return HTMLResponse(
                    f"<h2>Ошибка генерации</h2><pre>{traceback.format_exc()}</pre>",
                    status_code=500,
                )
            return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

        db.query(Shift).filter(
            Shift.status == "draft",
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).delete(synchronize_session=False)

        for s in pubs:
            db.add(Shift(
                date=s.date,
                location_id=s.location_id,
                employee_id=s.employee_id,
                status="draft",
            ))
        db.commit()
        return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)
    finally:
        db.close()


@router.post("/schedule/generate_next", name="schedule_generate_next")
def schedule_generate_next(request: Request, start_iso: str = Form(...)):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    try:
        start_date = datetime.fromisoformat(start_iso).date()
    except ValueError:
        start_date = week_monday(date.today())

    next_week_start = start_date + timedelta(days=7)
    try:
        generate_schedule(next_week_start, weeks=1, persist=True)
        return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)
    except Exception:
        logger.exception("Generation of next week FAILED")
        return HTMLResponse(f"<h2>Ошибка генерации следующей недели</h2><pre>{traceback.format_exc()}</pre>", status_code=500)


@router.post("/schedule/save", name="schedule_save")
async def schedule_save(request: Request, start_iso: str = Form(...)):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    try:
        start_date = datetime.fromisoformat(start_iso).date()
    except ValueError:
        start_date = week_monday(date.today())

    dates, _, _ = period_dates(start_date, days=14)
    form = await request.form()

    db: Session = SessionLocal()
    try:
        # Проверка: есть ли хоть одно поле decisions в форме
        has_decisions = any(key.startswith("decisions[") for key in form.keys())

        if not has_decisions:
            # Просто переводим все черновики в published
            db.query(Shift).filter(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
                Shift.status == "draft"
            ).update({"status": "published"}, synchronize_session=False)
            db.commit()
            return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

        # Если форма с данными — работаем по старой логике
        locations = db.query(Location).order_by(Location.order).all()
        loc_ids = [l.id for l in locations]

        db.execute(
            delete(Shift).where(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
                Shift.status.in_(["published", "draft"]),
            )
        )

        new_published = []
        for d in dates:
            d_iso = d.isoformat()
            for loc_id in loc_ids:
                key = f"decisions[{d_iso}][{loc_id}]"
                val = form.get(key)
                if not val:
                    continue
                try:
                    emp_id = int(val)
                except ValueError:
                    continue
                new_published.append(
                    Shift(date=d, location_id=loc_id, employee_id=emp_id, status="published")
                )

        db.add_all(new_published)
        for s in new_published:
            db.add(
                Shift(
                    date=s.date,
                    location_id=s.location_id,
                    employee_id=s.employee_id,
                    status="draft",
                )
            )

        db.commit()
        return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)
    finally:
        db.close()
