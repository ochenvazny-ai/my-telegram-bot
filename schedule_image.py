import io
import os
import logging
from PIL import Image, ImageDraw, ImageFont

import database as db
from config import WEEKDAYS_RU

logger = logging.getLogger(__name__)

# ---------- Геометрия ----------
MARGIN = 14
TITLE_H = 34
DAY_BANNER_H = 30
HEADER_H = 26
ROW_MIN_H = 30
LINE_H = 15
PAD_V = 5
SPLIT_GAP = 4

COL_W = {"num": 34, "subject": 190, "teacher": 160, "room": 80}
TABLE_W = sum(COL_W.values())
IMG_W = TABLE_W + MARGIN * 2

# ---------- Цвета ----------
COLOR_BG = (255, 255, 255)
COLOR_GRID = (190, 190, 190)
COLOR_DAY_BG = (44, 62, 80)
COLOR_DAY_TEXT = (255, 255, 255)
COLOR_HEADER_BG = (222, 226, 230)
COLOR_HEADER_TEXT = (20, 20, 20)
COLOR_ROW_EVEN = (255, 255, 255)
COLOR_ROW_ODD = (245, 246, 247)
COLOR_TEXT = (20, 20, 20)
COLOR_ORANGE = (211, 84, 0)
COLOR_TITLE = (20, 20, 20)


# ---------- Шрифты (гарантированный источник — matplotlib, см. предыдущий фикс) ----------
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
        logger.exception("matplotlib недоступен для получения шрифта с кириллицей")
    return None


_FONT_PATH_REGULAR = _find_cyrillic_font_path(bold=False)
_FONT_PATH_BOLD = _find_cyrillic_font_path(bold=True)

if not _FONT_PATH_REGULAR:
    logger.error("Не найден TTF-шрифт с поддержкой кириллицы — текст на картинках будет нечитаем.")


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
FONT_DAY = _font_bold(14)
FONT_HEADER = _font_bold(12)
FONT_CELL = _font(12)
FONT_CELL_ORANGE = _font(12)


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


def _get_day_data(week_type: str, day: int) -> dict:
    """{pair_num(int): {subject, teacher, room}} только заполненные пары."""
    return db.get_base_schedule(week_type, day)


