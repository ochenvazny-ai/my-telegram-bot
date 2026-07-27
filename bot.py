import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Загрузка переменных с очисткой
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY or not BOT_TOKEN:
    raise ValueError("Missing required environment variables")

SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_KEY = SUPABASE_KEY.strip()
BOT_TOKEN = BOT_TOKEN.strip()

# Диагностика (удали после успешного запуска)
print(f"DEBUG: SUPABASE_URL = {repr(SUPABASE_URL)}")
print(f"DEBUG: BOT_TOKEN (first 5 chars) = {repr(BOT_TOKEN[:5])}")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        supabase.table('users').upsert({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name
        }, on_conflict='id').execute()
    except Exception as e:
        print(f"Ошибка upsert: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении данных.")
        return

    admin_check = supabase.table('admins').select('*').eq('user_id', user.id).execute()
    if admin_check.data:
        keyboard = [[InlineKeyboardButton("👑 Админка", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Привет, {user.first_name}! Ты админ.", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"Привет, {user.first_name}! Ты сохранён в базе.")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой Telegram ID: {update.effective_user.id}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    print("✅ Бот запущен с RLS и политиками!")
    app.run_polling()

if __name__ == "__main__":
    main()
