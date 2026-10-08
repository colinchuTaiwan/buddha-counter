"""
pages/member_count.py
計數頁面：大型計數按鈕、今日/累計顯示、撤銷、螢幕常亮。
"""
import uuid

import streamlit as st

from modules.auth import require_login
from modules.counting import add_count, undo_last_count, get_today_count, get_total_count, generate_event_id
from modules.recitation import get_item, get_user_items
from modules.rbac import require_permission, P
from modules.ui_components import (
    inject_global_css, page_header, render_nav, render_wakelock_widget,
    success_box, error_box, unsaved_box, gold_divider, info_box
)


def render_item_select(user_id: str) -> None:
    """顯示誦經項目選擇列表。"""
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
                f'{item["name"]}</div>',
                unsafe_allow_html=True,
            )
            if item.get("note"):
                st.markdown(
                    f'<div style="color:#8a7060;font-size:0.95rem">{item["note"]}</div>',
                    unsafe_allow_html=True,
                )
        with col2:
            if st.button("開始計數", key=f"start_{item['id']}", use_container_width=True):
                st.session_state["selected_item_id"] = item["id"]
                st.session_state["selected_item_name"] = item["name"]
                # 產生新的 event_id，每次進入計數頁面重新產生
                st.session_state["count_event_id"] = generate_event_id()
                st.session_state["count_status"] = None
                st.rerun()

        gold_divider()


def render_count_page(user_id: str, item_id: str) -> None:
    """計數主頁面。"""
    require_permission(user_id, P.COUNT_ADD)

    item = get_item(user_id, item_id)
    if not item:
        error_box("找不到此誦經項目。")
        if st.button("← 返回選擇"):
            st.session_state.pop("selected_item_id", None)
            st.rerun()
        return

    item_name = item.get("name", "")
    today_count = get_today_count(user_id, item_id)
    total_count = get_total_count(user_id, item_id)

    # 螢幕常亮設定
    wakelock_enabled = st.session_state.get("wakelock_enabled", True)

    # ── 頁面上方：項目名稱 + 返回 ──
    col_back, col_title = st.columns([1, 4])
    with col_back:
        if st.button("← 返回", key="back_to_select"):
            st.session_state.pop("selected_item_id", None)
            st.session_state.pop("count_event_id", None)
            st.session_state["count_status"] = None
            st.rerun()
    with col_title:
        st.markdown(
            f'<h2 class="item-name" style="margin:0">{item_name}</h2>',
            unsafe_allow_html=True,
        )

    gold_divider()

    # ── 計數顯示 ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="count-number">{today_count}</div>'
            f'<div class="count-label">今日次數</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="count-number" style="color:#7a6048">{total_count}</div>'
            f'<div class="count-label">累計次數</div>',
            unsafe_allow_html=True,
        )

    gold_divider()

    # ── 計數狀態回饋 ──
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
        error_box(st.session_state.get("count_error", "撤銷失敗，請稍後再試。"))
        st.session_state["count_status"] = None

    # ── 大型計數按鈕 ──
    st.markdown("""
    <style>
    div[data-testid="stButton"]:has(button[title="count_btn"]) button {
        font-size: 2rem !important;
        font-weight: 700 !important;
        min-height: 100px !important;
        border-radius: 50% !important;
        width: 180px !important;
        height: 180px !important;
        background: linear-gradient(145deg, #c8a86a, #9e7a4e) !important;
        color: #fdfaf6 !important;
        border: none !important;
        box-shadow: 0 6px 20px rgba(158,122,78,0.35) !important;
        transition: transform 0.1s ease, box-shadow 0.1s ease !important;
        display: block;
        margin: 0 auto;
    }
    div[data-testid="stButton"]:has(button[title="count_btn"]) button:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 8px 28px rgba(158,122,78,0.45) !important;
    }
    div[data-testid="stButton"]:has(button[title="count_btn"]) button:active {
        transform: scale(0.97) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 計數按鈕（大型圓形）
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        # 使用唯一 key 防止重複觸發
        event_id = st.session_state.get("count_event_id", generate_event_id())
        clicked = st.button(
            "🙏\n念誦",
            key=f"count_btn_{event_id[:8]}",
            use_container_width=True,
            help="每按一次記錄一次念誦（支援 Enter 或空白鍵）",
        )

        if clicked:
            ok, err = add_count(user_id, item_id, event_id)
            if ok:
                st.session_state["count_status"] = "success"
                # 產生新 event_id 供下一次使用
                st.session_state["count_event_id"] = generate_event_id()
            else:
                st.session_state["count_status"] = "failed"
                st.session_state["count_error"] = err
            st.rerun()

    gold_divider()

    # ── 撤銷 ──
    with st.expander("撤銷最近一次計數"):
        st.warning("⚠ 確定要撤銷最近一次計數嗎？此操作無法恢復。")
        col_undo, col_cancel = st.columns(2)
        if col_undo.button("確定撤銷", key="confirm_undo", type="secondary"):
            require_permission(user_id, P.COUNT_UNDO)
            ok, err = undo_last_count(user_id, item_id)
            if ok:
                st.session_state["count_status"] = "undo_success"
            else:
                st.session_state["count_status"] = "undo_failed"
                st.session_state["count_error"] = err
            st.rerun()

    gold_divider()

    # ── 螢幕常亮 ──
    st.markdown("#### 螢幕常亮設定")
    new_wl = st.toggle(
        "保持螢幕常亮",
        value=wakelock_enabled,
        key="wl_toggle",
        help="開啟時，計數期間螢幕不會自動關閉（需瀏覽器支援）",
    )
    if new_wl != wakelock_enabled:
        st.session_state["wakelock_enabled"] = new_wl
        st.rerun()

    render_wakelock_widget(new_wl)


def render(user_doc: dict) -> None:
    """計數頁面入口。"""
    user_id = user_doc["id"]
    is_admin = st.session_state.get("user_id") and __import__(
        "modules.rbac", fromlist=["is_superadmin"]
    ).is_superadmin(user_id)

    render_nav("count_select", is_admin=is_admin)

    selected_item_id = st.session_state.get("selected_item_id")
    if selected_item_id:
        render_count_page(user_id, selected_item_id)
    else:
        render_item_select(user_id)
