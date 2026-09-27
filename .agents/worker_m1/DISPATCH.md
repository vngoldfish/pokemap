## 2026-09-27T03:50:00Z
You are Worker M1 (Database & Data Integrity Worker) for the PokéTan Stock Tracker project.
Your working directory is: c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read:
- c:\Users\Admin\Desktop\project\POKETAN\.agents\ORIGINAL_REQUEST.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\orchestrator_1\PROJECT.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\explorer_survey_1\handoff.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\explorer_survey_2\handoff.md

Your Scope: Milestone 1 - SQLite Database & Data Integrity
You have exclusive write ownership of:
- app/db.py
- scripts/harvest_all_history.py
- Database migration on app/data/pokemap.db

Tasks:
1. Connection lifecycle in app/db.py:
   Refactor `get_db_connection()` to use `@contextmanager` ensuring `conn.close()` is always called in `finally:` block. Keep WAL, timeout=30.0, synchronous=NORMAL, foreign_keys=ON. Ensure all callers in `app/db.py` and throughout the app using `with get_db_connection() as conn:` continue to work seamlessly.
2. Concurrency write lock in app/db.py:
   Add module-level `_db_write_lock = threading.Lock()` and protect SQLite write operations (`record_new_report`, `save_bulk_history`, `backfill_all_poketan_statuses`, etc.) to eliminate lock upgrade deadlocks.
3. Database migration in app/db.py `init_db()`:
   - Ensure `CREATE UNIQUE INDEX IF NOT EXISTS idx_hist_unique ON store_history(store_id, timestamp, status_code);`
   - Add auto-migration query to fix the 12 existing inflated records:
     `UPDATE store_history SET created_at = timestamp WHERE created_at > timestamp + 120 AND timestamp > 0;`
4. Created_at logic fixes:
   - In `app/db.py:306` (`backfill_all_poketan_statuses`): set `created_at` properly:
     `created_at_val = now_ts if (0 <= now_ts - ts <= 120) else (ts if ts > 0 else now_ts)`
   - In `app/db.py:561` (`record_new_report`): bound clock skew:
     `created_at_val = now_ts if (abs(now_ts - timestamp) <= 120) else timestamp`
5. Explicit JST formatting:
   - In `app/db.py:751` (`save_bulk_history`) and `app/db.py:942` (`get_store_restock_analytics`): use explicit `tz=timezone(timedelta(hours=9))`.
6. Tokyo region support in `app/db.py`:
   - Update `seed_stores_if_empty()` to include `"tokyo"` in `pref_files`.
   - Update `get_stores()` and `get_report_counts()` to map `"tokyo"` to `["tokyo", "kanagawa"]` and include `"tokyo"` in `"all"`.
7. `scripts/harvest_all_history.py`:
   - Line 112: `jst_dt = dt.astimezone(JST); formatted_time = jst_dt.strftime("%H:%M %d/%m/%Y")`.
   - Line 219: `created_at = ts if ts > 0 else now_ts`.
8. Verification & Test Execution:
   - Run `python -c "from app.db import init_db; init_db()"` to execute migration.
   - Run compilation check: `python -m compileall app scripts`.
   - Run tests checking:
     * PRAGMA integrity_check
     * 0 duplicate records on (store_id, timestamp, status_code)
     * 0 inflated created_at records (`created_at > timestamp + 120`)
     * 100% formatted_time conforms to JST (`%H:%M %d/%m/%Y`)
     * Multithreaded concurrent write test with 5 threads to verify 0 `database is locked` errors.
9. Write complete handoff report with exact diffs, commands run, and test outputs in:
   c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m1\handoff.md
Update your progress in c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_m1\progress.md.
When finished, notify parent via send_message.
