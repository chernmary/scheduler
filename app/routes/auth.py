from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.auth import ADMIN_USERNAME, ADMIN_PASSWORD

router = APIRouter()


@router.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    """Обработка формы входа"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/schedule", status_code=302)
        response.set_cookie("auth", "admin_logged_in", httponly=True)
        return response
    # Если логин/пароль неверный — вернёмся на /schedule с параметром ошибки
    return RedirectResponse(url="/schedule?error=1", status_code=302)


@router.get("/logout")
def logout():
    """Выход из аккаунта"""
    response = RedirectResponse(url="/schedule", status_code=302)
    response.delete_cookie("auth")
    return response
