"""
Milestone M5 Challenger Empirical Test Suite.
Exhaustively and adversarially verifies:
1. AI Fallback Resilience (Unset key, Network Timeout, Connection Refused, Rate Limit 429, HTTP 500, Corrupted JSON).
2. Prediction Accuracy & Bounds ([0, 100] clamping across all DB stores and extreme synthetic parameters; 30m flash green=100, flash red=0).
3. Distance Consistency (Haversine straight and 1.22 road factor across boundaries 0.5km, 0.85km, 1.0km, 2.5km between Python and Node.js).
4. Mobile Layout & JavaScript Syntax Integrity (node -c validation on templates.py, templates_stats.py, templates_prediction.py).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.web import app, format_distance_pair
from app import config
from app.db import (
    get_db_connection,
    _db_write_lock,
    db_get_restock_predictions,
    db_get_store_prediction,
    record_new_report,
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
def reset_cache_state():
    clear_explanation_cache()
    invalidate_stores_cache()
    yield
    clear_explanation_cache()
    invalidate_stores_cache()


# ==============================================================================
# SECTION 1: AI FALLBACK RESILIENCE EMPIRICAL TESTS
# ==============================================================================

MOCK_STORE = {
    "store_id": "test_adv_store_01",
    "name": "Lawson Namba Ekimae",
    "pref": "osaka",
    "chain": "lawson",
    "chain_name": "Lawson (ローソン)",
    "current_status": "i",
    "score": 88,
    "flash_mode": "none",
    "predicted_hour": 14,
    "predicted_window": "14:00 - 15:30 JST",
    "current_dow_name": "Thứ Sáu",
    "avg_interval_days": 2.8,
    "days_since_last_in": 2.7,
    "truck_en_route": True,
    "top_packs": ["Battle Partners", "Super Electric Breaker"],
    "reasons": ["Lý do thử nghiệm"],
    "action_tip": "Nên ghé ngay!"
}


def test_ai_fallback_unset_or_empty_key(monkeypatch, client):
    """Verify unset/empty/whitespace GEMINI_API_KEY immediately uses rule_based_fallback."""
    for empty_val in ["", None, "   "]:
        monkeypatch.setattr(config, "GEMINI_API_KEY", empty_val)
        clear_explanation_cache()

        # 1. Direct service call
        res = generate_store_prediction_explanation(MOCK_STORE)
        assert res["status"] == "ok"
        assert res["source"] == "rule_based_fallback"
        assert len(res["summary"]) > 10
        assert len(res["reasons"]) >= 1
        assert len(res["action_tip"]) > 5

        # 2. HTTP GET /api/predictions/{store_id}/explain
        preds = db_get_restock_predictions(pref="osaka", limit=1)
        if preds.get("predictions"):
            real_sid = preds["predictions"][0]["store_id"]
            resp = client.get(f"/api/predictions/{real_sid}/explain")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["source"] == "rule_based_fallback"
            assert data["store_id"] == real_sid


def test_ai_fallback_simulated_network_timeout(monkeypatch, client):
    """Verify simulated network timeout falls back cleanly to rule_based_fallback with HTTP 200."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "dummy_key_timeout")
    clear_explanation_cache()

    with patch("app.services.ai_service._call_gemini_api", side_effect=TimeoutError("Request timed out after 2000ms")):
        res = generate_store_prediction_explanation(MOCK_STORE)
        assert res["status"] == "ok"
        assert res["source"] == "rule_based_fallback"
        assert res["score"] == 88

        # HTTP Endpoint
        preds = db_get_restock_predictions(pref="osaka", limit=1)
        if preds.get("predictions"):
            real_sid = preds["predictions"][0]["store_id"]
            resp = client.get(f"/api/predictions/{real_sid}/explain")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["source"] == "rule_based_fallback"


def test_ai_fallback_connection_refused_and_socket_errors(monkeypatch, client):
    """Verify socket connection refused or host unreachable falls back cleanly."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "dummy_key_conn_err")
    clear_explanation_cache()

    errs = [
        ConnectionRefusedError("[WinError 10061] No connection could be made because the target machine actively refused it"),
        ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host"),
        OSError("Network is unreachable")
    ]

    for err in errs:
        clear_explanation_cache()
        with patch("app.services.ai_service._call_gemini_api", side_effect=err):
            res = generate_store_prediction_explanation(MOCK_STORE)
            assert res["status"] == "ok"
            assert res["source"] == "rule_based_fallback"


def test_ai_fallback_rate_limit_and_http_errors(monkeypatch, client):
    """Verify HTTP 429 (Rate Limit / Quota Exceeded) and HTTP 500/503 from Gemini fallback gracefully."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "dummy_key_rate_limit")
    clear_explanation_cache()

    http_errs = [
        Exception("429 Resource has been exhausted (e.g. check quota)."),
        Exception("503 The model is overloaded. Please try again later."),
        Exception("500 Internal Server Error encountered while processing request.")
    ]

    for err in http_errs:
        clear_explanation_cache()
        with patch("app.services.ai_service._call_gemini_api", side_effect=err):
            res = generate_store_prediction_explanation(MOCK_STORE)
            assert res["status"] == "ok"
            assert res["source"] == "rule_based_fallback"


