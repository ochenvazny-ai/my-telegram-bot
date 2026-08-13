import io
import os
import logging
from PIL import Image, ImageDraw, ImageFont

import database as db
from config import WEEKDAYS_RU

logger = logging.getLogger(__name__)

# ---------- Геометрия ----------
MARGIN = 14
TITLE_H = 32
WATERMARK_H = 22
DAY_BANNER_H = 28
HEADER_H = 24
ROW_MIN_H = 32
LINE_H = 15
PAD_V = 6
SPLIT_GAP = 4

COL_W = {"num": 32, "subject": 200, "teacher": 160, "room": 72}

# ---------- Палитра ----------
COLOR_BG = (255, 249, 235)
COLOR_GRID = (200, 195, 180)
COLOR_DAY_BG = (50, 40, 38)
COLOR_DAY_TEXT = (255, 249, 235)
COLOR_HEADER_BG = (235, 228, 210)
COLOR_HEADER_TEXT = (50, 40, 38)
COLOR_ROW_EVEN = (255, 249, 235)
COLOR_ROW_ODD = (245, 239, 220)
COLOR_TEXT = (40, 32, 28)
COLOR_TITLE = (93, 13, 24)

COLOR_NUM = (93, 13, 24)
COLOR_DEN = (224, 120, 86)
COLOR_MATCH = (93, 13, 24)

COLOR_WM_TOP_STRIP = (61, 161, 110)
COLOR_WM_BG = (14, 40, 28)
COLOR_WM_SHADOW = (10, 33, 23)
COLOR_WM_ACCENT = (76, 168, 119)
COLOR_WM_TEXT = (255, 255, 255)

# ---------- Шрифты ----------
def _find_cyrillic_font_path(bold: bool) -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        import matplotlib
        mpl_font = os.path.join(
            matplotlib.get_data_path(), "fonts", "ttf",
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        )
        if os.path.exists(mpl_font):
            return mpl_font
    except Exception:
        logger.exception("matplotlib недоступен для получения шрифта")
    return None


_FONT_PATH_REGULAR = _find_cyrillic_font_path(bold=False)
_FONT_PATH_BOLD = _find_cyrillic_font_path(bold=True)


def _font(size=12):
    if _FONT_PATH_REGULAR:
        try:
            return ImageFont.truetype(_FONT_PATH_REGULAR, size)
        except Exception:
            logger.exception("Не удалось загрузить шрифт")
    return ImageFont.load_default()


def _font_bold(size=13):
    path = _FONT_PATH_BOLD or _FONT_PATH_REGULAR
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            logger.exception("Не удалось загрузить жирный шрифт")
    return ImageFont.load_default()


FONT_TITLE = _font_bold(18)
FONT_WM = _font_bold(12)
FONT_DAY = _font_bold(14)
FONT_HEADER = _font_bold(12)
FONT_CELL = _font(12)
FONT_CELL_BOLD = _font_bold(12)


