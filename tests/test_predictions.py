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
