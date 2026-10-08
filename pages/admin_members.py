"""
pages/admin_members.py
管理後台：會員管理 — 完整版。
功能：新增、刪除、停用/啟用、重設密碼、修改會員密碼、解除鎖定。
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
    page_header, render_nav, gold_divider, success_box, error_box, info_box
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


def _render_create_user(admin_id: str) -> None:
    """新增會員帳號。"""
    require_permission(admin_id, P.USER_CREATE)
    with st.expander("＋ 新增會員帳號"):
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
                    f'<b>臨時密碼（僅顯示一次，請立即告知會員）：</b><br>'
                    f'<code style="font-size:1.4rem;color:#9e7a4e">{temp_pwd}</code></div>',
                    unsafe_allow_html=True,
                )
                st.rerun()
            else:
                error_box(msg)


def _render_user_detail(admin_id: str, user: dict) -> None:
    """渲染單一會員的管理面板。"""
    uid = user["id"]
    username = user.get("username", "")
    display_name = user.get("display_name", "")
    is_active = user.get("is_active", True)
    is_locked = bool(user.get("lockout_until"))
    failed_count = user.get("failed_login_count", 0)
    created_at = user.get("created_at", "")[:19].replace("T", " ")
    role = get_user_role(uid)

    role_label = {"member": "一般會員", "account_admin": "帳號管理者",
                  "superadmin": "最高管理者"}.get(role, role)
    status_color = "#5a8a5a" if is_active else "#c05050"

    # ── 會員資訊卡 ──
    st.markdown(f"""
    <div class="card" style="margin-bottom:0.3rem">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
            <div>
                <b class="item-name" style="font-size:1.15rem">{display_name}</b>
                <span style="color:#8a7060;font-size:0.9rem"> @{username}</span>
            </div>
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
                <span style="background:#f5f0ea;border-radius:8px;padding:0.2rem 0.7rem;
                    font-size:0.88rem;font-weight:600">{role_label}</span>
                <span style="background:{"#e8f5e9" if is_active else "#fce4ec"};
                    border-radius:8px;padding:0.2rem 0.7rem;
                    font-size:0.88rem;font-weight:600;color:{status_color}">
                    {"✓ 啟用" if is_active else "✗ 停用"}</span>
                {"<span style='background:#fff3e0;border-radius:8px;padding:0.2rem 0.7rem;font-size:0.88rem;font-weight:600;color:#e65100'>🔒 鎖定中</span>" if is_locked else ""}
            </div>
        </div>
        <div style="color:#8a7060;font-size:0.85rem;margin-top:0.3rem">
            建立時間：{created_at}　|　登入失敗次數：{failed_count}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 操作按鈕列 ──
    cols = st.columns(5)

    # 1. 重設密碼
    if cols[0].button("🔑 重設密碼", key=f"rst_{uid}", use_container_width=True):
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

    # 2. 停用/啟用
    if cols[1].button("🚫 停用" if is_active else "✓ 啟用",
                      key=f"toggle_{uid}", use_container_width=True):
        require_permission(admin_id, P.USER_DISABLE)
        if is_active and role == "superadmin" and count_active_superadmins() <= 1:
            error_box("無法停用最後一位有效最高管理者。")
        else:
            rtdb_update(f"/users/{uid}", {"is_active": not is_active, "session_token": None})
            invalidate_permission_cache(uid)
            action = "disable_user" if is_active else "enable_user"
            log_action(admin_id, action, "user", uid, "success",
                       {"username": username, "display_name": display_name})
            st.rerun()

    # 3. 解除鎖定
    if is_locked:
        if cols[2].button("🔓 解除鎖定", key=f"unlock_{uid}", use_container_width=True):
            require_permission(admin_id, P.USER_UNLOCK)
            rtdb_update(f"/users/{uid}", {"lockout_until": None, "failed_login_count": 0})
            log_action(admin_id, "unlock_user", "user", uid, "success",
                       {"username": username})
            success_box("已解除鎖定。")
            st.rerun()

    # 4. 修改密碼（管理者直接設定新密碼，不需原密碼）
    if cols[3].button("✏ 改密碼", key=f"chpwd_{uid}", use_container_width=True):
        st.session_state[f"show_pwd_form_{uid}"] = not st.session_state.get(f"show_pwd_form_{uid}", False)
        st.rerun()

    # 5. 刪除帳號
    if cols[4].button("🗑 刪除", key=f"del_{uid}", use_container_width=True):
        require_permission(admin_id, P.USER_DISABLE)  # 用停用權限控制刪除
        if role == "superadmin" and count_active_superadmins() <= 1:
            error_box("無法刪除最後一位有效最高管理者。")
        else:
            st.session_state[f"confirm_delete_{uid}"] = True
            st.rerun()

    # ── 修改密碼表單 ──
    if st.session_state.get(f"show_pwd_form_{uid}"):
        require_permission(admin_id, P.USER_RESET_PWD)
        with st.form(f"admin_pwd_form_{uid}"):
            st.markdown("**管理者直接設定新密碼**")
            new_pwd = st.text_input("新密碼", type="password",
                                    help="至少 10 碼，含大寫、小寫英文及數字")
            confirm_pwd = st.text_input("確認新密碼", type="password")
            col_save, col_cancel = st.columns(2)
            save = col_save.form_submit_button("設定密碼", type="primary")
            cancel = col_cancel.form_submit_button("取消")

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
                    success_box("密碼已更新，該會員下次登入須修改密碼。")
                    st.session_state.pop(f"show_pwd_form_{uid}", None)
                    st.rerun()
        if cancel:
            st.session_state.pop(f"show_pwd_form_{uid}", None)
            st.rerun()

    # ── 刪除確認 ──
    if st.session_state.get(f"confirm_delete_{uid}"):
        st.error(f"⚠ 確定要永久刪除會員「{display_name}（@{username}）」嗎？此操作無法復原！")
        col_yes, col_no = st.columns(2)
        if col_yes.button("確定刪除", key=f"yes_del_{uid}", type="primary"):
            _delete_user(admin_id, uid, username, display_name)
            st.session_state.pop(f"confirm_delete_{uid}", None)
            st.rerun()
        if col_no.button("取消", key=f"no_del_{uid}"):
            st.session_state.pop(f"confirm_delete_{uid}", None)
            st.rerun()


