"""
pages/admin_audit.py
管理後台：稽核紀錄 — RTDB 版本。
"""
import streamlit as st
from modules.audit import get_audit_logs
from modules.rbac import require_permission, P, is_superadmin
from modules.ui_components import page_header, render_nav, gold_divider, info_box


def render(user_doc: dict) -> None:
    admin_id = user_doc["id"]
    require_permission(admin_id, P.AUDIT_VIEW)
    render_nav("admin_members", is_admin=True)
    page_header("📋 稽核紀錄", "系統操作歷程（唯讀）")

    limit = st.selectbox("顯示筆數", [20, 50, 100], index=0)
    logs = get_audit_logs(limit=limit)

    if not logs:
        info_box("目前沒有稽核紀錄。")
        return

    for log in logs:
        ts = log.get("timestamp", "")[:19].replace("T", " ")
        action = log.get("action", "")
        target = f"{log.get('target_type', '')} / {log.get('target_id', '')}"
        result = log.get("result", "")
        actor = log.get("actor_id", "")
        detail = log.get("detail", {})
        color = "#5a8a5a" if result == "success" else "#c05050"
        st.markdown(
            f'<div class="card" style="margin-bottom:0.5rem;font-size:0.95rem">'
            f'<b>{ts}</b>　操作者：<code>{actor[:8]}</code>　'
            f'動作：<b>{action}</b>　目標：<code>{target}</code>　'
            f'結果：<span style="color:{color}"><b>{result}</b></span>'
            f'{"　" + str(detail) if detail else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )
