"""
Tests for AI Restock Prediction Dashboard (/dudoan, /goiy, /radar, /predict)
Validates endpoints:
- GET /dudoan, /goiy, /radar, /predict
- GET /api/stats/predictions
- Filter support (pref, chain, hour, window, sort, GPS proximity)
- JavaScript syntax check with node -c
"""

import os
import sys
import subprocess
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from starlette.testclient import TestClient
from app.web import app
from app.templates_prediction import render_dudoan_page


@pytest.fixture
def client():
    return TestClient(app)


def test_predictions_html_pages_return_200(client):
    """Verify all prediction route aliases return 200 HTML."""
    for path in ["/dudoan", "/goiy", "/radar", "/predict"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "POKÉDAR AI" in res.text or "POKEDAR AI" in res.text
        assert "Dự Đoán Restock Theo Giờ" in res.text
        assert "radar-status-banner" in res.text
        assert "hour-scroller" in res.text
        assert "prediction-list" in res.text


def test_predictions_api_basic(client):
    """Verify /api/stats/predictions returns structured restock forecast."""
    res = client.get("/api/stats/predictions")
    assert res.status_code == 200
    data = res.json()
    assert "server_time_jst" in data
    assert "current_hour" in data
    assert "current_dow" in data
    assert "current_dow_name" in data
    assert "hourly_distribution" in data
    assert "total_candidates" in data
    assert "predictions" in data

    # Check 24-hour distribution
    assert len(data["hourly_distribution"]) == 24
    assert sum(data["hourly_distribution"]) > 1000

    # Check prediction items
    preds = data["predictions"]
    assert len(preds) > 0
    first = preds[0]
    assert "store_id" in first
    assert "name" in first
    assert "pref" in first
    assert "chain" in first
    assert "score" in first
    assert 20 <= first["score"] <= 100
    assert "predicted_hour" in first
    assert 0 <= first["predicted_hour"] <= 23
    assert "predicted_window" in first
    assert "reasons" in first
    assert isinstance(first["reasons"], list)
    assert len(first["reasons"]) > 0


def test_predictions_api_pref_filter(client):
    """Verify filtering by prefecture."""
    res = client.get("/api/stats/predictions?pref=osaka&limit=30")
    assert res.status_code == 200
    data = res.json()
    preds = data["predictions"]
    assert len(preds) > 0
    for p in preds:
        assert p["pref"] == "osaka"


def test_predictions_api_chain_filter(client):
    """Verify filtering by chain."""
    res = client.get("/api/stats/predictions?chain=seven&limit=25")
    assert res.status_code == 200
    data = res.json()
    preds = data["predictions"]
    assert len(preds) > 0
    for p in preds:
        assert p["chain"] == "seven"


def test_predictions_api_hour_filter(client):
    """Verify filtering by specific target hour."""
    target_h = 10
    res = client.get(f"/api/stats/predictions?hour={target_h}&limit=20")
    assert res.status_code == 200
    data = res.json()
    preds = data["predictions"]
    assert len(preds) > 0
    for p in preds:
        assert p["predicted_hour"] == target_h


def test_predictions_api_gps_distance(client):
    """Verify GPS proximity calculations and distance sorting."""
    # Ga JR Imamiya, Osaka
    lat = 34.6540
    lng = 135.4925
    res = client.get(f"/api/stats/predictions?pref=osaka&user_lat={lat}&user_lng={lng}&sort=distance&limit=15")
    assert res.status_code == 200
    data = res.json()
    preds = data["predictions"]
    assert len(preds) > 0

    first = preds[0]
    assert first["distance_km"] is not None
    assert first["distance_str"] != ""
    assert first["walk_time_min"] is not None
    # Nearest store should be within 500m of Imamiya Station
    assert first["distance_km"] < 0.5

    # Verify ascending distance order
    for i in range(len(preds) - 1):
        if preds[i]["distance_km"] is not None and preds[i + 1]["distance_km"] is not None:
            assert preds[i]["distance_km"] <= preds[i + 1]["distance_km"]


def test_predictions_api_radius_stats(client):
    """Verify local radius statistics and in-stock rate calculations."""
    # Namba Station, Osaka: 3km radius
    lat = 34.6667
    lng = 135.5000
    r_km = 3.0
    res = client.get(f"/api/stats/predictions?user_lat={lat}&user_lng={lng}&max_dist_km={r_km}&limit=20")
    assert res.status_code == 200
    data = res.json()
    assert "radius_stats" in data
    rs = data["radius_stats"]
    assert rs["is_active"] is True
    assert rs["radius_km"] == 3.0
    assert rs["total_stores"] > 100
    assert rs["ever_restocked"] > 20
    assert rs["ever_restocked_rate"] > 5.0
    assert rs["peak_hour"] is not None
    assert 0 <= rs["peak_hour"] <= 23

    # All stores returned should be <= 3km
    preds = data["predictions"]
    for p in preds:
        if p["distance_km"] is not None:
            assert p["distance_km"] <= 3.05


def test_predictions_js_syntax_with_node():
    """Verify embedded JavaScript in prediction template has 0 syntax errors."""
    import re
    html = render_dudoan_page()
    script_matches = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    assert len(script_matches) >= 1, "Must contain at least 1 <script> tag"

    for idx, script_content in enumerate(script_matches):
        proc = subprocess.run(
            ["node", "-c"],
            input=script_content.encode("utf-8"),
            capture_output=True
        )
        assert proc.returncode == 0, f"Node syntax error in script #{idx+1}: {proc.stderr.decode('utf-8')}"


def test_predictions_api_30m_flash_green_and_red(client):
    """Verify 30-minute real-time flash rules for in-stock (green 100%) and out-of-stock (red 0% warning)."""
    # 1. Check status_filter=all
    res_all = client.get("/api/stats/predictions?status=all&limit=60")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert "radius_stats" in data_all
    assert "green_30m_count" in data_all["radius_stats"]
    assert "red_30m_count" in data_all["radius_stats"]

    # 2. Check status_filter=green (100% in stock within 30m)
    res_green = client.get("/api/stats/predictions?status=green")
    assert res_green.status_code == 200
    preds_green = res_green.json()["predictions"]
    for p in preds_green:
        assert p["flash_mode"] == "green"
        assert p["score"] == 100
        assert p["confidence_level"] == "flash_green"
        assert p["is_hot_30m"] is True
        assert p["is_cold_30m"] is False
        assert p["recent_min_ago"] <= 30
        assert any("100% CÓ HÀNG" in r for r in p["reasons"])

    # 3. Check status_filter=red (out-of-stock warning within 30m)
    res_red = client.get("/api/stats/predictions?status=red")
    assert res_red.status_code == 200
    preds_red = res_red.json()["predictions"]
    for p in preds_red:
        assert p["flash_mode"] == "red"
        assert p["score"] == 0
        assert p["confidence_level"] == "flash_red"
        assert p["is_cold_30m"] is True
        assert p["is_hot_30m"] is False
        assert p["recent_min_ago"] <= 30
        assert any("HẾT HÀNG" in r for r in p["reasons"])

    # 4. Check status_filter=predictions (pure algorithmic restock predictions)
    res_pred = client.get("/api/stats/predictions?status=predictions&limit=20")
    assert res_pred.status_code == 200
    preds_pure = res_pred.json()["predictions"]
    for p in preds_pure:
        assert p["flash_mode"] == "none"
        assert p["score"] >= 40


def test_predictions_html_contains_flash_animations(client):
    """Verify /dudoan HTML includes CSS animations and status filter tabs."""
    res = client.get("/dudoan")
    assert res.status_code == 200
    html = res.text
    assert "card-flash-green" in html
    assert "card-flash-red" in html
    assert "pulse-green-glow" in html
    assert "pulse-red-glow" in html
    assert "score-badge-flash-green" in html
    assert "score-badge-flash-red" in html
    assert "status-filter-tabs" in html
    assert "tab-count-green" in html
    assert "tab-count-red" in html

