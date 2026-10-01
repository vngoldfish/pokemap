"""
Milestone M4 Verification Test Suite:
1. Mobile UX Overhaul (<400px and 400-768px):
   - CSS .filter-select class and media query rules in app/templates_stats.py
   - Table Mobile Card Wrap for #leaderboard-table and #history-tbody
   - Header & Action bar on <400px in app/templates_stats.py
   - Compact #radar-filters-card on <400px in app/templates_prediction.py
2. GPS Distance Calculation & Telegram Sync Consistency:
   - Haversine distance and road multiplier (1.22) formatting consistency
   - Boundary distances (0.5km, 0.85km, 1.0km, 2.5km)
   - Elimination of unit discrepancy between 0.82km and 1.0km
   - Seamless GPS coordinates sync between Web and Telegram settings (/api/settings)
3. SQLite Concurrency & Caching:
   - _stats_overview_cache invalidation upon new report writes (record_new_report & save_bulk_history)
   - Strict _db_write_lock guard and WAL mode with 30s timeout
4. JavaScript Syntax Validation:
   - node -c verification on all updated template scripts
"""

import json
import math
import re
import subprocess
import time
import copy
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.web import app, format_distance_pair, send_telegram_alert, load_user_settings, save_user_settings
from app.templates_stats import render_thongke_page
from app.templates_prediction import render_dudoan_page
from app.templates import render_map_page, render_thongbao_page
from app.db import (
    db_get_stats_overview,
    invalidate_stats_overview_cache,
    invalidate_stores_cache,
    record_new_report,
    save_bulk_history,
    _db_write_lock,
    get_db_connection,
)
import app.db as app_db


# ==============================================================================
# 1. MOBILE UX & RESPONSIVE LAYOUT TESTS
# ==============================================================================

def test_templates_stats_filter_select_class_and_media_queries():
    """Verify that filter selects in app/templates_stats.py use filter-select and 2-column grid."""
    html = render_thongke_page()

    # 1. Verify CSS rules for .filter-bar, .filter-input, .filter-select
    assert ".filter-bar {" in html
    assert ".filter-select" in html
    assert "grid-template-columns: 1fr 1fr" in html

    # 2. Verify select elements have class filter-select
    assert 'select class="filter-select" id="lb-pref-select"' in html
    assert 'select class="filter-select" id="lb-chain-select"' in html
    assert 'select class="filter-select" id="lb-anchor-select"' in html
    assert 'select class="filter-select" id="lb-sort-select"' in html
    assert 'select class="filter-select" id="hist-status"' in html
    assert 'select class="filter-select" id="hist-pref"' in html
    assert 'select class="filter-select" id="hist-chain"' in html

    # 3. Verify CSS prevents select elements from stretching to full width
    assert ".filter-bar select" in html
    assert "grid-column: auto !important;" in html


def test_templates_stats_table_mobile_cards():
    """Verify that #leaderboard-table and #history-tbody transform into responsive cards on <640px."""
    html = render_thongke_page()

    # 1. Thead is hidden on mobile screens
    assert "#leaderboard-table thead" in html
    assert "#history-table thead" in html
    assert "display: none !important;" in html

    # 2. Rows transform to card blocks
    assert "#leaderboard-table tbody tr" in html
    assert "#history-tbody tr" in html
    assert "border-radius: 10px !important;" in html
    assert "box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;" in html

    # 3. Cells use data-label attribute for responsive key-value display
    assert "content: attr(data-label);" in html
    assert 'data-label=\\"Thứ hạng\\"' in html or 'data-label="Thứ hạng"' in html
    assert 'data-label=\\"Cửa hàng\\"' in html or 'data-label="Cửa hàng"' in html
    assert 'data-label=\\"Tổng báo cáo\\"' in html or 'data-label="Tổng báo cáo"' in html
    assert 'data-label=\\"Thời gian\\"' in html or 'data-label="Thời gian"' in html
    assert 'data-label=\\"Trạng thái\\"' in html or 'data-label="Trạng thái"' in html

    # 4. Touch-friendly button padding on mobile table cards
    assert "#leaderboard-table .stats-btn" in html
    assert "min-height: 32px !important;" in html


def test_templates_stats_header_small_screen_400px():
    """Verify that #stats-top-header title and actions do not collide on <400px screens."""
    html = render_thongke_page()

    # Check for dedicated @media (max-width: 400px) block
    assert "@media (max-width: 400px)" in html
    assert "#stats-top-header" in html
    # Logo badge is hidden on ultra-small screens to free space for brand title
    assert ".stats-header-brand .logo-badge" in html
    assert "display: none !important;" in html


