import re
import io
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

import database as db
import keyboards as kb
import schedule_image as sched_img
import schedule_service as sched
from config import (
    INITIAL_ADMIN_ID, WEEKDAYS_RU,
    HW_TEXT, HW_DUE, ANN_TEXT, ANN_PHOTO, ANN_CONFIRM,
    REPLNOTE_TEXT, REPLNOTE_CONFIRM,
    SCHED_UPLOAD_TEXT, SCHED_FIELD_VALUE, ADMIN_ID, ADMIN_NAME,
    EXTRA_NAME, EXTRA_CONTENT, SET_GROUP, SET_BOT_NAME, SET_BOT_PHOTO,
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


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Отменено.\n\n👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


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


async def admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👥 Админы:", reply_markup=kb.admins_menu_kb())


async def extra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📚 Доп. занятия:", reply_markup=kb.extra_admin_menu_kb())


async def bot_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⚙️ Настройки бота:", reply_markup=kb.bot_settings_kb())


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


# ---------- ДЗ ----------
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
    await asyncio.to_thread(db.delete_task_db, task_id)
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.edit_message_text("📭 Нет текущих домашних заданий.", reply_markup=kb.admin_panel_kb())
    else:
        lines = ["Выберите задание для удаления:\n"]
        for idx, (_, task, due_date, _) in enumerate(tasks, start=1):
            due_str = f" ({due_date})" if due_date else ""
            lines.append(f"{idx}️⃣ {task}{due_str}")
        await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_hw_kb(tasks))


# ---------- ОБЪЯВЛЕНИЯ ----------
async def add_ann_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    try:
        await query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "📝 Введите текст объявления.\n"
            "После текста можно прикрепить фото.\n"
            "Если нужно только фото — напишите любой текст, потом пришлите фото."
        ),
        reply_markup=kb.cancel_button(),
    )
    return ANN_TEXT


async def add_ann_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ann_text'] = update.message.text.strip()
    await update.message.reply_text(
        f"📝 Текст объявления:\n{context.user_data['ann_text']}\n\n"
        f"Хотите прикрепить фото? Пришлите фото или нажмите «Пропустить».",
        reply_markup=kb.ann_skip_photo_kb(),
    )
    return ANN_PHOTO


async def add_ann_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = (update.message.caption or "").strip() if update.message else ""
    photo_id = None
    if update.message and update.message.photo:
        photo_id = update.message.photo[-1].file_id

    ann_text = caption if caption else context.user_data.get('ann_text', '')
    context.user_data['ann_text'] = ann_text
    context.user_data['ann_photo_id'] = photo_id

    preview_text = ann_text if ann_text else "(без текста)"
    await update.message.reply_text(
        f"📢 Текст объявления:\n{preview_text}\n📎 Вложение: фото\n\n"
        f"Отправить всем пользователям?",
        reply_markup=kb.announcement_confirm_kb(),
    )
    return ANN_CONFIRM


async def add_ann_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['ann_photo_id'] = None
    text = context.user_data.get('ann_text', '')
    await query.edit_message_text(
        f"📢 Текст объявления:\n{text}\n\nОтправить всем пользователям?",
        reply_markup=kb.announcement_confirm_kb(),
    )
    return ANN_CONFIRM


async def add_ann_change_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('ann_photo_id', None)
    await query.edit_message_text(
        "Пришлите фото (можно с подписью):",
        reply_markup=kb.cancel_button(),
    )
    return ANN_PHOTO


RATE_LIMIT_DELAY = 0.05


async def _broadcast_text(bot, text: str, has_attachment: bool) -> tuple[int, int]:
    user_ids = await asyncio.to_thread(db.get_all_user_ids)
    sent, failed = 0, 0
    broadcast_text = f"📢 {text}"
    if has_attachment:
        broadcast_text += "\n\n📎 Вложение"
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
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
    photo_id = context.user_data.get('ann_photo_id')
    author_id = update.effective_user.id
    has_attach = bool(photo_id)
    save_text = text if text else ""
    await asyncio.to_thread(db.add_announcement_db, save_text, author_id, False, photo_id)

    if query.data == "ann_send_yes":
        await query.edit_message_text("⏳ Рассылаю объявление...")
        sent, failed = await _broadcast_text(context.bot, save_text, has_attach)
        await query.message.reply_text(f"✅ Отправлено {sent}, ❌ не доставлено {failed}")
    else:
        await query.edit_message_text("✅ Объявление сохранено. Рассылка не выполнялась.")

    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


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
    for idx, item in enumerate(anns, start=1):
        ann_id, text, created_at, is_note, photo_id = item
        prefix = "📝 " if is_note else ("📎 " if photo_id else "")
        date_part = created_at.split(" ")[0] if created_at else ""
        short = text[:28] + "..." if len(text) > 28 else text
        lines.append(f"{idx}️⃣ {prefix}{date_part}: {short or '(без текста)'}")
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
        for idx, item in enumerate(anns, start=1):
            ann_id, text, created_at, is_note, photo_id = item
            prefix = "📝 " if is_note else ("📎 " if photo_id else "")
            date_part = created_at.split(" ")[0] if created_at else ""
            short = text[:28] + "..." if len(text) > 28 else text
            lines.append(f"{idx}️⃣ {prefix}{date_part}: {short or '(без текста)'}")
        await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_ann_kb(anns))


