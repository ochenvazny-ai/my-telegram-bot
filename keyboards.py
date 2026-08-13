from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import WEEKDAYS_RU


def main_menu_kb(is_admin_user: bool):
    kb = [
        [InlineKeyboardButton("📅 Замены", callback_data="menu_zam")],
        [InlineKeyboardButton("📚 Домашка", callback_data="menu_hw")],
        [InlineKeyboardButton("📢 Объявления", callback_data="menu_ann")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="menu_extra")],
        [InlineKeyboardButton("ℹ️ Учебная инфа", callback_data="menu_info")],
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


# ---------- ИНФО ----------
def info_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Расписание звонков", callback_data="info_bells")],
        [InlineKeyboardButton("📚 Расписание пар", callback_data="info_sched_img")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ])


def bells_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Обычные дни", callback_data="bells_regular")],
        [InlineKeyboardButton("Предпраздничные дни", callback_data="bells_preholiday")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_info")],
    ])


def bells_building_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("По А корпусу", callback_data="bells_regular_a")],
        [InlineKeyboardButton("По Б корпусу", callback_data="bells_regular_b")],
        [InlineKeyboardButton("🔙 Назад", callback_data="info_bells")],
    ])


def schedule_img_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Числитель", callback_data="schedimg_num")],
        [InlineKeyboardButton("Знаменатель", callback_data="schedimg_den")],
        [InlineKeyboardButton("Оба (Сравнение)", callback_data="schedimg_cmp")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_info")],
    ])


# ---------- ДОП. ЗАНЯТИЯ (пользователь) ----------
def extra_classes_list_kb(items):
    buttons = []
    for idx, item in enumerate(items, start=1):
        item_id, subject = item[0], item[1]
        short = subject[:30] + "..." if len(subject) > 30 else subject
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"open_extra_{item_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def extra_skip_photo_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить фото", callback_data="extra_skip_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")],
    ])


# ---------- АДМИН-ПАНЕЛЬ ----------
def admin_panel_kb():
    kb = [
        [InlineKeyboardButton("📚 Домашнее задание", callback_data="a_hw_menu")],
        [InlineKeyboardButton("📢 Объявления", callback_data="a_ann_menu")],
        [InlineKeyboardButton("📅 Праздничный день", callback_data="a_ph_menu")],
        [InlineKeyboardButton("⚙️ Настроить Расписание", callback_data="a_sched_menu")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="a_extra_menu")],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data="a_bot_settings")],
        [InlineKeyboardButton("👥 Админы", callback_data="a_admins_menu")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(kb)


def shift_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 смена", callback_data="shiftset_1")],
        [InlineKeyboardButton("2 смена", callback_data="shiftset_2")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_bot_settings")],
    ])


def hw_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить ДЗ", callback_data="a_add_hw")],
        [InlineKeyboardButton("❌ Удалить ДЗ", callback_data="a_del_hw")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def ann_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Создать объявление", callback_data="a_add_ann")],
        [InlineKeyboardButton("➖ Удалить объявление", callback_data="a_del_ann")],
        [InlineKeyboardButton("📝 Подпись к замене", callback_data="a_add_replnote")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def ph_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Назначить предпраздничный день", callback_data="a_set_ph")],
        [InlineKeyboardButton("❌ Отменить предпраздничный день", callback_data="a_unset_ph")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def ph_set_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Завтра", callback_data="phset_tomorrow")],
        [InlineKeyboardButton("Послезавтра", callback_data="phset_daftertomorrow")],
        [InlineKeyboardButton("Назначить дату", callback_data="phset_manual")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")],
    ])


def admins_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить админа", callback_data="a_add_admin")],
        [InlineKeyboardButton("➖ Удалить админа", callback_data="a_del_admin")],
        [InlineKeyboardButton("👀 Посмотреть Админов", callback_data="a_view_admins")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def announcement_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, отправить", callback_data="ann_send_yes")],
        [InlineKeyboardButton("❌ Нет, только сохранить", callback_data="ann_send_no")],
    ])


def replnote_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, сохранить", callback_data="replnote_save_yes")],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data="replnote_save_no")],
    ])


# ---------- ДОП. ЗАНЯТИЯ (админ) ----------
def extra_admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить занятие", callback_data="a_add_extra")],
        [InlineKeyboardButton("❌ Удалить занятие", callback_data="a_del_extra")],
        [InlineKeyboardButton("👀 Посмотреть занятия", callback_data="a_view_extra")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def extra_delete_kb(items):
    buttons = []
    for idx, item in enumerate(items, start=1):
        item_id, subject = item[0], item[1]
        short = subject[:30] + "..." if len(subject) > 30 else subject
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"delextra_{item_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_extra_menu")])
    return InlineKeyboardMarkup(buttons)


# ---------- НАСТРОЙКИ БОТА ----------
def bot_settings_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Изменить смену", callback_data="a_shift")],
        [InlineKeyboardButton("📝 Изменить группу", callback_data="a_set_group")],
        [InlineKeyboardButton("✏️ Изменить название бота", callback_data="a_set_botname")],
        [InlineKeyboardButton("🖼️ Изменить картинку бота", callback_data="a_set_botphoto")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


# ---------- СПИСКИ ДЛЯ УДАЛЕНИЯ ----------
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
    for idx, item in enumerate(anns, start=1):
        ann_id, text = item[0], item[1]
        is_note = item[3] if len(item) > 3 else False
        prefix = "📝 " if is_note else ""
        short = text[:28] + "..." if len(text) > 28 else text
        buttons.append([InlineKeyboardButton(f"{idx}. {prefix}{short}", callback_data=f"delann_{ann_id}")])
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


# ---------- РЕДАКТОР РАСПИСАНИЯ ----------
def schedule_edit_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Загрузить из Excel", callback_data="sched_upload")],
        [InlineKeyboardButton("📝 Редактировать по дням", callback_data="sched_by_day")],
        [InlineKeyboardButton("🗑 Удалить все пары на день", callback_data="a_del_all_day")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")],
    ])


def delete_all_day_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"delallday_{i}")]
               for i in range(6)]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def weekday_choice_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"schedday_{i}")]
               for i in range(6)]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def week_type_kb(day_index: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Числитель", callback_data=f"weektype_Числитель_{day_index}")],
        [InlineKeyboardButton("Знаменатель", callback_data=f"weektype_Знаменатель_{day_index}")],
        [InlineKeyboardButton("🗑 Удалить все пары на день", callback_data=f"delallday_{day_index}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")],
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