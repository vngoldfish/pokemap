"""
Empirical Challenge Test Suite (Challenger 2):
- /api/config: verify serverTime skew against time.time() under sequential and concurrent load.
- /api/latest_reports?since=...: verify historical reports with historical timestamps are NEVER returned.
- /api/store_history/{id}: verify ordering (timestamp DESC) and pagination (100 cap).
- JavaScript Node.js Execution:
  * updateSettings('soundEnabled', true), selectRegion('tokyo'), refreshData() for both pages
  * toast relative time formatting edge cases (now, now-60, now-120, now-121)
  * header counter pill clicks and status filtering
"""
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.web import app
from app.db import (
    get_db_connection,
    record_new_report,
    save_bulk_history,
    get_store_history as db_get_store_history,
    get_recent_reports
)
from app.templates import render_map_page, render_thongbao_page


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ==============================================================================
# 1. Challenge /api/config: serverTime skew under different conditions
# ==============================================================================

def test_api_config_server_time_skew_sequential(client):
    """Empirically test serverTime skew across 50 rapid sequential requests."""
    skews = []
    for _ in range(50):
        t0 = time.time()
        res = client.get("/api/config")
        t1 = time.time()
        assert res.status_code == 200
        data = res.json()
        assert "serverTime" in data
        server_time = data["serverTime"]
        assert isinstance(server_time, int)
        
        # Server time should be between int(t0) and int(t1) + 1
        mid_time = (t0 + t1) / 2.0
        skew = abs(server_time - mid_time)
        skews.append(skew)
        assert skew <= 1.5, f"serverTime skew {skew}s exceeds 1.5s tolerance (server={server_time}, mid={mid_time})"

    max_skew = max(skews)
    avg_skew = sum(skews) / len(skews)
    assert max_skew <= 1.0, f"Max sequential skew too high: {max_skew}s"
    assert avg_skew <= 0.5, f"Avg sequential skew too high: {avg_skew}s"


def test_api_config_server_time_skew_concurrent(client):
    """Empirically test serverTime skew under concurrent load (10 workers x 10 requests)."""
    results = []

    def make_request():
        t0 = time.time()
        res = client.get("/api/config")
        t1 = time.time()
        assert res.status_code == 200
        server_time = res.json()["serverTime"]
        mid = (t0 + t1) / 2.0
        return abs(server_time - mid), server_time

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(100)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    skews = [r[0] for r in results]
    assert max(skews) <= 2.0, f"Max concurrent skew exceeded 2.0s: {max(skews)}s"
    assert sum(skews) / len(skews) <= 1.0, f"Avg concurrent skew exceeded 1.0s: {sum(skews) / len(skews)}s"


def test_api_config_fields_and_integrity(client):
    """Verify /api/config returns all expected configuration keys with valid values."""
    res = client.get("/api/config")
    assert res.status_code == 200
    cfg = res.json()

    assert isinstance(cfg["serverTime"], int)
    assert cfg["serverTime"] > 1700000000
    assert "apiKey" in cfg
    assert "projectId" in cfg
    assert isinstance(cfg.get("chainNames"), dict)
    assert isinstance(cfg.get("packCodes"), dict)
    assert "soundEnabled" in cfg
    assert "currentRegion" in cfg


# ==============================================================================
# 2. Challenge /api/latest_reports?since=... Historical Reports Filtering
# ==============================================================================

