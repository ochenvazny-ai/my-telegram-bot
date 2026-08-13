from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import WEEKDAYS_RU


def main_menu_kb(is_admin_user: bool):
    kb = [
        [InlineKeyboardButton("📅 Замены", callback_data="menu_zam")],
        [InlineKeyboardButton("📚 Домашка", callback_data="menu_hw")],
        [InlineKeyboardButton("📢 Объявления", callback_data="menu_ann")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="menu_extra")],
        [InlineKeyboardButton("👤 Кабинет", callback_data="cabinet")],
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


def skip_name_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Оставить как в Telegram", callback_data="start_skip_name")]
    ])


# ===== ОНБОРДИНГ/КАБИНЕТ =====
def cabinet_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Изменить имя", callback_data="cabinet_name")],
        [InlineKeyboardButton("💸 Мои долги", callback_data="cabinet_open_debts")],
        [InlineKeyboardButton("📝 Мои заметки", callback_data="cabinet_open_notes")],
        [InlineKeyboardButton("🔔 Уведомления: Замены", callback_data="toggle_replacements")],
        [InlineKeyboardButton("🔔 Уведомления: Объявления", callback_data="toggle_announcements")],
        [InlineKeyboardButton("🔔 Уведомления: Домашка", callback_data="toggle_homework")],
        [InlineKeyboardButton("🔔 Уведомления: Доп. занятия", callback_data="toggle_extra_classes")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ])


def cabinet_notes_kb(kind: str):
    """Список долгов или заметок."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data=f"addnote_{kind}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="cabinet")],
    ])


def cabinet_notes_with_items_kb(kind: str, notes):
    """Список с предметами для клика."""
    buttons = []
    buttons.append([InlineKeyboardButton("➕ Добавить", callback_data=f"addnote_{kind}")])
    for note_id, title, _, is_done, _ in notes:
        mark = "✅" if is_done else "❗"
        short = (title[:25] + "...") if len(title) > 25 else title
        buttons.append([InlineKeyboardButton(f"{mark} {short}", callback_data=f"viewnote_{note_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="cabinet")])
    return InlineKeyboardMarkup(buttons)


def cabinet_note_actions_kb(note_id: int, is_done: bool, back_to: str):
    done_label = "↩️ Вернуть в активные" if is_done else "✅ Выполнено"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(done_label, callback_data=f"donenote_{note_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"delnote_{note_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data=back_to)],
    ])


# ===== ИНФО =====
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
        [InlineKeyboardButton("Оба (Сравнение)", callback_data="schedimg_cmp")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_info")],
    ])


# ===== ДОП. ЗАНЯТИЯ =====
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
        [InlineKeyboardButton("⏭ Пропустить фото", callback_data="ann_skip_photo")],
        [InlineKeyboardButton("🖼 Поменять фото", callback_data="ann_change_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")],
    ])


# ===== АДМИНКА =====
def admin_panel_kb():
    kb = [
        [InlineKeyboardButton("📚 Домашнее задание", callback_data="a_hw_menu")],
        [InlineKeyboardButton("📢 Объявления", callback_data="a_ann_menu")],
        [InlineKeyboardButton("📚 Доп. занятия", callback_data="a_extra_menu")],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data="a_bot_settings")],
        [InlineKeyboardButton("👥 Админы", callback_data="a_admins_menu")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_menu")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(kb)


def users_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Все пользователи", callback_data="users_view")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def users_paginated_kb(users, page: int):
    buttons = []
    # Кнопки пользователей    for u in users[page*30:(page+1)*30]:
        uid = u[0]
        name = u[3] or u[2] or u[1] or "Без имени"
        short = name[:25] + "..." if len(name) > 25 else name
        buttons.append([InlineKeyboardButton(f"{short}", callback_data=f"useraction_{uid}")])
    # Пагинация
    nav = []
    if page >0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"userspage_{page -1}"))
    if (page + 1) * 30 < len(users):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"userspage_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="users_menu")])
    return InlineKeyboardMarkup(buttons)


def user_action_kb(user_id: int, is_admin_user: bool):
    admin_label = "❌ Снять с админа" if is_admin_user else "✅ Сделать админом"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(admin_label, callback_data=f"toggleadmin_{user_id}")],
        [InlineKeyboardButton("🗑 Удалить юзера", callback_data=f"deleteuser_{user_id}")],
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
        [InlineKeyboardButton("📣 Разослать ДЗ подписанным", callback_data="broadcast_hw")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def ann_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Создать объявление", callback_data="a_add_ann")],
        [InlineKeyboardButton("➖ Удалить объявление", callback_data="a_del_ann")],
        [InlineKeyboardButton("📝 Подпись к замене", callback_data="a_add_replnote")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def admins_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить админа", callback_data="a_add_admin")],
        [InlineKeyboardButton("➖ Удалить админа", callback_data="a_del_admin")],
        [InlineKeyboardButton("👀 Посмотреть", callback_data="a_view_admins")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def announcement_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, разослать", callback_data="ann_send_yes")],
        [InlineKeyboardButton("❌ Нет, сохранить", callback_data="ann_send_no")],
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
        [InlineKeyboardButton("📣 Разослать подписанным", callback_data="broadcast_extra")],
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
        [InlineKeyboardButton("🔁 Изменить смену", callback_data="a_shift")],
        [InlineKeyboardButton("⚙️ Настроить Расписание", callback_data="a_sched_menu")],
        [InlineKeyboardButton("📝 Изменить группу", callback_data="a_set_group")],
        [InlineKeyboardButton("✏️ Изменить название бота", callback_data="a_set_botname")],
        [InlineKeyboardButton("🖼 Изменить картинку бота", callback_data="a_set_botphoto")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
    ])


def delete_hw_kb(tasks):
    if not tasks:
        return None
    buttons = []
    for idx, (db_id, task, due_date, _) in enumerate(tasks, start=1):
        short = task[:30] + "..." if len(task) > 30 else task
        buttons.append([InlineKeyboardButton(f"{idx}. {short}", callback_data=f"delhw_{db_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_hw_menu")])
    return InlineKeyboardMarkup(buttons)


def delete_ann_kb(anns):
    if not anns:
        return None
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
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_admins_menu")])
    return InlineKeyboardMarkup(buttons)


def schedule_edit_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Загрузить из Excel", callback_data="sched_upload")],
        [InlineKeyboardButton("📝 Редактировать по дням", callback_data="sched_by_day")],
        [InlineKeyboardButton("🗑 Удалить все пары на день", callback_data="a_del_all_day")],
        [InlineKeyboardButton("📣 Разослать замены сейчас", callback_data="force_repl_broadcast")],
        [InlineKeyboardButton("🔙 Назад", callback_data="a_bot_settings")],
    ])


def delete_all_day_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"delallday_{i}")]
               for i in range(6)]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")])
    return InlineKeyboardMarkup(buttons)


def weekday_choice_kb():
    buttons = [[InlineKeyboardButton(WEEKDAYS_RU[i].capitalize(), callback_data=f"schedday_{i}")]
               for i in range(6)]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="a_sched_menu")])
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