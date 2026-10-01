"""
Tests for Milestone M1: Combini Indexing & Restock Pattern Analytics
Validates:
1. Combini brand catalog & store normalization in SQLite database
2. Restock pattern analytics engine (get_chain_restock_analytics) across major chains and all chains
3. 24-hour distribution schema (len == 24) and 7-day DOW distribution schema (len == 7)
4. 4-Window day distribution consistency (window counts sum to total in-stock reports)
5. Calibrated logistics profiles (db_get_chain_profiles)
6. REST API endpoint GET /api/stats/combini_analytics response schema, status 200, latency < 150ms
"""

import os
import sys
import time
import pytest
from starlette.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import CHAIN_NAMES, COMBINI_CHAINS
from app.db import (
    get_db_connection,
    init_db,
    get_chain_restock_analytics,
    db_get_chain_profiles,
    get_chain_logistics_profile,
    db_get_stats_overview
)
from app.web import app


@pytest.fixture
def client():
    return TestClient(app)


def test_combini_brand_catalog_config():
    """Verify COMBINI_CHAINS and CHAIN_NAMES contain required brands."""
    expected_combini = [
        "seven", "lawson", "familymart", "ministop",
        "dailyyamazaki", "newdays", "bellmart", "poplar", "seicomart"
    ]
    for c in expected_combini:
        assert c in COMBINI_CHAINS, f"Missing {c} in COMBINI_CHAINS"
        assert c in CHAIN_NAMES, f"Missing {c} in CHAIN_NAMES"

    assert "tsutaya" in CHAIN_NAMES
    assert "apita" in CHAIN_NAMES
    assert "piagu" in CHAIN_NAMES


