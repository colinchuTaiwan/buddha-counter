"""
pages/admin_audit.py
管理後台：操作紀錄 + 錯誤紀錄 — 完整版。
"""
import streamlit as st
from modules.audit import get_audit_logs, get_error_logs
from modules.rbac import require_permission, P, is_superadmin
from modules.ui_components import page_header, render_admin_nav, gold_divider, info_box


ACTION_OPTIONS = {
    "": "全部操作",
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
}

ERROR_TYPE_OPTIONS = {
    "": "全部類型",
    "database_error": "資料庫錯誤",
    "auth_error": "驗證錯誤",
    "permission_error": "權限錯誤",
    "delete_user_error": "刪除會員錯誤",
    "system_error": "系統錯誤",
}


def _render_audit_logs(admin_id: str) -> None:
    """操作紀錄頁籤。"""
    col1, col2 = st.columns([2, 1])
    with col1:
        action_filter = st.selectbox(
            "篩選操作類型",
            options=list(ACTION_OPTIONS.keys()),
            format_func=lambda x: ACTION_OPTIONS[x],
            key="audit_action_filter",
        )
    with col2:
        limit = st.selectbox("顯示筆數", [20, 50, 100], key="audit_limit")

    logs = get_audit_logs(limit=limit, action_filter=action_filter)

    if not logs:
        info_box("目前沒有操作紀錄。")
        return

    st.markdown(f"<p style='color:#8a7060'>顯示 {len(logs)} 筆紀錄</p>", unsafe_allow_html=True)

    for i, log in enumerate(logs):
        ts = log.get("timestamp", "")[:19].replace("T", " ")
        action = log.get("action", "")
        action_label = log.get("action_label", action)
        target_type = log.get("target_type", "")
        target_id = log.get("target_id", "")
        result = log.get("result", "")
        actor = log.get("actor_id", "")
        detail = log.get("detail", {})

        result_color = "#5a8a5a" if result == "success" else "#c05050"
        result_label = "✓ 成功" if result == "success" else "✗ 失敗"

        with st.container():
            st.markdown(f"""
            <div class="card" style="margin-bottom:0.3rem;padding:0.9rem 1.2rem">
                <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.3rem">
                    <div>
                        <b style="font-size:1.05rem">{action_label}</b>
                        <span style="color:#8a7060;font-size:0.88rem">
                            　{target_type} / <code>{target_id[:12]}...</code>
                        </span>
                    </div>
                    <span style="color:{result_color};font-weight:700">{result_label}</span>
                </div>
                <div style="color:#8a7060;font-size:0.85rem;margin-top:0.2rem">
                    🕐 {ts}　　👤 操作者：<code>{actor[:16]}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 詳細內容展開
            if detail:
                with st.expander("查看詳細內容", expanded=False):
                    for k, v in detail.items():
                        st.markdown(f"**{k}**：{v}")

        gold_divider()


def _render_error_logs(admin_id: str) -> None:
    """錯誤紀錄頁籤。"""
    col1, col2 = st.columns([2, 1])
    with col1:
        error_filter = st.selectbox(
            "篩選錯誤類型",
            options=list(ERROR_TYPE_OPTIONS.keys()),
            format_func=lambda x: ERROR_TYPE_OPTIONS.get(x, x),
            key="error_type_filter",
        )
    with col2:
        limit = st.selectbox("顯示筆數", [20, 50, 100], key="error_limit")

    logs = get_error_logs(limit=limit, error_type_filter=error_filter)

    if not logs:
        info_box("目前沒有錯誤紀錄。")
        return

    st.markdown(f"<p style='color:#8a7060'>顯示 {len(logs)} 筆紀錄</p>", unsafe_allow_html=True)

    for log in logs:
        ts = log.get("timestamp", "")[:19].replace("T", " ")
        error_type = log.get("error_type", "")
        message = log.get("message", "")
        user_id = log.get("user_id", "system")
        tb = log.get("traceback", "")

        with st.container():
            st.markdown(f"""
            <div class="card" style="margin-bottom:0.3rem;padding:0.9rem 1.2rem;
                border-left:4px solid #c05050">
                <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.3rem">
                    <b style="color:#c05050;font-size:1rem">{error_type}</b>
                    <span style="color:#8a7060;font-size:0.85rem">🕐 {ts}</span>
                </div>
                <div style="margin-top:0.3rem;font-size:0.95rem">{message}</div>
                <div style="color:#8a7060;font-size:0.85rem;margin-top:0.2rem">
                    👤 使用者：<code>{user_id[:16]}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 詳細堆疊資訊
            if tb:
                with st.expander("查看詳細錯誤內容", expanded=False):
                    st.code(tb, language="python")

        gold_divider()


def render(user_doc: dict) -> None:
    admin_id = user_doc["id"]
    require_permission(admin_id, P.AUDIT_VIEW)
    render_admin_nav("log")
    page_header("📋 系統紀錄", "操作紀錄與錯誤紀錄")

    tab1, tab2 = st.tabs(["📝 操作紀錄", "🚨 錯誤紀錄"])

    with tab1:
        _render_audit_logs(admin_id)

    with tab2:
        _render_error_logs(admin_id)