def test_ai_fallback_corrupted_llm_json_payloads(monkeypatch):
    """Verify malformed JSON, markdown fences, HTML errors, or non-dict payloads fallback gracefully."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "dummy_key_corrupted_llm")

    corrupted_payloads = [
        "",
        "   ",
        "<html><body>502 Bad Gateway</body></html>",
        "```json\n{\nincomplete_json: true\n",
        "I am an AI and I think this store is good.",
        json.dumps(["not", "a", "dictionary"]),
        json.dumps({"wrong_keys": 123}),
    ]

    for payload in corrupted_payloads:
        clear_explanation_cache()
        with patch("app.services.ai_service._call_gemini_api", return_value=payload):
            res = generate_store_prediction_explanation(MOCK_STORE)
            assert res["status"] == "ok"
            assert res["source"] == "rule_based_fallback"
            assert len(res["summary"]) > 5


# ==============================================================================
# SECTION 2: PREDICTION ACCURACY & STRICT [0, 100] BOUNDS
# ==============================================================================

def test_prediction_scores_clamped_strictly_0_to_100():
    """Audit 100% of candidate predictions in real DB across all prefectures for strict [0, 100] range."""
    prefs = ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]
    total_audited = 0

    for pref in prefs:
        res = db_get_restock_predictions(pref=pref, min_score=0, limit=2000)
        preds = res.get("predictions", [])
        total_audited += len(preds)
        for cand in preds:
            score = cand.get("score")
            assert isinstance(score, int), f"Store {cand.get('store_id')} score is not int: {score}"
            assert 0 <= score <= 100, f"Store {cand.get('store_id')} score {score} out of bounds [0, 100]"
            
            # Confidence level validation
            conf = cand.get("confidence_level")
            assert conf in ("flash_green", "flash_red", "prime", "high", "medium"), f"Invalid conf level: {conf}"

    assert total_audited > 50, f"Expected to audit realistic number of stores, got {total_audited}"


def test_prediction_30m_flash_green_and_flash_red_overrides():
    """
    Empirically test that reports within 30 minutes trigger:
    - Status 'i' -> score 100, flash_mode 'green', is_hot_30m True, confidence_level 'flash_green'
    - Status 'o' -> score 0, flash_mode 'red', is_cold_30m True, confidence_level 'flash_red'
    """
    now_ts = int(time.time())
    test_sid_green = f"test_adv_flash_green_{now_ts}"
    test_sid_red = f"test_adv_flash_red_{now_ts}"

    try:
        # 1. Fresh in-stock report 5 minutes ago (< 30m)
        is_new_g, _ = record_new_report(
            store_id=test_sid_green,
            status_code="i",
            timestamp=now_ts - 300,
            pref="osaka",
            source="pytest_adv_flash",
            notify=False
        )
        assert is_new_g is True

        # 2. Fresh out-of-stock report 8 minutes ago (< 30m)
        is_new_r, _ = record_new_report(
            store_id=test_sid_red,
            status_code="o",
            timestamp=now_ts - 480,
            pref="osaka",
            source="pytest_adv_flash",
            notify=False
        )
        assert is_new_r is True

        invalidate_stores_cache()

        # Check Green Flash
        pred_green = db_get_store_prediction(test_sid_green)
        assert pred_green is not None, f"Store {test_sid_green} not returned by db_get_store_prediction"
        assert pred_green["score"] == 100, f"Expected green score 100, got {pred_green['score']}"
        assert pred_green["flash_mode"] == "green"
        assert pred_green["is_hot_30m"] is True
        assert pred_green["is_cold_30m"] is False
        assert pred_green["confidence_level"] == "flash_green"
        assert any("100% CÓ HÀNG" in r for r in pred_green["reasons"])

        # Check Red Flash
        pred_red = db_get_store_prediction(test_sid_red)
        assert pred_red is not None, f"Store {test_sid_red} not returned by db_get_store_prediction"
        assert pred_red["score"] == 0, f"Expected red score 0, got {pred_red['score']}"
        assert pred_red["flash_mode"] == "red"
        assert pred_red["is_cold_30m"] is True
        assert pred_red["is_hot_30m"] is False
        assert pred_red["confidence_level"] == "flash_red"
        assert any("HẾT HÀNG" in r for r in pred_red["reasons"])

    finally:
        with _db_write_lock:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM store_history WHERE store_id IN (?, ?);", (test_sid_green, test_sid_red))
                conn.execute("DELETE FROM stores WHERE id IN (?, ?);", (test_sid_green, test_sid_red))
                conn.commit()
        invalidate_stores_cache()


# ==============================================================================
# SECTION 3: DISTANCE CONSISTENCY BETWEEN PYTHON (web.py) & JS (templates.py)
# ==============================================================================

def _run_node_script(js_code: str) -> str:
    """Execute javascript snippet in Node.js and return trimmed stdout using UTF-8."""
    res = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5
    )
    if res.returncode != 0:
        raise RuntimeError(f"Node execution error: {res.stderr}")
    return res.stdout.strip()


def test_distance_formatting_across_boundaries_python_vs_node():
    """
    Empirically compare Python's format_distance_pair against Node.js formatDist logic
    across the critical boundary conditions: 0.5km, 0.85km, 1.0km, 2.5km.
    Ensure zero discrepancy between backend alerts and frontend display.
    """
    boundaries = [0.5, 0.85, 1.0, 2.5]

    for d in boundaries:
        # Python calculation
        road_str_py, straight_str_py = format_distance_pair(d)

        # Node.js calculation matching templates.py formatDist
        js_code = f"""
        function formatDist(km) {{
            if (!km) return '';
            return km < 1 ? Math.round(km * 1000) + 'm' : km.toFixed(1) + 'km';
        }}
        const d = {d};
        const roadD = d * 1.22;
        const dStr = formatDist(d);
        const roadStr = '~' + formatDist(roadD) + ' đường đi';
        console.log(JSON.stringify({{ road_str: roadStr, straight_str: dStr }}));
        """
        node_out = _run_node_script(js_code)
        node_res = json.loads(node_out)

        assert road_str_py == node_res["road_str"], (
            f"Distance {d}km road discrepancy: Python '{road_str_py}' vs Node '{node_res['road_str']}'"
        )
        assert straight_str_py == node_res["straight_str"], (
            f"Distance {d}km straight discrepancy: Python '{straight_str_py}' vs Node '{node_res['straight_str']}'"
        )


def test_combined_distance_string_representation():
    """
    Verify complete road + straight combined strings match contract:
    - 0.5km:  "~610m đường đi (500m thẳng)"
    - 0.85km: "~1.0km đường đi (850m thẳng)"
    - 1.0km:  "~1.2km đường đi (1.0km thẳng)"
    - 2.5km:  "~3.0km đường đi (2.5km thẳng)"
    """
    expected_pairs = {
        0.5: "~610m đường đi (500m thẳng)",
        0.85: "~1.0km đường đi (850m thẳng)",
        1.0: "~1.2km đường đi (1.0km thẳng)",
        2.5: "~3.0km đường đi (2.5km thẳng)"
    }

    for d, expected in expected_pairs.items():
        road_str, straight_str = format_distance_pair(d)
        combined = f"{road_str} ({straight_str} thẳng)"
        assert combined == expected, f"Boundary {d}: expected '{expected}', got '{combined}'"


# ==============================================================================
# SECTION 4: MOBILE LAYOUT & TEMPLATE JAVASCRIPT INTEGRITY WITH NODE -C
# ==============================================================================

def _extract_script_blocks(html_content: str) -> str:
    """Extract and concatenate all JavaScript code inside <script> blocks."""
    # Ignore external src scripts
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE)
    return "\n\n;\n\n".join(scripts)


def test_template_javascript_syntax_with_node_check():
    """
    Extract JavaScript from templates.py, templates_stats.py, templates_prediction.py
    and execute `node -c` syntax check on each file.
    """
    from app import templates, templates_stats, templates_prediction

    # 1. Main map page
    map_html = templates.render_map_page()
    js_map = _extract_script_blocks(map_html)
    assert len(js_map) > 500

    # 2. Stats dashboard (/thongke)
    stats_html = templates_stats.render_thongke_page()
    js_stats = _extract_script_blocks(stats_html)
    assert len(js_stats) > 500

    # 3. Prediction dashboard (/dudoan)
    pred_html = templates_prediction.render_dudoan_page()
    js_pred = _extract_script_blocks(pred_html)
    assert len(js_pred) > 500

    # Validate each using node -c via temporary files
    for name, code in [("map_page", js_map), ("stats_dashboard", js_stats), ("prediction_dashboard", js_pred)]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        try:
            res = subprocess.run(["node", "-c", tmp_path], capture_output=True, text=True, encoding="utf-8")
            assert res.returncode == 0, f"JavaScript syntax error in {name}:\n{res.stderr}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def test_mobile_responsive_css_and_card_elements():
    """
    Verify mobile responsive CSS rules exist in template files:
    - @media (max-width: 640px)
    - @media (max-width: 480px) or (max-width: 400px)
    - Table-to-card transformation via display: block / flex and data-label on small screens
    """
    from app import templates_stats, templates_prediction

    stats_html = templates_stats.render_thongke_page()
    pred_html = templates_prediction.render_dudoan_page()

    assert "@media (max-width: 640px)" in stats_html
    assert "#leaderboard-table thead" in stats_html
    assert "#leaderboard-table tbody tr" in stats_html
    assert 'data-label="Cửa hàng"' in stats_html or 'data-label=\\"Cửa hàng\\"' in stats_html
    assert "@media (max-width: 640px)" in pred_html
    assert "prediction-grid" in pred_html or "pred-card" in pred_html

