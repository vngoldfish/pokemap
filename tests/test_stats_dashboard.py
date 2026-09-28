"""
Tests for Admin & Analytics Dashboard (/thongke, /admin, /quanly)
Validates endpoints:
- GET /thongke, /admin, /quanly, /stats
- GET /api/stats/overview
- GET /api/stats/leaderboard
- GET /api/stats/history_logs
- GET /api/stats/export_csv
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
from app.templates_stats import render_thongke_page


@pytest.fixture
def client():
    return TestClient(app)


def test_stats_html_pages_return_200(client):
    """Verify all admin & stats routes return 200 HTML."""
    for path in ["/thongke", "/admin", "/quanly", "/stats"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Quản Lý &amp; Thống Kê" in res.text or "Quản Lý & Thống Kê" in res.text
        assert "kpi-grid" in res.text
        assert "stats-nav-tabs" in res.text


def test_stats_overview_api(client):
    """Verify /api/stats/overview returns complete KPIs and breakdowns."""
    res = client.get("/api/stats/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_stores" in data
    assert "total_reports" in data
    assert "active_stores" in data
    assert "in_stock_now" in data
    assert "by_pref" in data
    assert "by_chain" in data
    assert "by_hour" in data
    assert "top_packs" in data
    assert data["total_stores"] > 10000
    assert data["total_reports"] > 10000
    assert isinstance(data["by_pref"], list)
    assert isinstance(data["by_hour"], list)


def test_stats_leaderboard_api(client):
    """Verify /api/stats/leaderboard returns ranked stores ordered by total_reports."""
    res = client.get("/api/stats/leaderboard?limit=20")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) > 0
    first = items[0]
    assert "id" in first
    assert "name" in first
    assert "total_reports" in first
    assert "in_rate" in first
    # Verify ordered descending
    for i in range(len(items) - 1):
        assert items[i]["total_reports"] >= items[i + 1]["total_reports"]


def test_stats_history_logs_api(client):
    """Verify /api/stats/history_logs supports pagination and filtering."""
    res = client.get("/api/stats/history_logs?page=1&limit=15")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert "total_pages" in data
    assert "items" in data
    assert data["page"] == 1
    assert data["limit"] == 15
    assert len(data["items"]) <= 15
    if data["items"]:
        item = data["items"][0]
        assert "store_id" in item
        assert "status_code" in item
        assert "formatted_time" in item


def test_stats_export_csv_api(client):
    """Verify /api/stats/export_csv returns valid CSV file."""
    res = client.get("/api/stats/export_csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "attachment" in res.headers.get("content-disposition", "")
    content = res.text
    assert "Store ID" in content
    assert "Tên cửa hàng" in content
    assert len(content.splitlines()) > 5


def test_stats_javascript_syntax_node():
    """Verify JavaScript inside render_thongke_page passes node -c syntax validation."""
    html = render_thongke_page()
    start_tag = "<script>"
    end_tag = "</script>"
    start_idx = html.find(start_tag)
    end_idx = html.find(end_tag)
    assert start_idx != -1 and end_idx != -1
    js_code = html[start_idx + len(start_tag):end_idx]

    proc = subprocess.run(["node", "-c"], input=js_code, text=True, capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, f"Node syntax error in stats dashboard JS: {proc.stderr}"
