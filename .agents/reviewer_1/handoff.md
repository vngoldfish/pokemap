# Code Integrity & Adversarial Review Report: PokéTan Stock Tracker

- **Reviewer**: Reviewer 1 (Code Integrity Reviewer & Adversarial Critic)
- **Date**: 2026-09-27T04:22:00Z
- **Working Directory**: `c:\Users\Admin\Desktop\project\POKETAN\.agents\reviewer_1`
- **Scope**: `app/db.py`, `app/web.py`, `app/templates.py`, `scripts/harvest_all_history.py`, `app/data/pokemap.db`, `tests/`
- **Verdict**: **REQUEST_CHANGES**

---

## Review Summary

**Verdict**: **REQUEST_CHANGES**

### Integrity Assessment
- **Integrity Violations**: **NONE DETECTED (0 Violations)**.
- **Evidence Verification**: Confirmed NO hardcoded test results, NO dummy/facade implementations, NO task bypasses, NO fabricated logs or self-certifying artifacts. The core implementations across `app/db.py`, `app/web.py`, and `app/templates.py` are genuine, functional, and well-structured.
- **Reason for REQUEST_CHANGES**:
  1. `scripts/harvest_all_history.py` contains a critical SQLite connection leak (unclosed connections in batch chunk loop) and lacks `_db_write_lock`, posing database lock risks under live operation.
  2. `app/db.py` contains hardcoded `pref = 'osaka'` on fallback store creation in `record_new_report` and `save_bulk_history`, and the existing `app/data/pokemap.db` database contains 0 stores from Tokyo because `seed_stores_if_empty()` skips execution when `COUNT(*) > 0`.
  3. `python -m pytest -v` currently reports 3 test failures in `tests/test_challenger_api_ui.py` due to mismatched contract expectations (`poketan_settings` vs `poketan_config`, `packCodes` list vs dict, subsecond skew float tolerance).

---

## 1. Observation

### 1.1 Python Compilation Check (`python -m compileall app scripts tests`)
- **Command**: `python -m compileall app scripts tests`
- **Exit Code**: `0`
- **Verbatim Output**: All files compiled cleanly with 0 syntax errors across `app/`, `scripts/`, and `tests/`.

### 1.2 Database Integrity & Data Cleanliness (`app/data/pokemap.db`)
Directly verified via independent SQLite queries against `app/data/pokemap.db`:
1. `PRAGMA integrity_check;` returned `ok`.
2. Total rows in `store_history`: **24,501**.
3. Total rows in `stores`: **11,993**.
4. Unique Index: `idx_hist_unique ON store_history(store_id, timestamp, status_code)` is active and verified.
5. Duplicates query:
   ```sql
   SELECT store_id, timestamp, status_code, COUNT(*) 
   FROM store_history 
   GROUP BY store_id, timestamp, status_code 
   HAVING COUNT(*) > 1;
   ```
   Returned **0 duplicates**.
6. Inflated `created_at` records query:
   ```sql
   SELECT COUNT(*) FROM store_history WHERE created_at > timestamp + 120 AND timestamp > 0;
   ```
   Returned **0 inflated records** (all 12 legacy inflated rows were repaired).
7. JST Timezone Compliance query:
   Verified all 24,501 rows with `timestamp > 0`. Comparing `formatted_time` against `datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=9))).strftime("%H:%M %d/%m/%Y")`:
   - Exact JST match: **24,501 / 24,501 (100.0%)**.
   - Mismatches: **0**.
   - Malformed time strings: **0**.

### 1.3 Concurrency & Lock Safety
- Spatially isolated write transactions: `app/db.py` implements `@contextmanager def get_db_connection()` with `try...finally: conn.close()` and protects writes with module-level `_db_write_lock = threading.Lock()`.
- Stress test: `tests/test_adversarial_db_stress.py` executed 8 concurrent writer threads + 4 bulk writers + 8 reader threads over 500+ operations.
- Verbatim result: **0 occurrences of `sqlite3.OperationalError: database is locked`**.

