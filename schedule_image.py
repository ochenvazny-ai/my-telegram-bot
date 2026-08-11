"""Генерация изображений расписания (вертикальная таблица) для Telegram-бота.

Лейаут:
  * Одиночный тип недели — 6 дневных секций, расположенных друг под другом.
    Внутри каждой секции: горизонтальная таблица с колонками
    [№ пары | Предмет | Преподаватель | Кабинет], пары идут сверху вниз (0..6).
  * Сравнение Числитель/Знаменатель — те же вертикальные секции, но в каждой
    секции две группы колонок рядом: Числитель и Знаменатель. Отличающиеся
    ячейки Знаменателя подсвечиваются оранжевым (COLOR_DIFF).

Публичные функции (вызываются из handlers_user.py через asyncio.to_thread):
    render_schedule_image(week_type: str) -> bytes
    render_comparison_image() -> bytes
"""

import io
import os
import logging

from PIL import Image, ImageDraw, ImageFont

import database as db

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Константы оформления
# --------------------------------------------------------------------------- #
COLOR_BG = (255, 255, 255)          # фон изображения
COLOR_GRID = (200, 200, 200)         # линии сетки
COLOR_TEXT = (33, 37, 41)           # основной текст
COLOR_HEADER_BG = (52, 73, 94)      # фон шапки дня
COLOR_HEADER_TEXT = (255, 255, 255) # текст шапки дня
COLOR_COLHDR_BG = (236, 240, 241)   # фон заголовков колонок
COLOR_DIFF = (230, 126, 34)         # подсветка отличий (знаменатель)
COLOR_DIFF_TEXT = (255, 255, 255)   # текст на оранжевой подсветке
COLOR_ALT_ROW = (248, 249, 250)     # альтернативная строка (зебра)
COLOR_EMPTY = (245, 245, 245)       # пустая ячейка

# Дни недели (понедельник .. суббота, индексы 0..5 — как weekday() в datetime)
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]

# Размеры ячеек
MARGIN = 10
COL_PAIR = 50
COL_SUBJECT = 200
COL_TEACHER = 150
COL_ROOM = 80
CELL_HEIGHT = 60
HEADER_HEIGHT = 35          # высота полосы с названием дня
COL_HEADER_HEIGHT = 30      # высота строки с названиями колонок
TITLE_HEIGHT = 50           # высота заголовка изображения
SECTION_GAP = 8             # отступ между дневными секциями
MAX_PAIR = 6                # пары 0..6

WEEK_TYPES = ("Числитель", "Знаменатель")

# --------------------------------------------------------------------------- #
#  Шрифты (DejaVuSans)
# --------------------------------------------------------------------------- #
_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/dejavu/DejaVuSans.ttf",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/dejavu/DejaVuSans-Bold.ttf",
]


def _find_font(candidates):
    """Ищет файл шрифта по списку путей, затем — в данных matplotlib."""
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        import matplotlib
        mpl_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        for path in candidates:
            full = os.path.join(mpl_dir, os.path.basename(path))
            if os.path.exists(full):
                return full
    except Exception:
        logger.debug("matplotlib недоступен для поиска шрифтов")
    return None


_REGULAR_PATH = _find_font(_REGULAR_CANDIDATES)
_BOLD_PATH = _find_font(_BOLD_CANDIDATES)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _BOLD_PATH if bold else _REGULAR_PATH
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        logger.exception("Не удалось загрузить шрифт %s", path)
    return ImageFont.load_default()


# Кэшированные шрифты
_FONT_TITLE = _load_font(24, bold=True)
_FONT_DAY = _load_font(17, bold=True)
_FONT_COLHDR = _load_font(13, bold=True)
_FONT_BODY = _load_font(13, bold=False)


# --------------------------------------------------------------------------- #
#  Низкоуровневые помощники отрисовки
# --------------------------------------------------------------------------- #
def _wrap_text(text, font, max_width):
    """Перенос текста по словам (с посимвольным дроблением слишком длинных слов)."""
    text = "" if text is None else str(text).strip()
    if not text:
        return []
    words = text.split()
    if not words:
        # одни пробелы/переносы — рисуем как есть
        return [text]
    raw_lines = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            raw_lines.append(current)
            current = word
    raw_lines.append(current)

    # Дробим слишком длинные слова посимвольно
    final_lines = []
    for line in raw_lines:
        if font.getlength(line) <= max_width:
            final_lines.append(line)
            continue
        chunk = ""
        for ch in line:
            if chunk and font.getlength(chunk + ch) > max_width:
                final_lines.append(chunk)
                chunk = ch
            else:
                chunk += ch
        if chunk:
            final_lines.append(chunk)
    return final_lines


