
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routes import admin, public, schedule

from app.database import init_db
app = FastAPI()
init_db()
from app.seed_locations import seed_locations

seed_locations()

from app.seed_employees import seed_employees

seed_employees()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(admin.router, prefix="/admin")
app.include_router(public.router)
app.include_router(schedule.router)
from app.run_migrations import run_migrations
run_migrations()


