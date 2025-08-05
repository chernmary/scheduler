
from fastapi import APIRouter, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from app.schemas import *
from typing import List

router = APIRouter()

@router.get("/employees")
def admin_employees():
    return {"message": "Страница управления сотрудниками"}

@router.post("/templates/save")
def save_template(template: ScheduleTemplate):
    return {"status": "Сохранено"}