### 1.4 Test Suite Results
1. `tests/test_db_integrity.py`: 9 passed, 0 failed.
2. `tests/test_daemon_api.py`: 8 passed, 0 failed.
3. `tests/test_frontend_templates.py`: 11 passed, 0 failed.
4. `tests/test_adversarial_db_stress.py`: 7 passed, 0 failed.
5. `tests/test_challenger_api_ui.py`: 6 passed, 3 failed:
   - `test_api_config_server_time_skew_sequential`: failed on `avg_skew <= 0.5s` (got 0.55s due to subsecond float vs integer second truncation).
   - `test_api_config_fields_and_integrity`: failed on `assert isinstance(cfg.get("packCodes"), list)` (in `app/config.py`, `PACK_CODES` is a `dict`).
   - `test_javascript_node_execution_settings_and_region`: failed on `Error: localStorage poketan_settings not updated` (in `app/templates.py:2455`, localStorage key is `'poketan_config'`).

### 1.5 Code Defects Observed
1. **Connection Leak in `scripts/harvest_all_history.py:43-48` and line 242**:
   ```python
   def get_db():
       conn = sqlite3.connect(DB_PATH, timeout=30.0)
       conn.row_factory = sqlite3.Row
       conn.execute("PRAGMA journal_mode = WAL;")
       conn.execute("PRAGMA synchronous = NORMAL;")
       return conn
   ...
   for i in range(0, len(pending_stores), chunk_size):
       ...
       with get_db() as db_conn:
           ...
           db_conn.commit()
   ```
   In Python `sqlite3`, using `with conn:` only manages transaction commit/rollback; it **never closes** the connection handle. In a full run of 12,000 stores with chunk size 50, this leaks ~240 unclosed SQLite connections. Furthermore, `harvest_all_history.py` does not acquire `_db_write_lock`, conflicting with concurrent writes in `app.web`.

2. **Unseeded Tokyo Stores & Hardcoded Fallback `'osaka'`**:
   - `app/data/stores_tokyo.json` has 6,627 valid Tokyo stores.
   - However, `SELECT pref, COUNT(*) FROM stores GROUP BY pref;` shows:
     * aichi: 3,849
     * gifu: 21
     * kanagawa: 4,045
     * mie: 4
     * osaka: 4,074
     * **tokyo: 0 stores**.
   - `seed_stores_if_empty()` skips execution if `existing_count > 0`, so Tokyo stores were never seeded into the pre-existing database.
   - In `app/db.py:613` (`record_new_report`) and line 745 (`save_bulk_history`), when an unknown store reports status, the fallback store creation executes:
     `INSERT OR IGNORE INTO stores (id, name, chain, address, pref, current_status, updated_at) VALUES (?, ?, 'other', '', 'osaka', ?, ?);`
     This hardcodes `pref = 'osaka'`, causing any newly ingested Tokyo stores to be miscategorized as Osaka!

---

## 2. Logic Chain

1. **Integrity Rule Compliance**:
   - We inspected all modifications across `app/db.py`, `app/web.py`, `app/templates.py`, and `scripts/harvest_all_history.py`. All logic chains (unique index creation, `@contextmanager` lifecycle, `_db_write_lock`, JST conversions, DOM helper implementations) are genuine and implement actual business logic.
   - PRAGMA checks and independent verification on 24,501 rows confirm that data cleansing was fully applied without shortcuts or fabrication.

2. **Consequences of Harvester Connection Leak (Finding 1)**:
   - On Windows OS, open unclosed SQLite file handles retain read/write locks at the filesystem level.
   - If a developer or administrator runs `python scripts/harvest_all_history.py` while the FastAPI server daemon is running, the accumulating open connection handles without `_db_write_lock` synchronization will trigger `sqlite3.OperationalError: database is locked` on the daemon or API endpoints.

