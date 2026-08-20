import re
import io
import os
import asyncio
import logging
from datetime import datetime, timedelta
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


def _pick_display_name(user_tuple):
    if len(user_tuple) >= 4 and user_tuple[3]:
        return user_tuple[3]
    if len(user_tuple) >= 3 and user_tuple[2]:
        return user_tuple[2]
    if len(user_tuple) >= 2 and user_tuple[1]:
        return user_tuple[1]
    return "Без имени"


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
    await query.edit_message_text("👑 Админы:", reply_markup=kb.admins_menu_kb())


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
    msg = f"📚<b>Обновлено ДЗ</b>\n\n{task_text}{due_str}"
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
        await query.edit_message_text("   Нет.", reply_markup=kb.admin_panel_kb())
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
        await query.edit_message_text("📭 Пусто.", reply_markup=kb.back_button("users_menu"))
        return
    lines = ["Админы:\n"]
    for idx, (user_id, username, name) in enumerate(admins, start=1):
        lines.append(f"{idx}️⃣ {name} (ID: {user_id})")
    await query.edit_message_text("\n".join(lines), reply_markup=kb.back_button("users_menu"))


async def users_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    context.user_data['viewing_admins'] = False
    await query.edit_message_text("👥 Пользователи:", reply_markup=kb.users_menu_kb())


async def view_users_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    context.user_data['viewing_admins'] = False
    users = await asyncio.to_thread(db.get_all_users_with_username)
    if not users:
        await query.edit_message_text("📭 Нет.", reply_markup=kb.back_button("users_menu"))
        return
    await query.edit_message_text(
        f"👤 Пользователи ({len(users)}):\n\nНажми на юзера для действий.",
        reply_markup=kb.users_paginated_kb(users, page=0)
    )


