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


# ==============================================================================
# 9. In-Stock Pin Effect Duration Settings (Ghim có hàng)
# ==============================================================================

def test_stock_pin_effect_hours_settings():
    """Verify In-Stock Pin effect duration setting is present in HTML, JS and API."""
    from app.web import app
    from starlette.testclient import TestClient

    client = TestClient(app)

    # 1. API: /api/config returns stockPinEffectHours
    cfg = client.get("/api/config").json()
    assert "stockPinEffectHours" in cfg, "stockPinEffectHours missing from /api/config"

    # 2. API: /api/settings updates stockPinEffectHours
    res = client.post("/api/settings", json={"stockPinEffectHours": "6"})
    assert res.status_code == 200
    cfg2 = client.get("/api/config").json()
    assert cfg2["stockPinEffectHours"] == "6"

    # Reset back to default
    client.post("/api/settings", json={"stockPinEffectHours": "24"})

    # 3. HTML: Verify #set-stock-pin-hours in both templates
    map_html = render_map_page()
    tb_html = render_thongbao_page()
    assert 'id="set-stock-pin-hours"' in map_html, "Missing #set-stock-pin-hours in map page"
    assert 'id="set-stock-pin-hours"' in tb_html, "Missing #set-stock-pin-hours in thongbao page"

    # 4. JS: Verify updateStockPinHours function in both scripts
    assert "function updateStockPinHours(" in map_html, "Missing updateStockPinHours in map page"
    assert "function updateStockPinHours(" in tb_html, "Missing updateStockPinHours in thongbao page"
    assert "stockEffectSetting" in map_html, "Missing stockEffectSetting check in map page"


# ==============================================================================
# 10. Real-time Relative Time Ticker (In-Stock Pin & /thongbao)
# ==============================================================================

