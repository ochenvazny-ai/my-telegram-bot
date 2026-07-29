import logging
import asyncio
import io
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
import database as db
import keyboards as kb
import schedule_service as sched
import schedule_image as sched_img

logger = logging.getLogger(__name__)

INFO_TEXT = (
    "🤖 Бот для группы ИБ1-31\n\n"
    "📌 Как пользоваться:\n"
    "• Управляй ботом с помощью кнопок под сообщениями.\n\n"
    "📅 Замены — замены на день, указанный на сайте колледжа.\n"
    "📚 Домашка — список актуальных домашних заданий.\n"
    "📢 Объявления — активные объявления от администрации.\n"
    "ℹ️ Инфо — расписание звонков и расписание пар.\n\n"
    "Успехов в учёбе! 📚"
)

BELLS_REGULAR_TEXT = (
    "📞 Расписание звонков (обычные дни)\n\n"
    "По А корпусу:\n"
    "0 пара – 8:00 – 9:10\n"
    "1 пара – 9:20 – 10:50\n"
    "2 пара – 11:00 – 11:45, потом перерыв 40 мин, затем вторая часть с 12:25 до 13:10\n"
    "3 пара – 13:20 – 14:50\n"
    "4 пара – 15:05 – 16:35\n"
    "5 пара – 17:05 – 18:35\n"
    "6 пара – 18:45 – 19:55\n\n"
    "По Б корпусу:\n"
    "0 пара – 8:00 – 9:10\n"
    "1 пара – 9:20 – 10:50\n"
    "2 пара – 11:00 – 12:30 (сплошная, без разбивки), после неё перерыв 50 минут\n"
    "3 пара – 13:20 – 14:50\n"
    "4 пара – 15:05 – 16:35\n"
    "5 пара – 17:05 – 18:35\n"
    "6 пара – 18:45 – 19:55"
)

BELLS_PRE_HOLIDAY_TEXT = (
    "📞 Расписание звонков (предпраздничный день)\n\n"
    "Для всех корпусов. Занятия по 60 минут.\n"
    "0 пара – 8:00 – 9:00\n"
    "1 пара – 9:10 – 10:10\n"
    "2 пара – 10:20 – 11:20\n"
    "перемена 30 минут\n"
    "3 пара – 11:50 – 12:50\n"
    "4 пара – 13:00 – 14:00\n"
    "5 пара – 14:10 – 15:10\n"
    "6 пара – 15:20 – 16:20\n\n"
    "Перемены между остальными парами – по 10 минут."
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

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Раздел «Инфо» — теперь это подменю, а не статичный текст."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ℹ️ Инфо. Выберите раздел:", reply_markup=kb.info_menu_kb())

async def show_bells_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📞 Расписание звонков. Выберите тип дня:", reply_markup=kb.bells_choice_kb())

async def show_bells_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BELLS_REGULAR_TEXT, reply_markup=kb.back_button("info_bells"))

async def show_bells_preholiday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BELLS_PRE_HOLIDAY_TEXT, reply_markup=kb.back_button("info_bells"))

async def show_sched_img_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(" Расписание пар. Выберите вариант:", reply_markup=kb.schedule_img_choice_kb())

async def send_schedule_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data  # schedimg_num / schedimg_den / schedimg_cmp
    
    await query.edit_message_text("⏳ Формирую изображение...")
    
    try:
        if choice == "schedimg_num":
            img_bytes = await asyncio.to_thread(sched_img.render_schedule_image, "Числитель")
        elif choice == "schedimg_den":
            img_bytes = await asyncio.to_thread(sched_img.render_schedule_image, "Знаменатель")
        else:
            img_bytes = await asyncio.to_thread(sched_img.render_comparison_image)
        
        # Отправляем фото с кнопкой «Назад»
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=io.BytesIO(img_bytes),
            reply_markup=kb.back_button("info_sched_img"),
        )
        # Удаляем сообщение «⏳ Формирую изображение...», чтобы не было дубля меню
        await query.delete_message()
    except Exception:
        logger.exception("Не удалось сформировать изображение расписания")
        await query.edit_message_text(
            "❌ Не удалось сформировать изображение. Попробуйте позже.",
            reply_markup=kb.back_button("info_sched_img"),
        )
