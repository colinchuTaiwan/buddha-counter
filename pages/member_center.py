"""
pages/member_center.py
會員中心 — Firebase Realtime Database 版本。
"""
import streamlit as st

from modules.auth import change_password, validate_password_complexity
from modules.db import rtdb_get, rtdb_update, now_tw
from modules.rbac import require_permission, P, is_superadmin
from modules.recitation import get_user_items, create_item, update_item, archive_item
from modules.ui_components import (
    page_header, render_nav, gold_divider, success_box, error_box, info_box
)


def _render_profile(user_doc: dict) -> None:
    user_id = user_doc["id"]
    st.subheader("個人基本資料")
    with st.form("profile_form"):
        display_name = st.text_input("顯示名稱", value=user_doc.get("display_name", ""), max_chars=30)
        st.caption(f"帳號：{user_doc.get('username', '')}（無法修改）")
        submitted = st.form_submit_button("儲存變更")
    if submitted:
        name = display_name.strip()
        if not name:
            error_box("顯示名稱不得為空。")
        elif len(name) > 30:
            error_box("顯示名稱不得超過 30 個字元。")
        else:
            ok = rtdb_update(f"/users/{user_id}", {
                "display_name": name,
                "updated_at": now_tw().isoformat(),
            })
            if ok:
                st.session_state["display_name"] = name
                success_box("基本資料已更新。")
                st.rerun()
            else:
                error_box("更新失敗，請稍後再試。")


def _render_change_password(user_id: str, force: bool = False) -> None:
    if force:
        st.warning("⚠ 請先設定新密碼才能使用其他功能。")
        st.subheader("設定新密碼")
    else:
        st.subheader("修改密碼")

    with st.form("change_pwd_form"):
        old_pwd = st.text_input("原密碼", type="password")
        new_pwd = st.text_input("新密碼", type="password",
                                help="至少 10 碼，須含大寫英文、小寫英文及數字")
        confirm_pwd = st.text_input("確認新密碼", type="password")
        submitted = st.form_submit_button("確認修改", type="primary")

    if submitted:
        if not old_pwd or not new_pwd or not confirm_pwd:
            error_box("請填寫所有欄位。")
            return
        if new_pwd != confirm_pwd:
            error_box("新密碼與確認密碼不一致。")
            return
        ok, msg = validate_password_complexity(new_pwd)
        if not ok:
            error_box(msg)
            return
        ok, err = change_password(user_id, old_pwd, new_pwd)
        if ok:
            st.success("✓ 密碼已修改，請重新登入。")
            st.session_state["current_page"] = "login"
            st.rerun()
        else:
            error_box(err)


def _render_items(user_id: str) -> None:
    require_permission(user_id, P.ITEM_VIEW)
    st.subheader("誦經項目管理")

    with st.expander("＋ 新增誦經項目", expanded=False):
        with st.form("add_item_form"):
            new_name = st.text_input("項目名稱（必填，最多 30 字）", max_chars=40)
            new_note = st.text_input("備註（選填，最多 100 字）", max_chars=110)
            add_ok = st.form_submit_button("新增", type="primary")
        if add_ok:
            require_permission(user_id, P.ITEM_CREATE)
            ok, msg, _ = create_item(user_id, new_name, new_note)
            if ok:
                success_box("已新增誦經項目。")
                st.rerun()
            else:
                error_box(msg)

    gold_divider()
    items = get_user_items(user_id, include_archived=True)
    if not items:
        info_box("尚未建立任何誦經項目。")
        return

    active_items = [i for i in items if not i.get("is_archived")]
    archived_items = [i for i in items if i.get("is_archived")]

    def _render_item_row(item: dict) -> None:
        is_archived = item.get("is_archived", False)
        col_name, col_actions = st.columns([3, 2])
        with col_name:
            st.markdown(
                f'<b class="item-name" style="font-size:1.1rem">{item["name"]}</b>',
                unsafe_allow_html=True)
            if item.get("note"):
                st.markdown(f'<span style="color:#8a7060;font-size:0.95rem">{item["note"]}</span>',
                            unsafe_allow_html=True)
        with col_actions:
            if st.button("✏ 編輯", key=f"edit_{item['id']}"):
                st.session_state[f"editing_{item['id']}"] = True
                st.rerun()
            if not is_archived:
                if st.button("封存", key=f"arch_{item['id']}"):
                    require_permission(user_id, P.ITEM_ARCHIVE)
                    ok, msg = archive_item(user_id, item["id"], True)
                    success_box("已封存。") if ok else error_box(msg)
                    st.rerun()
            else:
                if st.button("取消封存", key=f"unarch_{item['id']}"):
                    require_permission(user_id, P.ITEM_ARCHIVE)
                    ok, msg = archive_item(user_id, item["id"], False)
                    success_box("已取消封存。") if ok else error_box(msg)
                    st.rerun()

        if st.session_state.get(f"editing_{item['id']}"):
            with st.form(f"edit_form_{item['id']}"):
                new_name = st.text_input("名稱", value=item["name"], max_chars=40)
                new_note = st.text_input("備註", value=item.get("note", ""), max_chars=110)
                col_save, col_cancel = st.columns(2)
                save = col_save.form_submit_button("儲存", type="primary")
                cancel = col_cancel.form_submit_button("取消")
            if save:
                require_permission(user_id, P.ITEM_EDIT)
                ok, msg = update_item(user_id, item["id"], new_name, new_note)
                if ok:
                    success_box("已更新。")
                    st.session_state.pop(f"editing_{item['id']}", None)
                else:
                    error_box(msg)
                st.rerun()
            if cancel:
                st.session_state.pop(f"editing_{item['id']}", None)
                st.rerun()

    if active_items:
        st.markdown("**使用中的項目**")
        for item in active_items:
            _render_item_row(item)
            gold_divider()

    if archived_items:
        with st.expander(f"封存的項目（{len(archived_items)} 個）"):
            for item in archived_items:
                _render_item_row(item)


def render(user_doc: dict, force_change_password: bool = False) -> None:
    user_id = user_doc["id"]
    admin = is_superadmin(user_id)
    render_nav("member_center", is_admin=admin)

    if force_change_password:
        page_header("🔒 請設定密碼", "首次登入必須修改密碼")
        _render_change_password(user_id, force=True)
        return

    page_header("👤 會員中心")
    tab1, tab2, tab3 = st.tabs(["個人資料", "修改密碼", "誦經項目"])
    with tab1:
        _render_profile(user_doc)
    with tab2:
        _render_change_password(user_id)
    with tab3:
        _render_items(user_id)
