import io
import os
import logging
import textwrap
from PIL import Image, ImageDraw, ImageFont
import database as db
from config import WEEKDAYS_RU

logger = logging.getLogger(__name__)

# Цвета
COLOR_BG = (255, 255, 255)
COLOR_HEADER_BG = (230, 230, 230)
COLOR_GRID = (180, 180, 180)
COLOR_TEXT = (20, 20, 20)
COLOR_HEADER_TEXT = (0, 0, 0)

# Размеры колонок
COL_NUM_W = 60
COL_SUBJECT_W = 280
COL_TEACHER_W = 220
COL_ROOM_W = 120

ROW_HEIGHT = 80
HEADER_HEIGHT = 40
MARGIN = 10

def _find_font_path(bold: bool = False) -> str | None:
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        import matplotlib
        candidate = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", filename)
        if os.path.isfile(candidate):
            return candidate
    except Exception:
        pass
    
    system_candidates = [
        f"/usr/share/fonts/truetype/dejavu/{filename}",
        f"/usr/share/fonts/dejavu/{filename}",
    ]
    for path in system_candidates:
        if os.path.isfile(path):
            return path
    return None

_FONT_CACHE = {}

def _load_font(size: int, bold: bool = False):
    cache_key = (size, bold)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    
    path = _find_font_path(bold=bold)
    if path:
        try:
            font = ImageFont.truetype(path, size)
            _FONT_CACHE[cache_key] = font
            return font
        except Exception:
            pass
    
    font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font

def _font(size=14):
    return _load_font(size, bold=False)

def _font_bold(size=15):
    return _load_font(size, bold=True)

def render_schedule_image(week_type: str) -> bytes:
    """Генерирует изображение расписания в формате: дни как строки, 4 колонки"""
    
    # Получаем данные из БД
    schedule_data = {}
    max_pairs = 0
    for day_idx in range(6):
        pairs = db.get_base_schedule(week_type, day_idx)
        schedule_data[day_idx] = pairs
        if pairs:
            max_pairs = max(max_pairs, max(pairs.keys()) + 1)
    
    if max_pairs == 0:
        max_pairs = 4  # минимум 4 пары
    
    # Размеры изображения
    total_width = COL_NUM_W + COL_SUBJECT_W + COL_TEACHER_W + COL_ROOM_W + MARGIN * 2
    total_height = MARGIN + HEADER_HEIGHT + 6 * (ROW_HEIGHT * max_pairs + HEADER_HEIGHT) + MARGIN
    
    img = Image.new('RGB', (total_width, total_height), COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    font_header = _font_bold(16)
    font_cell = _font(13)
    font_pair_num = _font_bold(14)
    
    # Заголовок
    title = f"Расписание — {week_type}"
    draw.text((MARGIN, MARGIN), title, fill=COLOR_HEADER_TEXT, font=font_header)
    
    y = MARGIN + HEADER_HEIGHT
    
    # Рисуем каждый день
    for day_idx in range(6):
        day_name = WEEKDAYS_RU[day_idx].capitalize()
        
        # Заголовок дня
        draw.rectangle(
            [MARGIN, y, total_width - MARGIN, y + HEADER_HEIGHT],
            fill=COLOR_HEADER_BG,
            outline=COLOR_GRID
        )
        draw.text((MARGIN + 10, y + 10), day_name, fill=COLOR_HEADER_TEXT, font=font_header)
        y += HEADER_HEIGHT
        
        # Получаем пары для этого дня
        pairs = schedule_data.get(day_idx, {})
        
        # Рисуем строки с парами
        for pair_num in range(max_pairs):
            # Номер пары
            draw.rectangle(
                [MARGIN, y, MARGIN + COL_NUM_W, y + ROW_HEIGHT],
                outline=COLOR_GRID
            )
            if pair_num in pairs:
                draw.text(
                    (MARGIN + 20, y + 30),
                    str(pair_num),
                    fill=COLOR_TEXT,
                    font=font_pair_num
                )
            
            # Дисциплина
            x_subject = MARGIN + COL_NUM_W
            draw.rectangle(
                [x_subject, y, x_subject + COL_SUBJECT_W, y + ROW_HEIGHT],
                outline=COLOR_GRID
            )
            
            # Преподаватель
            x_teacher = x_subject + COL_SUBJECT_W
            draw.rectangle(
                [x_teacher, y, x_teacher + COL_TEACHER_W, y + ROW_HEIGHT],
                outline=COLOR_GRID
            )
            
            # Кабинет
            x_room = x_teacher + COL_TEACHER_W
            draw.rectangle(
                [x_room, y, x_room + COL_ROOM_W, y + ROW_HEIGHT],
                outline=COLOR_GRID
            )
            
            # Заполняем данные если пара есть
            if pair_num in pairs:
                info = pairs[pair_num]
                
                # Предмет
                subject_text = info.get('subject', '')
                lines = textwrap.wrap(subject_text, width=35)
                for i, line in enumerate(lines[:3]):
                    draw.text(
                        (x_subject + 5, y + 5 + i * 18),
                        line,
                        fill=COLOR_TEXT,
                        font=font_cell
                    )
                
                # Преподаватель
                teacher_text = info.get('teacher', '')
                lines = textwrap.wrap(teacher_text, width=25)
                for i, line in enumerate(lines[:3]):
                    draw.text(
                        (x_teacher + 5, y + 5 + i * 18),
                        line,
                        fill=COLOR_TEXT,
                        font=font_cell
                    )
                
                # Кабинет
                room_text = info.get('room', '')
                draw.text(
                    (x_room + 5, y + 30),
                    room_text,
                    fill=COLOR_TEXT,
                    font=font_cell
                )
            
            y += ROW_HEIGHT
        
        y += 10  # отступ между днями
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def render_comparison_image() -> bytes:
    """Для сравнения используем числитель"""
    return render_schedule_image("Числитель")