3. **Consequences of Unseeded Tokyo Stores & Fallback Hardcoding (Finding 2)**:
   - Although `REGION_PREFS["tokyo"] = ["tokyo", "kanagawa"]` was added in `app/web.py`, queries for Tokyo currently only return Kanagawa stores because `stores` has 0 stores with `pref = 'tokyo'`.
   - Furthermore, when the daemon fetches Tokyo real-time statuses from Firestore, unknown Tokyo store IDs inserted via `record_new_report` are inserted with `pref = 'osaka'`. Consequently, Tokyo stores end up categorized under Osaka, corrupting prefecture-based filtering on both the map and list views.

4. **Consequences of Failing Challenger Tests (Finding 3)**:
   - The test suite execution `python -m pytest -v` fails with exit code 1. While the root cause in 2 of the 3 failures stems from inaccurate challenger test expectations (`packCodes` is dict, not list; localStorage key is `poketan_config`, not `poketan_settings`), these tests reside in `tests/` and cause pipeline failures.

---

## 3. Findings

### [Major] Finding 1: Unclosed Connection Leak & Missing Write Lock in `scripts/harvest_all_history.py`
- **Where**: `scripts/harvest_all_history.py:43-48, 242-265`
- **Why**: `get_db()` returns a raw `sqlite3.Connection` without a closing context manager. `with get_db() as db_conn:` leaks handles across loop iterations. It also bypasses `_db_write_lock`, risking database lock errors against `telegram_background_watcher`.
- **Suggestion**:
  Refactor `scripts/harvest_all_history.py` to use `get_db_connection()` and `_db_write_lock` imported from `app.db`:
  ```python
  from app.db import get_db_connection, _db_write_lock
  ...
  with _db_write_lock:
      with get_db_connection() as db_conn:
          ...
  ```

### [Major] Finding 2: Unseeded Tokyo Stores in `pokemap.db` & Hardcoded `'osaka'` in Store Fallback
- **Where**: `app/db.py:209-212`, `app/db.py:613`, `app/db.py:745`
- **Why**:
  1. `seed_stores_if_empty()` only seeds when `stores` is completely empty. As a result, the 6,627 stores from `stores_tokyo.json` were never loaded into the existing database.
  2. When an unseen store is reported via `record_new_report` or `save_bulk_history`, `pref` is hardcoded to `'osaka'`, misrouting Tokyo stores to Osaka.
- **Suggestion**:
  1. In `app/db.py`, provide a prefecture-aware seed function or auto-seed `stores_tokyo.json` in `init_db()` via `INSERT OR IGNORE INTO stores`.
  2. In `record_new_report(..., pref="osaka")` and `save_bulk_history()`, pass the actual prefecture of the store rather than hardcoding `'osaka'`.

### [Minor] Finding 3: Failing Assertions in `tests/test_challenger_api_ui.py`
- **Where**: `tests/test_challenger_api_ui.py:68, 105, 402`
- **Why**:
  1. Line 402 asserts `localStorage.getItem('poketan_settings') !== null`, but the application correctly writes to `'poketan_config'`.
  2. Line 105 asserts `isinstance(cfg.get("packCodes"), list)`, but `packCodes` is a `dict`.
  3. Line 68 asserts `avg_skew <= 0.5s`, but integer second truncation against subsecond float timestamps causes expected skew ~0.55s.
- **Suggestion**: Align `test_challenger_api_ui.py` assertions with the established system contracts: check `'poketan_config'`, assert `isinstance(packCodes, dict)`, and allow `avg_skew <= 1.0s`.

### [Minor] Finding 4: FastAPI Deprecation Warning on Startup Event
- **Where**: `app/web.py:534`
- **Why**: `@app.on_event("startup")` produces a `DeprecationWarning` in FastAPI/Starlette.
- **Suggestion**: Migrate to FastAPI `lifespan` context manager when convenient.

---

## 4. Adversarial Challenges & Stress-Testing

### Challenge 1: Concurrent High-Volume Write/Read Deadlock
- **Assumption Challenged**: SQLite WAL mode alone prevents `database is locked` during concurrent bursts.
- **Stress Test**: 8 concurrent writer threads + 4 bulk history threads + 8 concurrent readers executed 500+ writes and 480 reads simultaneously.
- **Result**: **PASS**. Module-level `_db_write_lock` in `app/db.py` fully serialized write transactions, completely eliminating lock contention (0 lock errors).

