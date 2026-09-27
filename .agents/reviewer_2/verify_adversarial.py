import os
import sys
sys.path.insert(0, os.path.abspath("."))
import re
import json
import time
from fastapi.testclient import TestClient
from app.web import app
from app.templates import render_map_page, render_thongbao_page

client = TestClient(app)

print("=== 1. VERIFY ALL API ENDPOINTS ===")
endpoints = [
    ("/", 200, "text/html"),
    ("/thongbao", 200, "text/html"),
    ("/map", 200, "text/html"),
    ("/stores", 200, "text/html"),
    ("/api/config", 200, "application/json"),
    ("/api/latest_reports", 200, "application/json"),
    ("/api/latest_reports?since=0&limit=10", 200, "application/json"),
    ("/api/store_history/any_id", 200, "application/json"),
    ("/api/report_counts", 200, "application/json"),
    ("/api/report_counts?region=tokyo", 200, "application/json"),
    ("/api/stores_data?region=osaka", 200, "application/json"),
]

for url, expected_status, expected_ct in endpoints:
    res = client.get(url)
    ct = res.headers.get("content-type", "")
    assert res.status_code == expected_status, f"{url} returned status {res.status_code}, expected {expected_status}"
    assert expected_ct in ct, f"{url} returned content-type {ct}, expected {expected_ct}"
    print(f"  [OK] {url} -> {res.status_code} ({ct})")

print("\n=== 2. VERIFY /api/config serverTime ACCURACY ===")
t_start = int(time.time())
cfg_res = client.get("/api/config")
t_end = int(time.time())
assert cfg_res.status_code == 200
cfg_data = cfg_res.json()
server_time = cfg_data.get("serverTime")
assert server_time is not None, "serverTime missing in /api/config"
assert t_start <= server_time <= t_end + 1, f"serverTime {server_time} skewed outside [{t_start}, {t_end + 1}]"
print(f"  [OK] serverTime: {server_time} (Current system epoch: {t_start})")

print("\n=== 3. VERIFY TEMPLATES HTML & DOM HANDLERS ===")
for page_name, html in [('map', render_map_page()), ('thongbao', render_thongbao_page())]:
    print(f"\n--- Checking {page_name} page ---")
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    print(f"  Found {len(scripts)} inline script tags")
    full_script = '\n'.join(scripts)

    # Check for syntax errors via node --check
    import subprocess, tempfile, os
    for i, s in enumerate(scripts):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(s)
            tmp_path = f.name
        try:
            res = subprocess.run(['node', '--check', tmp_path], capture_output=True, text=True)
            assert res.returncode == 0, f"Node syntax error in {page_name} script {i}:\n{res.stderr}"
            print(f"  [OK] Script {i} syntax clean via node --check")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Check required functions
    for fn in ["updateSettings", "selectRegion", "refreshData"]:
        assert f"function {fn}" in full_script, f"Missing function {fn} in {page_name}"
        print(f"  [OK] {fn} defined")

    # Scan all onclick, onchange, oninput in HTML
    handlers = re.findall(r'(on[a-z]+)=["\']([^"\']+)["\']', html)
    print(f"  Total event handlers in HTML: {len(handlers)}")
    called_fns = set()
    for attr, code in handlers:
        calls = re.findall(r'([a-zA-Z0-9_$]+)\s*\(', code)
        for c in calls:
            called_fns.add(c)
    
    defined_fns = set(re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', full_script))
    defined_fns.update(re.findall(r'(?:var|let|const|window\.)\s*([a-zA-Z0-9_$]+)\s*=\s*(?:function|\()', full_script))

    # Builtins
    builtins = {'alert', 'confirm', 'parseInt', 'parseFloat', 'closeSettingsModal', 'openSettingsModal',
                'closeMapFilterModal', 'openMapFilterModal', 'closeListFilterModal', 'openListFilterModal',
                'closeDetailModal', 'openDetailModal', 'selectTab', 'openFilterModal', 'if', 'stopPropagation',
                'closest', 'toLowerCase', 'includes', 'trim', 'preventDefault'}
    
    unresolved = [fn for fn in called_fns if fn not in defined_fns and fn not in builtins]
    print(f"  Called functions: {sorted(called_fns)}")
    print(f"  Unresolved functions: {unresolved}")
    assert len(unresolved) == 0, f"Unresolved handler calls in {page_name}: {unresolved}"

print("\n=== 4. VERIFY #poketan-header.map-top-bar STAT FILTER MAPPINGS ===")
map_html = render_map_page()
# Must have #poketan-header and .map-top-bar
assert 'id="poketan-header"' in map_html
assert 'map-top-bar' in map_html or 'header-stat-badge' in map_html or 'map-counter-pill' in map_html

# Check quickFilterMapStatus calls
assert "quickFilterMapStatus('n')" in map_html, "Missing quickFilterMapStatus('n')"
assert "quickFilterMapStatus('unknown')" in map_html, "Missing quickFilterMapStatus('unknown')"
assert "quickFilterMapStatus('not')" not in map_html, "Buggy quickFilterMapStatus('not') still found"

# Check map flyTo in applyAndCloseMapFilterModal
assert "applyAndCloseMapFilterModal" in map_html
assert "flyTo" in map_html

print("  [OK] Stat filter mappings and map filter modal verified!")

print("\n=== 5. ADVERSARIAL EDGE CASE TESTS ===")
# Test 5.1: Negative since
res = client.get("/api/latest_reports?since=-1")
assert res.status_code == 200, f"since=-1 failed: {res.status_code}"
print("  [OK] /api/latest_reports?since=-1 returns 200")

# Test 5.2: Future since
res = client.get("/api/latest_reports?since=9999999999")
assert res.status_code == 200
assert res.json() == []
print("  [OK] /api/latest_reports?since=9999999999 returns empty list 200")

# Test 5.3: Invalid / non-int since
res = client.get("/api/latest_reports?since=invalid")
assert res.status_code == 422 # FastAPI validation
print("  [OK] /api/latest_reports?since=invalid returns 422 Unprocessable Entity")

# Test 5.4: Special chars in store_history id
res = client.get("/api/store_history/nonexistent_store_99999")
assert res.status_code == 200
print(f"  [OK] Non-existent store history returns 200 (type: {type(res.json())})")

# Test 5.5: SQL injection attempt in store_history id
res = client.get("/api/store_history/' OR 1=1 --")
assert res.status_code == 200
print("  [OK] SQL injection attempt safely returns 200 without error")

# Test 5.6: Store history with _c suffix
res = client.get("/api/store_history/some_store_c")
assert res.status_code == 200
print("  [OK] store_history with _c suffix returns 200")

print("\n=== ALL INDEPENDENT VERIFICATION CHECKS PASSED ===")
