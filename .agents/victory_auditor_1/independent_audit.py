"""
Independent Victory Audit Script for PokéTan Stock Tracker
Audits SQLite database integrity, JST timestamps, API endpoints, and JS syntax.
"""
import os
import sys
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = r"c:\Users\Admin\Desktop\project\POKETAN"
DB_PATH = os.path.join(PROJECT_ROOT, "app", "data", "pokemap.db")
JST = timezone(timedelta(hours=9))

def audit_sqlite():
    print("=== 1. SQLITE DATABASE FORENSIC AUDIT ===")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. PRAGMA integrity
    c.execute("PRAGMA integrity_check;")
    integrity = c.fetchone()[0]
    print(f"[*] PRAGMA integrity_check: {integrity}")
    assert integrity == "ok"

    # 2. PRAGMA foreign_key_check
    c.execute("PRAGMA foreign_key_check;")
    fk_errors = c.fetchall()
    print(f"[*] PRAGMA foreign_key_check: {len(fk_errors)} errors")
    assert len(fk_errors) == 0

    # 3. Unique index definition
    c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_hist_unique';")
    idx_row = c.fetchone()
    idx_sql = idx_row[0] if idx_row else None
    print(f"[*] Unique index idx_hist_unique: {idx_sql}")
    assert idx_sql is not None

    # 4. Duplicate count
    c.execute("""
        SELECT store_id, timestamp, status_code, COUNT(*) as cnt
        FROM store_history
        GROUP BY store_id, timestamp, status_code
        HAVING COUNT(*) > 1;
    """)
    dups = c.fetchall()
    print(f"[*] Duplicate records in store_history: {len(dups)}")
    assert len(dups) == 0

    # 5. Counts
    c.execute("SELECT COUNT(*) FROM stores;")
    total_stores = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM store_history;")
    total_hist = c.fetchone()[0]
    print(f"[*] Total stores: {total_stores}")
    print(f"[*] Total history records: {total_hist}")
    assert total_stores > 15000
    assert total_hist > 20000

    # 6. Check created_at > timestamp + 120
    c.execute("""
        SELECT COUNT(*) FROM store_history
        WHERE created_at > timestamp + 120 AND timestamp > 0;
    """)
    inflated_cnt = c.fetchone()[0]
    print(f"[*] Inflated created_at records (> ts + 120): {inflated_cnt}")
    assert inflated_cnt == 0

    # 7. 100% JST compliance
    c.execute("SELECT id, timestamp, formatted_time FROM store_history WHERE timestamp > 0 AND formatted_time IS NOT NULL AND formatted_time != '';")
    rows = c.fetchall()
    jst_mismatches = 0
    for r in rows:
        expected = datetime.fromtimestamp(r["timestamp"], tz=JST).strftime("%H:%M %d/%m/%Y")
        if r["formatted_time"] != expected:
            jst_mismatches += 1
    print(f"[*] JST formatted_time checks: {len(rows)} checked, {jst_mismatches} mismatches")
    assert jst_mismatches == 0

    # 8. Prefecture store distribution
    c.execute("SELECT pref, COUNT(*) as cnt FROM stores GROUP BY pref ORDER BY cnt DESC;")
    pref_counts = {r["pref"]: r["cnt"] for r in c.fetchall()}
    print(f"[*] Stores by prefecture: {pref_counts}")
    assert "tokyo" in pref_counts and pref_counts["tokyo"] > 5000
    assert "osaka" in pref_counts and pref_counts["osaka"] > 3000
    assert "kanagawa" in pref_counts and pref_counts["kanagawa"] > 3000
    assert "aichi" in pref_counts and pref_counts["aichi"] > 3000

    conn.close()
    print("[+] SQLite Database Forensic Audit: PASS\n")


def audit_api_endpoints():
    print("=== 2. FASTAPI ENDPOINTS & CLOCK AUDIT ===")
    from fastapi.testclient import TestClient
    sys.path.insert(0, PROJECT_ROOT)
    from app.web import app

    with TestClient(app) as client:
        # /
        res_map = client.get("/")
        print(f"[*] GET / -> status: {res_map.status_code}, content-type: {res_map.headers.get('content-type')}")
        assert res_map.status_code == 200
        assert "text/html" in res_map.headers.get("content-type", "")

        # /thongbao
        res_tb = client.get("/thongbao")
        print(f"[*] GET /thongbao -> status: {res_tb.status_code}, content-type: {res_tb.headers.get('content-type')}")
        assert res_tb.status_code == 200
        assert "text/html" in res_tb.headers.get("content-type", "")

        # /api/config
        t_before = int(time.time())
        res_cfg = client.get("/api/config")
        t_after = int(time.time())
        print(f"[*] GET /api/config -> status: {res_cfg.status_code}")
        assert res_cfg.status_code == 200
        cfg_data = res_cfg.json()
        assert "serverTime" in cfg_data
        server_time = cfg_data["serverTime"]
        print(f"[*] serverTime: {server_time} (current range: [{t_before}, {t_after}])")
        assert (t_before - 2) <= server_time <= (t_after + 2)

        # /api/latest_reports
        res_lr = client.get("/api/latest_reports?since=0&limit=10")
        print(f"[*] GET /api/latest_reports -> status: {res_lr.status_code}")
        assert res_lr.status_code == 200
        lr_data = res_lr.json()
        assert isinstance(lr_data, list)
        print(f"[*] /api/latest_reports returned {len(lr_data)} items")

        # /api/store_history/{store_id}
        # Pick first store from DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT store_id FROM store_history LIMIT 1;")
        sample_sid = c.fetchone()[0]
        conn.close()

        res_sh = client.get(f"/api/store_history/{sample_sid}")
        sample_sid_display = sample_sid.encode('ascii', errors='backslashreplace').decode('ascii')
        print(f"[*] GET /api/store_history/{sample_sid_display} -> status: {res_sh.status_code}")
        assert res_sh.status_code == 200
        sh_data = res_sh.json()
        assert isinstance(sh_data, list)
        print(f"[*] /api/store_history returned {len(sh_data)} items")
        if len(sh_data) > 0:
            assert "status_code" in sh_data[0]
            assert "formatted_time" in sh_data[0]

    print("[+] FastAPI Endpoints & Clock Audit: PASS\n")


def audit_javascript_syntax():
    print("=== 3. JAVASCRIPT SYNTAX & NODE.JS CHECK ===")
    sys.path.insert(0, PROJECT_ROOT)
    from app.templates import render_map_page, render_thongbao_page
    import re, tempfile

    pages = {
        "Map Page (/)": render_map_page(),
        "Thongbao Page (/thongbao)": render_thongbao_page()
    }

    for name, html in pages.items():
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        print(f"[*] {name}: found {len(scripts)} inline script blocks")
        for i, s in enumerate(scripts):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(s)
                tmp_path = f.name
            try:
                res = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
                assert res.returncode == 0, f"Node --check failed for {name} block {i}: {res.stderr}"
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        print(f"[*] {name}: node --check passed for all blocks")

    print("[+] JavaScript Syntax Audit: PASS\n")


if __name__ == "__main__":
    audit_sqlite()
    audit_api_endpoints()
    audit_javascript_syntax()
    print("ALL INDEPENDENT VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")
