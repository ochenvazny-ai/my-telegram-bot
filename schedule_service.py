import re
import logging
import asyncio
from datetime import datetime, date as date_cls, timedelta
import requests
from bs4 import BeautifulSoup

import database as db
from config import (
    GROUP_NAME, WEEKDAYS_RU, MONTHS_RU, MONTHS_RU_TO_NUM, NUMBER_EMOJIS, get_site_url,
)

logger = logging.getLogger(__name__)


def format_date_russian(d: date_cls) -> str:
    return f"{d.day} {MONTHS_RU[d.month]} {d.year}"


def expand_pair_numbers(pair_str: str):
    pair_str = pair_str.strip()
    if ',' in pair_str:
        result = []
        for p in pair_str.split(','):
            p = p.strip()
            if '-' in p:
                start, end = map(int, p.split('-'))
                result.extend(str(i) for i in range(start, end + 1))
            else:
                result.append(p)
        return result
    elif '-' in pair_str:
        start, end = map(int, pair_str.split('-'))
        return [str(i) for i in range(start, end + 1)]
    return [pair_str]


def extract_metadata_from_html(html_text: str):
    soup = BeautifulSoup(html_text, 'lxml')
    header_text = soup.get_text()
    date_match = re.search(r'(\d+)\s+([а-я]+)\s+(\d{4})\s+года', header_text)
    if not date_match:
        return None, None
    day = int(date_match.group(1))
    month = MONTHS_RU_TO_NUM.get(date_match.group(2).lower(), 1)
    year = int(date_match.group(3))
    try:
        file_date = datetime(year, month, day).date()
    except ValueError:
        file_date = None
    type_match = re.search(r'\((Числитель|Знаменатель)\)', header_text)
    week_type = type_match.group(1) if type_match else None
    return file_date, week_type


def parse_replacements_from_html(html_text: str, group_name: str = None):
    """group_name по умолчанию берётся из БД (db.get_group_name),
    fallback на GROUP_NAME из config.py."""
    if group_name is None:
        try:
            group_name = db.get_group_name()
        except Exception:
            group_name = GROUP_NAME

    soup = BeautifulSoup(html_text, 'lxml')
    table = soup.find('table')
    if not table:
        return []
    results = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 6:
            continue
        if cells[1].get_text(strip=True) != group_name:
            continue
        pair_numbers_str = cells[2].get_text(strip=True)
        if not pair_numbers_str:
            continue
        replacement_full = cells[4].get_text(strip=True)
        room = cells[5].get_text(strip=True)
        pair_list = expand_pair_numbers(pair_numbers_str)
        repl = replacement_full.strip()
        if repl in ("", "—") or repl.lower() == "по расписанию":
            if room and room != "?":
                for p in pair_list:
                    results.append({"pair": p, "type": "dist", "room": room})
            continue
        if repl.lower() == "снято":
            for p in pair_list:
                results.append({"pair": p, "type": "remove"})
            continue
        for p in pair_list:
            results.append({"pair": p, "type": "replace", "replacement": replacement_full, "room": room})
    return results


def build_final_entries(week_type: str, day_of_week: int, replacements: list[dict]) -> list[dict]:
    base = db.get_base_schedule(week_type, day_of_week)
    repl_dict = {}
    for r in replacements:
        pair = r['pair']
        if r['type'] == 'remove':
            repl_dict[pair] = ('remove',)
        elif r['type'] == 'replace':
            repl_dict[pair] = ('replace', r['replacement'], r['room'])
        elif r['type'] == 'dist':
            repl_dict[pair] = ('dist', r['room'])

    all_pairs = set(str(k) for k in base.keys())
    for pair_num, info in repl_dict.items():
        if info[0] != 'remove':
            all_pairs.add(pair_num)

    result = []
    for pair_str in sorted(all_pairs, key=lambda x: int(x)):
        pair_int = int(pair_str)
        base_info = base.get(pair_int, {"subject": "Занятие", "teacher": "", "room": "?"})

        if pair_str in repl_dict:
            info = repl_dict[pair_str]
            if info[0] == 'remove':
                continue
            elif info[0] == 'replace':
                _, replacement_text, room = info
                result.append({
                    "pair_num": pair_str, "subject": replacement_text, "teacher": "", "room": room,
                    "is_replaced": True,
                    "original_subject": base_info["subject"],
                    "original_teacher": base_info["teacher"],
                    "original_room": base_info["room"],
                })
            elif info[0] == 'dist':
                _, room = info
                result.append({
                    "pair_num": pair_str, "subject": base_info["subject"], "teacher": base_info["teacher"],
                    "room": room, "is_replaced": False,
                    "original_subject": base_info["subject"],
                    "original_teacher": base_info["teacher"],
                    "original_room": base_info["room"],
                })
        else:
            result.append({
                "pair_num": pair_str, "subject": base_info["subject"], "teacher": base_info["teacher"],
                "room": base_info["room"], "is_replaced": False,
                "original_subject": base_info["subject"],
                "original_teacher": base_info["teacher"],
                "original_room": base_info["room"],
            })
    return result


