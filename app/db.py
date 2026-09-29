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
import math
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
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
_predictions_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 15.0  # seconds
_PRED_CACHE_TTL = 30.0  # seconds

def invalidate_stores_cache():
    """Invalidate in-memory cache for stores, report counts, and predictions."""
    global _stores_cache, _report_counts_cache, _predictions_cache
    _stores_cache.clear()
    _report_counts_cache.clear()
    _predictions_cache.clear()


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


def _calc_haversine_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in kilometers."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    return 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


CHAIN_LOGISTICS_PROFILES = {
    "seven": {
        "name": "7-Eleven",
        "peak_hours": [11, 12, 13, 21, 22],
        "peak_window": "11:00 - 13:30 & 21:00 - 22:30 JST",
        "dow_peak": [4, 5],
        "base_cycle_days": 2.5,
        "desc": "Chuyến trưa (11:00-13:30) & đêm (21:00-22:30)"
    },
    "lawson": {
        "name": "Lawson",
        "peak_hours": [7, 8, 9, 17, 18],
        "peak_window": "07:30 - 09:30 & 17:00 - 18:30 JST",
        "dow_peak": [4, 5],
        "base_cycle_days": 3.0,
        "desc": "Chuyến sáng (07:30-09:30) & chiều (17:00-18:30)"
    },
    "familymart": {
        "name": "FamilyMart",
        "peak_hours": [9, 10, 15, 16],
        "peak_window": "09:00 - 10:30 & 15:30 - 17:00 JST",
        "dow_peak": [3, 4],
        "base_cycle_days": 3.0,
        "desc": "Chuyến sáng (09:00-10:30) & xế chiều (15:30-17:00)"
    },
    "ministop": {
        "name": "Ministop",
        "peak_hours": [10, 11, 14, 15],
        "peak_window": "10:00 - 12:00 & 14:00 - 15:30 JST",
        "dow_peak": [4],
        "base_cycle_days": 3.5,
        "desc": "Chuyến trưa (10:00-12:00)"
    },
    "specialty": {
        "name": "Shop thẻ bài / PokéCenter",
        "peak_hours": [11, 12, 15, 16, 17],
        "peak_window": "11:00 - 12:00 & 15:00 - 17:00 JST",
        "dow_peak": [4, 5, 6],
        "base_cycle_days": 2.0,
        "desc": "Mở cửa (11:00-12:00) & xả hàng chiều (15:00-17:00)"
    },
    "electronics": {
        "name": "GEO / Đồ điện máy / Đồ chơi",
        "peak_hours": [10, 11, 14],
        "peak_window": "10:00 - 11:30 JST",
        "dow_peak": [4, 5],
        "base_cycle_days": 4.0,
        "desc": "Mở cửa sáng (10:00-11:30)"
    },
    "default": {
        "name": "Cửa hàng bán lẻ",
        "peak_hours": [10, 11, 14, 15, 16],
        "peak_window": "10:00 - 12:00 & 14:00 - 16:30 JST",
        "dow_peak": [4, 5],
        "base_cycle_days": 3.0,
        "desc": "Khung giờ restock thông thường"
    }
}


def get_chain_logistics_profile(chain_code: str) -> Dict[str, Any]:
    c = (chain_code or "").strip().lower()
    if c in CHAIN_LOGISTICS_PROFILES:
        return CHAIN_LOGISTICS_PROFILES[c]
    if c in ("geo", "joshin", "yamada", "biccamera", "yodobashi", "edion", "ks", "toysrus", "aeon", "piagu", "apita", "tsutaya"):
        return CHAIN_LOGISTICS_PROFILES["electronics"]
    return CHAIN_LOGISTICS_PROFILES["default"]


