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

# Миграции и сиды — выполняются ДО создания приложения
run_migrations()
init_db()
seed_locations()
seed_employees()
seed_employee_settings()

# Создание приложения
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Шаблоны
templates = Jinja2Templates(directory="app/templates")

# Статика
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Роуты
from app.routes.ui_employees import router as ui_employees_router
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router, prefix="/api")
app.include_router(schedule.router)
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(ui_employees_router)  # ← добавили

# Корень -> /schedule
@app.get("/", response_class=HTMLResponse)
def render_schedule(request: Request):
    return RedirectResponse(url="/schedule", status_code=303)

