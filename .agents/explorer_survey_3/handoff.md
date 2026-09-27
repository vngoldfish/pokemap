# Handoff Report: Requirement R4 (Frontend Map & List UI Review)

**Author**: Explorer Survey 3 (Frontend UI Explorer)  
**Date**: 2026-09-27  
**Scope**: Requirement R4 (`app/templates.py`, JavaScript console/syntax, header stats, filter button, toast notifications, Python compilation)

---

## 1. Observation

### Obs 1: Python Compilation Cleanliness
- Command: `python -m py_compile app/__init__.py app/calendar_tracker.py app/config.py app/db.py app/exporter.py app/fetcher.py app/main.py app/parser.py app/templates.py app/web.py scripts/harvest_all_history.py`
- Result: Exit code `0`, no compilation errors or critical syntax warnings across all 11 python files.

### Obs 2: JavaScript Syntax & Strict Mode Parsing
- Extracted inline JavaScript from `render_map_page()` (1,393 lines) and `render_thongbao_page()` (1,253 lines).
- Executed `node --check` and `node --check` with `'use strict';` prepended to both scripts.
- Result: Exit code `0` on both scripts. There are zero JavaScript parse/syntax errors and zero duplicate variable declarations in identical scope (e.g. no duplicate `const`/`let` in top-level scope).

### Obs 3: Missing JavaScript Functions Called in HTML (`SHARED_MODALS_HTML`)
In `app/templates.py` inside `SHARED_MODALS_HTML` (lines 850–905), the Settings modal contains inline event listeners calling three functions that are never defined in `app/templates.py`:
1. **`updateSettings('soundEnabled', this.checked)`** at line 870:
   ```html
   870: <input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)">
   ```
2. **`selectRegion('osaka')` / `'tokyo'` / `'nagoya'` / `'all'`** at lines 879, 883, 887, 891:
   ```html
   879: <input type="radio" name="set-region-radio" value="osaka" onchange="selectRegion('osaka')">
   883: <input type="radio" name="set-region-radio" value="tokyo" onchange="selectRegion('tokyo')">
   887: <input type="radio" name="set-region-radio" value="nagoya" onchange="selectRegion('nagoya')">
   891: <input type="radio" name="set-region-radio" value="all" onchange="selectRegion('all')">
   ```
3. **`refreshData()`** at line 899:
   ```html
   899: <button type="button" onclick="refreshData(); closeSettingsModal();" ...>
   ```
- **Runtime Error Observed via Playwright**:
  When a user opens the Settings modal (via footer "Cài đặt") and interacts with these controls:
  - Clicking `#set-sound-check`: `Uncaught ReferenceError: updateSettings is not defined`
  - Clicking radio button `set-region-radio`: `Uncaught ReferenceError: selectRegion is not defined`
  - Clicking "Cập nhật dữ liệu mới nhất": `Uncaught ReferenceError: refreshData is not defined`
  This affects both `/` (Map page) and `/thongbao` (Notifications page).

