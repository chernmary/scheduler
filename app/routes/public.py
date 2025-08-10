@router.post("/schedule/begin_edit", name="schedule_begin_edit")
async def schedule_begin_edit(request: Request, start_iso: str = Form(...)):
    """Ленивое начало редактирования: копируем published → draft, либо генерируем, если нечего копировать"""
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
            # Если нет опубликованного графика — просто генерируем черновик
            from app.scheduler.generator import generate_schedule
            generate_schedule(start_date, weeks=2, persist=True)
            return RedirectResponse(url=f"/schedule?start={start_date.isoformat()}", status_code=302)

        # Чистим draft и копируем published → draft
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
