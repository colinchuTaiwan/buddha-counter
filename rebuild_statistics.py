"""
tools/rebuild_statistics.py
從 count_events 重建 daily_stats — RTDB 版本。
可重複執行，全量替換不累加。
"""
import sys, argparse
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()

    print(f"{'='*60}\n統計重建（RTDB） — {'DRY-RUN' if args.dry_run else '實際寫入'}\n{'='*60}")
    if not args.dry_run:
        if input("確定要覆蓋 daily_stats？(yes)：").strip().lower() != "yes":
            print("已取消"); return

    try:
        from modules.db import _init_firebase, rtdb_get, rtdb_set, now_tw
        _init_firebase()
        print("✓ Firebase 連線成功")
    except Exception as e:
        print(f"✗ {e}"); sys.exit(1)

    from modules.db import parse_timestamp

    events_root = rtdb_get("/count_events") or {}
    if args.user_id:
        events_root = {args.user_id: events_root.get(args.user_id, {})}

    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    total_events = 0
    for uid, events in events_root.items():
        for eid, ev in (events or {}).items():
            item_id = ev.get("item_id", "")
            delta = ev.get("delta", 0)
            date_str = ev.get("date_str", "")
            if not date_str:
                ts = parse_timestamp(ev.get("timestamp"))
                date_str = ts.strftime("%Y-%m-%d") if ts else ""
            if not item_id or not date_str:
                continue
            stats[uid][item_id][date_str] += delta
            total_events += 1

    print(f"讀取 {total_events} 筆事件")

    written = 0
    for uid, items in stats.items():
        for item_id, dates in items.items():
            for date_str, count in dates.items():
                count = max(0, count)
                path = f"/daily_stats/{uid}/{item_id}/{date_str}"
                if args.dry_run:
                    print(f"  [DRY] {path} = {count}")
                else:
                    rtdb_set(path, count)
                written += 1

    print(f"\n✓ 完成，{'預計' if args.dry_run else ''}寫入 {written} 筆。")

if __name__ == "__main__":
    main()
