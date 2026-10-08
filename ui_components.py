"""
modules/ui_components.py
共用 UI 元件、CSS 樣式、佛教禪學風格設計。
採米白、暖灰、木質棕、柔和金色。
正文字體不小於 20px，主要按鈕不小於 24px。
"""
import streamlit as st


# ── 全域 CSS ───────────────────────────────────────────────────────────────────

def inject_global_css() -> None:
    st.markdown("""
<style>
/* Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@300;400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');

/* ── Reset & Base ── */
html, body, [class*="css"] {
    font-family: 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
    font-size: 18px;
    color: #3d2b1f;
}
.stApp {
    background-color: #f7f3ed;
    background-image:
        radial-gradient(ellipse at top left, #f0e8dc 0%, transparent 60%),
        radial-gradient(ellipse at bottom right, #e8ddd0 0%, transparent 60%);
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 2rem;
    max-width: 900px;
}

/* ── Typography ── */
h1, h2, h3 {
    font-family: 'Noto Serif TC', serif;
    color: #5c3d1e;
}
h1 { font-size: 2rem; font-weight: 700; }
h2 { font-size: 1.6rem; font-weight: 600; }
h3 { font-size: 1.3rem; font-weight: 500; }
p, li, label, .stTextInput label, .stSelectbox label {
    font-size: 1.1rem !important;
    line-height: 1.8;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    font-size: 1.1rem !important;
    border-radius: 8px !important;
    border-color: #c8b49a !important;
    background-color: #fdfaf6 !important;
    color: #3d2b1f !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #9e7a4e !important;
    box-shadow: 0 0 0 2px rgba(158,122,78,0.25) !important;
}

/* ── General buttons ── */
.stButton > button {
    font-family: 'Noto Sans TC', sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: 2px solid #c8b49a !important;
    background-color: #f7f0e6 !important;
    color: #5c3d1e !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.2s ease !important;
    min-height: 44px !important;
    cursor: pointer !important;
}
.stButton > button:hover {
    background-color: #e8d8c0 !important;
    border-color: #9e7a4e !important;
    color: #3d2b1f !important;
}
.stButton > button:focus {
    outline: 3px solid #c8a86a !important;
    outline-offset: 2px !important;
}

/* ── Primary button (計數按鈕專用) ── */
.stButton > button[kind="primary"] {
    background-color: #9e7a4e !important;
    color: #fdfaf6 !important;
    border-color: #7a5c35 !important;
    font-size: 1.35rem !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #7a5c35 !important;
}

/* ── Cards ── */
.card {
    background: rgba(253, 250, 246, 0.92);
    border: 1px solid #ddd0be;
    border-radius: 12px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 12px rgba(60,40,20,0.07);
}
.card-gold {
    border-left: 5px solid #c8a86a;
}

/* ── Count display ── */
.count-number {
    font-family: 'Noto Serif TC', serif;
    font-size: 4.5rem;
    font-weight: 700;
    color: #9e7a4e;
    text-align: center;
    letter-spacing: 4px;
    line-height: 1.1;
    text-shadow: 1px 1px 4px rgba(0,0,0,0.08);
}
.count-label {
    font-size: 1rem;
    color: #8a7060;
    text-align: center;
    margin-top: 0.2rem;
}
.count-button-wrap {
    display: flex;
    justify-content: center;
    margin: 1.5rem 0;
}

/* ── Status messages ── */
.msg-success {
    background: #f0f7f0;
    border-left: 4px solid #5a8a5a;
    color: #2d5a2d;
    padding: 0.8rem 1.2rem;
    border-radius: 6px;
    font-size: 1.05rem;
    font-weight: 600;
}
.msg-error {
    background: #fdf0f0;
    border-left: 4px solid #c05050;
    color: #7a2020;
    padding: 0.8rem 1.2rem;
    border-radius: 6px;
    font-size: 1.05rem;
    font-weight: 600;
}
.msg-info {
    background: #f5f0ea;
    border-left: 4px solid #c8a86a;
    color: #5c3d1e;
    padding: 0.8rem 1.2rem;
    border-radius: 6px;
    font-size: 1.05rem;
}
.msg-unsaved {
    background: #fff8e8;
    border: 2px dashed #c8a86a;
    color: #7a5c20;
    padding: 0.8rem 1.2rem;
    border-radius: 6px;
    font-size: 1.1rem;
    font-weight: 700;
    text-align: center;
}

/* ── Navigation ── */
.nav-link {
    display: inline-block;
    padding: 0.6rem 1.2rem;
    font-size: 1.05rem;
    font-weight: 600;
    color: #5c3d1e;
    text-decoration: none;
    border-radius: 6px;
    cursor: pointer;
}
.nav-link:hover { background: #e8d8c0; }
.nav-link.active {
    background: #9e7a4e;
    color: #fdfaf6;
}

/* ── Table/form responsive ── */
.stDataFrame, .dataframe-container {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

/* ── Wake Lock indicator ── */
.wakelock-on  { color: #5a8a5a; font-weight: 600; font-size: 0.95rem; }
.wakelock-off { color: #8a7060; font-size: 0.95rem; }

/* ── Long text wrap ── */
.item-name {
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
}

/* ── Divider ── */
.gold-divider {
    border: none;
    border-top: 1px solid #c8a86a;
    margin: 1.5rem 0;
    opacity: 0.4;
}

/* ── Mobile responsive ── */
@media (max-width: 480px) {
    .count-number { font-size: 3.5rem; }
    h1 { font-size: 1.6rem; }
    h2 { font-size: 1.3rem; }
    .card { padding: 1.2rem 1rem; }
    .stButton > button { font-size: 1rem !important; }
}
@media (max-width: 768px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
}

/* ── Screen keyboard focus accessibility ── */
a:focus, button:focus, input:focus, select:focus, textarea:focus {
    outline: 3px solid #c8a86a;
    outline-offset: 2px;
}
</style>
""", unsafe_allow_html=True)


