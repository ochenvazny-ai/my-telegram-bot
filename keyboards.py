from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import WEEKDAYS_RU


def main_menu_kb(is_admin_user):
    kb = [
        [InlineKeyboardButton("📅 Замены", callback_data="menu_zam")],
        [InlineKeyboardButton("📚 Домашка", callback_data="menu_hw")],
        [InlineKeyboardButton("📢 Объявления", callback_data="menu_ann")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="menu_extra")],
        [InlineKeyboardButton("ℹ️ Учебная инфа", callback_data="menu_info")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="cabinet")],
    ]
    if is_admin_user:
        kb.append([InlineKeyboardButton("👑 Админка", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


def reply_menu_button():
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Меню")]], resize_keyboard=True)


def back_button(callback_data="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("   Назад", callback_data=callback_data)]])


def cancel_button(callback_data="cancel_action"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=callback_data)]])


def confirm_kb(action, item_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{item_id}")],
        [InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}")],
    ])


def cabinet_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Замены", callback_data="toggle_replacements")],
        [InlineKeyboardButton("📢 Объявления", callback_data="toggle_announcements")],
        [InlineKeyboardButton("📚 Домашка", callback_data="toggle_homework")],
        [InlineKeyboardButton("📖 Доп. занятия", callback_data="toggle_extra_classes")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ])


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


def schedule_img_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Числитель", callback_data="schedimg_num")],
        [InlineKeyboardButton("Знаменатель", callback_data="schedimg_den")],
        [InlineKeyboardButton("Оба", callback_data="schedimg_cmp")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_info")],
    ])


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


def ann_skip_photo_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить", callback_data="ann_skip_photo")],
        [InlineKeyboardButton("🖼 Поменять", callback_data="ann_change_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")],
    ])


def admin_panel_kb():
    kb = [
        [InlineKeyboardButton("📚 Домашнее задание", callback_data="a_hw_menu")],
        [InlineKeyboardButton("📢 Объявления", callback_data="a_ann_menu")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="a_extra_menu")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_menu")],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data="a_bot_settings")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(kb)


def users_menu_kb(show_banned=False):
    """Если есть забаненные — показываем третий пункт."""
    buttons = [
        [InlineKeyboardButton("👤 Пользователи", callback_data="users_view")],
        [InlineKeyboardButton("👑 Админы", callback_data="admins_view")],
    ]
    if show_banned:
        buttons.append([InlineKeyboardButton("🚫 Забаненные", callback_data="banned_view")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


def admins_only_paginated_kb(admins, page):
    buttons = []
    for u in admins[page*30:(page+1)*30]:
        user_id, _username, _first_name, display_name, _created = u
        name = display_name or _first_name or _username or "Без имени"
        short = name[:25] + "..." if len(name) > 25 else name
        buttons.append([InlineKeyboardButton(f"👑 {short} (ID:{user_id})", callback_data=f"useraction_{user_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"userspage_{page - 1}"))
    if (page + 1) * 30 < len(admins):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"userspage_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="users_menu")])
    return InlineKeyboardMarkup(buttons)


def users_paginated_kb(users, page):
    buttons = []
    for u in users[page*30:(page+1)*30]:
        user_id, _username, _first_name, display_name, _created = u
        name = display_name or _first_name or _username or "Без имени"
        short = name[:25] + "..." if len(name) > 25 else name
        buttons.append([InlineKeyboardButton(f"{short} (ID:{user_id})", callback_data=f"useraction_{user_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"userspage_{page - 1}"))
    if (page + 1) * 30 < len(users):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"userspage_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="users_menu")])
    return InlineKeyboardMarkup(buttons)


def banned_paginated_kb(rows, page):
    """Список забаненных. rows: (id, username, first_name, display_name)."""
    buttons = []
    for r in rows[page*30:(page+1)*30]:
        user_id, _u, _f, display_name = r
        name = display_name or _u or _f or "Без имени"
        short = name[:25] + "..." if len(name) > 25 else name
        buttons.append([InlineKeyboardButton(f"   {short} (ID:{user_id})", callback_data=f"unbanuser_{user_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"userspage_{page - 1}"))
    if (page + 1) * 30 < len(rows):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"userspage_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="users_menu")])
    return InlineKeyboardMarkup(buttons)


def user_action_kb(user_id, is_admin_user):
    admin_label = "❌ Снять с админа" if is_admin_user else "✅ Сделать админом"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(admin_label, callback_data=f"toggleadmin_{user_id}")],
        [InlineKeyboardButton("🚫 Забанить", callback_data=f"banuser_{user_id}")],
        [InlineKeyboardButton("🔙 К списку", callback_data="users_view")],
    ])


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
        [InlineKeyboardButton("📣 Разослать подписанным", callback_data="broadcast_hw")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def ann_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Создать объявление", callback_data="a_add_ann")],
        [InlineKeyboardButton("➖ Удалить", callback_data="a_del_ann")],
        [InlineKeyboardButton("📝 Подпись к замене", callback_data="a_add_replnote")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def admins_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="a_add_admin")],
        [InlineKeyboardButton("➖ Удалить", callback_data="a_del_admin")],
        [InlineKeyboardButton("👀 Посмотреть", callback_data="a_view_admins")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def announcement_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Разослать", callback_data="ann_send_yes")],
        [InlineKeyboardButton("❌ Сохранить", callback_data="ann_send_no")],
    ])


def replnote_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data="replnote_save_yes")],
        [InlineKeyboardButton("❌ Нет", callback_data="replnote_save_no")],
    ])


def extra_admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="a_add_extra")],
        [InlineKeyboardButton("❌ Удалить", callback_data="a_del_extra")],
        [InlineKeyboardButton("👀 Посмотреть", callback_data="a_view_extra")],
        [InlineKeyboardButton("📣 Разослать", callback_data="broadcast_extra")],
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


def bot_settings_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Смена", callback_data="a_shift")],
        [InlineKeyboardButton("⚙️ Расписание", callback_data="a_sched_menu")],
        [InlineKeyboardButton("   Группа", callback_data="a_set_group")],
        [InlineKeyboardButton("✏️ Название бота", callback_data="a_set_botname")],
        [InlineKeyboardButton("🖼 Картинка бота", callback_data="a_set_botphoto")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def delete_hw_kb(tasks):
    buttons = []
    for idx, (db_id, task, due_date, _) in enumerate(tasks, start=1):
        short = task[:30] + "..." if len(task) > 30 else task
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"delhw_{db_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_hw_menu")])
    return InlineKeyboardMarkup(buttons)