async def view_admins_list(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    context.user_data['viewing_admins'] = True
    admins = await asyncio.to_thread(db.get_all_admins)
    if not admins:
        await query.edit_message_text("📭 Нет админов.", reply_markup=kb.back_button("users_menu"))
        return
    admin_rows = [(a[0], a[1], None, a[2], "") for a in admins]
    await query.edit_message_text(
        f"👑 Админы ({len(admins)}):\n\nНажми на админа для действий.",
        reply_markup=kb.admins_only_paginated_kb(admin_rows, page=0)
    )


async def users_paginated(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    page = int(query.data.split("_")[1])
    if context.user_data.get('viewing_admins'):
        admins = await asyncio.to_thread(db.get_all_admins)
        admin_rows = [(a[0], a[1], None, a[2], "") for a in admins]
        await query.edit_message_text(
            f"👑 Админы (стр. {page + 1}):",
            reply_markup=kb.admins_only_paginated_kb(admin_rows, page=page)
        )
    else:
        users = await asyncio.to_thread(db.get_all_users_with_username)
        await query.edit_message_text(
            f"👤 Пользователи (стр. {page + 1}):",
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
    name = _pick_display_name(target)
    text = (
        f"{'👑' if is_admin_user else '👤'} <b>{name}</b>\n"
        f"Telegram: @{target[1] or '—'}\n"
        f"ID: {target_id}\n"
        f"Админ: {'✅' if is_admin_user else '❌'}\n"
        f"Регистрация: {target[4].split(' ')[0] if target[4] else '—'}"
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
        name = _pick_display_name(target) if target else "Пользователь"
        await asyncio.to_thread(db.add_admin_to_db, target_id, f"id{target_id}", name)
        await query.answer("✅ Назначен админом.", show_alert=True)
    users = await asyncio.to_thread(db.get_all_users_with_username)
    target = next((u for u in users if u[0] == target_id), None)
    if not target:
        return
    is_admin_user = await asyncio.to_thread(db.is_admin, target_id)
    name = _pick_display_name(target)
    text = (
        f"{'👑' if is_admin_user else '👤'} <b>{name}</b>\n"
        f"Telegram: @{target[1] or '—'}\n"
        f"ID: {target_id}\n"
        f"Админ: {'✅' if is_admin_user else '❌'}\n"
        f"Регистрация: {target[4].split(' ')[0] if target[4] else '—'}"
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
        f"👤 Пользователи ({len(users)}):",
        reply_markup=kb.users_paginated_kb(users, page=0)
    )


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
        await query.answer("Нет.", show_alert=True)
        return
    last = items[0]
    item_id, subject, description, photo_id, _ = last
    user_ids = await asyncio.to_thread(db.get_user_ids_with_notify, "extra_classes")
    if not user_ids:
        await query.answer("Нет подписанных.", show_alert=True)
        return
    await query.edit_message_text("⏳ Рассылаю...")
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            if photo_id:
                await context.bot.send_photo(chat_id=uid, photo=photo_id, caption=f"📚 Новое: <b>{subject}</b>", parse_mode='HTML')
            else:
                body = f"   Новое: <b>{subject}</b>"
                if description:
                    body += f"\n\n{description}"
                await context.bot.send_message(chat_id=uid, text=body, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await query.message.reply_text(f"✅ Разослано {sent}. ❌ Не доставлено {failed}.")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="👑 Админ-панель", reply_markup=kb.admin_panel_kb())


async def set_group_start(update, context):
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
        text=f"Сейчас: <b>{current}</b>\n\nВведите новое:",
        parse_mode='HTML',
        reply_markup=kb.cancel_button(),
    )
    return SET_GROUP


async def set_group_finish(update, context):
    name = update.message.text.strip()
    loading = await update.message.reply_text("⏳ Сохраняю...")
    await asyncio.to_thread(db.set_group_name, name)
    try:
        await loading.delete()
    except Exception:
        pass
    await update.message.reply_text(f"✅ «{name}».")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def set_bot_name_start(update, context):
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
        text=f"Сейчас: <b>{current}</b>\n\nВведите новое:",
        parse_mode='HTML',
        reply_markup=kb.cancel_button(),
    )
    return SET_BOT_NAME


async def set_bot_name_finish(update, context):
    name = update.message.text.strip()
    loading = await update.message.reply_text("⏳ Сохраняю...")
    await asyncio.to_thread(db.set_bot_display_name, name)
    try:
        await context.bot.set_my_name(name=name)
    except Exception:
        pass
    try:
        await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    except Exception:
        pass
    try:
        await loading.delete()
    except Exception:
        pass
    await update.message.reply_text("✅ Готово.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def set_bot_photo_start(update, context):
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
        text="⚠️ Смена аватарки через API невозможна. Используйте @BotFather → /setuserpic.",
        reply_markup=kb.cancel_button(),
    )
    return SET_BOT_PHOTO


async def set_bot_photo_finish(update, context):
    await update.message.reply_text("⚠️ Сделайте вручную.")
    context.user_data.clear()
    await update.message.reply_text("👑 Админ-панель", reply_markup=kb.admin_panel_kb())
    return ConversationHandler.END


async def edit_schedule_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⚙️ Расписание:", reply_markup=kb.schedule_edit_menu_kb())


async def force_broadcast_replacements_btn(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("⏳ Рассылаю...")
    try:
        sent = await sched.force_broadcast_replacements()
        if sent < 0:
            await query.edit_message_text("❌ Ошибка.", reply_markup=kb.schedule_edit_menu_kb())
        else:
            await query.edit_message_text(f"✅ Разослано {sent}.", reply_markup=kb.schedule_edit_menu_kb())
    except Exception:
        await query.edit_message_text("❌ Ошибка.", reply_markup=kb.schedule_edit_menu_kb())


async def sched_upload_start(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return ConversationHandler.END
    await query.edit_message_text("📤 Заполните и пришлите обратно:", reply_markup=kb.cancel_button())
    template_path = os.path.join(os.path.dirname(__file__), "assets", "schedule_template.xlsx")
    try:
        with open(template_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id, document=f,
                filename="Формат_Расписания.xlsx",
                caption="Числитель слева, Знаменатель справа.",
            )
    except FileNotFoundError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Шаблон не найден.")
    return SCHED_UPLOAD_TEXT


def _parse_schedule_xlsx(file_bytes):
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
            errors.append(f"Строка {row_idx}")
            continue
        subj_num, teach_num, room_num = cells[1], cells[2], cells[3]
        subj_den, teach_den, room_den = cells[4], cells[5], cells[6]
        if subj_num:
            result.setdefault(("Числитель", current_day), []).append({
                "pair_number": pair_num, "subject": str(subj_num).strip(),
                "teacher": str(teach_num).strip() if teach_num else "",
                "room": str(room_num).strip() if room_num else "",
            })
        if subj_den:
            result.setdefault(("Знаменатель", current_day), []).append({
                "pair_number": pair_num, "subject": str(subj_den).strip(),
                "teacher": str(teach_den).strip() if teach_den else "",
                "room": str(room_den).strip() if room_den else "",
            })
    return result, errors


async def sched_upload_document(update, context):
    document = update.message.document
    if not document or not document.file_name.lower().endswith(".xlsx"):
        await update.message.reply_text("❌ Нужен .xlsx", reply_markup=kb.cancel_button())
        return SCHED_UPLOAD_TEXT
    tg_file = await document.get_file()
    file_bytes = bytes(await tg_file.download_as_bytearray())
    try:
        parsed, errors = await asyncio.to_thread(_parse_schedule_xlsx, file_bytes)
    except Exception:
        await update.message.reply_text("❌ Ошибка чтения.", reply_markup=kb.cancel_button())
        return SCHED_UPLOAD_TEXT
    if not parsed:
        await update.message.reply_text("❌ Нет данных.", reply_markup=kb.cancel_button())
        return SCHED_UPLOAD_TEXT
    context.user_data['pending_schedule'] = parsed
    await update.message.reply_text(
        f"Найдено дней: {len(parsed)}. Применить?",
        reply_markup=kb.confirm_kb("schedupload", "0")
    )
    return ConversationHandler.END


async def sched_upload_confirm(update, context):
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
    loading = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Загружаю...")
    try:
        for (week_type, day_idx), entries in parsed.items():
            await asyncio.to_thread(db.replace_day_schedule, week_type, day_idx, entries)
        await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    except Exception:
        try:
            await loading.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Ошибка.", reply_markup=kb.bot_settings_kb())
        return
    try:
        await loading.delete()
    except Exception:
        pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Обновлено.", reply_markup=kb.bot_settings_kb())


async def del_all_day_menu(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("Удалить ВСЕ пары на день:", reply_markup=kb.delete_all_day_kb())


async def sched_by_day_start(update, context):
    query = update.callback_query
    await query.answer()
    if not await _require_admin(update):
        return
    await query.edit_message_text("День:", reply_markup=kb.weekday_choice_kb())


async def sched_day_chosen(update, context):
    query = update.callback_query
    await query.answer()
    day_idx = int(query.data.split("_")[1])
    await query.edit_message_text(
        f"{WEEKDAYS_RU[day_idx].capitalize()}. Тип недели:", reply_markup=kb.week_type_kb(day_idx)
    )


async def sched_delete_all_day(update, context):
    query = update.callback_query
    await query.answer()
    day_idx = int(query.data.split("_")[1])
    await asyncio.to_thread(db.delete_all_pairs_for_day, day_idx)
    await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    await query.edit_message_text(f"🗑 Удалено.", reply_markup=kb.bot_settings_kb())


async def sched_week_type_chosen(update, context):
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


async def sched_pair_chosen(update, context):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx, pair_num = query.data.split("_")
    await query.edit_message_text(
        f"Пара {pair_num} ({week_type}, {WEEKDAYS_RU[int(day_idx)]}):",
        reply_markup=kb.pair_field_kb(week_type, int(day_idx), int(pair_num)),
    )


async def sched_new_pair(update, context):
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
    await query.edit_message_text(f"Предмет для пары {next_pair}:", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_delete_pair(update, context):
    query = update.callback_query
    await query.answer()
    _, week_type, day_idx, pair_num = query.data.split("_")
    await asyncio.to_thread(db.delete_pair, week_type, int(day_idx), int(pair_num))
    await asyncio.to_thread(sched_img.regenerate_all_cached_images)
    await query.answer("Удалено", show_alert=True)
    pairs = await asyncio.to_thread(db.get_base_schedule, week_type, int(day_idx))
    lines = [f"{week_type}, {WEEKDAYS_RU[int(day_idx)]}:\n"]
    for num, info in sorted(pairs.items()):
        lines.append(f"{num}. {info['subject']} ({info['teacher']}) — {info['room']}")
    await query.edit_message_text("\n".join(lines) or "Пар пока нет.",
                                  reply_markup=kb.pair_choice_kb(pairs, week_type, int(day_idx)))


async def sched_field_chosen(update, context):
    query = update.callback_query
    await query.answer()
    _, field, week_type, day_idx, pair_num = query.data.split("_")
    context.user_data['sched_edit'] = {
        "week_type": week_type, "day_idx": int(day_idx), "pair_num": int(pair_num), "field": field,
    }
    field_names = {"subject": "предмет", "teacher": "преподавателя", "room": "аудиторию"}
    await query.edit_message_text(f"Введите ({field_names[field]}):", reply_markup=kb.cancel_button())
    return SCHED_FIELD_VALUE


async def sched_field_value(update, context):
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
            await update.message.reply_text("Преподаватель:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE

    if edit.get('is_new'):
        if edit['field'] == 'teacher':
            edit['teacher'] = value
            edit['field'] = 'room'
            context.user_data['sched_edit'] = edit
            await update.message.reply_text("Аудитория:", reply_markup=kb.cancel_button())
            return SCHED_FIELD_VALUE
        elif edit['field'] == 'room':
            edit['room'] = value
            await asyncio.to_thread(
                db.upsert_pair, week_type, day_idx, pair_num, edit['subject'], edit['teacher'], edit['room']
            )
            await asyncio.to_thread(sched_img.regenerate_all_cached_images)
            await update.message.reply_text(f"✅ Добавлено.")
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