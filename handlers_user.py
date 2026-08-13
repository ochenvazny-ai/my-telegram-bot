import logging
import asyncio
import io
from telegram import Update
from telegram.ext import ContextTypesimport database as db
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
    "👤 Кабинет — личные заметки и настройки.\n"
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
    # Проверяем, есть ли display_name — если нет, онбординг
    settings = await asyncio.to_thread(db.get_user_settings_row, user.id)
    if not settings.get("display_name"):
        await update.message.reply_text(
            f"👋 Привет, {user.first_name or 'друг'}!\n\n"
            "Как тебя звать в боте? Это имя будет в уведомлениях.\n"
            "Просто напиши своё имя или ник:",
            reply_markup=kb.skip_name_kb(),
        )
        return    await update.message.reply_text(
        await _greeting_text(),
        reply_markup=kb.main_menu_kb(admin),
    )
    await update.message.reply_text("Меню:", reply_markup=kb.reply_menu_button())


async def start_set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Онбординг: юзер вводит имя."""
    name = update.message.text.strip()[:40]
    if not name:
        await update.message.reply_text("Имя пустое. Попробуй ещё раз:")
        return
    await asyncio.to_thread(db.set_user_display_name, update.effective_user.id, name)
    user = update.effective_user
    admin = await asyncio.to_thread(db.is_admin, user.id)
    await update.message.reply_text(f"✅ Записал: «{name}».")
    await update.message.reply_text(
        await _greeting_text(),
        reply_markup=kb.main_menu_kb(admin),
    )
    await update.message.reply_text("Меню:", reply_markup=kb.reply_menu_button())


async def start_skip_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Онбординг: юзер пропустил имя — оставляем first_name из Telegram."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    default_name = user.first_name or user.username or "Студент"
    await asyncio.to_thread(db.set_user_display_name, user.id, default_name)
    admin = await asyncio.to_thread(db.is_admin, user.id)
    try:
        await query.edit_message_text(f"✅ Окей, буду звать тебя «{default_name}».")
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=await _greeting_text(),
        reply_markup=kb.main_menu_kb(admin),
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Меню:", reply_markup=kb.reply_menu_button())


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
            chat_id=update.effective_chat.id, text=text, reply_markup=kb.main_menu_kb(admin)
        )
    else:
        user_id = update.effective_user.id
        admin = await asyncio.to_thread(db.is_admin, user_id)
        text = await _greeting_text()
        await query.edit_message_text(text, reply_markup=kb.main_menu_kb(admin))


# ===== ГЛАВНОЕ МЕНЮ: "📅 Замены" =====
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        logger.exception("check_and_broadcast_new_replacements failed")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Главное меню:", reply_markup=kb.main_menu_kb(admin)
    )


# ===== ГЛАВНОЕ МЕНЮ: "📚 Домашка" =====
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


# ===== ГЛАВНОЕ МЕНЮ: "📢 Объявления" =====
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


# ===== ГЛАВНОЕ МЕНЮ: "📚 Доп. занятия" =====
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
        await query.edit_message_text("📭 Нет активных дополнительных занятий.", reply_markup=kb.back_button())
        return
    await query.edit_message_text("📚 Дополнительные занятия. Выберите:", reply_markup=kb.extra_classes_list_kb(items))


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
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_id)
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


# ===== ГЛАВНОЕ МЕНЮ: "ℹ️ Учебная инфа" =====
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


# ===== ЛИЧНЫЙ КАБИНЕТ =====
async def show_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    name = s.get("display_name") or "не задано"
    repl = "✅" if s.get("notify_replacements") else "❌"
    ann = "✅" if s.get("notify_announcements") else "❌"
    hw = "✅" if s.get("notify_homework") else "❌"
    ec = "✅" if s.get("notify_extra_classes") else "❌"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"Имя в боте: <b>{name}</b>\n\n"
        f"🔔 Уведомления:\n"
        f"  • Замены: {repl}\n"
        f"  • Объявления: {ann}\n"
        f"  • Домашка: {hw}\n"
        f"  • Доп. занятия: {ec}\n"
    )
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())


async def cabinet_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юзер нажал «Изменить имя» — ждём ввода текста."""
    query = update.callback_query
    await query.answer()
    context.user_data['cabinet_state'] = 'awaiting_name'
    await query.edit_message_text(
        "Введите новое имя для бота:", reply_markup=kb.back_button("cabinet")
    )


