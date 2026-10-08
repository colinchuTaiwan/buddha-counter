"""
pages/admin_members.py
管理後台：會員管理 — 表格格式 + 完整操作。
"""
import streamlit as st

from modules.auth import create_user, admin_reset_password, validate_password_complexity, hash_password
from modules.audit import log_action, log_error
from modules.db import rtdb_get, rtdb_update, rtdb_set, rtdb_delete, now_tw
from modules.rbac import (
    require_permission, P, is_superadmin,
    count_active_superadmins, get_user_role,
    invalidate_permission_cache,
)
from modules.ui_components import (
    page_header, render_admin_nav, gold_divider, success_box, error_box, info_box
)


def _get_all_users(search: str = "") -> list:
    try:
        users_data = rtdb_get("/users") or {}
        users = []
        for uid, u in users_data.items():
            if not isinstance(u, dict):
                continue
            u["id"] = uid
            users.append(u)
        if search:
            s = search.strip().lower()
            users = [u for u in users
                     if s in u.get("username", "").lower()
                     or s in u.get("display_name", "").lower()]
        users.sort(key=lambda x: x.get("created_at", ""))
        return users
    except Exception as e:
        log_error("database_error", f"讀取會員列表失敗: {e}")
        return []


def _fmt_dt(s: str) -> str:
    """格式化時間字串。"""
    if not s:
        return "尚未登入"
    return s[:19].replace("T", " ")


