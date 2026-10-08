"""
modules/audit.py
稽核紀錄（操作紀錄 + 錯誤紀錄）— RTDB 版本。

RTDB 路徑：
  /audit_logs/{push_key}/    操作紀錄
  /error_logs/{push_key}/    錯誤紀錄
"""
import logging
import traceback
from typing import Optional
from modules.db import rtdb_push, rtdb_get, now_tw

logger = logging.getLogger(__name__)


# ── 操作紀錄 ───────────────────────────────────────────────────────────────────

def log_action(
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    detail: Optional[dict] = None,
) -> None:
    """
    寫入操作紀錄。
    包含：發生時間、操作人員、操作類型、資料異動內容。
    不得包含密碼、雜湊、金鑰。
    """
    try:
        record = {
            "actor_id": actor_id,
            "action": action,
            "action_label": _action_label(action),
            "target_type": target_type,
            "target_id": target_id,
            "result": result,
            "timestamp": now_tw().isoformat(),
        }
        if detail:
            safe_detail = {
                k: v for k, v in detail.items()
                if k not in {"password", "password_hash", "token", "secret", "key"}
            }
            record["detail"] = safe_detail
        rtdb_push("/audit_logs", record)
    except Exception as e:
        logger.error("log_action 寫入失敗: %s", e)


def _action_label(action: str) -> str:
    """將操作代碼轉為中文說明。"""
    labels = {
        "create_user": "新增會員",
        "delete_user": "刪除會員",
        "disable_user": "停用會員",
        "enable_user": "啟用會員",
        "reset_password": "重設密碼",
        "change_password": "修改密碼",
        "unlock_user": "解除鎖定",
        "update_user": "修改會員資料",
        "update_role_permissions": "修改角色權限",
        "login": "登入",
        "logout": "登出",
        "create_item": "新增誦經項目",
        "update_item": "修改誦經項目",
        "archive_item": "封存誦經項目",
        "unarchive_item": "取消封存",
        "add_count": "計數",
        "undo_count": "撤銷計數",
    }
    return labels.get(action, action)


# ── 錯誤紀錄 ───────────────────────────────────────────────────────────────────

def log_error(
    error_type: str,
    message: str,
    user_id: Optional[str] = None,
    exc: Optional[Exception] = None,
) -> None:
    """
    寫入錯誤紀錄。
    包含：發生時間、錯誤類型、使用者、錯誤訊息、詳細堆疊。
    """
    try:
        record = {
            "error_type": error_type,
            "message": message,
            "user_id": user_id or "system",
            "timestamp": now_tw().isoformat(),
        }
        if exc:
            record["traceback"] = traceback.format_exc()
        rtdb_push("/error_logs", record)
    except Exception as e:
        logger.error("log_error 寫入失敗: %s", e)


# ── 查詢 ───────────────────────────────────────────────────────────────────────

def get_audit_logs(limit: int = 50, action_filter: str = "") -> list:
    """取得操作紀錄，依時間倒序。"""
    try:
        data = rtdb_get("/audit_logs") or {}
        logs = list(data.values())
        if action_filter:
            logs = [l for l in logs if l.get("action") == action_filter]
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]
    except Exception as e:
        logger.error("get_audit_logs 失敗: %s", e)
        return []


def get_error_logs(limit: int = 50, error_type_filter: str = "") -> list:
    """取得錯誤紀錄，依時間倒序。"""
    try:
        data = rtdb_get("/error_logs") or {}
        logs = list(data.values())
        if error_type_filter:
            logs = [l for l in logs if l.get("error_type") == error_type_filter]
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]
    except Exception as e:
        logger.error("get_error_logs 失敗: %s", e)
        return []
