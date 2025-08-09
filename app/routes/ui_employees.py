from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Шаблоны лежат в app/templates
templates = Jinja2Templates(directory="app/templates")

router = APIRouter()

@router.get("/ui/employees", response_class=HTMLResponse)
def employees_page(request: Request):
    return templates.TemplateResponse("employees.html", {"request": request})
