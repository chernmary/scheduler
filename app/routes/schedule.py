import logging
import traceback
from datetime import date, timedelta, datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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
    """
    ВОСКРЕСЕНЬЕ >= 16:00 Europe/Berlin:
    - переводим published текущей недели в archived
    - удаляем draft этой же недели
    """
    tz = ZoneInfo("Europe/Berlin")
    now = now_dt.astimezone(tz)
    if now.weekday() != 6 or now.hour < 16:
        return
    w_start, w_end = week_range(now.date())

    updated = db.query(Shift).filter(
        Shift.status == Shift.STATUS_PUBLISHED,
        Shift.date >= w_start,
        Shift.date <= w_end,
    ).update({"status": "archived"}, synchronize_session=False)

    db.query(Shift).filter(
        Shift.status == Shift.STATUS_DRAFT,
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
            Shift.status.in_([Shift.STATUS_DRAFT, Shift.STATUS_PUBLISHED]),
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).first() is not None

        locations = db.query(Location).order_by(Location.order).all()
        locations_map = {loc.name: loc.id for loc in locations}

        has_draft = db.query(Shift).filter(
            Shift.status == Shift.STATUS_DRAFT,
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).first() is not None

        if is_admin(request):
            basis_status = Shift.STATUS_DRAFT if has_draft else Shift.STATUS_PUBLISHED
            shifts = db.query(Shift).filter(
                Shift.status == basis_status,
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
            ).all()
        else:
            shifts = db.query(Shift).filter(
                Shift.status == Shift.STATUS_PUBLISHED,
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
            Shift.status.in_([Shift.STATUS_DRAFT, Shift.STATUS_PUBLISHED]),
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
            Shift.status == Shift.STATUS_PUBLISHED,
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).all()

        if not pubs:
            # Нет опубликованного — генерируем черновик на окно
            try:
                generate_schedule(start_date, weeks=2, persist=True)
            except Exception:
                logger.exception("Generation during begin_edit FAILED")
                return HTMLResponse(
                    f"<h2>Ошибка генерации</h2><pre>{traceback.format_exc()}</pre>",
                    status_code=500,
                )
            return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

        # Чистим draft и копируем published → draft
        db.query(Shift).filter(
            Shift.status == Shift.STATUS_DRAFT,
            Shift.date >= dates[0],
            Shift.date <= dates[-1],
        ).delete(synchronize_session=False)

        for s in pubs:
            db.add(
                Shift(
                    date=s.date,
                    location_id=s.location_id,
                    employee_id=s.employee_id,
                    status=Shift.STATUS_DRAFT,
                )
            )
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
        return HTMLResponse(
            f"<h2>Ошибка генерации следующей недели</h2><pre>{traceback.format_exc()}</pre>",
            status_code=500
        )


@router.post("/schedule/save", name="schedule_save")
async def schedule_save(request: Request, start_iso: str = Form(...)):
    """
    Публикация:
    - если форма пустая → чистим published в окне, переводим все draft -> published
    - если форма с decisions[...] → пересобираем окно как published (без создания дублей draft)
    Любая ошибка БД возвращается в теле ответа понятным текстом.
    """
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)

    # разбор даты
    try:
        start_date = datetime.fromisoformat(start_iso).date()
    except ValueError:
        start_date = week_monday(date.today())

    dates, _, _ = period_dates(start_date, days=14)
    form = await request.form()

    db: Session = SessionLocal()
    try:
        has_decisions = any(str(k).startswith("decisions[") for k in form.keys())

        if not has_decisions:
            # Форма пустая: публикуем черновики, но сперва удаляем опубликованные (избегаем UNIQUE (date, location_id))
            db.execute(
                delete(Shift).where(
                    Shift.date >= dates[0],
                    Shift.date <= dates[-1],
                    Shift.status == Shift.STATUS_PUBLISHED,
                )
            )
            updated = db.query(Shift).filter(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
                Shift.status == Shift.STATUS_DRAFT,
            ).update({"status": Shift.STATUS_PUBLISHED}, synchronize_session=False)

            db.commit()
            if not updated:
                # Полезный ответ, если публикация нечего не изменила
                return PlainTextResponse(
                    "PUBLISH: нет черновиков в выбранном окне — нечего публиковать.",
                    status_code=400
                )
            return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

        # Форма заполнена: пересобираем окно как published
        locations = db.query(Location).order_by(Location.order).all()
        loc_ids = [l.id for l in locations]

        # Сносим всё окно (и draft, и published)
        db.execute(
            delete(Shift).where(
                Shift.date >= dates[0],
                Shift.date <= dates[-1],
                Shift.status.in_([Shift.STATUS_PUBLISHED, Shift.STATUS_DRAFT]),
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
                    Shift(
                        date=d,
                        location_id=loc_id,
                        employee_id=emp_id,
                        status=Shift.STATUS_PUBLISHED,
                    )
                )

        if new_published:
            db.add_all(new_published)

        db.commit()
        return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

    except IntegrityError as e:
        db.rollback()
        # ВСЕГДА отдаём реальную причину 500
        return PlainTextResponse(
            "PUBLISH_ERROR: IntegrityError\n" + str(e.orig),
            status_code=500
        )
    except Exception:
        db.rollback()
        # Полный traceback, чтобы сразу увидеть место
        return PlainTextResponse(
            "PUBLISH_ERROR: Unexpected\n" + traceback.format_exc(),
            status_code=500
        )
    finally:
        db.close()
