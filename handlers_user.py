import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import database as db
import keyboards as kb
import schedule_service as sched
from config import INITIAL_ADMIN_ID, BELL_SCHEDULE_REGULAR, BELL_SCHEDULE_PRE_HOLIDAY

logger = logging.getLogger(__name__)

INFO_TEXT = (
    "🤖 Бот для группы ИБ1-31\n\n"
    "📌 Как пользоваться:\n"
    "• Управляй ботом с помощью кнопок под сообщениями.\n\n"
    "📅 Замены:\n"
    "Показывает замены на день, указанный на сайте колледжа.\n"
    "Формат вывода:\n"
    "✨ РАСПИСАНИЕ ЗАНЯТИЙ НА ДАТА ✨\n"
    "🔹 N урок | Предмет (Преподаватель) | Аудитория\n\n"
    "🔍 Обозначения:\n"
    "• [ЗАМЕНА] — пара была заменена.\n"
    "• Если пара удалена — она не отображается.\n"
    "• Дистант отображается как аудитория ДОТ.\n\n"
    "📚 Домашка:\n"
    "Показывает список АКТУАЛЬНЫХ домашних заданий.\n\n"
    "📢 Объявления:\n"
    "Показывает активные объявления от администрации.\n\n"
    "📞 Расписание звонков:\n"
    "Показывает обычное или предпраздничное расписание звонков на сегодня.\n\n"
    "💡 Кнопка «Инфо» — снова покажет это сообщение.\n\n"
    "Успехов в учёбе! 📚"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await asyncio.to_thread(db.upsert_user, user.id, user.username, user.first_name)
    admin = await asyncio.to_thread(db.is_admin, user.id)
    await update.message.reply_text(
        "🤖 Бот для группы ИБ1-31\n\nГлавное меню:",
        reply_markup=kb.main_menu_kb(admin),
    )
    await update.message.reply_text("Меню:", reply_markup=kb.reply_menu_button())


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')


async def handle_menu_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловит нажатие Reply-кнопки «📋 Меню» вне активных диалогов."""
    if update.message.text == "📋 Меню":
        await start(update, context)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    await query.edit_message_text("Главное меню:", reply_markup=kb.main_menu_kb(admin))


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Загружаю расписание...")
    text, ok = await sched.get_schedule_for_display()
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.back_button())


async def show_hw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Загружаю список...")
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        text = "📭 Нет текущих домашних заданий."
    else:
        lines = ["📚 Текущие домашние задания:\n"]
        for idx, (_, task, due_date, _) in enumerate(tasks, start=1):
            due_str = f" (срок: {due_date})" if due_date else ""
            lines.append(f"{idx}️⃣ {task}{due_str}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_button())


async def show_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Загружаю объявления...")
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        text = "📭 Активных объявлений нет."
    else:
        lines = ["📢 Объявления:\n"]
        for idx, (_, ann_text, created_at) in enumerate(anns, start=1):
            date_part = created_at.split(" ")[0] if created_at else ""
            lines.append(f"{idx}️⃣ {date_part}: {ann_text}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_button())


async def show_bells(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today_mmdd = datetime.now().strftime("%m-%d")
    is_ph = await asyncio.to_thread(db.is_pre_holiday_today, today_mmdd)
    schedule = BELL_SCHEDULE_PRE_HOLIDAY if is_ph else BELL_SCHEDULE_REGULAR
    title = "предпраздничный день" if is_ph else "обычное"
    lines = [f"📞 РАСПИСАНИЕ ЗВОНКОВ ({title})\n"]
    for name, start_t, end_t in schedule:
        lines.append(f"{name}: {start_t} – {end_t}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button())


async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(INFO_TEXT, reply_markup=kb.back_button())