def db_get_restock_predictions(
    pref: Optional[str] = None,
    chain: Optional[str] = None,
    target_hour: Optional[int] = None,
    time_window: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    max_dist_km: Optional[float] = None,
    min_score: int = 40,
    limit: int = 60,
    sort_by: str = "score",
    status_filter: Optional[str] = "all"
) -> Dict[str, Any]:
    """
    Predict stores most likely to have stock or restock today in upcoming/selected hours.
    Based on historical in-stock distribution, day-of-week affinity, restock turnaround cycles,
    current stock status, and GPS proximity.
    """
    global _predictions_cache
    from .config import CHAIN_NAMES

    # Normalize parameters
    clean_pref = (pref or "").strip().lower()
    clean_chain = (chain or "").strip().lower()
    clean_window = (time_window or "").strip().lower()
    clean_status = (status_filter or "all").strip().lower()
    if clean_pref in ("all", "", "tatca"):
        clean_pref = None
    if clean_chain in ("all", "", "tatca"):
        clean_chain = None
    if target_hour is not None and (target_hour < 0 or target_hour > 23):
        target_hour = None

    cache_key = f"{clean_pref}_{clean_chain}_{target_hour}_{clean_window}_{user_lat}_{user_lng}_{max_dist_km}_{min_score}_{limit}_{sort_by}_{clean_status}"
    now_ts = int(time.time())

    if cache_key in _predictions_cache:
        cached_ts, cached_data = _predictions_cache[cache_key]
        if now_ts - cached_ts < _PRED_CACHE_TTL:
            return cached_data

    now_dt = datetime.fromtimestamp(now_ts, tz=JST)
    current_dow = now_dt.weekday()  # 0 = Monday, 1 = Tuesday...
    current_hour = now_dt.hour
    dow_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    dow_jp_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

    # 1. Fetch historical in-stock records
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clauses = ["h.timestamp > 0", "h.status_code = 'i'"]
        params = []

        if clean_pref:
            where_clauses.append("s.pref = ?")
            params.append(clean_pref)
        if clean_chain:
            where_clauses.append("s.chain = ?")
            params.append(clean_chain)

        where_sql = " AND ".join(where_clauses)
        cursor.execute(f"""
            SELECT h.store_id, h.timestamp, h.packs_json,
                   s.name, s.pref, s.chain, s.address, s.lat, s.lng, s.current_status
            FROM store_history h
            JOIN stores s ON h.store_id = s.id
            WHERE {where_sql}
            ORDER BY h.timestamp ASC;
        """, params)
        rows = cursor.fetchall()

        # 1b. Fetch stores reported within last 30 minutes (1800 seconds)
        recent_where = ["s.last_timestamp > 0", "(? - s.last_timestamp) <= 1800"]
        recent_params = [now_ts]
        if clean_pref:
            recent_where.append("s.pref = ?")
            recent_params.append(clean_pref)
        if clean_chain:
            recent_where.append("s.chain = ?")
            recent_params.append(clean_chain)

        cursor.execute(f"""
            SELECT s.id, s.name, s.pref, s.chain, s.address, s.lat, s.lng,
                   s.current_status, s.last_timestamp, s.last_reported_at, s.packs_json
            FROM stores s
            WHERE {" AND ".join(recent_where)};
        """, recent_params)
        recent_30m_rows = cursor.fetchall()
        recent_30m_map = {r["id"]: r for r in recent_30m_rows}

        # 1c. Fetch active in-stock stores reported within last 60 minutes (3600 seconds)
        # for Truck Route Ripple detection (logistics trucks delivering to nearby stores of same chain)
        truck_where = [
            "s.last_timestamp > 0",
            "(? - s.last_timestamp) <= 3600",
            "s.current_status = 'i'",
            "s.lat IS NOT NULL",
            "s.lng IS NOT NULL"
        ]
        truck_params = [now_ts]
        if clean_pref:
            truck_where.append("s.pref = ?")
            truck_params.append(clean_pref)

        cursor.execute(f"""
            SELECT s.id, s.name, s.pref, s.chain, s.lat, s.lng, s.last_timestamp
            FROM stores s
            WHERE {" AND ".join(truck_where)};
        """, truck_params)
        active_truck_sources = cursor.fetchall()

    # 2. Aggregate store data and calculate 24h restock distribution
    stores_data = defaultdict(lambda: {
        "timestamps": [],
        "packs": [],
        "name": "",
        "pref": "",
        "chain": "",
        "address": "",
        "lat": None,
        "lng": None,
        "current_status": "u",
        "last_timestamp": 0
    })
    hourly_distribution = [0] * 24

    for sid, ts, packs_json, name, spref, schain, addr, lat, lng, st in rows:
        jst_h = (ts + 32400) % 86400 // 3600
        hourly_distribution[jst_h] += 1
        d = stores_data[sid]
        d["name"] = name or sid
        d["pref"] = spref or ""
        d["chain"] = schain or "other"
        d["address"] = addr or ""
        d["lat"] = lat
        d["lng"] = lng
        d["current_status"] = st or "u"
        d["timestamps"].append(ts)
        if packs_json:
            try:
                p_list = json.loads(packs_json)
                if isinstance(p_list, list):
                    d["packs"].extend(p_list)
            except Exception:
                pass

    # Merge recent 30m stores that might not have historical 'i'
    for sid, r in recent_30m_map.items():
        if sid not in stores_data:
            d = stores_data[sid]
            d["name"] = r["name"] or sid
            d["pref"] = r["pref"] or ""
            d["chain"] = r["chain"] or "other"
            d["address"] = r["address"] or ""
            d["lat"] = r["lat"]
            d["lng"] = r["lng"]
            d["current_status"] = r["current_status"] or "u"
            d["last_timestamp"] = r["last_timestamp"] or 0
            if r["packs_json"]:
                try:
                    p_list = json.loads(r["packs_json"])
                    if isinstance(p_list, list):
                        d["packs"].extend(p_list)
                except Exception:
                    pass

    # 3. Radius-specific calculations if user location and max_dist_km are specified
    radius_stats = {
        "is_active": False,
        "radius_km": round(max_dist_km, 1) if max_dist_km else None,
        "total_stores": 0,
        "in_stock_now": 0,
        "in_stock_rate": 0.0,
        "ever_restocked": 0,
        "ever_restocked_rate": 0.0,
        "peak_hour": None,
        "peak_hour_count": 0,
        "peak_window": "",
        "prime_stores_today": 0
    }

    if user_lat is not None and user_lng is not None and max_dist_km is not None and max_dist_km > 0:
        dlat = (max_dist_km + 0.5) / 111.0
        dlng = (max_dist_km + 0.5) / (111.0 * max(0.01, math.cos(math.radians(user_lat))))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, lat, lng, current_status
                FROM stores
                WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?;
            """, (user_lat - dlat, user_lat + dlat, user_lng - dlng, user_lng + dlng))
            box_stores = cursor.fetchall()

            stores_in_radius = []
            for s in box_stores:
                dist = _calc_haversine_dist(user_lat, user_lng, s["lat"], s["lng"])
                if dist <= max_dist_km:
                    stores_in_radius.append(s)

            radius_store_ids = set(s["id"] for s in stores_in_radius)
            total_in_radius = len(stores_in_radius)
            in_stock_now_in_radius = sum(1 for s in stores_in_radius if s["current_status"] == 'i')

            radius_hourly_dist = [0] * 24
            ever_restocked_ids = set()
            if radius_store_ids:
                id_list = list(radius_store_ids)
                batch_size = 900
                for i in range(0, len(id_list), batch_size):
                    batch = id_list[i:i + batch_size]
                    q_marks = ",".join("?" for _ in batch)
                    cursor.execute(f"""
                        SELECT store_id, timestamp
                        FROM store_history
                        WHERE timestamp > 0 AND status_code = 'i' AND store_id IN ({q_marks});
                    """, batch)
                    for r_sid, r_ts in cursor.fetchall():
                        h_jst = (r_ts + 32400) % 86400 // 3600
                        radius_hourly_dist[h_jst] += 1
                        ever_restocked_ids.add(r_sid)

            peak_h = max(range(24), key=lambda h: radius_hourly_dist[h]) if radius_store_ids else 10
            peak_h_cnt = radius_hourly_dist[peak_h]
            in_stock_rate = round(in_stock_now_in_radius / total_in_radius * 100, 1) if total_in_radius > 0 else 0.0
            ever_rate = round(len(ever_restocked_ids) / total_in_radius * 100, 1) if total_in_radius > 0 else 0.0

            radius_stats = {
                "is_active": True,
                "radius_km": round(max_dist_km, 1),
                "total_stores": total_in_radius,
                "in_stock_now": in_stock_now_in_radius,
                "in_stock_rate": in_stock_rate,
                "ever_restocked": len(ever_restocked_ids),
                "ever_restocked_rate": ever_rate,
                "peak_hour": peak_h,
                "peak_hour_count": peak_h_cnt,
                "peak_window": f"{peak_h:02d}:00 - {(peak_h + 1) % 24:02d}:30 JST",
                "prime_stores_today": 0
            }
            # Use radius-specific hourly distribution for local timeline
            hourly_distribution = radius_hourly_dist

    # 4. Analyze each candidate store
    candidates = []

    # Prepare window bounds if window filter selected
    allowed_hours = None
    if target_hour is not None:
        allowed_hours = [target_hour]
    elif clean_window:
        if clean_window == "now":
            allowed_hours = [(current_hour - 1) % 24, current_hour, (current_hour + 1) % 24, (current_hour + 2) % 24]
        elif clean_window == "morning":
            allowed_hours = list(range(6, 11))
        elif clean_window == "noon":
            allowed_hours = list(range(11, 14))
        elif clean_window == "afternoon":
            allowed_hours = list(range(14, 18))
        elif clean_window == "evening":
            allowed_hours = list(range(18, 24))
        elif clean_window == "all":
            allowed_hours = None

    for sid, d in stores_data.items():
        in_ts = d["timestamps"]
        last_ts = in_ts[-1] if in_ts else d["last_timestamp"]
        days_since = (now_ts - last_ts) / 86400.0 if last_ts > 0 else 999.0

        # Profile for this store's chain
        chain_prof = get_chain_logistics_profile(d["chain"])
        prior_peak = chain_prof["peak_hours"]

        # Recency exponential decay weighting (half-life tau = 21 days)
        w_hours = defaultdict(float)
        w_dows = defaultdict(float)
        sum_w = 0.0
        hours = []
        dows = []
        for t in in_ts:
            delta_d = max(0.0, (now_ts - t) / 86400.0)
            wi = math.exp(-delta_d / 21.0)
            h_jst = (t + 32400) % 86400 // 3600
            dw_jst = datetime.fromtimestamp(t, tz=JST).weekday()
            w_hours[h_jst] += wi
            w_dows[dw_jst] += wi
            sum_w += wi
            hours.append(h_jst)
            dows.append(dw_jst)

        count_hours = Counter(hours) if hours else {}
        count_dows = Counter(dows) if dows else {}

        # Bayesian Shrinkage on hour distribution
        p_prior = {}
        for h in range(24):
            p_prior[h] = 1.0 if h in prior_peak else 0.15
        sum_prior = sum(p_prior.values())
        for h in range(24):
            p_prior[h] /= sum_prior

        # Store empirical probabilities
        p_store = {}
        if sum_w > 0:
            for h in range(24):
                p_store[h] = w_hours.get(h, 0.0) / sum_w
        else:
            p_store = p_prior.copy()

        # Posterior probability: lambda = sum_w / (sum_w + 2.5)
        shrinkage_lambda = sum_w / (sum_w + 2.5) if sum_w > 0 else 0.0
        p_posterior = {}
        for h in range(24):
            p_posterior[h] = shrinkage_lambda * p_store[h] + (1.0 - shrinkage_lambda) * p_prior[h]

        # Calculate turnaround cycle (interval between shipments)
        if len(in_ts) >= 2:
            diffs = [(in_ts[i] - in_ts[i - 1]) / 86400.0 for i in range(1, len(in_ts))]
            valid_diffs = [diff for diff in diffs if 0.5 <= diff <= 30.0]
            avg_cycle = sum(valid_diffs) / len(valid_diffs) if valid_diffs else chain_prof["base_cycle_days"]
        else:
            avg_cycle = chain_prof["base_cycle_days"]

        avg_cycle = max(1.5, min(14.0, avg_cycle))

        # Check if store has a report within last 30 minutes (1800 seconds)
        is_querying_now = (clean_status in ("green", "red", "hot", "warning", "depleted")) or (
            (target_hour is None or target_hour == current_hour) and
            (allowed_hours is None or current_hour in allowed_hours)
        )
        recent = recent_30m_map.get(sid) if is_querying_now else None
        flash_mode = "none"  # "green", "red", "none"
        recent_min_ago = None
        reasons = []

        # Check Truck Route Ripple Effect (active delivery truck within 1.8km of same chain)
        truck_en_route = False
        truck_source_name = ""
        truck_source_dist_m = 0
        truck_source_min_ago = 0
        s_truck = 0

        if d["lat"] is not None and d["lng"] is not None:
            c_lat = float(d["lat"])
            c_lng = float(d["lng"])
            c_chain = d["chain"]
            best_truck_dist_km = 999.0
            best_truck_source = None

            for t in active_truck_sources:
                if t["id"] == sid:
                    continue
                if t["chain"] != c_chain:
                    continue
                t_lat = float(t["lat"])
                t_lng = float(t["lng"])
                if abs(t_lat - c_lat) > 0.02 or abs(t_lng - c_lng) > 0.02:
                    continue
                d_truck_km = _calc_haversine_dist(c_lat, c_lng, t_lat, t_lng)
                if d_truck_km <= 1.8 and d_truck_km < best_truck_dist_km:
                    best_truck_dist_km = d_truck_km
                    best_truck_source = t

            if best_truck_source:
                truck_en_route = True
                truck_source_dist_m = int(round(best_truck_dist_km * 1000))
                sec_since_truck = max(0, now_ts - best_truck_source["last_timestamp"])
                truck_source_min_ago = max(1, sec_since_truck // 60)
                truck_source_name = best_truck_source["name"] or best_truck_source["id"]
                s_truck = int(round(20 - (best_truck_dist_km / 1.8) * 8))
                s_truck = max(12, min(20, s_truck))

        if recent:
            sec_ago = max(0, now_ts - recent["last_timestamp"])
            recent_min_ago = sec_ago // 60
            time_ago_str = f"{recent_min_ago} phút trước" if recent_min_ago > 0 else "vừa xong"
            st = recent["current_status"]

            if st == "i":
                # Chắc chắn 100% có hàng! Chớp chớp xanh!
                total_score = 100
                flash_mode = "green"
                confidence_level = "flash_green"
                display_h = current_hour
                predicted_window = f"NGAY BÂY GIỜ ({time_ago_str})"
                reasons.append(f"⚡ 100% CÓ HÀNG: Vừa có báo cáo CÓ HÀNG {time_ago_str}!")
                reasons.append("🔥 Chắc chắn còn hàng! Hãy đến cửa hàng ngay lập tức.")
            elif st in ("o", "n"):
                # Vừa báo hết hàng trong 30p! Chớp chớp đỏ cảnh báo!
                total_score = 0
                flash_mode = "red"
                confidence_level = "flash_red"
                display_h = current_hour
                predicted_window = f"ĐÃ HẾT HÀNG ({time_ago_str})"
                reasons.append(f"🚨 CẢNH BÁO: Vừa có báo cáo HẾT HÀNG {time_ago_str}!")
                reasons.append("⛔ Kệ đã sạch hàng - KHÔNG NÊN ĐẾN tránh lãng phí thời gian!")
            else:
                total_score = 50
                flash_mode = "none"
                confidence_level = "medium"
                display_h = max(range(24), key=lambda h: (p_posterior[h], count_hours.get(h, 0)))
                predicted_window = f"{display_h:02d}:00 - {(display_h + 1) % 24:02d}:30 JST"
        else:
            # Hour selection & filtering
            if target_hour is not None:
                m0 = count_hours.get(target_hour, 0)
                m1 = count_hours.get((target_hour - 1) % 24, 0) + count_hours.get((target_hour + 1) % 24, 0)
                is_chain_peak = target_hour in prior_peak
                if m0 == 0 and m1 == 0 and not (is_chain_peak and len(in_ts) <= 2):
                    continue
                display_h = target_hour
            elif allowed_hours is not None:
                window_matches = sum(count_hours.get(h, 0) for h in allowed_hours)
                window_prior_matches = any(h in prior_peak for h in allowed_hours)
                if window_matches == 0 and not (window_prior_matches and len(in_ts) <= 2):
                    continue
                display_h = max(allowed_hours, key=lambda h: (p_posterior[h], count_hours.get(h, 0)))
            else:
                display_h = max(range(24), key=lambda h: (p_posterior[h], count_hours.get(h, 0)))

            # 1. Hour scoring (10 to 35 points)
            h_prob = p_posterior.get(display_h, 0.0)
            h_emp = w_hours.get(display_h, 0.0)
            s_hour = int(round(min(26, h_prob * 110)))
            if h_emp >= 0.8:
                s_hour += min(7, int(round(h_emp * 3)))
            if abs(display_h - current_hour) <= 1:
                s_hour += 4
            s_hour = max(10, min(35, s_hour))

            # 2. Day of week affinity scoring (6 to 25 points)
            dow_w = w_dows.get(current_dow, 0.0)
            dow_cnt = count_dows.get(current_dow, 0)
            if dow_w >= 1.5 or dow_cnt >= 2:
                s_dow = 25
            elif dow_w >= 0.7 or dow_cnt == 1:
                s_dow = 18
            elif current_dow in chain_prof.get("dow_peak", []):
                s_dow = 14
            else:
                s_dow = 6

            # 3. Restock cycle turnaround scoring (7 to 24 points)
            if 0.8 <= days_since <= max(6.0, avg_cycle * 1.4):
                s_cycle = 24  # Prime cycle turnaround window!
            elif days_since < 0.8:
                s_cycle = 15  # Fresh shipment today
            elif days_since <= avg_cycle * 2.2:
                s_cycle = 15  # Slightly overdue
            else:
                s_cycle = 7

            # 4. Current status & shelf readiness scoring (-15 to 20 points)
            st = d["current_status"]
            if st == "i":
                s_shelf = 20
            elif st == "o":
                s_shelf = 16  # Shelves clear, ready for next drop
            elif st == "n":
                s_shelf = -15  # Flagged not carrying Pokemon cards
            else:
                s_shelf = 6

            # Dormancy penalty: no restock in >45 days and not currently 'i'
            if days_since > 45.0 and st != "i":
                s_shelf -= 15

            # 5. Restock consistency cluster bonus (0 to 6 points)
            s_cluster = 6 if len(in_ts) >= 4 and sum_w >= 1.5 else 0

            # Calculate final confidence score
            raw_score = s_hour + s_dow + s_cycle + s_shelf + s_cluster + s_truck
            total_score = min(99, max(15, raw_score))
            if truck_en_route:
                total_score = max(total_score, 78)

            confidence_level = "prime" if total_score >= 85 else ("high" if total_score >= 70 else "medium")
            predicted_window = f"{display_h:02d}:00 - {(display_h + 1) % 24:02d}:30 JST"

            # Build prediction reasons
            if truck_en_route:
                reasons.append(
                    f"🚚 Tuyến xe cùng chuỗi: '{truck_source_name}' (cách {truck_source_dist_m}m) vừa có hàng {truck_source_min_ago} phút trước! Xe hàng nhiều khả năng đang trên tuyến đến đây."
                )

            if dow_cnt > 0:
                reasons.append(f"🎯 Đã {dow_cnt} lần có hàng vào {dow_names[current_dow]} (tỷ trọng gần đây cao)")
            elif current_dow in chain_prof.get("dow_peak", []):
                reasons.append(f"📅 Trùng ngày giao hàng trọng điểm của {chain_prof['name']} ({dow_names[current_dow]})")

            h_freq = count_hours.get(display_h, 0)
            if h_freq > 0:
                reasons.append(f"⏰ Giờ quen thuộc: {display_h:02d}:00 - {(display_h + 1) % 24:02d}:30 ({h_freq} lần)")
            else:
                reasons.append(f"⏰ Khung giờ giao hàng đặc trưng chuỗi: {chain_prof['peak_window']}")

            if 0.8 <= days_since <= max(6.0, avg_cycle * 1.4):
                reasons.append(f"🔄 Điểm rơi chu kỳ: TB {avg_cycle:.1f} ngày/đợt (cách {days_since:.1f} ngày)")
            elif days_since < 0.8:
                reasons.append("⚡ Vừa có hàng trong ngày hôm nay!")

            if st == "i":
                reasons.append("🟢 Đang có báo cáo CÓ HÀNG gần đây!")
            elif st == "o":
                reasons.append("📦 Vừa hết hàng - Kệ trống sẵn sàng đón đợt mới")
            elif st == "n":
                reasons.append("⚠️ Báo cáo gần nhất: Chưa bán thẻ Pokémon")

        # Determine data reliability rating and action tips
        if flash_mode == "green":
            reliability_level = "realtime"
            reliability_stars = 3
            reliability_text = "Thời gian thực (100% chính xác)"
            action_tip = "🔥 Chắc chắn còn hàng! Hãy đến cửa hàng ngay lập tức trước khi hết."
        elif flash_mode == "red":
            reliability_level = "realtime"
            reliability_stars = 3
            reliability_text = "Thời gian thực (Cảnh báo hết hàng)"
            action_tip = "⛔ Kệ đã sạch hàng - KHÔNG NÊN ĐẾN tránh lãng phí thời gian!"
        else:
            if len(in_ts) >= 5 and sum_w >= 2.0:
                reliability_level = "verified"
                reliability_stars = 3
                reliability_text = "Đã xác minh qua nhiều đợt restock"
            elif len(in_ts) >= 2 or (len(in_ts) >= 1 and truck_en_route):
                reliability_level = "high"
                reliability_stars = 2
                reliability_text = "Độ tin cậy khá (Lịch sử + Chuỗi)"
            else:
                reliability_level = "estimated"
                reliability_stars = 1
                reliability_text = "Ước tính theo chuỗi & tuyến xe"

            is_prime_now = (abs(display_h - current_hour) <= 1)
            if truck_en_route:
                action_tip = f"🚚 Xe giao hàng đang ở gần ({truck_source_dist_m}m)! Nên ghé kiểm tra kệ trong 20-45 phút tới."
            elif is_prime_now:
                action_tip = f"⚡ Đang trong khung giờ vàng ({predicted_window})! Tỷ lệ lên kệ cao nhất trong ngày."
            elif d["current_status"] == "o" and days_since <= 2.5:
                action_tip = "📦 Kệ đang trống sau đợt bán trước, rất thích hợp đón đợt bổ sung tiếp theo."
            else:
                action_tip = f"🕒 Canh giờ ghé vào khoảng {display_h:02d}:00 - {(display_h + 1) % 24:02d}:30 để có cơ hội cao nhất."

        # Status filtering:
        if clean_status in ("green", "hot", "in_stock") and flash_mode != "green":
            continue
        if clean_status in ("red", "warning", "depleted") and flash_mode != "red":
            continue
        if clean_status in ("truck", "route", "en_route") and not truck_en_route:
            continue
        if clean_status in ("predictions", "pred_only") and flash_mode != "none":
            continue

        # Score threshold filtering:
        # Keep green flash (100%), red flash (0% warning), and truck ripple stores, but filter regular predictions below min_score
        if flash_mode == "none" and not truck_en_route and total_score < min_score:
            continue

        # Proximity & Walking Distance calculation
        dist_km = None
        dist_m = None
        dist_str = ""
        walk_min = None
        if user_lat is not None and user_lng is not None and d["lat"] is not None and d["lng"] is not None:
            try:
                dist_km = _calc_haversine_dist(user_lat, user_lng, float(d["lat"]), float(d["lng"]))
                if max_dist_km and dist_km > max_dist_km:
                    continue
                dist_m = int(round(dist_km * 1000))
                dist_str = f"~{dist_m}m" if dist_km < 1.0 else f"~{dist_km:.1f}km"
                walk_min = max(1, int(round(dist_km * 12.5)))
            except Exception:
                dist_km, dist_m, dist_str, walk_min = None, None, "", None

        # Extract top cards/packs
        pack_counter = Counter(d["packs"])
        top_packs = [p for p, _ in pack_counter.most_common(2)]
        if top_packs and flash_mode != "red":
            reasons.append(f"🃏 Thẻ hay về: {', '.join(top_packs)}")

        is_prime_now = (flash_mode == "green") or (abs(display_h - current_hour) <= 1)

        candidates.append({
            "store_id": sid,
            "name": d["name"],
            "pref": d["pref"],
            "chain": d["chain"],
            "chain_name": CHAIN_NAMES.get(d["chain"], d["chain"]),
            "address": d["address"],
            "lat": d["lat"],
            "lng": d["lng"],
            "current_status": st,
            "score": total_score,
            "flash_mode": flash_mode,
            "recent_min_ago": recent_min_ago,
            "is_hot_30m": flash_mode == "green",
            "is_cold_30m": flash_mode == "red",
            "truck_en_route": truck_en_route,
            "truck_source_name": truck_source_name,
            "truck_source_dist_m": truck_source_dist_m,
            "truck_source_min_ago": truck_source_min_ago,
            "confidence_level": confidence_level,
            "reliability_level": reliability_level,
            "reliability_stars": reliability_stars,
            "reliability_text": reliability_text,
            "action_tip": action_tip,
            "chain_pattern_match": display_h in prior_peak,
            "predicted_hour": display_h,
            "predicted_window": predicted_window,
            "is_prime_now": is_prime_now,
            "days_since_last_in": round(days_since, 1),
            "avg_interval_days": round(avg_cycle, 1),
            "total_in_reports": len(in_ts),
            "top_packs": top_packs,
            "reasons": reasons,
            "distance_km": round(dist_km, 2) if dist_km is not None else None,
            "distance_m": dist_m,
            "distance_str": dist_str,
            "walk_time_min": walk_min
        })

    # Sort results
    if sort_by == "distance" and user_lat is not None:
        candidates.sort(key=lambda x: (
            x["distance_km"] if x["distance_km"] is not None else 99999,
            0 if x["flash_mode"] == "green" else (1 if x["flash_mode"] == "none" else 2),
            -x["score"]
        ))
    elif sort_by == "score":
        candidates.sort(key=lambda x: (
            0 if x["flash_mode"] == "green" else (1 if x["flash_mode"] == "none" else 2),
            -x["score"],
            x["predicted_hour"]
        ))
    elif sort_by == "time":
        candidates.sort(key=lambda x: (
            0 if x["flash_mode"] == "green" else 1,
            x["predicted_hour"],
            -x["score"]
        ))
    else:
        candidates.sort(key=lambda x: (
            0 if x["flash_mode"] == "green" else (1 if x["flash_mode"] == "none" else 2),
            -x["score"],
            x["predicted_hour"]
        ))

    truck_cand_count = sum(1 for c in candidates if c.get("truck_en_route"))
    green_30m_count = sum(1 for c in candidates if c["flash_mode"] == "green")
    red_30m_count = sum(1 for c in candidates if c["flash_mode"] == "red")

    if radius_stats["is_active"]:
        radius_stats["prime_stores_today"] = sum(1 for c in candidates if c["score"] >= 70)
    radius_stats["green_30m_count"] = green_30m_count
    radius_stats["red_30m_count"] = red_30m_count
    radius_stats["truck_count"] = truck_cand_count

    result_payload = {
        "server_time_jst": now_dt.strftime("%H:%M %d/%m/%Y"),
        "current_hour": current_hour,
        "current_dow": current_dow,
        "current_dow_name": dow_names[current_dow],
        "current_dow_jp": dow_jp_names[current_dow],
        "radius_stats": radius_stats,
        "hourly_distribution": hourly_distribution,
        "total_candidates": len(candidates),
        "predictions": candidates[:limit]
    }

    _predictions_cache[cache_key] = (now_ts, result_payload)
    return result_payload



