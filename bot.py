import sqlite3
import datetime
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from database import init_db

print("TOKEN =", os.environ.get("TOKEN"))
TOKEN = os.getenv("TOKEN")
print("TOKEN =", TOKEN) 
FAMILY_CODE = "FAMILY20162026"

user_states = {}

# --- Главное меню ---
def main_menu():
    keyboard = [
        ["👤 Профиль"],
        ["💬 Написать семье"],
        ["🔔 Напоминание"],
        ["⭐ Премиум"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Добавление пользователя ---
def add_user(user_id, name):
    conn = sqlite3.connect("family.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    conn.commit()
    conn.close()

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_states[user.id] = "awaiting_code"
    await update.message.reply_text("🔐 Введите код семьи:")

# --- Отправка напоминания ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"🔔 Напоминание:\n\n{context.job.data}"
    )

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    conn = sqlite3.connect("family.db")
    cursor = conn.cursor()

    # --- Проверка кода семьи ---
    if user_states.get(user_id) == "awaiting_code":
        if text == FAMILY_CODE:
            add_user(user_id, update.effective_user.first_name)
            user_states[user_id] = None
            await update.message.reply_text(
                "✅ Код верный! Добро пожаловать в семью ❤️",
                reply_markup=main_menu()
            )
        else:
            await update.message.reply_text("❌ Неверный код. Попробуйте снова:")
        conn.close()
        return

    # --- Ввод текста напоминания ---
    if user_states.get(user_id) == "awaiting_reminder_text":
        context.user_data["reminder_text"] = text
        user_states[user_id] = "awaiting_reminder_time"
        await update.message.reply_text("⏰ Введите время в формате ЧЧ:ММ (например 18:30):")
        conn.close()
        return

    # --- Ввод времени напоминания ---
    if user_states.get(user_id) == "awaiting_reminder_time":
        try:
            clean_text = text.strip()
            parts = clean_text.split(":")

            if len(parts) != 2:
                raise ValueError

            hour = int(parts[0])
            minute = int(parts[1])

            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError

            reminder_text = context.user_data.get("reminder_text")

            context.job_queue.run_daily(
                send_reminder,
                time=datetime.time(hour=hour, minute=minute),
                chat_id=user_id,
                data=reminder_text
            )

            await update.message.reply_text("✅ Напоминание установлено!")
            user_states[user_id] = None

        except:
            await update.message.reply_text(
                "❌ Неверный формат.\nВведите время так: 18:30"
            )

        conn.close()
        return

    # --- Сообщение семье ---
    if user_states.get(user_id) == "awaiting_message":
        cursor.execute(
            "INSERT INTO messages (sender_id, text) VALUES (?, ?)",
            (user_id, text)
        )
        conn.commit()

        cursor.execute("SELECT name FROM users WHERE telegram_id=?", (user_id,))
        sender_name = cursor.fetchone()[0]

        cursor.execute("SELECT telegram_id FROM users")
        users = cursor.fetchall()

        for user in users:
            if user[0] != user_id:
                await context.bot.send_message(
                    chat_id=user[0],
                    text=f"📩 Сообщение от {sender_name}:\n\n{text}"
                )

        await update.message.reply_text("✅ Сообщение отправлено семье ❤️")
        user_states[user_id] = None
        conn.close()
        return

    # --- Кнопки ---
    if text == "💬 Написать семье":
        user_states[user_id] = "awaiting_message"
        await update.message.reply_text("✏️ Введите сообщение для семьи:")
    
    elif text == "🔔 Напоминание":
        user_states[user_id] = "awaiting_reminder_text"
        await update.message.reply_text("📝 Введите текст напоминания:")
    
    elif text == "👤 Профиль":
        cursor.execute("SELECT name, premium FROM users WHERE telegram_id=?", (user_id,))
        row = cursor.fetchone()
        if row:
            name, premium = row
            status = "⭐ Премиум" if premium else "❌ Обычный"
            await update.message.reply_text(
                f"Имя: {name}\nID: {user_id}\nСтатус: {status}"
            )
        else:
            await update.message.reply_text("Профиль не найден!")

    elif text == "⭐ Премиум":
        await update.message.reply_text("Премиум скоро будет подключён ⭐")

    conn.close()

# --- Запуск ---
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()



