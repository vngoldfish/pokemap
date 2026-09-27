# Handoff Report: Milestone 4 (Frontend Map & List UI, JavaScript Syntax, Filters & Toast Notifications)

**Author**: Worker M4 (Frontend UI Worker)  
**Date**: 2026-09-27  
**Working Directory**: `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m4`  
**Modified Files**:
- `app/templates.py`
- `tests/test_frontend_templates.py` (New Test Suite)

---

## 1. Observation

1. **Missing Functions in Settings Modal Interaction (`SHARED_MODALS_HTML`)**:
   - In `app/templates.py`:
     - Line 870: `<input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)">`
     - Lines 879, 883, 887, 891: `<input type="radio" name="set-region-radio" value="..." onchange="selectRegion(...)">`
     - Line 899: `<button type="button" onclick="refreshData(); closeSettingsModal();" ...>`
   - Prior to our fix, neither `updateSettings`, `selectRegion`, nor `refreshData` existed in `app/templates.py`. Interacting with any of these elements triggered `Uncaught ReferenceError: <fn> is not defined`.
   - In addition, `#set-sound-check` initialization in `openSettingsModal()` checked `configData.notifications.soundEnabled`, but `/api/config` delivers flattened `configData.soundEnabled`, leaving the checkbox unsynced unless mapped.

2. **Counter Pill Quick Filter Mismatch (`render_map_page`)**:
   - In `app/templates.py`:
     - Line 2053 was: `html += `<span class="stat-sep">•</span><span class="stat-seg stat-not" onclick="quickFilterMapStatus('not')" title="Lọc: Không bán thẻ">🟡 <b>${notCount}</b> ko bán</span>`;`
     - Line 2056 was: `html += `<span class="stat-sep">•</span><span class="stat-seg stat-unk" onclick="quickFilterMapStatus('all')" title="Lọc: Chưa rõ">⚪ <b>${unkCount}</b> chưa tin</span>`;`
   - However, `renderMapMarkers()` checks `mapStatusFilter === 'n'` (not `'not'`). Thus, clicking the yellow pill failed to filter. Furthermore, clicking the unconfirmed pill reset `mapStatusFilter` to `'all'` instead of `'unknown'`.

3. **Map Viewport Desynchronization on Filter Modal Region Change**:
   - In `applyAndCloseMapFilterModal()`:
     ```javascript
     function applyAndCloseMapFilterModal() {
       mapRegionFilter = mapModalTempRegion;
       ...
       renderMapMarkers();
     }
     ```
   - When a user selected a different region (e.g. from Osaka to Tokyo), the markers were updated, but Leaflet map viewport remained in Osaka.

4. **Toast Notification 120-Second Display (`showNewReportToast` & `formatTimeAgoJp`)**:
   - In both `render_map_page()` and `render_thongbao_page()`:
     - `formatTimeAgoJp()` returned `'たった今'` only when `diffSec < 60`, and transitioned to `${Math.floor(diffSec / 60)}分前` for `diffSec >= 60`.
     - Consequently, fresh reports between 60s and 120s displayed `1分前` instead of `たった今`, violating Requirement R4.

5. **Risk of Stale Status Overwrite in Polling**:
   - In both map and thongbao poller loops (`pollDatabaseUpdates`):
     ```javascript
     } else if (st) {
       st.status = rep.status_code;
       st.last_timestamp = rep.timestamp;
       ...
     }
     ```
     An out-of-order or backfill report with an older timestamp could overwrite a fresher status on store `st`.

6. **Orphaned DOM References & Unused Variables**:
   - `header-loc-name` was queried in `selectCityArea()` in both `render_map_page()` and `render_thongbao_page()`, but the element was removed in the top bar redesign.
   - `map-chain-select` and `map-time-select` were queried in `updateMapFilterUI()`, but select dropdowns were replaced by the filter modal.
   - `header = render_shared_header()` was assigned at `render_map_page():1493` but never referenced.

---

## 2. Logic Chain

1. **Resolution of Missing Settings Functions**:
   - Implemented `updateSettings(key, val)`, `selectRegion(pref)`, and `refreshData()` in both `render_map_page()` and `render_thongbao_page()` script scopes.
   - `updateSettings(key, val)` writes both to local `configData` (setting both `configData[key]` and `configData.notifications[key]`), saves to `localStorage`, and asynchronously POSTs `{ notifications: { [key]: val } }` to `/api/settings`.
   - `selectRegion(pref)` updates `currentRegion`, saves to `localStorage`, POSTs to `/api/settings`, updates the map/list filter, pans/flies the Leaflet map to the selected region center via `REGIONS[pref].center`, refreshes markers/list, and closes the modal.
   - `refreshData()` triggers `initData()` if present.
   - In `openSettingsModal()`, `soundCheck.checked` falls back to `configData.soundEnabled` if `configData.notifications` is absent.

