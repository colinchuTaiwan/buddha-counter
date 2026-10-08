"""
tools/init_superadmin.py
初始化第一位最高管理者。
完全獨立腳本，不依賴 modules/ 任何檔案，直接讀取 JSON 金鑰。

用法：
    python tools\init_superadmin.py --key 金鑰檔案.json
"""
import sys
import uuid
import getpass
import argparse
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True, help="Firebase 服務帳戶 JSON 金鑰路徑")
    args = parser.parse_args()

    print("=" * 60)
    print("念佛計數器 — 最高管理者初始化")
    print("=" * 60)

    key_path = Path(args.key)
    if not key_path.exists():
        print(f"✗ 找不到金鑰檔案：{key_path}")
        sys.exit(1)

    # ── 直接初始化 Firebase，不透過任何 modules ──
    import firebase_admin
    from firebase_admin import credentials, db as rtdb_module

    # 清除舊的 app（避免重複初始化錯誤）
    if firebase_admin._apps:
        firebase_admin.delete_app(firebase_admin.get_app())

    try:
        with open(key_path, encoding="utf-8") as f:
            key_data = json.load(f)
        project_id = key_data.get("project_id", "")
        print(f"✓ 讀取金鑰成功，專案：{project_id}")
    except Exception as e:
        print(f"✗ 讀取金鑰檔案失敗：{e}")
        sys.exit(1)

    db_url = input(
        f"\n請輸入 Realtime Database URL（直接按 Enter 使用預設）\n"
        f"預設：https://{project_id}-default-rtdb.asia-southeast1.firebasedatabase.app\n> "
    ).strip()
    if not db_url:
        db_url = f"https://{project_id}-default-rtdb.asia-southeast1.firebasedatabase.app"

    try:
        cred = credentials.Certificate(str(key_path))
        firebase_admin.initialize_app(cred, {"databaseURL": db_url})
        print(f"✓ Firebase 連線成功")
    except Exception as e:
        print(f"✗ Firebase 連線失敗：{e}")
        sys.exit(1)

    now = datetime.now(ZoneInfo("Asia/Taipei")).isoformat()

    # ── 確認是否已有最高管理者 ──
    try:
        user_roles = rtdb_module.reference("/user_roles").get() or {}
        for uid, roles in user_roles.items():
            if isinstance(roles, dict) and roles.get("superadmin"):
                user = rtdb_module.reference(f"/users/{uid}").get() or {}
                if user.get("is_active"):
                    print(f"\n✓ 已存在最高管理者（帳號：{user.get('username', uid)}）")
                    print("  若需重設密碼，請登入後台使用「重設密碼」功能。")
                    return
    except Exception:
        pass

    # ── 建立預設角色 ──
    DEFAULT_PERMS = {
        "member": ["item_view","item_create","item_edit","item_archive",
                   "count_add","count_undo","stats_self"],
        "account_admin": ["user_view","user_create","user_edit",
                          "user_disable","user_reset_password"],
        "superadmin": ["item_view","item_create","item_edit","item_archive",
                       "count_add","count_undo","stats_self","stats_view_all",
                       "user_view","user_create","user_edit","user_disable",
                       "user_reset_password","user_unlock","role_manage",
                       "audit_view","system_settings"],
    }
    for role_code, perms in DEFAULT_PERMS.items():
        rtdb_module.reference(f"/roles/{role_code}").set({
            "code": role_code, "is_active": True, "created_at": now,
        })
        for perm in perms:
            rtdb_module.reference(f"/role_permissions/{role_code}/{perm}").set(True)
    print("✓ 預設角色已建立")

    # ── 輸入帳號資訊 ──
    print()
    username = input("請輸入管理者帳號（英文小寫或數字）：").strip().lower()
    if not username:
        print("✗ 帳號不得為空。")
        sys.exit(1)

    display_name = input("請輸入顯示名稱（例如：系統管理員）：").strip()
    if not display_name:
        display_name = username

    # ── 輸入並驗證密碼 ──
    while True:
        password = getpass.getpass("請設定密碼（至少10碼，含大小寫英文及數字）：")
        confirm = getpass.getpass("再次確認密碼：")
        if password != confirm:
            print("✗ 兩次密碼不一致。")
            continue
        if len(password) < 10:
            print("✗ 密碼至少需要 10 個字元。")
            continue
        if not any(c.isupper() for c in password):
            print("✗ 密碼必須包含大寫英文字母。")
            continue
        if not any(c.islower() for c in password):
            print("✗ 密碼必須包含小寫英文字母。")
            continue
        if not any(c.isdigit() for c in password):
            print("✗ 密碼必須包含數字。")
            continue
        break

    # ── 雜湊密碼並寫入 RTDB ──
    from argon2 import PasswordHasher
    ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
    pwd_hash = ph.hash(password)

    user_id = str(uuid.uuid4())
    rtdb_module.reference(f"/users/{user_id}").set({
        "username": username,
        "display_name": display_name,
        "password_hash": pwd_hash,
        "must_change_password": False,
        "is_active": True,
        "role": "superadmin",
        "failed_login_count": 0,
        "lockout_until": None,
        "session_token": None,
        "created_at": now,
        "created_by": "init_tool",
    })
    rtdb_module.reference(f"/username_index/{username}").set(user_id)
    rtdb_module.reference(f"/user_roles/{user_id}/superadmin").set(True)

    print()
    print("=" * 60)
    print(f"✓ 最高管理者帳號已建立！")
    print(f"  帳號：{username}")
    print(f"  顯示名稱：{display_name}")
    print(f"  請妥善保管密碼，系統不儲存明文。")
    print("=" * 60)


if __name__ == "__main__":
    main()