async def add_replnote_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "📝 Введите текст подписи, которая будет отображаться в разделе «Замены»:",
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
        await query.edit_message_text("✅ Подпись к замене сохранена.")
    else:
        await query.edit_message_text("❌ Отменено.")
    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ---------- АДМИНЫ ----------
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


# ---------- ДОП. ЗАНЯТИЯ ----------
async def extra_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    try:
        await query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📝 Введите название предмета:",
        reply_markup=kb.cancel_button(),
    )
    return EXTRA_NAME


async def extra_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['extra_subject'] = update.message.text.strip()
    await update.message.reply_text(
        "Пришлите фото расписания (опционально с подписью) или нажмите «Пропустить фото».",
        reply_markup=kb.extra_skip_photo_kb(),
    )
    return EXTRA_CONTENT


async def extra_add_content_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subject = context.user_data.get('extra_subject', '')
    description = (update.message.caption or "").strip() if update.message else ""
    photo_id = None
    if update.message and update.message.photo:
        photo_id = update.message.photo[-1].file_id
    new_id = await asyncio.to_thread(db.add_extra_class, subject, description or None, photo_id)
    if new_id:
        await update.message.reply_text(f"✅ Дополнительное занятие «{subject}» добавлено.")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def extra_add_content_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Если хотите добавить фото — пришлите его. Если только название — нажмите «Пропустить фото».",
        reply_markup=kb.extra_skip_photo_kb(),
    )
    return EXTRA_CONTENT


async def extra_add_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subject = context.user_data.get('extra_subject', '')
    new_id = await asyncio.to_thread(db.add_extra_class, subject, None, None)
    if new_id:
        await query.message.reply_text(f"✅ Дополнительное занятие «{subject}» добавлено.")
    else:
        await query.message.reply_text("❌ Ошибка при сохранении.")
    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def extra_del_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await query.edit_message_text("📭 Нет активных доп. занятий.", reply_markup=kb.back_button("a_extra_menu"))
        return
    await query.edit_message_text(
        "Выберите занятие для удаления:", reply_markup=kb.extra_delete_kb(items)
    )


async def extra_del_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    item_id = int(query.data.split("_")[1])
    rec = await asyncio.to_thread(db.get_extra_class, item_id)
    if not rec:
        await query.answer("❌ Не найдено.", show_alert=True)
        return
    context.user_data['pending_extra_id'] = item_id
    await query.edit_message_text(
        f"⚠️ Точно удалить занятие «{rec[1]}»?",
        reply_markup=kb.confirm_kb("delextra", item_id),
    )


async def extra_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    item_id = context.user_data.pop('pending_extra_id', None)
    if item_id is not None:
        await asyncio.to_thread(db.deactivate_extra_class, item_id)
    await query.edit_message_text("🗑 Занятие удалено.", reply_markup=kb.admin_panel_kb())


async def extra_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await query.edit_message_text("📭 Нет активных доп. занятий.", reply_markup=kb.back_button("a_extra_menu"))
        return
    lines = ["👀 Активные дополнительные занятия:\n"]
    for idx, (item_id, subject, description, photo_id, created_at) in enumerate(items, start=1):
        date_part = created_at.split(" ")[0] if created_at else ""
        marker = "📎" if photo_id else ""
        snippet = (description or "")[:40]
        lines.append(f"{idx}️⃣ {marker}{subject} ({date_part}) {snippet}{'…' if snippet and len(description or '') > 40 else ''}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button("a_extra_menu"))


# ---------- НАСТРОЙКИ БОТА ----------
async def set_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    try:
        await query.message.delete()
    except Exception:
        pass
    current = await asyncio.to_thread(db.get_group_name)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Текущее название группы: <b>{current}</b>\n\nВведите новое название:",
        parse_mode='HTML',
        reply_markup=kb.cancel_button(),
    )
    return SET_GROUP


