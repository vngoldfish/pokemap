"""
Milestone M5 Empirical Adversarial Verification Suite: DB Concurrency, Latency SLA & Boundary Resilience
Targeting:
1. Flood read endpoints concurrently (/api/stats/combini_analytics, /api/stats/heatmap,
   /api/stats/overview, /api/stats/predictions) during simultaneous write transactions
   (record_new_report, save_bulk_history).
2. Measure response times to verify queries complete in < 150ms.
3. Test boundary values: unknown chain, invalid prefecture, extreme lat/lng, negative limits, invalid store IDs.
4. Verify zero sqlite3.OperationalError: database is locked or deadlocks.
"""

import math
import os
import random
import sqlite3
import sys
import threading
import time
import urllib.parse
from typing import Dict, Any, List, Tuple
import pytest
from starlette.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.web import app
from app.db import (
    get_db_connection,
    record_new_report,
    save_bulk_history,
    _db_write_lock,
    invalidate_stats_overview_cache,
    invalidate_stores_cache,
    db_get_stats_overview,
    get_chain_restock_analytics,
    db_get_restock_predictions,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ==============================================================================
# 1. CONCURRENT READ FLOOD WITH SIMULTANEOUS WRITE TRANSACTIONS
# ==============================================================================

def test_adversarial_endpoint_flood_with_concurrent_writes_and_no_locks(client):
    """
    Flood all 4 stats endpoints concurrently across 8 reader threads while 4 single-report
    writers and 2 bulk-history writers hammer SQLite concurrently.
    Verifies:
    - Zero sqlite3.OperationalError: database is locked
    - Zero deadlocks (clean thread completion within timeout)
    - Zero 500 Internal Server Errors in any read endpoint
    """
    total_reader_threads = 8
    total_single_writers = 4
    total_bulk_writers = 2
    read_ops_per_thread = 30
    write_ops_per_thread = 25
    bulk_ops_per_thread = 8

    test_uid = f"bench_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    created_store_ids = []

    errors: List[Tuple[str, str]] = []
    locked_errors: List[str] = []
    latencies: Dict[str, List[float]] = {
        "combini_analytics": [],
        "heatmap": [],
        "overview": [],
        "predictions": []
    }
    latencies_lock = threading.Lock()
    stop_event = threading.Event()

    # Pre-populate dummy stores with valid pref so foreign key constraint is satisfied
    for w in range(total_single_writers):
        sid = f"{test_uid}_sw_{w}"
        created_store_ids.append(sid)
        with _db_write_lock:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO stores (id, name, chain, pref, current_status) VALUES (?, ?, 'seven', 'osaka', 'u');",
                    (sid, f"Bench Store {sid}")
                )
                conn.commit()

    for bw in range(total_bulk_writers):
        sid = f"{test_uid}_bw_{bw}"
        created_store_ids.append(sid)
        with _db_write_lock:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO stores (id, name, chain, pref, current_status) VALUES (?, ?, 'familymart', 'tokyo', 'u');",
                    (sid, f"Bench Bulk Store {sid}")
                )
                conn.commit()

    def single_writer_worker(worker_id):
        sid = f"{test_uid}_sw_{worker_id}"
        base_ts = int(time.time()) - 2000
        for i in range(write_ops_per_thread):
            if stop_event.is_set():
                break
            ts = base_ts + i * 10
            status = random.choice(["i", "o", "n", "u"])
            try:
                record_new_report(
                    store_id=sid,
                    status_code=status,
                    timestamp=ts,
                    note=f"Bench write {worker_id}-{i}",
                    source="pytest_bench",
                    pref="osaka",
                    notify=False
                )
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(f"single_writer_{worker_id}_{i}: {oe}")
                errors.append(("single_writer", str(oe)))
            except Exception as e:
                errors.append(("single_writer", str(e)))
            time.sleep(0.002)

    def bulk_writer_worker(worker_id):
        sid = f"{test_uid}_bw_{worker_id}"
        base_ts = int(time.time()) - 60000
        for b in range(bulk_ops_per_thread):
            if stop_event.is_set():
                break
            batch = []
            for j in range(15):
                ts = base_ts + (b * 50) + j
                batch.append({
                    "id": f"{sid}_{ts}_{j % 2}",
                    "timestamp": ts,
                    "status_code": "i" if j % 2 == 0 else "o",
                    "note": f"Bulk bench {worker_id}-{b}-{j}",
                    "packs": ["Pokemon 151"] if j % 2 == 0 else []
                })
            try:
                save_bulk_history(sid, batch, source="pytest_bench", pref="tokyo")
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(f"bulk_writer_{worker_id}_{b}: {oe}")
                errors.append(("bulk_writer", str(oe)))
            except Exception as e:
                errors.append(("bulk_writer", str(e)))
            time.sleep(0.005)

    def reader_worker(reader_id):
        endpoints = [
            ("combini_analytics", "/api/stats/combini_analytics?chain=seven&pref=osaka"),
            ("combini_analytics", "/api/stats/combini_analytics?chain=familymart"),
            ("heatmap", "/api/stats/heatmap?mode=chain&pref=osaka"),
            ("heatmap", "/api/stats/heatmap?mode=dow"),
            ("overview", "/api/stats/overview"),
            ("predictions", "/api/stats/predictions?pref=osaka&limit=20&min_score=40"),
            ("predictions", "/api/stats/predictions?pref=tokyo&chain=seven&limit=15"),
            ("predictions", "/api/stats/predictions?pref=aichi&sort=score&limit=25"),
        ]
        for r in range(read_ops_per_thread):
            if stop_event.is_set():
                break
            ep_name, url = endpoints[(reader_id + r) % len(endpoints)]
            t0 = time.perf_counter()
            try:
                resp = client.get(url)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if resp.status_code != 200:
                    errors.append(("reader_http_status", f"{resp.status_code} for {url}"))
                with latencies_lock:
                    latencies[ep_name].append(elapsed_ms)
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(f"reader_{reader_id}_{r}: {oe}")
                errors.append(("reader", str(oe)))
            except Exception as e:
                errors.append(("reader", str(e)))
            time.sleep(0.001)

    threads = []
    for w in range(total_single_writers):
        threads.append(threading.Thread(target=single_writer_worker, args=(w,)))
    for bw in range(total_bulk_writers):
        threads.append(threading.Thread(target=bulk_writer_worker, args=(bw,)))
    for rd in range(total_reader_threads):
        threads.append(threading.Thread(target=reader_worker, args=(rd,)))

    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=35.0)
            assert not t.is_alive(), "Thread deadlock detected: thread failed to finish within 35 seconds"
    finally:
        stop_event.set()
        # Clean up bench records
        try:
            with _db_write_lock:
                with get_db_connection() as conn:
                    conn.execute("DELETE FROM store_history WHERE source = 'pytest_bench';")
                    for sid in created_store_ids:
                        conn.execute("DELETE FROM stores WHERE id = ?;", (sid,))
                    conn.commit()
        except Exception as ce:
            print("Cleanup error:", ce)

    # Assertions
    assert len(locked_errors) == 0, f"Detected database locked errors under flood: {locked_errors}"
    assert len(errors) == 0, f"Detected errors during concurrency flood: {errors}"

    total_reads = sum(len(l) for l in latencies.values())
    assert total_reads == total_reader_threads * read_ops_per_thread

    # Validate median latencies under flood are well within SLAs
    for ep, lats in latencies.items():
        if lats:
            p50 = sorted(lats)[len(lats) // 2]
            p95 = sorted(lats)[int(len(lats) * 0.95)]
            max_lat = max(lats)
            print(f"[Latency Flood] {ep}: count={len(lats)}, p50={p50:.2f}ms, p95={p95:.2f}ms, max={max_lat:.2f}ms")
            assert p50 < 150.0, f"{ep} median latency {p50:.2f}ms exceeded 150ms SLA!"


# ==============================================================================
# 2. QUERY RESPONSE TIME LATENCY BENCHMARKS (< 150ms SLA)
# ==============================================================================

def test_adversarial_latency_benchmarks_under_150ms(client):
    """
    Directly measure query response times across each endpoint to verify queries complete in < 150ms.
    Verifies warm latency (< 50ms) and steady-state query latencies across all 4 endpoints.
    Documents empirical observations for cold cache vs warm cache behavior.
    """
    # 1. Combini Analytics: Across chains
    chains = ["seven", "familymart", "lawson", "ministop", None]
    for ch in chains:
        url = f"/api/stats/combini_analytics?chain={ch}" if ch else "/api/stats/combini_analytics"
        t0 = time.perf_counter()
        resp = client.get(url)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 200
        assert elapsed_ms < 150.0, f"combini_analytics for chain={ch} took {elapsed_ms:.2f}ms, exceeded 150ms SLA!"

    # 2. Heatmap: Both chain and dow modes across prefectures
    modes = ["chain", "dow"]
    for m in modes:
        for pref in ["osaka", "tokyo", "aichi"]:
            url = f"/api/stats/heatmap?mode={m}&pref={pref}"
            t0 = time.perf_counter()
            resp = client.get(url)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            assert resp.status_code == 200
            assert elapsed_ms < 150.0, f"heatmap for mode={m}&pref={pref} took {elapsed_ms:.2f}ms, exceeded 150ms SLA!"

    # 3. Stats Overview: Warm query response (< 50ms)
    client.get("/api/stats/overview")  # Prime warm cache
    t0 = time.perf_counter()
    resp_warm = client.get("/api/stats/overview")
    elapsed_warm_ms = (time.perf_counter() - t0) * 1000.0
    assert resp_warm.status_code == 200
    assert elapsed_warm_ms < 50.0, f"Warm overview query took {elapsed_warm_ms:.2f}ms, expected < 50ms!"

    # 4. Predictions: Localized query (pref=osaka, tokyo, aichi, or localized GPS)
    client.get("/api/stats/predictions?pref=osaka&limit=5")  # Warm-up query
    pred_queries = [
        "/api/stats/predictions?pref=osaka&limit=30",
        "/api/stats/predictions?pref=tokyo&chain=seven&limit=25",
        "/api/stats/predictions?pref=aichi&min_score=50&limit=30",
        "/api/stats/predictions?user_lat=34.6937&user_lng=135.5023&max_dist_km=5.0&limit=20",
        "/api/stats/predictions?pref=osaka&sort=distance&user_lat=34.6667&user_lng=135.5000&limit=20",
    ]
    for pq in pred_queries:
        client.get(pq)  # Warm-up to measure steady-state query latency
        t0 = time.perf_counter()
        resp = client.get(pq)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 200
        assert elapsed_ms < 150.0, f"Predictions query '{pq}' took {elapsed_ms:.2f}ms, exceeded 150ms SLA!"


# ==============================================================================
# 3. BOUNDARY VALUE RESILIENCE & ADVERSARIAL STRESS
# ==============================================================================

def test_adversarial_unknown_chain_handling(client):
    """Test boundary condition: unknown/non-existent chain code."""
    # 1. Combini analytics with unknown chain -> returns 404 cleanly (safe, not 500)
    resp = client.get("/api/stats/combini_analytics?chain=unknown_super_fake_chain_999")
    assert resp.status_code in (404, 200)
    if resp.status_code == 404:
        assert "not found" in resp.json().get("error", "").lower()

    # 2. Predictions with unknown chain -> returns 200 with empty/safe candidates, zero crash
    resp2 = client.get("/api/stats/predictions?chain=unknown_super_fake_chain_999")
    assert resp2.status_code == 200
    data2 = resp2.json()
    non_flash_matching = [p for p in data2.get("predictions", []) if p.get("chain") == "unknown_super_fake_chain_999"]
    assert len(non_flash_matching) == 0


def test_adversarial_invalid_prefecture_handling(client):
    """Test boundary condition: invalid/non-existent prefecture name."""
    # 1. Combini analytics with invalid prefecture -> 404 cleanly
    resp = client.get("/api/stats/combini_analytics?pref=atlantis_city")
    assert resp.status_code in (404, 200)

    # 2. Heatmap with invalid prefecture -> 404 cleanly
    resp2 = client.get("/api/stats/heatmap?pref=atlantis_city")
    assert resp2.status_code in (404, 200)

    # 3. Predictions with invalid prefecture -> returns 200 with safe response, no 500 crash
    resp3 = client.get("/api/stats/predictions?pref=atlantis_city")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert isinstance(data3.get("predictions"), list)


def test_adversarial_extreme_lat_lng_coordinates(client):
    """Test boundary conditions: extreme, out-of-bounds, or NaN lat/lng coordinates."""
    extreme_coords = [
        {"user_lat": 999999.0, "user_lng": -999999.0, "max_dist_km": 10.0},
        {"user_lat": -90.0, "user_lng": 180.0, "max_dist_km": 5.0},
        {"user_lat": 0.0, "user_lng": 0.0, "max_dist_km": 0.1},
        {"user_lat": 34.6937, "user_lng": 135.5023, "max_dist_km": -10.0},  # Negative max_dist_km
    ]
    for c in extreme_coords:
        query_str = f"/api/stats/predictions?user_lat={c['user_lat']}&user_lng={c['user_lng']}&max_dist_km={c['max_dist_km']}"
        resp = client.get(query_str)
        assert resp.status_code == 200, f"Extreme coordinates failed: {c} -> {resp.status_code}"
        data = resp.json()
        assert "predictions" in data


def test_adversarial_negative_limits_and_score_bounds(client):
    """
    Challenge limit and score boundaries:
    - limit = 0 -> returns empty predictions list
    - limit < 0 -> observe and verify negative slice handling without server crash
    - min_score = -50 -> handled safely
    - min_score = 999 -> verify bypass semantics (flash green=100% or truck_en_route=True)
    """
    # 1. limit = 0
    resp_zero = client.get("/api/stats/predictions?limit=0")
    assert resp_zero.status_code == 200
    assert len(resp_zero.json().get("predictions", [])) == 0

    # 2. limit = -5 (adversarial input) -> must not throw 500 internal server error
    resp_neg = client.get("/api/stats/predictions?limit=-5")
    assert resp_neg.status_code == 200
    assert isinstance(resp_neg.json().get("predictions"), list)

    # 3. min_score = -50
    resp_neg_score = client.get("/api/stats/predictions?min_score=-50&limit=10")
    assert resp_neg_score.status_code == 200
    assert len(resp_neg_score.json().get("predictions", [])) <= 10

    # 4. min_score = 999 (super high threshold)
    resp_high_score = client.get("/api/stats/predictions?min_score=999")
    assert resp_high_score.status_code == 200
    preds = resp_high_score.json().get("predictions", [])
    for p in preds:
        # Must be either a flash store (flash_mode != none), truck ripple (truck_en_route=True), or score 100
        is_override = (p.get("score") == 100 or p.get("flash_mode") != "none" or p.get("truck_en_route") is True)
        assert is_override, f"Unexpected regular candidate bypassed min_score=999: {p}"


def test_adversarial_invalid_store_id_injections(client):
    """Test boundary condition: non-existent store IDs and injection attacks on prediction explain."""
    malicious_ids = [
        "nonexistent_store_99999",
        "' OR 1=1 --",
        "<script>alert('xss')</script>",
        "../../../../etc/passwd",
        "store_id_with_null%00_byte",
        "a" * 300,
    ]
    for mid in malicious_ids:
        safe_encoded = urllib.parse.quote(mid, safe="%")
        url = f"/api/predictions/{safe_encoded}/explain"
        resp = client.get(url)
        # Must return 404 or 400 safely, NEVER 500 Internal Server Error
        assert resp.status_code in (404, 400, 422), f"Malicious store ID {mid} returned unexpected status {resp.status_code}"
        assert resp.status_code != 500


# ==============================================================================
# 4. LOW-LEVEL SQLITE WAL WRITER-READER ISOLATION & NO-LOCK CHECK
# ==============================================================================

def test_adversarial_low_level_wal_concurrent_transactions():
    """
    Stress SQLite WAL mode concurrency directly using raw multi-connection transactions:
    - 5 threads executing immediate write transactions on stores and store_history
    - 5 threads executing large analytical aggregate queries
    - Verify that zero sqlite3.OperationalError: database is locked occur.
    """
    stop_event = threading.Event()
    locked_errors = []
    other_errors = []
    writes_completed = 0
    reads_completed = 0
    count_lock = threading.Lock()

    def raw_writer(thread_id):
        nonlocal writes_completed
        for i in range(20):
            if stop_event.is_set():
                break
            sid = f"raw_wal_test_{thread_id}_{i}"
            ts = int(time.time()) - 1000 + i
            try:
                with _db_write_lock:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute(
                            "INSERT OR REPLACE INTO stores (id, name, chain, pref, current_status) VALUES (?, 'Raw WAL Store', 'seven', 'osaka', 'u');",
                            (sid,)
                        )
                        c.execute(
                            "INSERT OR REPLACE INTO store_history (id, store_id, status_code, timestamp, created_at, source) VALUES (?, ?, 'i', ?, ?, 'pytest_raw_wal');",
                            (f"{sid}_{ts}_i", sid, ts, ts)
                        )
                        conn.commit()
                with count_lock:
                    writes_completed += 1
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(f"raw_writer_{thread_id}_{i}: {oe}")
                other_errors.append(str(oe))
            except Exception as e:
                other_errors.append(str(e))
            time.sleep(0.002)

    def raw_reader(thread_id):
        nonlocal reads_completed
        for i in range(25):
            if stop_event.is_set():
                break
            try:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("""
                        SELECT s.chain, COUNT(h.id), MAX(h.timestamp)
                        FROM stores s
                        LEFT JOIN store_history h ON s.id = h.store_id
                        GROUP BY s.chain;
                    """)
                    rows = c.fetchall()
                    assert len(rows) > 0
                with count_lock:
                    reads_completed += 1
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower():
                    locked_errors.append(f"raw_reader_{thread_id}_{i}: {oe}")
                other_errors.append(str(oe))
            except Exception as e:
                other_errors.append(str(e))
            time.sleep(0.001)

    threads = []
    for w in range(5):
        threads.append(threading.Thread(target=raw_writer, args=(w,)))
    for r in range(5):
        threads.append(threading.Thread(target=raw_reader, args=(r,)))

    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20.0)
            assert not t.is_alive(), "Raw WAL thread deadlock detected"
    finally:
        stop_event.set()
        # Clean up
        with _db_write_lock:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM store_history WHERE source = 'pytest_raw_wal';")
                conn.execute("DELETE FROM stores WHERE id LIKE 'raw_wal_test_%';")
                conn.commit()

    assert len(locked_errors) == 0, f"Encountered locked errors in raw WAL test: {locked_errors}"
    assert len(other_errors) == 0, f"Encountered other errors in raw WAL test: {other_errors}"
    assert writes_completed == 100
    assert reads_completed == 125
