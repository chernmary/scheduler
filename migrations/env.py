
# Заглушка под Telegram-бота
import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def notify_user(chat_id, message):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": message})

# Пример использования:
# notify_user(123456789, "Ваша смена назначена на завтра.")
