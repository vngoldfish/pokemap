"""
Tests for Milestone 4 (Frontend Map & List UI):
- HTML structure validity for render_map_page() and render_thongbao_page()
- JavaScript syntax validation via `node --check`
- JavaScript execution tests for updateSettings, selectRegion, refreshData
- Header stats / #map-counter-pill filter clicks ('n', 'unknown')
- Map Filter Modal region viewport synchronization (flyTo)
- Toast notification 120s 'たった今' formatting and logic
- Stale status overwrite guard in latest_reports poll
- Cleanup of orphaned DOM elements (header-loc-name, map-chain-select, map-time-select)
- HTTP 200 checks for / and /thongbao endpoints
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.web import app
from app.templates import render_map_page, render_thongbao_page, SHARED_MODALS_HTML


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def extract_inline_scripts(html: str):
    """Extract all inline script content from an HTML string."""
    return re.findall(r"<script>(.*?)</script>", html, re.DOTALL)


# ==============================================================================
# 1. HTML Generation & Endpoint Status Tests
# ==============================================================================

def test_render_map_page_html_validity(client):
    """Verify render_map_page() returns valid HTML with expected structural elements."""
    html = render_map_page()
    assert isinstance(html, str)
    assert len(html) > 5000
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "<head>" in html
    assert "<body>" in html
    assert "</html>" in html
    assert 'id="map"' in html
    assert 'id="poketan-header"' in html
    assert 'id="map-counter-pill"' in html
    assert 'id="settings-modal"' in html

    # Verify HTTP endpoint returns 200
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "ポケ探" in res.text


def test_render_thongbao_page_html_validity(client):
    """Verify render_thongbao_page() returns valid HTML with expected structural elements."""
    html = render_thongbao_page()
    assert isinstance(html, str)
    assert len(html) > 5000
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "<head>" in html
    assert "<body>" in html
    assert "</html>" in html
    assert 'id="store-cards-list"' in html
    assert 'id="settings-modal"' in html

    # Verify HTTP endpoint returns 200
    res = client.get("/thongbao")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "ポケ探" in res.text


# ==============================================================================
# 2. Node.js JavaScript Syntax Validation (node --check)
# ==============================================================================

def test_javascript_syntax_node_check():
    """Extract inline scripts from both pages and verify zero syntax errors via node --check."""
    for page_name, html in [("map_page", render_map_page()), ("thongbao_page", render_thongbao_page())]:
        scripts = extract_inline_scripts(html)
        assert len(scripts) >= 1, f"Expected at least 1 inline script in {page_name}"
        for idx, script in enumerate(scripts):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(script)
                f_path = f.name
            try:
                res = subprocess.run(["node", "--check", f_path], capture_output=True, text=True)
                assert res.returncode == 0, f"Node syntax error in {page_name} script {idx}:\n{res.stderr}"
            finally:
                if os.path.exists(f_path):
                    os.remove(f_path)


# ==============================================================================
# 3. Settings Modal Functions Presence & Node Execution
# ==============================================================================

def test_settings_functions_presence_in_templates():
    """Verify updateSettings, selectRegion, and refreshData exist in both templates."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    for name, html in [("map", map_html), ("thongbao", tb_html)]:
        assert "function updateSettings(" in html, f"Missing updateSettings in {name} page"
        assert "function selectRegion(" in html, f"Missing selectRegion in {name} page"
        assert "function refreshData(" in html, f"Missing refreshData in {name} page"


