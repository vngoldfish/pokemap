"""
Interactive Web Dashboard for BAWUI POKE APP
Features:
- Complete 4,050 Stores in Osaka with Real-time Statuses
- Default View: ONLY In-Stock Stores (🟢 Có hàng) for speed & focus
- Report Freshness & Time Options Filter (⚙️ Tùy chọn thời gian báo cáo):
  * ⚡ Siêu mới: Trong vòng 1 giờ (Khả năng còn hàng cao nhất! 🔥)
  * ⏱ Trong vòng 3 giờ (Khuyên dùng khi đi săn thẻ)
  * ⏱ Trong vòng 6 giờ
  * 📅 Trong vòng 12 giờ
  * 📅 Trong vòng 24 giờ (Mặc định)
  * ⏳ Tất cả thời gian (Bao gồm tin cũ)
- Freshness Badges & Warning Alerts on Cards & Map Popups for older reports (>3h, >6h) to avoid wasting trips
- Settings Option Icon (⚙️) & Modal to customize store status & report freshness
- High-Performance Hybrid Map Rendering (Canvas CircleMarkers for 4,000+ points + DivIcon for In-Stock)
- Application Top Navbar with Semantic Navigation Menu & Bi-directional URL Sync (/map, /calendar)
- Dedicated Full-Width Header and View for Lottery & Event Calendar
- User Current GPS Location with Pulsing Marker & Accuracy Circle
- Haversine Distance Calculation (km/m) & Google Maps Walking Directions
- Real-time Firestore onSnapshot Push Listener & Audio Chime Alerts
"""

import sys
import os
import json
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .fetcher import fetch_stores, fetch_firestore_document, DEFAULT_CACHE_DIR, fetch_store_history, fetch_realtime_status
from .parser import merge_stores_with_status, parse_store_status
from .calendar_tracker import fetch_calendar_events
from .config import CHAIN_NAMES, PACK_CODES, FIREBASE_API_KEY, PROJECT_ID
from .db import (
    init_db,
    seed_stores_if_empty,
    backfill_all_poketan_statuses,
    get_stores as db_get_stores,
    get_store_by_id as db_get_store_by_id,
    get_store_history as db_get_store_history,
    record_new_report,
    save_bulk_history,
    get_report_counts as db_get_report_counts
)
import threading

# Initialize local SQLite database and populate stores on startup
init_db()
seed_stores_if_empty()
threading.Thread(target=backfill_all_poketan_statuses, daemon=True).start()

app = FastAPI(title="BAWUI POKE APP - Real-Time Stock & Lottery Tracker")

SETTINGS_FILE = os.path.join(DEFAULT_CACHE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    # 1. BẢN ĐỒ: HIỂN THỊ CỬA HÀNG TRÊN BẢN ĐỒ (MAP STORE VISIBILITY)
    "mapDisplay": {
        "mode": "all",              # 'all', 'only_in', 'with_out', 'custom'
        "chain": "",                # Lọc chuỗi trên bản đồ ("" = tất cả)
        "includeCold": True,        # Nạp dữ liệu lịch sử (>24h)
        "showInStock": True,        # 🟢 Cửa hàng có hàng
        "showOutOfStock": True,     # 🔴 Cửa hàng hết hàng
        "showNotHandled": True,     # ⚪ Cửa hàng không bán thẻ
        "showUnknown": True         # 🔘 Chưa có thông báo gì / chưa rõ
    },

    # 2. THÔNG BÁO: HIỂN THỊ THÔNG BÁO CÓ HÀNG & CẢNH BÁO (IN-STOCK NOTIFICATIONS & ALERTS)
    "notifications": {
        "soundEnabled": True,
        "pushEnabled": True,
        "notifyInStock": True,        # Thông báo & hiển thị tin có hàng
        "notifyOutOfStock": False,    # Thông báo tin hết hàng
        "notifyNotHandled": False,    # Thông báo tin không bán thẻ
        "notifyLottery": True,        # Thông báo lịch bốc thăm mới
        "notifyChain": "",            # Lọc thông báo theo chuỗi
        "maxReportAgeHours": 24.0,    # Độ mới tin báo (giờ, 24h mặc định)
        "onlyOnsiteGps": False,       # Chỉ thông báo tin có GPS tại quán
        "discordWebhookUrl": "",      # Webhook URL của kênh Discord
        "telegramBotToken": "",       # Token bot Telegram (từ @BotFather)
        "telegramChatId": "",         # ID chat hoặc nhóm Telegram
        "telegramEnabled": False,     # Bật gửi Telegram khi có hàng
        "telegramStatus": "in",       # 'in' (chỉ có hàng), 'onsite' (tại quán), 'recent', 'all'
        "telegramChain": "all",       # 'all', 'conbini', 'seven', ...
        "telegramTime": "24",         # '1', '3', '6', '24', 'all'
        "telegramRegion": "osaka",    # 'osaka', 'tokyo', 'nagoya', 'all'
        "notifyPrefs": ["osaka", "aichi", "kanagawa", "gifu", "mie"]  # Các tỉnh nhận thông báo
    },

    # Chế độ xem danh sách sidebar: 'feed' (Thông báo có hàng) hoặc 'all' (Tất cả cửa hàng bản đồ)
    "sidebarTab": "feed",

    # Tương thích ngược
    "statusFilter": { "i": True, "o": True, "n": True, "u": True },
    "maxReportAgeHours": 24.0,
    "includeCold": True,
    "currentChain": "",
    "sortMode": "newest",
    "showExpired": False
}


