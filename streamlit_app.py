"""
streamlit_app.py
線上念佛計數器 — 主程式入口（Firebase Realtime Database 版本）
"""
import logging
import streamlit as st

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="念佛計數器",
    page_icon="🙏",
    layout="centered",
    initial_sidebar_state="collapsed",
)

from modules.ui_components import inject_global_css
inject_global_css()

# ── Firebase RTDB 初始化 ───────────────────────────────────────────────────────
try:
    from modules.db import _init_firebase
    _init_firebase()
except Exception as e:
    st.error(f"🚨 Firebase 初始化失敗：{e}\n\n請確認 Streamlit Cloud Secrets 設定正確。")
    st.stop()


# ── 登入頁面 ───────────────────────────────────────────────────────────────────

def render_login_page() -> None:
    st.markdown("""
        <div style='text-align:center;padding:2rem 0 1rem'>
            <span style='font-size:3rem'>🙏</span>
            <h1 style='font-family:"Noto Serif TC",serif;font-size:2rem;
                color:#5c3d1e;margin:0.5rem 0'>念佛計數器</h1>
            <p style='color:#8a7060;font-size:1.05rem'>慈悲喜捨，精進修行</p>
        </div>
    """, unsafe_allow_html=True)

    is_admin_login = st.session_state.get("admin_mode", False)
    col_user, col_admin = st.columns([3, 1])
    if col_admin.button("管理後台" if not is_admin_login else "← 會員登入",
                        key="toggle_admin_mode"):
        st.session_state["admin_mode"] = not is_admin_login
        st.rerun()

    if is_admin_login:
        st.markdown(
            '<div style="background:#f5f0ea;border-left:4px solid #c8a86a;'
            'padding:0.5rem 1rem;border-radius:6px;margin-bottom:1rem">'
            '⚙ 管理後台登入</div>',
            unsafe_allow_html=True,
        )

    with st.form("login_form"):
        username = st.text_input("帳號", placeholder="請輸入帳號",
                                 max_chars=50, autocomplete="username")
        password = st.text_input("密碼", type="password", placeholder="請輸入密碼",
                                 max_chars=128, autocomplete="current-password")
        submitted = st.form_submit_button("登入", type="primary", use_container_width=True)

    if submitted:
        if not username.strip() or not password:
            st.error("請填寫帳號與密碼。")
            return

        from modules.auth import login
        ok, err = login(username, password)
        if not ok:
            st.error(err)
            return

        user_id = st.session_state["user_id"]

        if st.session_state.get("must_change_password"):
            st.session_state["current_page"] = "force_change_password"
            st.rerun()

        from modules.rbac import has_permission, P
        if is_admin_login and not has_permission(user_id, P.USER_VIEW):
            from modules.auth import logout
            logout()
            st.error("您沒有管理後台的存取權限。")
            return

        st.session_state["current_page"] = "admin_members" if is_admin_login else "count_select"
        st.rerun()


def render_force_change_password() -> None:
    from modules.auth import check_session
    from modules.db import rtdb_get

    valid, _ = check_session()
    if not valid:
        st.session_state["current_page"] = "login"
        st.rerun()

    user_id = st.session_state.get("user_id")
    user_data = rtdb_get(f"/users/{user_id}")
    if not user_data:
        st.session_state["current_page"] = "login"
        st.rerun()

    user_data["id"] = user_id
    from pages.member_center import render as render_center
    render_center(user_data, force_change_password=True)


def route() -> None:
    page = st.session_state.get("current_page", "login")

    if page == "login":
        render_login_page()
        return

    if page == "force_change_password":
        render_force_change_password()
        return

    from modules.auth import check_session, logout
    from modules.db import rtdb_get

    valid, _ = check_session()
    if not valid:
        st.session_state["current_page"] = "login"
        st.rerun()

    user_id = st.session_state["user_id"]
    user_data = rtdb_get(f"/users/{user_id}")
    if not user_data:
        logout()
        st.session_state["current_page"] = "login"
        st.rerun()

    user_data["id"] = user_id

    if user_data.get("must_change_password") and page != "force_change_password":
        st.session_state["current_page"] = "force_change_password"
        st.rerun()

    if page in ("count_select", "counting"):
        from pages.member_count import render
        render(user_data)
    elif page == "stats":
        from pages.member_stats import render
        render(user_data)
    elif page == "member_center":
        from pages.member_center import render
        render(user_data)
    elif page == "admin_members":
        from pages.admin_members import render
        render(user_data)
    elif page == "admin_roles":
        from pages.admin_roles import render
        render(user_data)
    elif page == "admin_audit":
        from pages.admin_audit import render
        render(user_data)
    else:
        st.session_state["current_page"] = "count_select"
        st.rerun()


# ── 主程式入口（含全域錯誤捕捉與記錄）────────────────────────────────────────
try:
    route()
except Exception as e:
    logger.exception("未預期的頂層錯誤")
    # 記錄到 RTDB error_logs
    try:
        from modules.audit import log_error
        user_id = st.session_state.get("user_id")
        log_error("system_error", str(e), user_id=user_id, exc=e)
    except Exception:
        pass
    st.error("系統發生未預期的錯誤，請稍後再試或聯絡管理員。")
    if st.button("返回首頁"):
        from modules.auth import logout
        logout()
        st.session_state["current_page"] = "login"
        st.rerun()
