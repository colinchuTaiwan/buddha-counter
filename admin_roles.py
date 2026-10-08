"""
pages/admin_roles.py
管理後台：角色與權限管理（功能樹、角色、綁定）。
僅最高管理者（ROLE_MANAGE 權限）可存取。
"""
import streamlit as st

from modules.audit import log_action
from modules.db import db, now_tw, doc_to_dict
from modules.rbac import (
    require_permission, P, FEATURE_TREE, DEFAULT_ROLES,
    invalidate_permission_cache,
)
from modules.ui_components import (
    page_header, render_nav, gold_divider, success_box, error_box, info_box
)


def _render_feature_tree() -> None:
    """顯示功能樹（唯讀，反映實際已實作功能）。"""
    st.subheader("功能樹（已實作功能與權限代碼）")
    st.caption("功能樹設定僅限已實作功能，不支援輸入任意程式碼。")
    for module in FEATURE_TREE:
        with st.expander(f"📁 {module['name']}"):
            for feat in module.get("children", []):
                st.markdown(
                    f"　　<code>{feat['code']}</code>　{feat['name']}",
                    unsafe_allow_html=True,
                )


def _render_role_permissions(admin_id: str) -> None:
    """角色權限綁定管理。"""
    st.subheader("角色權限設定")

    # 取得所有角色
    try:
        roles = [doc_to_dict(d) for d in db().collection("roles").get()]
    except Exception:
        error_box("讀取角色失敗。")
        return

    for role in roles:
        role_code = role.get("code", "")
        with st.expander(f"角色：{role.get('display_name', role_code)}（{role_code}）"):
            # 取得此角色的現有權限
            try:
                role_perms = [
                    d.to_dict().get("permission_code", "")
                    for d in db().collection("role_permissions")
                    .where("role_code", "==", role_code)
                    .where("is_active", "==", True)
                    .get()
                ]
            except Exception:
                role_perms = []

            # 列出所有可選權限
            all_perms = []
            for module in FEATURE_TREE:
                for feat in module.get("children", []):
                    all_perms.append((feat["code"], f"{module['name']} > {feat['name']}"))

            st.markdown("**目前擁有的權限：**")
            selected = []
            for code, label in all_perms:
                checked = st.checkbox(
                    label,
                    value=(code in role_perms),
                    key=f"perm_{role_code}_{code}",
                )
                if checked:
                    selected.append(code)

            if st.button("儲存角色權限", key=f"save_role_{role_code}", type="primary"):
                _save_role_permissions(admin_id, role_code, selected)
                success_box(f"角色 {role_code} 的權限已更新。")
                st.rerun()


def _save_role_permissions(admin_id: str, role_code: str, selected_perms: list) -> None:
    """儲存角色權限（全量替換）。"""
    batch = db().batch()
    col = db().collection("role_permissions")

    # 取得現有權限文件
    existing = col.where("role_code", "==", role_code).get()
    for doc in existing:
        batch.update(doc.reference, {"is_active": False})

    # 寫入新權限
    for perm_code in selected_perms:
        perm_id = f"{role_code}_{perm_code.replace('.', '_')}"
        ref = col.document(perm_id)
        batch.set(ref, {
            "role_code": role_code,
            "permission_code": perm_code,
            "is_active": True,
            "updated_at": now_tw().isoformat(),
            "updated_by": admin_id,
        }, merge=True)

    batch.commit()

    # 清除所有該角色使用者的快取
    try:
        user_roles = db().collection("user_roles").where("role_code", "==", role_code).get()
        for ur in user_roles:
            uid = ur.to_dict().get("user_id")
            if uid:
                invalidate_permission_cache(uid)
    except Exception:
        pass

    log_action(admin_id, "update_role_permissions", "role", role_code, "success",
               {"permissions": selected_perms})


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
