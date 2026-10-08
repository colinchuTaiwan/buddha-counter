"""
pages/member_count.py
計數頁面 — RTDB 版本。
"""
import streamlit as st
from modules.counting import add_count, undo_last_count, get_today_count, get_total_count, generate_event_id
from modules.recitation import get_user_items, get_item
from modules.rbac import require_permission, P, is_superadmin
from modules.ui_components import (
    page_header, render_nav, render_wakelock_widget,
    success_box, error_box, unsaved_box, gold_divider, info_box
)


def render_item_select(user_id: str) -> None:
    page_header("🕊 選擇誦經項目", "請選擇要計數的誦經項目")
    items = get_user_items(user_id, include_archived=False)
    if not items:
        info_box("您尚未建立任何誦經項目，請先前往「會員中心」新增。")
        return
    for item in items:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(
                f'<div class="item-name" style="font-size:1.2rem;font-weight:600;padding:0.4rem 0">'
                f'{item["name"]}</div>', unsafe_allow_html=True)
            if item.get("note"):
                st.markdown(f'<div style="color:#8a7060;font-size:0.95rem">{item["note"]}</div>',
                            unsafe_allow_html=True)
        with col2:
            if st.button("開始計數", key=f"start_{item['id']}", use_container_width=True):
                st.session_state["selected_item_id"] = item["id"]
                st.session_state["selected_item_name"] = item["name"]
                st.session_state["count_event_id"] = generate_event_id()
                st.session_state["count_status"] = None
                st.rerun()
        gold_divider()


def render_count_page(user_id: str, item_id: str) -> None:
    require_permission(user_id, P.COUNT_ADD)
    item = get_item(user_id, item_id)
    if not item:
        error_box("找不到此誦經項目。")
        if st.button("← 返回選擇"):
            st.session_state.pop("selected_item_id", None)
            st.rerun()
        return

    today_count = get_today_count(user_id, item_id)
    total_count = get_total_count(user_id, item_id)
    wakelock_enabled = st.session_state.get("wakelock_enabled", True)

    col_back, col_title = st.columns([1, 4])
    with col_back:
        if st.button("← 返回"):
            st.session_state.pop("selected_item_id", None)
            st.session_state.pop("count_event_id", None)
            st.session_state["count_status"] = None
            st.rerun()
    with col_title:
        st.markdown(f'<h2 class="item-name" style="margin:0">{item["name"]}</h2>',
                    unsafe_allow_html=True)

    gold_divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="count-number">{today_count}</div>'
                    f'<div class="count-label">今日次數</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="count-number" style="color:#7a6048">{total_count}</div>'
                    f'<div class="count-label">累計次數</div>', unsafe_allow_html=True)

    gold_divider()

    count_status = st.session_state.get("count_status")
    if count_status == "success":
        success_box("已記錄，阿彌陀佛 🙏")
        st.session_state["count_status"] = None
    elif count_status == "failed":
        unsaved_box()
    elif count_status == "undo_success":
        success_box("已撤銷最近一次計數")
        st.session_state["count_status"] = None
    elif count_status == "undo_failed":
        error_box(st.session_state.get("count_error", "撤銷失敗"))
        st.session_state["count_status"] = None

    # 大型計數按鈕
    st.markdown("""<style>
    div[data-testid="stButton"] button[kind="primary"] {
        font-size: 2rem !important; min-height: 120px !important;
        border-radius: 50% !important; width: 180px !important;
        height: 180px !important;
    }
    </style>""", unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        event_id = st.session_state.get("count_event_id", generate_event_id())
        if st.button("🙏\n念誦", key=f"count_btn_{event_id[:8]}",
                     use_container_width=True, type="primary"):
            ok, err = add_count(user_id, item_id, event_id)
            if ok:
                st.session_state["count_status"] = "success"
                st.session_state["count_event_id"] = generate_event_id()
            else:
                st.session_state["count_status"] = "failed"
                st.session_state["count_error"] = err
            st.rerun()

    gold_divider()

    with st.expander("撤銷最近一次計數"):
        st.warning("⚠ 確定要撤銷最近一次計數嗎？")
        if st.button("確定撤銷", key="confirm_undo"):
            require_permission(user_id, P.COUNT_UNDO)
            ok, err = undo_last_count(user_id, item_id)
            st.session_state["count_status"] = "undo_success" if ok else "undo_failed"
            if not ok:
                st.session_state["count_error"] = err
            st.rerun()

    gold_divider()
    st.markdown("#### 螢幕常亮設定")
    new_wl = st.toggle("保持螢幕常亮", value=wakelock_enabled, key="wl_toggle")
    if new_wl != wakelock_enabled:
        st.session_state["wakelock_enabled"] = new_wl
        st.rerun()
    render_wakelock_widget(new_wl)


def render(user_doc: dict) -> None:
    user_id = user_doc["id"]
    admin = is_superadmin(user_id)
    render_nav("count_select", is_admin=admin)
    selected_item_id = st.session_state.get("selected_item_id")
    if selected_item_id:
        render_count_page(user_id, selected_item_id)
    else:
        render_item_select(user_id)