def _line_height(font):
    return font.getbbox("Ag")[3] + 4


def _draw_cell(draw, x, y, w, h, text, font, fill=None, text_color=COLOR_TEXT,
               align="center", wrap=True, border=True):
    """Рисует одну ячейку: заливка, рамка, текст (с переносом и центрированием)."""
    if fill is not None:
        draw.rectangle([x, y, x + w - 1, y + h - 1], fill=fill)
    if border:
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=COLOR_GRID)

    display = "" if text is None else str(text).strip()
    if not display:
        return

    max_w = w - 8
    lines = _wrap_text(display, font, max_w) if wrap else [display]
    lh = _line_height(font)
    total = lh * len(lines)
    start_y = y + max(2, (h - total) // 2)

    for i, line in enumerate(lines):
        ty = start_y + i * lh
        if align == "center":
            tx = x + (w - font.getlength(line)) // 2
        elif align == "right":
            tx = x + (w - font.getlength(line)) - 5
        else:
            tx = x + 5
        draw.text((tx, ty), line, fill=text_color, font=font)


def _draw_section_header(draw, x, y, w, title, subtitle=None):
    """Полоса-заголовок дневной секции с названием дня."""
    draw.rectangle([x, y, x + w - 1, y + HEADER_HEIGHT - 1], fill=COLOR_HEADER_BG)
    # Название дня — слева, с отступом
    label = title.capitalize()
    if subtitle:
        label = f"{label}   ·   {subtitle}"
    tw = _FONT_DAY.getlength(label)
    ty = y + (HEADER_HEIGHT - (_FONT_DAY.getbbox("Ag")[3] + 2)) // 2
    draw.text((x + 10, ty), label, fill=COLOR_HEADER_TEXT, font=_FONT_DAY)
    return HEADER_HEIGHT


# --------------------------------------------------------------------------- #
#  Доступ к данным
# --------------------------------------------------------------------------- #
def _pair_info(base, pair):
    """Возвращает (subject, teacher, room) для пары из словаря базы."""
    info = base.get(pair) or base.get(str(pair))
    if not info:
        return ("", "", "")
    return (
        str(info.get("subject", "") or ""),
        str(info.get("teacher", "") or ""),
        str(info.get("room", "") or ""),
    )


def _day_pairs(week_type, day_idx):
    """Словарь {pair_number: (subject, teacher, room)} для пар 0..6."""
    base = db.get_base_schedule(week_type, day_idx)
    return {p: _pair_info(base, p) for p in range(0, MAX_PAIR + 1)}


# --------------------------------------------------------------------------- #
#  Одиночное расписание
# --------------------------------------------------------------------------- #
def _single_table_width():
    return COL_PAIR + COL_SUBJECT + COL_TEACHER + COL_ROOM


def _render_single(week_type: str) -> bytes:
    table_w = _single_table_width()
    img_w = 2 * MARGIN + table_w

    # Собираем данные по всем дням
    days = [(name, _day_pairs(week_type, idx)) for idx, name in enumerate(WEEKDAYS_RU)]

    # Считаем высоту изображения
    section_h = HEADER_HEIGHT + COL_HEADER_HEIGHT + (MAX_PAIR + 1) * CELL_HEIGHT
    img_h = MARGIN + TITLE_HEIGHT + len(days) * section_h + (len(days) - 1) * SECTION_GAP + MARGIN

    img = Image.new("RGB", (img_w, img_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # Заголовок
    _draw_title(draw, 0, MARGIN, img_w, TITLE_HEIGHT, f"Расписание — {week_type}")

    y = MARGIN + TITLE_HEIGHT
    for name, pairs in days:
        _draw_single_section(draw, MARGIN, y, table_w, name, pairs)
        y += section_h + SECTION_GAP

    return _to_png(img)


def _draw_single_section(draw, x, y, w, day_name, pairs):
    """Рисует одну дневную секцию: шапка + колонки + 7 строк пар."""
    _draw_section_header(draw, x, y, w, day_name)
    y += HEADER_HEIGHT

    # Заголовки колонок
    col_x = [x, x + COL_PAIR, x + COL_PAIR + COL_SUBJECT,
             x + COL_PAIR + COL_SUBJECT + COL_TEACHER]
    col_w = [COL_PAIR, COL_SUBJECT, COL_TEACHER, COL_ROOM]
    headers = ["№", "Предмет", "Преподаватель", "Кабинет"]
    for cx, cw, head in zip(col_x, col_w, headers):
        draw.rectangle([cx, y, cx + cw - 1, y + COL_HEADER_HEIGHT - 1],
                       fill=COLOR_COLHDR_BG, outline=COLOR_GRID)
        ty = y + (COL_HEADER_HEIGHT - (_FONT_COLHDR.getbbox("Ag")[3] + 2)) // 2
        tx = cx + (cw - _FONT_COLHDR.getlength(head)) // 2
        draw.text((tx, ty), head, fill=COLOR_TEXT, font=_FONT_COLHDR)
    y += COL_HEADER_HEIGHT

    # Строки пар (0..6)
    for row_idx, pair_num in enumerate(range(0, MAX_PAIR + 1)):
        subject, teacher, room = pairs.get(pair_num, ("", "", ""))
        empty = not (subject or teacher or room)
        row_fill = COLOR_ALT_ROW if row_idx % 2 else None

        _draw_cell(draw, col_x[0], y, col_w[0], CELL_HEIGHT,
                   str(pair_num), _FONT_BODY, fill=row_fill, align="center")
        _draw_cell(draw, col_x[1], y, col_w[1], CELL_HEIGHT,
                   subject or "—", _FONT_BODY, fill=row_fill, align="left")
        _draw_cell(draw, col_x[2], y, col_w[2], CELL_HEIGHT,
                   teacher or ("—" if empty else "—"), _FONT_BODY,
                   fill=row_fill, align="left")
        _draw_cell(draw, col_x[3], y, col_w[3], CELL_HEIGHT,
                   room or "—", _FONT_BODY, fill=row_fill, align="center")
        y += CELL_HEIGHT


# --------------------------------------------------------------------------- #
#  Сравнение Числитель / Знаменатель
# --------------------------------------------------------------------------- #
def _comparison_table_width():
    half = COL_SUBJECT + COL_TEACHER + COL_ROOM
    return COL_PAIR + half * 2


def _render_comparison() -> bytes:
    table_w = _comparison_table_width()
    img_w = 2 * MARGIN + table_w

    # Групповой заголовок + подзаголовок колонок -> две строки шапки
    group_header_h = COL_HEADER_HEIGHT
    sub_header_h = COL_HEADER_HEIGHT
    section_h = HEADER_HEIGHT + group_header_h + sub_header_h + (MAX_PAIR + 1) * CELL_HEIGHT

    days = [(name, _day_pairs("Числитель", idx), _day_pairs("Знаменатель", idx))
            for idx, name in enumerate(WEEKDAYS_RU)]

    img_h = MARGIN + TITLE_HEIGHT + len(days) * section_h + (len(days) - 1) * SECTION_GAP + MARGIN

    img = Image.new("RGB", (img_w, img_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    _draw_title(draw, 0, MARGIN, img_w, TITLE_HEIGHT,
                "Сравнение: Числитель / Знаменатель")

    y = MARGIN + TITLE_HEIGHT
    for name, num_pairs, den_pairs in days:
        _draw_comparison_section(draw, MARGIN, y, table_w, name, num_pairs, den_pairs)
        y += section_h + SECTION_GAP

    return _to_png(img)


def _draw_comparison_section(draw, x, y, w, day_name, num_pairs, den_pairs):
    half_w = COL_SUBJECT + COL_TEACHER + COL_ROOM
    # координаты колонок
    col_x = [
        x,                                              # №
        x + COL_PAIR,                                   # num subject
        x + COL_PAIR + COL_SUBJECT,                     # num teacher
        x + COL_PAIR + COL_SUBJECT + COL_TEACHER,       # num room
        x + COL_PAIR + half_w,                          # den subject
        x + COL_PAIR + half_w + COL_SUBJECT,            # den teacher
        x + COL_PAIR + half_w + COL_SUBJECT + COL_TEACHER,  # den room
    ]
    col_w = [COL_PAIR, COL_SUBJECT, COL_TEACHER, COL_ROOM,
             COL_SUBJECT, COL_TEACHER, COL_ROOM]

    # Шапка дня
    _draw_section_header(draw, x, y, w, day_name)
    y += HEADER_HEIGHT

    # Групповая строка: № | Числитель | Знаменатель
    group_header_h = COL_HEADER_HEIGHT
    group_labels = [(col_x[0], col_w[0], "№"),
                    (col_x[1], half_w, "Числитель"),
                    (col_x[4], half_w, "Знаменатель")]
    for cx, cw, label in group_labels:
        draw.rectangle([cx, y, cx + cw - 1, y + group_header_h - 1],
                       fill=COLOR_COLHDR_BG, outline=COLOR_GRID)
        ty = y + (group_header_h - (_FONT_COLHDR.getbbox("Ag")[3] + 2)) // 2
        tx = cx + (cw - _FONT_COLHDR.getlength(label)) // 2
        draw.text((tx, ty), label, fill=COLOR_TEXT, font=_FONT_COLHDR)
    y += group_header_h

    # Подзаголовок колонок: Предмет/Преподаватель/Кабинет (дважды)
    sub_header_h = COL_HEADER_HEIGHT
    sub_labels = ["Предмет", "Преподаватель", "Кабинет", "Предмет", "Преподаватель", "Кабинет"]
    for cx, cw, label in zip(col_x[1:], col_w[1:], sub_labels):
        draw.rectangle([cx, y, cx + cw - 1, y + sub_header_h - 1],
                       fill=COLOR_COLHDR_BG, outline=COLOR_GRID)
        ty = y + (sub_header_h - (_FONT_COLHDR.getbbox("Ag")[3] + 2)) // 2
        tx = cx + (cw - _FONT_COLHDR.getlength(label)) // 2
        draw.text((tx, ty), label, fill=COLOR_TEXT, font=_FONT_COLHDR)
    y += sub_header_h

    # Строки пар (0..6)
    for row_idx, pair_num in enumerate(range(0, MAX_PAIR + 1)):
        num = num_pairs.get(pair_num, ("", "", ""))
        den = den_pairs.get(pair_num, ("", "", ""))
        row_fill = COLOR_ALT_ROW if row_idx % 2 else None

        # Номер пары
        _draw_cell(draw, col_x[0], y, col_w[0], CELL_HEIGHT,
                   str(pair_num), _FONT_BODY, fill=row_fill, align="center")

        # Числитель
        num_values = [num[0], num[1], num[2]]
        for j, val in enumerate(num_values):
            text = val or "—"
            _draw_cell(draw, col_x[1 + j], y, col_w[1 + j], CELL_HEIGHT,
                       text, _FONT_BODY, fill=row_fill, align="left")

        # Знаменатель (с подсветкой отличий)
        differ = num != den
        for j, val in enumerate(den):
            text = val or "—"
            if differ:
                cell_fill = COLOR_DIFF
                tcolor = COLOR_DIFF_TEXT
            else:
                cell_fill = row_fill
                tcolor = COLOR_TEXT
            _draw_cell(draw, col_x[4 + j], y, col_w[4 + j], CELL_HEIGHT,
                       text, _FONT_BODY, fill=cell_fill, text_color=tcolor, align="left")
        y += CELL_HEIGHT


# --------------------------------------------------------------------------- #
#  Общие помощники
# --------------------------------------------------------------------------- #
def _draw_title(draw, x, y, w, h, title):
    tw = _FONT_TITLE.getlength(title)
    ty = y + (h - (_FONT_TITLE.getbbox("Ag")[3] + 2)) // 2
    tx = x + (w - tw) // 2
    draw.text((tx, ty), title, fill=COLOR_TEXT, font=_FONT_TITLE)


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
#  Публичный API
# --------------------------------------------------------------------------- #
def render_schedule_image(week_type: str) -> bytes:
    """PNG-изображение расписания для одного типа недели (вертикальный лейаут)."""
    try:
        if week_type not in WEEK_TYPES:
            logger.warning("Неизвестный тип недели: %s", week_type)
            week_type = WEEK_TYPES[0]
        return _render_single(week_type)
    except Exception:
        logger.exception("render_schedule_image failed for %s", week_type)
        return _error_image(f"Ошибка: {week_type}")


def render_comparison_image() -> bytes:
    """PNG-изображение сравнения Числитель/Знаменатель (вертикальный лейаут)."""
    try:
        return _render_comparison()
    except Exception:
        logger.exception("render_comparison_image failed")
        return _error_image("Ошибка сравнения")


def _error_image(message: str) -> bytes:
    """Простейшее изображение-заглушка при ошибке генерации."""
    img = Image.new("RGB", (500, 80), COLOR_BG)
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), message, fill=COLOR_DIFF, font=_FONT_BODY)
    return _to_png(img)
