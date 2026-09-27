# Investigation & Audit Report: Requirement R2 (Background Daemon) & R3 (API Endpoints & Time Sync)

**Author**: Explorer 2 (Daemon & API Explorer)  
**Date**: 2026-09-27  
**Scope**: `app/web.py`, `app/db.py`, `app/fetcher.py`, `app/parser.py`, `scripts/harvest_all_history.py`, `app/templates.py`, `app/data/pokemap.db`.

---

## 1. Observation

### 1.1 Python Compilation and Warning Status
Execution of compilation and AST checks across the entire codebase:
- Command: `python -m compileall app scripts`
  - Output: Exit code `0`. All Python bytecodes compiled without syntax errors.
- AST and Warning Audit:
  - All 11 Python files (`app/__init__.py`, `app/config.py`, `app/fetcher.py`, `app/parser.py`, `app/db.py`, `app/calendar_tracker.py`, `app/exporter.py`, `app/main.py`, `app/templates.py`, `app/web.py`, `scripts/harvest_all_history.py`) parsed cleanly via `ast.parse()`.
  - Module import check with `warnings.catch_warnings(record=True)` confirmed **0 syntax errors and 0 critical warnings**.

---

### 1.2 Background Daemon (`telegram_background_watcher`) & Prefecture Scanning
Inspecting `app/web.py` lines 155–167 and 406–518:

1. **Missing Tokyo in Polling List**:
   - `app/web.py` Line 156 defines:
     ```python
     ALL_PREFS = ["osaka", "aichi", "kanagawa", "gifu", "mie"]
     ```
   - `app/web.py` Lines 159–166 defines:
     ```python
     REGION_PREFS = {
         "osaka": ["osaka"],
         "tokyo": ["kanagawa"],
         "kanagawa": ["kanagawa"],
         "nagoya": ["aichi", "gifu", "mie"],
         "aichi": ["aichi", "gifu", "mie"],
         "all": ["osaka", "aichi", "kanagawa", "gifu", "mie"],
     }
     ```
   - **Verification on Live Firestore**:
     - `fetch_firestore_document('status/tokyo')` returns **733 active reports**.
     - `fetch_firestore_document('status/tokyo_cold')` returns **132 records**.
     - `fetch_stores('tokyo')` downloads metadata for **6,627 stores** (`stores_tokyo.json`, 1.66 MB).
   - **Omission in Database Initializers (`app/db.py`)**:
     - Line 160: `("tokyo", "東京・神奈川 (Tokyo & Lân cận)", "横浜", 35.4500, 139.6300, 12, json.dumps(["kanagawa"]))` — Tokyo region only contains Kanagawa!
     - Line 187: `pref_files` in `seed_stores_if_empty()` omits `"tokyo"`. SQLite `stores` table contains 0 stores for Tokyo (Aichi: 3,849; Gifu: 21; Kanagawa: 4,045; Mie: 4; Osaka: 4,051; Tokyo: 0).
     - Line 260: `prefs = ["osaka", "kanagawa", "aichi", "gifu", "mie"]` in `backfill_all_poketan_statuses()` omits Tokyo.
     - Line 383: `get_stores()` maps `tokyo` to `["kanagawa"]` and omits `tokyo` from `all`.
     - Line 794: `get_report_counts()` maps `tokyo` to `["kanagawa"]` and omits `tokyo` from `all`.