def test_settings_functions_node_runtime_execution():
    """Execute updateSettings, selectRegion, refreshData under Node with mock DOM/globals to verify no ReferenceErrors."""
    node_test_runner = """
    // Mock minimal browser environment
    global.window = global;
    global.document = {
      getElementById: (id) => ({
        classList: { add: () => {}, remove: () => {}, toggle: () => {} },
        style: {},
        value: '',
        checked: false
      }),
      querySelectorAll: (sel) => [],
      querySelector: (sel) => ({ checked: false }),
      addEventListener: () => {}
    };
    global.localStorage = {
      _data: {},
      getItem(k) { return this._data[k] || null; },
      setItem(k, v) { this._data[k] = String(v); }
    };
    global.fetch = async (url, opts) => ({
      json: async () => ({ status: 'ok' })
    });
    global.map = {
      flyTo: (center, zoom, opts) => { global.__lastFlyTo = { center, zoom }; }
    };
    global.REGIONS = {
      'osaka': { center: [34.69, 135.50], zoom: 13 },
      'tokyo': { center: [35.44, 139.63], zoom: 13 },
      'nagoya': { center: [35.18, 136.90], zoom: 13 },
      'all': { center: [34.69, 135.50], zoom: 10 }
    };
    global.configData = {};
    global.currentRegion = 'osaka';
    global.mapRegionFilter = 'osaka';
    global.listRegionFilter = 'osaka';
    global.listCurrentPage = 1;

    let initDataCalled = false;
    global.initData = () => { initDataCalled = true; };
    global.updateMapFilterUI = () => {};
    global.renderMapMarkers = () => {};
    global.updateListFilterBadgeUI = () => {};
    global.renderStoreList = () => {};
    global.closeSettingsModal = () => {};

    // Test map script implementations
    %MAP_SETTINGS_CODE%

    // 1. Test updateSettings
    updateSettings('soundEnabled', true);
    if (!configData.soundEnabled || !configData.notifications || !configData.notifications.soundEnabled) {
      throw new Error('updateSettings failed to set soundEnabled');
    }
    updateSettings('soundEnabled', false);
    if (configData.soundEnabled !== false) {
      throw new Error('updateSettings failed to toggle soundEnabled');
    }

    // 2. Test selectRegion
    selectRegion('tokyo');
    if (currentRegion !== 'tokyo') throw new Error('selectRegion failed to update currentRegion');
    if (mapRegionFilter !== 'tokyo') throw new Error('selectRegion failed to update mapRegionFilter');
    if (!global.__lastFlyTo || global.__lastFlyTo.center[0] !== 35.44) {
      throw new Error('selectRegion failed to flyTo tokyo center');
    }

    // 3. Test refreshData
    refreshData();
    if (!initDataCalled) throw new Error('refreshData failed to trigger initData');

    console.log('SETTINGS_FUNCTIONS_NODE_OK');
    """

    # Extract updateSettings, selectRegion, refreshData functions from map page script
    map_html = render_map_page()
    script = extract_inline_scripts(map_html)[0]

    # Extract helper code
    upd_match = re.search(r"function updateSettings\(.*?\n    \}", script, re.DOTALL)
    sel_match = re.search(r"function selectRegion\(.*?\n    \}", script, re.DOTALL)
    ref_match = re.search(r"function refreshData\(.*?\n    \}", script, re.DOTALL)

    assert upd_match, "updateSettings code block not found in map script"
    assert sel_match, "selectRegion code block not found in map script"
    assert ref_match, "refreshData code block not found in map script"

    combined_code = f"{upd_match.group(0)}\n{sel_match.group(0)}\n{ref_match.group(0)}"
    full_test_js = node_test_runner.replace("%MAP_SETTINGS_CODE%", combined_code)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(full_test_js)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node execution failed:\n{res.stderr}"
        assert "SETTINGS_FUNCTIONS_NODE_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


# ==============================================================================
# 4. #map-counter-pill Filter Clicks ('n' and 'unknown')
# ==============================================================================

def test_map_counter_pill_filter_clicks():
    """Verify #map-counter-pill uses 'n' and 'unknown' instead of 'not' and 'all'."""
    map_html = render_map_page()

    # Must contain correct status filter codes
    assert "onclick=\"quickFilterMapStatus('n')\"" in map_html, "Missing 'n' filter click for notCount"
    assert "onclick=\"quickFilterMapStatus('unknown')\"" in map_html, "Missing 'unknown' filter click for unkCount"

    # Must NOT contain the old buggy codes
    assert "onclick=\"quickFilterMapStatus('not')\"" not in map_html, "Stale 'not' filter click still present!"

    # Ensure stat-unk segment does not bind to 'all'
    stat_unk_match = re.search(r'class="stat-seg stat-unk"[^>]*onclick="([^"]+)"', map_html)
    assert stat_unk_match, "stat-unk segment not found"
    assert stat_unk_match.group(1) == "quickFilterMapStatus('unknown')", (
        f"stat-unk segment should bind to 'unknown', found {stat_unk_match.group(1)}"
    )


# ==============================================================================
# 5. Map Filter Modal Viewport Synchronization (flyTo)
# ==============================================================================

def test_map_filter_modal_viewport_synchronization():
    """Verify applyAndCloseMapFilterModal pans/flies Leaflet map when region changes."""
    map_html = render_map_page()
    script = extract_inline_scripts(map_html)[0]

    # Verify applyAndCloseMapFilterModal contains the flyTo logic
    apply_fn_match = re.search(r"function applyAndCloseMapFilterModal\(\)\s*\{(.*?)\}", script, re.DOTALL)
    assert apply_fn_match, "applyAndCloseMapFilterModal function not found"
    body = apply_fn_match.group(1)

    assert "regionChanged" in body, "regionChanged check missing in applyAndCloseMapFilterModal"
    assert "map.flyTo" in body, "map.flyTo call missing in applyAndCloseMapFilterModal"
    assert "REGIONS[mapRegionFilter]" in body, "REGIONS[mapRegionFilter] check missing"


