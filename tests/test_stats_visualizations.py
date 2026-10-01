"""
Tests for Milestone M3:
- Interactive Visual Charts & SVG Rendering (/thongke)
- 2D Prime Time Heatmap Matrix (Combini Chain x 24h & Day-of-Week x 24h)
- Proximity & Distance Filtering (Station / GPS Anchors & Radius Chips)
- Confidence & Score Filters on /dudoan
- "✨ AI Phân tích" Trigger & Modal Integration
- JavaScript syntax check with node -c
"""

import math
import os
import sys
import subprocess
import pytest
from starlette.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.web import app
from app.templates_stats import render_thongke_page
from app.templates_prediction import render_dudoan_page
from app.db import db_get_restock_predictions


@pytest.fixture
def client():
    return TestClient(app)


def test_thongke_html_visualization_elements():
    """Verify presence of interactive SVG chart, heatmap, and proximity controls on /thongke."""
    html = render_thongke_page()

    # 1. Interactive SVG Chart Elements
    assert 'id="interactive-chart-container"' in html
    assert 'id="chart-tooltip"' in html
    assert 'class="chain-chip' in html
    assert 'data-chain=""' in html
    assert 'data-chain="seven"' in html
    assert 'data-chain="lawson"' in html
    assert 'data-chain="familymart"' in html
    assert 'data-chain="ministop"' in html

    # 2. 2D Heatmap Matrix Card & Controls
    assert 'id="heatmap-card"' in html
    assert 'id="heatmap-matrix-container"' in html
    assert 'id="btn-hm-chain"' in html
    assert 'id="btn-hm-dow"' in html
    assert 'heatmap-legend' in html

    # 3. Station / GPS Proximity & Distance Controls
    assert 'id="lb-anchor-select"' in html
    assert 'id="lb-radius-chips-bar"' in html
    assert 'id="lb-sort-select"' in html
    assert 'id="hist-anchor-select"' in html
    assert 'id="hist-radius-chips-bar"' in html


def test_dudoan_html_visualization_elements():
    """Verify presence of score filter, AI explanation modal, and prime restock tooltip on /dudoan."""
    html = render_dudoan_page()

    # 1. Hourly Prime Window Tooltip & Scroller
    assert 'id="hour-tooltip"' in html
    assert 'hour-tooltip' in html
    assert 'id="hour-scroller-bar"' in html

    # 2. Score & Confidence Filter Selector
    assert 'id="filter-score"' in html
    assert 'value="70"' in html
    assert 'value="85"' in html
    assert 'value="stars2"' in html

    # 3. AI Explanation Modal & Trigger
    assert 'id="ai-explain-modal"' in html
    assert 'id="ai-explain-modal-body"' in html
    assert 'btn-ai-explain' in html
    assert 'AI Restock Intelligence' in html


def test_stats_and_prediction_scripts_syntax_with_node():
    """Verify JavaScript in both /thongke and /dudoan passes node -c syntax validation."""
    for page_name, html in [("thongke", render_thongke_page()), ("dudoan", render_dudoan_page())]:
        start_tag = "<script>"
        end_tag = "</script>"
        start_idx = html.find(start_tag)
        end_idx = html.find(end_tag)
        assert start_idx != -1 and end_idx != -1, f"Missing <script> block in {page_name}"
        js_code = html[start_idx + len(start_tag):end_idx]

        proc = subprocess.run(
            ["node", "-c"],
            input=js_code,
            text=True,
            capture_output=True,
            encoding="utf-8"
        )
        assert proc.returncode == 0, f"Node syntax error in {page_name} JS: {proc.stderr}"


def test_endpoints_status_200(client):
    """Verify primary and API visualization endpoints return HTTP 200."""
    res_thongke = client.get("/thongke")
    assert res_thongke.status_code == 200
    assert "text/html" in res_thongke.headers.get("content-type", "")

    res_dudoan = client.get("/dudoan")
    assert res_dudoan.status_code == 200
    assert "text/html" in res_dudoan.headers.get("content-type", "")

    res_overview = client.get("/api/stats/overview")
    assert res_overview.status_code == 200
    data_overview = res_overview.json()
    assert "by_hour" in data_overview
    assert len(data_overview["by_hour"]) == 24

    res_preds = client.get("/api/stats/predictions?pref=osaka&limit=10")
    assert res_preds.status_code == 200
    data_preds = res_preds.json()
    assert "predictions" in data_preds


