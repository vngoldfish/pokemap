"""
Tests for Milestone 1: SQLite Database & Data Integrity
"""
import sqlite3
import threading
import time
import os
import sys
from datetime import datetime, timezone, timedelta
import pytest

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import (
    get_db_connection,
    record_new_report,
    save_bulk_history,
    get_stores,
    get_report_counts,
    get_store_restock_analytics,
    _db_write_lock,
    init_db
)

JST = timezone(timedelta(hours=9))


def test_db_pragma_integrity():
    """PRAGMA integrity_check must return 'ok'."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()[0]
        assert res == "ok"


def test_unique_index_and_zero_duplicates():
    """Verify unique index idx_hist_unique exists and zero duplicates exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_hist_unique';")
        idx_sql = cursor.fetchone()
        assert idx_sql is not None

        cursor.execute("""
            SELECT store_id, timestamp, status_code, COUNT(*) as cnt
            FROM store_history
            GROUP BY store_id, timestamp, status_code
            HAVING COUNT(*) > 1;
        """)
        dups = cursor.fetchall()
        assert len(dups) == 0


def test_zero_inflated_created_at_records():
    """Verify zero historical records have created_at > timestamp + 120."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM store_history
            WHERE created_at > timestamp + 120 AND timestamp > 0;
        """)
        inflated_cnt = cursor.fetchone()[0]
        assert inflated_cnt == 0


def test_jst_formatted_time_compliance():
    """Verify 100% of formatted_time strings conform to JST (%H:%M %d/%m/%Y)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, formatted_time
            FROM store_history
            WHERE timestamp > 0 AND formatted_time IS NOT NULL AND formatted_time != '';
        """)
        rows = cursor.fetchall()
        assert len(rows) > 0
        for r in rows:
            expected = datetime.fromtimestamp(r["timestamp"], tz=JST).strftime("%H:%M %d/%m/%Y")
            assert r["formatted_time"] == expected, f"Row {r['id']} mismatch: {r['formatted_time']} vs {expected}"


def test_tokyo_region_support():
    """Verify tokyo region in regions table, get_stores, and get_report_counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, prefs_json FROM regions WHERE id IN ('tokyo', 'all');")
        reg_map = {r["id"]: r["prefs_json"] for r in cursor.fetchall()}
        assert "tokyo" in reg_map["tokyo"]
        assert "tokyo" in reg_map["all"]

    tokyo_stores = get_stores(region="tokyo")
    assert len(tokyo_stores) > 0

    all_stores = get_stores(region="all")
    assert len(all_stores) >= len(tokyo_stores)

    report_counts = get_report_counts(region="tokyo")
    assert isinstance(report_counts, dict)


def test_connection_lifecycle_guaranteed_close():
    """Verify get_db_connection contextmanager guarantees conn.close() on success and exception."""
    # Test success path
    with get_db_connection() as conn:
        success_conn = conn
    with pytest.raises(sqlite3.ProgrammingError):
        success_conn.execute("SELECT 1;")

    # Test exception path
    fail_conn = None
    try:
        with get_db_connection() as conn:
            fail_conn = conn
            raise ValueError("Forced error to test finally close")
    except ValueError:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        fail_conn.execute("SELECT 1;")


def test_clock_skew_bounding():
    """Verify created_at assigns now_ts only for real-time reports within 120s."""
    now_ts = int(time.time())

    # 1. Fresh report within 120s
    is_new, rep = record_new_report('test_clock_fresh', 'i', now_ts - 20, note='fresh', source='pytest')
    assert is_new is True

    # 2. Historical report older than 120s
    hist_ts = now_ts - 10000
    is_new, rep = record_new_report('test_clock_old', 'o', hist_ts, note='old', source='pytest')
    assert is_new is True

    # 3. Future skewed report
    future_ts = now_ts + 500
    is_new, rep = record_new_report('test_clock_future', 'n', future_ts, note='future', source='pytest')
    assert is_new is True

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT created_at FROM store_history WHERE store_id = 'test_clock_fresh';")
        fresh_cat = c.fetchone()[0]
        assert abs(fresh_cat - now_ts) <= 2

        c.execute("SELECT created_at FROM store_history WHERE store_id = 'test_clock_old';")
        old_cat = c.fetchone()[0]
        assert old_cat == hist_ts

        c.execute("SELECT created_at FROM store_history WHERE store_id = 'test_clock_future';")
        future_cat = c.fetchone()[0]
        assert future_cat == future_ts

        # Clean up
        c.execute("DELETE FROM store_history WHERE source = 'pytest';")
        c.execute("DELETE FROM stores WHERE id IN ('test_clock_fresh', 'test_clock_old', 'test_clock_future');")
        conn.commit()


def test_concurrent_writes_no_lock_errors():
    """Verify multithreaded concurrent writes do not trigger SQLite database is locked errors."""
    errors = []
    success_counts = [0] * 5

    def worker(worker_id):
        base_time = int(time.time()) - 2000
        for i in range(20):
            try:
                ts = base_time + (worker_id * 100) + i
                sid = f"concur_test_{worker_id}"
                is_new, rep = record_new_report(
                    store_id=sid,
                    status_code="i" if i % 2 == 0 else "o",
                    timestamp=ts,
                    note=f"thread {worker_id} iter {i}",
                    source="pytest_concur"
                )
                success_counts[worker_id] += 1
                time.sleep(0.002)
            except Exception as e:
                errors.append((worker_id, i, str(e)))

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Clean up
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM store_history WHERE source = 'pytest_concur';")
        for w in range(5):
            c.execute("DELETE FROM stores WHERE id = ?;", (f"concur_test_{w}",))
        conn.commit()

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
    assert sum(success_counts) == 100


def test_store_restock_analytics_jst():
    """Verify store restock analytics produces JST formatted last_in_stock_time."""
    # Insert temporary test store with an in-stock report
    test_ts = 1789870000
    expected_jst = datetime.fromtimestamp(test_ts, tz=JST).strftime("%H:%M %d/%m/%Y")
    
    with _db_write_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO stores (id, name, pref, current_status) VALUES ('test_store_analytics', 'Test Store', 'osaka', 'i');")
            c.execute("""
                INSERT OR REPLACE INTO store_history (id, store_id, status_code, timestamp, formatted_time, created_at, source)
                VALUES ('test_analytics_hist', 'test_store_analytics', 'i', ?, ?, ?, 'pytest_analytics');
            """, (test_ts, expected_jst, test_ts))
            conn.commit()

    try:
        analytics = get_store_restock_analytics("test_store_analytics")
        assert analytics["last_in_stock_time"] == expected_jst
        assert analytics["in_stock_reports"] >= 1
    finally:
        with _db_write_lock:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM store_history WHERE source = 'pytest_analytics';")
                c.execute("DELETE FROM stores WHERE id = 'test_store_analytics';")
                conn.commit()
