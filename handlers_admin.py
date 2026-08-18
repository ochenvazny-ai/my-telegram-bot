import re
import io
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters,
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


async def _require_admin(update):
    query = update.callback_query
    user_id = update.effective_user.id
    admin = await asyncio.to_thread(db.is_admin, user_id)
    if not admin:
        await query.answer("⛔ Нет прав.", show_alert=True)
        return False
    return True


async def admin_panel_entry(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())


async def back_to_admin_panel(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def cancel_conversation(update, context):
    context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Отменено.\n\n👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def hw_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📚 Домашнее задание:", reply_markup=kb.hw_menu_kb())


async def ann_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📢 Объявления:", reply_markup=kb.ann_menu_kb())


async def admins_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👥 Админы:", reply_markup=kb.admins_menu_kb())


async def extra_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("📚 Доп. занятия:", reply_markup=kb.extra_admin_menu_kb())


async def bot_settings_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⚙️ Настройки бота:", reply_markup=kb.bot_settings_kb())


async def shift_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    current = await asyncio.to_thread(db.get_current_shift)
    await query.edit_message_text(
        f"🔁 Текущая смена: {current}. Выберите смену:", reply_markup=kb.shift_choice_kb()
    )


async def shift_set(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    shift = query.data.split("_")[1]
    await asyncio.to_thread(db.set_current_shift, shift)
    await query.edit_message_text(f"✅ Смена изменена на {shift} смену.", reply_markup=kb.admin_panel_kb())


# === ДЗ ===
async def add_hw_start(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("📝 Введите текст задания:", reply_markup=kb.cancel_button())
    return HW_TEXT


async def add_hw_text(update, context):
    context.user_data['task_text'] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Введите срок сдачи или '-' без срока:", reply_markup=kb.cancel_button()
    )
    return HW_DUE


async def add_hw_due(update, context):
    text = update.message.text.strip()
    due_date = None if text == "-" else text
    task_text = context.user_data.get('task_text')
    new_id = await asyncio.to_thread(db.add_task_db, task_text, due_date)
    if new_id:
        await update.message.reply_text(f"✅ Добавлено.")
    else:
        await update.message.reply_text("❌ Ошибка.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def broadcast_hw_to_subscribers(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    user_ids = await asyncio.to_thread(db.get_user_ids_with_notify, "homework")
    if not user_ids:
        await query.answer("Нет подписанных.", show_alert=True)
        return
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.answer("Нет ДЗ.", show_alert=True)
        return
    last_task = tasks[-1]
    _, task_text, due_date, _ = last_task
    due_str = f"\n(срок: {due_date})" if due_date else ""
    msg = f"  <b>Обновлено ДЗ</b>\n\n{task_text}{due_str}"
    await query.edit_message_text("⏳ Рассылаю...")
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await query.message.reply_text(f"✅ Разослано {sent}. ❌ Не доставлено {failed}.")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="👑 Админ-панель", reply_markup=kb.admin_panel_kb())


async def del_hw_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    tasks = await asyncio.to_thread(db.get_all_tasks_db)
    if not tasks:
        await query.edit_message_text("📭 Нет ДЗ.", reply_markup=kb.admin_panel_kb())
        return
    lines = ["Удалить ДЗ:\n"]
    for idx, (_, task, due_date, _) in enumerate(tasks, start=1):
        due_str = f" ({due_date})" if due_date else ""
        lines.append(f"{idx}️⃣ {task}{due_str}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_hw_kb(tasks))


async def del_hw_pick(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    task_id = int(query.data.split("_")[1])
    context.user_data['pending_hw_id'] = task_id
    await query.edit_message_text("⚠️ Точно удалить?", reply_markup=kb.confirm_kb("delhw", task_id))


async def del_hw_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    task_id = context.user_data.pop('pending_hw_id', None)
    if task_id is not None:
        await asyncio.to_thread(db.delete_task_db, task_id)
    await query.edit_message_text("🗑 Удалено.", reply_markup=kb.admin_panel_kb())


# === ОБЪЯВЛЕНИЯ ===
async def add_ann_start(update, context):
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
        text="📝 Введите текст объявления. После можно прикрепить фото.",
        reply_markup=kb.cancel_button(),
    )
    return ANN_TEXT


async def add_ann_text(update, context):
    context.user_data['ann_text'] = update.message.text.strip()
    await update.message.reply_text(
        f"📝 Текст:\n{context.user_data['ann_text']}\n\nПришлите фото или «Пропустить».",
        reply_markup=kb.ann_skip_photo_kb(),
    )
    return ANN_PHOTO


async def add_ann_photo(update, context):
    caption = (update.message.caption or "").strip() if update.message else ""
    photo_id = None
    if update.message and update.message.photo:
        photo_id = update.message.photo[-1].file_id
    ann_text = caption if caption else context.user_data.get('ann_text', '')
    context.user_data['ann_text'] = ann_text
    context.user_data['ann_photo_id'] = photo_id
    preview_text = ann_text if ann_text else "(без текста)"
    await update.message.reply_text(
        f"📢 Текст:\n{preview_text}\n📎 Фото\n\nРазослать подписанным?",
        reply_markup=kb.announcement_confirm_kb(),
    )
    return ANN_CONFIRM


async def add_ann_skip_photo(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['ann_photo_id'] = None
    text = context.user_data.get('ann_text', '')
    await query.edit_message_text(
        f"📢 Текст:\n{text}\n\nРазослать подписанным?",
        reply_markup=kb.announcement_confirm_kb(),
    )
    return ANN_CONFIRM


async def add_ann_change_photo(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('ann_photo_id', None)
    await query.edit_message_text("Пришлите фото:", reply_markup=kb.cancel_button())
    return ANN_PHOTO


async def _broadcast_to_kind(bot, kind, text):
    user_ids = await asyncio.to_thread(db.get_user_ids_with_notify, kind)
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    return sent, failed


async def add_ann_confirm(update, context):
    query = update.callback_query
    await query.answer()
    text = context.user_data.get('ann_text', '')
    photo_id = context.user_data.get('ann_photo_id')
    author_id = update.effective_user.id
    save_text = text if text else ""
    await asyncio.to_thread(db.add_announcement_db, save_text, author_id, False, photo_id)
    if query.data == "ann_send_yes":
        broadcast_text = f"📢 {save_text}"
        if photo_id:
            broadcast_text += "\n\n📎 Вложение"
        await query.edit_message_text("⏳ Рассылаю...")
        sent, failed = await _broadcast_to_kind(context.bot, "announcements", broadcast_text)
        await query.message.reply_text(f"✅ Разослано {sent}. ❌ Не доставлено {failed}.")
    else:
        await query.edit_message_text("✅ Сохранено.")
    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def del_ann_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    anns = await asyncio.to_thread(db.get_active_announcements)
    if not anns:
        await query.edit_message_text("📭 Нет.", reply_markup=kb.admin_panel_kb())
        return
    lines = ["Удалить:\n"]
    for idx, item in enumerate(anns, start=1):
        ann_id, text, created_at, is_note, photo_id = item
        prefix = "📝 " if is_note else ("📎 " if photo_id else "")
        date_part = created_at.split(" ")[0] if created_at else ""
        short = text[:28] + "..." if len(text) > 28 else text
        lines.append(f"{idx}️⃣ {prefix}{date_part}: {short or '(без текста)'}")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.delete_ann_kb(anns))


async def del_ann_pick(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    ann_id = int(query.data.split("_")[1])
    context.user_data['pending_ann_id'] = ann_id
    await query.edit_message_text("⚠️ Удалить?", reply_markup=kb.confirm_kb("delann", ann_id))


async def del_ann_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    ann_id = context.user_data.pop('pending_ann_id', None)
    if ann_id is not None:
        await asyncio.to_thread(db.deactivate_announcement_db, ann_id)
    await query.edit_message_text("🗑 Удалено.", reply_markup=kb.admin_panel_kb())


async def add_replnote_start(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("📝 Текст подписи для раздела «Замены»:", reply_markup=kb.cancel_button())
    return REPLNOTE_TEXT


async def add_replnote_text(update, context):
    text = update.message.text.strip()
    context.user_data['replnote_text'] = text
    await update.message.reply_text(f"📝 Текст:\n{text}\n\nСохранить?", reply_markup=kb.replnote_confirm_kb())
    return REPLNOTE_CONFIRM


async def add_replnote_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "replnote_save_yes":
        text = context.user_data.get('replnote_text', '')
        await asyncio.to_thread(db.add_announcement_db, text, update.effective_user.id, True)
        await query.edit_message_text("✅ Сохранено.")
    else:
        await query.edit_message_text("❌ Отменено.")
    context.user_data.clear()
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


# === АДМИНЫ ===
async def add_admin_start(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("Отправьте числовой Telegram ID:", reply_markup=kb.cancel_button())
    return ADMIN_ID


async def add_admin_id(update, context):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ ID должен быть числом.", reply_markup=kb.cancel_button())
        return ADMIN_ID
    context.user_data['new_admin_id'] = int(text)
    await update.message.reply_text("Введите имя:", reply_markup=kb.cancel_button())
    return ADMIN_NAME


async def add_admin_name(update, context):
    name = update.message.text.strip()
    user_id = context.user_data.get('new_admin_id')
    await asyncio.to_thread(db.add_admin_to_db, user_id, f"id{user_id}", name)
    context.user_data.clear()
    await update.message.reply_text("✅ Готово.")
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def del_admin_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    admins = await asyncio.to_thread(db.get_all_admins)
    buttons = kb.delete_admin_kb(admins, update.effective_user.id, INITIAL_ADMIN_ID)
    if not buttons:
        await query.edit_message_text("Нет.", reply_markup=kb.admin_panel_kb())
        return
    await query.edit_message_text("Удалить админа:", reply_markup=buttons)


async def del_admin_pick(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = int(query.data.split("_")[1])
    if target_id == INITIAL_ADMIN_ID:
        await query.answer("❌ Нельзя.", show_alert=True)
        return
    if target_id == update.effective_user.id:
        await query.answer("❌ Нельзя.", show_alert=True)
        return
    context.user_data['pending_admin_id'] = target_id
    await query.edit_message_text(f"Удалить админа {target_id}?", reply_markup=kb.confirm_kb("deladmin", target_id))


async def del_admin_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = context.user_data.pop('pending_admin_id', None)
    if target_id is not None:
        await asyncio.to_thread(db.remove_admin_by_user_id, target_id)
    await query.edit_message_text("✅ Удалён.", reply_markup=kb.admin_panel_kb())


async def view_admins(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    admins = await asyncio.to_thread(db.get_all_admins)
    if not admins:
        await query.edit_message_text("📭 Пусто.", reply_markup=kb.back_button("a_admins_menu"))
        return
    lines = ["Админы:\n"]
    for idx, (user_id, username, name) in enumerate(admins, start=1):
        lines.append(f"{idx}️⃣ {name} (ID: {user_id})")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button("a_admins_menu"))


# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===
async def users_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("👥 Пользователи:", reply_markup=kb.users_menu_kb())


async def view_users_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    users = await asyncio.to_thread(db.get_all_users_with_username)
    if not users:
        await query.edit_message_text("📭 Нет.", reply_markup=kb.back_button("users_menu"))
        return
    await query.edit_message_text(
        f"👥 Пользователи ({len(users)}):\n\nНажми на юзера для действий.",
        reply_markup=kb.users_paginated_kb(users, page=0)
    )


async def users_paginated(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    page = int(query.data.split("_")[1])
    users = await asyncio.to_thread(db.get_all_users_with_username)
    await query.edit_message_text(
        f"👥 Пользователи (стр. {page + 1}):",
        reply_markup=kb.users_paginated_kb(users, page=page)
    )


async def user_action_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = int(query.data.split("_")[1])
    users = await asyncio.to_thread(db.get_all_users_with_username)
    target = next((u for u in users if u[0] == target_id), None)
    if not target:
        await query.answer("❌ Не найден.", show_alert=True)
        return
    is_admin_user = await asyncio.to_thread(db.is_admin, target_id)
    name = target[2] or target[1] or "Без имени"
    text = (
        f"👤 <b>{name}</b>\n"
        f"Telegram: @{target[1] or '—'}\n"
        f"ID: {target_id}\n"
        f"Админ: {'✅' if is_admin_user else '❌'}\n"
        f"Регистрация: {target[3].split(' ')[0] if target[3] else '—'}"
    )
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.user_action_kb(target_id, is_admin_user))


async def user_toggle_admin(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = int(query.data.split("_")[1])
    if target_id == INITIAL_ADMIN_ID:
        await query.answer("❌ Нельзя создателя.", show_alert=True)
        return
    if target_id == update.effective_user.id:
        await query.answer("❌ Нельзя себя.", show_alert=True)
        return
    is_admin_user = await asyncio.to_thread(db.is_admin, target_id)
    if is_admin_user:
        await asyncio.to_thread(db.remove_admin_by_user_id, target_id)
        await query.answer("✅ Снят с админа.", show_alert=True)
    else:
        users = await asyncio.to_thread(db.get_all_users_with_username)
        target = next((u for u in users if u[0] == target_id), None)
        name = (target[2] or target[1] or "Пользователь") if target else "Пользователь"
        await asyncio.to_thread(db.add_admin_to_db, target_id, f"id{target_id}", name)
        await query.answer("✅ Назначен админом.", show_alert=True)
    users = await asyncio.to_thread(db.get_all_users_with_username)
    target = next((u for u in users if u[0] == target_id), None)
    if not target:
        return
    is_admin_user = await asyncio.to_thread(db.is_admin, target_id)
    name = target[2] or target[1] or "Без имени"
    text = (
        f"👤 <b>{name}</b>\n"
        f"Telegram: @{target[1] or '—'}\n"
        f"ID: {target_id}\n"
        f"Админ: {'✅' if is_admin_user else '❌'}\n"
        f"Регистрация: {target[3].split(' ')[0] if target[3] else '—'}"
    )
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb.user_action_kb(target_id, is_admin_user))


async def user_delete(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    target_id = int(query.data.split("_")[1])
    if target_id == update.effective_user.id:
        await query.answer("❌ Нельзя себя.", show_alert=True)
        return
    if target_id == INITIAL_ADMIN_ID:
        await query.answer("❌ Нельзя создателя.", show_alert=True)
        return
    try:
        with db.get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM users WHERE id = %s;", (target_id,))
    except Exception:
        logger.exception("delete user failed")
        await query.answer("❌ Ошибка.", show_alert=True)
        return
    await query.answer("✅ Удалён.", show_alert=True)
    users = await asyncio.to_thread(db.get_all_users_with_username)
    await query.edit_message_text(
        f"👥 Пользователи ({len(users)}):",
        reply_markup=kb.users_paginated_kb(users, page=0)
    )


# === ДОП. ЗАНЯТИЯ ===
async def extra_add_start(update, context):
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
        text="📝 Название предмета:",
        reply_markup=kb.cancel_button(),
    )
    return EXTRA_NAME


async def extra_add_name(update, context):
    context.user_data['extra_subject'] = update.message.text.strip()
    await update.message.reply_text(
        "Пришлите фото или «Пропустить фото».",
        reply_markup=kb.extra_skip_photo_kb(),
    )
    return EXTRA_CONTENT


async def extra_add_content_photo(update, context):
    subject = context.user_data.get('extra_subject', '')
    description = (update.message.caption or "").strip() if update.message else ""
    photo_id = None
    if update.message and update.message.photo:
        photo_id = update.message.photo[-1].file_id
    await asyncio.to_thread(db.add_extra_class, subject, description or None, photo_id)
    context.user_data.clear()
    await update.message.reply_text("✅ Добавлено.")
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def extra_add_content_text(update, context):
    await update.message.reply_text(
        "Пришлите фото или «Пропустить фото».",
        reply_markup=kb.extra_skip_photo_kb(),
    )
    return EXTRA_CONTENT


async def extra_add_skip_photo(update, context):
    query = update.callback_query
    await query.answer()
    subject = context.user_data.get('extra_subject', '')
    await asyncio.to_thread(db.add_extra_class, subject, None, None)
    context.user_data.clear()
    await query.message.reply_text("✅ Добавлено.")
    await query.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def extra_del_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await query.edit_message_text("📭 Нет.", reply_markup=kb.back_button("a_extra_menu"))
        return
    await query.edit_message_text("Удалить:", reply_markup=kb.extra_delete_kb(items))


async def extra_del_pick(update, context):
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
    await query.edit_message_text(f"Удалить «{rec[1]}»?", reply_markup=kb.confirm_kb("delextra", item_id))


async def extra_del_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    item_id = context.user_data.pop('pending_extra_id', None)
    if item_id is not None:
        await asyncio.to_thread(db.deactivate_extra_class, item_id)
    await query.edit_message_text("🗑 Удалено.", reply_markup=kb.admin_panel_kb())


async def extra_view(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await query.edit_message_text("📭 Нет.", reply_markup=kb.back_button("a_extra_menu"))
        return
    lines = ["Активные:\n"]
    for idx, (item_id, subject, description, photo_id, created_at) in enumerate(items, start=1):
        date_part = created_at.split(" ")[0] if created_at else ""
        marker = "📎" if photo_id else ""
        lines.append(f"{idx}️⃣ {marker}{subject} ({date_part})")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button("a_extra_menu"))


async def broadcast_extra_class(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    items = await asyncio.to_thread(db.get_active_extra_classes)
    if not items:
        await q