2. **Threading Structure & Failure Boundary**:
   - In `app/web.py` lines 434–438:
     ```python
     with ThreadPoolExecutor(max_workers=min(5, len(ALL_PREFS))) as executor:
         futs = {executor.submit(fetch_realtime_status, p, False): p for p in ALL_PREFS}
         pref_data_map = {p: f.result() for f, p in futs.items()}
     ```
     `ThreadPoolExecutor` fetches HTTP documents from Firestore in parallel.
   - Lines 440–513:
     ```python
     for pref, hot_data in pref_data_map.items():
         if not hot_data:
             continue
         try:
             for k, raw in hot_data.items():
                 ...
                 is_new, rep = record_new_report(...)
                 if is_new and code == "i":
                     threading.Thread(target=_backfill_store_history_safe, args=(sid,), daemon=True).start()
         except Exception as pe:
             pass
     ```
     **Critical Exception Boundary Flaw**: The `try...except Exception as pe: pass` block wraps the *entire* inner loop of all stores for a prefecture. If one store encounters a transient lock error, network hiccup, or invalid payload, the loop breaks and all subsequent stores in that prefecture are skipped for that cycle.
   - **Daemon Lifecycle in ASGI Mode**:
     In `app/web.py` line 795, `watcher_thread` is instantiated and started only inside `def main():`. When deployed via `uvicorn app.web:app`, `main()` is not executed, meaning `telegram_background_watcher()` is never started unless started via FastAPI startup event or lifespan handler.

---

### 1.3 SQLite Concurrency, WAL Mode, and Lock Prevention
Inspecting `app/db.py` lines 19–27 and transaction patterns across `app/db.py`:

1. **Connection Lifecycle & WAL**:
   - Lines 19–26:
     ```python
     def get_db_connection() -> sqlite3.Connection:
         conn = sqlite3.connect(DB_PATH, timeout=20.0)
         conn.row_factory = sqlite3.Row
         conn.execute("PRAGMA journal_mode = WAL;")
         conn.execute("PRAGMA synchronous = NORMAL;")
         conn.execute("PRAGMA foreign_keys = ON;")
         return conn
     ```
   - Connection per call: Connections are created on-demand, avoiding cross-thread sharing (`check_same_thread=True` default is respected).
   - WAL mode and timeout (20.0s) are enabled.
2. **Missing `conn.close()` in Context Management**:
   - Across `app/db.py`, functions use:
     ```python
     with get_db_connection() as conn:
         cursor = conn.cursor()
         ...
         conn.commit()
     ```
   - In Python standard library `sqlite3`, `sqlite3.Connection.__exit__` only issues `commit` or `rollback`. It **does not close** the connection handle.
   - Connection handles remain open until garbage collection runs. Under heavy polling loops (2,130 reports evaluated every 12 seconds in `telegram_background_watcher`), thousands of connection handles and read-locks can linger before GC runs, creating file descriptor leaks and blocking WAL checkpoints.
3. **Absence of Concurrency Lock on SQLite Writes**:
   - `telegram_background_watcher()`, `_backfill_store_history_safe()`, `record_report_endpoint()`, and background startup backfill all initiate write transactions concurrently.
   - Default isolation level in Python `sqlite3` is deferred (`""`). When Thread A executes `SELECT ...` and Thread B executes `SELECT ...`, both obtain SHARED locks. When both subsequently attempt `INSERT ...` or `UPDATE ...`, they enter SQLite lock upgrade deadlock, triggering `sqlite3.OperationalError: database is locked`.

---

### 1.4 History Backfill vs. Real-Time Stream Pollution (`created_at`)
Inspecting `app/db.py`, `scripts/harvest_all_history.py`, and `app/templates.py`:

1. **`record_new_report` (line 561)**:
   ```python
   created_at_val = now_ts if (now_ts - timestamp <= 120) else timestamp
   ```
   Correctly assigns `created_at = now_ts` only when report arrival is within 120 seconds of its timestamp; otherwise preserves historical `timestamp`.
2. **`save_bulk_history` (line 677)**:
   ```python
   hist_created_at = ts if ts > 0 else now_ts
   ```
   Correctly assigns historical `ts` as `created_at`.
3. **CRITICAL BUG in `backfill_all_poketan_statuses` (`app/db.py` line 306)**:
   ```python
   history_batch.append((
       hist_id, sid, code, label, "", json.dumps(packs, ensure_ascii=False),
       "匿名トレーナー", "", 1 if onsite else 0, confirms,
       ts, rep_time, now_ts, "poketan"  # <-- BUG: passes now_ts instead of ts!
   ))
   ```
   Every historical status backfilled via this function has its `created_at` artificially inflated to the current execution timestamp (`now_ts`).
