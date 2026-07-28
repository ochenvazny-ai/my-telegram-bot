from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import WEEKDAYS_RU


def main_menu_kb(is_admin_user: bool):
    kb = [
        [InlineKeyboardButton("📅 Замены", callback_data="menu_zam")],
        [InlineKeyboardButton("📚 Домашка", callback_data="menu_hw")],
        [InlineKeyboardButton("📢 Объявления", callback_data="menu_ann")],
        [InlineKeyboardButton("📞 Расписание звонков", callback_data="menu_bells")],
        [InlineKeyboardButton("ℹ️ Инфо", callback_data="menu_info")],
    ]
    if is_admin_user:
        kb.append([InlineKeyboardButton("👑 Админка", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


def reply_menu_button():
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Меню")]], resize_keyboard=True)


def back_button(callback_data="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]])


def cancel_button(callback_data="cancel_action"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=callback_data)]])


def confirm_kb(action: str, item_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{item_id}")],
        [InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}")],
    ])


def admin_panel_kb():
    kb = [
        [InlineKeyboardButton("➕ Добавить ДЗ", callback_data="a_add_hw")],
        [InlineKeyboardButton("❌ Удалить ДЗ", callback_data="a_del_hw")],
        [InlineKeyboardButton("📢 Создать объявление", callback_data="a_add_ann")],
        [InlineKeyboardButton("➖ Удалить объявление", callback_data="a_del_ann")],
        [InlineKeyboardButton("📅 Назначить предпраздничный день", callback_data="a_set_ph")],
        [InlineKeyboardButton("❌ Отменить предпраздничный день", callback_data="a_unset_ph")],
        [InlineKeyboardButton("✏️ Изменить расписание", callback_data="a_edit_sched")],
        [InlineKeyboardButton("➕ Добавить админа", callback_data="a_add_admin")],
        [InlineKeyboardButton("➖ Удалить админа", callback_data="a_del_admin")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(kb)


def delete_hw_kb(tasks):
    if not tasks:
        return None
    buttons = []
    for idx, (db_id, task, due_date, _) in enumerate(tasks, start=1):
        short = task[:30] + "..." if len(task) > 30 else task
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"delhw_{db_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def delete_ann_kb(anns):
    if not anns:
        return None
    buttons = []
    for idx, (ann_id, text, created_at) in enumerate(anns, start=1):
        short = text[:30] + "..." if len(text) > 30 else text
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"delann_{ann_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def delete_admin_kb(admins, current_user_id, initial_admin_id):
    buttons = []
    for user_id, username, name in admins:
        if user_id == initial_admin_id or user_id == current_user_id:
            continue
        buttons.append([InlineKeyboardButton(f"{name} (ID {user_id})", callback_data=f"deladmin_{user_id}")])
    if not buttons:
        return None
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def pre_holiday_list_kb(items, action_prefix):
    if not items:
        return None
    buttons = [[InlineKeyboardButton(date, callback_data=f"{action_prefix}_{ph_id}")] for ph_id, date in items]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def announcement_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, отправить", callback_data="ann_send_yes")],
        [InlineKeyboardButton("❌ Нет, только сохранить", callback_data="ann_send_no")],
    ])


def weekday_choice_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"schedday_{i}")]
               for i in range(6)]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def schedule_edit_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Загрузить новое расписание", callback_data="sched_upload")],
        [InlineKeyboardButton("📝 Редактировать по дням", callback_data="sched_by_day")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")],
    ])


def week_type_kb(day_index: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Числитель", callback_data=f"weektype_Числитель_{day_index}")],
        [InlineKeyboardButton("Знаменатель", callback_data=f"weektype_Знаменатель_{day_index}")],
        [InlineKeyboardButton("🗑 Удалить все пары на день", callback_data=f"delallday_{day_index}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_edit_sched")],
    ])


def pair_choice_kb(pairs: dict, week_type: str, day_index: int):
    buttons = []
    for pair_num in sorted(pairs.keys()):
        info = pairs[pair_num]
        buttons.append([InlineKeyboardButton(
            f"{pair_num}. {info['subject']}", callback_data=f"editpair_{week_type}_{day_index}_{pair_num}")])
    buttons.append([InlineKeyboardButton("➕ Добавить пару", callback_data=f"newpair_{week_type}_{day_index}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"schedday_{day_index}")])
    return InlineKeyboardMarkup(buttons)


def pair_field_kb(week_type: str, day_index: int, pair_num: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Предмет", callback_data=f"field_subject_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("Преподаватель", callback_data=f"field_teacher_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("Аудитория", callback_data=f"field_room_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("🗑 Удалить пару", callback_data=f"delpair_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"weektype_{week_type}_{day_index}")],
    ])