async def set_group_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    loading = await update.message.reply_text("⏳ Сохраняю название группы...")
    await asyncio.to_thread(db.set_group_name, name)
    try:
        await loading.delete()
    except Exception:
        pass
    await update.message.reply_text(f"✅ Название группы изменено на «{name}».")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def set_bot_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    try:
        await query.message.delete()
    except Exception:
        pass
    current = await asyncio.to_thread(db.get_bot_display_name)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Текущее название для водяного знака: <b>{current}</b>\n\n"
             "Введите новое название:",
        parse_mode='HTML',
        reply_markup=kb.cancel_button(),
    )
    return SET_BOT_NAME


async def set_bot_name_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    loading = await update.message.reply_text("⏳ Сохраняю и перегенерирую картинки...")
    await asyncio.to_thread(db.set_bot_display_name, name)
    tg_ok = False
    try:
        await context.bot.set_my_name(name=name)
        tg_ok = True
    except Exception:
        logger.exception("set_my_name failed")
    try:
        await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    except Exception:
        logger.exception("regenerate cache after rename failed")
    try:
        await loading.delete()
    except Exception:
        pass
    msg = f"✅ Название для водяного знака изменено на «{name}». Картинки перегенерированы."
    if tg_ok:
        msg += "\nИмя в Telegram тоже обновлено."
    else:
        msg += "\n⚠️ Имя в Telegram обновить не удалось (недостаточно прав)."
    await update.message.reply_text(msg)
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def set_bot_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    try:
        await query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Пришлите новую картинку для бота (фото).\n\n"
            "⚠️ Telegram Bot API не поддерживает смену аватарки бота программно. "
            "Сделайте это через @BotFather → /setuserpic."
        ),
        reply_markup=kb.cancel_button(),
    )
    return SET_BOT_PHOTO


async def set_bot_photo_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Смена аватарки бота через API невозможна. Сделайте это вручную через @BotFather → /setuserpic."
    )
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# ---------- РАСПИСАНИЕ ----------
async def edit_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⚙️ Изменение расписания:", reply_markup=kb.schedule_edit_menu_kb())


