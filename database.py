import logging
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL, GROUP_NAME, BOT_DISPLAY_NAME

logger = logging.getLogger(__name__)

_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)


@contextmanager
def get_cursor(commit=False):
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _pool.putconn(conn)


def upsert_user(user_id, username=None, first_name=None):
    """Создаёт/обновляет юзера. Если забанен — НЕ перезаписывает, чтобы не вернуть случайно."""
    try:
        with get_cursor(commit=True) as cur:
            # Проверяем бан-статус
            cur.execute("SELECT is_banned FROM users WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            if row and row.get("is_banned"):
                return  # Забаненный, не трогаем
            cur.execute("""
                INSERT INTO users (id, username, first_name, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET username = EXCLUDED.username, first_name = EXCLUDED.first_name;
            """, (user_id, username, first_name))
    except Exception:
        logger.exception("upsert_user failed")


def set_user_display_name(user_id, display_name):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE users SET display_name = %s WHERE id = %s;", (display_name, user_id))
            return True
    except Exception:
        logger.exception("set_user_display_name failed")
        return False


def get_user_display_name(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT display_name FROM users WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            return row["display_name"] if row else None
    except Exception:
        logger.exception("get_user_display_name failed")
        return None


def is_user_banned(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT is_banned FROM users WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            return bool(row and row.get("is_banned"))
    except Exception:
        return False


def ban_user(user_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE users SET is_banned = true, banned_at = NOW() WHERE id = %s;",
                (user_id,),
            )
            return True
    except Exception:
        logger.exception("ban_user failed")
        return False


def unban_user(user_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE users SET is_banned = false, banned_at = NULL WHERE id = %s;",
                (user_id,),
            )
            return True
    except Exception:
        logger.exception("unban_user failed")
        return False


def delete_user_by_id(user_id):
    """Алиас для совместимости — теперь не удаляет, а банит."""
    return ban_user(user_id)


def get_all_user_ids():
    """Только НЕ забаненные."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE is_banned = false OR is_banned IS NULL;")
            return [row["id"] for row in cur.fetchall()]
    except Exception:
        logger.exception("get_all_user_ids failed")
        return []


def is_admin(user_id):
    """Только не забаненные."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM admins WHERE user_id = %s "
                "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = admins.user_id AND u.is_banned = true);",
                (user_id,),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("is_admin failed")
        return False


def get_all_admins():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT user_id, username, name FROM admins ORDER BY name;")
            return [(row["user_id"], row["username"], row["name"]) for row in cur.fetchall()]
    except Exception:
        logger.exception("get_all_admins failed")
        return []


def add_admin_to_db(user_id, username, name):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO admins (user_id, username, name) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id) DO NOTHING;",
                (user_id, username, name),
            )
        return True
    except Exception:
        logger.exception("add_admin_to_db failed")
        return False


def remove_admin_by_user_id(user_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM admins WHERE user_id = %s RETURNING user_id;", (user_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("remove_admin_by_user_id failed")
        return False


def add_task_db(task_text, due_date_str):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO homework (task, due_date, created_at) VALUES (%s, %s, NOW()) RETURNING id;",
                (task_text, due_date_str),
            )
            return cur.fetchone()["id"]
    except Exception:
        logger.exception("add_task_db failed")
        return None


def get_all_tasks_db():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, task, due_date, created_at FROM homework ORDER BY due_date, created_at;")
            return [(r["id"], r["task"], r["due_date"], r["created_at"]) for r in cur.fetchall()]
    except Exception:
        logger.exception("get_all_tasks_db failed")
        return []


def delete_task_db(task_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM homework WHERE id = %s RETURNING id;", (task_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("delete_task_db failed")
        return False


def add_announcement_db(text, author_id, is_replacement_note=False, photo_id=None):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO announcements (text, created_at, author_id, is_active, is_replacement_note, photo_id) "
                "VALUES (%s, NOW(), %s, true, %s, %s) RETURNING id;",
                (text, author_id, is_replacement_note, photo_id),
            )
            return cur.fetchone()["id"]
    except Exception:
        logger.exception("add_announcement_db failed")
        return None


def get_active_announcements():
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, text, created_at, is_replacement_note, photo_id "
                "FROM announcements WHERE is_active = true ORDER BY created_at DESC;"
            )
            return [(r["id"], r["text"], str(r["created_at"]), r["is_replacement_note"], r["photo_id"])
                    for r in cur.fetchall()]
    except Exception:
        logger.exception("get_active_announcements failed")
        return []


