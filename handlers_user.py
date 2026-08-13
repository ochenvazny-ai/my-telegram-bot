import logging
import asyncio
import io
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
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с изображением")
        user_id = update.effective_user.id
        admin = await asyncio.to_thread(db.is_admin, user_id)
        text = await _greeting_text()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=kb.main_menu_kb(admin),
        )
    else:
        user_id = update.effective_user.id
        admin = await asyncio.to_thread(db.is_admin, user_id)
        text = await _greeting_text()
        await query.edit_message_text(text, reply_markup=kb.main_menu_kb(admin))


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Замены: новым сообщением + ниже меню.
    Перед показом — проверка, не появились ли новые замены (по дате с сайта).
    Если да — авторассылка остальным."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    try:
        await query.delete_message()
    except Exception:
        pass
    loading = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ Загружаю замены...",
    )
    text, ok = await sched.get_schedule_for_display()
    try:
        await loading.delete()
    except Exception:
        pass
    # Проверка и авторассылка новых замен (реактивно, при нажатии)
    try:
        await sched.check_and_broadcast_new_replacements(user_id)
    except Exception:
        logger.exception("check_and_broadcast_new_replacements failed")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode='HTML',
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Главное меню:",
        reply_markup=kb.main_menu_kb(admin),
    )


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
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        text = "📭 Активных объявлений нет."
    else:
        lines = ["📢 Активные объявления:\n"]
        for idx, (_, ann_text, created_at, is_note, photo_id) in enumerate(anns, start=1):
            date_part = created_at.split(" ")[0] if created_at else ""
            prefix = "📝 " if is_note else ("📎 " if photo_id else "")
            body = ann_text if ann_text else "(без текста — только вложение)"
            lines.append(f"{idx}️⃣ {prefix}{date_part}: {body}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_button())


# ---- ДОП. ЗАНЯТИЯ ----
async def show_extra_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с фото")
        if not items:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📭 Нет активных дополнительных занятий.",
                reply_markup=kb.back_button(),
            )
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📚 Дополнительные занятия. Выберите:",
            reply_markup=kb.extra_classes_list_kb(items),
        )
        return
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

    if photo_id:
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_id,
            )
        except Exception:
            logger.exception("Не удалось отправить фото доп. занятия")

    if description:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📚 <b>{subject}</b>\n\n{description}",
            parse_mode='HTML',
            reply_markup=kb.back_button("menu_extra"),
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📚 <b>{subject}</b>",
            parse_mode='HTML',
            reply_markup=kb.back_button("menu_extra"),
        )

    try:
        await query.delete_message()
    except Exception:
        pass


async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с фото")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ Учебная инфа. Выберите раздел:",
            reply_markup=kb.info_menu_kb(),
        )
        return
    await query.edit_message_text("ℹ️ Учебная инфа. Выберите раздел:", reply_markup=kb.info_menu_kb())


async def show_bells_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с фото")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📞 Расписание звонков. Выберите тип дня:",
            reply_markup=kb.bells_choice_kb(),
        )
        return
    await query.edit_message_text("📞 Расписание звонков. Выберите тип дня:", reply_markup=kb.bells_choice_kb())


async def show_bells_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kind = "bells_reg"
    cached = await asyncio.to_thread(db.get_image, kind)
    if not cached:
        try:
            await query.edit_message_text("⏳ Готовлю изображение...")
        except Exception:
            pass
        try:
            data = await asyncio.to_thread(sched_img.render_bells_regular_image)
            await asyncio.to_thread(db.save_image, kind, data)
        except Exception:
            logger.exception("Не удалось сгенерировать bells_reg")
            try:
                await query.edit_message_text("❌ Ошибка генерации.", reply_markup=kb.bells_choice_kb())
            except Exception:
                pass
            return
    else:
        data = cached

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=io.BytesIO(data),
        reply_markup=kb.back_button("info_bells"),
    )
    try:
        await query.delete_message()
    except Exception:
        pass


async def show_bells_preholiday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kind = "bells_pre"
    cached = await asyncio.to_thread(db.get_image, kind)
    if not cached:
        try:
            await query.edit_message_text("⏳ Готовлю изображение...")
        except Exception:
            pass
        try:
            data = await asyncio.to_thread(sched_img.render_bells_preholiday_image)
            await asyncio.to_thread(db.save_image, kind, data)
        except Exception:
            logger.exception("Не удалось сгенерировать bells_pre")
            try:
                await query.edit_message_text("❌ Ошибка генерации.", reply_markup=kb.bells_choice_kb())
            except Exception:
                pass
            return
    else:
        data = cached

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=io.BytesIO(data),
        reply_markup=kb.back_button("info_bells"),
    )
    try:
        await query.delete_message()
    except Exception:
        pass


async def show_sched_img_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Не удалось удалить сообщение с фото")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📚 Расписание пар. Выберите вариант:",
            reply_markup=kb.schedule_img_choice_kb(),
        )
        return
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
        try:
            await query.edit_message_text("⏳ Готовлю изображение (первый раз)...")
        except Exception:
            pass
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
            try:
                await query.edit_message_text(
                    "❌ Не удалось сформировать изображение. Попробуйте позже.",
                    reply_markup=kb.back_button("info_sched_img"),
                )
            except Exception:
                pass
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