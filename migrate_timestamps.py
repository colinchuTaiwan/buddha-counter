"""
tools/migrate_timestamps.py
舊時間資料遷移工具。
將不帶時區的舊 ISO 字串視為台灣時間，加上 +08:00。
可重複執行，不會重複處理（已遷移文件有 migrated_at 欄位）。
支援 dry-run 模式：先預覽，確認後再寫入。

用法：
    python tools/migrate_timestamps.py --dry-run    # 預覽
    python tools/migrate_timestamps.py              # 實際執行
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_and_fix_timestamp(value: str) -> str | None:
    """若時間字串無時區，加上 +08:00。已有時區則不變。"""
    if not isinstance(value, str):
        return None
    if "+08:00" in value or "+00:00" in value or "Z" in value:
        return None  # 已有時區，不需遷移
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        TAIWAN_TZ = ZoneInfo("Asia/Taipei")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            fixed = dt.replace(tzinfo=TAIWAN_TZ)
            return fixed.isoformat()
    except Exception:
        pass
    return None


def migrate_collection(client, collection_name: str, fields: list, dry_run: bool) -> int:
    """遷移指定 collection 的時間欄位。回傳遷移筆數。"""
    count = 0
    docs = client.collection(collection_name).get()
    for doc in docs:
        data = doc.to_dict()
        if data.get("migrated_at"):
            continue  # 已遷移

        updates = {}
        for field in fields:
            val = data.get(field)
            if isinstance(val, str):
                fixed = parse_and_fix_timestamp(val)
                if fixed:
                    updates[field] = fixed

        if updates:
            count += 1
            if dry_run:
                print(f"  [DRY-RUN] {collection_name}/{doc.id}: {updates}")
            else:
                from modules.db import now_tw
                updates["migrated_at"] = now_tw().isoformat()
                doc.reference.update(updates)
                print(f"  ✓ {collection_name}/{doc.id}: {list(updates.keys())}")

    return count


def main():
    parser = argparse.ArgumentParser(description="舊時間資料遷移工具")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際寫入")
    args = parser.parse_args()

    dry_run = args.dry_run
    mode_label = "DRY-RUN（預覽）" if dry_run else "實際寫入"
    print(f"=" * 60)
    print(f"時間資料遷移工具 — {mode_label}")
    print(f"=" * 60)

    if not dry_run:
        confirm = input("確定要執行實際寫入嗎？（輸入 yes 繼續）：").strip()
        if confirm.lower() != "yes":
            print("已取消。")
            return

    try:
        from modules.db import get_firestore_client
        client = get_firestore_client()
        print("✓ Firebase 連線成功")
    except Exception as e:
        print(f"✗ Firebase 連線失敗：{e}")
        sys.exit(1)

    collections = {
        "count_events": ["timestamp"],
        "users": ["created_at", "lockout_until", "password_changed_at"],
        "recitation_items": ["created_at", "updated_at"],
    }

    total = 0
    for col, fields in collections.items():
        print(f"\n處理 {col}…")
        n = migrate_collection(client, col, fields, dry_run)
        print(f"  → 處理 {n} 筆")
        total += n

    print(f"\n{'=' * 60}")
    print(f"完成。共{'預計遷移' if dry_run else '遷移'} {total} 筆文件。")
    if dry_run:
        print("若確認無誤，請執行：python tools/migrate_timestamps.py")


if __name__ == "__main__":
    main()