async def cabinet_save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('cabinet_state') != 'awaiting_name':
        return
    name = update.message.text.strip()[:40]
    if not name:
        await update.message.reply_text("Имя пустое. Попробуй ещё раз:", reply_markup=kb.back_button("cabinet"))
        return
    await asyncio.to_thread(db.set_user_display_name, update.effective_user.id, name)
    context.user_data.pop('cabinet_state', None)
    await update.message.reply_text(f"✅ Имя изменено на «{name}».")
    # Возвращаем в кабинет
    user_id = update.effective_user.id
    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    name_disp = s.get("display_name") or "не задано"
    repl = "✅" if s.get("notify_replacements") else "❌"
    ann = "✅" if s.get("notify_announcements") else "❌"
    hw = "✅" if s.get("notify_homework") else "❌"
    ec = "✅" if s.get("notify_extra_classes") else "❌"
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"Имя в боте: <b>{name_disp}</b>\n\n"
        f"🔔 Уведомления:\n"
        f"  • Замены: {repl}\n"
        f"  • Объявления: {ann}\n"
        f"  • Домашка: {hw}\n"
        f"  • Доп. занятия: {ec}\n"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())


async def cabinet_toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # kind_on: 'replacements', 'announcements', 'homework', 'extra_classes'
    kind = query.data.split("_")[1]  # 'toggle_replacements' -> 'replacements'
    user_id = update.effective_user.id
    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    col_map = {
        "replacements": "notify_replacements",
        "announcements": "notify_announcements",
        "homework": "notify_homework",
        "extra_classes": "notify_extra_classes",
    }
    col = col_map.get(kind)
    if not col:
        return
    current = bool(s.get(col))
    new_val = not current
    await asyncio.to_thread(db.set_user_notify, user_id, kind, new_val)
    # Обновляем кабинет
    s = await asyncio.to_thread(db.get_user_settings_row, user_id)
    name_disp = s.get("display_name") or "не задано"
    repl = "✅" if s.get("notify_replacements") else "❌"
    ann = "✅" if s.get("notify_announcements") else "❌"
    hw = "✅" if s.get("notify_homework") else "❌"
    ec = "✅" if s.get("notify_extra_classes") else "❌"
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"Имя в боте: <b>{name_disp}</b>\n\n"
        f"🔔 Уведомления:\n"
        f"  • Замены: {repl}\n"
        f"  • Объявления: {ann}\n"
        f"  • Домашка: {hw}\n"
        f"  • Доп. занятия: {ec}\n"
    )
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_menu_kb())


