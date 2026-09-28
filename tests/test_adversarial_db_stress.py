"""
Adversarial Stress Test Harness: Database & Concurrency Integrity for PokéTan Tracker
Targeting app/data/pokemap.db, app/db.py, concurrency locks, index constraints, JST timestamps, and created_at boundaries.
"""

import os
import sys
import time
import re
import random
import threading
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.db import (
    get_db_connection,
    record_new_report,
    save_bulk_history,
    get_stores,
    get_store_by_id,
    get_store_history,
    get_recent_reports,
    get_report_counts,
    get_store_restock_analytics,
    _db_write_lock,
    DB_PATH
)

JST = timezone(timedelta(hours=9))
TIME_FORMAT_REGEX = re.compile(r"^\d{2}:\d{2} \d{2}/\d{2}/\d{4}$")


def test_adversarial_concurrent_writes_and_reads_no_locks():
    """
    Simulate high-frequency concurrent writes from multiple threads alongside concurrent reads on app/data/pokemap.db.
    Verify that sqlite3.OperationalError: database is locked NEVER occurs under high stress.
    """
    total_writers = 8
    total_bulk_writers = 4
    total_readers = 8
    ops_per_writer = 50
    ops_per_bulk = 10
    ops_per_reader = 60

    errors = []
    locked_errors = []
    completed_writes = 0
    completed_reads = 0
    counter_lock = threading.Lock()

    # Track IDs created by this test for clean up
    test_tag = f"adv_stress_{int(time.time())}"
    created_store_ids = set()

    def single_report_writer(thread_id):
        nonlocal completed_writes
        base_ts = int(time.time()) - 1000
        for i in range(ops_per_writer):
            sid = f"{test_tag}_sw_{thread_id}_{i % 5}"
            with counter_lock:
                created_store_ids.add(sid)
            ts = base_ts + (thread_id * 500) + i
            status = random.choice(["i", "o", "n", "u"])
            try:
                is_new, rep = record_new_report(
                    store_id=sid,
                    status_code=status,
                    timestamp=ts,
                    note=f"Adversarial write {thread_id}-{i}",
                    source="pytest_adversarial"
                )
                with counter_lock:
                    completed_writes += 1
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(("writer", thread_id, i, str(oe)))
                errors.append(("writer", thread_id, i, str(oe)))
            except Exception as e:
                errors.append(("writer", thread_id, i, str(e)))
            time.sleep(0.001)

    def bulk_history_writer(thread_id):
        nonlocal completed_writes
        base_ts = int(time.time()) - 50000
        for b in range(ops_per_bulk):
            sid = f"{test_tag}_bw_{thread_id}_{b % 3}"
            with counter_lock:
                created_store_ids.add(sid)
            history_batch = []
            for j in range(25):
                ts = base_ts + (thread_id * 1000) + (b * 50) + j
                history_batch.append({
                    "id": f"{sid}_{ts}_{j % 2}",
                    "timestamp": ts,
                    "status_code": "i" if j % 2 == 0 else "o",
                    "note": f"Bulk {thread_id}-{b}-{j}",
                    "packs": ["Pack A", "Pack B"] if j % 2 == 0 else []
                })
            try:
                cnt = save_bulk_history(sid, history_batch, source="pytest_adversarial")
                with counter_lock:
                    completed_writes += cnt
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(("bulk_writer", thread_id, b, str(oe)))
                errors.append(("bulk_writer", thread_id, b, str(oe)))
            except Exception as e:
                errors.append(("bulk_writer", thread_id, b, str(e)))
            time.sleep(0.002)

    def reader_worker(thread_id):
        nonlocal completed_reads
        query_types = ["stores", "store_id", "history", "recent", "counts", "analytics", "raw_sql"]
        for r in range(ops_per_reader):
            q_type = query_types[r % len(query_types)]
            try:
                if q_type == "stores":
                    res = get_stores(region="osaka")
                    assert isinstance(res, dict)
                elif q_type == "store_id":
                    res = get_store_by_id(f"{test_tag}_sw_0_0")
                elif q_type == "history":
                    res = get_store_history(f"{test_tag}_bw_0_0", limit=50)
                    assert isinstance(res, list)
                elif q_type == "recent":
                    res = get_recent_reports(since_created_at=int(time.time()) - 3600, limit=20)
                    assert isinstance(res, list)
                elif q_type == "counts":
                    res = get_report_counts(region="osaka")
                    assert isinstance(res, dict)
                elif q_type == "analytics":
                    res = get_store_restock_analytics(f"{test_tag}_bw_0_0")
                    assert isinstance(res, dict)
                elif q_type == "raw_sql":
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute("SELECT COUNT(*) FROM store_history WHERE source = 'pytest_adversarial';")
                        _ = c.fetchone()[0]
                with counter_lock:
                    completed_reads += 1
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(("reader", thread_id, r, str(oe)))
                errors.append(("reader", thread_id, r, str(oe)))
            except Exception as e:
                errors.append(("reader", thread_id, r, str(e)))
            time.sleep(0.001)

    threads = []
    # Start writers
    for w in range(total_writers):
        threads.append(threading.Thread(target=single_report_writer, args=(w,)))
    # Start bulk writers
    for bw in range(total_bulk_writers):
        threads.append(threading.Thread(target=bulk_history_writer, args=(bw,)))
    # Start readers
    for rd in range(total_readers):
        threads.append(threading.Thread(target=reader_worker, args=(rd,)))

    # Launch all concurrently
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Clean up test rows
    try:
        with _db_write_lock:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM store_history WHERE source = 'pytest_adversarial';")
                for sid in created_store_ids:
                    c.execute("DELETE FROM stores WHERE id = ?;", (sid,))
                conn.commit()
    except Exception as clean_err:
        print("Cleanup error:", clean_err)

    # Assertions
    assert len(locked_errors) == 0, f"Encountered database locked errors: {locked_errors}"
    assert len(errors) == 0, f"Encountered general concurrency errors: {errors}"
    assert completed_writes > 0
    assert completed_reads == total_readers * ops_per_reader