# ==================== ОДИНОЧНОЕ РАСПИСАНИЕ (Числитель / Знаменатель) ====================
def render_schedule_image(week_type: str) -> bytes:
    measure_img = Image.new("RGB", (10, 10))
    md = ImageDraw.Draw(measure_img)

    days_blocks = []  # (day_idx, [(pair_num, subject, teacher, room, row_h), ...])
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
            max_lines = max(len(lines_s), len(lines_t), len(lines_r), 1)
            row_h = max(ROW_MIN_H, max_lines * LINE_H + 2 * PAD_V)
            rows.append((pair_num, lines_s, lines_t, lines_r, row_h))
        days_blocks.append((day, rows))

    if not days_blocks:
        return _render_empty_image(f"Расписание — {week_type}", "Нет данных для отображения")

    total_h = MARGIN + TITLE_H
    for day, rows in days_blocks:
        total_h += DAY_BANNER_H + HEADER_H + sum(r[4] for r in rows)
    total_h += MARGIN

    img = Image.new("RGB", (IMG_W, total_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    title = f"Расписание — {week_type}"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((IMG_W - tw) // 2, MARGIN), title, fill=COLOR_TITLE, font=FONT_TITLE)

    y = MARGIN + TITLE_H
    x0 = MARGIN
    col_x = {
        "num": x0,
        "subject": x0 + COL_W["num"],
        "teacher": x0 + COL_W["num"] + COL_W["subject"],
        "room": x0 + COL_W["num"] + COL_W["subject"] + COL_W["teacher"],
    }

    for day, rows in days_blocks:
        draw.rectangle([x0, y, x0 + TABLE_W, y + DAY_BANNER_H], fill=COLOR_DAY_BG)
        day_title = WEEKDAYS_RU[day].capitalize()
        dw = draw.textlength(day_title, font=FONT_DAY)
        draw.text((x0 + (TABLE_W - dw) // 2, y + 6), day_title, fill=COLOR_DAY_TEXT, font=FONT_DAY)
        y += DAY_BANNER_H

        draw.rectangle([x0, y, x0 + TABLE_W, y + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
        headers = [("№", "num"), ("Предмет", "subject"), ("Преподаватель", "teacher"), ("Кабинет", "room")]
        for label, key in headers:
            draw.text((col_x[key] + 6, y + 5), label, fill=COLOR_HEADER_TEXT, font=FONT_HEADER)
        y += HEADER_H

        for idx, (pair_num, lines_s, lines_t, lines_r, row_h) in enumerate(rows):
            bg = COLOR_ROW_EVEN if idx % 2 == 0 else COLOR_ROW_ODD
            draw.rectangle([x0, y, x0 + TABLE_W, y + row_h], fill=bg, outline=COLOR_GRID)
            draw.text((col_x["num"] + 10, y + (row_h - LINE_H) // 2), str(pair_num),
                       fill=COLOR_TEXT, font=FONT_CELL)
            _draw_lines_centered(draw, lines_s, FONT_CELL, col_x["subject"] + 6, y, row_h,
                                  COL_W["subject"] - 10, COLOR_TEXT)
            _draw_lines_centered(draw, lines_t, FONT_CELL, col_x["teacher"] + 6, y, row_h,
                                  COL_W["teacher"] - 10, COLOR_TEXT)
            _draw_lines_centered(draw, lines_r, FONT_CELL, col_x["room"] + 6, y, row_h,
                                  COL_W["room"] - 10, COLOR_TEXT)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _render_empty_image(title: str, message: str) -> bytes:
    img = Image.new("RGB", (IMG_W, 120), COLOR_BG)
    draw = ImageDraw.Draw(img)
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((IMG_W - tw) // 2, 20), title, fill=COLOR_TITLE, font=FONT_TITLE)
    mw = draw.textlength(message, font=FONT_CELL)
    draw.text(((IMG_W - mw) // 2, 60), message, fill=(120, 120, 120), font=FONT_CELL)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ==================== СРАВНЕНИЕ (Числитель vs Знаменатель) ====================
def _cmp_field(md, num_val: str, den_val: str, max_width: int):
    """Возвращает (equal, lines_num, lines_den, content_height)."""
    equal = (num_val or "") == (den_val or "")
    if equal:
        lines = _wrap_lines(md, num_val, FONT_CELL, max_width)
        return True, lines, lines, len(lines) * LINE_H
    lines_num = _wrap_lines(md, num_val, FONT_CELL, max_width) if num_val else [""]
    lines_den = _wrap_lines(md, den_val, FONT_CELL_ORANGE, max_width) if den_val else [""]
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

    if not days_blocks:
        return _render_empty_image("Расписание — Сравнение", "Нет данных для отображения")

    total_h = MARGIN + TITLE_H * 2
    for day, rows in days_blocks:
        total_h += DAY_BANNER_H + HEADER_H + sum(r["row_h"] for r in rows)
    total_h += MARGIN

    img = Image.new("RGB", (IMG_W, total_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    title = "Расписание — Сравнение"
    subtitle = "(различия по знаменателю — оранжевым)"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((IMG_W - tw) // 2, MARGIN), title, fill=COLOR_TITLE, font=FONT_TITLE)
    sw = draw.textlength(subtitle, font=FONT_CELL)
    draw.text(((IMG_W - sw) // 2, MARGIN + 22), subtitle, fill=COLOR_ORANGE, font=FONT_CELL)

    y = MARGIN + TITLE_H * 2
    x0 = MARGIN
    col_x = {
        "num": x0,
        "subject": x0 + COL_W["num"],
        "teacher": x0 + COL_W["num"] + COL_W["subject"],
        "room": x0 + COL_W["num"] + COL_W["subject"] + COL_W["teacher"],
    }

    def draw_field(col_key, eq, lines_num, lines_den, row_top, row_h):
        cx = col_x[col_key] + 6
        cw = COL_W[col_key] - 10
        if eq:
            _draw_lines_centered(draw, lines_num, FONT_CELL, cx, row_top, row_h, cw, COLOR_TEXT)
            return
        block_h = len(lines_num) * LINE_H + SPLIT_GAP + len(lines_den) * LINE_H
        y_start = row_top + max(0, (row_h - block_h) // 2)
        yy = y_start
        for line in lines_num:
            draw.text((cx, yy), line, fill=COLOR_TEXT, font=FONT_CELL)
            yy += LINE_H
        divider_y = yy + SPLIT_GAP // 2
        yy += SPLIT_GAP
        den_top = yy
        den_h = len(lines_den) * LINE_H
        # тонкая оранжевая рамка вокруг значения знаменателя
        draw.rectangle(
            [col_x[col_key] + 2, den_top - 2, col_x[col_key] + COL_W[col_key] - 2, den_top + den_h + 2],
            outline=COLOR_ORANGE, width=1,
        )
        for line in lines_den:
            draw.text((cx, yy), line, fill=COLOR_ORANGE, font=FONT_CELL_ORANGE)
            yy += LINE_H

    for day, rows in days_blocks:
        draw.rectangle([x0, y, x0 + TABLE_W, y + DAY_BANNER_H], fill=COLOR_DAY_BG)
        day_title = WEEKDAYS_RU[day].capitalize()
        dw = draw.textlength(day_title, font=FONT_DAY)
        draw.text((x0 + (TABLE_W - dw) // 2, y + 6), day_title, fill=COLOR_DAY_TEXT, font=FONT_DAY)
        y += DAY_BANNER_H

        draw.rectangle([x0, y, x0 + TABLE_W, y + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
        headers = [("№", "num"), ("Предмет", "subject"), ("Преподаватель", "teacher"), ("Кабинет", "room")]
        for label, key in headers:
            draw.text((col_x[key] + 6, y + 5), label, fill=COLOR_HEADER_TEXT, font=FONT_HEADER)
        y += HEADER_H

        for idx, row in enumerate(rows):
            row_h = row["row_h"]
            bg = COLOR_ROW_EVEN if idx % 2 == 0 else COLOR_ROW_ODD
            draw.rectangle([x0, y, x0 + TABLE_W, y + row_h], fill=bg, outline=COLOR_GRID)
            draw.text((col_x["num"] + 10, y + (row_h - LINE_H) // 2), str(row["pair_num"]),
                       fill=COLOR_TEXT, font=FONT_CELL)

            eq_s, ls_num, ls_den = row["subject"]
            eq_t, lt_num, lt_den = row["teacher"]
            eq_r, lr_num, lr_den = row["room"]
            draw_field("subject", eq_s, ls_num, ls_den, y, row_h)
            draw_field("teacher", eq_t, lt_num, lt_den, y, row_h)
            draw_field("room", eq_r, lr_num, lr_den, y, row_h)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