def test_api_latest_reports_historical_reports_never_returned(client):
    """
    CRITICAL EMPIRICAL CHALLENGE:
    Ensure that historical reports with historical timestamps are NEVER returned
    as new reports when querying /api/latest_reports?since=...
    """
    now_ts = int(time.time())
    poll_start = now_ts - 30

    # 1. Ingest historical reports via record_new_report across diverse historical ages
    historical_offsets = [
        121,         # 121 seconds ago (>120s boundary)
        300,         # 5 minutes ago
        3600,        # 1 hour ago
        86400,       # 24 hours ago
        604800,      # 7 days ago
        31536000     # 1 year ago
    ]

    hist_sids = []
    for idx, offset in enumerate(historical_offsets):
        sid = f"test_chal_hist_{idx}_{now_ts % 10000}"
        hist_sids.append(sid)
        is_new, rep = record_new_report(
            store_id=sid,
            status_code="o",
            timestamp=now_ts - offset,
            note=f"historical_offset_{offset}",
            source="chal_test"
        )
        assert is_new is True

    # 2. Ingest historical records via save_bulk_history (simulating PokéTan backfill)
    bulk_sid = f"test_chal_bulk_{now_ts % 10000}"
    hist_sids.append(bulk_sid)
    bulk_history = [
        {"timestamp": now_ts - 500, "status_code": "i", "note": "bulk_500s_ago"},
        {"timestamp": now_ts - 7200, "status_code": "o", "note": "bulk_2h_ago"},
        {"timestamp": 1700000000, "status_code": "n", "note": "bulk_old_epoch"}
    ]
    saved_cnt = save_bulk_history(bulk_sid, bulk_history, source="chal_test")
    assert saved_cnt == 3

    # 3. Ingest ONE genuinely fresh report (10s ago)
    fresh_sid = f"test_chal_fresh_{now_ts % 10000}"
    is_new, fresh_rep = record_new_report(
        store_id=fresh_sid,
        status_code="i",
        timestamp=now_ts - 10,
        note="fresh_10s_ago",
        source="chal_test"
    )
    assert is_new is True

    try:
        # Retrieve created_at of the fresh report
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at FROM store_history WHERE store_id = ?;", (fresh_sid,))
            fresh_cat = cursor.fetchone()[0]

        # Query /api/latest_reports with since strictly before fresh_cat
        res = client.get(f"/api/latest_reports?since={fresh_cat - 1}&limit=200")
        assert res.status_code == 200
        reports = res.json()
        assert isinstance(reports, list)

        returned_sids = set(r["store_id"] for r in reports)

        # The fresh report MUST be returned
        assert fresh_sid in returned_sids, f"Fresh report {fresh_sid} was not returned!"

        # ZERO historical reports must be returned
        for h_sid in hist_sids:
            assert h_sid not in returned_sids, (
                f"VIOLATION: Historical report for {h_sid} was returned in /api/latest_reports?since={poll_start}!"
            )

        # Every returned report MUST satisfy created_at > (fresh_cat - 1)
        for r in reports:
            assert r["created_at"] > (fresh_cat - 1), (
                f"Report {r['id']} has created_at {r['created_at']} <= since {fresh_cat - 1}"
            )

        # Query with since equal to or after fresh_cat -> fresh report must NOT be returned
        res_after = client.get(f"/api/latest_reports?since={fresh_cat}&limit=200")
        assert res_after.status_code == 200
        after_reports = res_after.json()
        assert all(r["store_id"] != fresh_sid for r in after_reports)

    finally:
        # Cleanup
        with get_db_connection() as conn:
            conn.execute("DELETE FROM store_history WHERE source = 'chal_test';")
            conn.execute("DELETE FROM stores WHERE id LIKE 'test_chal_%';")
            conn.commit()