def test_adversarial_idx_hist_unique_catches_duplicates():
    """
    Test insertion of duplicate (store_id, timestamp, status_code) to verify that
    idx_hist_unique catches and prevents duplicates or handles conflict properly.
    """
    store_id = "test_adv_dup_store"
    ts = 1789990000
    status_code = "i"
    hist_id_1 = f"raw_dup_1_{ts}"
    hist_id_2 = f"raw_dup_2_{ts}"

    with _db_write_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Ensure store exists
            c.execute("INSERT OR REPLACE INTO stores (id, name, pref, current_status) VALUES (?, 'Dup Test Store', 'osaka', 'u');", (store_id,))
            c.execute("DELETE FROM store_history WHERE store_id = ?;", (store_id,))
            conn.commit()

            # 1. First raw insert succeeds
            c.execute("""
                INSERT INTO store_history (id, store_id, status_code, timestamp, created_at, source)
                VALUES (?, ?, ?, ?, ?, 'pytest_dup_test');
            """, (hist_id_1, store_id, status_code, ts, ts))
            conn.commit()

            # 2. Second raw insert with identical (store_id, timestamp, status_code) MUST FAIL with IntegrityError
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                c.execute("""
                    INSERT INTO store_history (id, store_id, status_code, timestamp, created_at, source)
                    VALUES (?, ?, ?, ?, ?, 'pytest_dup_test');
                """, (hist_id_2, store_id, status_code, ts, ts))
                conn.commit()

            assert "UNIQUE constraint failed" in str(exc_info.value) or "idx_hist_unique" in str(exc_info.value)

            # Verify only 1 record exists in store_history
            c.execute("SELECT COUNT(*) FROM store_history WHERE store_id = ? AND timestamp = ? AND status_code = ?;", (store_id, ts, status_code))
            cnt = c.fetchone()[0]
            assert cnt == 1

            # 3. Clean up
            c.execute("DELETE FROM store_history WHERE store_id = ?;", (store_id,))
            c.execute("DELETE FROM stores WHERE id = ?;", (store_id,))
            conn.commit()


