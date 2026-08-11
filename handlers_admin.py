import re
import io
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

import database as db
import keyboards as kb
from config import (
    INITIAL_ADMIN_ID, WEEKDAYS_RU,
    HW_TEXT, HW_DUE, ANN_TEXT, ANN_CONFIRM, REPLNOTE_TEXT, REPLNOTE_CONFIRM, PH_DATE,
    SCHED_UPLOAD_TEXT, SCHED_FIELD_VALUE, ADMIN_ID, ADMIN_NAME,
)

logger = logging.getLogger(__name__)


async def _require_admin(update: Update) -> bool:
    query = update.callback_query
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    if not admin:
        await query.answer("⛔ Нет прав.", show_alert=True)
        return False
    return True


async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())


async def back_to_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ============ ВХОД В ПОДМЕНЮ ВЕРХНЕГО УРОВНЯ ============
async def hw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📚 Домашнее задание:", reply_markup=kb.hw_menu_kb())


async def ann_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📢 Объявления:", reply_markup=kb.ann_menu_kb())


async def ph_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📅 Праздничный день:", reply_markup=kb.ph_menu_kb())


async def admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👥 Админы:", reply_markup=kb.admins_menu_kb())


# ============ СМЕНА ============
async def shift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    current = await asyncio.to_thread(db.get_current_shift)
    await query.edit_message_text(
        f"🔁 Текущая смена: {current}. Выберите смену:", reply_markup=kb.shift_choice_kb()
    )


async def shift_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    shift = query.data.split("_")[1]
    await asyncio.to_thread(db.set_current_shift, shift)
    await query.edit_message_text(f"✅ Смена изменена на {shift} смену.", reply_markup=kb.admin_panel_kb())


# ============ ДОБАВЛЕНИЕ ДЗ ============
async def add_hw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("📝 Введите текст задания:", reply_markup=kb.cancel_button())
    return HW_TEXT


async def add_hw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_text'] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Введите срок сдачи (свободная форма) или '-' без срока:", reply_markup=kb.cancel_button()
    )
    return HW_DUE


async def add_hw_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    due_date = None if text == "-" else text
    task_text = context.user_data.get('task_text')
    new_id = await asyncio.to_thread(db.add_task_db, task_text, due_date)
    if new_id:
        due_display = f"срок: {due_date}" if due_date else "без срока"
        await update.message.reply_text(f"✅ Добавлено задание:\n{task_text}\n{due_display}")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении задания.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ============ УДАЛЕНИЕ ДЗ (без Conversation, чисто кнопки) ============
async def del_hw_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.edit_message_text("📭 Нет заданий для удаления.", reply_markup=kb.admin_panel_kb())
        return
    lines = ["Выберите задание для удаления:\n"]
    for idx, (_, task, due_date, _) in enumerate(tasks, start=1):
        due_str = f" ({due_date})" if due_date else ""
        lines.append(f"{idx}️⃣ {task}{due_str}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_hw_kb(tasks))


async def del_hw_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    task_id = int(query.data.split("_")[1])
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    task_text = next((t for _id, t, *_ in tasks if _id == task_id), None)
    if not task_text:
        await query.edit_message_text("❌ Задание не найдено.", reply_markup=kb.admin_panel_kb())
        return
    context.user_data['pending_hw_id'] = task_id
    await query.edit_message_text(
        f"⚠️ Точно удалить задание?\n\n{task_text}", reply_markup=kb.confirm_kb("delhw", task_id)
    )


async def del_hw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    task_id = context.user_data.pop('pending_hw_id', None)
    if task_id is None:
        await query.edit_message_text("❌ Ошибка.", reply_markup=kb.admin_panel_kb())
        return
    ok = await asyncio.to_thread(db.delete_task_db, task_id)
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.edit_message_text("📭 Нет текущих домашних заданий.", reply_markup=kb.admin_panel_kb())
    else:
        lines = ["Выберите задание для удаления:\n"]
        for idx, (_, task, due_date, _) in enumerate(tasks, start=1):
            due_str = f" ({due_date})" if due_date else ""
            lines.append(f"{idx}️⃣ {task}{due_str}")
        await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_hw_kb(tasks))


