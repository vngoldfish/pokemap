"""
Comprehensive Data Harvester & Bulk Backfill Module for PokéMap.
Pulls 100% of external stores metadata and historical statuses from PokéTan / Google Firestore
into the local SQLite database (pokemap.db).

Ensures the local SQLite database is the completely independent Single Source of Truth.
Mutes all notifications (Telegram & Toast) during bulk harvesting.
"""

import sys
import os
import json
import time
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from .config import (
    FIRESTORE_BASE_URL,
    FIREBASE_API_KEY,
    STORES_URL_TEMPLATE
)
from .fetcher import (
    fetch_stores,
    fetch_firestore_document,
    fetch_store_history,
    DEFAULT_CACHE_DIR
)
from .parser import parse_store_status
from .db import (
    init_db,
    get_db_connection,
    _db_write_lock,
    invalidate_stores_cache,
    save_bulk_history,
    get_store_catalog
)

ALL_HARVEST_PREFS = ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]


def harvest_stores_metadata(prefs: List[str] = ALL_HARVEST_PREFS) -> Dict[str, int]:
    """
    Download and seed store catalog for all prefectures into SQLite stores table.
    Ensures 21,170+ stores across Japan are permanently persisted locally.
    """
    print("=" * 60)
    print("  [Harvester] 1. BẮT ĐẦU KÉO TOÀN BỘ CỬA HÀNG VỀ CSDL SQLITE...")
    print("=" * 60)

    results = {}
    now_ts = int(time.time())

    for pref in prefs:
        try:
            print(f"  --> Đang tải danh sách quán tỉnh: {pref}...")
            stores_dict = fetch_stores(pref, force_refresh=False)
            batch = []
            for sid, s in stores_dict.items():
                if not sid:
                    continue
                batch.append((
                    sid,
                    s.get("name") or "Cửa hàng",
                    s.get("chain") or "other",
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

            if batch:
                with _db_write_lock:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.executemany("""
                            INSERT OR IGNORE INTO stores (
                                id, name, chain, address, lat, lng, pref, city, zip, phone,
                                current_status, last_timestamp, last_reported_at, onsite, packs_json, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, batch)
                        # Ensure correct prefecture is updated
                        cursor.executemany("""
                            UPDATE stores
                            SET pref = ?,
                                name = CASE WHEN name = 'Cửa hàng' OR name = id THEN ? ELSE name END,
                                chain = CASE WHEN chain = 'other' THEN ? ELSE chain END,
                                address = CASE WHEN address = '' THEN ? ELSE address END,
                                lat = CASE WHEN lat IS NULL THEN ? ELSE lat END,
                                lng = CASE WHEN lng IS NULL THEN ? ELSE lng END
                            WHERE id = ?;
                        """, [(b[6], b[1], b[2], b[3], b[4], b[5], b[0]) for b in batch])
                        conn.commit()

            results[pref] = len(batch)
            print(f"  ✅ Đã lưu {len(batch)} quán tỉnh {pref} vào SQLite stores.")
        except Exception as e:
            print(f"  ❌ Lỗi nạp cửa hàng tỉnh {pref}: {e}")
            results[pref] = 0

    return results


def harvest_all_statuses_and_history(prefs: List[str] = ALL_HARVEST_PREFS) -> Dict[str, Any]:
    """
    Fetch all hot and cold status documents from Firestore for all prefectures.
    Insert into SQLite store_history and update stores.
    Mutes notifications so no alerts are triggered for historical data.
    """
    print("\n" + "=" * 60)
    print("  [Harvester] 2. BẮT ĐẦU KÉO TOÀN BỘ TRẠNG THÁI & LỊCH SỬ TỒN KHO...")
    print("=" * 60)

    now_ts = int(time.time())
    total_history_inserted = 0
    in_stock_store_ids = []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM stores;")
        existing_store_ids = set(r[0] for r in cursor.fetchall())

    for pref in prefs:
        print(f"  --> Đang kéo trạng thái hot & cold tỉnh {pref}...")
        try:
            hot = fetch_firestore_document(f"status/{pref}")
        except Exception:
            hot = {}
        try:
            cold = fetch_firestore_document(f"status/{pref}_cold")
        except Exception:
            cold = {}

        merged = {**cold, **hot}
        history_batch = []
        store_update_batch = []
        new_stores_map = {}

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

            if code == "i":
                in_stock_store_ids.append((sid, pref))

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
                    meta.get("pref") or pref,
                    code,
                    now_ts
                )

            # Historical reports have created_at = timestamp so web toasts NEVER trigger
            created_at_val = ts if ts > 0 else now_ts

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
                    total_history_inserted += len(history_batch)

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

        print(f"  ✅ Đã đồng bộ {len(history_batch)} báo cáo tỉnh {pref} vào CSDL SQLite.")

    # Synchronize stores current_status with newest record from store_history
    with _db_write_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
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

    # Backfill deep history for in-stock stores
    print(f"\n  [Harvester] 3. TẢI LỊCH SỬ CHI TIẾT CHO CÁC QUÁN CÓ HÀNG ({len(in_stock_store_ids)} quán)...")
    backfilled_count = 0
    for sid, pref in in_stock_store_ids[:150]:
        try:
            remote_hist = fetch_store_history(sid)
            if remote_hist:
                n = save_bulk_history(sid, remote_hist, source="poketan", pref=pref)
                backfilled_count += n
        except Exception:
            pass

    print(f"  ✅ Đã tải bổ sung {backfilled_count} bản ghi chi tiết cho các quán có hàng.")

    invalidate_stores_cache()
    return {
        "status": "ok",
        "history_inserted": total_history_inserted,
        "in_stock_found": len(in_stock_store_ids),
        "deep_history_backfilled": backfilled_count
    }


def harvest_all_to_csdl() -> Dict[str, Any]:
    """Execute complete harvesting workflow."""
    init_db()
    store_results = harvest_stores_metadata(ALL_HARVEST_PREFS)
    hist_results = harvest_all_statuses_and_history(ALL_HARVEST_PREFS)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stores;")
        total_stores = cursor.fetchone()[0]
        cursor.execute("SELECT pref, COUNT(*) FROM stores GROUP BY pref;")
        pref_breakdown = {r[0]: r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) FROM store_history;")
        total_history = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM stores WHERE current_status = 'i';")
        total_in_stock = cursor.fetchone()[0]

    print("\n" + "=" * 60)
    print("  🎉 HOÀN TẤT ĐỒNG BỘ TOÀN DIỆN VỀ CSDL NỘI BỘ SQLITE!")
    print(f"  - Tổng số quán trong CSDL: {total_stores:,} quán")
    for p, c in pref_breakdown.items():
        print(f"    * {p}: {c:,} quán")
    print(f"  - Tổng số bản ghi lịch sử trong CSDL: {total_history:,} bản ghi")
    print(f"  - Số quán đang có hàng (🟢): {total_in_stock:,} quán")
    print("=" * 60)

    return {
        "total_stores": total_stores,
        "pref_breakdown": pref_breakdown,
        "total_history": total_history,
        "total_in_stock": total_in_stock,
        "stores_seeded": store_results,
        "hist_results": hist_results
    }


if __name__ == "__main__":
    harvest_all_to_csdl()