def _wrap_lines(draw, text, font, max_width):
    if not text:
        return [""]
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            if draw.textlength(w, font=font) > max_width:
                chunk = ""
                for ch in w:
                    if draw.textlength(chunk + ch, font=font) <= max_width:
                        chunk += ch
                    else:
                        lines.append(chunk)
                        chunk = ch
                cur = chunk
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _draw_lines_centered(draw, lines, font, x, y_top, height, width, color, align_center_h=False):
    total_h = len(lines) * LINE_H
    y = y_top + max(0, (height - total_h) // 2)
    for line in lines:
        if align_center_h:
            w = draw.textlength(line, font=font)
            tx = x + max(0, (width - w) // 2)
        else:
            tx = x
        draw.text((tx, y), line, fill=color, font=font)
        y += LINE_H


def _draw_watermark_strip(draw, width, y):
    draw.rectangle([0, y, width, y + 4], fill=COLOR_WM_TOP_STRIP)
    draw.rectangle([0, y + 4, width, y + 4 + WATERMARK_H], fill=COLOR_WM_BG)
    draw.rectangle([0, y + 4 + WATERMARK_H, width, y + 4 + WATERMARK_H + 2], fill=COLOR_WM_SHADOW)


def _draw_watermark_text(draw, text, y_text_start, img_w):
    tw = draw.textlength(text, font=FONT_WM)
    tx = (img_w - tw) // 2
    ty = y_text_start + 4 + (WATERMARK_H - 13) // 2
    draw.text((tx, ty), text, fill=COLOR_WM_TEXT, font=FONT_WM)
    accent_w = 16
    accent_h = 2
    ay = ty + 6
    left_x1 = tx - accent_w - 6
    left_x2 = tx - 6
    right_x1 = tx + tw + 6
    right_x2 = right_x1 + accent_w
    draw.rectangle([left_x1, ay, left_x2, ay + accent_h], fill=COLOR_WM_ACCENT)
    draw.rectangle([right_x1, ay, right_x2, ay + accent_h], fill=COLOR_WM_ACCENT)


def _get_watermark_text() -> str:
    try:
        name = db.get_bot_display_name()
    except Exception:
        name = "Бот"
    return f"{name} — Бот"


def _get_day_data(week_type: str, day: int) -> dict:
    return db.get_base_schedule(week_type, day)


# ==================== ОДИНОЧНОЕ РАСПИСАНИЕ ====================
def render_schedule_image(week_type: str) -> bytes:
    accent = COLOR_NUM if week_type == "Числитель" else COLOR_DEN
    measure_img = Image.new("RGB", (10, 10))
    md = ImageDraw.Draw(measure_img)

    days_blocks = []
    for day in range(6):
        pairs = _get_day_data(week_type, day)
        if not pairs:
            continue
        rows = []
        for pair_num in sorted(pairs.keys()):
            info = pairs[pair_num]
            lines_s = _wrap_lines(md, info["subject"], FONT_CELL, COL_W["subject"] - 10)
            lines_t = _wrap_lines(md, info["teacher"], FONT_CELL, COL_W["teacher"] - 10)
            lines_r = _wrap_lines(md, info["room"], FONT_CELL, COL_W["room"] - 10)
            # Берём максимум по всем трём колонкам + padding
            max_lines = max(len(lines_s), len(lines_t), len(lines_r), 1)
            row_h = max(ROW_MIN_H, max_lines * LINE_H + 2 * PAD_V)
            rows.append((pair_num, lines_s, lines_t, lines_r, row_h))
        days_blocks.append((day, rows))

    table_w = sum(COL_W.values())
    img_w = table_w + MARGIN * 2

    if not days_blocks:
        return _render_empty_image(f"Расписание — {week_type}", "Нет данных для отображения", img_w)

    # Считаем высоту ПРАВИЛЬНО: учитываем все дни и все ряды
    body_h = MARGIN + TITLE_H + WATERMARK_H + 6 + HEADER_H
    for day, rows in days_blocks:
        body_h += DAY_BANNER_H
        body_h += sum(r[4] for r in rows)
    body_h += MARGIN

    img = Image.new("RGB", (img_w, body_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    x0 = MARGIN
    y = MARGIN

    # Заголовок
    title = f"Расписание — {week_type}"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((img_w - tw) // 2, y), title, fill=COLOR_TITLE, font=FONT_TITLE)
    y += TITLE_H

    # Водяной знак
    _draw_watermark_strip(draw, img_w, y)
    _draw_watermark_text(draw, _get_watermark_text(), y, img_w)
    y += 4 + WATERMARK_H + 2

    col_x = {
        "num": x0,
        "subject": x0 + COL_W["num"],
        "teacher": x0 + COL_W["num"] + COL_W["subject"],
        "room": x0 + COL_W["num"] + COL_W["subject"] + COL_W["teacher"],
    }

    # Общая шапка таблицы
    draw.rectangle([x0, y, x0 + table_w, y + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
    headers = [("№", "num"), ("Предмет", "subject"), ("Преподаватель", "teacher"), ("Кабинет", "room")]
    for label, key in headers:
        draw.text((col_x[key] + 6, y + 4), label, fill=COLOR_HEADER_TEXT, font=FONT_HEADER)
    y += HEADER_H

    # Дни
    for day, rows in days_blocks:
        # Баннер дня
        draw.rectangle([x0, y, x0 + table_w, y + DAY_BANNER_H], fill=COLOR_DAY_BG)
        day_title = WEEKDAYS_RU[day].capitalize()
        dw = draw.textlength(day_title, font=FONT_DAY)
        draw.text((x0 + (table_w - dw) // 2, y + 5), day_title, fill=COLOR_DAY_TEXT, font=FONT_DAY)
        y += DAY_BANNER_H

        # Пары дня
        for idx, (pair_num, lines_s, lines_t, lines_r, row_h) in enumerate(rows):
            bg = COLOR_ROW_EVEN if idx % 2 == 0 else COLOR_ROW_ODD
            draw.rectangle([x0, y, x0 + table_w, y + row_h], fill=bg, outline=COLOR_GRID)
            # Номер пары
            draw.text((col_x["num"] + 8, y + (row_h - LINE_H) // 2), str(pair_num),
                       fill=accent, font=FONT_CELL_BOLD)
            # Предмет
            _draw_lines_centered(draw, lines_s, FONT_CELL_BOLD, col_x["subject"] + 6, y, row_h,
                                  COL_W["subject"] - 10, accent)
            # Преподаватель
            _draw_lines_centered(draw, lines_t, FONT_CELL, col_x["teacher"] + 6, y, row_h,
                                  COL_W["teacher"] - 10, COLOR_TEXT)
            # Аудитория
            _draw_lines_centered(draw, lines_r, FONT_CELL, col_x["room"] + 6, y, row_h,
                                  COL_W["room"] - 10, COLOR_TEXT)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


def _render_empty_image(title: str, message: str, img_w: int) -> bytes:
    img_h = MARGIN + TITLE_H + WATERMARK_H + 6 + 60 + MARGIN
    img = Image.new("RGB", (img_w, img_h), COLOR_BG)
    draw = ImageDraw.Draw(img)
    y = MARGIN
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((img_w - tw) // 2, y), title, fill=COLOR_TITLE, font=FONT_TITLE)
    y += TITLE_H
    _draw_watermark_strip(draw, img_w, y)
    _draw_watermark_text(draw, _get_watermark_text(), y, img_w)
    y += 4 + WATERMARK_H + 2 + 20
    mw = draw.textlength(message, font=FONT_CELL)
    draw.text(((img_w - mw) // 2, y), message, fill=COLOR_TEXT, font=FONT_CELL)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ==================== СРАВНЕНИЕ ====================
def _cmp_field(md, num_val: str, den_val: str, max_width: int):
    equal = (num_val or "") == (den_val or "")
    if equal:
        lines = _wrap_lines(md, num_val, FONT_CELL_BOLD, max_width)
        return True, lines, lines, len(lines) * LINE_H
    lines_num = _wrap_lines(md, num_val, FONT_CELL_BOLD, max_width) if num_val else [""]
    lines_den = _wrap_lines(md, den_val, FONT_CELL_BOLD, max_width) if den_val else [""]
    h = len(lines_num) * LINE_H + SPLIT_GAP + len(lines_den) * LINE_H
    return False, lines_num, lines_den, h


def render_comparison_image() -> bytes:
    measure_img = Image.new("RGB", (10, 10))
    md = ImageDraw.Draw(measure_img)

    days_blocks = []
    for day in range(6):
        pairs_num = _get_day_data("Числитель", day)
        pairs_den = _get_day_data("Знаменатель", day)
        all_pairs = sorted(set(pairs_num.keys()) | set(pairs_den.keys()))
        if not all_pairs:
            continue

        rows = []
        for pair_num in all_pairs:
            e_num = pairs_num.get(pair_num, {"subject": "", "teacher": "", "room": ""})
            e_den = pairs_den.get(pair_num, {"subject": "", "teacher": "", "room": ""})

            eq_s, ls_num, ls_den, h_s = _cmp_field(md, e_num["subject"], e_den["subject"], COL_W["subject"] - 10)
            eq_t, lt_num, lt_den, h_t = _cmp_field(md, e_num["teacher"], e_den["teacher"], COL_W["teacher"] - 10)
            eq_r, lr_num, lr_den, h_r = _cmp_field(md, e_num["room"], e_den["room"], COL_W["room"] - 10)

            row_h = max(ROW_MIN_H, h_s + 2 * PAD_V, h_t + 2 * PAD_V, h_r + 2 * PAD_V)
            rows.append({
                "pair_num": pair_num, "row_h": row_h,
                "subject": (eq_s, ls_num, ls_den), "teacher": (eq_t, lt_num, lt_den), "room": (eq_r, lr_num, lr_den),
            })
        days_blocks.append((day, rows))

    table_w = sum(COL_W.values())
    img_w = table_w + MARGIN * 2

    if not days_blocks:
        return _render_empty_image("Расписание — Сравнение", "Нет данных для отображения", img_w)

    body_h = MARGIN + TITLE_H + WATERMARK_H + 6 + HEADER_H
    for day, rows in days_blocks:
        body_h += DAY_BANNER_H
        for r in rows:
            body_h += r["row_h"]
    body_h += MARGIN

    img = Image.new("RGB", (img_w, body_h), COLOR_BG)
    draw = ImageDraw.Draw(img)
    x0 = MARGIN
    y = MARGIN

    title = "Расписание — Сравнение"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((img_w - tw) // 2, y), title, fill=COLOR_TITLE, font=FONT_TITLE)
    y += TITLE_H

    _draw_watermark_strip(draw, img_w, y)
    _draw_watermark_text(draw, _get_watermark_text(), y, img_w)
    y += 4 + WATERMARK_H + 2

    col_x = {
        "num": x0,
        "subject": x0 + COL_W["num"],
        "teacher": x0 + COL_W["num"] + COL_W["subject"],
        "room": x0 + COL_W["num"] + COL_W["subject"] + COL_W["teacher"],
    }

    # Шапка один раз
    draw.rectangle([x0, y, x0 + table_w, y + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
    headers = [("№", "num"), ("Предмет", "subject"), ("Преподаватель", "teacher"), ("Кабинет", "room")]
    for label, key in headers:
        draw.text((col_x[key] + 6, y + 4), label, fill=COLOR_HEADER_TEXT, font=FONT_HEADER)
    y += HEADER_H

    def draw_field(col_key, eq, lines_num, lines_den, row_top, row_h):
        cx = col_x[col_key] + 6
        cw = COL_W[col_key] - 10
        if eq:
            _draw_lines_centered(draw, lines_num, FONT_CELL_BOLD, cx, row_top, row_h, cw, COLOR_MATCH)
            return
        block_h = len(lines_num) * LINE_H + SPLIT_GAP + len(lines_den) * LINE_H
        y_start = row_top + max(0, (row_h - block_h) // 2)
        yy = y_start
        for line in lines_num:
            draw.text((cx, yy), line, fill=COLOR_NUM, font=FONT_CELL_BOLD)
            yy += LINE_H
        yy += SPLIT_GAP
        den_top = yy
        den_h = len(lines_den) * LINE_H
        draw.rectangle(
            [col_x[col_key] + 2, den_top - 2, col_x[col_key] + COL_W[col_key] - 2, den_top + den_h + 2],
            outline=COLOR_DEN, width=1,
        )
        for line in lines_den:
            draw.text((cx, yy), line, fill=COLOR_DEN, font=FONT_CELL_BOLD)
            yy += LINE_H

    for day, rows in days_blocks:
        draw.rectangle([x0, y, x0 + table_w, y + DAY_BANNER_H], fill=COLOR_DAY_BG)
        day_title = WEEKDAYS_RU[day].capitalize()
        dw = draw.textlength(day_title, font=FONT_DAY)
        draw.text((x0 + (table_w - dw) // 2, y + 5), day_title, fill=COLOR_DAY_TEXT, font=FONT_DAY)
        y += DAY_BANNER_H

        for idx, row in enumerate(rows):
            row_h = row["row_h"]
            bg = COLOR_ROW_EVEN if idx % 2 == 0 else COLOR_ROW_ODD
            draw.rectangle([x0, y, x0 + table_w, y + row_h], fill=bg, outline=COLOR_GRID)
            draw.text((col_x["num"] + 8, y + (row_h - LINE_H) // 2), str(row["pair_num"]),
                       fill=COLOR_TEXT, font=FONT_CELL_BOLD)

            eq_s, ls_num, ls_den = row["subject"]
            eq_t, lt_num, lt_den = row["teacher"]
            eq_r, lr_num, lr_den = row["room"]
            draw_field("subject", eq_s, ls_num, ls_den, y, row_h)
            draw_field("teacher", eq_t, lt_num, lt_den, y, row_h)
            draw_field("room", eq_r, lr_num, lr_den, y, row_h)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ==================== ЗВОНКИ ====================
BELLS_COL_W = {"num": 70, "time": 240, "note": 200}


def _render_bells_table(rows, headers, title_text, title_color=COLOR_TITLE):
    measure_img = Image.new("RGB", (10, 10))
    md = ImageDraw.Draw(measure_img)

    table_w = sum(BELLS_COL_W.values())
    img_w = table_w + MARGIN * 2

    row_h_list = []
    for r in rows:
        cells_lines = []
        for cell in r:
            cells_lines.append(_wrap_lines(md, cell, FONT_CELL_BOLD, BELLS_COL_W["time"] - 14))
        max_lines = max(max(len(l) for l in cells_lines), 1)
        row_h_list.append(max(ROW_MIN_H, max_lines * LINE_H + 2 * PAD_V))

    body_h = MARGIN + TITLE_H + WATERMARK_H + 6 + HEADER_H + sum(row_h_list) + MARGIN

    img = Image.new("RGB", (img_w, body_h), COLOR_BG)
    draw = ImageDraw.Draw(img)
    y = MARGIN

    tw = draw.textlength(title_text, font=FONT_TITLE)
    draw.text(((img_w - tw) // 2, y), title_text, fill=title_color, font=FONT_TITLE)
    y += TITLE_H

    _draw_watermark_strip(draw, img_w, y)
    _draw_watermark_text(draw, _get_watermark_text(), y, img_w)
    y += 4 + WATERMARK_H + 2

    x0 = MARGIN
    col_x = {
        "num": x0,
        "time": x0 + BELLS_COL_W["num"],
        "note": x0 + BELLS_COL_W["num"] + BELLS_COL_W["time"],
    }

    draw.rectangle([x0, y, x0 + table_w, y + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
    for label, key in headers:
        draw.text((col_x[key] + 6, y + 4), label, fill=COLOR_HEADER_TEXT, font=FONT_HEADER)
    y += HEADER_H

    for idx, (row, row_h) in enumerate(zip(rows, row_h_list)):
        bg = COLOR_ROW_EVEN if idx % 2 == 0 else COLOR_ROW_ODD
        draw.rectangle([x0, y, x0 + table_w, y + row_h], fill=bg, outline=COLOR_GRID)
        draw.text((col_x["num"] + 6, y + (row_h - LINE_H) // 2), row[0],
                   fill=COLOR_NUM, font=FONT_CELL_BOLD)
        lines_time = _wrap_lines(md, row[1], FONT_CELL_BOLD, BELLS_COL_W["time"] - 14)
        _draw_lines_centered(draw, lines_time, FONT_CELL_BOLD, col_x["time"] + 6, y, row_h,
                              BELLS_COL_W["time"] - 10, COLOR_TEXT)
        lines_note = _wrap_lines(md, row[2], FONT_CELL, BELLS_COL_W["note"] - 14)
        _draw_lines_centered(draw, lines_note, FONT_CELL, col_x["note"] + 6, y, row_h,
                              BELLS_COL_W["note"] - 10, COLOR_TEXT)
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


def render_bells_regular_image() -> bytes:
    rows_a_b = [
        ("0 пара", "8:00 – 9:10", "8:00 – 9:10"),
        ("1 пара", "9:20 – 10:50", "9:20 – 10:50"),
        ("2 пара", "11:00 – 11:45\nперерыв 40 мин\n12:25 – 13:10", "11:00 – 12:30 (сплошная)\nперерыв 50 минут"),
        ("3 пара", "13:20 – 14:50", "13:20 – 14:50"),
        ("4 пара", "15:05 – 16:35", "15:05 – 16:35"),
        ("5 пара", "17:05 – 18:35", "17:05 – 18:35"),
        ("6 пара", "18:45 – 19:55", "18:45 – 19:55"),
    ]
    return _render_bells_table(
        rows_a_b,
        [("№", "num"), ("По А корпусу", "time"), ("По Б корпусу", "note")],
        "📞 Расписание звонков — обычные дни",
    )


def render_bells_preholiday_image() -> bytes:
    rows_pre = [
        ("0 пара", "8:00 – 9:00", ""),
        ("1 пара", "9:10 – 10:10", ""),
        ("2 пара", "10:20 – 11:20", ""),
        ("перемена", "30 минут", ""),
        ("3 пара", "11:50 – 12:50", ""),
        ("4 пара", "13:00 – 14:00", ""),
        ("5 пара", "14:10 – 15:10", ""),
        ("6 пара", "15:20 – 16:20", ""),
    ]
    return _render_bells_table(
        rows_pre,
        [("№", "num"), ("Время", "time"), ("Примечание", "note")],
        "📞 Расписание звонков — предпраздничный день",
    )


# ==================== ПРЕДГЕНЕРАЦИЯ КЭША ====================
def regenerate_all_cached_images() -> dict[str, bool]:
    results = {}
    for kind, generator in (
        ("num", lambda: render_schedule_image("Числитель")),
        ("den", lambda: render_schedule_image("Знаменатель")),
        ("cmp", render_comparison_image),
        ("bells_reg", render_bells_regular_image),
        ("bells_pre", render_bells_preholiday_image),
    ):
        try:
            data = generator()
            db.save_image(kind, data)
            results[kind] = True
        except Exception:
            logger.exception("regenerate_all_cached_images failed for %s", kind)
            results[kind] = False
    return results