# ── Wake Lock JavaScript 元件 ─────────────────────────────────────────────────

WAKELOCK_JS = """
<script>
(function() {
    let wakeLock = null;
    const enabled = {enabled};

    async function requestWakeLock() {
        if (!('wakeLock' in navigator)) {
            document.getElementById('wl-status').textContent = '此裝置不支援螢幕常亮';
            document.getElementById('wl-status').className = 'wakelock-off';
            return;
        }
        try {
            wakeLock = await navigator.wakeLock.request('screen');
            document.getElementById('wl-status').textContent = '✓ 螢幕常亮已啟用';
            document.getElementById('wl-status').className = 'wakelock-on';
            wakeLock.addEventListener('release', () => {
                document.getElementById('wl-status').textContent = '螢幕常亮已釋放（裝置省電）';
                document.getElementById('wl-status').className = 'wakelock-off';
            });
        } catch (err) {
            document.getElementById('wl-status').textContent =
                '此裝置目前無法保持螢幕常亮，請至裝置設定調整螢幕休眠時間';
            document.getElementById('wl-status').className = 'wakelock-off';
        }
    }

    async function releaseWakeLock() {
        if (wakeLock) {
            await wakeLock.release();
            wakeLock = null;
        }
        document.getElementById('wl-status').textContent = '螢幕常亮已關閉';
        document.getElementById('wl-status').className = 'wakelock-off';
    }

    // 頁面可見性變更：返回時重新取得
    document.addEventListener('visibilitychange', async () => {
        if (enabled && document.visibilityState === 'visible') {
            await requestWakeLock();
        }
    });

    if (enabled) {
        requestWakeLock();
    }
})();
</script>
<p id="wl-status" class="wakelock-off">正在初始化螢幕常亮…</p>
"""


def render_wakelock_widget(enabled: bool) -> None:
    """
    渲染螢幕常亮控制元件（純 HTML/JS，不使用自訂元件）。
    顯示實際啟用狀態，不得只切換開關就宣稱已啟用。
    """
    js = WAKELOCK_JS.replace("{enabled}", "true" if enabled else "false")
    st.markdown(js, unsafe_allow_html=True)


# ── 通用 UI helpers ───────────────────────────────────────────────────────────

def success_box(msg: str) -> None:
    st.markdown(f'<div class="msg-success">✓ {msg}</div>', unsafe_allow_html=True)


def error_box(msg: str) -> None:
    st.markdown(f'<div class="msg-error">✗ {msg}</div>', unsafe_allow_html=True)


def info_box(msg: str) -> None:
    st.markdown(f'<div class="msg-info">ℹ {msg}</div>', unsafe_allow_html=True)


def unsaved_box() -> None:
    st.markdown(
        '<div class="msg-unsaved">⚠ 尚未儲存，請重試</div>',
        unsafe_allow_html=True,
    )


def gold_divider() -> None:
    st.markdown('<hr class="gold-divider">', unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<h1>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<p style='color:#8a7060;font-size:1rem;margin-top:-0.8rem'>{subtitle}</p>",
                    unsafe_allow_html=True)
    gold_divider()


def render_nav(current_page: str, is_admin: bool = False) -> None:
    """渲染頂部導覽列。"""
    pages = [
        ("count_select", "🕊 開始計數"),
        ("stats", "📊 統計紀錄"),
        ("member_center", "👤 會員中心"),
    ]
    if is_admin:
        pages.append(("admin_members", "⚙ 管理後台"))

    cols = st.columns(len(pages) + 1)
    for i, (page_key, label) in enumerate(pages):
        active = "active" if current_page == page_key else ""
        if cols[i].button(label, key=f"nav_{page_key}",
                          use_container_width=True,
                          type="primary" if active else "secondary"):
            st.session_state["current_page"] = page_key
            st.rerun()

    if cols[-1].button("🚪 登出", key="nav_logout", use_container_width=True):
        from modules.auth import logout
        logout()
        st.session_state["current_page"] = "login"
        st.rerun()
