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


def telegram_background_watcher():
    """Background thread to poll Firestore for new in-stock reports matching Telegram filter settings and send alerts."""
    import time
    time.sleep(8)
    print("  [TelegramDaemon] Background stock monitor daemon started (polling every 35s)")
    is_first_scan = True
    while True:
        try:
            settings = load_user_settings()
            notif_cfg = settings.get("notifications", {})
            if not notif_cfg.get("telegramEnabled", False):
                time.sleep(30)
                continue
            
            tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
            tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()
            if not (tg_token and tg_chat_id):
                time.sleep(30)
                continue
            
            tg_reg = notif_cfg.get("telegramRegion", "osaka")
            target_prefs = REGION_PREFS.get(tg_reg, ["osaka"])
            if tg_reg == "all":
                target_prefs = ALL_PREFS
            
            tg_status = notif_cfg.get("telegramStatus", "in")
            tg_chain = notif_cfg.get("telegramChain", "all")
            tg_time = notif_cfg.get("telegramTime", "24")
            max_age_sec = int(tg_time) * 3600 if tg_time != "all" else 3600 * 24

            now_sec = time.time()
            for pref in target_prefs:
                try:
                    hot_data = fetch_realtime_status(pref, include_cold=False)
                    pref_stores = get_stores_by_pref(pref)
                    for sid, raw in hot_data.items():
                        parsed = parse_store_status(str(raw))
                        if not parsed:
                            continue
                        
                        ts = parsed.get("timestamp") or 0
                        report_key = f"{sid}_{ts}"

                        if is_first_scan:
                            # Seed existing reports on startup so we only notify for fresh incoming reports
                            _recent_notified_keys[report_key] = now_sec
                            continue

                        code = parsed.get("status_code")
                        if tg_status == "in" and code != "i":
                            continue
                        if tg_status == "onsite" and (code != "i" or not parsed.get("onsite")):
                            continue
                        
                        if ts > 0 and (now_sec - ts > max_age_sec):
                            continue

                        st = pref_stores.get(sid) or {"id": sid, "name": sid, "pref": pref}
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
                except Exception:
                    pass
            is_first_scan = False
        except Exception:
            pass
        time.sleep(35)


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
    try:
        return JSONResponse(content=fetch_store_history(store_id))
    except Exception as e:
        print(f"Error fetching history for {store_id}:", e)
        return JSONResponse(content=[])

_report_counts_cache = {}
_report_counts_time = {}

@app.get("/api/report_counts")
def get_report_counts(region: Optional[str] = None, pref: Optional[str] = None):
    global _report_counts_cache, _report_counts_time
    import time
    now = time.time()
    target_prefs = get_target_prefs(region, pref)
    cache_key = "_".join(sorted(target_prefs))

    if cache_key in _report_counts_cache and (now - _report_counts_time.get(cache_key, 0) < 60):
        return JSONResponse(content=_report_counts_cache[cache_key])

    try:
        merged_counts = {}
        for p in target_prefs:
            try:
                hot = fetch_realtime_status(p, include_cold=False)
                in_stores = [k for k, v in hot.items() if str(v).startswith('i')]
                for sid in in_stores:
                    try:
                        h = fetch_store_history(sid)
                        merged_counts[sid] = {
                            "in": sum(1 for x in h if x.get("status_code") == "i"),
                            "out": sum(1 for x in h if x.get("status_code") == "o")
                        }
                    except Exception:
                        merged_counts[sid] = {"in": 1, "out": 0}
            except Exception as pe:
                print(f"Error fetching counts for pref {p}:", pe)

        _report_counts_cache[cache_key] = merged_counts
        _report_counts_time[cache_key] = now
        return JSONResponse(content=merged_counts)
    except Exception as e:
        print("Error fetching report counts:", e)
        return JSONResponse(content=_report_counts_cache.get(cache_key, {}))



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
