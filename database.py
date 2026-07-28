import logging
from contextlib import contextmanager
from datetime import date as date_cls
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

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


# ---------- USERS ----------
def upsert_user(user_id: int, username: str = None, first_name: str = None):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO users (id, username, first_name, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET username = EXCLUDED.username, first_name = EXCLUDED.first_name;
            """, (user_id, username, first_name))
    except Exception:
        logger.exception("upsert_user failed for %s", user_id)


def get_all_user_ids():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users;")
            return [row["id"] for row in cur.fetchall()]
    except Exception:
        logger.exception("get_all_user_ids failed")
        return []


# ---------- ADMINS ----------
def is_admin(user_id: int) -> bool:
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1 FROM admins WHERE user_id = %s;", (user_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("is_admin failed for %s", user_id)
        return False


def get_all_admins():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT user_id, username, name FROM admins ORDER BY name;")
            return [(row["user_id"], row["username"], row["name"]) for row in cur.fetchall()]
    except Exception:
        logger.exception("get_all_admins failed")
        return []


def add_admin_to_db(user_id: int, username: str, name: str) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO admins (user_id, username, name) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id) DO NOTHING;",
                (user_id, username, name),
            )
        return True
    except Exception:
        logger.exception("add_admin_to_db failed for %s", user_id)
        return False


def remove_admin_by_user_id(user_id: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM admins WHERE user_id = %s RETURNING user_id;", (user_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("remove_admin_by_user_id failed for %s", user_id)
        return False


# ---------- HOMEWORK ----------
def add_task_db(task_text: str, due_date_str: str):
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


def delete_task_db(task_id: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM homework WHERE id = %s RETURNING id;", (task_id,))
            return cur.fetchone() is not None
    except Exception:
        logger.exception("delete_task_db failed for %s", task_id)
        return False


# ---------- ANNOUNCEMENTS ----------
def add_announcement_db(text: str, author_id: int):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO announcements (text, created_at, author_id, is_active) "
                "VALUES (%s, NOW(), %s, true) RETURNING id;",
                (text, author_id),
            )
            return cur.fetchone()["id"]
    except Exception:
        logger.exception("add_announcement_db failed")
        return None


def get_active_announcements():
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, text, created_at FROM announcements WHERE is_active = true "
                "ORDER BY created_at DESC;"
            )
            return [(r["id"], r["text"], str(r["created_at"])) for r in cur.fetchall()]
    except Exception:
        logger.exception("get_active_announcements failed")
        return []


def deactivate_announcement_db(ann_id: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE announcements SET is_active = false WHERE id = %s RETURNING id;", (ann_id,)
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("deactivate_announcement_db failed for %s", ann_id)
        return False


# ---------- PRE-HOLIDAYS ----------
def is_pre_holiday_today(mmdd: str) -> bool:
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pre_holidays WHERE date = %s AND is_active = true;", (mmdd,)
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("is_pre_holiday_today failed for %s", mmdd)
        return False


def set_pre_holiday(mmdd: str) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("SELECT id FROM pre_holidays WHERE date = %s;", (mmdd,))
            existing = cur.fetchone()
            if existing:
                cur.execute("UPDATE pre_holidays SET is_active = true WHERE id = %s;", (existing["id"],))
            else:
                cur.execute(
                    "INSERT INTO pre_holidays (date, is_active, created_at) VALUES (%s, true, NOW());",
                    (mmdd,),
                )
        return True
    except Exception:
        logger.exception("set_pre_holiday failed for %s", mmdd)
        return False


def get_active_pre_holidays():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, date FROM pre_holidays WHERE is_active = true ORDER BY date;")
            return [(r["id"], r["date"]) for r in cur.fetchall()]
    except Exception:
        logger.exception("get_active_pre_holidays failed")
        return []


def unset_pre_holiday(ph_id: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE pre_holidays SET is_active = false WHERE id = %s RETURNING id;", (ph_id,)
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("unset_pre_holiday failed for %s", ph_id)
        return False


# ---------- BASE SCHEDULE ----------
DEFAULT_PAIRS_NUM = 4
DEFAULT_PAIRS_DEN = 3


def init_default_schedule():
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("SELECT 1 FROM schedule LIMIT 1;")
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
        logger.info("Заводское расписание-заглушка загружено")
    except Exception:
        logger.exception("init_default_schedule failed")


def get_base_schedule(week_type: str, day_of_week: int):
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


def replace_day_schedule(week_type: str, day_of_week: int, entries: list[dict]) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM schedule WHERE week_type = %s AND day_of_week = %s;", (week_type, day_of_week)
            )
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


def delete_all_pairs_for_day(day_of_week: int) -> bool:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM schedule WHERE day_of_week = %s;", (day_of_week,))
        return True
    except Exception:
        logger.exception("delete_all_pairs_for_day failed")
        return False


def upsert_pair(week_type: str, day_of_week: int, pair_number: int, subject: str, teacher: str, room: str) -> bool:
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


def delete_pair(week_type: str, day_of_week: int, pair_number: int) -> bool:
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


# ---------- SCHEDULE HISTORY (кэш) ----------
def get_cached_schedule(target_date: date_cls):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM schedule_history WHERE date = %s ORDER BY pair_num;", (target_date,)
            )
            rows = cur.fetchall()
            return rows if rows else None
    except Exception:
        logger.exception("get_cached_schedule failed")
        return None


def save_schedule_cache(target_date: date_cls, week_type: str, day: str, entries: list[dict]) -> bool:
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