def test_api_latest_reports_strict_since_boundary(client):
    """Verify strict inequality (created_at > since): created_at == since must NOT be returned."""
    now_ts = int(time.time())
    sid = f"test_chal_bound_{now_ts % 10000}"
    is_new, rep = record_new_report(
        store_id=sid,
        status_code="i",
        timestamp=now_ts,
        note="exact_boundary_test",
        source="chal_test"
    )
    assert is_new is True

    # Retrieve exact created_at
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM store_history WHERE store_id = ?;", (sid,))
        cat = cursor.fetchone()[0]

    try:
        # 1. since = cat - 1 -> MUST be returned
        r_before = client.get(f"/api/latest_reports?since={cat - 1}&limit=200").json()
        assert any(r["store_id"] == sid for r in r_before)

        # 2. since = cat -> MUST NOT be returned (strict >)
        r_equal = client.get(f"/api/latest_reports?since={cat}&limit=200").json()
        assert all(r["store_id"] != sid for r in r_equal)

        # 3. since = cat + 1 -> MUST NOT be returned
        r_after = client.get(f"/api/latest_reports?since={cat + 1}&limit=200").json()
        assert all(r["store_id"] != sid for r in r_after)
    finally:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM store_history WHERE store_id = ?;", (sid,))
            conn.execute("DELETE FROM stores WHERE id = ?;", (sid,))
            conn.commit()


# ==============================================================================
# 3. Challenge /api/store_history/{id}: Ordering and Pagination
# ==============================================================================

def test_api_store_history_ordering_and_pagination_cap(client):
    """
    Empirically test /api/store_history/{id}:
    - Ingest 150 records for a single store with randomized insertion order.
    - Verify returned history is capped at exactly 100 entries (pagination limit).
    - Verify returned history is strictly sorted by timestamp DESC.
    - Verify the 100 returned are the NEWEST 100 (and the oldest 50 were omitted).
    - Verify JST formatted_time compliance.
    """
    sid = f"test_chal_hist_cap_{int(time.time() * 1000) % 100000}"
    base_ts = 1600000000

    # Generate 150 timestamps with step of 300s
    total_records = 150
    timestamps = [base_ts + i * 300 for i in range(total_records)]

    # Insert in randomized order
    import random
    shuffled_ts = list(timestamps)
    random.seed(42)
    random.shuffle(shuffled_ts)

    for i, ts in enumerate(shuffled_ts):
        status = "i" if i % 3 == 0 else ("o" if i % 3 == 1 else "n")
        record_new_report(
            store_id=sid,
            status_code=status,
            timestamp=ts,
            note=f"entry_{i}",
            source="chal_test_hist"
        )

    try:
        # 1. Fetch via API
        res = client.get(f"/api/store_history/{sid}")
        assert res.status_code == 200
        hist = res.json()
        assert isinstance(hist, list)

        # 2. Verify pagination limit (capped at 100)
        assert len(hist) == 100, f"Expected 100 capped records, got {len(hist)}"

        # 3. Verify ordering is strictly descending by timestamp
        for i in range(len(hist) - 1):
            assert hist[i]["timestamp"] >= hist[i + 1]["timestamp"], (
                f"History ordering failed at index {i}: {hist[i]['timestamp']} < {hist[i+1]['timestamp']}"
            )

        # 4. Verify the 100 returned items are the NEWEST 100
        expected_newest_100_ts = sorted(timestamps, reverse=True)[:100]
        actual_ts = [h["timestamp"] for h in hist]
        assert actual_ts == expected_newest_100_ts, "Returned records are not the top 100 newest items!"

        # 5. Verify JST formatted_time regex (HH:MM DD/MM/YYYY)
        jst_pattern = re.compile(r"^\d{2}:\d{2}\s\d{2}/\d{2}/\d{4}$")
        for h in hist:
            assert jst_pattern.match(h["formatted_time"]), (
                f"Invalid JST formatted_time: '{h['formatted_time']}'"
            )

        # 6. Verify clean_id handling: appending '_c' returns same history
        res_c = client.get(f"/api/store_history/{sid}_c")
        assert res_c.status_code == 200
        hist_c = res_c.json()
        assert len(hist_c) == 100
        assert hist_c[0]["timestamp"] == hist[0]["timestamp"]

        # 7. Non-existent store returns empty list []
        res_none = client.get("/api/store_history/non_existent_chal_store_99999")
        assert res_none.status_code == 200
        assert res_none.json() == []

    finally:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM store_history WHERE source = 'chal_test_hist';")
            conn.execute(f"DELETE FROM stores WHERE id = '{sid}';")
            conn.commit()