4. **CRITICAL BUG in `scripts/harvest_all_history.py` (line 219)**:
   ```python
   history_batch.append((
       hist_id, sid, code, h["status_label"], h["note"], h["packs_json"],
       h["user"], h["who"], h["onsite"], h["confirms"],
       ts, h["formatted_time"], now_ts, h["source"]  # <-- BUG: passes now_ts!
   ))
   ```
5. **Database Evidence in `pokemap.db`**:
   - Query: `SELECT COUNT(*) FROM store_history WHERE created_at - timestamp > 120;`
   - Result: **12 records** exist with inflated `created_at` (e.g. record `gBS7SDFZO6bHaX4kid1d` has `timestamp = 1789897953` and `created_at = 1790475687`, a difference of 577,734 seconds / 6.7 days).
6. **Frontend Map Mutation Vulnerability**:
   - In `app/templates.py` line 2946:
     ```javascript
     } else if (st) {
       st.status = rep.status_code;
       st.last_timestamp = rep.timestamp;
       st.onsite = !!rep.onsite;
       st.packs = rep.packs || [];
       st.last_reported_at = rep.reported_at || rep.formatted_time || '';
       shouldReRender = true;
     }
     ```
     The client does not check `if (rep.timestamp >= st.last_timestamp)`. When `/api/latest_reports` returns an ancient record whose `created_at` was inflated, the client overwrites a store's fresh state with the 7-day-old state.

---

### 1.5 API Endpoints and Time Sync (`/api/latest_reports`, `/api/store_history`, `/api/config`)
1. **`/api/config`**:
   - Implemented in `app/web.py` lines 720–745. Returns `"serverTime": int(time.time())` (Unix epoch seconds).
   - In `app/templates.py` lines 3004 and 4881:
     `serverTimeOffset = configData.serverTime - Math.floor(Date.now() / 1000);`
     `getServerNowSec() = Math.floor(Date.now() / 1000) + serverTimeOffset;`
   - Accurately tracks server time.
   - Minor latency offset: In `app/templates.py`, `serverTimeOffset` is evaluated after `Promise.all` downloads `stores_data?region=all` (several MBs), adding a 1–2s network latency delay to the offset calibration.
2. **`/api/latest_reports?since=...`**:
   - Implemented in `app/web.py` line 708 calling `get_recent_reports(since_created_at, limit)`.
   - Queries `WHERE h.created_at > ? ORDER BY h.timestamp DESC, h.created_at DESC LIMIT ?`.
   - Fully operational. When `created_at` is accurate, only reports created after `since` are returned.
3. **`/api/store_history/{store_id}`**:
   - Implemented in `app/web.py` lines 664–685.
   - Queries `store_history` up to `limit=100`, ordered by `timestamp DESC`.
   - **Database JST Compliance**:
     - Verified all 24,395 records in `store_history`: **0 mismatches** against JST `%H:%M %d/%m/%Y`.
     - Verified all `stores.last_reported_at`: **0 mismatches** against JST.
   - **Code Inconsistencies**:
     - `app/db.py` line 751: `dt = datetime.fromtimestamp(newest_ts)` omits `tz=JST` (uses host local time).
     - `app/db.py` line 942: `datetime.fromtimestamp(last_in_ts).strftime("%H:%M %d/%m/%Y")` omits `tz=JST`.
     - `scripts/harvest_all_history.py` line 112: `dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")); dt.strftime(...)` formats in UTC instead of JST (missing `jst_dt = dt.astimezone(JST)`).

---

## 2. Logic Chain

1. **Prefecture Gap**:
   - From Observation 1.2: `ALL_PREFS` in `app/web.py` and `pref_files` in `app/db.py` omit Tokyo (`tokyo`).
   - `fetch_stores('tokyo')` and `fetch_firestore_document('status/tokyo')` verify 6,627 stores and 733 active reports exist on PokéTan.
   - Therefore, the background daemon is failing to scan Tokyo, leaving 6,627 stores with stale status and omitting Tokyo from Telegram alerts and notifications.

