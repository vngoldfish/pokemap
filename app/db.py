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
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemap.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def get_db_connection() -> sqlite3.Connection:
    """Create a thread-safe connection to the SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initialize database tables and indexes."""
    os.makedirs(DATA_DIR, exist_ok=True)
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
        
        conn.commit()
    print("  [DB] SQLite database initialized at:", DB_PATH)


def seed_regions_if_empty():
    """Populate default regions."""
    default_regions = [
        ("osaka", "大阪・関西 (Osaka & Lân cận)", "なんば", 34.6667, 135.5000, 13, json.dumps(["osaka"])),
        ("tokyo", "東京・神奈川 (Tokyo & Lân cận)", "横浜", 35.4500, 139.6300, 12, json.dumps(["kanagawa"])),
        ("nagoya", "名古屋・東海 (Nagoya & Lân cận)", "名古屋", 35.1709, 136.8815, 12, json.dumps(["aichi", "gifu", "mie"])),
        ("all", "全エリア (Tất cả 3 vùng / Toàn quốc)", "全エリア", 34.6937, 135.5023, 11, json.dumps(["osaka", "kanagawa", "aichi", "gifu", "mie"]))
    ]
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
    """Seed stores from stores_*.json files into SQLite database if table is empty."""
    seed_regions_if_empty()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stores;")
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            return existing_count

        total_inserted = 0
        pref_files = {
            "osaka": "stores_osaka.json",
            "kanagawa": "stores_kanagawa.json",
            "aichi": "stores_aichi.json",
            "gifu": "stores_gifu.json",
            "mie": "stores_mie.json"
        }

        now_ts = int(time.time())
        batch = []
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
                    batch.append((
                        sid,
                        s.get("name") or "Cửa hàng",
                        s.get("chain") or "",
                        s.get("address") or "",
                        s.get("lat"),
                        s.get("lng"),
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
            except Exception as e:
                print(f"  [DB] Error loading {fname}: {e}")

        if batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO stores (
                    id, name, chain, address, lat, lng, pref, city, zip, phone,
                    current_status, last_timestamp, last_reported_at, onsite, packs_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, batch)
            conn.commit()
            total_inserted = len(batch)
            print(f"  [DB] Successfully seeded {total_inserted} stores into SQLite database!")
        return total_inserted


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
    prefs = ["osaka", "kanagawa", "aichi", "gifu", "mie"]
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
                packs = parsed.get("packs") or []
                rep_time = parsed.get("reported_at") or ""
                label = parsed.get("status_label") or ("🟢 Có hàng" if code == "i" else ("🔴 Hết hàng" if code == "o" else "🟡 Không bán thẻ"))
                hist_id = f"{sid}_{ts}_{code}"

                if sid not in existing_store_ids and sid not in new_stores_map:
                    new_stores_map[sid] = (sid, sid, 'other', '', p, code, now_ts)

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
                    ts,
                    rep_time,
                    now_ts,
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

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if new_stores_map:
            cursor.executemany("""
                INSERT OR IGNORE INTO stores (id, name, chain, address, pref, current_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, list(new_stores_map.values()))

        if history_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO store_history (
                    id, store_id, status_code, status_label, note, packs_json,
                    user, who, onsite, timestamp, formatted_time, created_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
        conn.commit()

    total_backfilled = len(history_batch)
    print(f"  [DB] Successfully backfilled {total_backfilled} statuses into SQLite store_history & stores!")
    return total_backfilled


def get_stores(region: Optional[str] = None, pref: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Query stores dictionary from SQLite database matching region or prefecture."""
    from .config import CHAIN_NAMES

    target_prefs = []
    if pref:
        target_prefs = [pref.strip().lower()]
    elif region:
        r = region.strip().lower()
        if r == "osaka":
            target_prefs = ["osaka"]
        elif r == "tokyo" or r == "kanagawa":
            target_prefs = ["kanagawa"]
        elif r == "nagoya" or r == "aichi":
            target_prefs = ["aichi", "gifu", "mie"]
        elif r == "all":
            target_prefs = ["osaka", "kanagawa", "aichi", "gifu", "mie"]
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
            res[sid] = {
                "id": sid,
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


def get_store_history(store_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieve history reports for a store from SQLite database."""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, store_id, status_code, status_label, note, packs_json,
                   user, who, onsite, timestamp, formatted_time, source
            FROM store_history
            WHERE store_id = ?
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
                "timestamp": r["timestamp"],
                "formatted_time": r["formatted_time"] or "",
                "source": r["source"] or "poketan"
            })
        return history


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
    source: str = "poketan"
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
            dt = datetime.fromtimestamp(timestamp)
            formatted_time = dt.strftime("%H:%M %d/%m/%Y")
        except Exception:
            formatted_time = ""

    hist_id = f"{clean_id}_{timestamp}_{status_code}"
    now_ts = int(time.time())

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT id FROM store_history WHERE id = ?;", (hist_id,))
        if cursor.fetchone():
            return False, {"id": hist_id, "store_id": clean_id, "status_code": status_code, "timestamp": timestamp}

        # Ensure store exists in stores table to satisfy foreign key
        cursor.execute("SELECT id FROM stores WHERE id = ?;", (clean_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT OR IGNORE INTO stores (id, name, chain, address, pref, current_status, updated_at)
                VALUES (?, ?, 'other', '', 'osaka', ?, ?);
            """, (clean_id, clean_id, status_code, now_ts))

        # Insert new history item
        cursor.execute("""
            INSERT OR REPLACE INTO store_history (
                id, store_id, status_code, status_label, note, packs_json,
                user, who, onsite, timestamp, formatted_time, created_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            timestamp,
            formatted_time,
            now_ts,
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
        "timestamp": timestamp,
        "formatted_time": formatted_time,
        "source": source
    }
    return True, entry


def save_bulk_history(store_id: str, history_list: List[Dict[str, Any]], source: str = "poketan") -> int:
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
        formatted_time = item.get("formatted_time") or ""
        if ts > 0 and not formatted_time:
            try:
                dt = datetime.fromtimestamp(ts)
                formatted_time = dt.strftime("%H:%M %d/%m/%Y")
            except Exception:
                pass

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
            ts,
            formatted_time,
            now_ts,
            source
        ))

    if not batch:
        return 0

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM stores WHERE id = ?;", (clean_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT OR IGNORE INTO stores (id, name, chain, address, pref, current_status, updated_at)
                VALUES (?, ?, 'other', '', 'osaka', 'u', ?);
            """, (clean_id, clean_id, now_ts))

        cursor.executemany("""
            INSERT OR REPLACE INTO store_history (
                id, store_id, status_code, status_label, note, packs_json,
                user, who, onsite, timestamp, formatted_time, created_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, batch)
        conn.commit()
    return len(batch)


def get_report_counts(region: Optional[str] = None, pref: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """
    Calculate number of in-stock and out-of-stock reports per store using fast SQL aggregation.
    Returns: { store_id: { "in": int, "out": int } }
    """
    target_prefs = []
    if pref:
        target_prefs = [pref.strip().lower()]
    elif region:
        r = region.strip().lower()
        if r == "osaka":
            target_prefs = ["osaka"]
        elif r == "tokyo" or r == "kanagawa":
            target_prefs = ["kanagawa"]
        elif r == "nagoya" or r == "aichi":
            target_prefs = ["aichi", "gifu", "mie"]
        elif r == "all":
            target_prefs = ["osaka", "kanagawa", "aichi", "gifu", "mie"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_prefs:
            placeholders = ",".join("?" for _ in target_prefs)
            cursor.execute(f"""
                SELECT h.store_id,
                       SUM(CASE WHEN h.status_code = 'i' THEN 1 ELSE 0 END) as count_in,
                       SUM(CASE WHEN h.status_code = 'o' THEN 1 ELSE 0 END) as count_out
                FROM store_history h
                INNER JOIN stores s ON h.store_id = s.id
                WHERE s.pref IN ({placeholders})
                GROUP BY h.store_id;
            """, target_prefs)
        else:
            cursor.execute("""
                SELECT store_id,
                       SUM(CASE WHEN status_code = 'i' THEN 1 ELSE 0 END) as count_in,
                       SUM(CASE WHEN status_code = 'o' THEN 1 ELSE 0 END) as count_out
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
        return counts