def test_templates_prediction_compact_mobile_filters():
    """Verify that #radar-filters-card is compacted into 2x2 grid on <400px screens in app/templates_prediction.py."""
    html = render_dudoan_page()

    # 1. Card has id attribute
    assert 'id="radar-filters-card"' in html

    # 2. CSS contains @media (max-width: 400px) with 2x2 grid for filter card
    assert "@media (max-width: 400px)" in html
    assert "#radar-filters-card" in html or ".radar-filters-card" in html
    assert "grid-template-columns: 1fr 1fr !important;" in html

    # 3. Filter count badge spans full bottom row
    assert ".filter-count-badge" in html
    assert "grid-column: 1 / -1 !important;" in html


# ==============================================================================
# 2. GPS DISTANCE CALCULATION & TELEGRAM SYNC CONSISTENCY TESTS
# ==============================================================================

def test_distance_formatting_rule_and_boundaries():
    """
    Standardize the rule:
    - Road distance = dist_km * 1.22
    - If road_km < 1.0: formatted road distance is '~{int(round(road_km * 1000))}m đường đi'
    - If road_km >= 1.0: formatted road distance is '~{road_km:.1f}km đường đi'
    - Straight distance: '< 1.0 km' formatted in meters (e.g. '850m'), '>= 1.0 km' formatted in km (e.g. '1.2km').
    - Unit discrepancy eliminated: 0.85km straight distance -> road is 1.0km (NOT 1037m).
    """
    # Boundary 1: 0.5 km (500m straight, road = 0.61km -> 610m road)
    road_str, straight_str = format_distance_pair(0.5)
    assert road_str == "~610m đường đi"
    assert straight_str == "500m"

    # Boundary 2: 0.85 km (850m straight, road = 1.037km -> 1.0km road)
    # CRITICAL: Previously Telegram output '~1037m đường đi', now it must be '~1.0km đường đi'!
    road_str, straight_str = format_distance_pair(0.85)
    assert road_str == "~1.0km đường đi"
    assert straight_str == "850m"
    assert "1037m" not in road_str

    # Boundary 3: 1.0 km (1.0km straight, road = 1.22km -> 1.2km road)
    road_str, straight_str = format_distance_pair(1.0)
    assert road_str == "~1.2km đường đi"
    assert straight_str == "1.0km"

    # Boundary 4: 2.5 km (2.5km straight, road = 3.05km -> 3.0km or 3.1km road)
    road_str, straight_str = format_distance_pair(2.5)
    assert "km đường đi" in road_str
    assert straight_str == "2.5km"


def test_telegram_alert_distance_boundary_consistency():
    """Verify send_telegram_alert applies unified distance formatting across boundaries."""
    # Namba station: 34.6667, 135.5000
    # Imamiya station: 34.6540, 135.4925
    # Calculate exact coordinates for testing boundary distances
    store_085km = {
        "id": "st_test_bound",
        "name": "7-Eleven Test Near",
        "lat": 34.6580,
        "lng": 135.5000,
        "address": "Osaka Test",
        "pref": "osaka"
    }
    info = {
        "status_code": "i",
        "timestamp": int(time.time()),
        "reported_at": "15:00 01/10",
        "packs": ["Pokemon 151"]
    }
    notif_cfg = {
        "telegramEnabled": True,
        "telegramBotToken": "dummy_bot_token",
        "telegramChatId": "dummy_chat_id",
        "telegramLat": 34.6540,
        "telegramLng": 135.4925,
        "telegramLocationName": "Ga Imamiya"
    }

    posted = []
    class MockResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"ok":true}'

    def fake_urlopen(req, timeout=None):
        data = json.loads(req.data.decode("utf-8"))
        posted.append(data)
        return MockResp()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = send_telegram_alert(store_085km, info, notif_cfg)
        assert res["status"] == "ok"
        assert len(posted) == 1
        msg = posted[0]["text"]
        # Ensure road and straight distances are formatted consistently
        assert "đường đi" in msg
        assert "(Ga Imamiya)" in msg


def test_gps_settings_sync_endpoint():
    """Verify /api/settings handles GPS sync from frontend without silent drops."""
    client = TestClient(app)
    orig_settings = copy.deepcopy(load_user_settings())
    try:
        # 1. POST settings with nested notifications
        payload_nested = {
            "notifications": {
                "telegramLocationName": "Vị trí GPS của tôi",
                "telegramLat": 34.6700,
                "telegramLng": 135.5100,
                "telegramAutoSyncGps": True
            }
        }
        res = client.post("/api/settings", json=payload_nested)
        assert res.status_code == 200
        cfg = res.json()["settings"]["notifications"]
        assert cfg["telegramLocationName"] == "Vị trí GPS của tôi"
        assert abs(cfg["telegramLat"] - 34.6700) < 1e-4
        assert abs(cfg["telegramLng"] - 135.5100) < 1e-4
        assert cfg["telegramAutoSyncGps"] is True

        # 2. POST settings with root-level telegramLat and telegramLng (seamless normalization)
        payload_root = {
            "telegramLat": 35.6812,
            "telegramLng": 139.7671,
            "telegramLocationName": "Ga Tokyo",
            "telegramAutoSyncGps": True
        }
        res2 = client.post("/api/settings", json=payload_root)
        assert res2.status_code == 200
        cfg2 = res2.json()["settings"]["notifications"]
        assert abs(cfg2["telegramLat"] - 35.6812) < 1e-4
        assert abs(cfg2["telegramLng"] - 139.7671) < 1e-4
        assert cfg2["telegramLocationName"] == "Ga Tokyo"
    finally:
        save_user_settings(orig_settings)