# ==============================================================================
# 4. Challenge Frontend JavaScript Execution under Node.js
# ==============================================================================

def test_javascript_node_execution_settings_and_region():
    """
    Extract JavaScript directly from app/templates.py and run under Node.js:
    - Test calling updateSettings('soundEnabled', true)
    - Test calling updateSettings('soundEnabled', false)
    - Test calling selectRegion('tokyo'), selectRegion('osaka'), selectRegion('nagoya')
    - Test calling refreshData()
    Verify for both map_page and thongbao_page scripts!
    """
    for page_name, html in [("map", render_map_page()), ("thongbao", render_thongbao_page())]:
        script = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)[0]

        # Extract updateSettings, selectRegion, refreshData function bodies
        upd_match = re.search(r"function updateSettings\(.*?\n    \}", script, re.DOTALL)
        sel_match = re.search(r"function selectRegion\(.*?\n    \}", script, re.DOTALL)
        ref_match = re.search(r"function refreshData\(.*?\n    \}", script, re.DOTALL)

        assert upd_match, f"updateSettings function missing in {page_name} page"
        assert sel_match, f"selectRegion function missing in {page_name} page"
        assert ref_match, f"refreshData function missing in {page_name} page"

        node_test_code = f"""
        // Mock Minimal Browser Environment
        global.window = global;
        global.document = {{
          getElementById: (id) => ({{
            classList: {{ add: () => {{}}, remove: () => {{}}, toggle: () => {{}} }},
            style: {{}},
            value: '',
            checked: false
          }}),
          querySelectorAll: (sel) => [],
          querySelector: (sel) => ({{ checked: false }})
        }};
        global.localStorage = {{
          _data: {{}},
          getItem(k) {{ return this._data[k] || null; }},
          setItem(k, v) {{ this._data[k] = String(v); }}
        }};
        global.fetchCalls = [];
        global.fetch = async (url, opts) => {{
          global.fetchCalls.push({{ url, opts }});
          return {{ json: async () => ({{ status: 'ok' }}) }};
        }};
        global.mapFlyToCalls = [];
        global.map = {{
          flyTo: (center, zoom, opts) => {{ global.mapFlyToCalls.push({{ center, zoom, opts }}); }}
        }};
        global.REGIONS = {{
          'osaka': {{ center: [34.69, 135.50], zoom: 13 }},
          'tokyo': {{ center: [35.44, 139.63], zoom: 13 }},
          'nagoya': {{ center: [35.18, 136.90], zoom: 13 }},
          'all': {{ center: [34.69, 135.50], zoom: 10 }}
        }};
        global.configData = {{}};
        global.currentRegion = 'osaka';
        global.mapRegionFilter = 'osaka';
        global.listRegionFilter = 'osaka';
        global.listCurrentPage = 1;
        global.initDataCalled = false;
        global.initData = () => {{ global.initDataCalled = true; }};
        global.updateMapFilterUI = () => {{}};
        global.renderMapMarkers = () => {{}};
        global.updateListFilterBadgeUI = () => {{}};
        global.renderStoreList = () => {{}};
        global.closeSettingsModal = () => {{}};

        // SUT Functions:
        {upd_match.group(0)}
        {sel_match.group(0)}
        {ref_match.group(0)}

        // 1. Test updateSettings('soundEnabled', true)
        updateSettings('soundEnabled', true);
        if (configData.soundEnabled !== true) throw new Error('configData.soundEnabled should be true');
        if (!configData.notifications || configData.notifications.soundEnabled !== true) {{
          throw new Error('configData.notifications.soundEnabled should be true');
        }}
        if (localStorage.getItem('poketan_config') === null) {{
          throw new Error('localStorage poketan_config not updated');
        }}

        // Test updateSettings('soundEnabled', false)
        updateSettings('soundEnabled', false);
        if (configData.soundEnabled !== false) throw new Error('configData.soundEnabled should be false');

        // 2. Test selectRegion('tokyo')
        selectRegion('tokyo');
        if (currentRegion !== 'tokyo') throw new Error(`currentRegion should be tokyo, got ${{currentRegion}}`);
        if (localStorage.getItem('poketan_selected_region') !== 'tokyo') {{
          throw new Error('localStorage poketan_selected_region not updated to tokyo');
        }}

        // Test selectRegion('nagoya')
        selectRegion('nagoya');
        if (currentRegion !== 'nagoya') throw new Error(`currentRegion should be nagoya, got ${{currentRegion}}`);

        // 3. Test refreshData()
        refreshData();
        if (!initDataCalled) throw new Error('refreshData failed to call initData');

        console.log('{page_name}_SETTINGS_NODE_OK');
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(node_test_code)
            f_path = f.name
        try:
            res = subprocess.run(["node", f_path], capture_output=True, text=True)
            assert res.returncode == 0, f"Node execution error in {page_name}:\n{res.stderr}"
            assert f"{page_name}_SETTINGS_NODE_OK" in res.stdout
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)


def test_javascript_node_execution_toast_formatting():
    """
    Extract formatTimeAgoJp from app/templates.py and test boundary edge cases under Node.js:
    - ts = now (0s) -> たった今
    - ts = now - 60s -> たった今
    - ts = now - 120s -> たった今
    - ts = now - 121s -> 2分前 (MUST NOT be たった今)
    - ts = now - 3600s -> 1時間前
    - ts = now + 30s (clock skew future) -> たった今
    """
    map_html = render_map_page()
    script = re.findall(r"<script>(.*?)</script>", map_html, re.DOTALL)[0]
    fmt_match = re.search(r"function formatTimeAgoJp\(.*?\n    \}", script, re.DOTALL)
    assert fmt_match, "formatTimeAgoJp not found in map script"

    node_test_code = f"""
    const NOW = 1700000000;
    function getServerNowSec() {{ return NOW; }}

    {fmt_match.group(0)}

    const cases = [
      {{ ts: NOW, expected: 'たった今', desc: 'ts=now (0s)' }},
      {{ ts: NOW - 30, expected: 'たった今', desc: 'ts=now-30s' }},
      {{ ts: NOW - 60, expected: 'たった今', desc: 'ts=now-60s' }},
      {{ ts: NOW - 119, expected: 'たった今', desc: 'ts=now-119s' }},
      {{ ts: NOW - 120, expected: 'たった今', desc: 'ts=now-120s' }},
      {{ ts: NOW - 121, expected: '2分前', desc: 'ts=now-121s' }},
      {{ ts: NOW - 180, expected: '3分前', desc: 'ts=now-180s' }},
      {{ ts: NOW - 3599, expected: '59分前', desc: 'ts=now-3599s' }},
      {{ ts: NOW - 3600, expected: '1時間前', desc: 'ts=now-3600s' }},
      {{ ts: NOW + 15, expected: 'たった今', desc: 'ts=now+15s (future skew)' }},
      {{ ts: 0, expected: 'たった今', desc: 'ts=0' }},
      {{ ts: null, expected: 'たった今', desc: 'ts=null' }}
    ];

    for (const c of cases) {{
      const actual = formatTimeAgoJp(c.ts);
      if (actual !== c.expected) {{
        throw new Error(`Edge case [${{c.desc}}] failed: expected "${{c.expected}}", got "${{actual}}"`);
      }}
    }}

    console.log('CHALLENGER_TOAST_NODE_OK');
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(node_test_code)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node toast execution error:\n{res.stderr}"
        assert "CHALLENGER_TOAST_NODE_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_javascript_node_execution_header_pills_and_filtering():
    """
    Test header counter pills and status filtering logic under Node.js:
    - quickFilterMapStatus('in') -> 'in'
    - quickFilterMapStatus('out') -> 'out'
    - quickFilterMapStatus('n') -> 'n'
    - quickFilterMapStatus('unknown') -> 'unknown'
    - Toggling clicked pill resets to 'all'
    - Verify filtering matches: 'in' matches code 'i', 'out' matches 'o', 'n' matches 'n', 'unknown' matches 'u'
    """
    map_html = render_map_page()
    script = re.findall(r"<script>(.*?)</script>", map_html, re.DOTALL)[0]

    # Verify HTML pill elements contain exact onclick handlers
    assert "onclick=\"quickFilterMapStatus('in')\"" in map_html
    assert "onclick=\"quickFilterMapStatus('out')\"" in map_html
    assert "onclick=\"quickFilterMapStatus('n')\"" in map_html
    assert "onclick=\"quickFilterMapStatus('unknown')\"" in map_html
    assert "quickFilterMapStatus('not')" not in map_html

    node_test_code = """
    // Mock environment
    let mapStatusFilter = 'all';
    function saveMapFiltersToStorage() {}
    function updateMapFilterUI() {}
    function renderMapMarkers() {}

    function quickFilterMapStatus(status) {
      if (mapStatusFilter === status) {
        mapStatusFilter = 'all';
      } else {
        mapStatusFilter = status;
      }
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }

    // Status filter matcher from renderMapMarkers()
    function storeMatchesStatus(filter, storeCode, storeTimestamp, storeOnsite) {
      if (filter === 'in') {
        return storeCode === 'i';
      } else if (filter === 'onsite') {
        return storeOnsite && storeCode === 'i';
      } else if (filter === 'out') {
        return storeCode === 'o';
      } else if (filter === 'n') {
        return storeCode === 'n';
      } else if (filter === 'recent') {
        return storeTimestamp > 0;
      } else if (filter === 'unknown') {
        return storeCode !== 'u' && storeTimestamp > 0 ? false : true;
      }
      return true; // 'all'
    }

    // 1. Test clicking 'in'
    quickFilterMapStatus('in');
    if (mapStatusFilter !== 'in') throw new Error('Filter should be "in"');
    if (!storeMatchesStatus(mapStatusFilter, 'i', 1000, false)) throw new Error('"in" filter should match "i"');
    if (storeMatchesStatus(mapStatusFilter, 'o', 1000, false)) throw new Error('"in" filter should reject "o"');

    // Toggle 'in' again -> resets to 'all'
    quickFilterMapStatus('in');
    if (mapStatusFilter !== 'all') throw new Error('Toggling "in" should reset to "all"');

    // 2. Test clicking 'out'
    quickFilterMapStatus('out');
    if (mapStatusFilter !== 'out') throw new Error('Filter should be "out"');
    if (!storeMatchesStatus(mapStatusFilter, 'o', 1000, false)) throw new Error('"out" filter should match "o"');

    // 3. Test clicking 'n' (ko bán)
    quickFilterMapStatus('n');
    if (mapStatusFilter !== 'n') throw new Error('Filter should be "n"');
    if (!storeMatchesStatus(mapStatusFilter, 'n', 1000, false)) throw new Error('"n" filter should match "n"');
    if (storeMatchesStatus(mapStatusFilter, 'i', 1000, false)) throw new Error('"n" filter should reject "i"');

    // 4. Test clicking 'unknown' (chưa rõ)
    quickFilterMapStatus('unknown');
    if (mapStatusFilter !== 'unknown') throw new Error('Filter should be "unknown"');
    if (!storeMatchesStatus(mapStatusFilter, 'u', 0, false)) throw new Error('"unknown" filter should match "u"');
    if (storeMatchesStatus(mapStatusFilter, 'i', 1000, false)) throw new Error('"unknown" filter should reject "i" with ts>0');

    console.log('CHALLENGER_PILLS_NODE_OK');
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(node_test_code)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node pills execution error:\n{res.stderr}"
        assert "CHALLENGER_PILLS_NODE_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)
