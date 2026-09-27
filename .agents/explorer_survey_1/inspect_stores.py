import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"c:\Users\Admin\Desktop\project\POKETAN\app\data\pokemap.db"

def inspect_stores():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("--- STORES INSPECTION ---")
    c.execute("SELECT COUNT(*) FROM stores;")
    total = c.fetchone()[0]
    print(f"Total stores: {total}")

    # Prefectures distribution
    c.execute("SELECT pref, COUNT(*) as cnt FROM stores GROUP BY pref;")
    print("Prefecture distribution:")
    for r in c.fetchall():
        print(f"  {r['pref']}: {r['cnt']}")

    # Current status distribution
    c.execute("SELECT current_status, COUNT(*) as cnt FROM stores GROUP BY current_status;")
    print("Current status distribution:")
    for r in c.fetchall():
        print(f"  {r['current_status']}: {r['cnt']}")

    # Missing lat/lng
    c.execute("SELECT COUNT(*) FROM stores WHERE lat IS NULL OR lng IS NULL OR lat = 0 OR lng = 0;")
    print(f"Stores missing coordinates: {c.fetchone()[0]}")

    # Stores with last_timestamp > 0 but last_reported_at empty
    c.execute("SELECT COUNT(*) FROM stores WHERE last_timestamp > 0 AND (last_reported_at IS NULL OR last_reported_at = '');")
    print(f"Stores with last_timestamp > 0 but empty last_reported_at: {c.fetchone()[0]}")

    # Check store sync with latest store_history
    c.execute("""
        SELECT COUNT(*)
        FROM stores s
        JOIN (
            SELECT store_id, status_code, timestamp, formatted_time,
                   ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY timestamp DESC) as rn
            FROM store_history
        ) h ON s.id = h.store_id AND h.rn = 1
        WHERE s.current_status != h.status_code OR s.last_timestamp != h.timestamp;
    """)
    unsynced = c.fetchone()[0]
    print(f"Stores where current_status/last_timestamp does not match latest store_history: {unsynced}")

    # Foreign key violations between store_history and stores
    c.execute("PRAGMA foreign_key_check;")
    fk_errors = c.fetchall()
    print(f"Foreign key check errors: {len(fk_errors)}")
    for fke in fk_errors:
        print(f"  FK error: {dict(fke)}")

    conn.close()

if __name__ == "__main__":
    inspect_stores()