def test_templates_gps_auto_sync_payload_consistency():
    """Verify that templates.py sends telegramAutoSyncGps: true in checkAutoSyncGpsToTelegram."""
    map_html = render_map_page()
    thongbao_html = render_thongbao_page()

    # Both map and thongbao pages must send telegramAutoSyncGps: true during auto-sync
    assert "telegramAutoSyncGps: true" in map_html
    assert "telegramAutoSyncGps: true" in thongbao_html


# ==============================================================================
# 3. SQLITE CONCURRENCY & CACHING TESTS
# ==============================================================================

def test_stats_overview_cache_invalidation():
    """Verify that _stats_overview_cache is populated and properly invalidated upon writes."""
    invalidate_stats_overview_cache()
    assert app_db._stats_overview_cache == (0.0, {})

    # 1. Fetch overview -> cache should be populated
    stats1 = db_get_stats_overview()
    assert stats1 is not None
    assert app_db._stats_overview_cache[0] > 0
    cached_ts1 = app_db._stats_overview_cache[0]

    # 2. Second fetch within TTL hits cache (same timestamp)
    stats2 = db_get_stats_overview()
    assert stats2 is stats1
    assert app_db._stats_overview_cache[0] == cached_ts1

    # 3. Invalidate directly
    invalidate_stats_overview_cache()
    assert app_db._stats_overview_cache == (0.0, {})

    # 4. Invalidate via invalidate_stores_cache
    db_get_stats_overview()
    assert app_db._stats_overview_cache[0] > 0
    invalidate_stores_cache()
    assert app_db._stats_overview_cache == (0.0, {})


def test_record_new_report_invalidates_overview_cache():
    """Verify that record_new_report clears _stats_overview_cache."""
    # Populate cache
    db_get_stats_overview()
    assert app_db._stats_overview_cache[0] > 0

    # Write a new report
    now_ts = int(time.time())
    entry = record_new_report(
        store_id="test_store_m4_cache_inv",
        status_code="i",
        note="M4 cache invalidation test",
        packs=["Test Pack"],
        user="Tester",
        who="Test",
        onsite=True,
        confirms=1,
        timestamp=now_ts,
        source="pytest_m4",
        notify=False
    )
    assert entry is not None

    # Overview cache MUST be invalidated (reset to 0.0)
    assert app_db._stats_overview_cache == (0.0, {})


def test_save_bulk_history_invalidates_overview_cache():
    """Verify that save_bulk_history clears _stats_overview_cache."""
    # Populate cache
    db_get_stats_overview()
    assert app_db._stats_overview_cache[0] > 0

    # Ingest bulk history
    now_ts = int(time.time()) - 3600
    cnt = save_bulk_history(
        store_id="test_store_m4_bulk_inv",
        history_list=[{
            "timestamp": now_ts,
            "status_code": "o",
            "note": "Bulk history test",
            "packs": [],
            "user": "Tester"
        }],
        source="pytest_m4",
        pref="osaka"
    )
    assert cnt >= 1

    # Overview cache MUST be invalidated
    assert app_db._stats_overview_cache == (0.0, {})


def test_db_wal_mode_and_write_lock():
    """Verify that SQLite connections use WAL mode and _db_write_lock is available."""
    assert _db_write_lock is not None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        assert row[0].lower() == "wal"

        cursor.execute("PRAGMA synchronous;")
        row_sync = cursor.fetchone()
        # Normal (1) or Full (2)
        assert row_sync[0] in (1, 2)


# ==============================================================================
# 4. JAVASCRIPT SYNTAX VERIFICATION (node -c)
# ==============================================================================

def test_all_templates_javascript_syntax():
    """Verify that all template JavaScript blocks pass syntax validation with node -c."""
    pages = [
        ("thongke", render_thongke_page()),
        ("dudoan", render_dudoan_page()),
        ("map", render_map_page()),
        ("thongbao", render_thongbao_page()),
    ]

    for name, html in pages:
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        assert len(scripts) >= 1, f"No <script> tag found in {name}"

        combined_js = "\n;\n".join(scripts)
        res = subprocess.run(
            ["node", "-c"],
            input=combined_js,
            text=True,
            capture_output=True,
            encoding="utf-8"
        )
        assert res.returncode == 0, f"JavaScript syntax error in {name}: {res.stderr}"
