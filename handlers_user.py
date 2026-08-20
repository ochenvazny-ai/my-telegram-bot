import logging
import asyncio
import io
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
    "🔔 Уведомления — настройка уведомлений.\n"
    "ℹ️ Учебная инфа — расписание звонков и расписание пар.\n\n"
    "Успехов в учёбе! 📚"
)

WELCOME_TEXT = (
    "👋 Привет! Я — бот-помощник твоей учебной группы.\n"
    "Для начала мне нужно узнать твоё имя.\n"
    "Это необходимо, чтобы ты корректно отображался в системе, "
    "мог полноценно пользоваться ботом, а также чтобы я мог "
    "( ну вдруг понадобиться) назначить тебя админом)\n\n"
    "📌 Никакие личные данные не собираются, статистика не ведётся, "
    "пароли не запрашиваются – всё работает прозрачно и исключительно "
    "для твоего удобства.\n\n"
    "✍️ Введи, пожалуйста, своё имя:"
)


async def _greeting_text():
    group = await asyncio.to_thread(db.get_group_name)
    return INFO_TEXT.format(group=group)


async def _send_main_menu(context, chat_id, user_id):
    admin = await asyncio.to_thread(db.is_admin, user_id)
    text = await _greeting_text()
    await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=kb.main_menu_kb(admin)
    )


async def start(update, context):
    user = update.effective_user
    await asyncio.to_thread(db.upsert_user, user.id, user.username, user.first_name)
    try:
        await update.message.reply_text(WELCOME_TEXT, reply_markup=kb.reply_menu_button())
    except Exception:
        pass
    return 0  # WELCOME_NAME


async def welcome_finish(update, context):
    name = (update.message.text or "").strip()
    user = update.effective_user
    if not name:
        await update.message.reply_text("Имя не может быть пустым. Введи, пожалуйста, своё имя:")
        return 0

    old_name = await asyncio.to_thread(db.get_user_display_name, user.id)
    await asyncio.to_thread(db.set_user_display_name, user.id, name)
    if old_name:
        await update.message.reply_text(f"✅ Имя обновлено: {old_name} → {name}")
    else:
        await update.message.reply_text(f"✅ Отлично, я тебя узнал!\n\nУспехов в учёбе, {name}! 📚")
    await _send_main_menu(context, update.effective_chat.id, user.id)
    return ConversationHandler.END if False else -1  # exit conv


async def my_id(update, context):
    await update.message.reply_text(f"🆔 Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')


async def show_main_menu_only(update, context):
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    text = await _greeting_text()
    try:
        await update.message.reply_text(text, reply_markup=kb.main_menu_kb(admin))
    except Exception:
        pass


async def on_user_blocked_bot(update, context):
    try:
        result = update.my_chat_member
        if not result:
            return
        if result.chat.type != "private":
            return
        if result.new_chat_member.status in ("left", "kicked"):
            await asyncio.to_thread(db.delete_user_by_id, result.chat.id)
    except Exception:
        logger.exception("on_user_blocked_bot failed")


async def main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    text = await _greeting_text()
    try:
        await query.edit_message_text(text, reply_markup=kb.main_menu_kb(admin))
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=kb.main_menu_kb(admin)
        )


async def show_schedule(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    try:
        await query.delete_message()
    except Exception:
        pass
    loading = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Загружаю замены...")
    text, ok = await sched.get_schedule_for_display()
    try:
        await loading.delete()
    except Exception:
        pass
    try:
        await sched.check_and_broadcast_new_replacements(user_id)
    except Exception:
        logger.exception("broadcast failed")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')
    await _send_main_menu(context, update.effective_chat.id, user_id)


async def show_hw(update, context):
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


async def show_announcements(update, context):
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


async def show_extra_classes(update, context):
    query = update.callback_query
    await query.answer()
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("del photo")
        if not items:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📭 Нет активных дополнительных занятий.",
                reply_markup=kb.back_button(),
            )
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="   Дополнительные занятия. Выберите:",
            reply_markup=kb.extra_classes_list_kb(items),
        )
        return
    if not items:
        await query.edit_message_text("📭 Нет активных дополнительных занятий.", reply_markup=kb.back_button())
        return
    await query.edit_message_text("📚 Дополнительные занятия. Выберите:", reply_markup=kb.extra_classes_list_kb(items))


async def extra_class_open(update, context):
    query = update.callback_query
    await query.answer()
    try:
        item_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        return
    rec = await asyncio.to_thread(db.get_extra_class, item_id)
    if not rec:
        await query.answer("❌ Занятие не найдено.", show_alert=True)
        return
    _id, subject, description, photo_id = rec
    if photo_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_id)
        except Exception:
            logger.exception("photo send")
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


