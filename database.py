# ---------- В users: ничего нового не надо, поля уже в миграции ----------

def set_user_display_name(user_id: int, name: str) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE users SET display_name = %s WHERE id = %s;", (name, user_id)
            )
            return cur.rowcount > 0
    except Exception:
        logger.exception("set_user_display_name failed")
        return False


def get_user_settings_row(user_id: int) -> dict:
    """Возвращает строку настроек юзера (имя +4 подписки)."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, first_name, display_name, "
                "notify_replacements, notify_announcements, notify_homework, notify_extra_classes "
                "FROM users WHERE id = %s;",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {}
            return dict(row)
    except Exception:
        logger.exception("get_user_settings_row failed")
        return {}


def set_user_notify(user_id: int, kind: str, enabled: bool) -> bool:
    col_map = {
        "replacements": "notify_replacements",
        "announcements": "notify_announcements",
        "homework": "notify_homework",
        "extra_classes": "notify_extra_classes",
 }
    col = col_map.get(kind)
    if not col:
        return False
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(f"UPDATE users SET {col} = %s WHERE id = %s;", (enabled, user_id))
            return True except Exception:
        logger.exception("set_user_notify failed")
        return False


def get_all_users_with_username() -> list:
    """Список юзеров для админ-панели."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, first_name, display_name, created_at "
                "FROM users ORDER BY created_at DESC;"
            )
            return [(r["id"], r["username"], r["first_name"], r["display_name"], str(r["created_at"]))
 for r in cur.fetchall()]
    except Exception:
        logger.exception("get_all_users_with_username failed")
        return []


# ---------- USER NOTES (долги и заметки) ----------
def add_user_note(user_id: int, kind: str, title: str, content: str | None) -> int | None:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO user_notes (user_id, kind, title, content, created_at) "
                "VALUES (%s, %s, %s, %s, NOW()) RETURNING id;",
                (user_id, kind, title, content),
            )
            return cur.fetchone()["id"]
    except Exception:
        logger.exception("add_user_note failed")
        return None


def get_user_notes(user_id: int, kind: str, include_done: bool = False) -> list:
    try:
        with get_cursor() as cur:
            if include_done:
                cur.execute(
                    "SELECT id, title, content, is_done, created_at FROM user_notes "
                    "WHERE user_id = %s AND kind = %s ORDER BY is_done, created_at DESC;",
                    (user_id, kind),
                )
            else:
                cur.execute(
                    "SELECT id, title, content, is_done, created_at FROM user_notes "
                    "WHERE user_id = %s AND kind = %s AND is_done = false ORDER BY created_at DESC;",
                    (user_id, kind),
                )
            return [(r["id"], r["title"], r["content"], r["is_done"], str(r["created_at"]))
                    for r in cur.fetchall()]
    except Exception:
        logger.exception("get_user_notes failed")
        return []


def get_user_note(note_id: int):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, user_id, kind, title, content, is_done FROM user_notes WHERE id = %s;",
                (note_id,),
            )
            row = cur.fetchone()
            if not row:
 return None
            return (row["id"], row["user_id"], row["kind"], row["title"], row["content"], row["is_done"])
    except Exception:
        logger.exception("get_user_note failed for %s", note_id)
        return None


def set_user_note_done(note_id: int, done: bool) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE user_notes SET is_done = %s WHERE id = %s RETURNING id;",
                (done, note_id),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("set_user_note_done failed")
        return False


def delete_user_note(note_id: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM user_notes WHERE id = %s RETURNING id;", (note_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("delete_user_note failed")
        return False


# ---------- Уведомления: кому слать ----------
def get_user_ids_with_notify(kind: str) -> list:
    """Возвращает user_id тех, кто подписан на указанный тип уведомлений.
    kind: 'replacements' | 'announcements' | 'homework' | 'extra_classes'"""
    col_map = {
        "replacements": "notify_replacements",
        "announcements": "notify_announcements",
        "homework": "notify_homework",
        "extra_classes": "notify_extra_classes",
    }
    col = col_map.get(kind)
    if not col:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(f"SELECT id FROM users WHERE {col} = true;")
            return [row["id"] for row in cur.fetchall()]
    except Exception:
        logger.exception("get_user_ids_with_notify failed")
        return []