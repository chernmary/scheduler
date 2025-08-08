# app/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 часов

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")  # bcrypt-хэш

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return bool(hashed) and pwd.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _read_token(request: Request) -> Optional[str]:
    raw = request.cookies.get("access_token")
    return raw.split(" ", 1)[1] if raw and raw.startswith("Bearer ") else None

def is_admin_request(request: Request) -> bool:
    token = _read_token(request)
    if not token:
        return False
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub") == ADMIN_USERNAME
    except JWTError:
        return False

async def admin_required(request: Request):
    if not is_admin_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
