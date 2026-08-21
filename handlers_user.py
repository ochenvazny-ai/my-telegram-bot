import logging
import asyncio
import io
from telegram.ext import ContextTypes, ConversationHandler
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
    "   Доп. занятия — дополнительные занятия с расписанием.\n"
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

BAN_TEXT = "🚫 Ваш аккаунт забанен!"


async def _greeting_text():
    group = await asyncio.to_thread(db.get_group_name)
    return INFO_TEXT.format(group=group)


async def _send_main_menu(context, chat_id, user_id):
    admin = await asyncio.to_thread(db.is_admin, user_id)
    text = await _greeting_text()
    await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=kb.main_menu_kb(admin)
    )


async def _check_banned_message(update, context):
    user_id = update.effective_user.id
    is_banned = await asyncio.to_thread(db.is_user_banned, user_id)
    if is_banned:
        try:
            await update.message.reply_text(BAN_TEXT)
        except Exception:
            pass
        return True
    return False


async def _check_banned_callback(update, context):
    user_id = update.effective_user.id
    is_banned = await asyncio.to_thread(db.is_user_banned, user_id)
    if is_banned:
        query = update.callback_query
        try:
            await query.answer(BAN_TEXT, show_alert=True)
        except Exception:
            pass
        return True
    return False


async def start(update, context):
    if await _check_banned_message(update, context):
        return ConversationHandler.END
    user = update.effective_user
    await asyncio.to_thread(db.upsert_user, user.id, user.username, user.first_name)
    try:
        await update.message.reply_text(WELCOME_TEXT, reply_markup=kb.reply_menu_button())
    except Exception:
        pass
    return 0


async def welcome_finish(update, context):
    if await _check_banned_message(update, context):
        return ConversationHandler.END
    name = (update.message.text or "").strip()
    user = update.effective_user
    if not name:
        await update.message.reply_text("Имя не может быть пустым. Введи, пожалуйста, своё имя:")
        return 0
    await asyncio.to_thread(db.set_user_display_name, user.id, name)
    await update.message.reply_text(f"✅ Отлично, я тебя узнал!\n\nУспехов в учёбе, {name}!   ")
    await _send_main_menu(context, update.effective_chat.id, user.id)
    return ConversationHandler.END


