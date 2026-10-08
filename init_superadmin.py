"""
tools/init_superadmin.py
初始化第一位最高管理者 — Firebase Realtime Database 版本。
在本機（有 secrets.toml）執行一次即可。
"""
import os, sys, uuid, getpass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    print("="*60)
    print("念佛計數器 — 最高管理者初始化（RTDB 版）")
    print("="*60)

    try:
        from modules.db import _init_firebase, now_tw, rtdb_get, rtdb_set
        _init_firebase()
        print("✓ Firebase RTDB 連線成功")
    except Exception as e:
        print(f"✗ Firebase 連線失敗：{e}")
        sys.exit(1)

    # 確認是否已有最高管理者
    user_roles = rtdb_get("/user_roles") or {}
    for uid, roles in user_roles.items():
        if isinstance(roles, dict) and roles.get("superadmin"):
            user = rtdb_get(f"/users/{uid}") or {}
            if user.get("is_active"):
                print(f"✓ 已存在最高管理者（{user.get('username', uid)}），無需重新初始化。")
                return

    from modules.rbac import ensure_default_roles
    ensure_default_roles()
    print("✓ 預設角色已確認")

    print()
    username = input("請輸入最高管理者帳號：").strip().lower()
    if not username:
        print("✗ 帳號不得為空。"); sys.exit(1)
    display_name = input("請輸入顯示名稱：").strip() or username

    while True:
        password = getpass.getpass("請設定密碼（至少10碼，含大小寫英文及數字）：")
        confirm  = getpass.getpass("再次確認密碼：")
        if password != confirm:
            print("✗ 兩次密碼不一致"); continue
        from modules.auth import validate_password_complexity
        ok, msg = validate_password_complexity(password)
        if not ok:
            print(f"✗ {msg}"); continue
        break

    from modules.auth import hash_password, normalize_username
    from modules.rbac import assign_role_to_user

    user_id = str(uuid.uuid4())
    now = now_tw()

    rtdb_set(f"/users/{user_id}", {
        "username": normalize_username(username),
        "display_name": display_name,
        "password_hash": hash_password(password),
        "must_change_password": False,
        "is_active": True,
        "role": "superadmin",
        "failed_login_count": 0,
        "lockout_until": None,
        "session_token": None,
        "created_at": now.isoformat(),
        "created_by": "init_tool",
    })
    rtdb_set(f"/username_index/{normalize_username(username)}", user_id)
    assign_role_to_user(user_id, "superadmin")

    print()
    print("="*60)
    print(f"✓ 最高管理者已建立！帳號：{username}")
    print("="*60)

if __name__ == "__main__":
    main()
