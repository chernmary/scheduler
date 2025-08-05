
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import sqlite3
from datetime import date, timedelta

BOT_TOKEN = "PLACE_YOUR_BOT_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /schedule чтобы получить своё расписание на ближайшие 2 недели.")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_nick = update.message.from_user.username
    if not tg_nick:
        await update.message.reply_text("Нужен Telegram-ник для получения расписания.")
        return

    conn = sqlite3.connect("scheduler.db")
    cursor = conn.cursor()

    query = '''
    SELECT s.date, s.location, s.shift_type
    FROM assignments a
    JOIN shifts s ON a.shift_id = s.id
    JOIN employees e ON a.employee_id = e.id
    WHERE e.telegram_nick = ? AND s.date >= ? AND s.date <= ?
    ORDER BY s.date
    '''
    today = date.today()
    two_weeks = today + timedelta(days=14)
    cursor.execute(query, (tg_nick, today.isoformat(), two_weeks.isoformat()))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("У вас нет смен в ближайшие 2 недели.")
        return

    message = "\n".join([f"{r[0]} — {r[1]} ({r[2]})" for r in rows])
    await update.message.reply_text("Ваши смены:\n" + message)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule))
    app.run_polling()

if __name__ == "__main__":
    main()
