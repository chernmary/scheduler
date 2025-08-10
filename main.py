from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.run_migrations import run_migrations
from app.database import init_db
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.seed_employee_settings import seed_employee_settings
from app.routes import admin, public, schedule, auth, employees

# --- Миграции и сиды: до создания приложения ---
run_migrations()
init_db()
seed_locations()
seed_employees()
seed_employee_settings()

# --- Приложение ---
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика и шаблоны
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# --- Роутеры ---
from app.routes.ui_employees import router as ui_employees_router

app.include_router(admin.router,    prefix="/admin")  # JSON/админ-API
app.include_router(public.router,   prefix="/api")    # публичный JSON
app.include_router(schedule.router)                   # админские действия расписания (generate/publish)
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(ui_employees_router)               # /ui/employees HTML

# --- Страницы HTML ---

# Страница расписания (HTML) по /schedule
@app.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request):
    # шаблон должен быть: app/templates/schedule.html
    return templates.TemplateResponse("schedule.html", {"request": request})

# Корень -> редирект на /schedule
@app.get("/", response_class=HTMLResponse)
def root_redirect():
    return RedirectResponse(url="/schedule", status_code=303)
