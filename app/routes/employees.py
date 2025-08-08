from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Employee

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def is_admin(request: Request) -> bool:
    return request.cookies.get("auth") == "admin_logged_in"

@router.get("/admin/employees", response_class=HTMLResponse)
def list_employees(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)
    db: Session = SessionLocal()
    employees = db.query(Employee).order_by(Employee.full_name).all()
    return templates.TemplateResponse("employees_list.html", {"request": request, "employees": employees})

@router.get("/admin/employees/{employee_id}", response_class=HTMLResponse)
def employee_detail(request: Request, employee_id: int):
    if not is_admin(request):
        return RedirectResponse(url="/schedule", status_code=302)
    db: Session = SessionLocal()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return HTMLResponse("Сотрудник не найден", status_code=404)
    return templates.TemplateResponse("employee_detail.html", {"request": request, "employee": employee})
