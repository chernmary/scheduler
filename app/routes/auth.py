from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import ADMIN_USERNAME, ADMIN_PASSWORD

router = APIRouter()

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/schedule", status_code=302)
        response.set_cookie("auth", "admin_logged_in", httponly=True)
        return response
    return HTMLResponse("<p style='color:red; text-align:center;'>Неверный логин или пароль</p>", status_code=401)

@router.post("/logout", name="logout")
def logout():
    response = RedirectResponse(url="/schedule", status_code=302)
    response.delete_cookie("auth")
    return response
