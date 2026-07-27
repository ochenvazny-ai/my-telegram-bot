import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    supabase.table('users').upsert({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name
    }, on_conflict='id').execute()

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
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    print("✅ Бот запущен с RLS и политиками!")
    app.run_polling()

if __name__ == "__main__":
    main()