# ==============================================================================
# 6. Toast Notification Formatting (<= 120s => たった今)
# ==============================================================================

def test_toast_time_formatting_code():
    """Verify toast formatting in both map and thongbao pages uses 'たった今' for reports <= 120s."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    for name, html in [("map", map_html), ("thongbao", tb_html)]:
        script = extract_inline_scripts(html)[0]

        # Check formatTimeAgoJp
        fmt_match = re.search(r"function formatTimeAgoJp\(.*?\)\s*\{(.*?)\}", script, re.DOTALL)
        assert fmt_match, f"formatTimeAgoJp not found in {name}"
        fmt_body = fmt_match.group(1)
        assert "diffSec <= 120" in fmt_body or "diffSec < 120" in fmt_body or "diffSec <= 120" in fmt_body, (
            f"formatTimeAgoJp in {name} does not gate <= 120s for たった今"
        )

        # Check showNewReportToast timeAgo assignment
        toast_match = re.search(r"function showNewReportToast\(.*?\)\s*\{(.*?)const toast = document\.createElement", script, re.DOTALL)
        assert toast_match, f"showNewReportToast not found in {name}"
        toast_body = toast_match.group(1)
        assert "<= 120" in toast_body, f"showNewReportToast in {name} does not check <= 120s"
        assert "'たった今'" in toast_body


def test_toast_formatting_node_execution():
    """Execute formatTimeAgoJp directly in Node to test boundary values (0s, 30s, 60s, 90s, 120s, 121s)."""
    node_script = """
    let serverNow = 1000000;
    function getServerNowSec() { return serverNow; }

    %FORMAT_TIME_AGO_JP%

    const testCases = [
      { ts: serverNow, expected: 'たった今' },              // 0s ago
      { ts: serverNow - 30, expected: 'たった今' },         // 30s ago
      { ts: serverNow - 60, expected: 'たった今' },         // 60s ago (must be たった今!)
      { ts: serverNow - 90, expected: 'たった今' },         // 90s ago (must be たった今!)
      { ts: serverNow - 120, expected: 'たった今' },        // 120s ago (must be たった今!)
      { ts: serverNow - 121, expected: '2分前' },           // 121s ago -> 2分前
      { ts: serverNow - 300, expected: '5分前' },           // 5 min ago
      { ts: serverNow + 10, expected: 'たった今' },         // future / clock skew -> たった今
      { ts: 0, expected: 'たった今' }                       // 0 timestamp -> たった今
    ];

    for (const tc of testCases) {
      const res = formatTimeAgoJp(tc.ts);
      if (res !== tc.expected) {
        throw new Error(`formatTimeAgoJp(${tc.ts}) failed: expected "${tc.expected}", got "${res}"`);
      }
    }

    console.log('TOAST_FORMATTING_NODE_OK');
    """

    map_html = render_map_page()
    script = extract_inline_scripts(map_html)[0]
    fmt_match = re.search(r"function formatTimeAgoJp\(.*?\n    \}", script, re.DOTALL)
    assert fmt_match, "formatTimeAgoJp not found in script"

    test_js = node_script.replace("%FORMAT_TIME_AGO_JP%", fmt_match.group(0))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(test_js)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node toast formatting test failed:\n{res.stderr}"
        assert "TOAST_FORMATTING_NODE_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


# ==============================================================================
# 7. Stale Status Overwrite Guard in latest_reports Poll
# ==============================================================================

def test_stale_status_overwrite_guard():
    """Verify latest_reports poller checks timestamp before overwriting store status."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    guard_pattern = r"!st\.last_timestamp\s*\|\|\s*\(rep\.timestamp\s*&&\s*rep\.timestamp\s*>=\s*st\.last_timestamp\)"

    for name, html in [("map", map_html), ("thongbao", tb_html)]:
        script = extract_inline_scripts(html)[0]
        assert re.search(guard_pattern, script), (
            f"Stale status overwrite guard missing in {name} latest_reports poller"
        )


# ==============================================================================
# 8. Orphaned DOM References Cleanup
# ==============================================================================

def test_orphaned_dom_references_cleanup():
    """Verify obsolete DOM lookups (header-loc-name, map-chain-select, map-time-select) are cleaned up."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    # header-loc-name should not be queried in either script
    assert "header-loc-name" not in map_html, "orphaned header-loc-name still queried in map page"
    assert "header-loc-name" not in tb_html, "orphaned header-loc-name still queried in thongbao page"

    # map-chain-select and map-time-select should not be queried in map updateMapFilterUI
    map_script = extract_inline_scripts(map_html)[0]
    assert "map-chain-select" not in map_script, "orphaned map-chain-select still queried in map script"
    assert "map-time-select" not in map_script, "orphaned map-time-select still queried in map script"