async def my_id(update, context):
    if await _check_banned_message(update, context):
        return
    await update.message.reply_text(f"🆔 Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')


async def show_main_menu_only(update, context):
    if await _check_banned_message(update, context):
        return
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
            await asyncio.to_thread(db.ban_user, result.chat.id)
    except Exception:
        logger.exception("on_user_blocked_bot failed")


async def main_menu_callback(update, context):
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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


def _render_hw_list_text(tasks):
    """Текст списка ДЗ для пользователя с кнопками-вложениями."""
    lines = ["📚 Текущие домашние задания:\n"]
    for idx, item in enumerate(tasks, start=1):
        db_id, subject, task, due_date_str, photos, _ = item
        photos_count = len(photos or [])
        marker = f" 📎×{photos_count}" if photos_count >0 else ""
        due_text = ""
        if due_date_str:
            date_obj = db.parse_due_date(due_date_str)
            due_text = f" — {db.format_due_date_for_display(date_obj)}" if date_obj else ""
        subj_str = f"<b>{subject}</b>" if subject else ""
        task_str = f"{task}" if task else ""
        if subj_str and task_str:
            body = f"{subj_str}: {task_str}"
        elif subj_str:
            body = subj_str
        else:
            body = task_str
        lines.append(f"{idx}️⃣ {body}{due_text}{marker}")
    return "\n".join(lines)


def _hw_photos_buttons(tasks):
    """Inline-кнопки под каждым ДЗ с фото: нажал → прислал фото."""
    buttons = []
    for idx, item in enumerate(tasks, start=1):
        db_id, subject, task, due_date_str, photos, _ = item
        if not photos:
            continue
        short = subject or task or "ДЗ"
        short = short[:25] + "..." if len(short) > 25 else short
        buttons.append([InlineKeyboardButton(
            f"📎 {idx}. {short}", callback_data=f"hwphoto_{db_id}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def show_hw(update, context):
    if await _check_banned_callback(update, context):
        return
    query = update.callback_query
    await query.answer()
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.edit_message_text("📭 Нет домашних заданий.", reply_markup=kb.back_button())
        return
    text = _render_hw_list_text(tasks)
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=_hw_photos_buttons(tasks))
    except Exception:
        try:
            await query.delete_message()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, parse_mode='HTML',
            reply_markup=_hw_photos_buttons(tasks),
        )


async def show_hw_photos(update, context):
    """Показывает фото ДЗ по кнопке."""
    if await _check_banned_callback(update, context):
        return
    query = update.callback_query
    await query.answer()
    try:
        task_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        return
    # Достаём нужное ДЗ
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    target = next((t for t in tasks if t[0] == task_id), None)
    if not target:
        await query.answer("❌ Не найдено.", show_alert=True)
        return
    db_id, subject, task_text, due_date_str, photos, _ = target
    if not photos:
        await query.answer("Нет вложений.", show_alert=True)
        return
    cap_lines = []
    if subject:
        cap_lines.append(f"📚<b>{subject}</b>")
    if task_text:
        cap_lines.append(task_text)
    if due_date_str:
        date_obj = db.parse_due_date(due_date_str)
        if date_obj:
            cap_lines.append(f"\n📅 {db.format_due_date_for_display(date_obj)}")
    caption = "\n".join(cap_lines) or "Вложение к ДЗ"
    try:
        await query.delete_message()
    except Exception:
        pass
    chat_id = update.effective_chat.id
    # Шлём медиа-группу если несколько фото
    if len(photos) == 1:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=photos[0], caption=caption, parse_mode='HTML')
        except Exception:
            logger.exception("send hw photo failed")
    else:
        from telegram import InputMediaPhoto
        media = []
        for i, p in enumerate(photos[:10]):
            cap = caption if i == 0 else ""
            media.append(InputMediaPhoto(media=p, caption=cap, parse_mode='HTML'))
        try:
            await context.bot.send_media_group(chat_id=chat_id, media=media)
        except Exception:
            logger.exception("send hw media_group failed")
            for p in photos:
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=p)
                except Exception:
                    pass
    # Кнопка назад к списку ДЗ
    await context.bot.send_message(
        chat_id=chat_id,
        text="🔼 Назад к списку ДЗ",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_hw")]]),
    )


async def show_announcements(update, context):
    if await _check_banned_callback(update, context):
        return
    query = update.callback_query
    await query.answer()
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        await query.edit_message_text("📭 Активных объявлений нет.", reply_markup=kb.back_button())
        return
    lines = ["📢 Активные объявления:\n"]
    for idx, (_, ann_text, created_at, is_note, photo_id) in enumerate(anns, start=1):
        date_part = created_at.split(" ")[0] if created_at else ""
        prefix = "📝 " if is_note else ("📎 " if photo_id else "")
        body = ann_text if ann_text else "(без текста — только вложение)"
        lines.append(f"{idx}️⃣ {prefix}{date_part}: {body}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button())


async def show_extra_classes(update, context):
    if await _check_banned_callback(update, context):
        return
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
            text="📚 Дополнительные занятия. Выберите:",
            reply_markup=kb.extra_classes_list_kb(items),
        )
        return
    if not items:
        await query.edit_message_text("📭 Нет активных дополнительных занятий.", reply_markup=kb.back_button())
        return
    await query.edit_message_text("📚 Дополнительные занятия. Выберите:", reply_markup=kb.extra_classes_list_kb(items))


async def extra_class_open(update, context):
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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
    await query.edit_message_text("   Расписание звонков. Выберите тип дня:", reply_markup=kb.bells_choice_kb())


async def show_bells_regular(update, context):
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
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
    if await _check_banned_callback(update, context):
        return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    text = await _render_cabinet_text_and_kb(user_id)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())


async def cabinet_toggle_notify(update, context):
    if await _check_banned_callback(update, context):
        return
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


WELCOME_NAME = 0