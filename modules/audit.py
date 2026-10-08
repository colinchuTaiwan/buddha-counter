"""
modules/audit.py
稽核紀錄 — Firebase Realtime Database 版本。

RTDB 路徑：/audit_logs/{push_key}/...
"""
import logging
from typing import Optional

from modules.db import rtdb_push, rtdb_get, now_tw

logger = logging.getLogger(__name__)


def log_action(actor_id: str, action: str, target_type: str,
               target_id: str, result: str, detail: Optional[dict] = None) -> None:
    try:
        record = {
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "result": result,
            "timestamp": now_tw().isoformat(),
        }
        if detail:
            safe_detail = {k: v for k, v in detail.items()
                           if k not in {"password", "password_hash", "token", "secret", "key"}}
            record["detail"] = safe_detail
        rtdb_push("/audit_logs", record)
    except Exception as e:
        logger.error("log_action 失敗: %s", e)


def get_audit_logs(limit: int = 50) -> list:
    try:
        data = rtdb_get("/audit_logs") or {}
        logs = list(data.values())
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]
    except Exception as e:
        logger.error("get_audit_logs 失敗: %s", e)
        return []
