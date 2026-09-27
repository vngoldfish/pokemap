"""
PokéTan Full History Harvester
Downloads the entire historical report archive for all stores in SQLite pokemap.db.
Supports resume, batch commits, rate-limiting, and smart prioritization.
"""

import asyncio
import sqlite3
import time
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx

# JST timezone (UTC+9)
JST = timezone(timedelta(hours=9))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import FIRESTORE_BASE_URL, FIREBASE_API_KEY, PACK_CODES
from app.fetcher import parse_firestore_fields
from app.db import get_db_connection, _db_write_lock

DB_PATH = os.path.join(BASE_DIR, "app", "data", "pokemap.db")
CHECKPOINT_PATH = os.path.join(BASE_DIR, "app", "data", "harvest_checkpoint.json")

# Concurrency & Rate limits
CONCURRENCY = 15  # 15 concurrent async requests
REQUEST_TIMEOUT = 12.0
BATCH_COMMIT_SIZE = 100

def get_db():
    """Return a managed connection via app.db.get_db_connection() for guaranteed cleanup."""
    return get_db_connection()

def load_checkpoint() -> set:
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("completed_store_ids", []))
        except Exception:
            pass
    return set()

def save_checkpoint(completed: set):
    try:
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump({"completed_store_ids": list(completed), "updated_at": int(time.time())}, f)
    except Exception as e:
        print(f"Error saving checkpoint: {e}")

def detect_packs_from_note(note: str) -> List[str]:
    if not note:
        return []
    note_lower = note.lower()
    packs = []
    for code, name in PACK_CODES.items():
        name_lower = name.lower()
        aliases = [name_lower]
        if "(" in name:
            aliases.append(name[name.find("(") + 1:name.find(")")].lower())
        if any(a in note_lower for a in aliases):
            packs.append(name)
    return packs

async def fetch_history_for_store(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, store_id: str) -> List[Dict[str, Any]]:
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    clean_quoted = urllib.parse.quote(clean_id)
    url = f"{FIRESTORE_BASE_URL}/stores/{clean_quoted}/history?key={FIREBASE_API_KEY}&pageSize=50"

    async with semaphore:
        for attempt in range(3):
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get("documents", [])
                    history = []
                    for d in docs:
                        fields = parse_firestore_fields(d.get("fields", {}))
                        raw_status = fields.get("status", "")
                        status_code = "u"
                        status_label = "⚪ Chưa rõ"
                        if raw_status in ["in-stock", "i"]:
                            status_code = "i"
                            status_label = "🟢 Có hàng"
                        elif raw_status in ["out-of-stock", "o"]:
                            status_code = "o"
                            status_label = "🔴 Hết hàng"
                        elif raw_status in ["not-handled", "none", "n"]:
                            status_code = "n"
                            status_label = "🟡 Không bán thẻ"

                        ts_str = fields.get("timestamp")
                        unix_ts = 0
                        formatted_time = ""
                        if ts_str:
                            try:
                                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                                unix_ts = int(dt.timestamp())
                                jst_dt = dt.astimezone(JST)
                                formatted_time = jst_dt.strftime("%H:%M %d/%m/%Y")
                            except Exception:
                                pass

                        note = str(fields.get("note") or "")
                        packs = fields.get("packs") or []
                        if not packs and note:
                            packs = detect_packs_from_note(note)

                        history.append({
                            "store_id": clean_id,
                            "status_code": status_code,
                            "status_label": status_label,
                            "note": note,
                            "packs_json": json.dumps(packs, ensure_ascii=False),
                            "user": str(fields.get("user") or "匿名トレーナー"),
                            "who": str(fields.get("who") or "")[:8],
                            "onsite": 1 if fields.get("os") == 1 else 0,
                            "confirms": max(1, int(fields.get("confirms") or fields.get("count") or 1)),
                            "timestamp": unix_ts,
                            "formatted_time": formatted_time,
                            "source": "poketan"
                        })
                    return history
                elif resp.status_code == 404:
                    return []
                elif resp.status_code == 429:
                    await asyncio.sleep(2.0 * (attempt + 1))
                else:
                    await asyncio.sleep(1.0)
            except Exception:
                await asyncio.sleep(1.0)
        return []