### Obs 4: Top Header `#poketan-header.map-top-bar` & Stats Display
- **Map page (`/`)**:
  - `#poketan-header.map-top-bar` exists at line 1639 of `app/templates.py`:
    ```html
    1639: <header id="poketan-header" class="map-top-bar">
    1640:   <div class="map-top-bar-inner">
    ...
    1657:     <div id="map-counter-pill" class="map-counter-pill-premium" title="Thống kê trạng thái cửa hàng">
    1658:       <span class="stat-seg stat-total"><b>...</b> quán</span>
    1659:     </div>
    ```
  - When stores are rendered, `renderMapMarkers()` updates `#map-counter-pill` (lines 2044–2060):
    ```javascript
    2046: let html = `<span class="stat-seg stat-total" onclick="quickFilterMapStatus('all')" title="Xem tất cả"><b>${visibleCount.toLocaleString()}</b> quán</span>`;
    2048: if (inStockVisibleCount > 0) {
    2049:   html += `<span class="stat-sep">•</span><span class="stat-seg stat-in" onclick="quickFilterMapStatus('in')" title="Lọc: Có hàng">🟢 <b>${inStockVisibleCount}</b> có</span>`;
    2050: }
    2051: if (outCount > 0) {
    2052:   html += `<span class="stat-sep">•</span><span class="stat-seg stat-out" onclick="quickFilterMapStatus('out')" title="Lọc: Hết hàng">🔴 <b>${outCount}</b> hết</span>`;
    2053: }
    2054: if (notCount > 0) {
    2055:   html += `<span class="stat-sep">•</span><span class="stat-seg stat-not" onclick="quickFilterMapStatus('not')" title="Lọc: Không bán thẻ">🟡 <b>${notCount}</b> ko bán</span>`;
    2056: }
    2057: if (unkCount > 0) {
    2058:   html += `<span class="stat-sep">•</span><span class="stat-seg stat-unk" onclick="quickFilterMapStatus('all')" title="Lọc: Chưa rõ">⚪ <b>${unkCount}</b> chưa tin</span>`;
    2059: }
    ```
  - **Bug in Pill Filter Click**:
    - Line 2054 sets `onclick="quickFilterMapStatus('not')"`. However, `renderMapMarkers()` (line 1992) checks `mapStatusFilter === 'n'`:
      ```javascript
      1992: } else if (mapStatusFilter === 'n') {
      1993:   if (info.code !== 'n') continue;
      ```
      Because `'not' !== 'n'`, clicking the yellow `🟡 ko bán` segment fails to filter stores and instead falls back to displaying all stores.
    - Line 2057 sets `onclick="quickFilterMapStatus('all')"` for `⚪ chưa tin`. Clicking `⚪ chưa tin` resets the filter to `'all'` instead of filtering to unknown stores (`quickFilterMapStatus('unknown')`).
- **Notifications page (`/thongbao`)**:
  - `render_shared_header()` at line 648 returns an empty string `""`:
    ```python
    648: def render_shared_header() -> str:
    649:     return ""
    ```
  - In `render_thongbao_page()` at line 3606, `header` (`""`) is interpolated. Therefore, `#poketan-header` does NOT exist in the DOM of `/thongbao`. `/thongbao` instead uses `.list-header-bar` (line 3609) and `#list-active-settings-banner` (line 3623).
  - In `render_map_page()` at line 1493, `header = render_shared_header()` is assigned but never used because `<header id="poketan-header" class="map-top-bar">` is hardcoded at line 1639.

### Obs 5: Map Filter Button (`Bộ lọc Bản đồ (地図フィルター)`) Functionality
- `#btn-map-filter` exists at line 1643 and triggers `openMapFilterModal()`.
- The modal `#map-filter-modal` contains 4 filter categories:
  - Region: Osaka, Tokyo, Nagoya, All (`#map-modal-region-group`)
  - Status: All, Có hàng (`in`), Không có (`out`), Không bán thẻ (`n`), Chưa có báo cáo (`unknown`), Tại quán (`onsite`), Tin gần đây (`recent`)
  - Chain: All, Conbini, 7-Eleven, Lawson, FamilyMart, Ministop, Specialty, Electronics
  - Time freshness: 1h, 3h, 6h, 12h, 24h, All
- Clicking "Áp dụng bộ lọc" calls `applyAndCloseMapFilterModal()` (line 2257):
  ```javascript
  2257: function applyAndCloseMapFilterModal() {
  2258:   mapRegionFilter = mapModalTempRegion;
  2259:   mapStatusFilter = mapModalTempStatus;
  2260:   mapChainFilter = mapModalTempChain;
  2261:   mapTimeFilter = mapModalTempTime;
  2262:   saveMapFiltersToStorage();
  2263:   closeMapFilterModal();
  2264:   updateMapFilterUI();
  2265:   renderMapMarkers();
  2266: }
  ```
- **Viewport Desynchronization Bug**:
  When a user switches regions in the modal (e.g. from Osaka to Tokyo) and applies, `mapRegionFilter` updates and `renderMapMarkers()` renders Tokyo markers, but the Leaflet map does NOT pan/fly to Tokyo's center (`REGIONS[mapModalTempRegion].center`). The viewport remains centered in Osaka while markers are in Tokyo.