def delete_ann_kb(anns):
    buttons = []
    for idx, item in enumerate(anns, start=1):
        ann_id = item[0]
        is_note = item[3] if len(item) > 3 else False
        has_photo = len(item) > 4 and item[4]
        prefix = "📝 " if is_note else ("📎 " if has_photo else "")
        text = item[1] or "(без текста)"
        short = text[:28] + "..." if len(text) > 28 else text
        buttons.append([InlineKeyboardButton(f"{idx}. {prefix}{short}", callback_data=f"delann_{ann_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_ann_menu")])
    return InlineKeyboardMarkup(buttons)


def delete_admin_kb(admins, current_user_id, initial_admin_id):
    buttons = []
    for user_id, username, name in admins:
        if user_id == initial_admin_id or user_id == current_user_id:
            continue
        buttons.append([InlineKeyboardButton(f"{name} (ID {user_id})", callback_data=f"deladmin_{user_id}")])
    if not buttons:
        return None
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="users_menu")])
    return InlineKeyboardMarkup(buttons)


def schedule_edit_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Загрузить из Excel", callback_data="sched_upload")],
        [InlineKeyboardButton("📝 Редактировать по дням", callback_data="sched_by_day")],
        [InlineKeyboardButton("🗑 Удалить пары на день", callback_data="a_del_all_day")],
        [InlineKeyboardButton("📣 Разослать замены", callback_data="force_repl_broadcast")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_bot_settings")],
    ])


def delete_all_day_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"delallday_{i}") for i in range(6)]]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")])
    return InlineKeyboardMarkup(buttons)


def weekday_choice_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"schedday_{i}") for i in range(6)]]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")])
    return InlineKeyboardMarkup(buttons)


def week_type_kb(day_index):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Числитель", callback_data=f"weektype_Числитель_{day_index}")],
        [InlineKeyboardButton("Знаменатель", callback_data=f"weektype_Знаменатель_{day_index}")],
        [InlineKeyboardButton("🗑 Удалить день", callback_data=f"delallday_{day_index}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")],
    ])


def pair_choice_kb(pairs, week_type, day_index):
    buttons = []
    for pair_num in sorted(pairs.keys()):
        info = pairs[pair_num]
        buttons.append([InlineKeyboardButton(
            f"{pair_num}. {info['subject']}", callback_data=f"editpair_{week_type}_{day_index}_{pair_num}")])
    buttons.append([InlineKeyboardButton("➕ Добавить пару", callback_data=f"newpair_{week_type}_{day_index}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"schedday_{day_index}")])
    return InlineKeyboardMarkup(buttons)


def pair_field_kb(week_type, day_index, pair_num):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Предмет", callback_data=f"field_subject_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("Преподаватель", callback_data=f"field_teacher_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("Аудитория", callback_data=f"field_room_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("🗑 Удалить пару", callback_data=f"delpair_{week_type}_{day_index}_{pair_num}")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"weektype_{week_type}_{day_index}")],
    ])