# ============ СОЗДАНИЕ ОБЪЯВЛЕНИЯ ============
async def add_ann_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("📝 Введите текст объявления:", reply_markup=kb.cancel_button())
    return ANN_TEXT


async def add_ann_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['ann_text'] = text
    await update.message.reply_text(
        f"📢 Текст объявления:\n{text}\n\nОтправить всем пользователям?",
        reply_markup=kb.announcement_confirm_kb(),
    )
    return ANN_CONFIRM


RATE_LIMIT_DELAY = 0.05  # ~20 сообщений/сек, с запасом от лимита Telegram


async def _broadcast(bot, text: str) -> tuple[int, int]:
    user_ids = await asyncio.to_thread(db.get_all_user_ids)
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=f"📢 {text}")
            sent += 1
        except Exception:
            failed += 1
            logger.warning("Не удалось отправить объявление пользователю %s", uid)
        await asyncio.sleep(RATE_LIMIT_DELAY)
    return sent, failed


async def add_ann_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = context.user_data.get('ann_text', '')
    author_id = update.effective_user.id
    ann_id = await asyncio.to_thread(db.add_announcement_db, text, author_id)

    if query.data == "ann_send_yes":
        await query.edit_message_text("⏳ Рассылаю объявление...")
        sent, failed = await _broadcast(context.bot, text)
        await query.message.reply_text(f"✅ Отправлено {sent}, ❌ не доставлено {failed}")
    else:
        await query.edit_message_text("✅ Объявление сохранено. Рассылка не выполнялась.")

    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ============ УДАЛЕНИЕ ОБЪЯВЛЕНИЯ (включая подписи к заменам) ============
async def del_ann_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        await query.edit_message_text("📭 Нет активных объявлений.", reply_markup=kb.admin_panel_kb())
        return
    lines = ["Выберите объявление для удаления:\n"]
    for idx, (_, text, created_at, is_note) in enumerate(anns, start=1):
        prefix = "📝 " if is_note else ""
        lines.append(f"{idx}️⃣ {prefix}{created_at.split(' ')[0]}: {text}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_ann_kb(anns))


async def del_ann_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    ann_id = int(query.data.split("_")[1])
    context.user_data['pending_ann_id'] = ann_id
    await query.edit_message_text("⚠️ Точно удалить объявление?", reply_markup=kb.confirm_kb("delann", ann_id))


async def del_ann_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    ann_id = context.user_data.pop('pending_ann_id', None)
    if ann_id is not None:
        await asyncio.to_thread(db.deactivate_announcement_db, ann_id)
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        await query.edit_message_text("📭 Нет активных объявлений.", reply_markup=kb.admin_panel_kb())
    else:
        lines = ["Выберите объявление для удаления:\n"]
        for idx, (_, text, created_at, is_note) in enumerate(anns, start=1):
            prefix = "📝 " if is_note else ""
            lines.append(f"{idx}️⃣ {prefix}{created_at.split(' ')[0]}: {text}")
        await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_ann_kb(anns))


# ============ ПОДПИСЬ К ЗАМЕНЕ (без рассылки) ============
async def add_replnote_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "📝 Введите текст подписи, которая будет отображаться в разделе «Замены» и в общем списке объявлений:",
        reply_markup=kb.cancel_button(),
    )
    return REPLNOTE_TEXT


async def add_replnote_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['replnote_text'] = text
    await update.message.reply_text(
        f"📝 Текст подписи:\n{text}\n\nСохранить?", reply_markup=kb.replnote_confirm_kb()
    )
    return REPLNOTE_CONFIRM


async def add_replnote_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "replnote_save_yes":
        text = context.user_data.get('replnote_text', '')
        author_id = update.effective_user.id
        await asyncio.to_thread(db.add_announcement_db, text, author_id, True)
        await query.edit_message_text(
            "✅ Подпись к замене сохранена. Она будет показываться в разделе «Замены» и в общем списке объявлений."
        )
    else:
        await query.edit_message_text("❌ Отменено.")
    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ============ ПРЕДПРАЗДНИЧНЫЕ ДНИ ============