### Challenge 2: Future Client Clock Skew Bounding
- **Assumption Challenged**: `record_new_report` correctly bounds clock skew.
- **Test**: Submitted reports with `timestamp = now + 500s`.
- **Finding**: `created_at_val = now_ts if (abs(now_ts - timestamp) <= 120) else timestamp`. If a client report is >120s in the future, `created_at` becomes that future timestamp, remaining visible indefinitely in `/api/latest_reports?since=...`.
- **Mitigation**: Use `created_at_val = now_ts if abs(now_ts - timestamp) <= 120 else min(now_ts, timestamp)`.

---

## 5. Verified Claims vs Acceptance Criteria

| # | Acceptance Criterion | Claim | Independent Verification Method | Result |
|---|----------------------|-------|---------------------------------|--------|
| 1 | 0 duplicates on `(store_id, timestamp, status_code)` | M1 Worker | Direct SQLite query: `HAVING COUNT(*) > 1` | **PASS (0 duplicates)** |
| 2 | 100% JST compliance (`%H:%M %d/%m/%Y`) | M1 Worker | Iterated 24,501 rows against `tz=JST` datetime | **PASS (100% compliant)** |
| 3 | 0 inflated `created_at` records | M1 Worker | Direct SQLite query: `created_at > timestamp + 120` | **PASS (0 inflated)** |
| 4 | No `database is locked` under concurrency | M2 Worker | Multithreaded stress test (8 writers, 8 readers) | **PASS (0 lock errors)** |
| 5 | Tokyo included in mappings & endpoints | M2 Worker | Inspected `ALL_PREFS`, `REGION_PREFS`, `regions` | **PASS** |
| 6 | Frontend JavaScript syntax & functions | M4 Worker | `node --check` and runtime execution under Node | **PASS** |
| 7 | Clean Python compilation | Orchestrator | `python -m compileall app scripts tests` | **PASS (Exit 0)** |

---

## 6. Caveats

- **Test Suite Mismatch**: `tests/test_challenger_api_ui.py` was introduced by parallel agent `challenger_2`. Reviewer 1 does not modify test or source code per constraints.
- **CDN Dependency**: External assets (Leaflet CDN) require internet access for full map tile rendering in a browser, but all server endpoints and local JS logic execute offline.

---

## 7. Conclusion

The core fixes delivered by Workers M1, M2, and M4 are genuine, effective, and verified: data and time integrity is fully established, WAL mode and write locking prevent concurrency deadlocks, and the frontend JavaScript executes without ReferenceErrors.

However, because:
1. `scripts/harvest_all_history.py` leaks SQLite connection handles and lacks write locking,
2. `stores_tokyo.json` remains unseeded in `pokemap.db` with fallback `'osaka'` misclassifying Tokyo stores, and
3. `python -m pytest -v` exits with code 1 due to test mismatches in `tests/test_challenger_api_ui.py`,

the verdict is **REQUEST_CHANGES** to ensure complete end-to-end reliability and clean CI test execution before final sign-off.

---

## 8. Verification Method

To independently verify all observations and test results:

1. **Compilation Check**:
   ```powershell
   python -m compileall app scripts tests
   ```

2. **Core Test Suites**:
   ```powershell
   python -m pytest tests/test_db_integrity.py tests/test_daemon_api.py tests/test_frontend_templates.py tests/test_adversarial_db_stress.py -v
   ```

3. **Database Integrity Verification**:
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect('app/data/pokemap.db'); c = conn.cursor(); c.execute('PRAGMA integrity_check;'); print('PRAGMA:', c.fetchone()[0]); c.execute('SELECT COUNT(*) FROM store_history WHERE created_at > timestamp + 120 AND timestamp > 0;'); print('Inflated created_at:', c.fetchone()[0]); c.execute('SELECT COUNT(*) FROM (SELECT store_id, timestamp, status_code FROM store_history GROUP BY store_id, timestamp, status_code HAVING COUNT(*) > 1);'); print('Duplicates:', c.fetchone()[0]);"
   ```
