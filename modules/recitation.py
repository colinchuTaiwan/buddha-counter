"""
modules/recitation.py
誦經項目 CRUD — Firebase Realtime Database 版本。

RTDB 路徑：/recitation_items/{user_id}/{item_id}/...
"""
import logging
import uuid
from typing import List, Optional, Tuple

from modules.db import rtdb_get, rtdb_set, rtdb_update, now_tw

logger = logging.getLogger(__name__)

MAX_NAME_LEN = 30
MAX_NOTE_LEN = 100


def validate_item_name(name: str) -> Tuple[bool, str]:
    stripped = name.strip()
    if not stripped:
        return False, "項目名稱不得為空。"
    if len(stripped) > MAX_NAME_LEN:
        return False, f"項目名稱不得超過 {MAX_NAME_LEN} 個字元（目前 {len(stripped)} 個）。"
    return True, ""


def _check_name_duplicate(user_id: str, name: str,
                           exclude_item_id: Optional[str] = None) -> bool:
    normalized = name.strip().lower()
    items = rtdb_get(f"/recitation_items/{user_id}") or {}
    for item_id, item in items.items():
        if exclude_item_id and item_id == exclude_item_id:
            continue
        if item.get("name", "").strip().lower() == normalized:
            return True
    return False


def get_user_items(user_id: str, include_archived: bool = False) -> List[dict]:
    items_data = rtdb_get(f"/recitation_items/{user_id}") or {}
    result = []
    for item_id, item in items_data.items():
        if not include_archived and item.get("is_archived", False):
            continue
        item["id"] = item_id
        result.append(item)
    result.sort(key=lambda x: x.get("created_at", ""))
    return result


def get_item(user_id: str, item_id: str) -> Optional[dict]:
    data = rtdb_get(f"/recitation_items/{user_id}/{item_id}")
    if not data:
        return None
    data["id"] = item_id
    return data


def create_item(user_id: str, name: str, note: str = "") -> Tuple[bool, str, Optional[str]]:
    ok, msg = validate_item_name(name)
    if not ok:
        return False, msg, None
    if note and len(note.strip()) > MAX_NOTE_LEN:
        return False, f"備註不得超過 {MAX_NOTE_LEN} 個字元。", None
    if _check_name_duplicate(user_id, name):
        return False, "您已有相同名稱的誦經項目，請使用不同名稱。", None

    item_id = str(uuid.uuid4())
    now = now_tw().isoformat()
    ok = rtdb_set(f"/recitation_items/{user_id}/{item_id}", {
        "name": name.strip(),
        "note": note.strip(),
        "is_archived": False,
        "created_at": now,
        "updated_at": now,
    })
    return (True, "", item_id) if ok else (False, "建立項目失敗，請稍後再試。", None)


def update_item(user_id: str, item_id: str, name: str, note: str = "") -> Tuple[bool, str]:
    if not get_item(user_id, item_id):
        return False, "找不到此項目。"
    ok, msg = validate_item_name(name)
    if not ok:
        return False, msg
    if note and len(note.strip()) > MAX_NOTE_LEN:
        return False, f"備註不得超過 {MAX_NOTE_LEN} 個字元。"
    if _check_name_duplicate(user_id, name, exclude_item_id=item_id):
        return False, "您已有相同名稱的誦經項目，請使用不同名稱。"
    ok = rtdb_update(f"/recitation_items/{user_id}/{item_id}", {
        "name": name.strip(), "note": note.strip(), "updated_at": now_tw().isoformat(),
    })
    return (True, "") if ok else (False, "更新失敗，請稍後再試。")


def archive_item(user_id: str, item_id: str, archive: bool = True) -> Tuple[bool, str]:
    if not get_item(user_id, item_id):
        return False, "找不到此項目。"
    ok = rtdb_update(f"/recitation_items/{user_id}/{item_id}", {
        "is_archived": archive, "updated_at": now_tw().isoformat(),
    })
    action = "封存" if archive else "取消封存"
    return (True, "") if ok else (False, f"{action}失敗，請稍後再試。")
