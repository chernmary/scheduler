from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.run_migrations import run_migrations
from app.database import init_db, engine
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.routes import admin, public, schedule
from app.models import ArchivedShift

# Миграции и сиды
run_migrations()
init_db()
seed_locations()
seed_employees()

# Создадим таблицу архива, если её нет
try:
    ArchivedShift.__table__.create(bind=engine, checkfirst=True)
except Exception as e:
    print("ArchivedShift create skipped:", e)

# Запуск приложения
app = FastAPI()

import traceback
from fastapi.responses import PlainTextResponse
from fastapi.requests import Request

# Ловим все необработанные ошибки и выводим их в логи
@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print("\n=== ОШИБКА ===\n", tb_str, "\n=== КОНЕЦ ОШИБКИ ===\n", flush=True)
    return PlainTextResponse(str(exc), status_code=500)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика — ЭТА СТРОКА где необъяснимо теряется скобка 
from fastapi.staticfiles import StaticFiles  # убедись, что импорт есть

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


# Шаблоны
templates = Jinja2Templates(directory="app/templates")

# Роуты
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router, prefix="/api")
app.include_router(schedule.router)

# Корень -> /schedule
@app.get("/", response_class=HTMLResponse)
def render_schedule(request: Request):
    return RedirectResponse(url="/schedule", status_code=303)
