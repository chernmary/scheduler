from fastapi import FastAPI, Request
import os
from app.database import SessionLocal
from app.models import Employee
from .notify import notify_user

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SECRET_PATH = f"/bot/{BOT_TOKEN}"

bot_app = FastAPI()

@bot_app.post(SECRET_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text.startswith("/start"):
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_nick == text.split(" ", 1)[-1].lstrip("@")).first()
        if emp:
            emp.telegram_chat_id = chat_id
            db.commit()
            notify_user(chat_id, f"Вы успешно связали Telegram с системой. Добро пожаловать, {emp.full_name}!")
        else:
            notify_user(chat_id, "Сотрудник с таким ником не найден.")
    return {"ok": True}