def format_schedule_message(target_date: date_cls, week_type: str, entries: list[dict], site_url: str,
                             note: str = "", replacement_notes: list[str] | None = None) -> str:
    weekday_name = WEEKDAYS_RU[target_date.weekday()]
    text = f"✨ РАСПИСАНИЕ ЗАНЯТИЙ НА {format_date_russian(target_date)} ({week_type}) ✨\n"
    text += f"({weekday_name})\n"
    if note:
        text += f"\n⚠️ {note}\n"
    text += "\n"
    if not entries:
        text += "Пар не найдено.\n"
    for e in entries:
        try:
            idx = int(e["pair_num"])
            emoji = NUMBER_EMOJIS[idx] if 0 <= idx <= 9 else f"{idx}️⃣"
        except (ValueError, TypeError):
            emoji = "🔹"
        teacher_part = f" ({e['teacher']})" if e.get("teacher") else ""
        replaced_tag = " [ЗАМЕНА]" if e.get("is_replaced") else ""
        text += f"🔹 {emoji} {e['subject']}{teacher_part}{replaced_tag} | {e.get('room', '?')}\n"
    text += f"\n🔗 <a href='{site_url}'>Проверить замены на сайте</a>"
    if replacement_notes:
        text += "\n\n📝 " + "\n📝 ".join(replacement_notes)
    return text


async def _fetch_site_html(site_url: str) -> str | None:
    try:
        response = await asyncio.to_thread(requests.get, site_url, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code != 200:
            return None
        return response.text
    except Exception:
        logger.exception("Не удалось загрузить сайт с заменами")
        return None


def _pre_holiday_note(file_date: date_cls, today: date_cls) -> str | None:
    mmdd = file_date.strftime("%m-%d")
    if not db.is_pre_holiday_today(mmdd):
        return None
    if file_date == today:
        return "Сегодня пары по часу!"
    if file_date == today + timedelta(days=1):
        return "Завтра пары по часу!"
    return None


async def get_schedule_for_display() -> tuple[str, bool]:
    shift = await asyncio.to_thread(db.get_current_shift)
    site_url = get_site_url(shift)

    html_text = await _fetch_site_html(site_url)
    if not html_text:
        return "Не удалось загрузить страницу с заменами. Попробуйте позже.", False

    file_date, week_type = extract_metadata_from_html(html_text)
    if not file_date or not week_type:
        return "Не удалось определить дату или тип недели на сайте.", False

    weekday_name = WEEKDAYS_RU[file_date.weekday()]
    if weekday_name == "воскресенье":
        return f"📅 {format_date_russian(file_date)} — воскресенье, пар нет.", True

    today = datetime.now().date()
    day_diff = (file_date - today).days

    ph_note = await asyncio.to_thread(_pre_holiday_note, file_date, today)
    repl_notes = await asyncio.to_thread(db.get_active_replacement_notes)

    cached = await asyncio.to_thread(db.get_cached_schedule, file_date)
    if cached:
        entries = [{
            "pair_num": row["pair_num"], "subject": row["subject"], "teacher": row.get("teacher", ""),
            "room": row.get("room", ""), "is_replaced": row.get("is_replaced", False),
        } for row in cached]
        return format_schedule_message(file_date, week_type, entries, site_url,
                                        note=ph_note or "", replacement_notes=repl_notes), True

    day_of_week = file_date.weekday()

    if day_diff <= 1:
        replacements = parse_replacements_from_html(html_text)
        entries = await asyncio.to_thread(build_final_entries, week_type, day_of_week, replacements)
        await asyncio.to_thread(db.save_schedule_cache, file_date, week_type, weekday_name, entries)
        return format_schedule_message(file_date, week_type, entries, site_url,
                                        note=ph_note or "", replacement_notes=repl_notes), True
    elif day_diff < 0:
        base = await asyncio.to_thread(db.get_base_schedule, week_type, day_of_week)
        entries = [{"pair_num": str(p), "subject": v["subject"], "teacher": v["teacher"],
                    "room": v["room"], "is_replaced": False} for p, v in sorted(base.items())]
        note = "Это прошедшая дата, замены на неё не сохранялись."
        return format_schedule_message(file_date, week_type, entries, site_url, note=note,
                                        replacement_notes=repl_notes), True
    else:
        base = await asyncio.to_thread(db.get_base_schedule, week_type, day_of_week)
        entries = [{"pair_num": str(p), "subject": v["subject"], "teacher": v["teacher"],
                    "room": v["room"], "is_replaced": False} for p, v in sorted(base.items())]
        note = "Замены на эту дату ещё не известны." + (f" {ph_note}" if ph_note else "")
        return format_schedule_message(file_date, week_type, entries, site_url, note=note,
                                        replacement_notes=repl_notes), True