### Obs 6: Toast Notification Logic & 120s / `たった今` Formatting
- **120-second Activation Threshold**:
  In both `render_map_page()` (lines 2959–2963) and `render_thongbao_page()` (lines 4834–4838):
  ```javascript
  2959: const toastKey = `${rep.store_id}_${rep.timestamp}_${rep.status_code}`;
  2960: const reportAgeSec = rep.timestamp > 0 ? (nowSec - rep.timestamp) : 0;
  2961: const isFreshRealtime = reportAgeSec >= 0 && reportAgeSec <= 120;
  2963: if (rep.status_code === 'i' && !seenToastKeys.has(toastKey) && isFreshRealtime) {
  2964:   seenToastKeys.add(toastKey);
  2965:   candidateStockReps.push(rep);
  2966: }
  ```
  Verified via Playwright:
  - Reports older than 120s (e.g. 200s ago) correctly produce **0 toasts**.
  - Reports <= 120s ago with `status_code === 'i'` trigger `showNewReportToast(rep)`.
- **Time Formatting Bug (`たった今`)**:
  In `showNewReportToast(rep)` (lines 2847 and 4734):
  ```javascript
  2847: const timeAgo = repTs > 0 ? formatTimeAgoJp(repTs) : 'たった今';
  ```
  And in `formatTimeAgoJp(timestamp)` (lines 2818–2825 and 4705–4712):
  ```javascript
  2818: function formatTimeAgoJp(timestamp) {
  2819:   if (!timestamp) return 'たった今';
  2820:   const diffSec = getServerNowSec() - timestamp;
  2821:   if (diffSec < 0) return 'たった今';
  2822:   if (diffSec < 60) return 'たった今';
  2823:   if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分前`;
  ```
  - When a report is 30s old: `diffSec < 60`, outputs `'たった今'`.
  - When a report is 90s old (which is <= 120s): `diffSec >= 60`, outputs `'1分前'`, NOT `'たった今'`.
  Requirement R4 specifies: *"Toast thông báo chỉ bật khi có báo cáo mới trong 120 giây và hiển thị `たった今`."*

### Obs 7: Obsolete / Missing Element IDs in DOM Lookups
Cross-referencing `document.getElementById` calls with DOM IDs revealed:
- `header-loc-name` (lines 2390 and 4259): `document.getElementById('header-loc-name')` returns `null` because the header location pill was removed in the top bar redesign. It is guarded by `if (headerLoc)` so it does not throw an uncaught error, but it is orphaned code.
- `map-chain-select` (line 2171) and `map-time-select` (line 2176): Select dropdowns were replaced by the filter modal; code is guarded by `if (selChain)` and `if (selTime)`.

---

## 2. Logic Chain

1. **Syntax vs Runtime Errors**:
   While static analysis (`node --check`) confirms that the JavaScript syntax is valid and there are no duplicate `const`/`let` bindings in identical scopes, runtime execution under Chromium revealed 3 critical missing global functions (`updateSettings`, `selectRegion`, `refreshData`). Because these functions are declared in HTML `onchange` and `onclick` attributes within `SHARED_MODALS_HTML`, any interaction with the Settings modal crashes with `ReferenceError`.
2. **Filter Matching Discrepancy**:
   The header counter pill renders `onclick="quickFilterMapStatus('not')"`. The state filter in `renderMapMarkers()` checks `mapStatusFilter === 'n'`. Because the values diverge (`'not'` vs `'n'`), the user's click fails to filter. Similarly, `⚪ chưa tin` binds to `'all'` instead of `'unknown'`.
3. **Region Viewport Synchronization**:
   Changing regions via `applyAndCloseMapFilterModal` modifies `mapRegionFilter` and calls `renderMapMarkers()`, but fails to reposition the map center. Because Japan spans over 1,000 km between Osaka and Tokyo, markers outside the current viewport are invisible until the user manually pans.
4. **Toast Time Formatting**:
   The 120-second gating logic (`reportAgeSec >= 0 && reportAgeSec <= 120`) correctly isolates fresh reports. However, the downstream formatter `formatTimeAgoJp` transitions to `${diff / 60}分前` at 60 seconds. A report between 61s and 120s displays `1分前` instead of `たった今`.

---

## 3. Caveats

- **Network Environment**: Leaflet and MarkerCluster scripts are loaded via `unpkg.com` CDN. In an offline environment without internet access, Leaflet will fail to load and throw `ReferenceError: L is not defined`.
- **Database Non-Interference**: During this investigation, database files and existing SQLite data were strictly preserved in read-only mode. Mock HTTP servers were used for Playwright execution to prevent any side effects on `pokemap.db`.

---

## 4. Conclusion & Recommendations

### Concrete Fix Recommendations for `app/templates.py`:

1. **Implement Missing Settings Modal Functions in `templates.py`**:
   Add implementations for `updateSettings`, `selectRegion`, and `refreshData` in both `render_map_page()` and `render_thongbao_page()` (or in shared script):
   ```javascript
   function updateSettings(key, val) {
     if (!configData.notifications) configData.notifications = {};
     configData.notifications[key] = val;
     configData[key] = val;
     try { localStorage.setItem('poketan_config', JSON.stringify(configData)); } catch(e) {}
   }
   function selectRegion(pref) {
     currentRegion = pref;
     try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
     if (typeof mapRegionFilter !== 'undefined') {
       mapRegionFilter = pref;
       if (REGIONS[pref] && window.map) {
         map.flyTo(REGIONS[pref].center, REGIONS[pref].zoom || 13, { duration: 1.0 });
       }
       renderMapMarkers();
     } else if (typeof listRegionFilter !== 'undefined') {
       listRegionFilter = pref;
       listCurrentPage = 1;
       renderStoreList();
     }
     closeSettingsModal();
   }
   function refreshData() {
     if (typeof initData === 'function') initData();
   }
   ```

2. **Fix Status Filter Mappings in `#map-counter-pill`**:
   In `render_map_page()` line 2054 and 2057:
   - Change `quickFilterMapStatus('not')` to `quickFilterMapStatus('n')`.
   - Change `quickFilterMapStatus('all')` on the `stat-unk` segment to `quickFilterMapStatus('unknown')`.

