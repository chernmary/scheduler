from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.run_migrations import run_migrations
from app.database import init_db
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.routes import admin, public, schedule

# 1. Прогоняем миграции
run_migrations()

# 2. Инициализируем базу и сиды
init_db()
seed_locations()
seed_employees()

# 3. Запускаем FastAPI
app = FastAPI()

# 4. Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Подключаем статические файлы и роутеры
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router)
app.include_router(schedule.router)

from fastapi.responses import RedirectResponse

@app.get("/")
def redirect_to_static():
    return RedirectResponse(url="/static/index.html")




