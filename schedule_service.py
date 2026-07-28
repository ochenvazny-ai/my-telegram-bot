import io
import textwrap
from PIL import Image, ImageDraw, ImageFont

import database as db
from config import WEEKDAYS_RU

CELL_W = 220
CELL_H = 100
HEADER_H = 50
LABEL_W = 70
MARGIN = 10

COLOR_BG = (255, 255, 255)
COLOR_GRID = (180, 180, 180)
COLOR_HEADER_BG = (230, 230, 230)
COLOR_TEXT = (20, 20, 20)
COLOR_DIFF = (230, 126, 34)  # оранжевый — для расхождений знаменателя


def _font(size=14):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _font_bold(size=15):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _cell_text(entry: dict | None) -> str:
    if not entry:
        return ""
    parts = [entry["subject"]]
    if entry.get("teacher"):
        parts.append(entry["teacher"])
    if entry.get("room"):
        parts.append(entry["room"])
    return "\n".join(parts)


def _wrap(text: str, width_chars: int = 22):
    lines = []
    for raw_line in text.split("\n"):
        lines.extend(textwrap.wrap(raw_line, width=width_chars) or [""])
    return lines


def _build_full_grid(week_type: str):
    """Возвращает (pairs_range, {day_idx: {pair_num: entry}})."""
    grid = {}
    all_pairs = set()
    for day in range(6):
        base = db.get_base_schedule(week_type, day)
        grid[day] = base
        all_pairs.update(base.keys())
    if not all_pairs:
        all_pairs = {0}
    pairs_range = list(range(min(all_pairs), max(all_pairs) + 1))
    return pairs_range, grid


def _draw_table(pairs_range, days, get_cell_fn, title: str) -> Image.Image:
    width = LABEL_W + CELL_W * len(days) + MARGIN * 2
    height = HEADER_H * 2 + CELL_H * len(pairs_range) + MARGIN * 2
    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)
    font = _font(13)
    font_bold = _font_bold(16)

    draw.text((MARGIN, MARGIN), title, fill=COLOR_TEXT, font=font_bold)

    top = MARGIN + HEADER_H
    # заголовки дней
    draw.rectangle([MARGIN, top, MARGIN + LABEL_W, top + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
    for i, day in enumerate(days):
        x0 = MARGIN + LABEL_W + i * CELL_W
        draw.rectangle([x0, top, x0 + CELL_W, top + HEADER_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
        draw.text((x0 + 10, top + 15), WEEKDAYS_RU[day].capitalize(), fill=COLOR_TEXT, font=font_bold)

    # строки пар
    for r, pair_num in enumerate(pairs_range):
        y0 = top + HEADER_H + r * CELL_H
        draw.rectangle([MARGIN, y0, MARGIN + LABEL_W, y0 + CELL_H], fill=COLOR_HEADER_BG, outline=COLOR_GRID)
        draw.text((MARGIN + 20, y0 + CELL_H // 2 - 8), str(pair_num), fill=COLOR_TEXT, font=font_bold)
        for c, day in enumerate(days):
            x0 = MARGIN + LABEL_W + c * CELL_W
            draw.rectangle([x0, y0, x0 + CELL_W, y0 + CELL_H], outline=COLOR_GRID)
            get_cell_fn(draw, x0, y0, day, pair_num, font)

    return img


def render_schedule_image(week_type: str) -> bytes:
    pairs_range, grid = _build_full_grid(week_type)
    days = list(range(6))

    def draw_cell(draw, x0, y0, day, pair_num, font):
        entry = grid[day].get(pair_num)
        text = _cell_text(entry)
        if not text:
            return
        lines = _wrap(text)
        for i, line in enumerate(lines[:5]):
            draw.text((x0 + 6, y0 + 6 + i * 16), line, fill=COLOR_TEXT, font=font)

    img = _draw_table(pairs_range, days, draw_cell, f"Расписание — {week_type}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def render_comparison_image() -> bytes:
    pairs_num, grid_num = _build_full_grid("Числитель")
    pairs_den, grid_den = _build_full_grid("Знаменатель")
    pairs_range = sorted(set(pairs_num) | set(pairs_den)) or [0]
    days = list(range(6))

    def entries_equal(a, b):
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return a["subject"] == b["subject"] and a["teacher"] == b["teacher"] and a["room"] == b["room"]

    def draw_cell(draw, x0, y0, day, pair_num, font):
        e_num = grid_num.get(day, {}).get(pair_num)
        e_den = grid_den.get(day, {}).get(pair_num)
        if e_num is None and e_den is None:
            return  # пустая пара — не выводим

        if entries_equal(e_num, e_den):
            text = _cell_text(e_num if e_num else e_den)
            lines = _wrap(text)
            for i, line in enumerate(lines[:5]):
                draw.text((x0 + 6, y0 + 6 + i * 16), line, fill=COLOR_TEXT, font=font)
            return

        # различаются — числитель сверху обычным цветом, знаменатель снизу оранжевым
        y_cursor = y0 + 4
        if e_num:
            for line in _wrap(_cell_text(e_num))[:2]:
                draw.text((x0 + 6, y_cursor), line, fill=COLOR_TEXT, font=font)
                y_cursor += 15
        y_cursor += 4
        if e_den:
            for line in _wrap(_cell_text(e_den))[:2]:
                draw.text((x0 + 6, y_cursor), line, fill=COLOR_DIFF, font=font)
                y_cursor += 15

    img = _draw_table(pairs_range, days, draw_cell, "Сравнение: Числитель / Знаменатель (расхождения — оранжевым)")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
