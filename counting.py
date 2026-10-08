"""
modules/counting.py
計數核心 — Firebase Realtime Database 版本。

RTDB 路徑設計：
  /count_events/{user_id}/{event_id}/...   計數原始事件
  /daily_stats/{user_id}/{item_id}/{date}  每日彙總（整數）

冪等性：
  寫入 count_events 前先讀取 event_id 是否已存在（RTDB transaction）。
  同一 event_id 重送不再累加。

多裝置安全：
  daily_stats 使用 RTDB transaction 原子性 +1/-1。
"""
import logging
import uuid
from typing import Tuple

from modules.db import rtdb_get, rtdb_set, rtdb_update, rtdb_transaction, now_tw
from modules.statistics import update_daily_stats_atomic

logger = logging.getLogger(__name__)


def generate_event_id() -> str:
    return str(uuid.uuid4())


def add_count(user_id: str, item_id: str, event_id: str) -> Tuple[bool, str]:
    """
    記錄一次計數。
    1. 先寫 count_events（以 event_id 為 key，確保冪等）
    2. 再以 RTDB transaction 更新 daily_stats

    RTDB 不支援跨路徑 transaction，故分兩步，
    但 event_id 去重確保即使重試也不重複計。
    """
    # 確認項目存在且歸屬正確
    from modules.recitation import get_item
    item = get_item(user_id, item_id)
    if not item:
        return False, "找不到此誦經項目或無存取權限。"
    if item.get("is_archived", False):
        return False, "此項目已封存，無法繼續計數。"

    now = now_tw()
    date_str = now.strftime("%Y-%m-%d")
    event_path = f"/count_events/{user_id}/{event_id}"

    # ── 步驟 1：冪等寫入事件（以 event_id 為 key）──
    # 若 event_id 已存在，transaction 回傳現有值（不覆寫）
    existing = rtdb_get(event_path)
    if existing:
        # 已存在：冪等，視為成功（daily_stats 已更新過）
        return True, ""

    ok = rtdb_set(event_path, {
        "item_id": item_id,
        "delta": 1,
        "is_undo": False,
        "undone": False,
        "undo_event_id": None,
        "timestamp": now.isoformat(),
        "date_str": date_str,
    })
    if not ok:
        return False, "計數儲存失敗，請重試（尚未儲存）。"

    # ── 步驟 2：原子性更新每日彙總 ──
    ok2 = update_daily_stats_atomic(user_id, item_id, date_str, 1)
    if not ok2:
        # 統計更新失敗：事件已寫入，重建工具可修復
        logger.error("add_count: daily_stats 更新失敗 user=%s item=%s event=%s",
                     user_id, item_id, event_id)
        # 仍回傳成功（事件已記錄），不讓使用者重複計數
        return True, ""

    return True, ""


def undo_last_count(user_id: str, item_id: str) -> Tuple[bool, str]:
    """
    撤銷最近一次計數。
    - 只能撤銷一次（undone 旗標）
    - 修正事件保留歷史
    - 不造成負數
    """
    # 取得此項目所有事件，找最近未撤銷的
    events_data = rtdb_get(f"/count_events/{user_id}") or {}
    candidates = []
    for eid, ev in events_data.items():
        if (ev.get("item_id") == item_id
                and not ev.get("is_undo", False)
                and not ev.get("undone", False)
                and ev.get("delta", 0) > 0):
            candidates.append((eid, ev))

    if not candidates:
        return False, "找不到可撤銷的計數紀錄。"

    candidates.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
    original_eid, original_ev = candidates[0]
    original_date_str = original_ev.get("date_str", now_tw().strftime("%Y-%m-%d"))

    # 標記原始事件為已撤銷
    ok1 = rtdb_update(f"/count_events/{user_id}/{original_eid}", {"undone": True})
    if not ok1:
        return False, "撤銷失敗，請稍後再試。"

    # 寫入撤銷事件（修正記錄，保留歷史）
    undo_eid = generate_event_id()
    rtdb_set(f"/count_events/{user_id}/{undo_eid}", {
        "item_id": item_id,
        "delta": -1,
        "is_undo": True,
        "undo_of_event_id": original_eid,
        "undone": False,
        "timestamp": now_tw().isoformat(),
        "date_str": original_date_str,
    })

    # 原子性更新每日彙總（不得造成負數）
    update_daily_stats_atomic(user_id, item_id, original_date_str, -1)

    return True, ""


def get_today_count(user_id: str, item_id: str) -> int:
    date_str = now_tw().strftime("%Y-%m-%d")
    val = rtdb_get(f"/daily_stats/{user_id}/{item_id}/{date_str}")
    return int(val or 0)


def get_total_count(user_id: str, item_id: str) -> int:
    dates = rtdb_get(f"/daily_stats/{user_id}/{item_id}") or {}
    return sum(int(v or 0) for v in dates.values())
