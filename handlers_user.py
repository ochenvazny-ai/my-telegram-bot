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
    "🤖 Бот для группы {group}\n\n"
    "📌 Как пользоваться:\n"
    "• Управляй ботом с помощью кнопок под сообщениями.\n\n"
    "📅 Замены — замены на день, указанный на сайте колледжа.\n"
    "📚 Домашка — список актуальных домашних заданий.\n"
    "📢 Объявления — активные объявления от администрации.\n"
    "📚 Доп. занятия — дополнительные занятия с расписанием.\n"
    "ℹ️ Учебная инфа — расписание звонков и расписание пар.\n\n"
    "Успехов в учёбе! 📚"
)

BELLS_REGULAR_A_TEXT = (
    "📞 Расписание звонков (обычные дни)\n"
    "По А корпусу:\n\n"
    "0 пара – 8:00 – 9:10\n"
    "1 пара – 9:20 – 10:50\n"
    "2 пара – 11:00 – 11:45, потом перерыв 40 мин, затем вторая часть с 12:25 до 13:10\n"
    "3 пара – 13:20 – 14:50\n"
    "4 пара – 15:05 – 16:35\n"
    "5 пара – 17:05 – 18:35\n"
    "6 пара – 18:45 – 19:55"
)

BELLS_REGULAR_B_TEXT = (
    "📞 Расписание звонков (обычные дни)\n"
    "По Б корпусу:\n\n"
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


async def _greeting_text() -> str:
    group = await asyncio.to_thread(db.get_group_name)
    return INFO_TEXT.format(group=group)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await asyncio.to_thread(db.upsert_user, user.id, user.username, user.first_name)
    admin = await asyncio.to_thread(db.is_admin, user.id)
    await update.message.reply_text(
        await _greeting_text(),
        reply_markup=kb.main_menu_kb(admin),
    )
    await update.message.reply_text("Меню:", reply_markup=kb.reply_menu_button())


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')


async def handle_menu_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📋 Меню":
        await start(update, context)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    text = await _greeting_text()
    await query.edit_message_text(text, reply_markup=kb.main_menu_kb(admin))


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
        for idx, (_, ann_text, created_at, is_note) in enumerate(anns, start=1):
            date_part = created_at.split(" ")[0] if created_at else ""
            prefix = "📝 " if is_note else ""
            lines.append(f"{idx}️⃣ {prefix}{date_part}: {ann_text}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_button())


# ---- ДОП. ЗАНЯТИЯ ----
async def show_extra_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await query.edit_message_text(
            "📭 Нет активных дополнительных занятий.",
            reply_markup=kb.back_button(),
        )
        return
    await query.edit_message_text(
        "📚 Дополнительные занятия. Выберите:",
        reply_markup=kb.extra_classes_list_kb(items),
    )


async def extra_class_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        item_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        logger.warning("Bad callback_data: %s", query.data)
        return
    rec = await asyncio.to_thread(db.get_extra_class, item_id)
    if not rec:
        await query.answer("❌ Занятие не найдено.", show_alert=True)
        return
    _id, subject, description, photo_id = rec
    caption_parts = [f"📚 <b>{subject}</b>"]
    if description:
        caption_parts.append(description)
    caption = "\n\n".join(caption_parts)
    try:
        if photo_id:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_id,
                caption=caption,
                parse_mode='HTML',
                reply_markup=kb.back_button("menu_extra"),
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                parse_mode='HTML',
                reply_markup=kb.back_button("menu_extra"),
            )
        try:
            await query.delete_message()
        except Exception:
            pass
    except Exception:
        logger.exception("Не удалось отправить доп. занятие %s", item_id)
        await query.edit_message_text(
            "❌ Не удалось показать занятие.", reply_markup=kb.back_button()
        )


async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ℹ️ Учебная инфа. Выберите раздел:", reply_markup=kb.info_menu_kb())


async def show_bells_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📞 Расписание звонков. Выберите тип дня:", reply_markup=kb.bells_choice_kb())


async def show_bells_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выберите корпус:", reply_markup=kb.bells_building_kb())


async def show_bells_regular_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BELLS_REGULAR_A_TEXT, reply_markup=kb.back_button("bells_regular"))


async def show_bells_regular_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BELLS_REGULAR_B_TEXT, reply_markup=kb.back_button("bells_regular"))


async def show_bells_preholiday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BELLS_PRE_HOLIDAY_TEXT, reply_markup=kb.back_button("info_bells"))


async def show_sched_img_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с изображением")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📚 Расписание пар. Выберите вариант:",
            reply_markup=kb.schedule_img_choice_kb(),
        )
    else:
        await query.edit_message_text("📚 Расписание пар. Выберите вариант:", reply_markup=kb.schedule_img_choice_kb())


async def send_schedule_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    kind = "cmp"
    if choice == "schedimg_num":
        kind = "num"
    elif choice == "schedimg_den":
        kind = "den"

    cached = await asyncio.to_thread(db.get_image, kind)
    if not cached:
        await query.edit_message_text("⏳ Готовлю изображение (первый раз)...")
        try:
            if kind == "num":
                data = await asyncio.to_thread(sched_img.render_schedule_image, "Числитель")
            elif kind == "den":
                data = await asyncio.to_thread(sched_img.render_schedule_image, "Знаменатель")
            else:
                data = await asyncio.to_thread(sched_img.render_comparison_image)
            await asyncio.to_thread(db.save_image, kind, data)
        except Exception:
            logger.exception("Не удалось сгенерировать изображение")
            await query.edit_message_text(
                "❌ Не удалось сформировать изображение. Попробуйте позже.",
                reply_markup=kb.back_button("info_sched_img"),
            )
            return
    else:
        data = cached

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=io.BytesIO(data),
        reply_markup=kb.back_button("info_sched_img"),
    )
    try:
        await query.delete_message()
    except Exception:
        pass