def _delete_user(admin_id: str, uid: str, username: str, display_name: str) -> None:
    """刪除會員帳號及相關資料。"""
    try:
        # 刪除使用者資料
        rtdb_delete(f"/users/{uid}")
        # 刪除帳號索引
        rtdb_delete(f"/username_index/{username}")
        # 刪除角色綁定
        rtdb_delete(f"/user_roles/{uid}")
        # 誦經項目、計數紀錄、統計保留（歷史資料）
        invalidate_permission_cache(uid)
        log_action(admin_id, "delete_user", "user", uid, "success",
                   {"username": username, "display_name": display_name})
        success_box(f"已刪除會員「{display_name}」。")
    except Exception as e:
        log_error("delete_user_error", f"刪除會員失敗: {e}", admin_id, e)
        error_box("刪除失敗，請稍後再試。")


def render(user_doc: dict) -> None:
    admin_id = user_doc["id"]
    require_permission(admin_id, P.USER_VIEW)
    render_nav("admin_members", is_admin=True)
    page_header("⚙ 管理後台", "會員管理")

    tab1, tab2 = st.tabs(["👥 會員列表", "➕ 新增會員"])

    with tab1:
        search = st.text_input("🔍 搜尋會員（帳號或顯示名稱）", key="admin_search")
        users = _get_all_users(search)
        st.markdown(f"<p style='color:#8a7060'>共 {len(users)} 位會員</p>",
                    unsafe_allow_html=True)
        if not users:
            info_box("找不到符合條件的會員。")
        else:
            for user in users:
                _render_user_detail(admin_id, user)
                gold_divider()

    with tab2:
        _render_create_user(admin_id)