async def main():
    print("=" * 65)
    print("🚀 POKETAN FULL HISTORY HARVESTER (BẮT ĐẦU ĐỒNG BỘ TOÀN DIỆN)")
    print("=" * 65)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Smart prioritization: stores with 'i' first, then 'o', then 'n', then 'u'
        cursor.execute("""
            SELECT id, name, current_status, last_timestamp
            FROM stores
            ORDER BY 
                CASE current_status
                    WHEN 'i' THEN 1
                    WHEN 'o' THEN 2
                    WHEN 'n' THEN 3
                    ELSE 4
                END,
                last_timestamp DESC;
        """)
        all_stores = cursor.fetchall()
    total_stores = len(all_stores)
    print(f"Tổng số cửa hàng cần kiểm tra: {total_stores:,} shop")

    completed = load_checkpoint()
    print(f"Đã hoàn thành từ trước (Checkpoint): {len(completed):,} shop")

    pending_stores = [s for s in all_stores if s["id"] not in completed]
    print(f"Số cửa hàng còn lại cần tải: {len(pending_stores):,} shop")

    if not pending_stores:
        print("🎉 Toàn bộ cửa hàng đã được tải đầy đủ!")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    start_time = time.time()
    total_saved_reports = 0
    now_ts = int(time.time())

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # Process in batches
        chunk_size = 50
        for i in range(0, len(pending_stores), chunk_size):
            chunk = pending_stores[i:i + chunk_size]
            tasks = [fetch_history_for_store(client, semaphore, s["id"]) for s in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            history_batch = []
            store_updates = []

            for store_row, res in zip(chunk, results):
                sid = store_row["id"]
                completed.add(sid)
                if isinstance(res, list) and res:
                    for h in res:
                        ts = h["timestamp"]
                        code = h["status_code"]
                        hist_id = f"{sid}_{ts}_{code}"
                        history_batch.append((
                            hist_id,
                            sid,
                            code,
                            h["status_label"],
                            h["note"],
                            h["packs_json"],
                            h["user"],
                            h["who"],
                            h["onsite"],
                            h["confirms"],
                            ts,
                            h["formatted_time"],
                            ts if ts > 0 else now_ts,
                            h["source"]
                        ))

                    # Update store's latest status if newest history record is newer
                    sorted_res = sorted(res, key=lambda x: x["timestamp"], reverse=True)
                    newest = sorted_res[0]
                    if newest["timestamp"] >= (store_row["last_timestamp"] or 0):
                        store_updates.append((
                            newest["status_code"],
                            newest["timestamp"],
                            newest["formatted_time"],
                            newest["onsite"],
                            newest["packs_json"],
                            now_ts,
                            sid
                        ))

            # Commit batch to SQLite
            with _db_write_lock:
                with get_db_connection() as db_conn:
                    db_cursor = db_conn.cursor()
                    if history_batch:
                        db_cursor.executemany("""
                            INSERT OR REPLACE INTO store_history (
                                id, store_id, status_code, status_label, note, packs_json,
                                user, who, onsite, confirms, timestamp, formatted_time, created_at, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, history_batch)
                        total_saved_reports += len(history_batch)

                    if store_updates:
                        db_cursor.executemany("""
                            UPDATE stores
                            SET current_status = ?,
                                last_timestamp = ?,
                                last_reported_at = ?,
                                onsite = ?,
                                packs_json = ?,
                                updated_at = ?
                            WHERE id = ?;
                        """, store_updates)
                    db_conn.commit()

            # Save checkpoint every 200 stores
            if (i + chunk_size) % 200 < chunk_size:
                save_checkpoint(completed)

            elapsed = time.time() - start_time
            done_count = len(completed)
            speed = (i + len(chunk)) / elapsed if elapsed > 0 else 0
            pct = (done_count / total_stores) * 100
            print(f"[{pct:5.1f}%] Đã xử lý {done_count:,}/{total_stores:,} shop | +{total_saved_reports:,} báo cáo | Tốc độ: {speed:.1f} shop/s")

    save_checkpoint(completed)
    elapsed = time.time() - start_time
    print("=" * 65)
    print(f"🎉 HOÀN TẤT THU THẬP LỊCH SỬ TOÀN DIỆN!")
    print(f"⏱️ Tổng thời gian: {elapsed:.1f}s ({elapsed/60:.1f} phút)")
    print(f"📦 Tổng số lượt báo cáo đã lưu vào SQLite: {total_saved_reports:,}")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