3. **Reposition Map Viewport on Region Filter Apply**:
   In `applyAndCloseMapFilterModal()` (line 2257):
   ```javascript
   function applyAndCloseMapFilterModal() {
     const regionChanged = (mapRegionFilter !== mapModalTempRegion);
     mapRegionFilter = mapModalTempRegion;
     mapStatusFilter = mapModalTempStatus;
     mapChainFilter = mapModalTempChain;
     mapTimeFilter = mapModalTempTime;
     saveMapFiltersToStorage();
     closeMapFilterModal();
     updateMapFilterUI();
     if (regionChanged && REGIONS[mapRegionFilter]) {
       map.flyTo(REGIONS[mapRegionFilter].center, REGIONS[mapRegionFilter].zoom || 13, { duration: 1.0 });
     }
     renderMapMarkers();
   }
   ```

4. **Format Toast Time to `たった今` for All Reports within 120s**:
   In `showNewReportToast(rep)` (lines 2847 and 4734):
   ```javascript
   const timeAgo = (repTs > 0 && (getServerNowSec() - repTs) <= 120) ? 'たった今' : formatTimeAgoJp(repTs);
   ```

5. **Clean Up Unused Header & Orphaned DOM References**:
   - In `render_map_page()` line 1493, remove unused `header = render_shared_header()`.
   - Remove orphaned DOM calls to `header-loc-name`, `map-chain-select`, `map-time-select`.

---

## 5. Verification Method

To independently verify these findings:
1. **Python Compilation**:
   ```powershell
   python -m py_compile app/templates.py app/web.py app/db.py app/fetcher.py app/parser.py
   ```
2. **JavaScript Syntax**:
   Extract scripts from `render_map_page()` and `render_thongbao_page()` and run:
   ```powershell
   node --check <script_file>.js
   ```
3. **Settings Modal Interaction**:
   Open `/` or `/thongbao` in browser or Playwright, trigger `openSettingsModal()`, and click `#set-sound-check`, radio `set-region-radio`, and "Cập nhật dữ liệu mới nhất". Observe console `Uncaught ReferenceError`.
4. **Header Counter Pill Click**:
   Click `🟡 ko bán` in the map header. Observe that `mapStatusFilter` becomes `'not'` while stores filter expects `'n'`, resulting in no filtering.
5. **Toast 120s Formatting**:
   Simulate `/api/latest_reports` with report timestamp = `now - 90`. Observe that the toast renders with badge `1分前` instead of `たった今`.