def deep_update_dict(base: dict, update: dict) -> dict:
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = deep_update_dict(base[k], v)
        else:
            base[k] = v
    return base


def load_user_settings() -> dict:
    import copy
    res = copy.deepcopy(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                deep_update_dict(res, saved)
        except Exception as e:
            print("Error loading settings:", e)
    return res


def save_user_settings(settings: dict) -> None:
    try:
        os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error saving settings:", e)


@app.get("/api/settings")
def get_settings():
    return JSONResponse(content=load_user_settings())


@app.post("/api/settings")
async def update_settings(request: Request):
    try:
        data = await request.json()
        current = load_user_settings()
        deep_update_dict(current, data)
        save_user_settings(current)
        return JSONResponse(content={"status": "ok", "settings": current})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# All available prefectures on PokéTan
ALL_PREFS = ["osaka", "aichi", "kanagawa", "gifu", "mie"]

# Defined 3 core regions + all (matching user specification)
REGION_PREFS = {
    "osaka": ["osaka"],
    "tokyo": ["kanagawa"],
    "kanagawa": ["kanagawa"],
    "nagoya": ["aichi", "gifu", "mie"],
    "aichi": ["aichi", "gifu", "mie"],
    "all": ["osaka", "aichi", "kanagawa", "gifu", "mie"],
}

_recent_notified_keys = {}

def send_telegram_alert(store: dict, info: dict, notif_cfg: dict, is_test: bool = False) -> dict:
    """Send formatted alert to Telegram bot matching configured channel."""
    import urllib.request
    import urllib.parse
    import json

    tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
    tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()
    tg_enabled = notif_cfg.get("telegramEnabled", False) or is_test

    if not (tg_token and tg_chat_id):
        return {"status": "no_credentials"}
    if not tg_enabled:
        return {"status": "disabled"}

    # Calculate distance to JR Imamiya Station (lat=34.6540, lng=135.4925)
    imamiya_dist_str = ""
    st_lat = store.get("lat")
    st_lng = store.get("lng")
    if st_lat is not None and st_lng is not None:
        try:
            import math
            lat1, lon1 = float(st_lat), float(st_lng)
            lat2, lon2 = 34.6540, 135.4925
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            dist_km = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist_km < 1.0:
                imamiya_dist_str = f"{int(round(dist_km * 1000))} m"
            else:
                imamiya_dist_str = f"{dist_km:.1f} km"
        except Exception:
            pass

    store_name = store.get('name', 'Cửa hàng')
    store_chain = store.get('chain_label') or store.get('chain') or 'Tiện lợi'
    store_addr = store.get('address') or 'Khu vực đang chọn'
    maps_query = urllib.parse.quote_plus(f"{store_name} {store_addr}".strip())
    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}" if maps_query else ""
    time_display = info.get('reported_at', 'Vừa xong')
    if info.get('timeAgo'):
        time_display += f" ({info.get('timeAgo')})"

    packs_text = ", ".join(info.get("packs", [])) if info.get("packs") else "Gói thẻ Pokémon (Xem tại quán)"

    # History
    store_id = store.get("id") or ""
    history_list = []
    if store_id and store_id != "test_store_webhook":
        try:
            history_list = fetch_store_history(store_id) or []
        except Exception:
            pass
    elif is_test:
        history_list = [
            {"status_code": "o", "status_label": "🔴 Hết hàng", "note": "Hết đợt Terastal Festival", "formatted_time": "14:20 24/09"},
            {"status_code": "i", "status_label": "🟢 Có hàng", "note": "Về 2 box Terastal", "formatted_time": "09:15 24/09"}
        ]

    # Filter out current report if duplicated in history
    filtered_hist = []
    cur_ts = info.get("timestamp") or 0
    for h in history_list:
        h_ts = h.get("timestamp") or 0
        if cur_ts > 0 and abs(h_ts - cur_ts) < 180:
            continue
        filtered_hist.append(h)
        if len(filtered_hist) >= 3:
            break

    hist_text_tg_lines = []
    if filtered_hist:
        for item in filtered_hist:
            s_icon = "🟢" if item.get("status_code") == "i" else ("🔴" if item.get("status_code") == "o" else "⚪")
            t_str = item.get("formatted_time") or "Trước đó"
            note_str = f" ({item.get('note')})" if item.get("note") else ""
            hist_text_tg_lines.append(f"- {s_icon} {t_str}: {item.get('status_label', '')}{note_str}")

    dist_part = f" • 📍 ~{imamiya_dist_str}" if imamiya_dist_str else ""
    title_status = "🟢📸 CÓ HÀNG (XÁC NHẬN TẠI CHỖ)" if info.get("onsite") else "🟢 CÓ HÀNG (IN STOCK)"
    header = "🧪 <b>[THÔNG BÁO THỬ NGHIỆM]</b>\n" if is_test else f"🔥 <b>{title_status}!</b>\n"

    msg_lines = [
        f"{header}🏪 <b>{store_name}</b> ({store_chain})",
        f"📍 {store_addr}{dist_part}",
        f"📦 <b>Sản phẩm:</b> {packs_text}",
        f"⏱ <b>Thời gian báo:</b> {time_display}"
    ]
    if hist_text_tg_lines:
        msg_lines.append("\n📜 <b>Lịch sử báo cáo gần đây:</b>")
        msg_lines.extend(hist_text_tg_lines)
    if maps_url:
        msg_lines.append(f"\n🗺️ <a href=\"{maps_url}\">Mở Google Maps dẫn đường chính xác ↗</a>")

    tg_payload = {
        "chat_id": tg_chat_id,
        "text": "\n".join(msg_lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        tg_api_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        req = urllib.request.Request(
            tg_api_url,
            data=json.dumps(tg_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"status": "ok"}
    except Exception as te:
        return {"status": f"error: {str(te)}"}


@app.post("/api/notify/webhook")
async def send_webhook_notification(request: Request):
    """
    Dispatch in-stock notifications to Telegram Bot and Discord Webhook.
    Strictly applies exact user settings (Region, Status Filter, Time Window, Deduplication).
    """
    import urllib.request
    import urllib.parse
    import time
    
    try:
        body = await request.json()
        store = body.get("store") or {}
        info = body.get("info") or {}
        is_test = bool(body.get("is_test", False))
        
        user_settings = load_user_settings()
        notif_cfg = user_settings.get("notifications", {})
        results = {}

        # 1. Telegram Enabled Check
        tg_enabled = notif_cfg.get("telegramEnabled", False) or is_test
        if not tg_enabled:
            return JSONResponse(content={"status": "disabled", "reason": "telegram notifications disabled in settings"})

        # 2. Telegram Region Check
        tg_region = notif_cfg.get("telegramRegion", "osaka")
        if not is_test and tg_region != "all":
            allowed_prefs = REGION_PREFS.get(tg_region, ["osaka"])
            store_pref = (store.get("pref") or "").strip().lower()
            if not store_pref:
                sid = store.get("id")
                for p_name in ALL_PREFS:
                    if sid in get_stores_by_pref(p_name):
                        store_pref = p_name.lower()
                        break
            if not store_pref or store_pref not in allowed_prefs:
                return JSONResponse(content={"status": "filtered", "reason": f"pref '{store_pref}' not in telegram region '{tg_region}'"})

        # 3. Telegram Status Filter Check
        status_code = info.get("status_code") or info.get("code") or "i"
        tg_status = notif_cfg.get("telegramStatus", "in")
        if not is_test:
            if tg_status == "in" and status_code != "i":
                return JSONResponse(content={"status": "filtered", "reason": f"status '{status_code}' does not match telegramStatus '{tg_status}'"})
            if tg_status == "onsite" and (status_code != "i" or not info.get("onsite")):
                return JSONResponse(content={"status": "filtered", "reason": "not onsite in-stock"})
            if tg_status == "recent" and (status_code != "i" and not (info.get("timestamp", 0) > 0 and status_code != "n")):
                return JSONResponse(content={"status": "filtered", "reason": "not recent or in-stock"})

        # 4. Telegram Chain Filter Check
        tg_chain = notif_cfg.get("telegramChain", "all")
        store_chain = (store.get("chain") or "").lower()
        if not is_test and tg_chain != "all":
            if tg_chain == "conbini" and store_chain not in ["seven", "lawson", "familymart", "ministop"]:
                return JSONResponse(content={"status": "filtered", "reason": f"chain '{store_chain}' not in conbini"})
            elif tg_chain == "specialty" and store_chain != "specialty":
                return JSONResponse(content={"status": "filtered", "reason": f"chain '{store_chain}' not specialty"})
            elif tg_chain == "electronics" and store_chain not in ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi']:
                return JSONResponse(content={"status": "filtered", "reason": f"chain '{store_chain}' not electronics"})
            elif tg_chain not in ["conbini", "specialty", "electronics"] and store_chain != tg_chain:
                return JSONResponse(content={"status": "filtered", "reason": f"chain '{store_chain}' does not match '{tg_chain}'"})

        # 5. Telegram Time Window Check
        tg_time = notif_cfg.get("telegramTime", "24")
        if not is_test and tg_time != "all":
            try:
                max_seconds = int(tg_time) * 3600
                cur_now = time.time()
                rep_ts = info.get("timestamp") or 0
                if rep_ts > 0 and (cur_now - rep_ts > max_seconds):
                    return JSONResponse(content={"status": "filtered", "reason": f"report age exceeds {tg_time}h"})
            except Exception:
                pass

        # Ingest into SQLite database
        sid = store.get("id") or info.get("store_id")
        if sid:
            status_code_raw = info.get("status_code") or info.get("code") or "i"
            timestamp_raw = info.get("timestamp") or int(time.time())
            record_new_report(
                store_id=sid,
                status_code=status_code_raw,
                timestamp=timestamp_raw,
                onsite=bool(info.get("onsite", False)),
                packs=info.get("packs") or [],
                note=info.get("note") or "",
                user=info.get("user") or "匿名トレーナー",
                formatted_time=info.get("reported_at") or "",
                source="webhook" if is_test else "poketan"
            )

        # 6. Deduplication: do not spam the exact same report within 2 hours
        global _recent_notified_keys
        now_t = time.time()
        report_key = f"{store.get('id')}_{info.get('timestamp') or int(now_t // 300)}"
        if not is_test:
            if report_key in _recent_notified_keys and (now_t - _recent_notified_keys[report_key] < 7200):
                return JSONResponse(content={"status": "duplicate", "message": "Already notified recently"})
            _recent_notified_keys[report_key] = now_t
            _recent_notified_keys = {k: v for k, v in _recent_notified_keys.items() if now_t - v < 7200}

        # 7. Send notification
        tg_res = send_telegram_alert(store, info, notif_cfg, is_test=is_test)
        results["telegram"] = tg_res.get("status", "error")

        return JSONResponse(content={"status": "ok", "results": results})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


def _backfill_store_history_safe(store_id: str):
    """Safely fetch full history from PokéTan and save to SQLite in background."""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    try:
        remote_hist = fetch_store_history(clean_id)
        if remote_hist:
            save_bulk_history(clean_id, remote_hist, source="poketan")
    except Exception as e:
        print(f"  [DB] Background history backfill error for {clean_id}: {e}")


def telegram_background_watcher():
    """Background thread to continuously ingest hot reports from PokéTan into SQLite and dispatch Telegram alerts."""
    import time
    import threading
    time.sleep(5)
    print("  [DataSync & TelegramDaemon] Background daemon started (syncing reports & monitoring alerts)")
    is_first_scan = True
    while True:
        try:
            settings = load_user_settings()
            notif_cfg = settings.get("notifications", {})
            tg_enabled = bool(notif_cfg.get("telegramEnabled", False))
            tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
            tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()
            tg_ready = tg_enabled and bool(tg_token and tg_chat_id)

            tg_reg = notif_cfg.get("telegramRegion", "osaka")
            tg_target_prefs = REGION_PREFS.get(tg_reg, ["osaka"]) if tg_reg != "all" else ALL_PREFS
            tg_status = notif_cfg.get("telegramStatus", "in")
            tg_chain = notif_cfg.get("telegramChain", "all")
            tg_time = notif_cfg.get("telegramTime", "24")
            max_age_sec = int(tg_time) * 3600 if tg_time != "all" else 3600 * 24

            now_sec = time.time()

            # Poll all active prefectures to ingest real-time reports into SQLite database
            for pref in ALL_PREFS:
                try:
                    hot_data = fetch_realtime_status(pref, include_cold=False)
                    for k, raw in hot_data.items():
                        if k.endswith("_c"):
                            continue
                        sid = k
                        conf_raw = hot_data.get(f"{sid}_c")
                        parsed = parse_store_status(str(raw), str(conf_raw) if conf_raw else None)
                        if not parsed:
                            continue

                        ts = parsed.get("timestamp") or 0
                        code = parsed.get("status_code") or "u"
                        onsite = bool(parsed.get("onsite", False))
                        packs = parsed.get("packs") or []
                        rep_time = parsed.get("reported_at") or ""

                        # 1. Ingest report into SQLite database
                        is_new, rep = record_new_report(
                            store_id=sid,
                            status_code=code,
                            timestamp=ts,
                            onsite=onsite,
                            packs=packs,
                            formatted_time=rep_time,
                            source="poketan"
                        )

                        report_key = f"{sid}_{ts}_{code}"
                        if is_new and code == "i":
                            # Backfill rich history with notes/packs in background
                            threading.Thread(target=_backfill_store_history_safe, args=(sid,), daemon=True).start()

                        if is_first_scan:
                            _recent_notified_keys[report_key] = now_sec
                            continue

                        # 2. Check Telegram Alert Conditions
                        if tg_ready and pref in tg_target_prefs:
                            if tg_status == "in" and code != "i":
                                continue
                            if tg_status == "onsite" and (code != "i" or not onsite):
                                continue
                            if tg_status == "recent" and (code != "i" and not (ts > 0 and code != "n")):
                                continue

                            if ts > 0 and (now_sec - ts > max_age_sec):
                                continue

                            st = db_get_store_by_id(sid) or get_stores_by_pref(pref).get(sid) or {"id": sid, "name": sid, "pref": pref}
                            st["pref"] = pref
                            st_chain = (st.get("chain") or "").lower()

                            if tg_chain != "all":
                                if tg_chain == "conbini" and st_chain not in ["seven", "lawson", "familymart", "ministop"]:
                                    continue
                                elif tg_chain == "specialty" and st_chain != "specialty":
                                    continue
                                elif tg_chain == "electronics" and st_chain not in ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi']:
                                    continue
                                elif tg_chain not in ["conbini", "specialty", "electronics"] and st_chain != tg_chain:
                                    continue

                            if report_key not in _recent_notified_keys:
                                _recent_notified_keys[report_key] = now_sec
                                print(f"  [TelegramDaemon] Auto-dispatching Telegram alert for {st.get('name')}")
                                send_telegram_alert(st, parsed, notif_cfg, is_test=False)
                except Exception as pe:
                    pass

            is_first_scan = False
        except Exception as e:
            pass
        time.sleep(35)


@app.post("/api/record_report")
async def record_report_endpoint(request: Request):
    """
    Ingest a newly observed report into local SQLite store_history and update store status.
    Called when Firestore onSnapshot fires on the client or via external reporting.
    """
    import time
    import threading
    try:
        body = await request.json()
        store_id = body.get("store_id")
        if not store_id:
            return JSONResponse(status_code=400, content={"error": "store_id required"})
        
        status_code = body.get("status_code") or body.get("code") or "i"
        timestamp = body.get("timestamp") or int(time.time())
        onsite = bool(body.get("onsite", False))
        packs = body.get("packs") or []
        note = body.get("note") or ""
        user = body.get("user") or "匿名トレーナー"
        who = body.get("who") or ""
        formatted_time = body.get("formatted_time")
        source = body.get("source") or "poketan"

        is_new, rep = record_new_report(
            store_id=store_id,
            status_code=status_code,
            timestamp=timestamp,
            onsite=onsite,
            packs=packs,
            note=note,
            user=user,
            who=who,
            formatted_time=formatted_time,
            source=source
        )

        if is_new and status_code == "i":
            threading.Thread(target=_backfill_store_history_safe, args=(store_id,), daemon=True).start()

        return JSONResponse(content={"status": "ok", "is_new": is_new, "report": rep})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


_pref_stores_cache = {}
_cold_cache = {}

def get_stores_by_pref(pref: str) -> dict:
    global _pref_stores_cache
    if pref not in _pref_stores_cache:
        try:
            stores = fetch_stores(pref=pref)
            for sid, store in stores.items():
                store["pref"] = pref
            _pref_stores_cache[pref] = stores
            print(f"  [RegionLoader] Loaded {len(stores)} stores from {pref}")
        except Exception as e:
            print(f"  [RegionLoader] Error loading stores from {pref}: {e}")
            _pref_stores_cache[pref] = {}
    return _pref_stores_cache[pref]

def get_target_prefs(region: Optional[str] = None, pref: Optional[str] = None) -> List[str]:
    if region:
        r = region.strip().lower()
        if r in REGION_PREFS:
            return REGION_PREFS[r]
    if pref:
        p = pref.strip().lower()
        if p in REGION_PREFS:
            return REGION_PREFS[p]
        if p in ALL_PREFS:
            return [p]
    return ["osaka"]

def fetch_single_pref_status(pref, is_cold=False):
    doc_path = f"status/{pref}_cold" if is_cold else f"status/{pref}"
    try:
        return fetch_firestore_document(doc_path)
    except Exception as e:
        return {}

@app.get("/api/stores_data")
def get_stores_data(region: Optional[str] = None, pref: Optional[str] = None):
    try:
        stores = db_get_stores(region=region, pref=pref)
        if stores:
            return JSONResponse(content=stores)
    except Exception as e:
        print("[DB] Error querying stores from SQLite:", e)

    target_prefs = get_target_prefs(region, pref)
    all_stores = {}
    for p in target_prefs:
        all_stores.update(get_stores_by_pref(p))
    return JSONResponse(content=all_stores)

@app.get("/api/cold_status")
def get_cold_status(region: Optional[str] = None, pref: Optional[str] = None):
    global _cold_cache
    target_prefs = get_target_prefs(region, pref)
    missing_prefs = [p for p in target_prefs if p not in _cold_cache]
    if missing_prefs:
        try:
            with ThreadPoolExecutor(max_workers=min(5, len(missing_prefs))) as ex:
                futures = {ex.submit(fetch_single_pref_status, p, True): p for p in missing_prefs}
                for f, p in futures.items():
                    _cold_cache[p] = f.result()
        except Exception as e:
            print("Cold status error:", e)
    
    merged = {}
    for p in target_prefs:
        if p in _cold_cache:
            merged.update(_cold_cache[p])
    return JSONResponse(content=merged)

@app.get("/api/hot_status")
def get_hot_status(region: Optional[str] = None, pref: Optional[str] = None):
    target_prefs = get_target_prefs(region, pref)
    try:
        merged = {}
        with ThreadPoolExecutor(max_workers=min(5, len(target_prefs))) as ex:
            futures = [ex.submit(fetch_single_pref_status, p, False) for p in target_prefs]
            for f in futures:
                merged.update(f.result())
        return JSONResponse(content=merged)
    except Exception as e:
        print("Error fetching hot status:", e)
        return JSONResponse(content={})

@app.get("/api/store_history/{store_id}")
def get_store_history(store_id: str):
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    try:
        local_hist = db_get_store_history(clean_id, limit=30)
        # If fewer than 2 records, backfill from PokéTan and save into SQLite
        if len(local_hist) < 2:
            try:
                remote_hist = fetch_store_history(clean_id)
                if remote_hist:
                    save_bulk_history(clean_id, remote_hist, source="poketan")
                    local_hist = db_get_store_history(clean_id, limit=30)
            except Exception as e:
                print(f"[DB] Error backfilling history for {clean_id}: {e}")
        return JSONResponse(content=local_hist)
    except Exception as e:
        print(f"Error fetching history for {clean_id}:", e)
        try:
            return JSONResponse(content=fetch_store_history(clean_id))
        except Exception:
            return JSONResponse(content=[])

@app.get("/api/report_counts")
def get_report_counts(region: Optional[str] = None, pref: Optional[str] = None):
    try:
        counts = db_get_report_counts(region=region, pref=pref)
        return JSONResponse(content=counts)
    except Exception as e:
        print("[DB] Error fetching SQL report counts:", e)
        return JSONResponse(content={})



@app.get("/api/config")
def get_config():
    user_settings = load_user_settings()
    notif = user_settings.get("notifications", {})
    return {
        "apiKey": FIREBASE_API_KEY,
        "projectId": PROJECT_ID,
        "chainNames": CHAIN_NAMES,
        "packCodes": PACK_CODES,
        "telegramEnabled": bool(notif.get("telegramEnabled", False)),
        "soundEnabled": bool(notif.get("soundEnabled", True)),
        "telegramBotToken": notif.get("telegramBotToken", ""),
        "telegramChatId": notif.get("telegramChatId", ""),
        "telegramBotTokenSet": bool(notif.get("telegramBotToken")),
        "telegramChatIdSet": bool(notif.get("telegramChatId")),
        "telegramStatus": notif.get("telegramStatus", "in"),
        "telegramChain": notif.get("telegramChain", "all"),
        "telegramTime": str(notif.get("telegramTime", "24")),
        "telegramRegion": notif.get("telegramRegion", "osaka"),
        "currentRegion": user_settings.get("currentRegion", "osaka"),
        "activeFilter": user_settings.get("activeFilter", "all"),
        "activeTime": user_settings.get("activeTime", "all")
    }


@app.get("/api/calendar")
def get_calendar(include_expired: bool = False):
    return fetch_calendar_events(include_expired=include_expired)


from .templates import render_map_page, render_thongbao_page


@app.get("/", response_class=HTMLResponse)
@app.get("/map", response_class=HTMLResponse)
@app.get("/calendar", response_class=HTMLResponse)
@app.get("/events", response_class=HTMLResponse)
def map_page():
    return HTMLResponse(content=render_map_page())


@app.get("/thongbao", response_class=HTMLResponse)
@app.get("/stores", response_class=HTMLResponse)
def thongbao_page():
    return HTMLResponse(content=render_thongbao_page())


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            port = 8080
    else:
        import socket
        port = 8080
        for test_port in [8080, 8081, 8082, 8888, 5000]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', test_port)) != 0:
                    port = test_port
                    break

    print("=================================================================")
    print("🚀 BAWUI POKE APP - Instant Real-Time Push Dashboard")
    print(f"👉 Mở trình duyệt tại: http://localhost:{port}")
    print("=================================================================")

    # Start 24/7 background Telegram stock watcher daemon
    import threading
    watcher_thread = threading.Thread(target=telegram_background_watcher, daemon=True)
    watcher_thread.start()

    uvicorn.run("app.web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
