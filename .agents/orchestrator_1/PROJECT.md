# Project: PokéTan Stock Tracker Review & Verification

## Architecture
- **Language/Framework**: Python 3.12 (FastAPI, SQLite, Uvicorn), HTML5/CSS3/Vanilla JavaScript + Leaflet.js.
- **Database**: `app/data/pokemap.db` (WAL mode, foreign keys enabled, unique index on `store_history`).
- **Core Modules**:
  - `app/db.py`: SQLite connection lifecycle (`@contextmanager`), locking, schema initialization, store data seeding, history queries and writes.
  - `app/web.py`: FastAPI application, HTTP endpoints (`/`, `/thongbao`, `/api/...`), background daemon `telegram_background_watcher`.
  - `app/fetcher.py` & `app/parser.py`: Telegram & Firestore scraper/parser.
  - `app/templates.py`: Map view (`/`) and Notification List view (`/thongbao`) HTML & JavaScript templates.

## Feature Inventory (Post-Survey Synthesis)
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SQLite Schema & Index | `idx_hist_unique ON store_history(store_id, timestamp, status_code)` verified, 0 duplicates | M1 | R1 (Survey 1) |
| 2 | JST Time Consistency | Ensure explicit `tz=JST` in `app/db.py:750, 942` and `scripts/harvest_all_history.py` | M1 | R1 (Survey 1, 2) |
| 3 | Created_at Timestamp Logic & Migration | Fix hardcoded `now_ts` in `app/db.py:306`, bound clock skew in `app/db.py:561`, run auto-migration for 12 inflated rows | M1 | R1 (Survey 1, 2) |
| 4 | Database Connection & Concurrency | `@contextmanager get_db_connection()` with guaranteed `conn.close()`, add `_db_write_lock` | M1 | R2 (Survey 2) |
| 5 | Tokyo Region Integration | Add `"tokyo"` to `ALL_PREFS`, `REGION_PREFS` in `app/web.py`, and `app/db.py` region mappings | M2 | R2 (Survey 2) |
| 6 | Daemon Concurrency & Resilience | Protect daemon inner loop with per-store `try...except`, add `@app.on_event("startup")` | M2 | R2 (Survey 2) |
| 7 | Client Map State Stale Guard | Guard `if (!st.last_timestamp \|\| rep.timestamp >= st.last_timestamp)` in `app/templates.py` | M3 | R3 (Survey 2) |
| 8 | API Endpoints & Time Sync | Validate `/api/config` `serverTime`, `/api/latest_reports`, `/api/store_history/{id}` | M3 | R3 (Survey 2) |
| 9 | JavaScript Runtime Fixes | Implement `updateSettings`, `selectRegion`, `refreshData` in `app/templates.py` | M4 | R4 (Survey 3) |
| 10 | Header Stats Pill Filter | Fix pill click mapping `'not'` -> `'n'`, and `stat-unk` `'all'` -> `'unknown'` | M4 | R4 (Survey 3) |
| 11 | Map Filter Region Sync | In `applyAndCloseMapFilterModal()`, pan/fly map to selected region center | M4 | R4 (Survey 3) |
| 12 | Toast 120s `たった今` Formatting | Ensure all reports <= 120s render `たった今` instead of `1分前` | M4 | R4 (Survey 3) |
| 13 | Final Acceptance & Forensic Verification | Automated test suite for all Acceptance Criteria, concurrency tests, and forensic audit | M5 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | SQLite Database & Data Integrity | `app/db.py`, `scripts/harvest_all_history.py`, DB migration | none | DONE |
| M2 | Background Daemon & Concurrency | `app/web.py`, prefecture scanning, daemon robustness | M1 | DONE |
| M3 | API Endpoints & Time Sync | `app/web.py`, `/api/...` verification, client state guard | M2 | DONE |
| M4 | Frontend Map & List | `app/templates.py` JS functions, pill filters, region pan, toast | M3 | DONE |
| M5 | Final Acceptance & Forensic Verification | All criteria verification, adversarial tests, auditor veto check | M1, M2, M3, M4 | DONE |

## Code Layout & Ownership
- `app/db.py`: Owned by M1 Worker
- `scripts/harvest_all_history.py`: Owned by M1 Worker
- `app/web.py`: Owned by M2 & M3 Workers
- `app/templates.py`: Owned by M4 Worker
- `app/data/pokemap.db`: Database file (migrated via M1)