def test_store_normalization_migration():
    """Verify Daily Yamazaki, NewDays, and Bellmart are normalized away from 'other'."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Daily Yamazaki stores should be categorized as 'dailyyamazaki'
        cursor.execute("SELECT COUNT(*) FROM stores WHERE chain = 'dailyyamazaki';")
        dy_count = cursor.fetchone()[0]
        assert dy_count >= 8, f"Expected at least 8 Daily Yamazaki stores, got {dy_count}"

        # NewDays stores should be categorized as 'newdays'
        cursor.execute("SELECT COUNT(*) FROM stores WHERE chain = 'newdays';")
        nd_count = cursor.fetchone()[0]
        assert nd_count >= 3, f"Expected at least 3 NewDays stores, got {nd_count}"

        # Bellmart stores should be categorized as 'bellmart'
        cursor.execute("SELECT COUNT(*) FROM stores WHERE chain = 'bellmart';")
        bm_count = cursor.fetchone()[0]
        assert bm_count >= 1, f"Expected at least 1 Bellmart store, got {bm_count}"

        # Manual FamilyMart stores should be 'familymart'
        cursor.execute("SELECT chain FROM stores WHERE id LIKE 'manual_fm_%';")
        fm_rows = cursor.fetchall()
        for r in fm_rows:
            assert r[0] == "familymart"

        # Check no Daily Yamazaki remains as 'other'
        cursor.execute("""
            SELECT COUNT(*) FROM stores 
            WHERE chain = 'other' AND (name LIKE '%デイリーヤマザキ%' OR name LIKE '%ニューヤマザキ%');
        """)
        assert cursor.fetchone()[0] == 0

        # Check no NewDays remains as 'other'
        cursor.execute("""
            SELECT COUNT(*) FROM stores 
            WHERE chain = 'other' AND (name LIKE '%NewDays%' OR name LIKE '%ニューデイズ%');
        """)
        assert cursor.fetchone()[0] == 0


@pytest.mark.parametrize("chain_code", ["seven", "familymart", "lawson", "ministop", None])
def test_chain_restock_analytics_schema_and_math(chain_code):
    """
    Test get_chain_restock_analytics across major chains and all chains (None).
    Assert response schema:
    - 24-hour list length == 24
    - day-of-week list length == 7
    - window counts sum to total in-stock reports
    """
    res = get_chain_restock_analytics(chain_code=chain_code)
    
    assert res["status"] == "ok"
    assert "total_instock" in res
    assert "total_out_of_stock" in res
    assert "total_reports" in res
    assert "instock_rate" in res
    assert "windows" in res
    assert "by_hour" in res
    assert "by_dow" in res
    assert "peak_hours" in res
    assert "peak_dow" in res
    assert "peak_dow_label" in res
    assert "hourly_distribution" in res
    assert "dow_distribution" in res

    # Schema length constraints
    assert len(res["by_hour"]) == 24, "by_hour list length must be exactly 24"
    assert len(res["by_dow"]) == 7, "by_dow list length must be exactly 7"
    assert len(res["hourly_distribution"]) == 24
    assert len(res["dow_distribution"]) == 7

    total_instock = res["total_instock"]
    assert total_instock >= 0

    # Mathematical integrity: sum of hours equals sum of DOW equals total_instock
    assert sum(res["by_hour"]) == total_instock
    assert sum(res["by_dow"]) == total_instock

    # Mathematical integrity: window counts MUST sum to total in-stock reports
    windows = res["windows"]
    assert "early_morning" in windows
    assert "noon" in windows
    assert "afternoon_evening" in windows
    assert "night" in windows
    
    sum_windows = sum(windows.values())
    assert sum_windows == total_instock, f"Window counts ({sum_windows}) must sum to total in-stock ({total_instock})"

    # Verify peak hours are valid hours (0-23)
    for h in res["peak_hours"]:
        assert 0 <= h < 24

    # Verify peak DOW is valid (0-6)
    assert 0 <= res["peak_dow"] < 7


def test_chain_restock_analytics_with_pref():
    """Verify get_chain_restock_analytics works with prefecture filter."""
    res_osaka = get_chain_restock_analytics(chain_code="seven", pref="osaka")
    assert res_osaka["status"] == "ok"
    assert res_osaka["chain"] == "seven"
    assert res_osaka["pref"] == "osaka"
    assert len(res_osaka["by_hour"]) == 24
    assert len(res_osaka["by_dow"]) == 7
    assert sum(res_osaka["windows"].values()) == res_osaka["total_instock"]


def test_chain_logistics_profiles():
    """Verify calibrated logistics profiles exist and adhere to empirical patterns."""
    profiles = db_get_chain_profiles()
    for c in ["seven", "familymart", "lawson", "ministop", "dailyyamazaki", "newdays"]:
        assert c in profiles, f"Missing profile for {c}"
        p = profiles[c]
        assert "name" in p
        assert "peak_hours" in p
        assert "peak_window" in p
        assert "dow_peak" in p
        assert "base_cycle_days" in p
        assert len(p["peak_hours"]) > 0
        assert len(p["dow_peak"]) > 0

    # Seven peak hours calibrated to noon and evening/night
    p_seven = get_chain_logistics_profile("seven")
    assert 12 in p_seven["peak_hours"] or 13 in p_seven["peak_hours"] or 18 in p_seven["peak_hours"] or 22 in p_seven["peak_hours"]

    # Lawson peak hours calibrated to morning
    p_lawson = get_chain_logistics_profile("lawson")
    assert 7 in p_lawson["peak_hours"] or 8 in p_lawson["peak_hours"]


def test_combini_analytics_api_endpoint(client):
    """
    Test GET /api/stats/combini_analytics:
    - HTTP 200
    - Latency < 150ms
    - Correct JSON schema
    """
    # 1. Test specific chain
    t0 = time.time()
    res = client.get("/api/stats/combini_analytics?chain=seven")
    latency_ms = (time.time() - t0) * 1000

    assert res.status_code == 200
    assert latency_ms < 150, f"Endpoint latency {latency_ms:.1f}ms exceeded 150ms limit"

    data = res.json()
    assert data["status"] == "ok"
    assert data["chain"] == "seven"
    assert data["total_instock"] > 0
    assert len(data["by_hour"]) == 24
    assert len(data["by_dow"]) == 7
    assert sum(data["windows"].values()) == data["total_instock"]

    # 2. Test all chains (no chain parameter)
    t0 = time.time()
    res_all = client.get("/api/stats/combini_analytics")
    latency_all_ms = (time.time() - t0) * 1000

    assert res_all.status_code == 200
    assert latency_all_ms < 150, f"All-chains latency {latency_all_ms:.1f}ms exceeded 150ms limit"
    data_all = res_all.json()
    assert data_all["chain"] == "all"
    assert len(data_all["by_hour"]) == 24
    assert len(data_all["by_dow"]) == 7
    assert sum(data_all["windows"].values()) == data_all["total_instock"]

    # 3. Test with pref parameter
    res_pref = client.get("/api/stats/combini_analytics?chain=familymart&pref=osaka")
    assert res_pref.status_code == 200
    data_pref = res_pref.json()
    assert data_pref["chain"] == "familymart"
    assert data_pref["pref"] == "osaka"


def test_overview_subquery_optimization():
    """Verify db_get_stats_overview executes efficiently and returns valid aggregation."""
    overview = db_get_stats_overview()
    assert "by_chain" in overview
    assert "by_pref" in overview
    assert isinstance(overview["by_chain"], list)
    assert isinstance(overview["by_pref"], list)
    assert len(overview["by_chain"]) > 0
    assert len(overview["by_pref"]) > 0

    # Top chain should be seven or familymart
    top_chains = [c["chain"] for c in overview["by_chain"][:3]]
    assert "seven" in top_chains
    assert "familymart" in top_chains
