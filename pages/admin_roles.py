"""
pages/admin_roles.py
管理後台：角色與權限管理 — RTDB 版本。
"""
import streamlit as st
from modules.audit import log_action
from modules.db import rtdb_get, rtdb_set, now_tw
from modules.rbac import require_permission, P, FEATURE_TREE, invalidate_permission_cache
from modules.ui_components import page_header, render_nav, gold_divider, success_box, error_box


def _render_feature_tree() -> None:
    st.subheader("功能樹（已實作功能與權限代碼）")
    for module in FEATURE_TREE:
        with st.expander(f"📁 {module['name']}"):
            for feat in module.get("children", []):
                st.markdown(f"　　<code>{feat['code']}</code>　{feat['name']}", unsafe_allow_html=True)


def _render_role_permissions(admin_id: str) -> None:
    st.subheader("角色權限設定")
    roles_data = rtdb_get("/roles") or {}

    for role_code, role_info in roles_data.items():
        if not isinstance(role_info, dict):
            continue
        with st.expander(f"角色：{role_info.get('display_name', role_code)}（{role_code}）"):
            # 取得現有權限
            role_perms = rtdb_get(f"/role_permissions/{role_code}") or {}
            current_perms = {p for p, v in role_perms.items() if v}

            all_perms = []
            for module in FEATURE_TREE:
                for feat in module.get("children", []):
                    all_perms.append((feat["code"], f"{module['name']} > {feat['name']}"))

            selected = []
            for code, label in all_perms:
                checked = st.checkbox(label, value=(code in current_perms),
                                      key=f"perm_{role_code}_{code}")
                if checked:
                    selected.append(code)

            if st.button("儲存角色權限", key=f"save_role_{role_code}", type="primary"):
                # 清除舊權限
                for code, _ in all_perms:
                    rtdb_set(f"/role_permissions/{role_code}/{code}", code in selected)

                # 清除快取
                user_roles_all = rtdb_get("/user_roles") or {}
                for uid, roles in user_roles_all.items():
                    if isinstance(roles, dict) and roles.get(role_code):
                        invalidate_permission_cache(uid)

                log_action(admin_id, "update_role_permissions", "role", role_code, "success",
                           {"permissions": selected})
                success_box(f"角色 {role_code} 的權限已更新。")
                st.rerun()


def render(user_doc: dict) -> None:
    admin_id = user_doc["id"]
    require_permission(admin_id, P.ROLE_MANAGE)
    render_nav("admin_members", is_admin=True)
    page_header("🔐 角色與權限管理")
    tab1, tab2 = st.tabs(["功能樹", "角色權限設定"])
    with tab1:
        _render_feature_tree()
    with tab2:
        _render_role_permissions(admin_id)
