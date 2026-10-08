"""
modules/auth.py
帳號驗證、Argon2id 雜湊、登入鎖定、工作階段管理。
使用 Firebase Realtime Database。

RTDB 路徑設計：
  /users/{user_id}/...          會員資料
  /username_index/{username}    帳號 → user_id 反查索引
"""
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from modules.db import (
    now_tw, parse_timestamp,
    rtdb_get, rtdb_set, rtdb_update, rtdb_transaction, ref,
    TAIWAN_TZ,
)

logger = logging.getLogger(__name__)

MAX_FAILED = 3
LOCKOUT_MINUTES = 15
SESSION_IDLE_MINUTES = 30
TEMP_PWD_LENGTH = 10
MIN_PWD_LENGTH = 10

ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2,
                    hash_len=32, salt_len=16)


# ── 密碼工具 ───────────────────────────────────────────────────────────────────

def validate_password_complexity(password: str) -> Tuple[bool, str]:
    if len(password) < MIN_PWD_LENGTH:
        return False, f"密碼至少需要 {MIN_PWD_LENGTH} 個字元。"
    if not any(c.isupper() for c in password):
        return False, "密碼必須包含至少一個大寫英文字母。"
    if not any(c.islower() for c in password):
        return False, "密碼必須包含至少一個小寫英文字母。"
    if not any(c.isdigit() for c in password):
        return False, "密碼必須包含至少一個數字。"
    return True, ""


def generate_temp_password() -> str:
    """secrets 模組產生恰好 10 碼，含大小寫英文及數字。"""
    alpha = string.ascii_letters + string.digits
    while True:
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
        ]
        for _ in range(TEMP_PWD_LENGTH - 3):
            pwd.append(secrets.choice(alpha))
        secrets.SystemRandom().shuffle(pwd)
        result = "".join(pwd)
        if len(result) == TEMP_PWD_LENGTH:
            return result


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def normalize_username(username: str) -> str:
    return username.strip().lower()


# ── RTDB 使用者路徑 ────────────────────────────────────────────────────────────

def _user_path(user_id: str) -> str:
    return f"/users/{user_id}"


def _username_index_path(username: str) -> str:
    return f"/username_index/{username}"


def get_user_by_username(username: str) -> Tuple[Optional[str], Optional[dict]]:
    """從 username_index 查 user_id，再讀使用者資料。回傳 (user_id, user_dict)。"""
    normalized = normalize_username(username)
    user_id = rtdb_get(_username_index_path(normalized))
    if not user_id:
        return None, None
    user_data = rtdb_get(_user_path(user_id))
    return (user_id, user_data) if user_data else (None, None)


def get_user(user_id: str) -> Optional[dict]:
    return rtdb_get(_user_path(user_id))


# ── 鎖定狀態 ───────────────────────────────────────────────────────────────────

def _get_lockout_info(user_data: dict) -> Tuple[bool, Optional[datetime], int]:
    failed = user_data.get("failed_login_count", 0)
    lockout_until_raw = user_data.get("lockout_until")
    lockout_until = parse_timestamp(lockout_until_raw)
    if lockout_until and now_tw() < lockout_until:
        return True, lockout_until, failed
    return False, lockout_until, failed


