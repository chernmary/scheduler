from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.run_migrations import run_migrations
from app.database import init_db
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.routes import admin, public, schedule

# Миграции и сиды
run_migrations()
init_db()
seed_locations()
seed_employees()

# Запуск приложения
app = FastAPI()

# CORS (пусть будет)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Подключаем статику
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 🔹 Подключаем шаблоны Jinja2
templates = Jinja2Templates(directory="app/templates")

# 🔹 Подключаем маршруты
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router, prefix="/api")
app.include_router(schedule.router)

# 💖 Когда заходим на сайт — показываем расписание
@app.get("/", response_class=HTMLResponse)
def render_schedule(request: Request):
    return RedirectResponse(url="/schedule", status_code=303)