async def show_info(update, context):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("del photo")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ Учебная инфа. Выберите раздел:",
            reply_markup=kb.info_menu_kb(),
        )
        return
    await query.edit_message_text("ℹ️ Учебная инфа. Выберите раздел:", reply_markup=kb.info_menu_kb())


async def show_bells_menu(update, context):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("del photo")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="   Расписание звонков. Выберите тип дня:",
            reply_markup=kb.bells_choice_kb(),
        )
        return
    await query.edit_message_text("📞 Расписание звонков. Выберите тип дня:", reply_markup=kb.bells_choice_kb())


async def show_bells_regular(update, context):
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
            logger.exception("bells_reg failed")
            try:
                await query.edit_message_text("❌ Ошибка генерации.", reply_markup=kb.bells_choice_kb())
            except Exception:
                pass
            return
    else:
        data = cached
    await context.bot.send_photo(
        chat_id=update.effective_chat.id, photo=io.BytesIO(data), reply_markup=kb.back_button("info_bells")
    )
    try:
        await query.delete_message()
    except Exception:
        pass


async def show_bells_preholiday(update, context):
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
            logger.exception("bells_pre failed")
            try:
                await query.edit_message_text("❌ Ошибка генерации.", reply_markup=kb.bells_choice_kb())
            except Exception:
                pass
            return
    else:
        data = cached
    await context.bot.send_photo(
        chat_id=update.effective_chat.id, photo=io.BytesIO(data), reply_markup=kb.back_button("info_bells")
    )
    try:
        await query.delete_message()
    except Exception:
        pass


async def show_sched_img_menu(update, context):
    query = update.callback_query
    await query.answer()
    if query.message and query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("del photo")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📚 Расписание пар. Выберите вариант:",
            reply_markup=kb.schedule_img_choice_kb(),
        )
        return
    await query.edit_message_text("📚 Расписание пар. Выберите вариант:", reply_markup=kb.schedule_img_choice_kb())


async def send_schedule_image(update, context):
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
            await query.edit_message_text("⏳ Готовлю изображение...")
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
            logger.exception("image gen failed")
            try:
                await query.edit_message_text("❌ Ошибка.", reply_markup=kb.back_button("info_sched_img"))
            except Exception:
                pass
            return
    else:
        data = cached
    await context.bot.send_photo(
        chat_id=update.effective_chat.id, photo=io.BytesIO(data), reply_markup=kb.back_button("info_sched_img")
    )
    try:
        await query.delete_message()
    except Exception:
        pass


async def _render_cabinet_text_and_kb(user_id):
    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    name = s.get("display_name") or s.get("first_name") or s.get("username") or "Пользователь"
    repl = "✅ Вкл" if s.get("notify_replacements") else "❌ Выкл"
    ann = "✅ Вкл" if s.get("notify_announcements") else "❌ Выкл"
    hw = "✅ Вкл" if s.get("notify_homework") else "❌ Выкл"
    ec = "✅ Вкл" if s.get("notify_extra_classes") else "❌ Выкл"
    text = (
        f"🔔 <b>Уведомления</b>\n\n"
        f"Привет, <b>{name}</b>!\n\n"
        f"Нажми на категорию, чтобы включить или выключить:\n\n"
        f"📅 Замены: {repl}\n"
        f"📢 Объявления: {ann}\n"
        f"📚 Домашка: {hw}\n"
        f"📖 Доп. занятия: {ec}"
    )
    return text


async def show_cabinet(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    text = await _render_cabinet_text_and_kb(user_id)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())


async def cabinet_toggle_notify(update, context):
    query = update.callback_query
    await query.answer()
    kind = query.data.split("_", 1)[1]
    user_id = update.effective_user.id

    kind_label_map = {
        "replacements": "замены",
        "announcements": "объявления",
        "homework": "домашку",
        "extra_classes": "доп. занятия",
    }
    col_map = {
        "replacements": "notify_replacements",
        "announcements": "notify_announcements",
        "homework": "notify_homework",
        "extra_classes": "notify_extra_classes",
    }
    col = col_map.get(kind)
    if not col:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    current = bool(s.get(col))
    new_value = not current
    ok = await asyncio.to_thread(db.set_user_notify, user_id, kind, new_value)

    if not ok:
        await query.answer("❌ Не удалось сохранить.", show_alert=True)
        return

    label = kind_label_map.get(kind, kind)
    if new_value:
        await query.answer(f"🔔 {label.capitalize()}: ВКЛ", show_alert=False)
    else:
        await query.answer(f"🔕 {label.capitalize()}: ВЫКЛ", show_alert=False)

    text = await _render_cabinet_text_and_kb(user_id)
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())
    except Exception:
        logger.exception("edit cabinet failed")


# Состояние диалога welcome
WELCOME_NAME = 0
from telegram.ext import ConversationHandler