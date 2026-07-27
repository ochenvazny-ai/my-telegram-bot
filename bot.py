import os
import sys
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# Берём полную строку подключения (Session Pooler URL с паролем)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задана в переменных окружения")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")

def get_db_connection():
    """Создаёт и возвращает соединение с базой данных."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    if conn is None:
        await update.message.reply_text("Не удалось подключиться к базе данных. Попробуйте позже.")
        return

    try:
        cur = conn.cursor()

        # UPSERT пользователя (вставка или обновление)
        cur.execute("""
            INSERT INTO users (id, username, first_name, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                created_at = NOW();
        """, (user.id, user.username, user.first_name))
        conn.commit()
        cur.close()

        # Проверка, является ли пользователь админом
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins WHERE user_id = %s;", (user.id,))
        is_admin = cur.fetchone() is not None
        cur.close()
        conn.close()

        if is_admin:
            keyboard = [[InlineKeyboardButton("👑 Админка", callback_data="admin")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Привет, {user.first_name}! Ты админ.", reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"Привет, {user.first_name}! Ты сохранён в базе.")

    except Exception as e:
        print(f"❌ Ошибка SQL: {e}")
        await update.message.reply_text("Произошла ошибка при работе с базой данных.")
        if conn:
            conn.close()

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой ID: {update.effective_user.id}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    print("✅ Бот запущен с прямым подключением к PostgreSQL!")
    sys.stdout.flush()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