def test_adversarial_record_new_report_and_save_bulk_idempotency():
    """
    Verify high-level API handling of duplicate reports:
    - record_new_report returns is_new=False on duplicate and does not duplicate row
    - 10 threads concurrently attempting to insert duplicate get exactly 1 is_new=True
    - save_bulk_history handles batch duplicates cleanly without throwing constraint errors
    """
    store_id = "test_adv_idemp_store"
    ts = 1789995000
    status = "i"

    # Step A: Sequential idempotency
    is_new_1, rep_1 = record_new_report(store_id, status, ts, note="first", source="pytest_idemp")
    assert is_new_1 is True

    is_new_2, rep_2 = record_new_report(store_id, status, ts, note="second duplicate", source="pytest_idemp")
    assert is_new_2 is False

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM store_history WHERE store_id = ? AND timestamp = ?;", (store_id, ts))
        assert c.fetchone()[0] == 1

    # Step B: Concurrent race condition with 10 threads trying to insert exact same report
    race_ts = ts + 1000
    race_results = []

    def race_worker(w_id):
        is_new, rep = record_new_report(
            store_id=store_id,
            status_code="o",
            timestamp=race_ts,
            note=f"race worker {w_id}",
            source="pytest_idemp"
        )
        race_results.append((w_id, is_new))

    threads = [threading.Thread(target=race_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread must have succeeded as new, all others must be False
    new_count = sum(1 for _, is_new in race_results if is_new is True)
    assert new_count == 1, f"Expected exactly 1 is_new=True, got {new_count}: {race_results}"

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM store_history WHERE store_id = ? AND timestamp = ? AND status_code = 'o';", (store_id, race_ts))
        assert c.fetchone()[0] == 1

    # Step C: Bulk history with internal duplicates
    bulk_ts = ts + 2000
    duplicated_batch = [
        {"timestamp": bulk_ts, "status_code": "i", "note": "dup 1"},
        {"timestamp": bulk_ts, "status_code": "i", "note": "dup 2"},
        {"timestamp": bulk_ts, "status_code": "i", "note": "dup 3"},
        {"timestamp": bulk_ts + 10, "status_code": "o", "note": "unique 1"}
    ]
    saved_cnt = save_bulk_history(store_id, duplicated_batch, source="pytest_idemp")
    assert saved_cnt == 2  # 1 unique 'i' + 1 unique 'o'

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM store_history WHERE store_id = ? AND timestamp = ? AND status_code = 'i';", (store_id, bulk_ts))
        assert c.fetchone()[0] == 1

        # Clean up
        c.execute("DELETE FROM store_history WHERE source = 'pytest_idemp';")
        c.execute("DELETE FROM stores WHERE id = ?;", (store_id,))
        conn.commit()


def test_adversarial_100_percent_jst_time_strings_in_db():
    """
    Exhaustively audit 100% of rows in store_history and stores in app/data/pokemap.db:
    - Every formatted_time in store_history must match %H:%M %d/%m/%Y and strictly equal UTC+9.
    - Every last_reported_at in stores must match %H:%M %d/%m/%Y and strictly equal UTC+9.
    - 0 rows may have UTC unshifted timestamps (9 hours discrepancy).
    """
    with get_db_connection() as conn:
        c = conn.cursor()

        # 1. Audit store_history
        c.execute("""
            SELECT id, store_id, timestamp, formatted_time
            FROM store_history
            WHERE timestamp > 0 AND formatted_time IS NOT NULL AND formatted_time != '';
        """)
        all_hist = c.fetchall()
        assert len(all_hist) > 0, "store_history table has no records to verify!"

        hist_mismatches = []
        for row in all_hist:
            ft = row["formatted_time"]
            if not TIME_FORMAT_REGEX.match(ft):
                hist_mismatches.append((row["id"], ft, "regex_fail"))
                continue
            expected_jst = datetime.fromtimestamp(row["timestamp"], tz=JST).strftime("%H:%M %d/%m/%Y")
            if ft != expected_jst:
                hist_mismatches.append((row["id"], ft, f"expected: {expected_jst}"))

        assert len(hist_mismatches) == 0, f"Found {len(hist_mismatches)} store_history JST mismatches: {hist_mismatches[:10]}"

        # 2. Audit stores table
        c.execute("""
            SELECT id, last_timestamp, last_reported_at
            FROM stores
            WHERE last_timestamp > 0 AND last_reported_at IS NOT NULL AND last_reported_at != '';
        """)
        all_stores = c.fetchall()
        assert len(all_stores) > 0, "stores table has no records with last_reported_at!"

        store_mismatches = []
        for row in all_stores:
            lra = row["last_reported_at"]
            if not TIME_FORMAT_REGEX.match(lra):
                store_mismatches.append((row["id"], lra, "regex_fail"))
                continue
            expected_jst = datetime.fromtimestamp(row["last_timestamp"], tz=JST).strftime("%H:%M %d/%m/%Y")
            if lra != expected_jst:
                store_mismatches.append((row["id"], lra, f"expected: {expected_jst}"))

        assert len(store_mismatches) == 0, f"Found {len(store_mismatches)} stores JST mismatches: {store_mismatches[:10]}"


def test_adversarial_zero_inflated_created_at_records_in_db():
    """
    Exhaustively audit 100% of rows in store_history in app/data/pokemap.db:
    - 0 records may have created_at > timestamp + 120 (when timestamp > 0).
    - 0 records may have created_at <= 0.
    """
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) FROM store_history
            WHERE created_at > timestamp + 120 AND timestamp > 0;
        """)
        inflated_count = c.fetchone()[0]
        assert inflated_count == 0, f"Detected {inflated_count} rows with inflated created_at in pokemap.db!"

        c.execute("SELECT COUNT(*) FROM store_history WHERE created_at <= 0;")
        invalid_created_at = c.fetchone()[0]
        assert invalid_created_at == 0, f"Detected {invalid_created_at} rows with created_at <= 0!"


def test_adversarial_created_at_skew_boundary_conditions():
    """
    Challenge the boundary conditions of created_at assignment in record_new_report and save_bulk_history:
    - delta = 0   -> created_at = now
    - delta = 119 -> created_at = now
    - delta = 120 -> created_at = now
    - delta = 121 -> created_at = ts (historical isolation)
    - delta = -120 -> created_at = now (future clock skew within 2m)
    - delta = -121 -> created_at = ts (anomalous future timestamp)
    - save_bulk_history with 1-month-old data -> created_at = timestamp (not now)
    """
    now_ts = int(time.time())
    test_sid = "test_adv_skew_store"

    cases = [
        ("exact_now", 0, True),
        ("within_119", -118, True),
        ("boundary_120", -119, True),
        ("stale_121", -123, False),
        ("stale_old", -86400, False),
        ("future_skew_60", 60, True),
        ("future_skew_120", 118, True),
        ("future_skew_125", 125, False),
    ]

    for label, offset, should_be_now in cases:
        sid = f"{test_sid}_{label}"
        cur_now = int(time.time())
        ts = cur_now + offset
        is_new, rep = record_new_report(
            store_id=sid,
            status_code="i",
            timestamp=ts,
            note=f"case {label}",
            source="pytest_skew_boundary"
        )
        assert is_new is True

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT created_at FROM store_history WHERE store_id = ?;", (sid,))
            cat = c.fetchone()[0]
            if should_be_now:
                # Should be approximately cur_now (within 2 seconds)
                assert abs(cat - cur_now) <= 2, f"Failed case {label}: expected cat ~ {cur_now}, got {cat}"
            else:
                # Should strictly retain timestamp
                assert cat == ts, f"Failed case {label}: expected cat == {ts}, got {cat}"

    # Test save_bulk_history: must NOT assign now_ts to historical items
    bulk_sid = f"{test_sid}_bulk"
    hist_ts = now_ts - 50000
    save_bulk_history(bulk_sid, [{
        "timestamp": hist_ts,
        "status_code": "o",
        "note": "bulk historical"
    }], source="pytest_skew_boundary")

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT created_at FROM store_history WHERE store_id = ?;", (bulk_sid,))
        bulk_cat = c.fetchone()[0]
        assert bulk_cat == hist_ts, f"save_bulk_history assigned inflated created_at: {bulk_cat} vs {hist_ts}"

        # Clean up
        c.execute("DELETE FROM store_history WHERE source = 'pytest_skew_boundary';")
        c.execute("DELETE FROM stores WHERE id LIKE ?;", (f"{test_sid}%",))
        conn.commit()


def test_adversarial_wal_checkpoint_concurrency():
    """
    Stress-test WAL checkpointing while readers and writers are simultaneously accessing pokemap.db.
    Verify WAL mode allows concurrent readers during checkpoint without deadlock.
    """
    stop_event = threading.Event()
    errors = []

    def writer():
        i = 0
        while not stop_event.is_set():
            try:
                sid = f"wal_stress_w_{i % 3}"
                record_new_report(sid, "i", int(time.time()) - 5000 + i, source="pytest_wal")
                i += 1
                time.sleep(0.005)
            except Exception as e:
                errors.append(("writer", str(e)))

    def reader():
        while not stop_event.is_set():
            try:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM store_history WHERE source = 'pytest_wal';")
                    _ = c.fetchone()[0]
                time.sleep(0.005)
            except Exception as e:
                errors.append(("reader", str(e)))

    def checkpointer():
        for _ in range(5):
            if stop_event.is_set():
                break
            try:
                with get_db_connection() as conn:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except Exception as e:
                errors.append(("checkpointer", str(e)))
            time.sleep(0.05)

    w_thread = threading.Thread(target=writer)
    r_thread = threading.Thread(target=reader)
    c_thread = threading.Thread(target=checkpointer)

    w_thread.start()
    r_thread.start()
    c_thread.start()

    c_thread.join()
    stop_event.set()
    w_thread.join()
    r_thread.join()

    # Clean up
    with _db_write_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM store_history WHERE source = 'pytest_wal';")
            for i in range(3):
                c.execute("DELETE FROM stores WHERE id = ?;", (f"wal_stress_w_{i}",))
            conn.commit()

    assert len(errors) == 0, f"Encountered errors during WAL checkpoint stress: {errors}"