def get_active_replacement_notes():
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT text FROM announcements WHERE is_active = true AND is_replacement_note = true "
                "ORDER BY created_at DESC;"
            )
            return [r["text"] for r in cur.fetchall()]
    except Exception:
        logger.exception("get_active_replacement_notes failed")
        return []


def deactivate_announcement_db(ann_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE announcements SET is_active = false WHERE id = %s RETURNING id;", (ann_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("deactivate_announcement_db failed")
        return False


DEFAULT_PAIRS_NUM = 4
DEFAULT_PAIRS_DEN = 3


def init_default_schedule():
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("SELECT1 FROM schedule LIMIT 1;")
            if cur.fetchone():
                return
            for day in range(6):
                for pair in range(1, DEFAULT_PAIRS_NUM + 1):
                    cur.execute(
                        "INSERT INTO schedule (week_type, day_of_week, pair_number, subject, teacher, room, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING;",
                        ("Числитель", day, pair, f"{pair} пара", "1 преподаватель", "1 Кабинет"),
                    )
                for pair in range(1, DEFAULT_PAIRS_DEN + 1):
                    cur.execute(
                        "INSERT INTO schedule (week_type, day_of_week, pair_number, subject, teacher, room, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING;",
                        ("Знаменатель", day, pair, f"{pair} пара", "1 преподаватель", "1 Кабинет"),
                    )
        logger.info("Заводское расписание загружено")
    except Exception:
        logger.exception("init_default_schedule failed")


def get_base_schedule(week_type, day_of_week):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT pair_number, subject, teacher, room FROM schedule "
                "WHERE week_type = %s AND day_of_week = %s ORDER BY pair_number;",
                (week_type, day_of_week),
            )
            return {r["pair_number"]: {"subject": r["subject"], "teacher": r["teacher"], "room": r["room"]}
                    for r in cur.fetchall()}
    except Exception:
        logger.exception("get_base_schedule failed")
        return {}


def replace_day_schedule(week_type, day_of_week, entries):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM schedule WHERE week_type = %s AND day_of_week = %s;", (week_type, day_of_week))
            for e in entries:
                cur.execute(
                    "INSERT INTO schedule (week_type, day_of_week, pair_number, subject, teacher, room, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,NOW());",
                    (week_type, day_of_week, e["pair_number"], e["subject"], e["teacher"], e["room"]),
                )
        return True
    except Exception:
        logger.exception("replace_day_schedule failed")
        return False


def delete_all_pairs_for_day(day_of_week):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM schedule WHERE day_of_week = %s;", (day_of_week,))
        return True
    except Exception:
        logger.exception("delete_all_pairs_for_day failed")
        return False


def upsert_pair(week_type, day_of_week, pair_number, subject, teacher, room):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO schedule (week_type, day_of_week, pair_number, subject, teacher, room, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (week_type, day_of_week, pair_number)
                DO UPDATE SET subject = EXCLUDED.subject, teacher = EXCLUDED.teacher, room = EXCLUDED.room;
            """, (week_type, day_of_week, pair_number, subject, teacher, room))
        return True
    except Exception:
        logger.exception("upsert_pair failed")
        return False


def delete_pair(week_type, day_of_week, pair_number):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM schedule WHERE week_type=%s AND day_of_week=%s AND pair_number=%s;",
                (week_type, day_of_week, pair_number),
            )
        return True
    except Exception:
        logger.exception("delete_pair failed")
        return False


def get_cached_schedule(target_date):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM schedule_history WHERE date = %s ORDER BY pair_num;", (target_date,))
            rows = cur.fetchall()
            return rows if rows else None
    except Exception:
        logger.exception("get_cached_schedule failed")
        return None


def save_schedule_cache(target_date, week_type, day, entries):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM schedule_history WHERE date = %s;", (target_date,))
            for e in entries:
                cur.execute("""
                    INSERT INTO schedule_history
                    (date, week_type, day, pair_num, subject, teacher, room, is_replaced,
                     original_subject, original_teacher, original_room, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW());
                """, (
                    target_date, week_type, day, e["pair_num"], e["subject"], e.get("teacher", ""),
                    e.get("room", ""), e.get("is_replaced", False),
                    e.get("original_subject"), e.get("original_teacher"), e.get("original_room"),
                ))
        return True
    except Exception:
        logger.exception("save_schedule_cache failed")
        return False


def get_setting(key, default=None):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s;", (key,))
            row = cur.fetchone()
            return row["value"] if row else default
    except Exception:
        logger.exception("get_setting failed")
        return default


def set_setting(key, value):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO settings (key, value, created_at) VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """, (key, value))
        return True
    except Exception:
        logger.exception("set_setting failed")
        return False