async def set_ph_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Точка входа «Назначить предпраздничный день» — теперь сначала выбор варианта."""
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("Когда предпраздничный день?", reply_markup=kb.ph_set_choice_kb())


async def set_ph_quick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    days_ahead = 1 if query.data == "phset_tomorrow" else 2
    target = datetime.now().date() + timedelta(days=days_ahead)
    mmdd = target.strftime("%m-%d")
    ok = await asyncio.to_thread(db.set_pre_holiday, mmdd)
    display = target.strftime("%d.%m")
    if ok:
        await query.edit_message_text(f"✅ Предпраздничный день {display} назначен.", reply_markup=kb.admin_panel_kb())
    else:
        await query.edit_message_text("❌ Ошибка при сохранении.", reply_markup=kb.admin_panel_kb())


async def set_ph_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручной ввод даты — вызывается из кнопки «Назначить дату»."""
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("Введите дату в формате ДД.ММ (например, 09.05):", reply_markup=kb.cancel_button())
    return PH_DATE


async def set_ph_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    m = re.match(r'^(\d{2})\.(\d{2})$', text)
    if not m:
        await update.message.reply_text(
            "❌ Неверный формат. Введите дату как ДД.ММ (например, 09.05):", reply_markup=kb.cancel_button()
        )
        return PH_DATE
    day, month = m.group(1), m.group(2)
    mmdd = f"{month}-{day}"
    ok = await asyncio.to_thread(db.set_pre_holiday, mmdd)
    if ok:
        await update.message.reply_text(f"✅ Предпраздничный день {text} назначен.")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении.")
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def unset_ph_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_pre_holidays)
    if not items:
        await query.edit_message_text("📭 Нет активных предпраздничных дней.", reply_markup=kb.admin_panel_kb())
        return
    display_items = [(i, f"{d.split('-')[1]}.{d.split('-')[0]}") for i, d in items]
    await query.edit_message_text(
        "Выберите предпраздничный день для отмены:", reply_markup=kb.pre_holiday_list_kb(display_items, "unsetph")
    )


async def unset_ph_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    ph_id = int(query.data.split("_")[1])
    ok = await asyncio.to_thread(db.unset_pre_holiday, ph_id)
    items = await asyncio.to_thread(db.get_active_pre_holidays)
    if not items:
        await query.edit_message_text("📭 Нет активных предпраздничных дней.", reply_markup=kb.admin_panel_kb())
    else:
        display_items = [(i, f"{d.split('-')[1]}.{d.split('-')[0]}") for i, d in items]
        await query.edit_message_text(
            "🗑 Отменено. Осталось:", reply_markup=kb.pre_holiday_list_kb(display_items, "unsetph")
        )


# ============ АДМИНЫ ============
async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "Отправьте числовой Telegram ID пользователя.\nЕго можно узнать командой /myid.",
        reply_markup=kb.cancel_button(),
    )
    return ADMIN_ID


async def add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз:", reply_markup=kb.cancel_button())
        return ADMIN_ID
    context.user_data['new_admin_id'] = int(text)
    await update.message.reply_text("Введите имя для отображения в списке:", reply_markup=kb.cancel_button())
    return ADMIN_NAME


