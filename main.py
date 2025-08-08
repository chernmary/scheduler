import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.run_migrations import run_migrations
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.routes import admin, public, schedule, auth  # ← добавили auth

# Запускаем миграции
run_migrations()

# Создаем таблицы, если их нет
Base.metadata.create_all(bind=engine)

# Засеваем базу начальными данными
seed_locations()
seed_employees()

app = FastAPI()

# Подключаем роуты
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router, prefix="/api")
app.include_router(schedule.router)
app.include_router(auth.router)  # ← добавили подключение авторизации

# Подключаем статику
app.mount("/static", StaticFiles(directory="app/static"), name="static")
