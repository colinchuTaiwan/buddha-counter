"""
pages/admin_members.py
管理後台：會員管理。
具有獨立入口，普通會員即使直接輸入後台網址也無法存取。
"""
import streamlit as st

from modules.auth import create_user, admin_reset_password, validate_password_complexity
from modules.audit import log_action
from modules.db import db, now_tw, safe_update, safe_get, doc_to_dict
from modules.rbac import (
    require_permission, P, is_superadmin,
    count_active_superadmins, assign_role_to_user,
    get_user_role, invalidate_permission_cache,
)
from modules.ui_components import (
    page_header, render_nav, gold_divider, success_box, error_box, info_box
)


def _get_all_users(search: str = "") -> list:
    """取得所有使用者（含停用），支援名稱/帳號搜尋。"""
    try:
        docs = db().collection("users").order_by("created_at").get()
        users = [doc_to_dict(d) for d in docs]
        if search:
            s = search.strip().lower()
            users = [
                u for u in users
                if s in (u.get("username", "").lower())
                or s in (u.get("display_name", "").lower())
            ]
        return users
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("_get_all_users: %s", e)
        return []


def _render_create_user(admin_id: str) -> None:
    require_permission(admin_id, P.USER_CREATE)
    with st.expander("＋ 新增會員帳號"):
        with st.form("create_user_form"):
            username = st.text_input("帳號（登入用）", max_chars=50)
            display_name = st.text_input("顯示名稱", max_chars=30)
            role = st.selectbox("角色", ["member", "account_admin", "superadmin"],
                                format_func=lambda x: {
                                    "member": "一般會員",
                                    "account_admin": "帳號管理者",
                                    "superadmin": "最高管理者",
                                }.get(x, x))
            submitted = st.form_submit_button("建立帳號", type="primary")

        if submitted:
            ok, msg, temp_pwd = create_user(admin_id, username, display_name, role)
            if ok:
                st.success("✓ 帳號已建立！")
                st.markdown(
                    f"""
                    <div class="card card-gold" style="font-size:1.1rem">
                    <b>臨時密碼（僅顯示一次，請立即告知會員）：</b><br>
                    <code style="font-size:1.4rem;color:#9e7a4e">{temp_pwd}</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                error_box(msg)


def _render_user_row(admin_id: str, user: dict) -> None:
    """渲染單一會員管理列。"""
    uid = user["id"]
    username = user.get("username", "")
    display_name = user.get("display_name", "")
    is_active = user.get("is_active", True)
    failed = user.get("failed_login_count", 0)
    is_locked = bool(user.get("lockout_until"))

    status_tag = "✓ 啟用" if is_active else "✗ 停用"
    lock_tag = "🔒 鎖定中" if is_locked else ""

    with st.container():
        st.markdown(
            f'<div class="card" style="margin-bottom:0.5rem">'
            f'<b class="item-name">{display_name}</b> '
            f'<span style="color:#8a7060;font-size:0.9rem">@{username}</span> '
            f'<span style="color:{"#5a8a5a" if is_active else "#c05050"}">{status_tag}</span> '
            f'<span style="color:#c05050">{lock_tag}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        cols = st.columns([1, 1, 1, 1])

        # 重設密碼
        if cols[0].button("重設密碼", key=f"rst_{uid}"):
            require_permission(admin_id, P.USER_RESET_PWD)
            ok, msg, temp_pwd = admin_reset_password(admin_id, uid)
            if ok:
                st.success("✓ 密碼已重設")
                st.markdown(
                    f'<div class="card card-gold"><b>臨時密碼（僅顯示一次）：</b><br>'
                    f'<code style="font-size:1.3rem;color:#9e7a4e">{temp_pwd}</code></div>',
                    unsafe_allow_html=True,
                )
            else:
                error_box(msg)

        # 停用/啟用
        require_permission(admin_id, P.USER_DISABLE)
        if is_active:
            if cols[1].button("停用", key=f"dis_{uid}"):
                # 防止停用最後一位有效最高管理者
                if get_user_role(uid) == "superadmin" and count_active_superadmins() <= 1:
                    error_box("無法停用最後一位有效最高管理者。")
                else:
                    safe_update("users", uid, {
                        "is_active": False,
                        "session": None,  # 使現有 session 失效
                    })
                    invalidate_permission_cache(uid)
                    log_action(admin_id, "disable_user", "user", uid, "success")
                    st.rerun()
        else:
            if cols[1].button("啟用", key=f"ena_{uid}"):
                safe_update("users", uid, {"is_active": True})
                log_action(admin_id, "enable_user", "user", uid, "success")
                st.rerun()

        # 解除鎖定
        if is_locked:
            if cols[2].button("解除鎖定", key=f"unlock_{uid}"):
                require_permission(admin_id, P.USER_UNLOCK)
                safe_update("users", uid, {
                    "lockout_until": None,
                    "failed_login_count": 0,
                })
                log_action(admin_id, "unlock_user", "user", uid, "success")
                success_box("已解除鎖定。")
                st.rerun()

        # 查看統計（需獨立權限）
        if has_stats_perm := __import__(
            "modules.rbac", fromlist=["has_permission"]
        ).has_permission(admin_id, P.STATS_VIEW_ALL):
            if cols[3].button("查看統計", key=f"stat_{uid}"):
                st.session_state["admin_view_stats_user"] = uid
                st.session_state["admin_view_stats_name"] = display_name
                st.rerun()


def render(user_doc: dict) -> None:
    """管理後台：會員管理入口。"""
    admin_id = user_doc["id"]

    # 後端再次確認：普通會員不得存取
    require_permission(admin_id, P.USER_VIEW)

    render_nav("admin_members", is_admin=True)
    page_header("⚙ 管理後台", "會員管理")

    # 新增會員
    _render_create_user(admin_id)
    gold_divider()

    # 搜尋
    search = st.text_input("🔍 搜尋會員（帳號或顯示名稱）", key="admin_search")
    users = _get_all_users(search)

    st.markdown(f"<p style='color:#8a7060'>共 {len(users)} 位會員</p>", unsafe_allow_html=True)

    if not users:
        info_box("找不到符合條件的會員。")
        return

    for user in users:
        _render_user_row(admin_id, user)
        gold_divider()
