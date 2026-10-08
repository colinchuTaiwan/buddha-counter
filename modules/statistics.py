"""
modules/statistics.py
統計與日期區間工具 — Firebase Realtime Database 版本。

RTDB 路徑：/daily_stats/{user_id}/{item_id}/{date_str}  → net_count (int)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from modules.db import rtdb_get, rtdb_set, rtdb_transaction, now_tw, TAIWAN_TZ

logger = logging.getLogger(__name__)


# ── 日期區間 ───────────────────────────────────────────────────────────────────

def get_today_range() -> Tuple[datetime, datetime]:
    now = now_tw()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def get_week_range() -> Tuple[datetime, datetime]:
    now = now_tw()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=7)


def get_month_range() -> Tuple[datetime, datetime]:
    now = now_tw()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1, day=1)
    else:
        end = start.replace(month=now.month + 1, day=1)
    return start, end


def get_custom_range(start_date, end_date) -> Tuple[datetime, datetime]:
    start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=TAIWAN_TZ)
    end = datetime(end_date.year, end_date.month, end_date.day, 0, 0, 0, tzinfo=TAIWAN_TZ) + timedelta(days=1)
    return start, end


def format_range_label(start: datetime, end: datetime) -> str:
    s = start.strftime("%Y/%m/%d")
    e = (end - timedelta(seconds=1)).strftime("%Y/%m/%d")
    return f"{s} ～ {e}"


def _date_in_range(date_str: str, start: datetime, end: datetime) -> bool:
    try:
        day_dt = datetime.fromisoformat(f"{date_str}T00:00:00").replace(tzinfo=TAIWAN_TZ)
        return start <= day_dt < end
    except Exception:
        return False


# ── 統計查詢 ───────────────────────────────────────────────────────────────────

def get_item_stats(user_id: str, item_id: str) -> Dict[str, int]:
    today_s, today_e = get_today_range()
    week_s, week_e = get_week_range()
    month_s, month_e = get_month_range()

    try:
        dates = rtdb_get(f"/daily_stats/{user_id}/{item_id}") or {}
        today = week = month = total = 0
        for date_str, count in dates.items():
            n = int(count or 0)
            total += n
            if _date_in_range(date_str, today_s, today_e): today += n
            if _date_in_range(date_str, week_s, week_e):   week += n
            if _date_in_range(date_str, month_s, month_e): month += n
        return {"today": today, "week": week, "month": month, "total": total}
    except Exception as e:
        logger.error("get_item_stats: %s", e)
        return {"today": 0, "week": 0, "month": 0, "total": 0}


def get_all_items_stats(user_id: str) -> Dict[str, Dict[str, int]]:
    today_s, today_e = get_today_range()
    week_s, week_e = get_week_range()
    month_s, month_e = get_month_range()

    try:
        all_items = rtdb_get(f"/daily_stats/{user_id}") or {}
        result = {}
        for item_id, dates in all_items.items():
            today = week = month = total = 0
            for date_str, count in (dates or {}).items():
                n = int(count or 0)
                total += n
                if _date_in_range(date_str, today_s, today_e): today += n
                if _date_in_range(date_str, week_s, week_e):   week += n
                if _date_in_range(date_str, month_s, month_e): month += n
            result[item_id] = {"today": today, "week": week, "month": month, "total": total}
        return result
    except Exception as e:
        logger.error("get_all_items_stats: %s", e)
        return {}


def get_daily_records(user_id: str, item_id: Optional[str],
                      start: datetime, end: datetime) -> List[dict]:
    try:
        if item_id:
            items_data = {item_id: rtdb_get(f"/daily_stats/{user_id}/{item_id}") or {}}
        else:
            items_data = rtdb_get(f"/daily_stats/{user_id}") or {}

        records = []
        for iid, dates in items_data.items():
            for date_str, count in (dates or {}).items():
                if _date_in_range(date_str, start, end):
                    records.append({"item_id": iid, "date_str": date_str, "net_count": int(count or 0)})
        records.sort(key=lambda x: x["date_str"])
        return records
    except Exception as e:
        logger.error("get_daily_records: %s", e)
        return []


def update_daily_stats_atomic(user_id: str, item_id: str, date_str: str, delta: int) -> bool:
    """
    原子性更新每日彙總（RTDB transaction）。
    確保多裝置同時計數不遺失。
    """
    path = f"/daily_stats/{user_id}/{item_id}/{date_str}"

    def _update(current):
        return max(0, (current or 0) + delta)

    return rtdb_transaction(path, _update)