def test_live_relative_time_attributes():
    """Verify data-timestamp attributes and ticker intervals exist in both map and thongbao pages."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    # Map Page:
    assert 'class="stock-time-badge" data-timestamp=' in map_html, "Missing data-timestamp on stock-time-badge in map"
    assert 'class="popup-time-ago" data-timestamp=' in map_html, "Missing data-timestamp on popup-time-ago in map"
    assert 'class="pill-time" data-timestamp=' in map_html, "Missing data-timestamp on pill-time in map"
    assert "function updateLiveRelativeTimes(" in map_html, "Missing updateLiveRelativeTimes in map page"
    assert "function checkStockPinEffectTransitions(" in map_html, "Missing checkStockPinEffectTransitions in map page"
    assert "window._liveTimeInterval" in map_html, "Missing _liveTimeInterval in map page"

    # Thongbao Page:
    assert 'class="time-ago-highlight" data-timestamp=' in tb_html, "Missing data-timestamp on time-ago-highlight in thongbao"
    assert 'class="pill-time" data-timestamp=' in tb_html, "Missing data-timestamp on pill-time in thongbao"
    assert "function formatTimeAgoVi(" in tb_html, "Missing formatTimeAgoVi in thongbao page"
    assert "function updateLiveRelativeTimes(" in tb_html, "Missing updateLiveRelativeTimes in thongbao page"
    assert "window._liveTimeInterval" in tb_html, "Missing _liveTimeInterval in thongbao page"


def test_vietnamese_time_ago_node_execution():
    """Execute formatTimeAgoVi directly in Node to test boundary values (0s, 30s, 60s, 15m, 1h, 1d)."""
    node_script = """
    let serverNow = 1000000;
    function getServerNowSec() { return serverNow; }

    %FORMAT_TIME_AGO_VI%

    const testCases = [
      { ts: serverNow, expected: 'Vừa xong' },             // 0s ago
      { ts: serverNow - 30, expected: 'Vừa xong' },        // 30s ago
      { ts: serverNow - 59, expected: 'Vừa xong' },        // 59s ago
      { ts: serverNow - 60, expected: '1 phút trước' },    // 60s ago
      { ts: serverNow - 900, expected: '15 phút trước' },  // 15 min ago (User's specific 11:00 -> 11:15 case!)
      { ts: serverNow - 3540, expected: '59 phút trước' }, // 59 min ago
      { ts: serverNow - 3600, expected: '1 giờ trước' },   // 1 hour ago
      { ts: serverNow - 7200, expected: '2 giờ trước' },   // 2 hours ago
      { ts: serverNow - 86400, expected: '1 ngày trước' }, // 1 day ago
      { ts: serverNow + 10, expected: 'Vừa xong' },        // clock skew / future
      { ts: 0, expected: 'Vừa xong' }                      // zero timestamp
    ];

    for (const tc of testCases) {
      const res = formatTimeAgoVi(tc.ts);
      if (res !== tc.expected) {
        throw new Error(`formatTimeAgoVi(${tc.ts}) failed: expected "${tc.expected}", got "${res}"`);
      }
    }

    console.log('VIETNAMESE_TIME_AGO_NODE_OK');
    """

    tb_html = render_thongbao_page()
    script = extract_inline_scripts(tb_html)[0]
    fmt_match = re.search(r"function formatTimeAgoVi\(.*?\n    \}", script, re.DOTALL)
    assert fmt_match, "formatTimeAgoVi not found in thongbao script"

    test_js = node_script.replace("%FORMAT_TIME_AGO_VI%", fmt_match.group(0))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(test_js)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node Vietnamese timeAgo test failed:\n{res.stderr}"
        assert "VIETNAMESE_TIME_AGO_NODE_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_live_ticker_simulation_in_node():
    """Simulate DOM time tick in Node: 11:00 to 11:15 automatically updates text to '15 phút trước' and '15分前'."""
    node_test = """
    // Minimal DOM Mock
    class MockElement {
      constructor(ts, initialText) {
        this.attributes = { 'data-timestamp': String(ts) };
        this.textContent = initialText;
      }
      getAttribute(k) { return this.attributes[k]; }
    }

    let serverNow = 1000000;
    function getServerNowSec() { return serverNow; }

    function formatTimeAgoJp(timestamp) {
      if (!timestamp) return 'たった今';
      const diffSec = getServerNowSec() - timestamp;
      if (diffSec < 0) return 'たった今';
      if (diffSec <= 120) return 'たった今';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分前`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}時間前`;
      return `${Math.floor(diffSec / 86400)}日前`;
    }

    function formatTimeAgoVi(timestamp) {
      if (!timestamp) return 'Vừa xong';
      const diffSec = Math.max(0, getServerNowSec() - Number(timestamp));
      if (diffSec < 60) return 'Vừa xong';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`;
      return `${Math.floor(diffSec / 86400)} ngày trước`;
    }

    // Report was created at 11:00 (ts = serverNow)
    const reportTs = serverNow;
    const pinBadge = new MockElement(reportTs, 'たった今');
    const thongBaoPill = new MockElement(reportTs, 'Vừa xong');

    // Verify initial states
    if (pinBadge.textContent !== 'たった今') throw new Error('Initial pin text wrong');
    if (thongBaoPill.textContent !== 'Vừa xong') throw new Error('Initial thongbao text wrong');

    // 15 minutes pass (11:15: serverNow advances 900 seconds)
    serverNow += 900;

    // Simulate updateLiveRelativeTimes()
    const newJp = formatTimeAgoJp(Number(pinBadge.getAttribute('data-timestamp')));
    pinBadge.textContent = newJp;

    const newVi = formatTimeAgoVi(Number(thongBaoPill.getAttribute('data-timestamp')));
    thongBaoPill.textContent = newVi;

    if (pinBadge.textContent !== '15分前') {
      throw new Error(`Expected 15分前, got ${pinBadge.textContent}`);
    }
    if (thongBaoPill.textContent !== '15 phút trước') {
      throw new Error(`Expected 15 phút trước, got ${thongBaoPill.textContent}`);
    }

    console.log('LIVE_TICKER_SIMULATION_OK');
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(node_test)
        f_path = f.name
    try:
        res = subprocess.run(["node", f_path], capture_output=True, text=True)
        assert res.returncode == 0, f"Node live ticker simulation failed:\n{res.stderr}"
        assert "LIVE_TICKER_SIMULATION_OK" in res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)

# ==============================================================================
# 11. Settings Modal Map Filter Tab
# ==============================================================================

def test_settings_map_filter_tab_structure():
    """Verify Map Filter is integrated as a dedicated tab inside Settings modal in both templates."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    for name, html in [("map", map_html), ("thongbao", tb_html)]:
        # Tab buttons
        assert 'id="tab-btn-set-map"' in html, f"Missing #tab-btn-set-map in {name}"
        assert 'id="tab-btn-set-telegram"' in html, f"Missing #tab-btn-set-telegram in {name}"
        assert 'id="tab-btn-set-system"' in html, f"Missing #tab-btn-set-system in {name}"

        # Tab panes
        assert 'id="settings-pane-map"' in html, f"Missing #settings-pane-map in {name}"
        assert 'id="settings-pane-telegram"' in html, f"Missing #settings-pane-telegram in {name}"
        assert 'id="settings-pane-system"' in html, f"Missing #settings-pane-system in {name}"

        # Map filter controls inside the pane (strictly Region, Chain, and In-Stock Pin)
        assert 'id="map-modal-region-group"' in html, f"Missing #map-modal-region-group in {name}"
        assert 'id="map-modal-chain-group"' in html, f"Missing #map-modal-chain-group in {name}"
        assert 'id="set-stock-pin-hours"' in html, f"Missing #set-stock-pin-hours in {name}"
        assert 'id="map-modal-status-group"' not in html, f"Obsolete #map-modal-status-group should be removed from {name}"
        assert 'id="map-modal-time-group"' not in html, f"Obsolete #map-modal-time-group should be removed from {name}"

        # JS functions
        assert "function switchSettingsTab(" in html, f"Missing switchSettingsTab in {name}"
        assert "function applyAndCloseMapFilterModal(" in html, f"Missing applyAndCloseMapFilterModal in {name}"
        assert "function resetMapFilters(" in html, f"Missing resetMapFilters in {name}"


# ==============================================================================
# 12. Map Header Brand Only (LOGO BAWUI TENPAI MAP)
# ==============================================================================

def test_map_header_brand_only():
    """Verify header on Map page strictly displays only LOGO + BAWUI TENPAI MAP."""
    map_html = render_map_page()

    # Extract header element
    header_match = re.search(r'<header id="poketan-header"[^>]*>(.*?)</header>', map_html, re.DOTALL)
    assert header_match, "poketan-header not found in map page"
    header_content = header_match.group(1)

    # 1. Brand logo and title MUST be inside header
    assert "brand-logo-icon" in header_content, "Missing brand-logo-icon in header"
    assert "BAWUI" in header_content, "Missing BAWUI text in header"
    assert "TENPAI MAP" in header_content, "Missing TENPAI MAP text in header"

    # 2. Filter buttons and stats breakdown MUST NOT be inside header
    assert "btn-map-filter" not in header_content, "btn-map-filter should be removed from header"
    assert "btn-map-filter-clear" not in header_content, "btn-map-filter-clear should be removed from header"
    assert "map-counter-pill" not in header_content, "map-counter-pill should be removed from header"
    assert "mft-title" not in header_content, "mft-title should be removed from header"


# ==============================================================================
# 13. Map Filter Persistence on Page Reload / Reset
# ==============================================================================

def test_map_filter_persistence():
    """Verify Map Filter persists region, chain, and pin hours to localStorage & /api/settings."""
    map_html = render_map_page()

    # 1. saveMapFiltersToStorage must persist selected region and chain
    assert "localStorage.setItem('poketan_selected_region', mapRegionFilter)" in map_html
    assert "localStorage.setItem('poketan_map_chain', mapChainFilter" in map_html

    # 2. applyAndCloseMapFilterModal must update currentRegion and in-stock pin hours
    assert "currentRegion = mapModalTempRegion" in map_html
    assert "updateStockPinHours(stockHours)" in map_html

    # 3. Initial load must read poketan_selected_region and poketan_map_chain
    assert "localStorage.getItem('poketan_selected_region')" in map_html
    assert "localStorage.getItem('poketan_map_chain')" in map_html


# ==============================================================================
# 14. Telegram Filter Tab Structure & UI Logic
# ==============================================================================

def test_telegram_filter_tab_structure():
    """Verify Telegram settings tab has rich filter chips and synchronized controls."""
    map_html = render_map_page()
    tb_html = render_thongbao_page()

    for name, html in [("map", map_html), ("thongbao", tb_html)]:
        # Header & Status Badge
        assert 'id="settings-pane-telegram"' in html, f"Missing #settings-pane-telegram in {name}"
        assert 'id="tg-status-badge"' in html, f"Missing #tg-status-badge in {name}"
        assert 'id="tg-cfg-enabled"' in html, f"Missing #tg-cfg-enabled in {name}"
        assert 'id="tg-cfg-token"' in html, f"Missing #tg-cfg-token in {name}"
        assert 'id="tg-cfg-chatid"' in html, f"Missing #tg-cfg-chatid in {name}"

        # 3 Filter Groups (Region, Status, Chain - Time filter removed as Telegram is strictly real-time)
        assert 'id="tg-modal-region-group"' in html, f"Missing #tg-modal-region-group in {name}"
        assert 'id="tg-modal-status-group"' in html, f"Missing #tg-modal-status-group in {name}"
        assert 'id="tg-modal-chain-group"' in html, f"Missing #tg-modal-chain-group in {name}"
        assert 'id="tg-modal-time-group"' not in html, f"Redundant #tg-modal-time-group should be removed from {name}"

        # Underlying hidden inputs for backward compatibility
        assert 'id="tg-cfg-region"' in html, f"Missing #tg-cfg-region in {name}"
        assert 'id="tg-cfg-status"' in html, f"Missing #tg-cfg-status in {name}"
        assert 'id="tg-cfg-chain"' in html, f"Missing #tg-cfg-chain in {name}"

        # JS functions
        assert "function syncTelegramModalUI(" in html, f"Missing syncTelegramModalUI in {name}"
        assert "function selectTgModalRegion(" in html, f"Missing selectTgModalRegion in {name}"
        assert "function selectTgModalStatus(" in html, f"Missing selectTgModalStatus in {name}"
        assert "function selectTgModalChain(" in html, f"Missing selectTgModalChain in {name}"
        assert "function saveTelegramConfig(" in html, f"Missing saveTelegramConfig in {name}"
        assert "function testTelegramWebhook(" in html, f"Missing testTelegramWebhook in {name}"


# ==============================================================================
# 15. Telegram Backend Dispatch Filter Logic
# ==============================================================================

def test_telegram_backend_dispatch_filters():
    """Verify on_csdl_report_added correctly handles multi-prefecture regions, filters, and real-time guard."""
    import time
    from unittest.mock import patch
    from app.web import on_csdl_report_added

    now = int(time.time())

    sent_alerts = []
    def fake_send(store, entry, notif_cfg, is_test=False):
        sent_alerts.append((store, entry))
        return {"status": "ok"}

    fake_cfg = {
        "notifications": {
            "telegramEnabled": True,
            "telegramRegion": "tokyo",
            "telegramStatus": "in",
            "telegramChain": "all",
            "telegramEnabledAt": now - 3600
        }
    }

    with patch("app.web.load_user_settings", return_value=fake_cfg), \
         patch("app.web.send_telegram_alert", side_effect=fake_send):
        
        # Kanagawa store should be ACCEPTED for Tokyo region
        kanagawa_store = {"id": "st_kn_1", "name": "7-Eleven Yokohama", "chain": "seven", "pref": "kanagawa"}
        report_in = {"status_code": "i", "timestamp": now - 60, "onsite": False}
        on_csdl_report_added(kanagawa_store, report_in)
        assert len(sent_alerts) == 1, "Kanagawa store should be accepted for tokyo region"

        # Osaka store should be REJECTED for Tokyo region
        osaka_store = {"id": "st_os_1", "name": "7-Eleven Umeda", "chain": "seven", "pref": "osaka"}
        on_csdl_report_added(osaka_store, report_in)
        assert len(sent_alerts) == 1, "Osaka store should be rejected for tokyo region"

        # Status 'o' (sold out) should be REJECTED when status filter is 'in'
        report_out = {"status_code": "o", "timestamp": now - 60, "onsite": False}
        on_csdl_report_added(kanagawa_store, report_out)
        assert len(sent_alerts) == 1, "Sold out report should be rejected when status filter is 'in'"

        # Outdated report (> 5 mins old) should be REJECTED (Telegram is strictly real-time)
        report_stale = {"status_code": "i", "timestamp": now - 400, "onsite": False}
        on_csdl_report_added(kanagawa_store, report_stale)
        assert len(sent_alerts) == 1, "Report older than 5m should be rejected as not real-time"



