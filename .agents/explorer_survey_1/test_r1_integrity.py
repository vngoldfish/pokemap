import sqlite3
import os
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"c:\Users\Admin\Desktop\project\POKETAN\app\data\pokemap.db"

def test_db_integrity():
    assert os.path.exists(DB_PATH), "pokemap.db must exist"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. PRAGMA integrity_check
    c.execute("PRAGMA integrity_check;")
    res = c.fetchone()[0]
    assert res == "ok", f"Database integrity check failed: {res}"
    print("[PASS] PRAGMA integrity_check == ok")

    # 2. Check idx_hist_unique exists
    c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_hist_unique';")
    idx = c.fetchone()
    assert idx is not None, "idx_hist_unique index must exist"
    print(f"[PASS] idx_hist_unique exists: {idx['sql']}")

    # 3. Check duplicate records on (store_id, timestamp, status_code)
    c.execute("""
        SELECT store_id, timestamp, status_code, COUNT(*) as cnt
        FROM store_history
        GROUP BY store_id, timestamp, status_code
        HAVING COUNT(*) > 1;
    """)
    dups = c.fetchall()
    assert len(dups) == 0, f"Found {len(dups)} duplicate groups in store_history"
    print("[PASS] 0 duplicates on (store_id, timestamp, status_code)")

    # 4. Check 100% formatted_time is JST (%H:%M %d/%m/%Y)
    JST = timezone(timedelta(hours=9))
    c.execute("SELECT id, timestamp, formatted_time FROM store_history WHERE formatted_time IS NOT NULL AND formatted_time != '';")
    rows = c.fetchall()
    mismatches = 0
    for r in rows:
        ts = r["timestamp"]
        ft = r["formatted_time"]
        if ts > 0:
            expected_jst = datetime.fromtimestamp(ts, tz=JST).strftime("%H:%M %d/%m/%Y")
            if ft != expected_jst:
                mismatches += 1
    assert mismatches == 0, f"Found {mismatches} non-JST formatted_time records"
    print(f"[PASS] 100% ({len(rows)} rows) formatted_time strictly matches JST (%H:%M %d/%m/%Y)")

    # 5. Check stores foreign keys
    c.execute("PRAGMA foreign_key_check;")
    fk_errors = c.fetchall()
    assert len(fk_errors) == 0, f"Found {len(fk_errors)} foreign key errors"
    print("[PASS] 0 foreign key violations")

    # 6. Check created_at > timestamp + 120s count
    c.execute("SELECT COUNT(*) FROM store_history WHERE created_at > timestamp + 120 AND timestamp > 0;")
    inflated_count = c.fetchone()[0]
    print(f"[INFO] Current inflated created_at records (> 120s): {inflated_count}")

    conn.close()

if __name__ == "__main__":
    test_db_integrity()
