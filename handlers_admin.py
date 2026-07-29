import re
import io
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)
import database as db
import keyboards as kb
from config import (
    INITIAL_ADMIN_ID, WEEKDAYS_RU,
    HW_TEXT, HW_DUE, ANN_TEXT, ANN_CONFIRM, PH_DATE,
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
    for idx, (_id, task, due_date, _) in enumerate(tasks, start=1):
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
        for idx, (_id, task, due_date, _) in enumerate(tasks, start=1):
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

RATE_LIMIT_DELAY = 0.05
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

# ============ УДАЛЕНИЕ ОБЪЯВЛЕНИЯ ============
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
    for idx, (_id, text
