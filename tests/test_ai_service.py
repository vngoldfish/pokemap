"""
Unit and Integration Tests for Milestone M2:
- Hybrid Prediction Engine & AI Explanation with Gemini Fallback
- Prediction Candidate Bounding Box Pruning (< 150ms latency)
- Web Route: GET /api/predictions/{store_id}/explain
- Web Route: GET /api/stats/predictions?with_ai=true
"""

import json
import os
import sys
import time
from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.web import app
from app import config
from app.db import (
    db_get_restock_predictions,
    db_get_store_prediction,
    invalidate_stores_cache,
    get_stores
)
from app.services.ai_service import (
    generate_store_prediction_explanation,
    generate_rule_based_explanation,
    clear_explanation_cache
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure cache is cleared between tests."""
    clear_explanation_cache()
    invalidate_stores_cache()
    yield
    clear_explanation_cache()
    invalidate_stores_cache()


SAMPLE_STORE_DATA = {
    "store_id": "test_seven_osaka_001",
    "name": "7-Eleven Chuo-ku Dotonbori",
    "pref": "osaka",
    "chain": "seven",
    "chain_name": "7-Eleven (セブン-イレブン)",
    "current_status": "u",
    "score": 82,
    "flash_mode": "none",
    "predicted_hour": 11,
    "predicted_window": "11:00 - 12:30 JST",
    "current_dow_name": "Thứ Sáu",
    "avg_interval_days": 2.5,
    "days_since_last_in": 2.4,
    "truck_en_route": False,
    "top_packs": ["Stellar Emerald", "Inferno"],
    "reasons": [
        "Trùng khớp khung giờ cao điểm chuỗi (11h, 12h, 13h, 21h, 22h)",
        "Đúng chu kỳ restock định kỳ ~2.5 ngày (đã qua 2.4 ngày)",
        "Thứ Sáu là ngày có tần suất về hàng lớn nhất"
    ],
    "action_tip": "⚡ Đang trong khung giờ vàng! Tỷ lệ lên kệ cao nhất trong ngày."
}


def test_ai_service_empty_api_key_fallback(monkeypatch):
    """
    Test empty GEMINI_API_KEY falls back to rule-based explanation cleanly
    with source='rule_based_fallback'.
    """
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    clear_explanation_cache()

    result = generate_store_prediction_explanation(SAMPLE_STORE_DATA)

    assert result["status"] == "ok"
    assert result["store_id"] == "test_seven_osaka_001"
    assert result["store_name"] == "7-Eleven Chuo-ku Dotonbori"
    assert result["chain"] == "seven"
    assert result["score"] == 82
    assert result["source"] == "rule_based_fallback"
    assert isinstance(result["summary"], str) and len(result["summary"]) > 10
    assert isinstance(result["reasons"], list) and len(result["reasons"]) >= 1
    assert isinstance(result["action_tip"], str) and len(result["action_tip"]) > 5


def test_ai_service_gemini_exception_fallback(monkeypatch):
    """
    Test simulated Gemini exception (network timeout, API error, 429 quota)
    falls back cleanly to rule-based explanation without 500 error or crash.
    """
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake_gemini_api_key_12345")
    clear_explanation_cache()

    # Simulate network timeout during Gemini call
    with patch("app.services.ai_service._call_gemini_api", side_effect=TimeoutError("Connection timed out after 2.0s")):
        result = generate_store_prediction_explanation(SAMPLE_STORE_DATA)

    assert result["status"] == "ok"
    assert result["source"] == "rule_based_fallback"
    assert result["store_id"] == "test_seven_osaka_001"
    assert result["score"] == 82
    assert isinstance(result["summary"], str)
    assert len(result["reasons"]) > 0


def test_ai_service_mocked_gemini_success(monkeypatch):
    """
    Test mocked successful Gemini API response returns source='gemini'
    with LLM-generated summary, reasons, and action tip.
    """
    monkeypatch.setattr(config, "GEMINI_API_KEY", "valid_mock_api_key_67890")
    clear_explanation_cache()

    mock_gemini_response = json.dumps({
        "summary": "7-Eleven Dotonbori có xác suất restock rất khả quan trong khung giờ trưa nay.",
        "reasons": [
            "Đúng chu kỳ thứ Sáu của chuỗi 7-Eleven",
            "Đã 2.4 ngày kể từ đợt restock trước",
            "Các pack hot Stellar Emerald thường về vào khung giờ này"
        ],
        "action_tip": "Nên có mặt lúc 11:15 để đón đợt hàng mới lên kệ."
    })

    with patch("app.services.ai_service._call_gemini_api", return_value=mock_gemini_response):
        result = generate_store_prediction_explanation(SAMPLE_STORE_DATA)

    assert result["status"] == "ok"
    assert result["source"] == "gemini"
    assert result["store_id"] == "test_seven_osaka_001"
    assert result["score"] == 82
    assert "Dotonbori" in result["summary"]
    assert len(result["reasons"]) == 3
    assert "11:15" in result["action_tip"]


def test_ai_service_in_memory_caching(monkeypatch):
    """
    Verify in-memory caching: subsequent calls for the same store_id
    hit the cache and execute in sub-millisecond time.
    """
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    clear_explanation_cache()

    # First call primes cache
    res1 = generate_store_prediction_explanation(SAMPLE_STORE_DATA)

    # Second call should be instant cache hit
    t0 = time.perf_counter()
    res2 = generate_store_prediction_explanation(SAMPLE_STORE_DATA)
    latency_ms = (time.perf_counter() - t0) * 1000

    assert res1 == res2
    assert latency_ms < 2.0, f"Cache latency too high: {latency_ms:.3f} ms"


def test_explain_endpoint_success(client):
    """
    Test endpoint GET /api/predictions/{store_id}/explain returns HTTP 200
    with required schema.
    """
    # Find a real store ID from the database
    preds = db_get_restock_predictions(pref="osaka", limit=1)
    assert len(preds["predictions"]) > 0
    real_store_id = preds["predictions"][0]["store_id"]

    resp = client.get(f"/api/predictions/{real_store_id}/explain")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["store_id"] == real_store_id
    assert "store_name" in data and len(data["store_name"]) > 0
    assert "chain" in data
    assert "score" in data and isinstance(data["score"], int)
    assert data["source"] in ("gemini", "rule_based_fallback")
    assert "summary" in data and len(data["summary"]) > 0
    assert "reasons" in data and isinstance(data["reasons"], list)
    assert "action_tip" in data and len(data["action_tip"]) > 0


def test_explain_endpoint_not_found(client):
    """
    Test endpoint GET /api/predictions/{store_id}/explain returns HTTP 404
    when store_id does not exist.
    """
    resp = client.get("/api/predictions/nonexistent_store_99999_xyz/explain")
    assert resp.status_code == 404
    data = resp.json()
    assert data["status"] == "error"
    assert "not found" in data["message"].lower()


def test_predictions_with_ai_query_param(client):
    """
    Test query parameter ?with_ai=true on /api/stats/predictions:
    Verifies top 3 candidates have 'ai_explanation' attached while maintaining fast response.
    """
    resp = client.get("/api/stats/predictions?pref=osaka&limit=5&with_ai=true")
    assert resp.status_code == 200
    data = resp.json()

    predictions = data.get("predictions", [])
    assert len(predictions) > 0

    # Top 3 should have ai_explanation attached
    for idx, cand in enumerate(predictions[:3]):
        assert "ai_explanation" in cand, f"Candidate {idx} missing ai_explanation"
        ai_exp = cand["ai_explanation"]
        assert ai_exp["status"] == "ok"
        assert ai_exp["source"] in ("gemini", "rule_based_fallback")
        assert "summary" in ai_exp
        assert "reasons" in ai_exp
        assert "action_tip" in ai_exp

    # Remaining candidates (> 3) should NOT have ai_explanation to keep response lean
    for cand in predictions[3:]:
        assert "ai_explanation" not in cand


def test_bounding_box_pruning_latency():
    """
    Test prediction latency with bounding box candidate pruning in SQLite.
    Verify uncached prediction with radius filter responds in < 150ms.
    """
    invalidate_stores_cache()

    # User coordinates near Umeda, Osaka with 3.0km radius filter
    t0 = time.perf_counter()
    result = db_get_restock_predictions(
        user_lat=34.7024,
        user_lng=135.4959,
        max_dist_km=3.0,
        limit=60
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    assert latency_ms < 150.0, f"Uncached bounded query too slow: {latency_ms:.2f} ms (expected < 150ms)"
    assert result["radius_stats"]["is_active"] is True
    assert result["radius_stats"]["total_stores"] > 0
    assert len(result["predictions"]) > 0

    # Verify every returned store is within 3.0km
    for cand in result["predictions"]:
        if cand.get("distance_km") is not None:
            assert cand["distance_km"] <= 3.05, f"Store {cand['store_id']} distance {cand['distance_km']} exceeds 3.0km"


def test_rule_based_explanation_pure_helper_never_crashes():
    """
    Test generate_rule_based_explanation with empty, None, and corrupted data
    to guarantee zero crashes in all edge cases.
    """
    cases = [
        {},
        {"store_id": None, "score": None},
        {"store_id": "test_s2", "score": 0, "flash_mode": "red"},
        {"store_id": "test_s3", "score": 100, "flash_mode": "green"},
        {"store_id": "test_s4", "score": 88, "truck_en_route": True},
        {"invalid_key": 1234}
    ]

    for c in cases:
        out = generate_rule_based_explanation(c)
        assert isinstance(out, dict)
        assert out["status"] == "ok"
        assert out["source"] == "rule_based_fallback"
        assert isinstance(out["summary"], str)
        assert isinstance(out["reasons"], list)
        assert isinstance(out["action_tip"], str)
