import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задана")

INITIAL_ADMIN_ID = int(os.environ.get("INITIAL_ADMIN_ID", "1207797393"))

GROUP_NAME = os.environ.get("GROUP_NAME", "ИБ1-31")

SCHEDULE_SITE_URL_SHIFT1 = "https://menu.sttec.yar.ru/timetable/rasp_first.html"
SCHEDULE_SITE_URL_SHIFT2 = "https://menu.sttec.yar.ru/timetable/rasp_second.html"


def get_site_url(shift: str) -> str:
    return SCHEDULE_SITE_URL_SHIFT2 if str(shift) == "2" else SCHEDULE_SITE_URL_SHIFT1


WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
MONTHS_RU_TO_NUM = {v: k for k, v in MONTHS_RU.items()}

NUMBER_EMOJIS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

(
    HW_TEXT, HW_DUE,
    ANN_TEXT, ANN_CONFIRM,
    REPLNOTE_TEXT, REPLNOTE_CONFIRM,
    PH_DATE,
    SCHED_UPLOAD_TEXT,
    SCHED_FIELD_VALUE,
    ADMIN_ID, ADMIN_NAME,
) = range(11)