def _increment_failed_login(user_id: str, current_failed: int) -> None:
    """使用 RTDB transaction 原子性增加失敗次數。"""
    failed_path = f"/users/{user_id}/failed_login_count"
    lockout_path = f"/users/{user_id}/lockout_until"

    def _update_failed(current):
        return (current or 0) + 1

    rtdb_transaction(failed_path, _update_failed)

    new_failed = current_failed + 1
    if new_failed >= MAX_FAILED:
        lockout_until = (now_tw() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        rtdb_set(lockout_path, lockout_until)


def _clear_failed_login(user_id: str) -> None:
    rtdb_update(_user_path(user_id), {
        "failed_login_count": 0,
        "lockout_until": None,
    })


# ── 登入 ───────────────────────────────────────────────────────────────────────

def login(username_raw: str, password: str) -> Tuple[bool, str]:
    GENERIC_ERROR = "帳號或密碼錯誤，請重新輸入。"
    username = normalize_username(username_raw)

    user_id, user_data = get_user_by_username(username)

    if not user_data:
        # 帳號不存在：執行假雜湊防計時攻擊
        try:
            verify_password("dummy", hash_password("placeholder"))
        except Exception:
            pass
        return False, GENERIC_ERROR

    if not user_data.get("is_active", True):
        return False, GENERIC_ERROR

    is_locked, lockout_until, failed = _get_lockout_info(user_data)
    if is_locked:
        remaining = max(1, int((lockout_until - now_tw()).total_seconds() // 60) + 1)
        return False, f"帳號已鎖定，請於 {remaining} 分鐘後再試。"

    stored_hash = user_data.get("password_hash", "")
    if not verify_password(password, stored_hash):
        _increment_failed_login(user_id, failed)
        new_failed = failed + 1
        if new_failed >= MAX_FAILED:
            return False, f"帳號已因多次錯誤被鎖定 {LOCKOUT_MINUTES} 分鐘。"
        return False, f"帳號或密碼錯誤。還可嘗試 {MAX_FAILED - new_failed} 次。"

    _clear_failed_login(user_id)

    token = secrets.token_urlsafe(32)
    now = now_tw()
    rtdb_update(_user_path(user_id), {
        "session_token": token,
        "session_created": now.isoformat(),
        "session_last_active": now.isoformat(),
    })

    st.session_state.update({
        "auth_token": token,
        "user_id": user_id,
        "username": username,
        "display_name": user_data.get("display_name", username),
        "must_change_password": user_data.get("must_change_password", False),
        "last_active": now.isoformat(),
    })
    return True, ""


def logout(user_id: Optional[str] = None) -> None:
    uid = user_id or st.session_state.get("user_id")
    if uid:
        rtdb_update(_user_path(uid), {
            "session_token": None,
            "session_last_active": None,
        })
    for key in ["auth_token", "user_id", "username", "display_name",
                "must_change_password", "last_active", "current_page",
                "selected_item_id", "count_event_id", "count_status"]:
        st.session_state.pop(key, None)


# ── 工作階段驗證 ───────────────────────────────────────────────────────────────

def get_session_timeout_minutes() -> int:
    try:
        val = rtdb_get("/system_settings/session_timeout_minutes")
        return int(val) if val else SESSION_IDLE_MINUTES
    except Exception:
        return SESSION_IDLE_MINUTES


def check_session() -> Tuple[bool, Optional[dict]]:
    token = st.session_state.get("auth_token")
    user_id = st.session_state.get("user_id")
    if not token or not user_id:
        return False, None

    user_data = get_user(user_id)
    if not user_data:
        logout()
        return False, None

    if not user_data.get("is_active", True):
        logout()
        return False, None

    if user_data.get("session_token") != token:
        logout()
        return False, None

    timeout_minutes = get_session_timeout_minutes()
    last_active_raw = st.session_state.get("last_active")
    if last_active_raw:
        last_active = parse_timestamp(last_active_raw)
        if last_active and (now_tw() - last_active).total_seconds() > timeout_minutes * 60:
            logout()
            return False, None

    now = now_tw()
    st.session_state["last_active"] = now.isoformat()
    rtdb_update(_user_path(user_id), {"session_last_active": now.isoformat()})

    return True, user_data


# ── 密碼修改 ───────────────────────────────────────────────────────────────────

def change_password(user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    user_data = get_user(user_id)
    if not user_data:
        return False, "找不到帳號資料。"

    if not verify_password(old_password, user_data.get("password_hash", "")):
        return False, "原密碼不正確。"

    if verify_password(new_password, user_data.get("password_hash", "")):
        return False, "新密碼不得與原密碼相同。"

    ok, msg = validate_password_complexity(new_password)
    if not ok:
        return False, msg

    ok = rtdb_update(_user_path(user_id), {
        "password_hash": hash_password(new_password),
        "must_change_password": False,
        "session_token": None,
        "password_changed_at": now_tw().isoformat(),
    })
    if not ok:
        return False, "密碼更新失敗，請稍後再試。"

    logout(user_id)
    return True, ""


def admin_reset_password(admin_user_id: str, target_user_id: str) -> Tuple[bool, str, str]:
    temp_pwd = generate_temp_password()
    ok = rtdb_update(_user_path(target_user_id), {
        "password_hash": hash_password(temp_pwd),
        "must_change_password": True,
        "session_token": None,
        "password_reset_at": now_tw().isoformat(),
        "password_reset_by": admin_user_id,
    })
    if not ok:
        return False, "密碼重設失敗。", ""

    from modules.audit import log_action
    log_action(admin_user_id, "reset_password", "user", target_user_id, "success")
    return True, "", temp_pwd


def create_user(admin_user_id: str, username: str, display_name: str,
                role: str = "member") -> Tuple[bool, str, str]:
    normalized = normalize_username(username)
    if not normalized:
        return False, "帳號名稱不得為空。", ""

    # 檢查帳號唯一性（透過 index）
    existing = rtdb_get(_username_index_path(normalized))
    if existing:
        return False, "此帳號名稱已被使用。", ""

    temp_pwd = generate_temp_password()
    user_id = str(uuid.uuid4())
    now = now_tw()

    user_data = {
        "username": normalized,
        "display_name": display_name.strip(),
        "password_hash": hash_password(temp_pwd),
        "must_change_password": True,
        "is_active": True,
        "role": role,
        "failed_login_count": 0,
        "lockout_until": None,
        "session_token": None,
        "created_at": now.isoformat(),
        "created_by": admin_user_id,
    }

    ok1 = rtdb_set(_user_path(user_id), user_data)
    ok2 = rtdb_set(_username_index_path(normalized), user_id)

    if not (ok1 and ok2):
        return False, "建立帳號失敗。", ""

    from modules.rbac import assign_role_to_user
    assign_role_to_user(user_id, role)

    from modules.audit import log_action
    log_action(admin_user_id, "create_user", "user", user_id, "success",
               {"username": normalized, "role": role})

    return True, "", temp_pwd
