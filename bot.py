import os
import psycopg2
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ... (загрузка переменных окружения) ...

# Используем данные из Session Pooler
SUPABASE_DB_URL = os.getenv("SUPABASE_URL")  # Это должен быть URL Session Pooler
SUPABASE_DB_KEY = os.getenv("SUPABASE_KEY")  # Это твой пароль от БД

def get_db_connection():
    """Устанавливает соединение с базой данных через Session Pooler."""
    try:
        # Парсим URL для получения параметров подключения
        # URL вида: postgresql://postgres.xxxx:password@aws-0-....pooler.supabase.com:5432/postgres
        conn = psycopg2.connect(SUPABASE_DB_URL)
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    if conn is None:
        await update.message.reply_text("Ошибка подключения к базе данных.")
        return

    try:
        cur = conn.cursor()
        # Выполняем UPSERT (вставка или обновление)
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

        # Проверяем, является ли пользователь админом
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins WHERE user_id = %s;", (user.id,))
        is_admin = cur.fetchone() is not None
        cur.close()

        if is_admin:
            keyboard = [[InlineKeyboardButton("👑 Админка", callback_data="admin")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Привет, {user.first_name}! Ты админ.", reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"Привет, {user.first_name}! Ты сохранён в базе.")

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        await update.message.reply_text("Произошла ошибка при работе с базой данных.")
    finally:
        if conn:
            conn.close()