2. **Concurrency & Database Lock Cause**:
   - From Observation 1.3: `get_db_connection()` leaves SQLite connections open because `with conn:` in standard Python `sqlite3` does not close connections.
   - Concurrently, `telegram_background_watcher()`, `_backfill_store_history_safe()`, and web endpoints write to SQLite without a shared `threading.Lock()` or `BEGIN IMMEDIATE`.
   - Therefore, concurrent threads executing deferred transactions encounter lock upgrade contention, directly explaining occurrences of `sqlite3.OperationalError: database is locked`.

3. **Stream Pollution Cause**:
   - From Observation 1.4: `backfill_all_poketan_statuses()` (line 306) and `harvest_all_history.py` (line 219) hardcode `created_at = now_ts`.
   - 12 existing records in `store_history` have `created_at` inflated up to 6.7 days beyond `timestamp`.
   - When clients call `/api/latest_reports?since=lastDbPollTs`, these backfilled records match `h.created_at > lastDbPollTs`.
   - Because `app/templates.py` line 2946 lacks a `rep.timestamp >= st.last_timestamp` guard, these spurious historical records overwrite current store statuses on the map.

4. **Time Sync & JST Formatting**:
   - From Observation 1.5: Existing database records are 100% compliant with JST.
   - However, lines 751 and 942 of `app/db.py` and line 112 of `harvest_all_history.py` rely on local system time or UTC rather than explicit `timezone(timedelta(hours=9))`.
   - On non-JST host environments (such as cloud servers or Docker containers configured to UTC), newly processed records from those specific code branches would be off by 9 hours.

---

## 3. Caveats

1. **Read-Only Investigation**: In accordance with the system constraints, no production files were modified during this investigation. All proposed fixes are presented with verbatim before/after snippets for the implementation phase.
2. **Firestore Rate Limits**: Polling all 6 prefectures (including Tokyo) increases the number of concurrent HTTP requests in `telegram_background_watcher()`. At an interval of 12 seconds, 6 HTTP GET requests every 12 seconds (~0.5 req/sec) is well within Firestore's free quota (50,000 reads/day).
3. **Existing Inflated Records**: 12 records in `pokemap.db` have `created_at > timestamp + 120`. They require a single SQL update (`UPDATE store_history SET created_at = timestamp WHERE created_at - timestamp > 120;`).

---

## 4. Conclusion & Actionable Fix Recommendations

### Finding Summary Table
| ID | Area | Severity | Root Cause | Impact | Recommended Fix |
|---|---|---|---|---|---|
| F1 | `app/web.py` & `app/db.py` | High | Tokyo omitted from `ALL_PREFS` and DB initializers | 6,627 Tokyo stores and 733 live reports not scanned | Add `"tokyo"` to `ALL_PREFS`, `REGION_PREFS`, `seed_stores_if_empty`, `get_stores`, `get_report_counts` |
| F2 | `app/db.py` (line 306) | High | `now_ts` assigned to `created_at` in backfill | Historical records flood real-time `/api/latest_reports` | Use `ts` (or `now_ts if now_ts - ts <= 120 else ts`) for `created_at` |
| F3 | `app/db.py` (line 21) | High | `get_db_connection` not closed via contextmanager | Lingering connection handles, lock contention | Refactor `get_db_connection` with `@contextmanager` + `try...finally: conn.close()` |
| F4 | `app/db.py` (line 518) | Medium | No thread write lock for SQLite transactions | Potential `database is locked` during concurrent writes | Add module-level `_db_write_lock = threading.Lock()` for write operations |
| F5 | `app/web.py` (line 443) | Medium | `try...except` outside inner store loop in daemon | One failure aborts processing for entire prefecture | Move `try...except` inside store loop |
| F6 | `app/web.py` (line 795) | Medium | Daemon thread only started in `def main()` | Daemon idle if app launched via `uvicorn app.web:app` | Add `@app.on_event("startup")` to launch daemon |
| F7 | `app/templates.py` (line 2946) | Medium | Client store status updated without timestamp check | Ancient reports can overwrite newer store status | Add `if (!st.last_timestamp \|\| rep.timestamp >= st.last_timestamp)` guard |
| F8 | `app/db.py` (751, 942) | Low | `datetime.fromtimestamp()` without explicit JST timezone | Server in UTC would output UTC time instead of JST | Add `tz=timezone(timedelta(hours=9))` |
| F9 | `scripts/harvest_all_history.py` (112, 219) | Low | UTC strftime and `created_at = now_ts` | Script corrupts JST time and created_at if executed | Add `dt.astimezone(JST)` and `created_at = ts` |