def get_current_shift():
    return get_setting("current_shift", "1")


def set_current_shift(shift):
    return set_setting("current_shift", shift)


def get_group_name():
    return get_setting("group_name", GROUP_NAME)


def set_group_name(name):
    return set_setting("group_name", name)


def get_bot_display_name():
    return get_setting("bot_display_name", BOT_DISPLAY_NAME)


def set_bot_display_name(name):
    return set_setting("bot_display_name", name)


def get_support_username():
    return get_setting("support_username", "admin")


def set_support_username(username):
    return set_setting("support_username", username)


def get_support_link():
    return get_setting("support_link", "https://t.me/admin")


def set_support_link(link):
    return set_setting("support_link", link)


def get_last_replacements_date():
    return get_setting("last_replacements_date", "")


def set_last_replacements_date(date_iso):
    return set_setting("last_replacements_date", date_iso)


def get_image(kind):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT image_bytes FROM schedule_images WHERE kind = %s;", (kind,))
            row = cur.fetchone()
            return bytes(row["image_bytes"]) if row else None
    except Exception:
        logger.exception("get_image failed")
        return None


def save_image(kind, data):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO schedule_images (kind, image_bytes, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (kind) DO UPDATE SET image_bytes = EXCLUDED.image_bytes, updated_at = NOW();
            """, (kind, data))
        return True
    except Exception:
        logger.exception("save_image failed")
        return False


def add_extra_class(subject, description, photo_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO extra_classes (subject, description, photo_id, created_at, is_active) "
                "VALUES (%s, %s, %s, NOW(), true) RETURNING id;",
                (subject, description, photo_id),
            )
            return cur.fetchone()["id"]
    except Exception:
        logger.exception("add_extra_class failed")
        return None


def get_active_extra_classes():
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, subject, description, photo_id, created_at FROM extra_classes "
                "WHERE is_active = true ORDER BY created_at DESC;"
            )
            return [(r["id"], r["subject"], r["description"], r["photo_id"], str(r["created_at"]))
                    for r in cur.fetchall()]
    except Exception:
        logger.exception("get_active_extra_classes failed")
        return []


def get_extra_class(item_id):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, subject, description, photo_id FROM extra_classes "
                "WHERE id = %s AND is_active = true;", (item_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return (row["id"], row["subject"], row["description"], row["photo_id"])
    except Exception:
        logger.exception("get_extra_class failed")
        return None


def deactivate_extra_class(item_id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE extra_classes SET is_active = false WHERE id = %s RETURNING id;", (item_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("deactivate_extra_class failed")
        return False


def get_user_settings_row(user_id):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, first_name, display_name, is_banned, "
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


def set_user_notify(user_id, kind, enabled):
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
            return True
    except Exception:
        logger.exception("set_user_notify failed")
        return False


def get_all_active_users():
    """Не забаненные пользователи (для отображения в админке)."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, first_name, display_name, created_at FROM users "
                "WHERE is_banned = false OR is_banned IS NULL ORDER BY created_at DESC;"
            )
            return [(r["id"], r["username"], r["first_name"], r["display_name"], str(r["created_at"]))
                    for r in cur.fetchall()]
    except Exception:
        logger.exception("get_all_active_users failed")
        return []


def get_all_banned_users():
    """Забаненные пользователи."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, first_name, display_name, created_at, banned_at FROM users "
                "WHERE is_banned = true ORDER BY banned_at DESC;"
            )
            return [(r["id"], r["username"], r["first_name"], r["display_name"], str(r["created_at"]), str(r["banned_at"]))
                    for r in cur.fetchall()]
    except Exception:
        logger.exception("get_all_banned_users failed")
        return []


def get_all_users_with_username():
    """Алиас для совместимости — теперь только активные."""
    return get_all_active_users()


def get_user_ids_with_notify(kind):
    """Только НЕ забаненные."""
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
            cur.execute(
                f"SELECT id FROM users WHERE {col} = true "
                f"AND (is_banned = false OR is_banned IS NULL);"
            )
            return [row["id"] for row in cur.fetchall()]
    except Exception:
        logger.exception("get_user_ids_with_notify failed")
        return []