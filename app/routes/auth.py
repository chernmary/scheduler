
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import ADMIN_USERNAME, ADMIN_PASSWORD

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
def login_form():
    return '''
    <form method="post">
        <input name="username" placeholder="Логин">
        <input name="password" type="password" placeholder="Пароль">
        <button type="submit">Войти</button>
    </form>
    '''

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin/employees", status_code=302)
        response.set_cookie("auth", "admin_logged_in")
        return response
    return HTMLResponse("Неверный логин или пароль", status_code=401)

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("auth")
    return response
