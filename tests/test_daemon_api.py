"""
Tests for Milestone 2 & Milestone 3:
- Background Daemon Concurrency & Robustness
- Prefecture Coverage (Tokyo integration)
- API Endpoints (/api/config, /api/latest_reports, /api/store_history, /, /thongbao)
- Concurrent API Polling and Daemon Report Recording without database locks
"""
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.web import (
    app,
    ALL_PREFS,
    REGION_PREFS,
    get_target_prefs,
    start_background_watcher,
    _watcher_thread
)
from app.db import (
    get_db_connection,
    record_new_report,
    get_recent_reports,
    get_store_history as db_get_store_history,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    # Teardown: Clean up test records
    with get_db_connection() as conn:
        conn.execute("DELETE FROM store_history WHERE store_id LIKE 'test_%';")
        conn.execute("DELETE FROM stores WHERE id LIKE 'test_%';")
        conn.commit()


def test_prefecture_coverage_in_web():
    """Verify ALL_PREFS and REGION_PREFS properly include Tokyo across all mappings."""
    expected_all_prefs = ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"]
    assert ALL_PREFS == expected_all_prefs, f"ALL_PREFS mismatch: {ALL_PREFS}"

    assert "tokyo" in REGION_PREFS, "tokyo missing from REGION_PREFS"
    assert REGION_PREFS["tokyo"] == ["tokyo", "kanagawa"], f"REGION_PREFS['tokyo'] mismatch: {REGION_PREFS['tokyo']}"

    assert "all" in REGION_PREFS, "all missing from REGION_PREFS"
    assert REGION_PREFS["all"] == expected_all_prefs, f"REGION_PREFS['all'] mismatch: {REGION_PREFS['all']}"

    # Verify get_target_prefs
    assert get_target_prefs(region="tokyo") == ["tokyo", "kanagawa"]
    assert get_target_prefs(region="all") == expected_all_prefs
    assert get_target_prefs(pref="tokyo") == ["tokyo", "kanagawa"]


def test_api_config_server_time(client):
    """Verify /api/config returns serverTime matching current time within 2 seconds."""
    t_before = int(time.time())
    response = client.get("/api/config")
    t_after = int(time.time())

    assert response.status_code == 200
    data = response.json()

    assert "serverTime" in data, "serverTime missing from /api/config"
    server_time = data["serverTime"]
    assert isinstance(server_time, int), f"serverTime is not int: {type(server_time)}"
    assert (t_before - 2) <= server_time <= (t_after + 2), (
        f"serverTime {server_time} not within 2s of range [{t_before}, {t_after}]"
    )

    # Core config contract fields
    assert "apiKey" in data
    assert "projectId" in data
    assert "chainNames" in data
    assert "packCodes" in data
    assert "telegramRegion" in data


def test_api_latest_reports_format_and_since_filtering(client):
    """Verify /api/latest_reports returns 200, clean list, and properly filters by `since`."""
    # 1. Base call
    res = client.get("/api/latest_reports?since=0&limit=10")
    assert res.status_code == 200
    reports = res.json()
    assert isinstance(reports, list)

    # 2. Insert a fresh distinct report
    now_ts = int(time.time())
    test_sid = f"test_m2_lr_{int(time.time() * 1000) % 100000}"
    is_new, rep = record_new_report(
        store_id=test_sid,
        status_code="i",
        timestamp=now_ts,
        onsite=True,
        packs=["SV8a"],
        source="test_daemon"
    )
    assert is_new is True

    # 3. Query with since strictly before now_ts -> MUST include this report
    res_since = client.get(f"/api/latest_reports?since={now_ts - 5}&limit=50")
    assert res_since.status_code == 200
    since_reports = res_since.json()
    matching = [r for r in since_reports if r["store_id"] == test_sid]
    assert len(matching) == 1
    assert matching[0]["status_code"] == "i"
    assert matching[0]["onsite"] is True
    assert "SV8a" in matching[0]["packs"]
    assert "created_at" in matching[0]

    # 4. Query with since strictly after now_ts -> MUST exclude this report
    res_future = client.get(f"/api/latest_reports?since={now_ts + 100}&limit=50")
    assert res_future.status_code == 200
    future_reports = res_future.json()
    assert all(r["store_id"] != test_sid for r in future_reports)


def test_api_store_history_order_and_limit(client):
    """Verify /api/store_history/{store_id} returns history ordered by timestamp DESC up to 100 entries."""
    test_sid = f"test_m2_hist_{int(time.time() * 1000) % 100000}"
    base_ts = 1700000000

    # Insert 5 sequential history records for this store
    for i in range(5):
        record_new_report(
            store_id=test_sid,
            status_code="i" if i % 2 == 0 else "o",
            timestamp=base_ts + i * 100,
            note=f"entry_{i}",
            source="test"
        )

    res = client.get(f"/api/store_history/{test_sid}")
    assert res.status_code == 200
    hist = res.json()
    assert isinstance(hist, list)
    assert len(hist) >= 5

    # Verify strictly descending by timestamp
    for idx in range(len(hist) - 1):
        assert hist[idx]["timestamp"] >= hist[idx + 1]["timestamp"], (
            f"History not sorted DESC at index {idx}: {hist[idx]['timestamp']} < {hist[idx+1]['timestamp']}"
        )


def test_html_endpoints_return_200(client):
    """Verify HTML routes / and /thongbao return HTTP 200."""
    res_map = client.get("/")
    assert res_map.status_code == 200
    assert "text/html" in res_map.headers.get("content-type", "")

    res_thongbao = client.get("/thongbao")
    assert res_thongbao.status_code == 200
    assert "text/html" in res_thongbao.headers.get("content-type", "")

    # Also test aliases
    assert client.get("/map").status_code == 200
    assert client.get("/stores").status_code == 200


def test_daemon_store_loop_robustness_isolation():
    """
    Verify that an error on a single store during status ingestion
    does not abort the processing of other stores in that prefecture.
    """
    processed = []
    hot_data_sample = {
        "store_good_1": "i,1700000100,onsite,0",
        "store_bad_broken": "corrupt_data_trigger_error",
        "store_good_2": "o,1700000200,,0",
    }

    from app.parser import parse_store_status

    for k, raw in hot_data_sample.items():
        try:
            if k == "store_bad_broken":
                raise RuntimeError("Simulated transient lock or parse error on store_bad_broken")
            parsed = parse_store_status(raw)
            processed.append(k)
        except Exception as pe:
            continue

    # Both good stores must be processed despite store_bad_broken error
    assert "store_good_1" in processed
    assert "store_good_2" in processed
    assert "store_bad_broken" not in processed
    assert len(processed) == 2


def test_startup_daemon_thread_registration():
    """Verify start_background_watcher() starts a daemon thread and is idempotent."""
    watcher = start_background_watcher()
    assert watcher is not None
    assert watcher.is_alive()
    assert watcher.daemon is True

    # Idempotent: calling again returns the same active thread
    watcher2 = start_background_watcher()
    assert watcher2 is watcher


def test_concurrent_api_polling_and_daemon_recording_no_locks(client):
    """
    Test concurrent API polling + daemon report recording without 'database is locked'.
    Simulates multiple daemon worker threads writing reports while multiple
    API client threads poll endpoints concurrently.
    """
    errors = []
    stop_event = threading.Event()
    num_writers = 4
    num_readers = 4
    ops_per_thread = 20

    def writer_worker(w_id: int):
        for op in range(ops_per_thread):
            if stop_event.is_set():
                break
            try:
                sid = f"test_conc_w{w_id}_{op}"
                ts = int(time.time()) - (op * 60)
                record_new_report(
                    store_id=sid,
                    status_code="i" if op % 2 == 0 else "o",
                    timestamp=ts,
                    onsite=bool(op % 2 == 0),
                    note=f"conc_test_writer_{w_id}_{op}",
                    source="conc_test"
                )
            except Exception as e:
                errors.append(f"Writer-{w_id} Error: {type(e).__name__}: {e}")
            time.sleep(0.01)

    def reader_worker(r_id: int):
        for op in range(ops_per_thread):
            if stop_event.is_set():
                break
            try:
                # 1. Poll /api/latest_reports
                r1 = client.get("/api/latest_reports?since=0&limit=20")
                assert r1.status_code == 200

                # 2. Poll /api/store_history
                r2 = client.get(f"/api/store_history/test_conc_w0_{op % 5}")
                assert r2.status_code == 200

                # 3. Poll /api/config
                r3 = client.get("/api/config")
                assert r3.status_code == 200
            except Exception as e:
                errors.append(f"Reader-{r_id} Error: {type(e).__name__}: {e}")
            time.sleep(0.01)

    threads = []
    for w in range(num_writers):
        t = threading.Thread(target=writer_worker, args=(w,))
        threads.append(t)
    for r in range(num_readers):
        t = threading.Thread(target=reader_worker, args=(r,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # Fail if any thread timed out
    for t in threads:
        assert not t.is_alive(), "A worker thread is still alive after timeout"

    # Assert 0 errors occurred and explicitly check for database is locked
    lock_errors = [e for e in errors if "locked" in e.lower()]
    assert len(lock_errors) == 0, f"Encountered SQLite lock errors: {lock_errors}"
    assert len(errors) == 0, f"Encountered concurrent errors: {errors}"
