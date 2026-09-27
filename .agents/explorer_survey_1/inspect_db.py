import sqlite3
import os
import sys
import json
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"c:\Users\Admin\Desktop\project\POKETAN\app\data\pokemap.db"

def inspect():
    print(f"DB Path: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB does not exist!")
        return

    print(f"DB File Size: {os.path.getsize(DB_PATH)} bytes")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Schema check
    print("\n--- TABLES & INDEXES ---")
    c.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name;")
    for row in c.fetchall():
        print(f"[{row['type']}] {row['name']} ON {row['tbl_name']}")
        if row['sql']:
            print(f"    SQL: {row['sql'].strip()}")

    # 2. Table row counts
    print("\n--- ROW COUNTS ---")
    for tbl in ["regions", "stores", "store_history"]:
        try:
            c.execute(f"SELECT COUNT(*) FROM {tbl};")
            cnt = c.fetchone()[0]
            print(f"{tbl}: {cnt} rows")
        except Exception as e:
            print(f"{tbl}: error {e}")

    # 3. Store history duplicate check on (store_id, timestamp, status_code)
    print("\n--- DUPLICATE CHECK on store_history(store_id, timestamp, status_code) ---")
    c.execute("""
        SELECT store_id, timestamp, status_code, COUNT(*) as cnt
        FROM store_history
        GROUP BY store_id, timestamp, status_code
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 20;
    """)
    dups = c.fetchall()
    print(f"Total duplicate groups found: {len(dups)}")
    for d in dups:
        print(f"  store_id: {d['store_id']}, ts: {d['timestamp']}, status: {d['status_code']}, count: {d['cnt']}")

    # 4. Check idx_hist_unique existence
    print("\n--- CHECK idx_hist_unique ---")
    c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_hist_unique';")
    idx_row = c.fetchone()
    if idx_row:
        print(f"idx_hist_unique exists: {idx_row['sql']}")
    else:
        print("idx_hist_unique DOES NOT EXIST!")

    # 5. Check formatted_time format & timezone in store_history and stores
    print("\n--- FORMATTED_TIME / LAST_REPORTED_AT CHECK ---")
    c.execute("""
        SELECT formatted_time, timestamp
        FROM store_history
        WHERE formatted_time IS NOT NULL AND formatted_time != ''
        LIMIT 25;
    """)
    sample_hist = c.fetchall()
    print("Sample formatted_time from store_history:")
    JST = timezone(timedelta(hours=9))
    UTC = timezone.utc
    mismatch_jst_count = 0
    total_checked = 0
    c.execute("SELECT id, timestamp, formatted_time FROM store_history WHERE formatted_time IS NOT NULL AND formatted_time != '';")
    all_hist = c.fetchall()
    for r in all_hist:
        total_checked += 1
        ts = r["timestamp"]
        ft = r["formatted_time"]
        if ts > 0:
            expected_jst = datetime.fromtimestamp(ts, tz=JST).strftime("%H:%M %d/%m/%Y")
            expected_utc = datetime.fromtimestamp(ts, tz=UTC).strftime("%H:%M %d/%m/%Y")
            if ft != expected_jst:
                mismatch_jst_count += 1
                if mismatch_jst_count <= 10:
                    print(f"  Mismatch in store_history id={r['id']}: ft='{ft}' vs expected_jst='{expected_jst}' (utc was '{expected_utc}')")

    print(f"Total store_history checked: {total_checked}, Mismatched JST: {mismatch_jst_count}")

    # Check stores.last_reported_at
    c.execute("SELECT id, last_timestamp, last_reported_at FROM stores WHERE last_reported_at IS NOT NULL AND last_reported_at != '';")
    stores_reported = c.fetchall()
    mismatch_store_count = 0
    for r in stores_reported:
        ts = r["last_timestamp"]
        ft = r["last_reported_at"]
        if ts > 0:
            expected_jst = datetime.fromtimestamp(ts, tz=JST).strftime("%H:%M %d/%m/%Y")
            if ft != expected_jst:
                mismatch_store_count += 1
                if mismatch_store_count <= 10:
                    print(f"  Mismatch in stores id={r['id']}: ft='{ft}' vs expected_jst='{expected_jst}'")
    print(f"Total stores with last_reported_at checked: {len(stores_reported)}, Mismatched JST: {mismatch_store_count}")

    # 6. Check created_at in store_history
    print("\n--- CREATED_AT VS TIMESTAMP CHECK ---")
    c.execute("""
        SELECT COUNT(*) as cnt,
               SUM(CASE WHEN created_at = timestamp THEN 1 ELSE 0 END) as eq_cnt,
               SUM(CASE WHEN created_at != timestamp THEN 1 ELSE 0 END) as diff_cnt,
               SUM(CASE WHEN created_at > timestamp AND (created_at - timestamp > 120) THEN 1 ELSE 0 END) as large_diff_cnt
        FROM store_history;
    """)
    cat_summary = c.fetchone()
    print(f"Total rows: {cat_summary['cnt']}")
    print(f"created_at == timestamp: {cat_summary['eq_cnt']}")
    print(f"created_at != timestamp: {cat_summary['diff_cnt']}")
    print(f"created_at > timestamp + 120s (potential inflated created_at): {cat_summary['large_diff_cnt']}")

    # Let's inspect some samples where created_at - timestamp > 120
    c.execute("""
        SELECT id, store_id, timestamp, created_at, (created_at - timestamp) as diff, formatted_time, source
        FROM store_history
        WHERE (created_at - timestamp) > 120
        ORDER BY diff DESC
        LIMIT 10;
    """)
    samples = c.fetchall()
    print("Sample rows where created_at > timestamp + 120s:")
    for s in samples:
        print(f"  id: {s['id']}, sid: {s['store_id']}, ts: {s['timestamp']}, created_at: {s['created_at']}, diff_sec: {s['diff']}, source: {s['source']}, ft: {s['formatted_time']}")

    # 7. Check stores schema details
    print("\n--- PRAGMA table_info(stores) ---")
    c.execute("PRAGMA table_info(stores);")
    for col in c.fetchall():
        print(f"  {col['cid']}: {col['name']} {col['type']} (default: {col['dflt_value']}, pk: {col['pk']})")

    # 8. Check store_history schema details
    print("\n--- PRAGMA table_info(store_history) ---")
    c.execute("PRAGMA table_info(store_history);")
    for col in c.fetchall():
        print(f"  {col['cid']}: {col['name']} {col['type']} (default: {col['dflt_value']}, pk: {col['pk']})")

    # 9. Check PRAGMA integrity_check
    print("\n--- PRAGMA integrity_check ---")
    c.execute("PRAGMA integrity_check;")
    for row in c.fetchall():
        print(f"  Integrity: {row[0]}")

    print("\n--- ALL 12 ROWS WHERE created_at > timestamp + 120s ---")
    c.execute("""
        SELECT id, store_id, status_code, timestamp, created_at, (created_at - timestamp) as diff, formatted_time, source, user, note
        FROM store_history
        WHERE (created_at - timestamp) > 120
        ORDER BY diff DESC;
    """)
    for r in c.fetchall():
        print(dict(r))

    conn.close()

if __name__ == "__main__":
    inspect()