async def add_admin_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user_id = context.user_data.get('new_admin_id')
    ok = await asyncio.to_thread(db.add_admin_to_db, user_id, f"id{user_id}", name)
    if ok:
        await update.message.reply_text(f"✅ Админ {name} (ID {user_id}) добавлен.")
    else:
        await update.message.reply_text("❌ Ошибка: возможно, уже админ.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def del_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    admins = await asyncio.to_thread(db.get_all_admins)
    buttons = kb.delete_admin_kb(admins, update.effective_user.id, INITIAL_ADMIN_ID)
    if not buttons:
        await query.edit_message_text("Нет доступных для удаления админов.", reply_markup=kb.admin_panel_kb())
        return
    await query.edit_message_text("Выберите админа для удаления:", reply_markup=buttons)


async def del_admin_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = int(query.data.split("_")[1])
    if target_id == INITIAL_ADMIN_ID:
        await query.answer("❌ Нельзя удалить создателя бота.", show_alert=True)
        return
    if target_id == update.effective_user.id:
        await query.answer("❌ Нельзя удалить самого себя.", show_alert=True)
        return
    admins = await asyncio.to_thread(db.get_all_admins)
    name = next((n for uid, _, n in admins if uid == target_id), str(target_id))
    context.user_data['pending_admin_id'] = target_id
    await query.edit_message_text(
        f"⚠️ Точно удалить админа {name} (ID {target_id})?", reply_markup=kb.confirm_kb("deladmin", target_id)
    )


async def del_admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = context.user_data.pop('pending_admin_id', None)
    if target_id is not None:
        await asyncio.to_thread(db.remove_admin_by_user_id, target_id)
    await query.edit_message_text("✅ Админ удалён.", reply_markup=kb.admin_panel_kb())


async def view_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    admins = await asyncio.to_thread(db.get_all_admins)
    if not admins:
        await query.edit_message_text("📭 Список админов пуст.", reply_markup=kb.back_button("a_admins_menu"))
        return
    lines = ["👥 Список админов:\n"]
    for idx, (user_id, username, name) in enumerate(admins, start=1):
        lines.append(f"{idx}️⃣ {name} (ID: {user_id})")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button("a_admins_menu"))


# ============ РЕДАКТОР РАСПИСАНИЯ ============
async def edit_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("Изменение расписания:", reply_markup=kb.schedule_edit_menu_kb())


async def sched_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "📤 Пришлите файл .xlsx с заголовком в первой строке (порядок колонок не важен):\n\n"
        "Тип недели | День | Номер пары | Предмет | Преподаватель | Кабинет\n\n"
        "Тип недели: «Числитель» или «Знаменатель».\n"
        "День: понедельник…суббота.",
        reply_markup=kb.cancel_button(),
    )
    return SCHED_UPLOAD_TEXT


_HEADER_ALIASES = {
    "week_type": ["тип недели", "неделя", "числитель/знаменатель"],
    "day": ["день", "день недели"],
    "pair_number": ["номер пары", "пара", "№ пары"],
    "subject": ["предмет", "дисциплина"],
    "teacher": ["преподаватель", "препод"],
    "room": ["кабинет", "аудитория"],
}


def _detect_columns(header_row) -> dict:
    """Ищет индекс колонки для каждого логического поля по заголовку (регистронезависимо)."""
    col_map = {}
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_norm = str(cell).strip().lower()
        for field, aliases in _HEADER_ALIASES.items():
            if field in col_map:
                continue
            if cell_norm in aliases:
                col_map[field] = idx
    return col_map


