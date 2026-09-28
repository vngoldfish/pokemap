"""
Local SQLite Database Module for PokéMap.
Provides permanent storage and fast indexed access for:
- Regions (Osaka, Tokyo, Nagoya, All)
- Stores (~12,000 stores across all prefectures)
- Store History (Historical stock reports, notes, timestamps, onsite status)
"""

import sqlite3
import os
import json
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemap.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# JST timezone (Japan Standard Time: UTC+9)
JST = timezone(timedelta(hours=9))

# Module-level concurrency write lock for SQLite transactions
_db_write_lock = threading.Lock()

# In-memory query TTL cache for stores and report counts
_stores_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_report_counts_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 15.0  # seconds

def invalidate_stores_cache():
    """Invalidate in-memory cache for stores and report counts."""
    global _stores_cache, _report_counts_cache
    _stores_cache.clear()
    _report_counts_cache.clear()


_store_catalog_cache = None

def get_store_catalog() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of store metadata keyed by store ID from all cached stores_*.json files."""
    global _store_catalog_cache
    if _store_catalog_cache is None:
        _store_catalog_cache = {}
        pref_files = {
            "osaka": "stores_osaka.json",
            "tokyo": "stores_tokyo.json",
            "kanagawa": "stores_kanagawa.json",
            "chiba": "stores_chiba.json",
            "aichi": "stores_aichi.json",
            "gifu": "stores_gifu.json",
            "mie": "stores_mie.json"
        }
        for pref, fname in pref_files.items():
            fpath = os.path.join(DATA_DIR, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for s in json.load(f):
                            if s.get("id"):
                                s["pref"] = pref
                                _store_catalog_cache[s["id"]] = s
                except Exception:
                    pass
    return _store_catalog_cache


@contextmanager
def get_db_connection():
    """Create a thread-safe connection to the SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database tables and indexes."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Regions Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    default_city TEXT,
                    center_lat REAL,
                    center_lng REAL,
                    zoom INTEGER,
                    prefs_json TEXT
                );
            """)

            # 2. Stores Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    chain TEXT,
                    address TEXT,
                    lat REAL,
                    lng REAL,
                    pref TEXT NOT NULL,
                    city TEXT,
                    zip TEXT,
                    phone TEXT,
                    current_status TEXT DEFAULT 'u',
                    last_timestamp INTEGER DEFAULT 0,
                    last_reported_at TEXT,
                    onsite INTEGER DEFAULT 0,
                    packs_json TEXT,
                    updated_at INTEGER DEFAULT 0
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_pref ON stores(pref);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_chain ON stores(chain);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(current_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_ts ON stores(last_timestamp DESC);")

            # 3. Store History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS store_history (
                    id TEXT PRIMARY KEY,
                    store_id TEXT NOT NULL,
                    status_code TEXT NOT NULL,
                    status_label TEXT,
                    note TEXT,
                    packs_json TEXT,
                    user TEXT DEFAULT '匿名トレーナー',
                    who TEXT,
                    onsite INTEGER DEFAULT 0,
                    confirms INTEGER DEFAULT 1,
                    timestamp INTEGER NOT NULL,
                    formatted_time TEXT,
                    created_at INTEGER NOT NULL,
                    source TEXT DEFAULT 'poketan',
                    FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_store_ts ON store_history(store_id, timestamp DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_ts ON store_history(timestamp DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_status ON store_history(status_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_created_at ON store_history(created_at DESC);")

            # Auto-migration: ensure confirms column exists in store_history
            cursor.execute("PRAGMA table_info(store_history);")
            existing_cols = [r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in cursor.fetchall()]
            if "confirms" not in existing_cols:
                try:
                    cursor.execute("ALTER TABLE store_history ADD COLUMN confirms INTEGER DEFAULT 1;")
                except Exception:
                    pass

            # Auto-deduplication & Unique Index on (store_id, timestamp, status_code)
            try:
                cursor.execute("""
                    DELETE FROM store_history
                    WHERE id LIKE '%/_%/_%' ESCAPE '/'
                      AND EXISTS (
                          SELECT 1 FROM store_history h2
                          WHERE h2.store_id = store_history.store_id
                            AND h2.timestamp = store_history.timestamp
                            AND h2.status_code = store_history.status_code
                            AND h2.id NOT LIKE '%/_%/_%' ESCAPE '/'
                      );
                """)
                cursor.execute("""
                    DELETE FROM store_history
                    WHERE rowid NOT IN (
                        SELECT MIN(rowid)
                        FROM store_history
                        GROUP BY store_id, timestamp, status_code
                    );
                """)
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_hist_unique ON store_history(store_id, timestamp, status_code);")
                # Auto-migrate any historical records that erroneously received inflated created_at values
                cursor.execute("""
                    UPDATE store_history
                    SET created_at = timestamp
                    WHERE created_at > timestamp + 120 AND timestamp > 0;
                """)
                # Auto-clean any corrupted rows in store_history and stores
                cursor.execute("""
                    DELETE FROM store_history
                    WHERE typeof(timestamp) != 'integer' 
                       OR typeof(created_at) != 'integer'
                       OR timestamp <= 0;
                """)
                cursor.execute("""
                    DELETE FROM stores
                    WHERE typeof(last_timestamp) != 'integer' AND last_timestamp IS NOT NULL;
                """)
            except Exception as e:
                print("  [DB] Unique index setup note:", e)

            # Auto-sync stores current_status with the latest status in store_history
            try:
                cursor.execute("""
                    UPDATE stores
                    SET current_status = h.status_code,
                        last_timestamp = h.timestamp,
                        last_reported_at = h.formatted_time,
                        onsite = h.onsite,
                        packs_json = h.packs_json
                    FROM (
                        SELECT store_id, status_code, timestamp, formatted_time, onsite, packs_json,
                               ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY timestamp DESC) as rn
                        FROM store_history
                    ) h
                    WHERE stores.id = h.store_id AND h.rn = 1 AND (h.timestamp >= stores.last_timestamp OR stores.current_status = 'u');
                """)
            except Exception:
                pass

            # Ensure region definitions include tokyo and chiba
            try:
                cursor.execute("UPDATE regions SET prefs_json = ? WHERE id = 'tokyo';", (json.dumps(["tokyo", "kanagawa", "chiba"]),))
                cursor.execute("UPDATE regions SET prefs_json = ? WHERE id = 'all';", (json.dumps(["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]),))
            except Exception:
                pass

            # Check Tokyo stores and seed from stores_tokyo.json if count is 0
            try:
                cursor.execute("SELECT COUNT(*) FROM stores WHERE pref = 'tokyo';")
                if cursor.fetchone()[0] == 0:
                    tokyo_file = os.path.join(DATA_DIR, "stores_tokyo.json")
                    if os.path.exists(tokyo_file):
                        with open(tokyo_file, "r", encoding="utf-8") as f:
                            tokyo_stores = json.load(f)
                        now_ts = int(time.time())
                        tokyo_batch = []
                        for s in tokyo_stores:
                            sid = s.get("id")
                            if not sid:
                                continue
                            tokyo_batch.append((
                                sid,
                                s.get("name") or "Cửa hàng",
                                s.get("chain") or "",
                                s.get("address") or "",
                                s.get("lat"),
                                s.get("lng"),
                                "tokyo",
                                "u",
                                now_ts
                            ))
                        if tokyo_batch:
                            cursor.executemany("""
                                INSERT OR IGNORE INTO stores (id, name, chain, address, lat, lng, pref, current_status, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """, tokyo_batch)
                            # Also update any fallback placeholder stores that were previously miscategorized as osaka
                            cursor.executemany("""
                                UPDATE stores
                                SET name = ?, chain = ?, address = ?, lat = ?, lng = ?, pref = 'tokyo'
                                WHERE id = ? AND chain = 'other' AND pref = 'osaka';
                            """, [(row[1], row[2], row[3], row[4], row[5], row[0]) for row in tokyo_batch])
                            print(f"  [DB] Seeded {len(tokyo_batch)} Tokyo stores into SQLite.")
            except Exception as e:
                print("  [DB] Tokyo store seeding note:", e)

            conn.commit()
    print("  [DB] SQLite database initialized at:", DB_PATH)


def seed_regions_if_empty():
    """Populate default regions."""
    default_regions = [
        ("osaka", "大阪・関西 (Osaka & Lân cận)", "なんば", 34.6667, 135.5000, 13, json.dumps(["osaka"])),
        ("tokyo", "東京・神奈川・千葉 (Tokyo, Kanagawa, Chiba)", "横浜", 35.4500, 139.6300, 12, json.dumps(["tokyo", "kanagawa", "chiba"])),
        ("nagoya", "名古屋・東海 (Nagoya & Lân cận)", "名古屋", 35.1709, 136.8815, 12, json.dumps(["aichi", "gifu", "mie"])),
        ("all", "全エリア (Tất cả vùng / Toàn quốc)", "全エリア", 34.6937, 135.5023, 11, json.dumps(["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]))
    ]
    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM regions;")
            if cursor.fetchone()[0] == 0:
                cursor.executemany("""
                    INSERT OR REPLACE INTO regions (id, name, default_city, center_lat, center_lng, zoom, prefs_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, default_regions)
                conn.commit()
                print("  [DB] Seeded default regions into SQLite.")


def seed_stores_if_empty():
    """Seed stores from stores_*.json files into SQLite database and update any stores with placeholder metadata."""
    seed_regions_if_empty()
    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            pref_files = {
                "osaka": "stores_osaka.json",
                "tokyo": "stores_tokyo.json",
                "kanagawa": "stores_kanagawa.json",
                "chiba": "stores_chiba.json",
                "aichi": "stores_aichi.json",
                "gifu": "stores_gifu.json",
                "mie": "stores_mie.json"
            }

            now_ts = int(time.time())
            batch = []
            update_batch = []
            for pref, fname in pref_files.items():
                fpath = os.path.join(DATA_DIR, fname)
                if not os.path.exists(fpath):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        stores_list = json.load(f)
                    for s in stores_list:
                        sid = s.get("id")
                        if not sid:
                            continue
                        s_name = s.get("name") or "Cửa hàng"
                        s_chain = s.get("chain") or "other"
                        s_addr = s.get("address") or ""
                        s_lat = s.get("lat")
                        s_lng = s.get("lng")
                        batch.append((
                            sid,
                            s_name,
                            s_chain,
                            s_addr,
                            s_lat,
                            s_lng,
                            pref,
                            s.get("city") or "",
                            s.get("zip") or "",
                            s.get("phone") or "",
                            s.get("status") or "u",
                            0,
                            "",
                            0,
                            json.dumps([]),
                            now_ts
                        ))
                        update_batch.append((
                            s_name,
                            s_chain,
                            s_addr,
                            s_lat,
                            s_lng,
                            pref,
                            sid
                        ))
                except Exception as e:
                    print(f"  [DB] Error loading {fname}: {e}")

            if batch:
                cursor.executemany("""
                    INSERT OR IGNORE INTO stores (
                        id, name, chain, address, lat, lng, pref, city, zip, phone,
                        current_status, last_timestamp, last_reported_at, onsite, packs_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, batch)

                cursor.executemany("""
                    UPDATE stores
                    SET name = ?,
                        chain = ?,
                        address = ?,
                        lat = ?,
                        lng = ?,
                        pref = CASE WHEN pref IS NULL OR pref = '' THEN ? ELSE pref END
                    WHERE id = ? AND (name = id OR name = 'Cửa hàng' OR lat IS NULL);
                """, update_batch)
                conn.commit()
                invalidate_stores_cache()
            
            cursor.execute("SELECT COUNT(*) FROM stores;")
            total_count = cursor.fetchone()[0]
            return total_count


def backfill_all_poketan_statuses(force: bool = False) -> int:
    """
    Backfill all current & historical statuses from PokéTan Firestore into SQLite stores and store_history.
    If store_history already has >= 50 records and not force, skips backfill.
    """
    from .fetcher import fetch_firestore_document
    from .parser import parse_store_status

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM store_history;")
        existing_hist = cursor.fetchone()[0]
        if existing_hist >= 50 and not force:
            return existing_hist
        cursor.execute("SELECT id FROM stores;")
        existing_store_ids = set(r[0] for r in cursor.fetchall())

    print("  [DB] Backfilling store statuses and history from PokéTan Firestore...")
    prefs = ["osaka", "tokyo", "kanagawa", "aichi", "gifu", "mie"]
    now_ts = int(time.time())

    history_batch = []
    store_update_batch = []
    new_stores_map = {}

    for p in prefs:
        try:
            hot = fetch_firestore_document(f"status/{p}")
            cold = fetch_firestore_document(f"status/{p}_cold")
            # Cold first, hot overwrites cold so hot takes precedence
            merged = {**cold, **hot}
            for sid, raw in merged.items():
                if sid.endswith("_c"):
                    continue
                conf_raw = merged.get(f"{sid}_c")
                parsed = parse_store_status(str(raw), str(conf_raw) if conf_raw else None)
                if not parsed:
                    continue

                code = parsed.get("status_code") or "u"
                ts = parsed.get("timestamp") or 0
                onsite = bool(parsed.get("onsite", False))
                confirms = parsed.get("confirms") or 1
                packs = parsed.get("packs") or []
                rep_time = parsed.get("reported_at") or ""
                label = parsed.get("status_label") or ("🟢 Có hàng" if code == "i" else ("🔴 Hết hàng" if code == "o" else "🟡 Không bán thẻ"))
                hist_id = f"{sid}_{ts}_{code}"

                if sid not in existing_store_ids and sid not in new_stores_map:
                    catalog = get_store_catalog()
                    meta = catalog.get(sid) or {}
                    new_stores_map[sid] = (
                        sid,
                        meta.get("name") or sid,
                        meta.get("chain") or "other",
                        meta.get("address") or "",
                        meta.get("lat"),
                        meta.get("lng"),
                        meta.get("pref") or p,
                        code,
                        now_ts
                    )

                created_at_val = now_ts if (0 <= now_ts - ts <= 120) else (ts if ts > 0 else now_ts)

                history_batch.append((
                    hist_id,
                    sid,
                    code,
                    label,
                    "",
                    json.dumps(packs, ensure_ascii=False),
                    "匿名トレーナー",
                    "",
                    1 if onsite else 0,
                    confirms,
                    ts,
                    rep_time,
                    created_at_val,
                    "poketan"
                ))

                store_update_batch.append((
                    code,
                    ts, ts,
                    ts, rep_time,
                    ts, 1 if onsite else 0,
                    ts, json.dumps(packs, ensure_ascii=False),
                    now_ts,
                    sid
                ))
        except Exception as e:
            print(f"  [DB] Error backfilling pref {p}: {e}")

    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if new_stores_map:
                cursor.executemany("""
                    INSERT OR IGNORE INTO stores (id, name, chain, address, lat, lng, pref, current_status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, list(new_stores_map.values()))

            if history_batch:
                cursor.executemany("""
                    INSERT OR IGNORE INTO store_history (
                        id, store_id, status_code, status_label, note, packs_json,
                        user, who, onsite, confirms, timestamp, formatted_time, created_at, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, history_batch)

            if store_update_batch:
                cursor.executemany("""
                    UPDATE stores
                    SET current_status = ?,
                        last_timestamp = CASE WHEN ? > last_timestamp THEN ? ELSE last_timestamp END,
                        last_reported_at = CASE WHEN ? >= last_timestamp THEN ? ELSE last_reported_at END,
                        onsite = CASE WHEN ? >= last_timestamp THEN ? ELSE onsite END,
                        packs_json = CASE WHEN ? >= last_timestamp THEN ? ELSE packs_json END,
                        updated_at = ?
                    WHERE id = ?;
                """, store_update_batch)
            
            # Ensure stores table is always synced with newest record from store_history
            cursor.execute("""
                UPDATE stores
                SET current_status = h.status_code,
                    last_timestamp = h.timestamp,
                    last_reported_at = h.formatted_time,
                    onsite = h.onsite,
                    packs_json = h.packs_json
                FROM (
                    SELECT store_id, status_code, timestamp, formatted_time, onsite, packs_json,
                           ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY timestamp DESC) as rn
                    FROM store_history
                ) h
                WHERE stores.id = h.store_id AND h.rn = 1;
            """)
            conn.commit()

    invalidate_stores_cache()
    total_backfilled = len(history_batch)
    print(f"  [DB] Successfully backfilled {total_backfilled} statuses into SQLite store_history & stores!")
    return total_backfilled


def get_stores(region: Optional[str] = None, pref: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Query stores dictionary from SQLite database matching region or prefecture."""
    from .config import CHAIN_NAMES

    cache_key = f"{region}:{pref}"
    now_mono = time.monotonic()
    if cache_key in _stores_cache:
        cached_ts, cached_res = _stores_cache[cache_key]
        if now_mono - cached_ts < _CACHE_TTL:
            return cached_res

    target_prefs = []
    if pref:
        target_prefs = [pref.strip().lower()]
    elif region:
        r = region.strip().lower()
        if r == "osaka":
            target_prefs = ["osaka"]
        elif r == "tokyo":
            target_prefs = ["tokyo", "kanagawa", "chiba"]
        elif r == "kanagawa":
            target_prefs = ["kanagawa"]
        elif r == "chiba":
            target_prefs = ["chiba"]
        elif r == "nagoya" or r == "aichi":
            target_prefs = ["aichi", "gifu", "mie"]
        elif r == "all":
            target_prefs = ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]
    if not target_prefs:
        target_prefs = ["osaka"]

    placeholders = ",".join("?" for _ in target_prefs)
    sql = f"""
        SELECT id, name, chain, address, lat, lng, pref, city, zip, phone,
               current_status, last_timestamp, last_reported_at, onsite, packs_json
        FROM stores
        WHERE pref IN ({placeholders});
    """
    
    res = {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, target_prefs)
        rows = cursor.fetchall()
        for r in rows:
            sid = r["id"]
            packs = []
            try:
                if r["packs_json"]:
                    packs = json.loads(r["packs_json"])
            except Exception:
                packs = []

            chain_key = r["chain"] or "other"
            item = {
                "id": sid,
                "name": r["name"],
                "chain": chain_key,
                "chain_label": CHAIN_NAMES.get(chain_key, chain_key),
                "address": r["address"],
                "lat": r["lat"],
                "lng": r["lng"],
                "pref": r["pref"],
                "status": r["current_status"],
                "last_timestamp": r["last_timestamp"],
                "last_reported_at": r["last_reported_at"],
                "onsite": bool(r["onsite"]),
                "packs": packs
            }
            if r["city"]:
                item["city"] = r["city"]
            if r["zip"]:
                item["zip"] = r["zip"]
            if r["phone"]:
                item["phone"] = r["phone"]
            res[sid] = item

    _stores_cache[cache_key] = (now_mono, res)
    return res


def get_store_by_id(store_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single store by ID from SQLite."""
    from .config import CHAIN_NAMES
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, chain, address, lat, lng, pref, city, zip, phone,
                   current_status, last_timestamp, last_reported_at, onsite, packs_json
            FROM stores WHERE id = ?;
        """, (clean_id,))
        r = cursor.fetchone()
        if not r:
            return None
        packs = []
        try:
            if r["packs_json"]:
                packs = json.loads(r["packs_json"])
        except Exception:
            packs = []
        chain_key = r["chain"] or "other"
        return {
            "id": r["id"],
            "name": r["name"],
            "chain": chain_key,
            "chain_label": CHAIN_NAMES.get(chain_key, chain_key),
            "address": r["address"],
            "lat": r["lat"],
            "lng": r["lng"],
            "pref": r["pref"],
            "city": r["city"],
            "zip": r["zip"],
            "phone": r["phone"],
            "status": r["current_status"],
            "last_timestamp": r["last_timestamp"],
            "last_reported_at": r["last_reported_at"],
            "onsite": bool(r["onsite"]),
            "packs": packs
        }


def get_store_history(store_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve history reports for a store from SQLite database."""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, store_id, status_code, status_label, note, packs_json,
                   user, who, onsite, MAX(confirms) as confirms, timestamp, formatted_time, source
            FROM store_history
            WHERE store_id = ?
            GROUP BY timestamp, status_code
            ORDER BY timestamp DESC
            LIMIT ?;
        """, (clean_id, limit))
        rows = cursor.fetchall()
        history = []
        for r in rows:
            packs = []
            try:
                if r["packs_json"]:
                    packs = json.loads(r["packs_json"])
            except Exception:
                packs = []
            history.append({
                "id": r["id"],
                "store_id": r["store_id"],
                "status_code": r["status_code"],
                "status_label": r["status_label"],
                "note": r["note"] or "",
                "packs": packs,
                "user": r["user"] or "匿名トレーナー",
                "who": r["who"] or "",
                "onsite": bool(r["onsite"]),
                "confirms": r["confirms"] if ("confirms" in r.keys() and r["confirms"]) else 1,
                "timestamp": r["timestamp"],
                "formatted_time": r["formatted_time"] or "",
                "source": r["source"] or "poketan"
            })
        return history


_on_report_added_callbacks: List[Any] = []

def register_on_report_added(callback: Any) -> None:
    """
    Register an event hook to be triggered immediately whenever a brand-new report
    is added and committed into the SQLite CSDL database.
    Deduplicates by qualname to avoid duplicate registration.
    """
    cb_name = getattr(callback, "__qualname__", str(callback))
    existing_names = [getattr(cb, "__qualname__", str(cb)) for cb in _on_report_added_callbacks]
    if cb_name not in existing_names:
        _on_report_added_callbacks.append(callback)


def record_new_report(
    store_id: str,
    status_code: str,
    timestamp: int,
    onsite: bool = False,
    packs: Optional[List[str]] = None,
    note: str = "",
    user: str = "匿名トレーナー",
    who: str = "",
    formatted_time: Optional[str] = None,
    source: str = "poketan",
    confirms: int = 1,
    pref: str = "osaka",
    notify: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """
    Record a new report into SQLite store_history and update stores table.
    Ensures idempotency (no duplicate entries for the same store, timestamp, and status).
    Returns (is_new, report_dict).
    """
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    if not clean_id or not status_code or timestamp <= 0:
        return False, {}

    packs = packs or []
    status_labels = {
        "i": "🟢 Có hàng (在庫あり)",
        "o": "🔴 Hết hàng (売り切れ)",
        "n": "🟡 Không bán thẻ (扱ってない)",
        "u": "⚪ Chưa có tin (未確認)"
    }
    status_label = status_labels.get(status_code, "⚪ Chưa rõ")

    if not formatted_time:
        try:
            dt = datetime.fromtimestamp(timestamp, tz=JST)
            formatted_time = dt.strftime("%H:%M %d/%m/%Y")
        except Exception:
            formatted_time = ""

    hist_id = f"{clean_id}_{timestamp}_{status_code}"
    now_ts = int(time.time())
    # Only assign created_at = now_ts if the report was actually submitted within [-120s, +120s]
    created_at_val = now_ts if (abs(now_ts - timestamp) <= 120) else timestamp

    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already exists (by ID or by (store_id, timestamp, status_code))
            cursor.execute("""
                SELECT id FROM store_history 
                WHERE id = ? OR (store_id = ? AND timestamp = ? AND status_code = ?);
            """, (hist_id, clean_id, timestamp, status_code))
            existing_hist = cursor.fetchone()
            if existing_hist:
                return False, {"id": existing_hist["id"], "store_id": clean_id, "status_code": status_code, "timestamp": timestamp}

            # Ensure store exists in stores table to satisfy foreign key and has real metadata
            catalog = get_store_catalog()
            meta = catalog.get(clean_id) or {}
            st_name = meta.get("name") or clean_id
            st_chain = meta.get("chain") or "other"
            st_addr = meta.get("address") or ""
            st_lat = meta.get("lat")
            st_lng = meta.get("lng")
            st_pref = meta.get("pref") or pref

            cursor.execute("SELECT id, name FROM stores WHERE id = ?;", (clean_id,))
            st_row = cursor.fetchone()
            if not st_row:
                cursor.execute("""
                    INSERT OR IGNORE INTO stores (id, name, chain, address, lat, lng, pref, current_status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (clean_id, st_name, st_chain, st_addr, st_lat, st_lng, st_pref, status_code, now_ts))
            elif st_row[1] == clean_id or st_row[1] == "Cửa hàng":
                if meta:
                    cursor.execute("""
                        UPDATE stores
                        SET name = ?, chain = ?, address = ?, lat = ?, lng = ?, pref = ?
                        WHERE id = ?;
                    """, (st_name, st_chain, st_addr, st_lat, st_lng, st_pref, clean_id))

            # Insert new history item
            cursor.execute("""
                INSERT OR REPLACE INTO store_history (
                    id, store_id, status_code, status_label, note, packs_json,
                    user, who, onsite, confirms, timestamp, formatted_time, created_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                hist_id,
                clean_id,
                status_code,
                status_label,
                note,
                json.dumps(packs, ensure_ascii=False),
                user,
                who,
                1 if onsite else 0,
                confirms,
                timestamp,
                formatted_time,
                created_at_val,
                source
            ))

            # Update store current status and last timestamp
            cursor.execute("""
                UPDATE stores
                SET current_status = ?,
                    last_timestamp = CASE WHEN ? > last_timestamp THEN ? ELSE last_timestamp END,
                    last_reported_at = CASE WHEN ? >= last_timestamp THEN ? ELSE last_reported_at END,
                    onsite = CASE WHEN ? >= last_timestamp THEN ? ELSE onsite END,
                    packs_json = CASE WHEN ? >= last_timestamp THEN ? ELSE packs_json END,
                    updated_at = ?
                WHERE id = ?;
            """, (
                status_code,
                timestamp, timestamp,
                timestamp, formatted_time,
                timestamp, 1 if onsite else 0,
                timestamp, json.dumps(packs, ensure_ascii=False),
                now_ts,
                clean_id
            ))

            conn.commit()
            invalidate_stores_cache()

    entry = {
        "id": hist_id,
        "store_id": clean_id,
        "status_code": status_code,
        "status_label": status_label,
        "note": note,
        "packs": packs,
        "user": user,
        "who": who,
        "onsite": onsite,
        "confirms": confirms,
        "timestamp": timestamp,
        "formatted_time": formatted_time,
        "source": source
    }

    # Database Event: A brand-new report has been officially committed into SQLite CSDL!
    if notify and _on_report_added_callbacks:
        store_dict = {"id": clean_id, "name": clean_id, "pref": pref}
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM stores WHERE id = ?;", (clean_id,))
                s_row = cursor.fetchone()
                if s_row:
                    store_dict = dict(s_row)
        except Exception:
            pass

        for cb in list(_on_report_added_callbacks):
            try:
                cb(store_dict, entry)
            except Exception as cb_err:
                print(f"  [CSDL Event Error] Failed executing callback: {cb_err}")

    return True, entry


def save_bulk_history(store_id: str, history_list: List[Dict[str, Any]], source: str = "poketan", pref: str = "osaka") -> int:
    """Save a list of history reports fetched from PokéTan into SQLite store_history."""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    if not clean_id or not history_list:
        return 0

    now_ts = int(time.time())
    batch = []
    for item in history_list:
        ts = item.get("timestamp") or 0
        status_code = item.get("status_code") or item.get("status") or "u"
        if len(status_code) > 1 and status_code in ["in-stock", "i"]:
            status_code = "i"
        elif len(status_code) > 1 and status_code in ["out-of-stock", "o"]:
            status_code = "o"
        elif len(status_code) > 1 and status_code in ["not-handled", "none", "n"]:
            status_code = "n"

        hist_id = item.get("id") or f"{clean_id}_{ts}_{status_code}"
        packs = item.get("packs") or []
        confirms = max(1, int(item.get("confirms") or 1))
        formatted_time = ""
        if ts > 0:
            try:
                dt = datetime.fromtimestamp(ts, tz=JST)
                formatted_time = dt.strftime("%H:%M %d/%m/%Y")
            except Exception:
                formatted_time = item.get("formatted_time") or ""

        hist_created_at = ts if ts > 0 else now_ts

        batch.append((
            hist_id,
            clean_id,
            status_code,
            item.get("status_label") or ("🟢 Có hàng" if status_code == "i" else ("🔴 Hết hàng" if status_code == "o" else "⚪ Không bán thẻ")),
            item.get("note") or "",
            json.dumps(packs, ensure_ascii=False),
            item.get("user") or "匿名トレーナー",
            item.get("who") or "",
            1 if item.get("onsite") else 0,
            confirms,
            ts,
            formatted_time,
            hist_created_at,
            source
        ))

    if not batch:
        return 0

    # Deduplicate batch by (clean_id, timestamp, status_code)
    deduped_batch_map = {}
    for row in batch:
        key = (row[1], row[10], row[2])  # (clean_id, timestamp, status_code)
        if key not in deduped_batch_map or not row[0].startswith(f"{row[1]}_"):
            deduped_batch_map[key] = row
    batch = list(deduped_batch_map.values())

    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            catalog = get_store_catalog()
            meta = catalog.get(clean_id) or {}
            st_name = meta.get("name") or clean_id
            st_chain = meta.get("chain") or "other"
            st_addr = meta.get("address") or ""
            st_lat = meta.get("lat")
            st_lng = meta.get("lng")
            st_pref = meta.get("pref") or pref

            cursor.execute("SELECT id, name FROM stores WHERE id = ?;", (clean_id,))
            st_row = cursor.fetchone()
            if not st_row:
                cursor.execute("""
                    INSERT OR IGNORE INTO stores (id, name, chain, address, lat, lng, pref, current_status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'u', ?);
                """, (clean_id, st_name, st_chain, st_addr, st_lat, st_lng, st_pref, now_ts))
            elif st_row[1] == clean_id or st_row[1] == "Cửa hàng":
                if meta:
                    cursor.execute("""
                        UPDATE stores
                        SET name = ?, chain = ?, address = ?, lat = ?, lng = ?, pref = ?
                        WHERE id = ?;
                    """, (st_name, st_chain, st_addr, st_lat, st_lng, st_pref, clean_id))

            # Clean up any existing synthetic stub row or old row with same (store_id, timestamp, status_code)
            for item_row in batch:
                h_id = item_row[0]
                s_id = item_row[1]
                s_code = item_row[2]
                s_ts = item_row[10]
                if s_ts > 0:
                    stub_id = f"{s_id}_{s_ts}_{s_code}"
                    cursor.execute("""
                        DELETE FROM store_history
                        WHERE store_id = ? AND (timestamp = ? OR id = ?) AND status_code = ? AND id != ?;
                    """, (s_id, s_ts, stub_id, s_code, h_id))

            cursor.executemany("""
                INSERT OR REPLACE INTO store_history (
                    id, store_id, status_code, status_label, note, packs_json,
                    user, who, onsite, confirms, timestamp, formatted_time, created_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, batch)

            # Update store current_status with newest history report if available
            sorted_history = sorted(history_list, key=lambda x: x.get("timestamp") or 0, reverse=True)
            if sorted_history:
                newest = sorted_history[0]
                newest_ts = newest.get("timestamp") or 0
                newest_code = newest.get("status_code") or newest.get("status") or "u"
                if len(newest_code) > 1 and newest_code in ["in-stock", "i"]:
                    newest_code = "i"
                elif len(newest_code) > 1 and newest_code in ["out-of-stock", "o"]:
                    newest_code = "o"
                elif len(newest_code) > 1 and newest_code in ["not-handled", "none", "n"]:
                    newest_code = "n"

                newest_formatted = newest.get("formatted_time") or ""
                if newest_ts > 0 and not newest_formatted:
                    try:
                        dt = datetime.fromtimestamp(newest_ts, tz=JST)
                        newest_formatted = dt.strftime("%H:%M %d/%m/%Y")
                    except Exception:
                        pass

                newest_onsite = 1 if newest.get("onsite") else 0
                newest_packs = json.dumps(newest.get("packs") or [], ensure_ascii=False)

                cursor.execute("""
                    UPDATE stores
                    SET current_status = CASE WHEN (? >= last_timestamp OR current_status = 'u') THEN ? ELSE current_status END,
                        last_timestamp = CASE WHEN ? > last_timestamp THEN ? ELSE last_timestamp END,
                        last_reported_at = CASE WHEN ? >= last_timestamp THEN ? ELSE last_reported_at END,
                        onsite = CASE WHEN ? >= last_timestamp THEN ? ELSE onsite END,
                        packs_json = CASE WHEN ? >= last_timestamp THEN ? ELSE packs_json END,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    newest_ts, newest_code,
                    newest_ts, newest_ts,
                    newest_ts, newest_formatted,
                    newest_ts, newest_onsite,
                    newest_ts, newest_packs,
                    now_ts,
                    clean_id
                ))

            conn.commit()
            invalidate_stores_cache()
    return len(batch)


def get_report_counts(region: Optional[str] = None, pref: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """
    Calculate number of in-stock and out-of-stock reports per store using fast SQL aggregation.
    Returns: { store_id: { "in": int, "out": int } }
    """
    cache_key = f"{region}:{pref}"
    now_mono = time.monotonic()
    if cache_key in _report_counts_cache:
        cached_ts, cached_res = _report_counts_cache[cache_key]
        if now_mono - cached_ts < _CACHE_TTL:
            return cached_res

    target_prefs = []
    if pref:
        target_prefs = [pref.strip().lower()]
    elif region:
        r = region.strip().lower()
        if r == "osaka":
            target_prefs = ["osaka"]
        elif r == "tokyo":
            target_prefs = ["tokyo", "kanagawa", "chiba"]
        elif r == "kanagawa":
            target_prefs = ["kanagawa"]
        elif r == "chiba":
            target_prefs = ["chiba"]
        elif r == "nagoya" or r == "aichi":
            target_prefs = ["aichi", "gifu", "mie"]
        elif r == "all":
            target_prefs = ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_prefs:
            placeholders = ",".join("?" for _ in target_prefs)
            cursor.execute(f"""
                SELECT h.store_id,
                       COUNT(DISTINCT CASE WHEN h.status_code = 'i' THEN h.timestamp END) as count_in,
                       COUNT(DISTINCT CASE WHEN h.status_code = 'o' THEN h.timestamp END) as count_out
                FROM store_history h
                INNER JOIN stores s ON h.store_id = s.id
                WHERE s.pref IN ({placeholders})
                GROUP BY h.store_id;
            """, target_prefs)
        else:
            cursor.execute("""
                SELECT store_id,
                       COUNT(DISTINCT CASE WHEN status_code = 'i' THEN timestamp END) as count_in,
                       COUNT(DISTINCT CASE WHEN status_code = 'o' THEN timestamp END) as count_out
                FROM store_history
                GROUP BY store_id;
            """)
        rows = cursor.fetchall()
        counts = {}
        for r in rows:
            counts[r["store_id"]] = {
                "in": r["count_in"] or 0,
                "out": r["count_out"] or 0
            }
        _report_counts_cache[cache_key] = (now_mono, counts)
        return counts


def get_store_restock_analytics(store_id: str) -> Dict[str, Any]:
    """
    Calculate restock patterns for a specific store:
    - Hourly in-stock distribution (which hours of the day does restock occur)
    - Weekday in-stock distribution (which days of week do restocks drop)
    - In-stock probability / success rate
    - Peak restock hours & days
    """
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Total counts
        cursor.execute("""
            SELECT 
                COUNT(*) as total_reports,
                SUM(CASE WHEN status_code = 'i' THEN 1 ELSE 0 END) as in_count,
                SUM(CASE WHEN status_code = 'o' THEN 1 ELSE 0 END) as out_count,
                SUM(CASE WHEN status_code = 'n' THEN 1 ELSE 0 END) as none_count,
                MIN(timestamp) as min_ts,
                MAX(CASE WHEN status_code = 'i' THEN timestamp ELSE 0 END) as last_in_ts
            FROM store_history
            WHERE store_id = ?;
        """, (clean_id,))
        summary_row = cursor.fetchone()
        
        total_reports = summary_row["total_reports"] or 0
        in_count = summary_row["in_count"] or 0
        out_count = summary_row["out_count"] or 0
        last_in_ts = summary_row["last_in_ts"] or 0
        in_stock_rate = round((in_count / total_reports * 100), 1) if total_reports > 0 else 0.0

        # 2. Hourly distribution (JST = UTC+9)
        cursor.execute("""
            SELECT 
                strftime('%H', datetime(timestamp, 'unixepoch', '+9 hours')) as hr,
                COUNT(*) as cnt
            FROM store_history
            WHERE store_id = ? AND status_code = 'i'
            GROUP BY hr
            ORDER BY cnt DESC;
        """, (clean_id,))
        hourly_rows = cursor.fetchall()
        hourly_dict = {f"{h:02d}": 0 for h in range(24)}
        for r in hourly_rows:
            hr_str = r["hr"]
            if hr_str in hourly_dict:
                hourly_dict[hr_str] = r["cnt"]

        peak_hours = []
        for r in hourly_rows[:3]:
            h_int = int(r["hr"])
            pct = round(r["cnt"] / in_count * 100) if in_count > 0 else 0
            peak_hours.append(f"{h_int:02d}:00 - {h_int+1:02d}:00 ({pct}%)")

        # 3. Weekday distribution (0=CN, 1=T2, ..., 6=T7)
        weekday_names = {
            "0": "Chủ Nhật (CN)",
            "1": "Thứ Hai (T2)",
            "2": "Thứ Ba (T3)",
            "3": "Thứ Tư (T4)",
            "4": "Thứ Năm (T5)",
            "5": "Thứ Sáu (T6)",
            "6": "Thứ Bảy (T7)"
        }
        cursor.execute("""
            SELECT 
                strftime('%w', datetime(timestamp, 'unixepoch', '+9 hours')) as wd,
                COUNT(*) as cnt
            FROM store_history
            WHERE store_id = ? AND status_code = 'i'
            GROUP BY wd
            ORDER BY cnt DESC;
        """, (clean_id,))
        weekday_rows = cursor.fetchall()
        weekday_dict = {w: 0 for w in ["1", "2", "3", "4", "5", "6", "0"]}
        for r in weekday_rows:
            wd_str = r["wd"]
            if wd_str in weekday_dict:
                weekday_dict[wd_str] = r["cnt"]

        peak_weekdays = []
        for r in weekday_rows[:3]:
            name = weekday_names.get(r["wd"], r["wd"])
            pct = round(r["cnt"] / in_count * 100) if in_count > 0 else 0
            peak_weekdays.append(f"{name} ({pct}%)")

        # 4. Common packs
        cursor.execute("""
            SELECT packs_json
            FROM store_history
            WHERE store_id = ? AND status_code = 'i' AND packs_json != '[]' AND packs_json IS NOT NULL;
        """, (clean_id,))
        pack_counts = {}
        for r in cursor.fetchall():
            try:
                pk_list = json.loads(r["packs_json"])
                for p in pk_list:
                    pack_counts[p] = pack_counts.get(p, 0) + 1
            except Exception:
                pass
        top_packs = sorted(pack_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_packs_list = [f"{p[0]} ({p[1]} lần)" for p in top_packs]

        return {
            "store_id": clean_id,
            "total_reports": total_reports,
            "in_stock_reports": in_count,
            "out_of_stock_reports": out_count,
            "in_stock_rate_pct": in_stock_rate,
            "last_in_stock_time": datetime.fromtimestamp(last_in_ts, tz=JST).strftime("%H:%M %d/%m/%Y") if last_in_ts else "Chưa có",
            "peak_hours": peak_hours,
            "peak_weekdays": peak_weekdays,
            "hourly_distribution": [{"hour": h, "count": cnt} for h, cnt in sorted(hourly_dict.items())],
            "weekday_distribution": [{"day": weekday_names[w], "day_num": int(w), "count": cnt} for w, cnt in weekday_dict.items()],
            "top_packs": top_packs_list
        }


def get_recent_reports(since_created_at: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve the most recent reports stored in SQLite store_history created after since_created_at."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if since_created_at > 0:
            cursor.execute("""
                SELECT h.id, h.store_id, h.status_code, h.status_label, h.note, h.packs_json,
                       h.user, h.who, h.onsite, h.confirms, h.timestamp, h.formatted_time, h.created_at, h.source,
                       s.name as store_name, s.chain, s.lat, s.lng, s.address, s.pref
                FROM store_history h
                LEFT JOIN stores s ON h.store_id = s.id
                WHERE h.created_at > ?
                ORDER BY h.timestamp DESC, h.created_at DESC
                LIMIT ?;
            """, (since_created_at, limit))
        else:
            cursor.execute("""
                SELECT h.id, h.store_id, h.status_code, h.status_label, h.note, h.packs_json,
                       h.user, h.who, h.onsite, h.confirms, h.timestamp, h.formatted_time, h.created_at, h.source,
                       s.name as store_name, s.chain, s.lat, s.lng, s.address, s.pref
                FROM store_history h
                LEFT JOIN stores s ON h.store_id = s.id
                ORDER BY h.timestamp DESC, h.created_at DESC
                LIMIT ?;
            """, (limit,))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            packs = []
            try:
                if r["packs_json"]:
                    packs = json.loads(r["packs_json"])
            except Exception:
                packs = []
            results.append({
                "id": r["id"],
                "store_id": r["store_id"],
                "store_name": r["store_name"] or r["store_id"],
                "chain": r["chain"] or "other",
                "lat": r["lat"],
                "lng": r["lng"],
                "address": r["address"] or "",
                "pref": r["pref"] or "osaka",
                "status_code": r["status_code"],
                "status_label": r["status_label"],
                "note": r["note"] or "",
                "packs": packs,
                "onsite": bool(r["onsite"]),
                "confirms": r["confirms"] if ("confirms" in r.keys() and r["confirms"]) else 1,
                "timestamp": r["timestamp"],
                "formatted_time": r["formatted_time"] or "",
                "created_at": r["created_at"],
                "source": r["source"] or "poketan"
            })
        return results


def db_get_stats_overview() -> Dict[str, Any]:
    """Retrieve comprehensive system statistics and KPI metrics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stores;")
        total_stores = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM store_history;")
        total_reports = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT store_id) FROM store_history;")
        active_stores = cursor.fetchone()[0]

        cursor.execute("SELECT current_status, COUNT(*) FROM stores GROUP BY current_status;")
        by_status = dict(cursor.fetchall())

        cursor.execute("""
            SELECT s.pref, COUNT(h.id) 
            FROM store_history h 
            JOIN stores s ON h.store_id = s.id 
            GROUP BY s.pref 
            ORDER BY COUNT(h.id) DESC;
        """)
        by_pref = [{"pref": r[0] or "other", "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT s.chain, COUNT(h.id) 
            FROM store_history h 
            JOIN stores s ON h.store_id = s.id 
            GROUP BY s.chain 
            ORDER BY COUNT(h.id) DESC 
            LIMIT 12;
        """)
        by_chain = [{"chain": r[0] or "other", "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT ((timestamp + 32400) % 86400) / 3600 as jst_hour,
                   COUNT(*) as total,
                   SUM(CASE WHEN status_code = 'i' THEN 1 ELSE 0 END) as in_stock
            FROM store_history
            WHERE timestamp > 0
            GROUP BY jst_hour
            ORDER BY jst_hour;
        """)
        by_hour = [{"hour": r[0], "total": r[1], "in_stock": r[2] or 0} for r in cursor.fetchall()]

        cursor.execute("SELECT packs_json FROM store_history WHERE packs_json IS NOT NULL AND packs_json != '[]' LIMIT 3000;")
        pack_counter = Counter()
        for row in cursor.fetchall():
            try:
                p_list = json.loads(row[0])
                for p in p_list:
                    pack_counter[p] += 1
            except Exception:
                pass
        top_packs = [{"pack": k, "count": v} for k, v in pack_counter.most_common(8)]

        cursor.execute("SELECT MAX(timestamp), MAX(formatted_time) FROM store_history;")
        latest_row = cursor.fetchone()
        latest_ts = latest_row[0] if latest_row else 0
        latest_time_str = latest_row[1] if latest_row else ""

        return {
            "total_stores": total_stores,
            "total_reports": total_reports,
            "active_stores": active_stores,
            "in_stock_now": by_status.get("i", 0),
            "out_of_stock_now": by_status.get("o", 0),
            "not_handled_now": by_status.get("n", 0),
            "unknown_now": by_status.get("u", 0),
            "by_pref": by_pref,
            "by_chain": by_chain,
            "by_hour": by_hour,
            "top_packs": top_packs,
            "latest_timestamp": latest_ts,
            "latest_formatted_time": latest_time_str
        }


def db_get_leaderboard(pref: Optional[str] = None, chain: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve top stores with the most report activity."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clauses = ["1=1"]
        params = []
        if pref:
            where_clauses.append("s.pref = ?")
            params.append(pref.strip().lower())
        if chain:
            where_clauses.append("s.chain = ?")
            params.append(chain.strip().lower())

        where_sql = " AND ".join(where_clauses)
        cursor.execute(f"""
            SELECT s.id, s.name, s.pref, s.chain, s.address, s.lat, s.lng, s.current_status,
                   COUNT(h.id) as total_reports,
                   SUM(CASE WHEN h.status_code = 'i' THEN 1 ELSE 0 END) as in_count,
                   SUM(CASE WHEN h.status_code = 'o' THEN 1 ELSE 0 END) as out_count,
                   MAX(h.timestamp) as last_ts,
                   MAX(h.formatted_time) as last_rep_time
            FROM store_history h
            JOIN stores s ON h.store_id = s.id
            WHERE {where_sql}
            GROUP BY s.id
            ORDER BY total_reports DESC, last_ts DESC
            LIMIT ?;
        """, params + [limit])
        rows = cursor.fetchall()
        leaderboard = []
        for r in rows:
            tot = r["total_reports"] or 0
            inc = r["in_count"] or 0
            leaderboard.append({
                "id": r["id"],
                "name": r["name"] or r["id"],
                "pref": r["pref"] or "",
                "chain": r["chain"] or "other",
                "address": r["address"] or "",
                "lat": r["lat"],
                "lng": r["lng"],
                "current_status": r["current_status"] or "u",
                "total_reports": tot,
                "in_count": inc,
                "out_count": r["out_count"] or 0,
                "in_rate": round((inc / tot * 100), 1) if tot > 0 else 0,
                "last_timestamp": r["last_ts"] or 0,
                "last_reported_at": r["last_rep_time"] or ""
            })
        return leaderboard


def db_search_history_logs(
    q: str = "",
    pref: str = "",
    chain: str = "",
    status: str = "",
    page: int = 1,
    limit: int = 30
) -> Dict[str, Any]:
    """Retrieve paginated store history reports with multi-criteria filters."""
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clauses = ["1=1"]
        params = []
        if q:
            clean_q = q.strip()
            where_clauses.append("(s.name LIKE ? OR s.address LIKE ? OR h.store_id LIKE ? OR h.note LIKE ?)")
            pattern = f"%{clean_q}%"
            params.extend([pattern, pattern, pattern, pattern])
        if pref:
            where_clauses.append("s.pref = ?")
            params.append(pref.strip().lower())
        if chain:
            where_clauses.append("s.chain = ?")
            params.append(chain.strip().lower())
        if status:
            where_clauses.append("h.status_code = ?")
            params.append(status.strip().lower())

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM store_history h 
            LEFT JOIN stores s ON h.store_id = s.id 
            WHERE {where_sql};
        """, params)
        total_items = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT h.id, h.store_id, s.name, s.pref, s.chain, s.address, s.lat, s.lng,
                   h.status_code, h.status_label, h.note, h.packs_json,
                   h.user, h.who, h.onsite, h.confirms, h.timestamp, h.formatted_time, h.source
            FROM store_history h
            LEFT JOIN stores s ON h.store_id = s.id
            WHERE {where_sql}
            ORDER BY h.timestamp DESC
            LIMIT ? OFFSET ?;
        """, params + [limit, offset])
        rows = cursor.fetchall()

        items = []
        for r in rows:
            packs = []
            try:
                if r["packs_json"]:
                    packs = json.loads(r["packs_json"])
            except Exception:
                packs = []
            items.append({
                "id": r["id"],
                "store_id": r["store_id"],
                "name": r["name"] or r["store_id"],
                "pref": r["pref"] or "",
                "chain": r["chain"] or "other",
                "address": r["address"] or "",
                "lat": r["lat"],
                "lng": r["lng"],
                "status_code": r["status_code"] or "u",
                "status_label": r["status_label"] or "",
                "note": r["note"] or "",
                "packs": packs,
                "user": r["user"] or "匿名トレーナー",
                "who": r["who"] or "",
                "onsite": bool(r["onsite"]),
                "confirms": r["confirms"] or 1,
                "timestamp": r["timestamp"] or 0,
                "formatted_time": r["formatted_time"] or "",
                "source": r["source"] or "poketan"
            })

        return {
            "total": total_items,
            "page": page,
            "limit": limit,
            "total_pages": (total_items + limit - 1) // limit if total_items > 0 else 1,
            "items": items
        }