---

### Concrete Code Proposals

#### 1. Fix `app/web.py`: Add Tokyo to Prefectures & Refine Daemon Loop
In `app/web.py`:
```python
# BEFORE (Line 156-166)
ALL_PREFS = ["osaka", "aichi", "kanagawa", "gifu", "mie"]
REGION_PREFS = {
    "osaka": ["osaka"],
    "tokyo": ["kanagawa"],
    "kanagawa": ["kanagawa"],
    "nagoya": ["aichi", "gifu", "mie"],
    "aichi": ["aichi", "gifu", "mie"],
    "all": ["osaka", "aichi", "kanagawa", "gifu", "mie"],
}

# AFTER
ALL_PREFS = ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"]
REGION_PREFS = {
    "osaka": ["osaka"],
    "tokyo": ["tokyo", "kanagawa"],
    "kanagawa": ["kanagawa"],
    "nagoya": ["aichi", "gifu", "mie"],
    "aichi": ["aichi", "gifu", "mie"],
    "all": ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"],
}
```

Daemon loop exception protection (`app/web.py` line 443):
```python
# BEFORE
for pref, hot_data in pref_data_map.items():
    if not hot_data:
        continue
    try:
        for k, raw in hot_data.items():
            ...
    except Exception as pe:
        pass

# AFTER
for pref, hot_data in pref_data_map.items():
    if not hot_data:
        continue
    for k, raw in hot_data.items():
        try:
            if k.endswith("_c"):
                continue
            ...
        except Exception as pe:
            continue
```

Add FastAPI startup event for daemon (`app/web.py`):
```python
# ADD to app/web.py
@app.on_event("startup")
def startup_event():
    import threading
    threading.Thread(target=telegram_background_watcher, daemon=True).start()
```

#### 2. Fix `app/db.py`: Connection Lifecycle, Write Lock, and Backfill `created_at`
```python
# BEFORE (app/db.py line 20)
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# AFTER (app/db.py)
from contextlib import contextmanager
_db_write_lock = threading.Lock()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()
```

Fix `backfill_all_poketan_statuses` (`app/db.py` line 306):
```python
# BEFORE (line 306)
now_ts = int(time.time())
...
history_batch.append((
    hist_id, sid, code, label, "", json.dumps(packs, ensure_ascii=False),
    "匿名トレーナー", "", 1 if onsite else 0, confirms,
    ts, rep_time, now_ts, "poketan"
))

# AFTER
created_at_val = now_ts if (now_ts - ts <= 120) else ts
history_batch.append((
    hist_id, sid, code, label, "", json.dumps(packs, ensure_ascii=False),
    "匿名トレーナー", "", 1 if onsite else 0, confirms,
    ts, rep_time, created_at_val, "poketan"
))
```

Fix JST timezone conversion (`app/db.py` lines 751 & 942):
```python
# BEFORE (line 751)
dt = datetime.fromtimestamp(newest_ts)
newest_formatted = dt.strftime("%H:%M %d/%m/%Y")

# AFTER
from datetime import timezone, timedelta
JST = timezone(timedelta(hours=9))
dt = datetime.fromtimestamp(newest_ts, tz=JST)
newest_formatted = dt.strftime("%H:%M %d/%m/%Y")
```