# ===== ДОЛГИ / ЗАМЕТКИ =====
async def cabinet_open_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    notes = await asyncio.to_thread(db.get_user_notes, update.effective_user.id, 'debt')
    if not notes:
        text = "💸 У тебя нет долгов. Добавь первый:"
 else:
        lines = ["💸 <b>Мои долги:</b>\n"]
        for idx, (note_id, title, content, is_done, _) in enumerate(notes, start=1):
            mark = "✅" if is_done else "❗"
            short_title = (title[:30] + "...") if len(title) > 30 else title
            lines.append(f"{idx}️⃣ {mark} {short_title}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_notes_kb('debt'))


async def cabinet_open_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    notes = await asyncio.to_thread(db.get_user_notes, update.effective_user.id, 'note')
    if not notes:
        text = "📝 У тебя нет заметок. Добавь первую:"
    else:
        lines = ["📝 <b>Мои заметки:</b>\n"]
        for idx, (note_id, title, content, is_done, _) in enumerate(notes, start=1):
            mark = "✅" if is_done else "❗"
            short_title = (title[:30] + "...") if len(title) > 30 else title
            lines.append(f"{idx}️⃣ {mark} {short_title}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_notes_kb('note'))


async def cabinet_add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юзер нажал «Добавить долг/заметку» — ждём ввода текста."""
    query = update.callback_query
    await query.answer()
    # callback_data = 'addnote_debt' или 'addnote_note'
    kind = query.data.split("_")[1]
    context.user_data['cabinet_note_state'] = 'awaiting_title'
    context.user_data['cabinet_note_kind'] = kind
    label = "долг" if kind == 'debt' else "заметку"
    await query.edit_message_text(
        f"Введите название {label}а:", reply_markup=kb.back_button(f"cabinet_open_{'debts' if kind == 'debt' else 'notes'}")
    )


async def cabinet_add_note_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('cabinet_note_state') != 'awaiting_title':
        return
    title = update.message.text.strip()[:80]
    if not title:
        await update.message.reply_text("Название пустое. Попробуй ещё раз:")
        return
    context.user_data['cabinet_note_title'] = title
    context.user_data['cabinet_note_state'] = 'awaiting_content'
    kind = context.user_data['cabinet_note_kind']
    label = "долга" if kind == 'debt' else "заметки"
    await update.message.reply_text(
        f"Теперь введите содержимое {label} (или «-» чтобы без описания):",
        reply_markup=kb.back_button(f"cabinet_open_{'debts' if kind == 'debt' else 'notes'}")
    )


async def cabinet_add_note_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('cabinet_note_state') != 'awaiting_content':
        return
    content_text = update.message.text.strip()
    if content_text == '-':
        content = None
    else:
        content = content_text
    kind = context.user_data.get('cabinet_note_kind')
    title = context.user_data.get('cabinet_note_title')
    context.user_data.clear()
    note_id = await asyncio.to_thread(db.add_user_note, update.effective_user.id, kind, title, content)
    if note_id:
        await update.message.reply_text(f"✅ Добавлено.")
        # Возвращаем в список notes = await asyncio.to_thread(db.get_user_notes, update.effective_user.id, kind)
        if not notes:
            text = "Пусто."
        else:
            lines = [("<b>Мои долги:</b>\n" if kind == 'debt' else "<b>Мои заметки:</b>\n")]
            for idx, (n_id, ttl, cont, is_done, _) in enumerate(notes, start=1):
                mark = "✅" if is_done else "❗"
                short_title = (ttl[:30] + "...") if len(ttl) > 30 else ttl
                lines.append(f"{idx}️⃣ {mark} {short_title}")
            text = "\n".join(lines)
        await update.message.reply_text(
            text, parse_mode='HTML',
            reply_markup=kb.cabinet_notes_kb(kind)
        )
    else:
        await update.message.reply_text("❌ Ошибка.")


async def cabinet_view_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юзер выбрал конкретный долг/заметку."""
    query = update.callback_query
    await query.answer()
    # viewnote_<id>
    try:
        note_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        return
    rec = await asyncio.to_thread(db.get_user_note, note_id)
    if not rec or rec[1] != update.effective_user.id:
        await query.answer("❌ Не найдено.", show_alert=True)
        return
    _, _, kind, title, content, is_done = rec
    text = f"<b>{title}</b>\n\n{content or '(без содержимого)'}"
    back_to = "cabinet_open_debts" if kind == 'debt' else "cabinet_open_notes"
    await query.edit_message_text(
        text, parse_mode='HTML', reply_markup=kb.cabinet_note_actions_kb(note_id, is_done, back_to)
    )


async def cabinet_toggle_note_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # donenote_<id>
    try:
        note_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        return
    rec = await asyncio.to_thread(db.get_user_note, note_id)
    if not rec or rec[1] != update.effective_user.id:
        await query.answer("❌ Не найдено.", show_alert=True)
        return
    _, _, kind, title, content, is_done = rec
    await asyncio.to_thread(db.set_user_note_done, note_id, not is_done)
    # Возвращаем в список
    notes = await asyncio.to_thread(db.get_user_notes, update.effective_user.id, kind)
    if not notes:
        text = "Пусто."
    else:
        lines = [("<b>Мои долги:</b>\n" if kind == 'debt' else "<b>Мои заметки:</b>\n")]
        for idx, (n_id, ttl, cont, dn, _) in enumerate(notes, start=1):
            mark = "✅" if dn else "❗"
            short_title = (ttl[:30] + "...") if len(ttl) > 30 else ttl
            lines.append(f"{idx}️⃣ {mark} {short_title}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_notes_kb(kind))


async def cabinet_delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # delnote_<id>
    try:
        note_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        return
    rec = await asyncio.to_thread(db.get_user_note, note_id)
    if not rec or rec[1] != update.effective_user.id:
        await query.answer("❌ Не найдено.", show_alert=True)
        return
    await asyncio.to_thread(db.delete_user_note, note_id)
    kind = rec[2]
    notes = await asyncio.to_thread(db.get_user_notes, update.effective_user.id, kind)
    if not notes:
        text = "Пусто."
    else:
        lines = [("<b>Мои долги:</b>\n" if kind == 'debt' else "<b>Мои заметки:</b>\n")]
        for idx, (n_id, ttl, cont, dn, _) in enumerate(notes, start=1):
            mark = "✅" if dn else "❗"
            short_title = (ttl[:30] + "...") if len(ttl) > 30 else ttl lines.append(f"{idx}️⃣ {mark} {short_title}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.cabinet_notes_kb(kind))