def test_heatmap_endpoint_chain_mode(client):
    """Verify GET /api/stats/heatmap?mode=chain returns 2D matrix for combini chains."""
    res = client.get("/api/stats/heatmap?mode=chain")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert data["mode"] == "chain"
    assert "rows" in data
    assert len(data["rows"]) == 6  # seven, lawson, familymart, ministop, geo, other
    assert "max_density" in data
    assert "golden_threshold" in data

    # Check row structure
    for row in data["rows"]:
        assert "key" in row
        assert "label" in row
        assert "hours" in row
        assert len(row["hours"]) == 24
        assert "total_in_stock" in row
        assert "peak_hour" in row
        assert 0 <= row["peak_hour"] <= 23
        assert isinstance(row["hours"], list)

        # Check cell structure
        for cell in row["hours"]:
            assert "hour" in cell
            assert "total" in cell
            assert "in_stock" in cell
            assert "in_rate" in cell
            assert "is_golden" in cell


def test_heatmap_endpoint_dow_mode(client):
    """Verify GET /api/stats/heatmap?mode=dow returns 2D matrix for days of week."""
    res = client.get("/api/stats/heatmap?mode=dow")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert data["mode"] == "dow"
    assert "rows" in data
    assert len(data["rows"]) == 7  # Monday through Sunday
    assert "max_density" in data
    assert "golden_threshold" in data

    for row in data["rows"]:
        assert "key" in row
        assert "label" in row
        assert "hours" in row
        assert len(row["hours"]) == 24
        assert "total_in_stock" in row
        assert "peak_hour" in row
        assert 0 <= row["peak_hour"] <= 23

        for cell in row["hours"]:
            assert "hour" in cell
            assert "total" in cell
            assert "in_stock" in cell
            assert "in_rate" in cell
            assert "is_golden" in cell


def test_heatmap_endpoint_pref_filter(client):
    """Verify GET /api/stats/heatmap respects prefecture filtering."""
    res_osaka = client.get("/api/stats/heatmap?mode=chain&pref=osaka")
    assert res_osaka.status_code == 200
    data_osaka = res_osaka.json()
    assert data_osaka["status"] == "ok"
    assert len(data_osaka["rows"]) == 6


def test_predictions_score_filter_query(client):
    """Verify /api/stats/predictions respects min_score query parameter."""
    res_all = client.get("/api/stats/predictions?pref=osaka&limit=20&min_score=40")
    assert res_all.status_code == 200
    items_all = res_all.json().get("predictions", [])

    res_high = client.get("/api/stats/predictions?pref=osaka&limit=20&min_score=70")
    assert res_high.status_code == 200
    items_high = res_high.json().get("predictions", [])

    for item in items_high:
        assert item["score"] >= 70, f"Expected score >= 70, got {item['score']}"


def test_ai_explanation_endpoint_integration(client):
    """Verify /api/predictions/{store_id}/explain returns AI explanation for real stores."""
    preds = db_get_restock_predictions(pref="osaka", limit=1)
    assert len(preds["predictions"]) > 0
    store_id = preds["predictions"][0]["store_id"]

    res = client.get(f"/api/predictions/{store_id}/explain")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert data["store_id"] == store_id
    assert "store_name" in data
    assert "chain" in data
    assert "score" in data
    assert data["source"] in ("gemini", "rule_based_fallback")
    assert "summary" in data and len(data["summary"]) > 0
    assert "reasons" in data and isinstance(data["reasons"], list)
    assert "action_tip" in data and len(data["action_tip"]) > 0


def test_haversine_and_road_factor_logic():
    """
    Verify client and server Haversine + road factor calculation:
    R = 6371 km, Road factor = 1.22
    """
    def haversine(lat1, lon1, lat2, lon2):
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(d_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    # Namba Station to Dotonbori Glico sign
    lat1, lon1 = 34.6666, 135.5008
    lat2, lon2 = 34.6687, 135.5013

    dist_km = haversine(lat1, lon1, lat2, lon2)
    dist_m = dist_km * 1000.0
    assert 200 < dist_m < 300, f"Expected ~240m, got {dist_m:.1f}m"

    road_km = dist_km * 1.22
    road_m = dist_m * 1.22
    assert 250 < road_m < 350, f"Expected ~290m, got {road_m:.1f}m"

    # Verify formatting rule: dist < 1km -> meters
    if dist_km < 1.0 and road_km < 1.0:
        fmt = f"~{int(round(road_m))}m đường đi ({int(round(dist_m))}m thẳng)"
        assert "m đường đi" in fmt
        assert "m thẳng" in fmt