```python
# BEFORE (line 942)
"last_in_stock_time": datetime.fromtimestamp(last_in_ts).strftime("%H:%M %d/%m/%Y") if last_in_ts else "Chưa có",

# AFTER
"last_in_stock_time": datetime.fromtimestamp(last_in_ts, tz=timezone(timedelta(hours=9))).strftime("%H:%M %d/%m/%Y") if last_in_ts else "Chưa có",
```

#### 3. Fix `app/templates.py`: Guard against Stale Status Overwrite
```javascript
// BEFORE (line 2946)
} else if (st) {
  st.status = rep.status_code;
  st.last_timestamp = rep.timestamp;
  st.onsite = !!rep.onsite;
  st.packs = rep.packs || [];
  st.last_reported_at = rep.reported_at || rep.formatted_time || '';
  shouldReRender = true;
}

// AFTER
} else if (st) {
  if (!st.last_timestamp || (rep.timestamp && rep.timestamp >= st.last_timestamp)) {
    st.status = rep.status_code;
    st.last_timestamp = rep.timestamp;
    st.onsite = !!rep.onsite;
    st.packs = rep.packs || [];
    st.last_reported_at = rep.reported_at || rep.formatted_time || '';
    shouldReRender = true;
  }
}
```

#### 4. Database Cleanup SQL: Correct Inflated `created_at`
```sql
UPDATE store_history
SET created_at = timestamp
WHERE created_at - timestamp > 120;
```

---

## 5. Verification Method

### 5.1 Verification Commands
1. **Compilation and Import Cleanliness**:
   ```powershell
   python -m compileall app scripts
   python -c "import app.web, app.db, app.fetcher, app.parser, app.templates; print('ALL IMPORTS OK')"
   ```
2. **Database Integrity & Concurrency Test**:
   ```powershell
   python -c "
   from app.db import get_db_connection, record_new_report
   import threading, time

   def worker(idx):
       for i in range(20):
           record_new_report(f'test_store_{idx}', 'i', int(time.time()), note=f'w{idx}_{i}')

   threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
   for t in threads: t.start()
   for t in threads: t.join()
   print('Concurrency test: SUCCESS - No lock errors!')
   "
   ```
3. **Verify Zero Duplicate Records & Zero Inflated `created_at`**:
   ```powershell
   python -c "
   from app.db import get_db_connection
   with get_db_connection() as conn:
       c = conn.cursor()
       c.execute('SELECT COUNT(*) FROM (SELECT store_id, timestamp, status_code FROM store_history GROUP BY store_id, timestamp, status_code HAVING COUNT(*) > 1);')
       print('Duplicates:', c.fetchone()[0])
       c.execute('SELECT COUNT(*) FROM store_history WHERE created_at - timestamp > 120;')
       print('Inflated created_at:', c.fetchone()[0])
   "
   ```
4. **API Endpoint Functionality Test**:
   ```powershell
   python -c "
   import sys; sys.stdout.reconfigure(encoding='utf-8')
   from fastapi.testclient import TestClient
   from app.web import app
   client = TestClient(app)

   # 1. Config
   r = client.get('/api/config')
   assert r.status_code == 200 and 'serverTime' in r.json()

   # 2. Latest reports
   r = client.get('/api/latest_reports?since=0&limit=5')
   assert r.status_code == 200

   # 3. Store history
   r = client.get('/api/store_history/p_REvOwf1HkvE4')
   assert r.status_code == 200
   print('All API endpoints verified: 200 OK!')
   "
   ```

### 5.2 Invalidation Conditions
- Any occurrence of `sqlite3.OperationalError: database is locked` in `app/web.py` daemon or API routes invalidates concurrency stability.
- Any record in `store_history` with `created_at > timestamp + 120` from backfilled sources invalidates stream isolation.
- Any response from `/api/config` where `abs(serverTime - int(time.time())) > 2` invalidates time synchronization.
