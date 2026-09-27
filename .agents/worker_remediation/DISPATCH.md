## 2026-09-27T04:19:28Z
You are the Remediation Worker for the PokéTan Stock Tracker project.
Your working directory is: c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_remediation

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read:
- c:\Users\Admin\Desktop\project\POKETAN\.agents\ORIGINAL_REQUEST.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\orchestrator_1\PROJECT.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\reviewer_1\handoff.md
- c:\Users\Admin\Desktop\project\POKETAN\.agents\reviewer_2\handoff.md

Your Scope: Remediate the concrete findings raised by Reviewers 1 and 2:

1. In `scripts/harvest_all_history.py`:
   - Import `get_db_connection` and `_db_write_lock` from `app.db`.
   - Replace the custom `get_db()` function so it uses `get_db_connection()` (which guarantees connection closure in `finally:`).
   - Wrap the SQLite write operations in `with _db_write_lock:` and `with get_db_connection() as db_conn:`.

2. In `app/db.py`:
   - In `init_db()`: Add a check for Tokyo stores. If `SELECT COUNT(*) FROM stores WHERE pref = 'tokyo';` is 0, read `app/data/stores_tokyo.json` and insert all Tokyo stores via `INSERT OR IGNORE INTO stores (id, name, chain, address, lat, lng, pref, current_status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);`. Run `python -c "from app.db import init_db; init_db()"` to seed Tokyo stores into `app/data/pokemap.db`.
   - In `record_new_report(..., pref: str = "osaka")`: Accept `pref` parameter and use it in fallback store creation rather than hardcoding `'osaka'`.
   - In `save_bulk_history(..., pref: str = "osaka")`: Accept `pref` parameter and use it in fallback store creation rather than hardcoding `'osaka'`.

3. In `app/templates.py`:
   - In `REGIONS` dictionary in both `render_map_page()` and `render_thongbao_page()`:
     * In `'tokyo'`, update `prefs: ['tokyo', 'kanagawa']` and center to `[35.6895, 139.6917]`.
     * In `'all'`, update `prefs: ['osaka', 'tokyo', 'kanagawa', 'aichi', 'gifu', 'mie']`.

4. Test Verification:
   - Run the complete test suite: `python -m pytest tests -v`. Ensure 100% of tests pass.
   - Run compilation: `python -m compileall app scripts tests`.
   - Verify Tokyo stores in database: `python -c "import sqlite3; c = sqlite3.connect('app/data/pokemap.db').cursor(); c.execute('SELECT COUNT(*) FROM stores WHERE pref=\'tokyo\';'); print('Tokyo stores:', c.fetchone()[0])"`.
   - Verify 0 duplicate records, 0 inflated created_at, 100% JST compliance.

5. Document all changes, diffs, and test outputs in:
   `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_remediation\handoff.md`.
Update your progress in `c:\Users\Admin\Desktop\project\POKETAN\.agents\worker_remediation\progress.md`.
When finished, notify parent via send_message.