async def force_broadcast_replacements_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «📣 Разослать замены сейчас» в меню расписания."""
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⏳ Рассылаю замены всем пользователям...")
    try:
        sent = await sched.force_broadcast_replacements()
        if sent < 0:
            await query.edit_message_text("❌ Не удалось получить данные с сайта колледжа.", reply_markup=kb.schedule_edit_menu_kb())
        else:
            await query.edit_message_text(f"✅ Разослано {sent} пользователям.", reply_markup=kb.schedule_edit_menu_kb())
    except Exception:
        logger.exception("force_broadcast_replacements failed")
        await query.edit_message_text("❌ Ошибка при рассылке.", reply_markup=kb.schedule_edit_menu_kb())


async def sched_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "📤 Заполните этот файл и пришлите его обратно:",
        reply_markup=kb.cancel_button(),
    )
    template_path = os.path.join(os.path.dirname(__file__), "assets", "schedule_template.xlsx")
    try:
        with open(template_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename="Формат_Расписания.xlsx",
                caption=(
                    "Впишите занятия в пустые ячейки. Для каждого дня — строки с номерами пар 0–6.\n"
                    "Слева — Числитель, справа — Знаменатель. Пустая строка = пары нет."
                ),
            )
    except FileNotFoundError:
        logger.exception("Файл-шаблон не найден")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Файл-шаблон не найден на сервере.",
        )
    return SCHED_UPLOAD_TEXT


def _parse_schedule_xlsx(file_bytes: bytes):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    result = {}
    errors = []
    current_day = None

    for row_idx, row in enumerate(rows, start=1):
        if row is None or all(c is None for c in row):
            continue
        cells = list(row) + [None] * (7 - len(row)) if len(row) < 7 else list(row[:7])
        col0 = cells[0]

        if row_idx <= 2:
            continue

        if isinstance(col0, str):
            day_norm = col0.strip().lower()
            if day_norm in WEEKDAYS_RU:
                current_day = WEEKDAYS_RU.index(day_norm)
                result.setdefault(("Числитель", current_day), [])
                result.setdefault(("Знаменатель", current_day), [])
            continue

        if current_day is None:
            continue
        try:
            pair_num = int(col0)
        except (TypeError, ValueError):
            errors.append(f"Строка {row_idx}: не удалось определить номер пары")
            continue

        subj_num, teach_num, room_num = cells[1], cells[2], cells[3]
        subj_den, teach_den, room_den = cells[4], cells[5], cells[6]

        if subj_num:
            result.setdefault(("Числитель", current_day), []).append({
                "pair_number": pair_num,
                "subject": str(subj_num).strip(),
                "teacher": str(teach_num).strip() if teach_num else "",
                "room": str(room_num).strip() if room_num else "",
            })
        if subj_den:
            result.setdefault(("Знаменатель", current_day), []).append({
                "pair_number": pair_num,
                "subject": str(subj_den).strip(),
                "teacher": str(teach_den).strip() if teach_den else "",
                "room": str(room_den).strip() if room_den else "",
            })

    return result, errors


async def sched_upload_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document or not document.file_name.lower().endswith(".xlsx"):
        await update.message.reply_text(
            "❌ Нужен файл в формате .xlsx:", reply_markup=kb.cancel_button()
        )
        return SCHED_UPLOAD_TEXT

    tg_file = await document.get_file()
    file_bytes = bytes(await tg_file.download_as_bytearray())

    try:
        parsed, errors = await asyncio.to_thread(_parse_schedule_xlsx, file_bytes)
    except Exception:
        logger.exception("Ошибка парсинга xlsx")
        await update.message.reply_text("❌ Не удалось прочитать файл.", reply_markup=kb.cancel_button())
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
    context.user_data['pending_schedule'] = parsed
    preview_lines.append("\n⚠️ Это ЗАМЕНИТ текущее расписание. Подтвердить?")
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
        try:
            await query.edit_message_text("❌ Данные потеряны.", reply_markup=kb.bot_settings_kb())
        except Exception:
            pass
        return
    try:
        await query.delete_message()
    except Exception:
        pass
    loading_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Загружаю расписание...")
    try:
        for (week_type, day_idx), entries in parsed.items():
            await asyncio.to_thread(db.replace_day_schedule, week_type, day_idx, entries)
        await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    except Exception:
        logger.exception("Не удалось применить расписание")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ошибка при сохранении.",
            reply_markup=kb.bot_settings_kb(),
        )
        return
    try:
        await loading_msg.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Расписание обновлено и картинки перегенерированы.",
        reply_markup=kb.bot_settings_kb(),
    )


async def del_all_day_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text(
        "Выберите день для удаления ВСЕХ пар (оба типа недели):",
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
    await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    await query.edit_message_text(
        f"🗑 Все пары на {WEEKDAYS_RU[day_idx]} удалены.",
        reply_markup=kb.bot_settings_kb(),
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
        f"Пара {pair_num} ({week_type}, {WEEKDAYS_RU[int(day_idx)]}).",
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
    await query.edit_message_text(f"Введите предмет для пары {next_pair}:", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_delete_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx, pair_num = query.data.split("_")
    await asyncio.to_thread(db.delete_pair, week_type, int(day_idx), int(pair_num))
    await asyncio.to_thread(sched_img.regenerate_all_cached_images)
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
    await query.edit_message_text(f"Введите ({field_names[field]}):", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    edit = context.user_data.get('sched_edit', {})
    week_type, day_idx, pair_num = edit.get('week_type'), edit.get('day_idx'), edit.get('pair_num')

    if edit.get('field') in ('subject', 'teacher', 'room') and 'is_new' not in edit:
        pairs_existing = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
        is_new_pair = pair_num not in pairs_existing
        if is_new_pair and edit.get('subject', None) == "":
            edit['subject'] = value
            edit['field'] = 'teacher'
            edit['is_new'] = True
            context.user_data['sched_edit'] = edit
            await update.message.reply_text("Введите преподавателя:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE

    if edit.get('is_new'):
        if edit['field'] == 'teacher':
            edit['teacher'] = value
            edit['field'] = 'room'
            context.user_data['sched_edit'] = edit
            await update.message.reply_text("Введите аудиторию:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE
        elif edit['field'] == 'room':
            edit['room'] = value
            await asyncio.to_thread(
                db.upsert_pair, week_type, day_idx, pair_num, edit['subject'], edit['teacher'], edit['room']
            )
            await asyncio.to_thread(sched_img.regenerate_all_cached_images)
            await update.message.reply_text(f"✅ Пара {pair_num} добавлена.")
            context.user_data.pop('sched_edit', None)
            await update.message.reply_text("⚙️ Настройки бота", reply_markup=kb.bot_settings_kb())
            return ConversationHandler.END

    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, day_idx)
    current = pairs.get(pair_num, {"subject": "", "teacher": "", "room": ""})
    current[edit['field']] = value
    await asyncio.to_thread(
        db.upsert_pair, week_type, day_idx, pair_num, current['subject'], current['teacher'], current['room']
    )
    await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    await update.message.reply_text("✅ Обновлено.")
    context.user_data.pop('sched_edit', None)
    await update.message.reply_text("⚙️ Настройки бота", reply_markup=kb.bot_settings_kb())
    return ConversationHandler.END