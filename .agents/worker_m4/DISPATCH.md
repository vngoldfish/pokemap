## 2026-09-27T04:03:05Z
You are Worker M4 (Frontend UI Worker) for the PokéTan Stock Tracker project.
Your working directory is: c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m4

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read:
- c:\Users\Admin\Desktop\project\POKETAN\.agents\ORIGINAL_REQUEST.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\orchestrator_1\PROJECT.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\explorer_survey_3\handoff.md

Your Scope: Milestone 4 (Frontend Map & List UI, JavaScript Syntax, Filters & Toast Notifications)
You have exclusive write ownership of:
- app/templates.py
- tests/test_frontend_templates.py

Tasks in `app/templates.py`:
1. Implement missing JavaScript functions in `SHARED_MODALS_HTML` or relevant script scopes:
   - `updateSettings(key, val)`
   - `selectRegion(pref)`
   - `refreshData()`
   Ensure that when the user clicks settings modal toggles, radios, or refresh, no ReferenceError is thrown.
2. Fix `#map-counter-pill` quick filter clicks in `render_map_page()`:
   - Change `onclick="quickFilterMapStatus('not')"` to `onclick="quickFilterMapStatus('n')"`.
   - Change `onclick="quickFilterMapStatus('all')"` on the `stat-unk` segment to `onclick="quickFilterMapStatus('unknown')"`.
3. Fix Map Filter Modal region viewport synchronization:
   - In `applyAndCloseMapFilterModal()`: when `mapModalTempRegion !== mapRegionFilter`, pan/fly the Leaflet map viewport to the new region center:
     `if (regionChanged && REGIONS[mapRegionFilter]) { map.flyTo(REGIONS[mapRegionFilter].center, REGIONS[mapRegionFilter].zoom || 13, { duration: 1.0 }); }`
4. Fix Toast Notification time formatting:
   - In `showNewReportToast(rep)` on both map page and notification page:
     Ensure that any fresh report (within 120 seconds: `(getServerNowSec() - repTs) <= 120` and `>= 0`) displays `たった今`, rather than transitioning to `1分前` at 60s.
5. Guard against stale status overwrite in `render_map_page()`:
   - When updating store in `latest_reports` poll (around line 2946), check:
     `if (!st.last_timestamp || (rep.timestamp && rep.timestamp >= st.last_timestamp))`
6. Clean up console warnings and orphaned DOM references (e.g. `header-loc-name`, `map-chain-select`, `map-time-select`).
7. Testing & Verification:
   - Create `tests/test_frontend_templates.py`:
     * Verify `render_map_page()` and `render_thongbao_page()` produce valid HTML.
     * Extract scripts from both pages and verify syntax using `node --check` (or node execution).
     * Verify presence of `updateSettings`, `selectRegion`, `refreshData`.
     * Verify `#map-counter-pill` filter click calls use `'n'` and `'unknown'`.
     * Verify toast logic formats `たった今` for reports <= 120s.
   - Run pytest: `python -m pytest tests/test_frontend_templates.py -v`.
   - Run compilation check: `python -m compileall app scripts tests`.
8. Write complete handoff report in `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m4\handoff.md`.
Update your progress in `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m4\progress.md`.
When finished, notify parent via send_message.