2. **Fix for Filter Pill Clicks**:
   - Replaced `quickFilterMapStatus('not')` with `quickFilterMapStatus('n')`.
   - Replaced `quickFilterMapStatus('all')` on the `stat-unk` element with `quickFilterMapStatus('unknown')`.
   - Now clicking the yellow pill activates `mapStatusFilter = 'n'`, matching `store.code === 'n'`; clicking the gray pill activates `mapStatusFilter = 'unknown'`, matching stores with no reports or `code === 'u'`.

3. **Leaflet Viewport Synchronization**:
   - In `applyAndCloseMapFilterModal()`, detected `const regionChanged = (mapModalTempRegion !== mapRegionFilter);`.
   - Added `if (regionChanged && REGIONS[mapRegionFilter]) { map.flyTo(REGIONS[mapRegionFilter].center, REGIONS[mapRegionFilter].zoom || 13, { duration: 1.0 }); }`.
   - When switching to Tokyo, Nagoya, or Osaka in the modal, the map smoothly pans to the region's geographical center.

4. **120-Second Toast Formatting**:
   - In `formatTimeAgoJp(timestamp)`: changed threshold from `diffSec < 60` to `diffSec <= 120`.
   - In `showNewReportToast(rep)`: calculated `repAgeSec = repTs > 0 ? (getServerNowSec() - repTs) : 0;` and explicitly set `timeAgo = (repTs > 0 && repAgeSec >= 0 && repAgeSec <= 120) ? 'たった今' : (repTs > 0 ? formatTimeAgoJp(repTs) : 'たった今');`.
   - Unit tests under Node verify timestamps from 0s to 120s render `'たった今'`, and 121s renders `'2分前'`.

5. **Stale Status Overwrite Protection**:
   - Enclosed store status update in `if (!st.last_timestamp || (rep.timestamp && rep.timestamp >= st.last_timestamp))` in both `render_map_page()` and `render_thongbao_page()`.
   - Out-of-order older reports received during polling are prevented from downgrading store status.

6. **Cleanup of Orphaned References**:
   - Removed orphaned `document.getElementById('header-loc-name')` lookups from `selectCityArea()` on both pages.
   - Removed orphaned `map-chain-select` and `map-time-select` lookups from `updateMapFilterUI()`.
   - Removed unused `header = render_shared_header()` in `render_map_page()`.

---

## 3. Caveats

- **External CDN Dependency**: Leaflet.js and Leaflet MarkerCluster CSS/JS are loaded via `unpkg.com` in real browsers. In environments without internet access, these external CDN resources cannot be loaded by the browser, though all HTML generation, Node.js syntax parsing (`node --check`), and unit tests execute completely offline.
- No other caveats; all changes are strictly bounded within `app/templates.py` and `tests/test_frontend_templates.py`.

---

## 4. Conclusion

Milestone 4 requirements are 100% completed:
- Zero syntax errors across all extracted inline scripts (`node --check`).
- Zero console ReferenceErrors when interacting with the Settings modal (`updateSettings`, `selectRegion`, `refreshData`).
- Counter pill filters properly match state filter handlers (`'n'` and `'unknown'`).
- Map viewport pans to the selected region on filter modal application.
- Toast notifications display `たった今` for all fresh reports within 120s.
- Polling is protected against stale status overwrite.
- Orphaned DOM lookups and unused variables are cleaned up.
- All 28 automated tests (11 new frontend tests + 17 existing daemon/db tests) pass cleanly.
- `python -m compileall app scripts tests` passes with zero errors.

---

## 5. Verification Method

### 1. Automated Test Suite (Pytest)
Execute all tests including the new frontend template test suite:
```powershell
python -m pytest tests/test_frontend_templates.py -v
python -m pytest -v
```
Expected result: `28 passed, 2 warnings in ~8s`.

### 2. Node.js Syntax & Execution Check
Verify syntax and execute the frontend functions directly under Node.js:
```powershell
python -c "
from app.templates import render_map_page, render_thongbao_page
import re, subprocess, tempfile, os

for name, html in [('map', render_map_page()), ('thongbao', render_thongbao_page())]:
    for i, s in enumerate(re.findall(r'<script>(.*?)</script>', html, re.DOTALL)):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(s)
            p = f.name
        try:
            res = subprocess.run(['node', '--check', p], capture_output=True, text=True)
            assert res.returncode == 0, res.stderr
            print(f'{name} script {i}: Syntax OK')
        finally:
            os.remove(p)
"
```
Expected result:
```
map script 0: Syntax OK
thongbao script 0: Syntax OK
```

### 3. Compilation Cleanliness
```powershell
python -m compileall app scripts tests
```
Expected result: Exit code 0, all files compiled cleanly.
