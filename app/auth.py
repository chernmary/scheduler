
from fastapi import Request, HTTPException, status

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminpass"

def is_admin(request: Request):
    auth = request.cookies.get("auth")
    if auth != "admin_logged_in":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True
