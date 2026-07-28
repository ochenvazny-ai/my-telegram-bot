import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задана")

INITIAL_ADMIN_ID = int(os.environ.get("INITIAL_ADMIN_ID", "1207797393"))

GROUP_NAME = os.environ.get("GROUP_NAME", "ИБ1-31")

SCHEDULE_SITE_URL = "https://menu.sttec.yar.ru/timetable/rasp_first.html"

WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
MONTHS_RU_TO_NUM = {v: k for k, v in MONTHS_RU.items()}

BELL_SCHEDULE_REGULAR = [
    ("1 урок", "08:30", "09:15"),
    ("2 урок", "09:25", "10:10"),
    ("3 урок", "10:20", "11:05"),
    ("4 урок", "11:15", "12:00"),
    ("5 урок", "12:10", "12:55"),
    ("6 урок", "13:05", "13:50"),
]

BELL_SCHEDULE_PRE_HOLIDAY = [
    ("1 урок", "08:30", "09:05"),
    ("2 урок", "09:15", "09:50"),
    ("3 урок", "10:00", "10:35"),
    ("4 урок", "10:45", "11:20"),
    ("5 урок", "11:30", "12:05"),
]

NUMBER_EMOJIS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

(
    HW_TEXT, HW_DUE,
    ANN_TEXT, ANN_CONFIRM,
    PH_DATE,
    SCHED_UPLOAD_TEXT,
    SCHED_FIELD_VALUE,
    ADMIN_ID, ADMIN_NAME,
) = range(9)
