import os
import socket
import sys
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY or not BOT_TOKEN:
    raise ValueError("Missing required environment variables")

SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_KEY = SUPABASE_KEY.strip()
BOT_TOKEN = BOT_TOKEN.strip()

# Диагностика DNS
try:
    ip = socket.gethostbyname('aws-0-eu-west-1.pooler.supabase.com')
    print(f"✅ DNS OK: {ip}")
except Exception as e:
    print(f"❌ DNS FAILED: {e}")
print(f"🔍 SUPABASE_URL = {repr(SUPABASE_URL)}")
sys.stdout.flush()

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
        print(f"❌ Upsert error: {e}")
        await update.message.reply_text("Ошибка сохранения данных.")
        return
    admin_check = supabase.table('admins').select('*').eq('user_id', user.id).execute()
    if admin_check.data:
        keyboard = [[InlineKeyboardButton("👑 Админка", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Привет, {user.first_name}! Ты админ.", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"Привет, {user.first_name}! Ты сохранён в базе.")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой ID: {update.effective_user.id}")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Сброс вебхука — теперь в том же event loop
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук сброшен")
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    
    print("✅ Бот запущен с RLS и политиками!")
    sys.stdout.flush()
    
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
