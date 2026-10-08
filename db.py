"""
modules/db.py
Firebase Admin SDK 初始化 — Firebase Realtime Database 版本。
與 quiz apps 相同架構，使用 database_url 連接 RTDB。
private_key 自動修正 \\n 問題（Streamlit Cloud 相容）。
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

import streamlit as st

logger = logging.getLogger(__name__)
TAIWAN_TZ = ZoneInfo("Asia/Taipei")


@st.cache_resource
def _init_firebase():
    import firebase_admin
    from firebase_admin import credentials, db as rtdb

    if not firebase_admin._apps:
        try:
            sec = dict(st.secrets["firebase"])
            # 修正 Streamlit Cloud 的 \n 問題
            if "private_key" in sec:
                sec["private_key"] = sec["private_key"].replace("\\n", "\n")
            database_url = sec.pop("database_url", None)
            cred = credentials.Certificate(sec)
            opts = {"databaseURL": database_url} if database_url else {}
            firebase_admin.initialize_app(cred, opts)
            logger.info("Firebase RTDB 初始化成功，URL=%s", database_url)
        except Exception as e:
            logger.error("Firebase 初始化失敗: %s", e)
            raise RuntimeError(f"Firebase 初始化失敗：{e}") from e
    return rtdb


def rtdb():
    """回傳 firebase_admin.db 模組（已初始化）。"""
    return _init_firebase()


def ref(path: str):
    """取得 RTDB 參考的快捷函式。path 範例：'/users/uid123'"""
    return rtdb().reference(path)


# ── 時間工具 ───────────────────────────────────────────────────────────────────

def now_tw() -> datetime:
    return datetime.now(TAIWAN_TZ)


def parse_timestamp(value: Any) -> Optional[datetime]:
    """
    統一時間解析：
    1. 帶時區的 ISO 字串
    2. 無時區舊字串 → 視為台灣時間
    3. Python datetime（有/無時區）
    失敗回傳 None，不拋例外。
    """
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=TAIWAN_TZ)
            return value.astimezone(TAIWAN_TZ)
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TAIWAN_TZ)
            return dt.astimezone(TAIWAN_TZ)
    except Exception as e:
        logger.error("parse_timestamp 失敗: %r -> %s", value, e)
    return None


# ── RTDB 通用 helpers ──────────────────────────────────────────────────────────

def rtdb_get(path: str) -> Any:
    """讀取節點值，失敗回傳 None。"""
    try:
        return ref(path).get()
    except Exception as e:
        logger.error("rtdb_get %s 失敗: %s", path, e)
        return None


def rtdb_set(path: str, data: Any) -> bool:
    """覆寫節點，失敗回傳 False。"""
    try:
        ref(path).set(data)
        return True
    except Exception as e:
        logger.error("rtdb_set %s 失敗: %s", path, e)
        return False


def rtdb_update(path: str, data: dict) -> bool:
    """部分更新節點，失敗回傳 False。"""
    try:
        ref(path).update(data)
        return True
    except Exception as e:
        logger.error("rtdb_update %s 失敗: %s", path, e)
        return False


def rtdb_push(path: str, data: Any) -> Optional[str]:
    """push 子節點，回傳生成的 key，失敗回傳 None。"""
    try:
        result = ref(path).push(data)
        return result.key
    except Exception as e:
        logger.error("rtdb_push %s 失敗: %s", path, e)
        return None


def rtdb_delete(path: str) -> bool:
    """刪除節點，失敗回傳 False。"""
    try:
        ref(path).delete()
        return True
    except Exception as e:
        logger.error("rtdb_delete %s 失敗: %s", path, e)
        return False


def rtdb_transaction(path: str, update_fn) -> bool:
    """
    對節點執行 transaction（原子性讀-改-寫）。
    update_fn(current_value) -> new_value
    失敗回傳 False。
    """
    try:
        ref(path).transaction(update_fn)
        return True
    except Exception as e:
        logger.error("rtdb_transaction %s 失敗: %s", path, e)
        return False
