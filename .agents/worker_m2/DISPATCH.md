## 2026-09-27T03:58:00Z
You are Worker M2 (Daemon & API Worker) for the PokéTan Stock Tracker project.
Your working directory is: c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read:
- c:\Users\Admin\Desktop\project\POKETAN\.agents\ORIGINAL_REQUEST.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\orchestrator_1\PROJECT.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\explorer_survey_2\handoff.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m1\handoff.md

Your Scope: Milestone 2 & Milestone 3 (Background Daemon Concurrency & API Endpoints)
You have exclusive write ownership of:
- app/web.py
- tests/test_daemon_api.py

Tasks:
1. Prefecture coverage in app/web.py:
   - Update ALL_PREFS to include "tokyo":
     `ALL_PREFS = ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"]`
   - Update REGION_PREFS:
     `"tokyo": ["tokyo", "kanagawa"]`
     `"all": ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"]`
2. Daemon loop robustness in app/web.py:
   - In `telegram_background_watcher()`:
     Refactor the exception handling so each store in `hot_data.items()` is wrapped in its own `try...except Exception as pe: continue`. This ensures an error on a single store does not abort the processing of the remaining stores in that prefecture.
   - Add `@app.on_event("startup")` to launch `telegram_background_watcher` in a daemon thread so that ASGI launches (`uvicorn app.web:app`) automatically run the background watcher. Keep existing `if __name__ == "__main__":` block clean.
3. API Endpoints & Time Sync verification in app/web.py:
   - Verify `/api/config`: returns `"serverTime": int(time.time())` accurately.
   - Verify `/api/latest_reports`: properly handles `since` parameter and returns clean list.
   - Verify `/api/store_history/{store_id}`: returns history ordered by timestamp DESC, up to 100 entries.
   - Verify `/` and `/thongbao` return HTTP 200.
4. Test creation and execution:
   - Create `tests/test_daemon_api.py` with comprehensive tests using `TestClient(app)`:
     * Test `/api/config` has valid `serverTime` matching `time.time()` within 2s.
     * Test `/api/latest_reports` returns 200 and list.
     * Test `/api/store_history/{id}` returns 200 and history list.
     * Test `/` and `/thongbao` return 200.
     * Test concurrent API polling + daemon report recording without `database is locked`.
   - Run tests: `python -m pytest tests/test_daemon_api.py -v`.
   - Verify Python compilation across all files: `python -m compileall app scripts tests`.
5. Write complete handoff report in `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m2\handoff.md`.
Update your progress in `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m2\progress.md`.
When finished, notify parent via send_message.