def _render_user_table(admin_id: str, users: list) -> None:
    """以表格形式顯示會員清單。"""
    # 表頭
    st.markdown("""
    <style>
    .member-table { width:100%; border-collapse:collapse; font-size:1rem; }
    .member-table th {
        background:#f5f0ea; color:#5c3d1e; font-weight:700;
        padding:0.7rem 0.8rem; text-align:left;
        border-bottom:2px solid #c8b49a;
    }
    .member-table td {
        padding:0.65rem 0.8rem; border-bottom:1px solid #e8ddd0;
        vertical-align:middle; word-break:break-word;
    }
    .member-table tr:hover td { background:#fdf8f2; }
    .badge-active   { background:#e8f5e9; color:#2e7d32; border-radius:8px; padding:0.15rem 0.6rem; font-size:0.82rem; font-weight:700; }
    .badge-inactive { background:#fce4ec; color:#c62828; border-radius:8px; padding:0.15rem 0.6rem; font-size:0.82rem; font-weight:700; }
    .badge-locked   { background:#fff3e0; color:#e65100; border-radius:8px; padding:0.15rem 0.6rem; font-size:0.82rem; font-weight:700; }
    </style>
    """, unsafe_allow_html=True)

    header = """
    <table class="member-table">
    <thead><tr>
        <th>姓名</th>
        <th>最後登入</th>
        <th>建立時間</th>
        <th>登入帳號</th>
        <th>狀態</th>
    </tr></thead><tbody>
    """
    rows = ""
    for u in users:
        uid = u["id"]
        display_name = u.get("display_name", "")
        username = u.get("username", "")
        created_at = _fmt_dt(u.get("created_at", ""))
        last_active = _fmt_dt(u.get("session_last_active", ""))
        is_active = u.get("is_active", True)
        is_locked = bool(u.get("lockout_until"))

        if is_locked:
            badge = '<span class="badge-locked">🔒 鎖定</span>'
        elif is_active:
            badge = '<span class="badge-active">✓ 啟用</span>'
        else:
            badge = '<span class="badge-inactive">✗ 停用</span>'

        rows += f"""<tr>
            <td><b>{display_name}</b></td>
            <td style="color:#8a7060">{last_active}</td>
            <td style="color:#8a7060">{created_at}</td>
            <td><code>{username}</code></td>
            <td>{badge}</td>
        </tr>"""

    st.markdown(header + rows + "</tbody></table>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:0.3rem'></div>", unsafe_allow_html=True)

    # 操作按鈕（表格下方逐筆）
    st.markdown("---")
    st.markdown("**操作**")
    for u in users:
        uid = u["id"]
        display_name = u.get("display_name", "")
        username = u.get("username", "")
        is_active = u.get("is_active", True)
        is_locked = bool(u.get("lockout_until"))
        role = get_user_role(uid)

        with st.container():
            st.markdown(
                f'<div style="background:#fdf8f2;border-radius:10px;'
                f'padding:0.6rem 1rem;margin-bottom:0.3rem">'
                f'<b>{display_name}</b> <span style="color:#8a7060">@{username}</span></div>',
                unsafe_allow_html=True,
            )
            cols = st.columns([1, 1, 1, 1, 1, 1])

            # 刪除
            if cols[0].button("🗑 刪除", key=f"del_{uid}", use_container_width=True):
                require_permission(admin_id, P.USER_DISABLE)
                if role == "superadmin" and count_active_superadmins() <= 1:
                    error_box("無法刪除最後一位有效最高管理者。")
                else:
                    st.session_state[f"confirm_delete_{uid}"] = True
                    st.rerun()

            # 重設密碼（臨時密碼）
            if cols[1].button("🔑 重設密碼", key=f"rst_{uid}", use_container_width=True):
                require_permission(admin_id, P.USER_RESET_PWD)
                ok, msg, temp_pwd = admin_reset_password(admin_id, uid)
                if ok:
                    st.success(f"✓ 已重設密碼")
                    st.markdown(
                        f'<div class="card card-gold"><b>臨時密碼（僅顯示一次）：</b><br>'
                        f'<code style="font-size:1.3rem;color:#9e7a4e">{temp_pwd}</code></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    error_box(msg)

            # 修改密碼（直接設定）
            if cols[2].button("✏ 改密碼", key=f"chpwd_{uid}", use_container_width=True):
                require_permission(admin_id, P.USER_RESET_PWD)
                cur = st.session_state.get(f"show_pwd_{uid}", False)
                st.session_state[f"show_pwd_{uid}"] = not cur
                st.rerun()

            # 停用/啟用
            label = "🚫 停用" if is_active else "✓ 啟用"
            if cols[3].button(label, key=f"toggle_{uid}", use_container_width=True):
                require_permission(admin_id, P.USER_DISABLE)
                if is_active and role == "superadmin" and count_active_superadmins() <= 1:
                    error_box("無法停用最後一位有效最高管理者。")
                else:
                    rtdb_update(f"/users/{uid}", {"is_active": not is_active, "session_token": None})
                    invalidate_permission_cache(uid)
                    log_action(admin_id, "disable_user" if is_active else "enable_user",
                               "user", uid, "success", {"username": username})
                    st.rerun()

            # 解除鎖定
            if is_locked:
                if cols[4].button("🔓 解鎖", key=f"unlock_{uid}", use_container_width=True):
                    require_permission(admin_id, P.USER_UNLOCK)
                    rtdb_update(f"/users/{uid}", {"lockout_until": None, "failed_login_count": 0})
                    log_action(admin_id, "unlock_user", "user", uid, "success", {"username": username})
                    st.rerun()

            # ── 改密碼表單 ──
            if st.session_state.get(f"show_pwd_{uid}"):
                with st.form(f"pwd_form_{uid}"):
                    new_pwd = st.text_input("新密碼", type="password",
                                            help="至少 10 碼，含大小寫英文及數字")
                    confirm_pwd = st.text_input("確認新密碼", type="password")
                    c1, c2 = st.columns(2)
                    save = c1.form_submit_button("確認設定", type="primary")
                    cancel = c2.form_submit_button("取消")
                if save:
                    if new_pwd != confirm_pwd:
                        error_box("兩次密碼不一致。")
                    else:
                        ok, msg = validate_password_complexity(new_pwd)
                        if not ok:
                            error_box(msg)
                        else:
                            rtdb_update(f"/users/{uid}", {
                                "password_hash": hash_password(new_pwd),
                                "must_change_password": True,
                                "session_token": None,
                                "password_reset_at": now_tw().isoformat(),
                                "password_reset_by": admin_id,
                            })
                            log_action(admin_id, "change_password", "user", uid, "success",
                                       {"username": username, "note": "管理者直接設定"})
                            success_box("密碼已更新，會員下次登入須修改密碼。")
                            st.session_state.pop(f"show_pwd_{uid}", None)
                            st.rerun()
                if cancel:
                    st.session_state.pop(f"show_pwd_{uid}", None)
                    st.rerun()

            # ── 刪除確認 ──
            if st.session_state.get(f"confirm_delete_{uid}"):
                st.error(f"⚠ 確定永久刪除「{display_name}（@{username}）」？此操作無法復原！")
                cy, cn = st.columns(2)
                if cy.button("確定刪除", key=f"yes_{uid}", type="primary"):
                    _delete_user(admin_id, uid, username, display_name)
                    st.session_state.pop(f"confirm_delete_{uid}", None)
                    st.rerun()
                if cn.button("取消", key=f"no_{uid}"):
                    st.session_state.pop(f"confirm_delete_{uid}", None)
                    st.rerun()

        gold_divider()


def _delete_user(admin_id, uid, username, display_name):
    try:
        rtdb_delete(f"/users/{uid}")
        rtdb_delete(f"/username_index/{username}")
        rtdb_delete(f"/user_roles/{uid}")
        invalidate_permission_cache(uid)
        log_action(admin_id, "delete_user", "user", uid, "success",
                   {"username": username, "display_name": display_name})
        success_box(f"已刪除會員「{display_name}」。")
    except Exception as e:
        log_error("delete_user_error", f"刪除會員失敗: {e}", admin_id, e)
        error_box("刪除失敗，請稍後再試。")


def _render_create_user(admin_id: str) -> None:
    require_permission(admin_id, P.USER_CREATE)
    with st.form("create_user_form"):
        username = st.text_input("帳號（登入用，英文小寫）", max_chars=50)
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
                f'<div class="card card-gold" style="font-size:1.1rem">'
                f'<b>臨時密碼（僅顯示一次）：</b><br>'
                f'<code style="font-size:1.4rem;color:#9e7a4e">{temp_pwd}</code></div>',
                unsafe_allow_html=True,
            )
            st.rerun()
        else:
            error_box(msg)


def render(user_doc: dict) -> None:
    admin_id = user_doc["id"]
    require_permission(admin_id, P.USER_VIEW)
    render_admin_nav("members")
    page_header("⚙ 管理後台", "會員管理")

    tab1, tab2 = st.tabs(["👥 會員清單", "➕ 新增會員"])

    with tab1:
        search = st.text_input("🔍 搜尋（姓名或帳號）", key="admin_search")
        users = _get_all_users(search)
        st.markdown(f"<p style='color:#8a7060'>共 {len(users)} 位會員</p>",
                    unsafe_allow_html=True)
        if not users:
            info_box("找不到符合條件的會員。")
        else:
            _render_user_table(admin_id, users)

    with tab2:
        _render_create_user(admin_id)
