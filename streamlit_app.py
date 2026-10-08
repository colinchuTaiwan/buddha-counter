"""
streamlit_app.py
線上念佛計數器 — 主程式入口（Firebase Realtime Database 版本）
前台（會員）與後台（管理）路由完全分開。
"""
import logging
import streamlit as st

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="念佛計數器",
    page_icon="🙏",
    layout="centered",
    initial_sidebar_state="collapsed",
)

from modules.ui_components import inject_global_css
inject_global_css()

try:
    from modules.db import _init_firebase
    _init_firebase()
except Exception as e:
    st.error(f"🚨 Firebase 初始化失敗：{e}\n\n請確認 Streamlit Cloud Secrets 設定正確。")
    st.stop()

# ── 後台專用頁面集合 ───────────────────────────────────────────────────────────
ADMIN_PAGES = {"admin_members", "admin_roles", "admin_audit"}

# ── 前台專用頁面集合 ───────────────────────────────────────────────────────────
MEMBER_PAGES = {"count_select", "counting", "stats", "member_center"}


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
            '⚙ 管理後台登入</div>', unsafe_allow_html=True)

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

        # 強制修改密碼
        if st.session_state.get("must_change_password"):
            st.session_state["current_page"] = "force_change_password"
            st.rerun()

        from modules.rbac import has_permission, P

        if is_admin_login:
            # 後台登入：必須有 USER_VIEW 權限
            if not has_permission(user_id, P.USER_VIEW):
                from modules.auth import logout
                logout()
                st.error("您沒有管理後台的存取權限。")
                return
            st.session_state["current_page"] = "admin_members"
            st.session_state["is_admin_session"] = True  # 標記為後台 session
        else:
            # 前台登入：導向會員頁面
            st.session_state["current_page"] = "count_select"
            st.session_state["is_admin_session"] = False
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

    # ── 驗證登入狀態 ──
    from modules.auth import check_session, logout
    from modules.db import rtdb_get
    from modules.rbac import has_permission, P

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
    is_admin_session = st.session_state.get("is_admin_session", False)

    # 強制修改密碼
    if user_data.get("must_change_password") and page != "force_change_password":
        st.session_state["current_page"] = "force_change_password"
        st.rerun()

    # ── 後台路由：管理者 session 只能存取後台頁面 ──
    if is_admin_session:
        if page not in ADMIN_PAGES:
            # 試圖進入前台頁面：拒絕，導回後台
            st.session_state["current_page"] = "admin_members"
            st.rerun()

        # 後台權限確認
        if not has_permission(user_id, P.USER_VIEW):
            st.error("⛔ 您沒有存取管理後台的權限。")
            logout()
            st.session_state["current_page"] = "login"
            st.rerun()

        if page == "admin_members":
            from pages.admin_members import render
            render(user_data)
        elif page == "admin_roles":
            from pages.admin_roles import render
            render(user_data)
        elif page == "admin_audit":
            from pages.admin_audit import render
            render(user_data)
        return

    # ── 前台路由：會員 session 只能存取前台頁面 ──
    if page in ADMIN_PAGES:
        # 試圖進入後台頁面：拒絕，導回前台
        st.session_state["current_page"] = "count_select"
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
    else:
        st.session_state["current_page"] = "count_select"
        st.rerun()


# ── 主程式入口 ─────────────────────────────────────────────────────────────────
try:
    route()
except Exception as e:
    logger.exception("未預期的頂層錯誤")
    try:
        from modules.audit import log_error
        log_error("system_error", str(e), user_id=st.session_state.get("user_id"), exc=e)
    except Exception:
        pass
    st.error("系統發生未預期的錯誤，請稍後再試或聯絡管理員。")
    if st.button("返回首頁"):
        from modules.auth import logout
        logout()
        st.session_state["current_page"] = "login"
        st.rerun()
