"""
modules/rbac.py
RBAC 角色權限管理 — Firebase Realtime Database 版本。

RTDB 路徑設計：
  /roles/{role_code}                    角色定義
  /role_permissions/{role_code}/{perm}  角色權限
  /user_roles/{user_id}/{role_code}     人員角色綁定
"""
import logging
from typing import Set

import streamlit as st
from modules.db import rtdb_get, rtdb_set, rtdb_update, rtdb_delete, now_tw

logger = logging.getLogger(__name__)


class P:
    ITEM_VIEW    = "item_view"
    ITEM_CREATE  = "item_create"
    ITEM_EDIT    = "item_edit"
    ITEM_ARCHIVE = "item_archive"
    COUNT_ADD    = "count_add"
    COUNT_UNDO   = "count_undo"
    STATS_SELF      = "stats_self"
    STATS_VIEW_ALL  = "stats_view_all"
    USER_VIEW       = "user_view"
    USER_CREATE     = "user_create"
    USER_EDIT       = "user_edit"
    USER_DISABLE    = "user_disable"
    USER_RESET_PWD  = "user_reset_password"
    USER_UNLOCK     = "user_unlock"
    ROLE_MANAGE     = "role_manage"
    AUDIT_VIEW      = "audit_view"
    SYSTEM_SETTINGS = "system_settings"


DEFAULT_ROLES = {
    "member": {
        "display_name": "一般會員",
        "permissions": [P.ITEM_VIEW, P.ITEM_CREATE, P.ITEM_EDIT, P.ITEM_ARCHIVE,
                        P.COUNT_ADD, P.COUNT_UNDO, P.STATS_SELF],
    },
    "account_admin": {
        "display_name": "帳號管理者",
        "permissions": [P.USER_VIEW, P.USER_CREATE, P.USER_EDIT, P.USER_DISABLE, P.USER_RESET_PWD],
    },
    "superadmin": {
        "display_name": "最高管理者",
        "permissions": [
            P.ITEM_VIEW, P.ITEM_CREATE, P.ITEM_EDIT, P.ITEM_ARCHIVE,
            P.COUNT_ADD, P.COUNT_UNDO, P.STATS_SELF, P.STATS_VIEW_ALL,
            P.USER_VIEW, P.USER_CREATE, P.USER_EDIT, P.USER_DISABLE,
            P.USER_RESET_PWD, P.USER_UNLOCK, P.ROLE_MANAGE,
            P.AUDIT_VIEW, P.SYSTEM_SETTINGS,
        ],
    },
}

FEATURE_TREE = [
    {"code": "recitation", "name": "誦經管理", "order": 1, "children": [
        {"code": P.ITEM_VIEW,    "name": "查看項目",     "order": 1},
        {"code": P.ITEM_CREATE,  "name": "新增項目",     "order": 2},
        {"code": P.ITEM_EDIT,    "name": "修改項目",     "order": 3},
        {"code": P.ITEM_ARCHIVE, "name": "封存/取消封存","order": 4},
    ]},
    {"code": "counting", "name": "計數功能", "order": 2, "children": [
        {"code": P.COUNT_ADD,  "name": "新增計數", "order": 1},
        {"code": P.COUNT_UNDO, "name": "撤銷計數", "order": 2},
    ]},
    {"code": "statistics", "name": "統計紀錄", "order": 3, "children": [
        {"code": P.STATS_SELF,    "name": "查看自己統計",    "order": 1},
        {"code": P.STATS_VIEW_ALL,"name": "查看所有會員統計","order": 2},
    ]},
    {"code": "user_management", "name": "會員管理", "order": 4, "children": [
        {"code": P.USER_VIEW,     "name": "查看會員",    "order": 1},
        {"code": P.USER_CREATE,   "name": "新增會員",    "order": 2},
        {"code": P.USER_EDIT,     "name": "修改會員資料","order": 3},
        {"code": P.USER_DISABLE,  "name": "停用/啟用",  "order": 4},
        {"code": P.USER_RESET_PWD,"name": "重設密碼",   "order": 5},
        {"code": P.USER_UNLOCK,   "name": "解除鎖定",   "order": 6},
    ]},
    {"code": "admin", "name": "系統管理", "order": 5, "children": [
        {"code": P.ROLE_MANAGE,    "name": "角色權限管理","order": 1},
        {"code": P.AUDIT_VIEW,     "name": "稽核紀錄",   "order": 2},
        {"code": P.SYSTEM_SETTINGS,"name": "系統設定",   "order": 3},
    ]},
]


def get_user_permissions(user_id: str) -> Set[str]:
    cache_key = f"_perms_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    perms = _load_permissions(user_id)
    st.session_state[cache_key] = perms
    return perms


def invalidate_permission_cache(user_id: str) -> None:
    st.session_state.pop(f"_perms_{user_id}", None)


def _load_permissions(user_id: str) -> Set[str]:
    perms: Set[str] = set()
    try:
        user_roles = rtdb_get(f"/user_roles/{user_id}") or {}
        for role_code, active in user_roles.items():
            if not active:
                continue
            role_perms = rtdb_get(f"/role_permissions/{role_code}") or {}
            perms.update(p for p, enabled in role_perms.items() if enabled)
    except Exception as e:
        logger.error("_load_permissions user=%s: %s", user_id, e)
    return perms


def has_permission(user_id: str, permission: str) -> bool:
    return permission in get_user_permissions(user_id)


def require_permission(user_id: str, permission: str) -> None:
    if not has_permission(user_id, permission):
        st.error("⛔ 您沒有執行此操作的權限。")
        st.stop()


def ensure_default_roles() -> None:
    for role_code, role_def in DEFAULT_ROLES.items():
        existing = rtdb_get(f"/roles/{role_code}")
        if not existing:
            rtdb_set(f"/roles/{role_code}", {
                "code": role_code,
                "display_name": role_def["display_name"],
                "is_active": True,
                "created_at": now_tw().isoformat(),
            })
        for perm_code in role_def["permissions"]:
            rtdb_set(f"/role_permissions/{role_code}/{perm_code}", True)


def assign_role_to_user(user_id: str, role_code: str) -> bool:
    ok = rtdb_set(f"/user_roles/{user_id}/{role_code}", True)
    invalidate_permission_cache(user_id)
    return ok


def get_user_role(user_id: str) -> str:
    roles = rtdb_get(f"/user_roles/{user_id}") or {}
    active = [r for r, v in roles.items() if v]
    for r in ["superadmin", "account_admin", "member"]:
        if r in active:
            return r
    return active[0] if active else "member"


def is_superadmin(user_id: str) -> bool:
    return has_permission(user_id, P.ROLE_MANAGE)


def count_active_superadmins() -> int:
    try:
        superadmin_users = rtdb_get("/user_roles") or {}
        count = 0
        for uid, roles in superadmin_users.items():
            if roles.get("superadmin"):
                user = rtdb_get(f"/users/{uid}") or {}
                if user.get("is_active"):
                    count += 1
        return count
    except Exception:
        return 0