def _parse_schedule_xlsx(file_bytes: bytes):
    """Парсит .xlsx в {(week_type, day_index): [entries]} по заголовкам колонок (порядок не важен)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {}, ["Файл пуст"]

    col_map = _detect_columns(rows[0])
    required = {"week_type", "day", "pair_number", "subject"}
    missing = required - col_map.keys()
    if missing:
        return {}, [f"Не найдены обязательные колонки в заголовке: {', '.join(missing)}. "
                     f"Проверьте, что первая строка файла — заголовки."]

    result = {}
    errors = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if row is None or all(c is None for c in row):
            continue

        def get(field):
            i = col_map.get(field)
            return row[i] if i is not None and i < len(row) else None

        week_type_raw = get("week_type")
        day_raw = get("day")
        pair_raw = get("pair_number")
        subject_raw = get("subject")
        teacher_raw = get("teacher")
        room_raw = get("room")

        if not week_type_raw or not day_raw or pair_raw is None or not subject_raw:
            errors.append(f"Строка {row_idx}: пропущены обязательные поля")
            continue

        week_type = str(week_type_raw).strip()
        if week_type not in ("Числитель", "Знаменатель"):
            errors.append(f"Строка {row_idx}: неверный тип недели '{week_type}'")
            continue

        day_norm = str(day_raw).strip().lower()
        if day_norm not in WEEKDAYS_RU:
            errors.append(f"Строка {row_idx}: неизвестный день '{day_raw}'")
            continue
        day_idx = WEEKDAYS_RU.index(day_norm)

        try:
            pair_num = int(pair_raw)
        except (TypeError, ValueError):
            errors.append(f"Строка {row_idx}: номер пары не число")
            continue

        result.setdefault((week_type, day_idx), []).append({
            "pair_number": pair_num,
            "subject": str(subject_raw).strip(),
            "teacher": str(teacher_raw).strip() if teacher_raw else "",
            "room": str(room_raw).strip() if room_raw else "",
        })
    return result, errors


async def sched_upload_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document or not document.file_name.lower().endswith(".xlsx"):
        await update.message.reply_text(
            "❌ Нужен файл в формате .xlsx. Пришлите файл ещё раз:", reply_markup=kb.cancel_button()
        )
        return SCHED_UPLOAD_TEXT

    tg_file = await document.get_file()
    file_bytes = bytes(await tg_file.download_as_bytearray())

    try:
        parsed, errors = await asyncio.to_thread(_parse_schedule_xlsx, file_bytes)
    except Exception:
        logger.exception("Ошибка парсинга xlsx")
        await update.message.reply_text(
            "❌ Не удалось прочитать файл. Убедитесь, что это корректный .xlsx, и попробуйте снова:",
            reply_markup=kb.cancel_button(),
        )
        return SCHED_UPLOAD_TEXT

    if not parsed:
        msg = "❌ Не удалось распознать ни одной строки."
        if errors:
            msg += "\n\nОшибки:\n" + "\n".join(errors[:10])
        await update.message.reply_text(msg, reply_markup=kb.cancel_button())
        return SCHED_UPLOAD_TEXT

    preview_lines = ["Найдено:\n"]
    for (week_type, day_idx), entries in parsed.items():
        preview_lines.append(f"{week_type}, {WEEKDAYS_RU[day_idx]}: {len(entries)} пар")
    if errors:
        preview_lines.append(f"\n⚠️ Пропущено строк с ошибками: {len(errors)}")
        preview_lines.extend(errors[:5])
    context.user_data['pending_schedule'] = parsed
    preview_lines.append("\n⚠️ Это ЗАМЕНИТ текущее расписание для указанных дней. Подтвердить?")
    await update.message.reply_text(
        "\n".join(preview_lines),
        reply_markup=kb.confirm_kb("schedupload", "0"),
    )
    return ConversationHandler.END


async def sched_upload_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parsed = context.user_data.pop('pending_schedule', None)
    if not parsed:
        await query.edit_message_text("❌ Данные для загрузки потеряны. Попробуйте заново.", reply_markup=kb.admin_panel_kb())
        return
    for (week_type, day_idx), entries in parsed.items():
        await asyncio.to_thread(db.replace_day_schedule, week_type, day_idx, entries)
    await query.edit_message_text("✅ Расписание обновлено.", reply_markup=kb.admin_panel_kb())


async def del_all_day_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text(
        "Выберите день, для которого удалить ВСЕ пары (оба типа недели):",
        reply_markup=kb.delete_all_day_kb(),
    )


async def sched_by_day_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("Выберите день недели:", reply_markup=kb.weekday_choice_kb())


async def sched_day_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day_idx = int(query.data.split("_")[1])
    await query.edit_message_text(
        f"{WEEKDAYS_RU[day_idx].capitalize()}. Выберите тип недели:", reply_markup=kb.week_type_kb(day_idx)
    )


async def sched_delete_all_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day_idx = int(query.data.split("_")[1])
    await asyncio.to_thread(db.delete_all_pairs_for_day, day_idx)
    await query.edit_message_text(
        f"🗑 Все пары на {WEEKDAYS_RU[day_idx]} удалены (оба типа недели).",
        reply_markup=kb.admin_panel_kb(),
    )


async def sched_week_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx = query.data.split("_")
    day_idx = int(day_idx)
    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
    if not pairs:
        text = f"{week_type}, {WEEKDAYS_RU[day_idx]}: пар пока нет."
    else:
        lines = [f"{week_type}, {WEEKDAYS_RU[day_idx]}:\n"]
        for num, info in sorted(pairs.items()):
            lines.append(f"{num}. {info['subject']} ({info['teacher']}) — {info['room']}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.pair_choice_kb(pairs, week_type, day_idx))


async def sched_pair_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx, pair_num = query.data.split("_")
    await query.edit_message_text(
        f"Пара {pair_num} ({week_type}, {WEEKDAYS_RU[int(day_idx)]}). Что изменить?",
        reply_markup=kb.pair_field_kb(week_type, int(day_idx), int(pair_num)),
    )


async def sched_new_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx = query.data.split("_")
    day_idx = int(day_idx)
    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
    next_pair = max(pairs.keys(), default=0) + 1
    context.user_data['sched_edit'] = {
        "week_type": week_type, "day_idx": day_idx, "pair_num": next_pair, "field": "subject",
        "subject": "", "teacher": "", "room": "",
    }
    await query.edit_message_text(f"Введите предмет для новой пары {next_pair}:", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_delete_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, week_type, day_idx, pair_num = query.data.split("_")
    await asyncio.to_thread(db.delete_pair, week_type, int(day_idx), int(pair_num))
    await query.answer("Пара удалена", show_alert=True)
    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, int(day_idx))
    lines = [f"{week_type}, {WEEKDAYS_RU[int(day_idx)]}:\n"]
    for num, info in sorted(pairs.items()):
        lines.append(f"{num}. {info['subject']} ({info['teacher']}) — {info['room']}")
    await query.edit_message_text("\n".join(lines) or "Пар пока нет.",
                                   reply_markup=kb.pair_choice_kb(pairs, week_type, int(day_idx)))


async def sched_field_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, field, week_type, day_idx, pair_num = query.data.split("_")
    context.user_data['sched_edit'] = {
        "week_type": week_type, "day_idx": int(day_idx), "pair_num": int(pair_num), "field": field,
    }
    field_names = {"subject": "предмет", "teacher": "преподавателя", "room": "аудиторию"}
    await query.edit_message_text(f"Введите новое значение ({field_names[field]}):", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    edit = context.user_data.get('sched_edit', {})
    week_type, day_idx, pair_num = edit.get('week_type'), edit.get('day_idx'), edit.get('pair_num')

    # Сценарий "новая пара": последовательно спрашиваем subject -> teacher -> room
    if edit.get('field') in ('subject', 'teacher', 'room') and 'is_new' not in edit:
        pairs_existing = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
        is_new_pair = pair_num not in pairs_existing
        if is_new_pair and edit.get('subject', None) == "":
            edit['subject'] = value
            edit['field'] = 'teacher'
            edit['is_new'] = True
            context.user_data['sched_edit'] = edit
            await update.message.reply_text("Теперь введите преподавателя:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE

    if edit.get('is_new'):
        if edit['field'] == 'teacher':
            edit['teacher'] = value
            edit['field'] = 'room'
            context.user_data['sched_edit'] = edit
            await update.message.reply_text("Теперь введите аудиторию:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE
        elif edit['field'] == 'room':
            edit['room'] = value
            await asyncio.to_thread(
                db.upsert_pair, week_type, day_idx, pair_num, edit['subject'], edit['teacher'], edit['room']
            )
            await update.message.reply_text(f"✅ Пара {pair_num} добавлена.")
            context.user_data.pop('sched_edit', None)
            await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
            return ConversationHandler.END

    # Обычное редактирование одного поля существующей пары
    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
    current = pairs.get(pair_num, {"subject": "", "teacher": "", "room": ""})
    current[edit['field']] = value
    await asyncio.to_thread(
        db.upsert_pair, week_type, day_idx, pair_num, current['subject'], current['teacher'], current['room']
    )
    await update.message.reply_text("✅ Обновлено.")
    context.user_data.pop('sched_edit', None)
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ============ ОТМЕНА ============
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Отменено.\n\n👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END
