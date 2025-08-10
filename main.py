from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.run_migrations import run_migrations
from app.database import init_db
from app.seed_locations import seed_locations
from app.seed_employees import seed_employees
from app.seed_employee_settings import seed_employee_settings
from app.routes import admin, public, schedule, auth, employees

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def _startup():
    run_migrations()
    init_db()
    seed_locations()
    seed_employees()
    seed_employee_settings()

@app.get("/")
def root():
    return RedirectResponse(url="/schedule", status_code=302)

app.include_router(admin.router, prefix="/admin")
app.include_router(public.router, prefix="/api")
app.include_router(schedule.router)
app.include_router(auth.router)
app.include_router(employees.router)
