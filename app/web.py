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


@app.get("/", response_class=HTMLResponse)
@app.get("/map", response_class=HTMLResponse)
@app.get("/stores", response_class=HTMLResponse)
@app.get("/thongbao", response_class=HTMLResponse)
@app.get("/calendar", response_class=HTMLResponse)
@app.get("/events", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>ポケ探 - ポケモンカード在庫マップ &amp; リアルタイム速報</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  
  <!-- Leaflet MarkerCluster -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  
  <!-- Font Inter -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  
  <!-- Firebase JS SDK for real-time Firestore sync -->
  <script type="module">
    import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js';
    import { initializeFirestore, doc, onSnapshot } from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js';
    window.FirebaseInit = { initializeApp, initializeFirestore, doc, onSnapshot };
  </script>

  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
      -webkit-tap-highlight-color: transparent;
    }
    html, body {
      width: 100%;
      height: 100%;
      height: 100dvh;
      overflow: hidden;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
      touch-action: pan-x pan-y;
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
      overscroll-behavior: none;
    }

    /* 1. TOP HEADER (White, Clean, matching PokéTan reference) */
    #poketan-header {
      height: 52px;
      background: #ffffff;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 12px;
      z-index: 1000;
      flex-shrink: 0;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
    }

    .header-brand-group {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand-logo-area {
      display: flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
      color: #0f172a;
    }
    .brand-pin-icon {
      width: 24px;
      height: 24px;
      background: #4f46e5;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-left: 2px;
    }
    .brand-pin-icon::after {
      content: '';
      width: 9px;
      height: 9px;
      background: #ffffff;
      border-radius: 50%;
    }
    .brand-title-text {
      font-weight: 900;
      font-size: 1.15rem;
      letter-spacing: -0.03em;
      color: #1e1b4b;
    }

    /* Location selector pill */
    .location-pill {
      display: flex;
      flex-direction: column;
      justify-content: center;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 3px 10px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .location-pill:hover {
      background: #e2e8f0;
    }
    .loc-main-title {
      font-size: 0.76rem;
      font-weight: 800;
      color: #1e293b;
      display: flex;
      align-items: center;
      gap: 4px;
      line-height: 1.2;
    }
    .loc-sub-title {
      font-size: 0.62rem;
      color: #64748b;
      font-weight: 600;
      line-height: 1.1;
    }

    .header-menu-btn {
      width: 38px;
      height: 38px;
      background: none;
      border: none;
      font-size: 1.35rem;
      color: #334155;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
    }
    .header-menu-btn:hover {
      background: #f1f5f9;
    }

    /* 2. FLOATING SUB-HEADER FILTER BAR (Over Map) */
    #filter-bar-container {
      position: absolute;
      top: 60px;
      left: 10px;
      right: 10px;
      z-index: 1000;
      pointer-events: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .filter-chips-scroll {
      pointer-events: auto;
      display: flex;
      gap: 6px;
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      padding-bottom: 2px;
    }
    .filter-chips-scroll::-webkit-scrollbar { display: none; }

    .poketan-chip {
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      padding: 6px 12px;
      font-size: 0.74rem;
      font-weight: 700;
      color: #334155;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
      white-space: nowrap;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .poketan-chip:hover {
      border-color: #94a3b8;
      background: #f8fafc;
    }
    .poketan-chip.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
    }
    .poketan-chip.chip-secondary {
      background: #f8fafc;
      border-color: #e2e8f0;
      font-size: 0.71rem;
      font-weight: 600;
      color: #475569;
    }
    .poketan-chip.chip-secondary:hover {
      background: #ffffff;
      border-color: #cbd5e1;
    }
    .poketan-chip.chip-secondary.active {
      background: #f5f3ff;
      border-color: #6366f1;
      color: #4f46e5;
      font-weight: 700;
      box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
    }

    select.poketan-chip {
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      padding-right: 24px;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' fill='%23475569' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: calc(100% - 8px) center;
      cursor: pointer;
      font-family: inherit;
      outline: none;
    }
    select.poketan-chip.active {
      background-color: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
    }

    .chip-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .dot-green { background: #22c55e; }
    .dot-yellow { background: #eab308; }
    .dot-red { background: #ef4444; }
    .dot-gray { background: #94a3b8; }
    .dot-blue { background: #3b82f6; }

    /* List Tab Chips */
    .list-tab-chip {
      padding: 6px 12px;
      border-radius: 99px;
      border: 1px solid #e2e8f0;
      background: #f8fafc;
      color: #64748b;
      font-size: 0.74rem;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .list-tab-chip:hover {
      background: #e2e8f0;
    }
    .list-tab-chip.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      font-weight: 800;
    }

    /* FILTER MODAL & TRIGGER BUTTON */
    .chip-main-filter {
      background: #0f172a !important;
      color: #ffffff !important;
      border-color: #0f172a !important;
      box-shadow: 0 3px 10px rgba(15, 23, 42, 0.25) !important;
    }
    .chip-main-filter:hover {
      background: #1e293b !important;
    }
    .filter-count-pill {
      background: #3b82f6;
      color: #ffffff;
      font-size: 0.65rem;
      font-weight: 800;
      padding: 1px 6px;
      border-radius: 10px;
      line-height: 1.2;
    }
    .filter-section-title {
      font-size: 0.8rem;
      font-weight: 800;
      color: #1e293b;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .filter-options-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .filter-option-btn {
      padding: 7px 11px;
      border-radius: 10px;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      color: #334155;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s ease;
    }
    .filter-option-btn:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }
    .filter-option-btn.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      font-weight: 800;
      box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
    }
    .btn-apply-filter {
      flex: 1;
      padding: 11px;
      background: #4f46e5;
      color: white;
      border: none;
      border-radius: 10px;
      font-weight: 800;
      font-size: 0.85rem;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
      transition: background 0.15s;
    }
    .btn-apply-filter:hover {
      background: #4338ca;
    }
    .btn-reset-filter {
      padding: 11px 16px;
      background: #f1f5f9;
      color: #475569;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.82rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-reset-filter:hover {
      background: #e2e8f0;
      color: #1e293b;
    }

    /* REAL-TIME STOCK TOAST (Exact Image 3 replica) */
    #live-stock-toast {
      pointer-events: auto;
      background: #ffffff;
      border-radius: 12px;
      padding: 8px 12px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.14);
      border: 1px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-size: 0.75rem;
      cursor: pointer;
      animation: slideDown 0.3s ease;
      max-width: 480px;
    }
    @keyframes slideDown {
      from { transform: translateY(-10px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .toast-info {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .toast-close-btn {
      background: none;
      border: none;
      color: #94a3b8;
      font-size: 0.85rem;
      font-weight: 700;
      cursor: pointer;
      padding: 0 4px;
    }

    /* REGION SWITCH & LOAD TOAST */
    #region-load-toast {
      display: none;
      align-items: center;
      gap: 6px;
      margin: 2px auto 0 auto;
      padding: 6px 14px;
      background: #0f172a;
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.4);
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 700;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
      animation: slideDown 0.25s ease;
      z-index: 1000;
      white-space: nowrap;
      pointer-events: auto;
    }

    /* 3. MAIN MAP AREA (Full viewport coverage, zero gray cutoffs) */
    #app-main {
      flex: 1;
      min-height: 0;
      width: 100%;
      height: 100%;
      position: relative;
      overflow: hidden;
      touch-action: none;
      overscroll-behavior: none;
    }

    #map, .leaflet-container {
      width: 100%;
      height: 100%;
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 1;
      touch-action: none !important;
      -webkit-touch-callout: none;
      -webkit-user-select: none;
      user-select: none;
      overscroll-behavior: none;
      cursor: grab;
    }
    #map:active, .leaflet-container:active {
      cursor: grabbing;
    }
    .leaflet-tile {
      image-rendering: -webkit-optimize-contrast;
    }

    /* FLOATING GPS BUTTON (Bottom Right - High z-index to stay above all Leaflet layers) */
    #gps-btn {
      position: absolute;
      bottom: 20px;
      right: 20px;
      z-index: 1500;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #4f46e5;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.35rem;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    }
    #gps-btn:hover {
      background: #eff6ff;
      transform: scale(1.08);
      border-color: #3b82f6;
    }
    #gps-btn:active {
      transform: scale(0.92);
      background: #e0e7ff;
    }
    #gps-btn.locating {
      border-color: #3b82f6;
      animation: gpsPulseAnim 0.8s infinite alternate;
    }
    @keyframes gpsPulseAnim {
      from { transform: scale(1); box-shadow: 0 0 6px rgba(59, 130, 246, 0.5); }
      to { transform: scale(1.1); box-shadow: 0 0 18px rgba(59, 130, 246, 0.9); }
    }

    /* USER LOCATION MARKER */
    .user-location-marker {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #4f46e5;
      border: 3px solid #ffffff;
      box-shadow: 0 0 10px rgba(79, 70, 229, 0.8);
      position: relative;
    }
    .user-location-marker::after {
      content: '';
      position: absolute;
      top: -6px;
      left: -6px;
      right: -6px;
      bottom: -6px;
      border-radius: 50%;
      border: 2px solid #818cf8;
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 1; }
      100% { transform: scale(2.2); opacity: 0; }
    }

    /* 4. MARKERCLUSTER STYLES (Matching PokéTan Image 3: Blue border circles ② ③) */
    .poketan-cluster-wrap {
      background: transparent;
      border: none;
    }
    .poketan-cluster {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #4f46e5;
      color: #1e1b4b;
      font-weight: 800;
      font-size: 0.84rem;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
      transition: transform 0.15s ease;
    }
    .poketan-cluster:hover {
      transform: scale(1.1);
    }
    .poketan-cluster.has-stock {
      border-color: #16a34a;
      box-shadow: 0 0 12px rgba(22, 163, 74, 0.6);
    }

    /* IN-STOCK PIN MARKER WITH TIME BADGE */
    .poketan-pin-wrap, .poketan-pin-leaflet-icon {
      background: transparent;
      border: none;
    }
    .poketan-pin-wrapper {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      pointer-events: auto;
    }
    .poketan-stock-pin {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #16a34a;
      border: 2.5px solid #ffffff;
      box-shadow: 0 0 10px rgba(22, 163, 74, 0.8), 0 3px 6px rgba(0,0,0,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.95rem;
      cursor: pointer;
      animation: bouncePin 1.6s infinite;
      flex-shrink: 0;
    }
    .poketan-pin-time-pill {
      background: rgba(15, 23, 42, 0.92);
      color: #4ade80;
      font-size: 0.65rem;
      font-weight: 800;
      padding: 2px 7px;
      border-radius: 10px;
      border: 1px solid rgba(74, 222, 128, 0.45);
      white-space: nowrap;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      backdrop-filter: blur(4px);
      letter-spacing: 0.02em;
      pointer-events: auto;
    }
    @keyframes bouncePin {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    /* 5. FOOTER (Exact Image 2 replica: White bar with Gachi Meguri center button + Settings) */
    #poketan-footer {
      height: calc(56px + env(safe-area-inset-bottom, 0px));
      padding-bottom: env(safe-area-inset-bottom, 0px);
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      display: flex;
      align-items: stretch;
      justify-content: space-around;
      z-index: 1000;
      flex-shrink: 0;
      box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
      position: relative;
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
    }

    .footer-tab-btn {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 2px;
      background: none;
      border: none;
      color: #64748b;
      font-size: 0.6rem;
      font-weight: 700;
      cursor: pointer;
      position: relative;
      padding: 4px 1px;
      transition: color 0.15s;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    .footer-tab-btn .tab-icon {
      font-size: 1.15rem;
      line-height: 1;
    }
    .footer-tab-btn .tab-label {
      font-size: 0.56rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }

    /* Active blue top indicator line (Image 2) */
    .footer-tab-btn.active {
      color: #4f46e5;
    }
    .footer-tab-btn.active::after {
      content: '';
      position: absolute;
      top: 0;
      left: 14%;
      right: 14%;
      height: 3px;
      background: #4f46e5;
      border-radius: 0 0 3px 3px;
    }

    /* Elevated center button: Gachi Meguri (Image 2) */
    .gachi-meguri-wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-end;
      cursor: pointer;
      flex: 0 0 52px;
      padding-bottom: 4px;
      -webkit-tap-highlight-color: transparent;
    }
    .gachi-meguri-btn {
      position: relative;
      top: -10px;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.45);
      border: 3px solid #ffffff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: white;
      cursor: pointer;
      flex-shrink: 0;
      z-index: 1010;
      transition: transform 0.15s;
    }
    .gachi-meguri-btn:active {
      transform: scale(0.92);
    }
    .gachi-meguri-btn .btn-icon {
      font-size: 1.4rem;
      line-height: 1;
      filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2));
    }
    .gachi-meguri-label {
      font-size: 0.56rem;
      font-weight: 800;
      color: #4f46e5;
      margin-top: 1px;
      white-space: nowrap;
    }

    /* 6. LIST VIEW (Sliding Sheet / Tab) */
    #view-list-container {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: calc(56px + env(safe-area-inset-bottom, 0px));
      background: #ffffff;
      z-index: 800;
      display: none;
      flex-direction: column;
    }
    #view-list-container.open {
      display: flex;
    }

    .list-header-bar {
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .list-search-box {
      flex: 1;
      position: relative;
    }
    .list-search-box input {
      width: 100%;
      height: 36px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 0 12px 0 32px;
      font-size: 0.8rem;
      outline: none;
    }
    .list-search-box .icon {
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 0.75rem;
      color: #64748b;
    }
    .list-sort-bar {
      padding: 7px 14px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #ffffff;
    }
    .list-sort-btn {
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      padding: 4px 10px;
      font-size: 0.72rem;
      font-weight: 700;
      color: #475569;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      transition: all 0.15s ease;
    }
    .list-sort-btn:hover {
      background: #e2e8f0;
    }
    .list-sort-btn.active {
      background: #3b82f6;
      border-color: #2563eb;
      color: #ffffff;
      box-shadow: 0 1px 4px rgba(37, 99, 235, 0.25);
    }

    .list-cards-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 8px 12px;
    }
    .store-list-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 10px 12px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      transition: background 0.12s;
    }
    .store-list-card:hover {
      background: #f8fafc;
    }
    .card-left-info {
      min-width: 0;
      flex: 1;
    }
    .card-store-name {
      font-weight: 800;
      font-size: 0.88rem;
      color: #0f172a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .card-chain-time {
      font-size: 0.72rem;
      color: #64748b;
      margin-top: 2px;
    }
    .card-badge {
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 800;
      flex-shrink: 0;
      margin-left: 10px;
    }
    .badge-in { background: #dcfce7; color: #15803d; }
    .badge-out { background: #fee2e2; color: #b91c1c; }
    .badge-none { background: #f1f5f9; color: #64748b; }

    /* 7. PREFECTURE & AREA MODAL (Dead-centered on all screens) */
    .modal-overlay {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      bottom: 0 !important;
      width: 100vw !important;
      height: 100vh !important;
      height: 100dvh !important;
      background: rgba(15, 23, 42, 0.55) !important;
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 9999 !important;
      display: none;
      align-items: center !important;
      justify-content: center !important;
      padding: 16px;
      box-sizing: border-box;
      margin: 0 !important;
    }
    .modal-overlay.open {
      display: flex !important;
    }
    .modal-card {
      background: #ffffff;
      border-radius: 20px;
      width: 100%;
      max-width: 440px;
      max-height: 88vh;
      max-height: 88dvh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
      animation: modalFadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
      margin: auto !important;
      position: relative;
    }
    @keyframes modalFadeIn {
      from { transform: scale(0.96) translateY(8px); opacity: 0; }
      to { transform: scale(1) translateY(0); opacity: 1; }
    }
    .modal-header {
      padding: 16px 20px 14px 20px;
      border-bottom: 1px solid #f1f5f9;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #ffffff;
    }
    .modal-header h3 {
      font-size: 1.05rem;
      font-weight: 800;
      color: #0f172a;
      margin: 0;
    }
    .modal-close-btn {
      background: #f1f5f9;
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.95rem;
      color: #64748b;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }
    .modal-close-btn:hover {
      background: #e2e8f0;
      color: #0f172a;
    }
    .modal-body {
      padding: 16px 20px 22px 20px;
      max-height: 75vh;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
    }

    /* Area Search & Selection (Exact PokéTan Reference Replica) */
    .area-search-row {
      display: flex;
      gap: 8px;
      margin-bottom: 10px;
    }
    .area-search-input {
      flex: 1;
      height: 42px;
      background: #f1f5f9;
      border: 1.5px solid transparent;
      border-radius: 12px;
      padding: 0 14px;
      font-size: 0.86rem;
      color: #1e293b;
      outline: none;
      transition: all 0.15s ease;
    }
    .area-search-input:focus {
      background: #ffffff;
      border-color: #4f46e5;
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
    }
    .area-search-btn {
      height: 42px;
      background: #4f46e5;
      color: #ffffff;
      border: none;
      border-radius: 12px;
      padding: 0 18px;
      font-weight: 700;
      font-size: 0.88rem;
      cursor: pointer;
      transition: background 0.15s;
      white-space: nowrap;
    }
    .area-search-btn:hover {
      background: #4338ca;
    }
    .area-gps-btn {
      width: 100%;
      height: 44px;
      background: #f5f3ff;
      border: 1px solid #e0e7ff;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      font-size: 0.88rem;
      font-weight: 700;
      color: #4f46e5;
      cursor: pointer;
      transition: all 0.15s;
    }
    .area-gps-btn:hover {
      background: #ede9fe;
    }
    .area-notice-text {
      font-size: 0.72rem;
      color: #64748b;
      line-height: 1.45;
      margin: 10px 0 12px 0;
    }
    .area-vote-box {
      background: #f1f5fd;
      border: 1px solid #e0e7ff;
      border-radius: 14px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .area-vote-box:hover {
      background: #e8edfb;
    }
    .area-section {
      margin-bottom: 14px;
    }
    .area-section-title {
      font-size: 0.82rem;
      font-weight: 800;
      color: #1e293b;
      margin-bottom: 8px;
    }
    .area-chips-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .area-chip {
      padding: 6px 14px;
      border-radius: 9999px;
      border: 1px solid #d1d5db;
      background: #ffffff;
      color: #1e293b;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .area-chip:hover {
      border-color: #6366f1;
      background: #f8fafc;
      color: #4f46e5;
    }
    .area-chip.active {
      border: 1.5px solid #4f46e5;
      color: #4f46e5;
      background: #eef2ff;
      font-weight: 800;
    }
    .pref-item-btn {
      width: 100%;
      padding: 12px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: white;
      font-weight: 700;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .pref-item-btn:hover {
      background: #f8fafc;
      border-color: #cbd5e1;
    }
    .pref-item-btn.selected {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
    }

    /* LEAFLET POPUP STYLES */
    .leaflet-popup-content-wrapper {
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      padding: 0;
      overflow: hidden;
    }
    .leaflet-popup-content {
      margin: 0;
      padding: 14px 16px;
      min-width: 250px;
      max-width: 330px;
      height: auto !important;
      color: #0f172a;
    }
    .popup-store-title {
      font-weight: 800;
      font-size: 0.95rem;
      line-height: 1.3;
    }
    .popup-store-chain {
      font-size: 0.72rem;
      color: #4f46e5;
      font-weight: 700;
      margin-top: 2px;
    }
    .popup-status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 800;
      font-size: 0.82rem;
      padding: 5px 10px;
      border-radius: 8px;
      margin: 8px 0 6px 0;
      width: 100%;
    }
    .popup-report-counts-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 4px 0 8px 0;
      flex-wrap: wrap;
    }
    .report-count-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 9px;
      border-radius: 12px;
      font-size: 0.72rem;
      font-weight: 700;
      line-height: 1.2;
    }
    .report-count-tag.tag-green {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      color: #15803d;
    }
    .report-count-tag.tag-red {
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #b91c1c;
    }
    .report-count-tag .count-badge-icon {
      font-size: 0.76rem;
      line-height: 1;
    }
    .report-count-tag .count-badge-val {
      font-size: 0.82rem;
      font-weight: 800;
    }
    .popup-actions-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-top: 10px;
    }
    .btn-popup-maps {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 8px 6px;
      background: #4f46e5;
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.74rem;
      border: none;
      cursor: pointer;
      text-align: center;
      transition: background 0.15s;
    }
    .btn-popup-maps:hover {
      background: #4338ca;
    }
    .btn-popup-hist {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 8px 6px;
      background: #0f172a;
      color: white;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.74rem;
      border: none;
      cursor: pointer;
      text-align: center;
      transition: background 0.15s;
    }
    .btn-popup-hist:hover {
      background: #1e293b;
    }
    .popup-hist-scroll {
      margin-top: 10px;
      padding-top: 8px;
      border-top: 1px dashed #cbd5e1;
      max-height: 190px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .popup-hist-scroll::-webkit-scrollbar {
      width: 4px;
    }
    .popup-hist-scroll::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 4px;
    }

    /* LOADING SPINNER */
    #loading-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: #ffffff;
      z-index: 2000;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #0f172a;
      transition: opacity 0.3s ease;
    }
    .spinner {
      width: 36px;
      height: 36px;
      border: 3.5px solid #e2e8f0;
      border-top-color: #4f46e5;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

  <!-- LOADING SCREEN -->
  <div id="loading-overlay">
    <div class="spinner"></div>
    <div style="margin-top: 12px; font-weight: 800; font-size: 0.85rem;" id="loading-text">
      店舗データを読み込み中...
    </div>
  </div>

  <!-- 1. TOP HEADER (Exact Image 3 replica) -->
  <header id="poketan-header">
    <div class="header-brand-group">
      <a href="/" class="brand-logo-area">
        <div class="brand-pin-icon"></div>
        <span class="brand-title-text">ポケ探</span>
      </a>

      <!-- Location Area Selector Pill -->
      <div class="location-pill" onclick="openPrefModal()">
        <div class="loc-main-title">
          <span>📍</span>
          <span id="header-loc-name">なんば周辺</span>
          <span style="font-size:0.6rem; color:#64748b;">▼</span>
        </div>
        <div class="loc-sub-title">エリアを変える</div>
      </div>
    </div>

    <!-- Right Button Group -->
    <div style="display:flex; align-items:center; gap:6px;">
      <button class="header-menu-btn" onclick="openTelegramModal()" title="Cấu hình Telegram & Bộ lọc cảnh báo" style="background:#0284c7; color:#ffffff; font-size:0.95rem; border:none; display:flex; align-items:center; justify-content:center; box-shadow:0 1px 3px rgba(2,132,199,0.3); border-radius:8px; width:34px; height:34px; cursor:pointer;">
        ✈️
      </button>
      <button class="header-menu-btn" onclick="openSettingsModal()" title="Cài đặt hệ thống">
        ☰
      </button>
    </div>
  </header>

  <!-- 2. FLOATING SUB-HEADER FILTER BAR (Bản đồ: Bộ lọc & Phím tắt nhanh) -->
  <div id="filter-bar-container">
    <div class="filter-chips-scroll">
      <!-- Nút mở Modal Bộ lọc Bản đồ -->
      <button class="poketan-chip chip-main-filter" id="btn-map-filter" onclick="openMapFilterModal()" title="Mở bộ lọc bản đồ">
        <span>⚙️ Bộ lọc</span>
        <span id="map-filter-badge" class="filter-count-pill" style="display:none; background:#38bdf8; color:#0f172a;">0</span>
      </button>

      <!-- Trạng thái hàng hóa trên bản đồ -->
      <button class="poketan-chip active" id="map-chip-all" onclick="setMapStatusFilter('all')">
        🌐 Tất cả
      </button>
      <button class="poketan-chip" id="map-chip-in" onclick="setMapStatusFilter('in')">
        <span class="chip-dot dot-green"></span> 🟢 Có hàng
      </button>
      <button class="poketan-chip" id="map-chip-recent" onclick="setMapStatusFilter('recent')">
        <span style="color:#eab308;font-size:0.75rem;">★</span> Từng có hàng
      </button>
      <button class="poketan-chip" id="map-chip-out" onclick="setMapStatusFilter('out')">
        <span class="chip-dot dot-red"></span> 🔴 Hết hàng
      </button>

      <!-- Chuỗi cửa hàng & Thương hiệu trên bản đồ -->
      <select class="poketan-chip select-chip" id="map-chain-select" onchange="setMapChainFilter(this.value)" title="Chuỗi cửa hàng & Thương hiệu">
        <option value="all">🏢 Tất cả chuỗi</option>
        <option value="conbini">🏪 Tất cả Conbini</option>
        <option value="seven">🏪 7-Eleven</option>
        <option value="lawson">🏪 Lawson</option>
        <option value="familymart">🏪 FamilyMart</option>
        <option value="ministop">🏪 Ministop</option>
        <option value="specialty">🃏 Card Shop chuyên biệt</option>
        <option value="electronics">🎮 Điện máy, GEO, Tsutaya</option>
      </select>
    </div>

    <!-- Real-time stock alert toast -->
    <div id="live-stock-toast" style="display:none;" onclick="focusStockStore()">
      <div class="toast-info">
        <span class="chip-dot dot-green"></span>
        <span id="toast-store-title" style="font-weight:700;">セブン-イレブン...</span>
        <span>で <b style="color:#16a34a;">在庫あり</b> の報告 <span id="toast-time">1分前</span></span>
      </div>
      <button class="toast-close-btn" onclick="event.stopPropagation(); hideToast()">✕</button>
    </div>

    <!-- Region loading & switch toast -->
    <div id="region-load-toast" style="display:none;">
      <span id="region-load-icon">⚡</span>
      <span id="region-load-text">Đang chuyển vùng...</span>
    </div>
  </div>

  <!-- 3. MAIN MAP AREA -->
  <main id="app-main">
    <div id="map"></div>

    <!-- Floating GPS Locate Button -->
    <button id="gps-btn" onclick="locateUser(true)" title="現在地を表示">
      📍
    </button>
  </main>

  <!-- 4. LIST VIEW SHEET (一覧 / Thông báo cập nhật báo cáo) -->
  <div id="view-list-container">
    <div class="list-header-bar">
      <div style="font-weight:800; font-size:0.92rem; color:#0f172a; display:flex; align-items:center; gap:6px;">
        <span>📋</span>
        <span>一覧 • Báo cáo & Điểm có hàng</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <button onclick="openFilterModal()" class="list-sort-btn" style="display:inline-flex; align-items:center; gap:5px; font-weight:800; background:#0f172a; color:#ffffff; border:1px solid #0f172a; padding:6px 12px; border-radius:8px; cursor:pointer;">
          <span>⚙️ Bộ lọc & Sắp xếp</span>
          <span id="list-filter-active-badge" class="filter-count-pill" style="display:none; background:#3b82f6; color:#ffffff; border-radius:99px; padding:1px 6px; font-size:0.65rem; font-weight:800;">0</span>
        </button>
        <button style="background:none;border:none;font-weight:700;color:#4f46e5;font-size:0.85rem;cursor:pointer;" onclick="switchFooterTab('map')">
          ✕ Đóng
        </button>
      </div>
    </div>

    <!-- Real-time settings synchronization banner on reports page -->
    <div id="list-active-settings-banner" style="background:#f8fafc; border-bottom:1px solid #e2e8f0; padding:6px 12px; font-size:0.72rem; color:#334155; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="font-weight:800; color:#0f172a;">📍 Đang lọc:</span>
        <span id="list-active-settings-text" style="color:#2563eb; font-weight:700;">Osaka • Tất cả • Toàn thời gian</span>
      </div>
      <div style="display:flex; align-items:center; gap:6px;">
        <span id="list-tg-status-tag" onclick="openTelegramModal()" style="font-size:0.65rem; background:#dcfce7; color:#15803d; font-weight:800; padding:2px 7px; border-radius:6px; cursor:pointer;" title="Bấm để mở cài đặt Telegram">✈️ Telegram: BẬT</span>
        <button type="button" onclick="openTelegramModal()" style="background:#0284c7; border:none; border-radius:4px; font-size:0.68rem; font-weight:700; color:#ffffff; padding:2px 8px; cursor:pointer;">✈️ Cấu hình Telegram</button>
      </div>
    </div>

    <!-- Status tabs matching PokéTan -->
    <div class="list-tabs-row" style="padding: 8px 12px 4px 12px; display: flex; gap: 6px; overflow-x: auto; background: #ffffff; border-bottom: 1px solid #f1f5f9; scrollbar-width: none;">
      <button class="list-tab-chip active" id="list-tab-all" onclick="setListStatusTab('all')">🌐 Tất cả</button>
      <button class="list-tab-chip" id="list-tab-in" onclick="setListStatusTab('in')">🟢 Có hàng</button>
      <button class="list-tab-chip" id="list-tab-onsite" onclick="setListStatusTab('onsite')">📍 Tại quán (GPS)</button>
      <button class="list-tab-chip" id="list-tab-out" onclick="setListStatusTab('out')">🔴 Hết hàng</button>
      <button class="list-tab-chip" id="list-tab-recent" onclick="setListStatusTab('recent')">★ Từng có</button>
      <button class="list-tab-chip" id="list-tab-unknown" onclick="setListStatusTab('unknown')">⚪ Chưa rõ</button>
    </div>

    <!-- Search and Filter Trigger -->
    <div style="padding:8px 12px; border-bottom:1px solid #f1f5f9; display:flex; gap:6px; align-items:center; background:#fafafa;">
      <div class="list-search-box" style="flex:1;">
        <span class="icon">🔍</span>
        <input type="text" id="list-search-input" placeholder="Tìm tên quán, địa chỉ..." oninput="onListSearch(this.value)" />
      </div>
      <button onclick="openFilterModal()" class="list-sort-btn" style="display:inline-flex; align-items:center; gap:5px; font-weight:800; background:#0f172a; color:#ffffff; border-color:#0f172a; padding:7px 11px; border-radius:8px; cursor:pointer;">
        <span>⚙️ Bộ lọc</span>
        <span id="list-filter-active-badge-2" class="filter-count-pill" style="display:none; background:#3b82f6; color:#ffffff; border-radius:99px; padding:1px 6px; font-size:0.65rem; font-weight:800;">0</span>
      </button>
      <select id="list-chain-select" onchange="setListChainFilter(this.value)" style="display:none;">
        <option value="all">all</option>
        <option value="conbini">conbini</option>
        <option value="seven">seven</option>
        <option value="lawson">lawson</option>
        <option value="familymart">familymart</option>
        <option value="ministop">ministop</option>
        <option value="specialty">specialty</option>
        <option value="electronics">electronics</option>
      </select>
      <select id="list-time-select" onchange="setListTimeFilter(this.value)" style="display:none;">
        <option value="all">all</option>
        <option value="1">1</option>
        <option value="3">3</option>
        <option value="6">6</option>
        <option value="24">24</option>
        <option value="72">72</option>
      </select>
    </div>

    <!-- Sort controls bar -->
    <div class="list-sort-bar">
      <span style="font-size:0.72rem; color:#64748b; font-weight:700;">Sắp xếp theo:</span>
      <div style="display:flex; gap:6px;">
        <button id="sort-btn-newest" onclick="setListSortMode('newest')" class="list-sort-btn active">
          🕒 Mới nhất
        </button>
        <button id="sort-btn-nearest" onclick="setListSortMode('nearest')" class="list-sort-btn">
          📍 Gần nhất
        </button>
      </div>
      <span id="list-count-badge" style="margin-left:auto; font-size:0.72rem; color:#4f46e5; font-weight:800;">
        0 quán
      </span>
    </div>
    <div class="list-cards-scroll" id="store-cards-list"></div>
  </div>

  <!-- 5. FOOTER BOTTOM NAVIGATION (Exact Image 2 replica + Settings) -->
  <footer id="poketan-footer">
    <button class="footer-tab-btn active" id="f-tab-map" onclick="switchFooterTab('map')" title="地図 / Bản đồ">
      <span class="tab-icon">🗺️</span>
      <span class="tab-label">地図</span>
    </button>

    <button class="footer-tab-btn" id="f-tab-list" onclick="switchFooterTab('list')" title="一覧 / Danh sách">
      <span class="tab-icon">📋</span>
      <span class="tab-label">一覧</span>
    </button>

    <!-- Center Elevated Button: Gachi Meguri (⚡) -->
    <div class="gachi-meguri-wrap" onclick="triggerGachiMeguri()" title="ガチ巡り (在庫あり店舗へ直行)">
      <div class="gachi-meguri-btn">
        <span class="btn-icon">⚡</span>
      </div>
      <span class="gachi-meguri-label">ガチ巡り</span>
    </div>

    <button class="footer-tab-btn" id="f-tab-search" onclick="openSearchModal()" title="さがす / Tìm kiếm">
      <span class="tab-icon">🔍</span>
      <span class="tab-label">さがす</span>
    </button>

    <button class="footer-tab-btn" id="f-tab-bulletin" onclick="openBulletinModal()" title="掲示板 / Bảng tin">
      <span class="tab-icon">💬</span>
      <span class="tab-label">掲示板</span>
    </button>

    <button class="footer-tab-btn" id="f-tab-settings" onclick="openSettingsModal()" title="設定 / Cài đặt">
      <span class="tab-icon">⚙️</span>
      <span class="tab-label">設定</span>
    </button>
  </footer>

  <!-- 5.4 MAP FILTER MODAL (⚙️ Bộ lọc bản đồ) -->
  <div id="map-filter-modal" class="modal-overlay" onclick="if(event.target===this) closeMapFilterModal()">
    <div class="modal-card" style="max-height:85vh; max-height:85dvh;">
      <div class="modal-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.15rem;">⚙️</span>
          <div>
            <h3 style="font-weight:800; font-size:1.02rem; color:#0f172a; margin:0;">Bộ lọc Bản đồ (地図フィルター)</h3>
            <div style="font-size:0.7rem; color:#64748b; font-weight:600; margin-top:1px;">Tùy chỉnh hiển thị ghim và cửa hàng trên bản đồ</div>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeMapFilterModal()">✕</button>
      </div>

      <div class="modal-body" style="padding:14px 16px; overflow-y:auto; display:flex; flex-direction:column; gap:16px;">
        <!-- SECTION 0: KHU VỰC BẢN ĐỒ -->
        <div>
          <div class="filter-section-title">
            <span>📍</span>
            <span>Khu vực hiển thị (地域・エリア)</span>
          </div>
          <div class="filter-options-grid" id="map-modal-region-group">
            <button class="filter-option-btn active" data-val="osaka" onclick="selectMapModalRegion('osaka')">
              🔵 Osaka &amp; Kansai
            </button>
            <button class="filter-option-btn" data-val="tokyo" onclick="selectMapModalRegion('tokyo')">
              🟣 Tokyo &amp; Kanto
            </button>
            <button class="filter-option-btn" data-val="nagoya" onclick="selectMapModalRegion('nagoya')">
              🟢 Nagoya &amp; Tokai
            </button>
            <button class="filter-option-btn" data-val="all" onclick="selectMapModalRegion('all')">
              🌐 Toàn quốc (~12.000 quán)
            </button>
          </div>
        </div>

        <!-- SECTION 1: TRẠNG THÁI HÀNG HÓA -->
        <div>
          <div class="filter-section-title">
            <span>📊</span>
            <span>Trạng thái hàng hóa (在庫状況)</span>
          </div>
          <div class="filter-options-grid" id="map-modal-status-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectMapModalStatus('all')">
              🌐 Tất cả cửa hàng
            </button>
            <button class="filter-option-btn" data-val="in" onclick="selectMapModalStatus('in')">
              <span class="chip-dot dot-green"></span> 🟢 Đang có hàng
            </button>
            <button class="filter-option-btn" data-val="recent" onclick="selectMapModalStatus('recent')">
              <span style="color:#eab308;font-size:0.75rem;">★</span> Từng có hàng gần đây
            </button>
            <button class="filter-option-btn" data-val="out" onclick="selectMapModalStatus('out')">
              <span class="chip-dot dot-red"></span> 🔴 Hết hàng
            </button>
            <button class="filter-option-btn" data-val="onsite" onclick="selectMapModalStatus('onsite')">
              📍 Báo cáo tại quán (GPS)
            </button>
            <button class="filter-option-btn" data-val="unknown" onclick="selectMapModalStatus('unknown')">
              ⚪ Chưa rõ trạng thái
            </button>
          </div>
        </div>

        <!-- SECTION 2: CHUỖI & THƯƠNG HIỆU -->
        <div>
          <div class="filter-section-title">
            <span>🏢</span>
            <span>Chuỗi cửa hàng & Thương hiệu (店舗チェーン)</span>
          </div>
          <div class="filter-options-grid" id="map-modal-chain-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectMapModalChain('all')">
              🏢 Tất cả chuỗi
            </button>
            <button class="filter-option-btn" data-val="conbini" onclick="selectMapModalChain('conbini')">
              🏪 Tất cả Conbini
            </button>
            <button class="filter-option-btn" data-val="seven" onclick="selectMapModalChain('seven')">
              🏪 7-Eleven
            </button>
            <button class="filter-option-btn" data-val="lawson" onclick="selectMapModalChain('lawson')">
              🏪 Lawson
            </button>
            <button class="filter-option-btn" data-val="familymart" onclick="selectMapModalChain('familymart')">
              🏪 FamilyMart
            </button>
            <button class="filter-option-btn" data-val="ministop" onclick="selectMapModalChain('ministop')">
              🏪 Ministop
            </button>
            <button class="filter-option-btn" data-val="specialty" onclick="selectMapModalChain('specialty')">
              🃏 Card Shop chuyên biệt
            </button>
            <button class="filter-option-btn" data-val="electronics" onclick="selectMapModalChain('electronics')">
              🎮 Điện máy, GEO, Tsutaya
            </button>
          </div>
        </div>

        <!-- SECTION 3: THỜI GIAN BÁO CÁO -->
        <div>
          <div class="filter-section-title">
            <span>⏱️</span>
            <span>Thời gian hiển thị báo cáo (報告時間)</span>
          </div>
          <div class="filter-options-grid" id="map-modal-time-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectMapModalTime('all')">
              ⏱️ Toàn bộ thời gian
            </button>
            <button class="filter-option-btn" data-val="1" onclick="selectMapModalTime('1')">
              ⚡ Trong 1 giờ qua
            </button>
            <button class="filter-option-btn" data-val="3" onclick="selectMapModalTime('3')">
              ⏱️ Trong 3 giờ qua
            </button>
            <button class="filter-option-btn" data-val="6" onclick="selectMapModalTime('6')">
              ⏱️ Trong 6 giờ qua
            </button>
            <button class="filter-option-btn" data-val="24" onclick="selectMapModalTime('24')">
              ⏱️ Trong 24 giờ qua
            </button>
            <button class="filter-option-btn" data-val="72" onclick="selectMapModalTime('72')">
              ⏱️ Trong 3 ngày qua
            </button>
          </div>
        </div>
      </div>

      <!-- MODAL FOOTER BUTTONS -->
      <div style="padding:12px 16px; border-top:1px solid #f1f5f9; background:#f8fafc; display:flex; gap:10px; align-items:center;">
        <button class="btn-reset-filter" onclick="resetMapFilters()">
          🔄 Đặt lại
        </button>
        <button class="btn-apply-filter" onclick="applyAndCloseMapFilterModal()">
          ✅ Áp dụng bộ lọc bản đồ
        </button>
      </div>
    </div>
  </div>

  <!-- 5.5 FILTER & SORT MODAL (Dedicated, Clean, Popup on Demand) -->
  <div id="filter-modal" class="modal-overlay" onclick="if(event.target===this) closeFilterModal()">
    <div class="modal-card" style="max-height:85vh; max-height:85dvh;">
      <div class="modal-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.15rem;">⚡</span>
          <h3 style="font-weight:800; font-size:1.02rem; color:#0f172a; margin:0;">Bộ lọc & Sắp xếp</h3>
        </div>
        <button class="modal-close-btn" onclick="closeFilterModal()">✕</button>
      </div>

      <div class="modal-body" style="padding:14px 16px; overflow-y:auto; display:flex; flex-direction:column; gap:16px;">
        <!-- SECTION 0: KHU VỰC HIỂN THỊ -->
        <div>
          <div class="filter-section-title">
            <span>📍</span>
            <span>Khu vực hiển thị (地域・エリア)</span>
          </div>
          <div class="filter-options-grid" id="modal-region-group">
            <button class="filter-option-btn active" data-val="osaka" onclick="selectModalRegion('osaka')">
              🔵 Osaka &amp; Kansai
            </button>
            <button class="filter-option-btn" data-val="tokyo" onclick="selectModalRegion('tokyo')">
              🟣 Tokyo &amp; Kanto
            </button>
            <button class="filter-option-btn" data-val="nagoya" onclick="selectModalRegion('nagoya')">
              🟢 Nagoya &amp; Tokai
            </button>
            <button class="filter-option-btn" data-val="all" onclick="selectModalRegion('all')">
              🌐 Toàn quốc (~12.000 quán)
            </button>
          </div>
        </div>

        <!-- SECTION 1: TRẠNG THÁI HÀNG HÓA -->
        <div>
          <div class="filter-section-title">
            <span>📊</span>
            <span>Trạng thái hàng hóa (在庫状況)</span>
          </div>
          <div class="filter-options-grid" id="modal-status-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalStatus('all')">
              🌐 Tất cả cửa hàng
            </button>
            <button class="filter-option-btn" data-val="in" onclick="selectModalStatus('in')">
              <span class="chip-dot dot-green"></span> 🟢 Đang có hàng
            </button>
            <button class="filter-option-btn" data-val="out" onclick="selectModalStatus('out')">
              <span class="chip-dot dot-red"></span> 🔴 Hết hàng
            </button>
            <button class="filter-option-btn" data-val="recent" onclick="selectModalStatus('recent')">
              <span style="color:#eab308;font-size:0.75rem;">★</span> Từng có hàng gần đây
            </button>
            <button class="filter-option-btn" data-val="onsite" onclick="selectModalStatus('onsite')">
              📍 Báo cáo tại quán (GPS)
            </button>
            <button class="filter-option-btn" data-val="unknown" onclick="selectModalStatus('unknown')">
              ⚪ Chưa rõ trạng thái
            </button>
          </div>
        </div>

        <!-- SECTION 2: CHUỖI & THƯƠNG HIỆU -->
        <div>
          <div class="filter-section-title">
            <span>🏢</span>
            <span>Chuỗi cửa hàng & Thương hiệu (店舗チェーン)</span>
          </div>
          <div class="filter-options-grid" id="modal-chain-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalChain('all')">
              🏢 Tất cả chuỗi
            </button>
            <button class="filter-option-btn" data-val="conbini" onclick="selectModalChain('conbini')">
              🏪 Tất cả Conbini
            </button>
            <button class="filter-option-btn" data-val="seven" onclick="selectModalChain('seven')">
              🏪 7-Eleven
            </button>
            <button class="filter-option-btn" data-val="lawson" onclick="selectModalChain('lawson')">
              🏪 Lawson
            </button>
            <button class="filter-option-btn" data-val="familymart" onclick="selectModalChain('familymart')">
              🏪 FamilyMart
            </button>
            <button class="filter-option-btn" data-val="ministop" onclick="selectModalChain('ministop')">
              🏪 Ministop
            </button>
            <button class="filter-option-btn" data-val="specialty" onclick="selectModalChain('specialty')">
              🃏 Card Shop chuyên biệt
            </button>
            <button class="filter-option-btn" data-val="electronics" onclick="selectModalChain('electronics')">
              🎮 Điện máy, GEO, Tsutaya
            </button>
          </div>
        </div>

        <!-- SECTION 3: THỜI GIAN BÁO CÁO -->
        <div>
          <div class="filter-section-title">
            <span>⏱️</span>
            <span>Thời gian hiển thị báo cáo (報告時間)</span>
          </div>
          <div class="filter-options-grid" id="modal-time-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalTime('all')">
              ⏱️ Toàn bộ thời gian
            </button>
            <button class="filter-option-btn" data-val="1" onclick="selectModalTime('1')">
              ⚡ Trong 1 giờ qua
            </button>
            <button class="filter-option-btn" data-val="3" onclick="selectModalTime('3')">
              ⏱️ Trong 3 giờ qua
            </button>
            <button class="filter-option-btn" data-val="6" onclick="selectModalTime('6')">
              ⏱️ Trong 6 giờ qua
            </button>
            <button class="filter-option-btn" data-val="24" onclick="selectModalTime('24')">
              ⏱️ Trong 24 giờ qua
            </button>
            <button class="filter-option-btn" data-val="72" onclick="selectModalTime('72')">
              ⏱️ Trong 3 ngày qua
            </button>
          </div>
        </div>

        <!-- SECTION 4: BÁN KÍNH KHOẢNG CÁCH -->
        <div>
          <div class="filter-section-title">
            <span>📍</span>
            <span>Bán kính tìm kiếm quanh bạn (距離・半径)</span>
          </div>
          <div class="filter-options-grid" id="modal-radius-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalRadius('all')">
              🌐 Không giới hạn bán kính
            </button>
            <button class="filter-option-btn" data-val="1" onclick="selectModalRadius('1')">
              📍 Bán kính 1 km
            </button>
            <button class="filter-option-btn" data-val="3" onclick="selectModalRadius('3')">
              📍 Bán kính 3 km
            </button>
            <button class="filter-option-btn" data-val="5" onclick="selectModalRadius('5')">
              📍 Bán kính 5 km
            </button>
            <button class="filter-option-btn" data-val="10" onclick="selectModalRadius('10')">
              📍 Bán kính 10 km
            </button>
          </div>
        </div>

        <!-- SECTION 5: THỨ TỰ SẮP XẾP -->
        <div>
          <div class="filter-section-title">
            <span>🔃</span>
            <span>Thứ tự sắp xếp danh sách (並び順)</span>
          </div>
          <div class="filter-options-grid" id="modal-sort-group">
            <button class="filter-option-btn active" data-val="newest" onclick="selectModalSort('newest')">
              🕒 Báo cáo mới nhất trước
            </button>
            <button class="filter-option-btn" data-val="nearest" onclick="selectModalSort('nearest')">
              📍 Gần vị trí bạn nhất
            </button>
          </div>
        </div>
      </div>

      <!-- MODAL FOOTER BUTTONS -->
      <div style="padding:12px 16px; border-top:1px solid #f1f5f9; background:#f8fafc; display:flex; gap:10px; align-items:center;">
        <button class="btn-reset-filter" onclick="resetAllFilters()">
          🔄 Đặt lại
        </button>
        <button class="btn-apply-filter" onclick="applyAndCloseFilterModal()">
          ✅ Áp dụng bộ lọc
        </button>
      </div>
    </div>
  </div>

  <!-- 5.6 TELEGRAM NOTIFICATION & ALERT CONFIGURATION MODAL -->
  <div id="telegram-modal" class="modal-overlay" onclick="if(event.target===this) closeTelegramModal()">
    <div class="modal-card" style="max-height:88vh; max-height:88dvh; max-width:480px;">
      <div class="modal-header" style="background:#0284c7; color:#ffffff;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.25rem;">✈️</span>
          <h3 style="font-weight:800; font-size:1.02rem; color:#ffffff; margin:0;">Cấu hình Telegram & Bộ lọc cảnh báo</h3>
        </div>
        <button class="modal-close-btn" style="color:#ffffff;" onclick="closeTelegramModal()">✕</button>
      </div>

      <div class="modal-body" style="padding:14px 16px; overflow-y:auto; display:flex; flex-direction:column; gap:16px;">
        <!-- SECTION 1: BẬT / TẮT & KẾT NỐI BOT -->
        <div style="background:#f0f9ff; border:1px solid #bae6fd; border-radius:10px; padding:12px;">
          <label style="display:flex; align-items:center; gap:10px; font-weight:800; font-size:0.86rem; color:#0369a1; cursor:pointer;">
            <input type="checkbox" id="tg-cfg-enabled" style="width:18px; height:18px; accent-color:#0284c7;" onchange="onTelegramToggleChanged(this.checked)">
            <span>✈️ Bật gửi thông báo tới Telegram (Telegram通知)</span>
          </label>
          <div style="font-size:0.72rem; color:#64748b; margin-top:4px;">Khi bật, bot sẽ tự động gửi tin nhắn báo có hàng theo đúng bộ lọc riêng bên dưới.</div>
        </div>

        <!-- Credentials Input -->
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div>
            <label style="font-weight:800; font-size:0.78rem; color:#0f172a; display:block; margin-bottom:4px;">
              🔑 Telegram Bot Token:
            </label>
            <input type="text" id="tg-cfg-token" placeholder="Ví dụ: 123456789:ABCdefGHIjklMNOpqrs..." style="width:100%; box-sizing:border-box; padding:9px 12px; border:1px solid #cbd5e1; border-radius:8px; font-size:0.8rem; font-family:monospace; outline:none;">
            <div style="font-size:0.68rem; color:#64748b; margin-top:3px;">
              Nhắn tin với <b style="color:#0284c7;">@BotFather</b> trên Telegram để tạo Bot và lấy Token.
            </div>
          </div>

          <div>
            <label style="font-weight:800; font-size:0.78rem; color:#0f172a; display:block; margin-bottom:4px;">
              💬 Telegram Chat ID:
            </label>
            <input type="text" id="tg-cfg-chatid" placeholder="Ví dụ: 987654321 hoặc -100123456789..." style="width:100%; box-sizing:border-box; padding:9px 12px; border:1px solid #cbd5e1; border-radius:8px; font-size:0.8rem; font-family:monospace; outline:none;">
            <div style="font-size:0.68rem; color:#64748b; margin-top:3px;">
              Nhắn tin với <b style="color:#0284c7;">@userinfobot</b> trên Telegram để lấy ID của bạn, hoặc ID nhóm/kênh.
            </div>
          </div>

          <!-- Test Button -->
          <div style="margin-top:4px;">
            <button type="button" id="btn-modal-test-tg" onclick="testTelegramInModal()" style="width:100%; padding:9px 12px; background:#0284c7; color:white; border:none; border-radius:8px; font-weight:800; font-size:0.78rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px;">
              <span>🧪 Gửi tin nhắn thử nghiệm (Test Bot)</span>
            </button>
            <div id="modal-test-tg-result" style="display:none; font-size:0.72rem; margin-top:6px; padding:7px 10px; border-radius:6px;"></div>
          </div>
        </div>

        <hr style="border:none; border-top:1px dashed #e2e8f0; margin:2px 0;">

        <!-- SECTION 2: BỘ LỌC THÔNG BÁO RIÊNG CỦA TELEGRAM -->
        <div style="font-weight:800; font-size:0.85rem; color:#0f172a; display:flex; align-items:center; gap:6px;">
          <span>⚙️</span>
          <span>Bộ lọc nhận tin riêng của Telegram</span>
        </div>

        <!-- 1. Trạng thái hàng hóa Telegram -->
        <div>
          <label style="font-weight:700; font-size:0.78rem; color:#334155; display:block; margin-bottom:4px;">
            📊 1. Trạng thái hàng hóa nhận tin:
          </label>
          <select id="tg-cfg-status" style="width:100%; padding:9px 12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; color:#1e293b; font-size:0.8rem; outline:none;">
            <option value="in">🟢 Chỉ gửi khi có hàng (Đang có hàng) - Khuyên dùng</option>
            <option value="onsite">📸 Chỉ gửi khi có hàng tại quán (GPS / 現地確認)</option>
            <option value="recent">★ Gửi cả tin từng có hàng gần đây</option>
            <option value="all">🌐 Gửi tất cả báo cáo (Có hàng & Hết hàng)</option>
          </select>
        </div>

        <!-- 2. Chuỗi cửa hàng & Thương hiệu Telegram -->
        <div>
          <label style="font-weight:700; font-size:0.78rem; color:#334155; display:block; margin-bottom:4px;">
            🏢 2. Chuỗi cửa hàng & Thương hiệu nhận tin:
          </label>
          <select id="tg-cfg-chain" style="width:100%; padding:9px 12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; color:#1e293b; font-size:0.8rem; outline:none;">
            <option value="all">🏢 Tất cả chuỗi cửa hàng</option>
            <option value="conbini">🏪 Tất cả Conbini (7-Eleven, Lawson, FamilyMart, Ministop)</option>
            <option value="seven">🏪 7-Eleven</option>
            <option value="lawson">🏪 Lawson</option>
            <option value="familymart">🏪 FamilyMart</option>
            <option value="ministop">🏪 Ministop</option>
            <option value="specialty">🃏 Card Shop chuyên biệt</option>
            <option value="electronics">🎮 Điện máy, GEO, Tsutaya</option>
          </select>
        </div>

        <!-- 3. Độ mới tin báo Telegram -->
        <div>
          <label style="font-weight:700; font-size:0.78rem; color:#334155; display:block; margin-bottom:4px;">
            ⏱️ 3. Thời gian / Độ mới tin báo:
          </label>
          <select id="tg-cfg-time" style="width:100%; padding:9px 12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; color:#1e293b; font-size:0.8rem; outline:none;">
            <option value="1">⚡ Trong 1 giờ qua (Báo cáo tức thì)</option>
            <option value="3">⏱️ Trong 3 giờ qua</option>
            <option value="6">⏱️ Trong 6 giờ qua</option>
            <option value="24">⏱️ Trong 24 giờ qua (Mặc định)</option>
            <option value="all">⏱️ Toàn bộ thời gian</option>
          </select>
        </div>

        <!-- 4. Khu vực nhận tin Telegram -->
        <div>
          <label style="font-weight:700; font-size:0.78rem; color:#334155; display:block; margin-bottom:4px;">
            📍 4. Khu vực nhận tin (Vùng dữ liệu):
          </label>
          <select id="tg-cfg-region" style="width:100%; padding:9px 12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; color:#1e293b; font-size:0.8rem; outline:none;">
            <option value="osaka">🔵 大阪・関西 (Osaka & Lân cận)</option>
            <option value="tokyo">🟣 東京・神奈川 (Tokyo & Lân cận)</option>
            <option value="nagoya">🟢 名古屋・東海 (Nagoya & Lân cận)</option>
            <option value="all">🌐 Toàn bộ 3 vùng / Toàn quốc (~12.000 quán)</option>
          </select>
        </div>
        <!-- In-modal save notification banner -->
        <div id="modal-save-tg-result" style="display:none; font-size:0.75rem; padding:9px 12px; border-radius:8px; font-weight:700;"></div>
      </div>

      <!-- MODAL FOOTER BUTTONS -->
      <div style="padding:12px 16px; border-top:1px solid #f1f5f9; background:#f8fafc; display:flex; gap:10px; align-items:center;">
        <button type="button" class="btn-reset-filter" onclick="closeTelegramModal()">
          Đóng
        </button>
        <button type="button" id="btn-save-tg" class="btn-apply-filter" onclick="saveTelegramSettings()" style="background:#0284c7; border-color:#0284c7;">
          💾 Lưu cấu hình Telegram
        </button>
      </div>
    </div>
  </div>

  <!-- 6. PREFECTURE & AREA SELECTION MODAL (Exact PokéTan Replica) -->
  <div id="pref-modal" class="modal-overlay" onclick="if(event.target===this) closePrefModal()">
    <div class="modal-card">
      <div class="modal-header">
        <h3 style="font-weight: 800; font-size: 1.05rem; color: #1e1b4b;">エリアを選ぶ</h3>
        <button class="modal-close-btn" onclick="closePrefModal()">✕</button>
      </div>
      <div class="modal-body">
        <!-- 1. Search Bar -->
        <div class="area-search-row">
          <input type="text" id="area-search-input" class="area-search-input" placeholder="駅名・店名・地名で探す" onkeydown="if(event.key==='Enter') searchAreaLocation()">
          <button class="area-search-btn" onclick="searchAreaLocation()">検索</button>
        </div>

        <!-- 2. GPS Button -->
        <button class="area-gps-btn" onclick="useGpsLocation()">
          <span style="font-size:1.15rem; color:#4f46e5; transform: rotate(45deg); display:inline-block;">➤</span>
          <span>現在地を使う</span>
        </button>

        <!-- 3. Notice text -->
        <div class="area-notice-text">
          対応エリア：愛知・神奈川・大阪（順次拡大中）。現在地から探すには、Xなどのアプリ内ではなくSafariやChromeで開いてください
        </div>

        <!-- 4. Voting banner -->
        <div class="area-vote-box" onclick="voteForNewPrefecture()">
          <div>
            <div style="font-weight: 800; font-size: 0.82rem; color: #1e1b4b;">お住まいの県がない？</div>
            <div style="font-size: 0.72rem; color: #64748b; margin-top: 2px;">次に追加する県は投票で決めます（無料）</div>
          </div>
          <div style="font-weight: 700; font-size: 0.82rem; color: #4f46e5; display: flex; align-items: center; gap: 3px; white-space: nowrap;">
            1票で投票 <span style="font-size: 0.95rem;">›</span>
          </div>
        </div>

        <!-- 5. Aichi Section -->
        <div class="area-section">
          <div class="area-section-title">愛知</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="aichi" data-city="名古屋駅" onclick="selectCityArea('aichi', '名古屋駅', 35.1709, 136.8815, 14)">名古屋駅</button>
            <button class="area-chip" data-pref="aichi" data-city="栄" onclick="selectCityArea('aichi', '栄', 35.1698, 136.9084, 14)">栄</button>
            <button class="area-chip" data-pref="aichi" data-city="豊田" onclick="selectCityArea('aichi', '豊田', 35.0833, 137.1500, 13)">豊田</button>
            <button class="area-chip" data-pref="aichi" data-city="岡崎" onclick="selectCityArea('aichi', '岡崎', 34.9550, 137.1683, 13)">岡崎</button>
            <button class="area-chip" data-pref="aichi" data-city="一宮" onclick="selectCityArea('aichi', '一宮', 35.3039, 136.8000, 13)">一宮</button>
            <button class="area-chip" data-pref="aichi" data-city="豊橋" onclick="selectCityArea('aichi', '豊橋', 34.7628, 137.3817, 13)">豊橋</button>
          </div>
        </div>

        <!-- 6. Osaka Section -->
        <div class="area-section">
          <div class="area-section-title">大阪</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="osaka" data-city="梅田" onclick="selectCityArea('osaka', '梅田', 34.7024, 135.4959, 14)">梅田</button>
            <button class="area-chip active" id="chip-namba" data-pref="osaka" data-city="なんば" onclick="selectCityArea('osaka', 'なんば', 34.6669, 135.5013, 14)">なんば</button>
            <button class="area-chip" data-pref="osaka" data-city="天王寺" onclick="selectCityArea('osaka', '天王寺', 34.6472, 135.5139, 14)">天王寺</button>
            <button class="area-chip" data-pref="osaka" data-city="堺" onclick="selectCityArea('osaka', '堺', 34.5733, 135.4830, 13)">堺</button>
            <button class="area-chip" data-pref="osaka" data-city="枚方" onclick="selectCityArea('osaka', '枚方', 34.8148, 135.6508, 13)">枚方</button>
          </div>
        </div>

        <!-- 7. Kanagawa Section -->
        <div class="area-section">
          <div class="area-section-title">神奈川</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="kanagawa" data-city="横浜" onclick="selectCityArea('kanagawa', '横浜', 35.4437, 139.6380, 14)">横浜</button>
            <button class="area-chip" data-pref="kanagawa" data-city="川崎" onclick="selectCityArea('kanagawa', '川崎', 35.5308, 139.7029, 14)">川崎</button>
            <button class="area-chip" data-pref="kanagawa" data-city="相模原" onclick="selectCityArea('kanagawa', '相模原', 35.5714, 139.3732, 13)">相模原</button>
            <button class="area-chip" data-pref="kanagawa" data-city="藤沢" onclick="selectCityArea('kanagawa', '藤沢', 35.3389, 139.4889, 13)">藤沢</button>
          </div>
        </div>

        <!-- 8. Other Areas Section -->
        <div class="area-section" style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e2e8f0;">
          <div class="area-section-title">その他エリア</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="all" data-city="全エリア" onclick="selectCityArea('all', '全エリア', 34.6937, 135.5023, 10)">🗾 全エリア (全国)</button>
            <button class="area-chip" data-pref="gifu" data-city="岐阜" onclick="selectCityArea('gifu', '岐阜', 35.4233, 136.7607, 12)">岐阜</button>
            <button class="area-chip" data-pref="mie" data-city="三重" onclick="selectCityArea('mie', '三重', 34.7303, 136.5086, 12)">三重</button>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- 7. BULLETIN MODAL (💬 掲示板) -->
  <div id="bulletin-modal" class="modal-overlay" onclick="if(event.target===this) closeBulletinModal()">
    <div class="modal-card" style="max-width:440px;">
      <div class="modal-header">
        <h3>💬 掲示板 (入荷速報・目撃情報)</h3>
        <button class="modal-close-btn" onclick="closeBulletinModal()">✕</button>
      </div>
      <div class="modal-body" style="font-size:0.82rem; max-height:70vh; overflow-y:auto;" id="bulletin-list">
        <!-- Rendered dynamically -->
      </div>
    </div>
  </div>

  <!-- 8. SETTINGS MODAL (⚙️ 設定 &amp; カスタマイズ) -->
  <div id="settings-modal" class="modal-overlay" onclick="if(event.target===this) closeSettingsModal()">
    <div class="modal-card" style="max-width:440px;">
      <div class="modal-header">
        <h3>⚙️ 設定 / Cài đặt tùy chỉnh</h3>
        <button class="modal-close-btn" onclick="closeSettingsModal()">✕</button>
      </div>
      <div class="modal-body" style="font-size:0.82rem; max-height:75vh; overflow-y:auto; display:flex; flex-direction:column; gap:16px;">

        <!-- REGION SELECTION: Load by Region to maximize performance -->
        <div style="margin-bottom:16px;">
          <div style="font-weight:800; font-size:0.85rem; color:#1e293b; margin-bottom:4px; display:flex; align-items:center; justify-content:space-between;">
            <div style="display:flex; align-items:center; gap:6px;">
              <span>📍 Vùng dữ liệu hiển thị (表示エリア)</span>
            </div>
            <span style="font-size:0.65rem; background:#dcfce7; color:#15803d; font-weight:800; padding:2px 7px; border-radius:6px;">⚡ Tải nhanh theo vùng</span>
          </div>
          <div style="font-size:0.72rem; color:#64748b; margin-bottom:8px;">Chọn vùng để chỉ tải dữ liệu của vùng đó, giúp bản đồ mượt và load siêu tốc:</div>

          <div style="display:flex; flex-direction:column; gap:6px;" id="settings-region-selector">
            <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; cursor:pointer; transition:all 0.15s;">
              <input type="radio" name="set-region-radio" value="osaka" onchange="selectRegion('osaka')">
              <div style="flex:1;">
                <div style="font-weight:800; font-size:0.82rem; color:#1e293b;">🔵 大阪・関西 (Osaka &amp; Lân cận)</div>
                <div style="font-size:0.69rem; color:#64748b; margin-top:1px;">Osaka, Namba, Umeda, Tennoji, Sakai, Hirakata... (~4.050 quán)</div>
              </div>
            </label>

            <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; cursor:pointer; transition:all 0.15s;">
              <input type="radio" name="set-region-radio" value="tokyo" onchange="selectRegion('tokyo')">
              <div style="flex:1;">
                <div style="font-weight:800; font-size:0.82rem; color:#1e293b;">🟣 東京・神奈川 (Tokyo &amp; Lân cận)</div>
                <div style="font-size:0.69rem; color:#64748b; margin-top:1px;">Yokohama, Kawasaki, Sagamihara, Fujisawa... (~4.040 quán)</div>
              </div>
            </label>

            <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; cursor:pointer; transition:all 0.15s;">
              <input type="radio" name="set-region-radio" value="nagoya" onchange="selectRegion('nagoya')">
              <div style="flex:1;">
                <div style="font-weight:800; font-size:0.82rem; color:#1e293b;">🟢 名古屋・東海 (Nagoya &amp; Lân cận)</div>
                <div style="font-size:0.69rem; color:#64748b; margin-top:1px;">Nagoya Station, Sakae, Toyota, Okazaki, Gifu, Mie... (~3.870 quán)</div>
              </div>
            </label>

            <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; cursor:pointer; transition:all 0.15s;">
              <input type="radio" name="set-region-radio" value="all" onchange="selectRegion('all')">
              <div style="flex:1;">
                <div style="font-weight:800; font-size:0.82rem; color:#1e293b;">🌐 全エリア (Tất cả 3 vùng / Toàn quốc)</div>
                <div style="font-size:0.69rem; color:#64748b; margin-top:1px;">Tải dữ liệu toàn bộ cả 3 vùng cùng lúc (~12.000 quán)</div>
              </div>
            </label>
          </div>

          <div style="margin-top:8px;">
            <button type="button" onclick="closeSettingsModal(); openPrefModal();" style="width:100%; display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:#f1f5f9; border:1px dashed #cbd5e1; border-radius:8px; font-weight:700; font-size:0.75rem; color:#475569; cursor:pointer;">
              <span>📍 Chọn chi tiết từng thành phố / khu vực</span>
              <span>Mở danh sách ❯</span>
            </button>
          </div>
        </div>

        <!-- Telegram & Notifications -->
        <div style="margin-bottom:16px;">
          <div style="font-weight:800; font-size:0.85rem; color:#1e293b; margin-bottom:4px; display:flex; align-items:center; justify-content:space-between;">
            <span>🔔 Thông báo Telegram &amp; Âm thanh</span>
            <span id="set-tg-status-pill" style="font-size:0.65rem; background:#dcfce7; color:#15803d; font-weight:800; padding:2px 7px; border-radius:6px;">✈️ Đang bật</span>
          </div>
          <div style="font-size:0.72rem; color:#64748b; margin-bottom:8px;">Cài đặt Token Bot, Chat ID và bộ lọc riêng (Trạng thái, Chuỗi, Thời gian, Vùng) cho Telegram.</div>

          <button type="button" onclick="closeSettingsModal(); openTelegramModal();" style="width:100%; padding:10px 14px; background:#0284c7; color:white; border:none; border-radius:8px; font-weight:800; font-size:0.82rem; cursor:pointer; display:flex; align-items:center; justify-content:space-between; gap:6px; box-shadow:0 2px 6px rgba(2,132,199,0.25); margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span>✈️</span>
              <span>Cấu hình Telegram &amp; Bộ lọc cảnh báo</span>
            </div>
            <span>Mở cài đặt ❯</span>
          </button>

          <div style="background:#f8fafc; padding:10px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:8px;">
            <label style="display:flex; align-items:center; gap:8px; font-weight:700; cursor:pointer;">
              <input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)" checked>
              <span>🔊 Âm thanh thông báo trên web (音声アラート)</span>
            </label>
          </div>
        </div>

        <!-- Refresh Button -->
        <button onclick="refreshData(); closeSettingsModal();" style="width:100%;padding:11px;background:#4f46e5;color:white;border:none;border-radius:8px;font-weight:800;font-size:0.84rem;cursor:pointer;box-shadow:0 2px 6px rgba(79,70,229,0.3);">
          🔄 Cập nhật dữ liệu mới nhất (データ更新)
        </button>
      </div>
    </div>
  </div>

  <!-- 9. STORE HISTORY MODAL (📜 入荷履歴 / Lịch sử báo cáo) -->
  <div id="store-history-modal" class="modal-overlay" onclick="if(event.target===this) closeStoreHistoryModal()">
    <div class="modal-card" style="max-width:440px;">
      <div class="modal-header">
        <div style="min-width:0; flex:1; text-align:left;">
          <h3 id="hist-modal-title" style="margin:0; font-size:1.0rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">📜 入荷履歴 / Lịch sử báo cáo</h3>
          <div id="hist-modal-subtitle" style="font-size:0.72rem; color:#64748b; margin-top:2px;"></div>
        </div>
        <button class="modal-close-btn" onclick="closeStoreHistoryModal()">✕</button>
      </div>
      <div class="modal-body" style="font-size:0.82rem; max-height:75vh; overflow-y:auto;">
        <!-- Current Status Banner -->
        <div id="hist-modal-current" style="margin-bottom:12px;"></div>

        <!-- History Timeline Header -->
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-weight:800; font-size:0.8rem; color:#1e293b;">
          <span>📋 過去の報告ログ (Nhật ký báo cáo)</span>
          <span id="hist-modal-count" style="font-size:0.72rem; color:#4f46e5; font-weight:700;"></span>
        </div>

        <!-- Timeline Items List -->
        <div id="hist-modal-timeline" style="display:flex; flex-direction:column; gap:8px;">
          <!-- Loaded dynamically -->
        </div>

        <!-- Bottom Actions -->
        <div style="margin-top:14px; display:flex; gap:8px;">
          <a id="hist-modal-maps-link" href="#" target="_blank" class="btn-popup-maps" style="flex:1; padding:10px; font-size:0.8rem;">
            🗺️ Googleマップでルート案内 ↗
          </a>
          <button type="button" onclick="closeStoreHistoryModal()" style="padding:10px 16px; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; font-size:0.8rem; cursor:pointer;">
            閉じる
          </button>
        </div>
      </div>
    </div>
  </div>

  <script>
    // 1. APP STATE & 3-REGION ON-DEMAND LOADING
    const REGIONS = {
      'osaka': {
        id: 'osaka',
        name: '大阪・関西',
        label: 'Osaka & Kansai (大阪・関西)',
        center: [34.6937, 135.5023],
        zoom: 13,
        defaultCity: 'なんば',
        prefs: ['osaka']
      },
      'tokyo': {
        id: 'tokyo',
        name: '東京・神奈川',
        label: 'Tokyo & Kanto (東京・神奈川・関東)',
        center: [35.4437, 139.6380],
        zoom: 13,
        defaultCity: '横浜',
        prefs: ['kanagawa']
      },
      'nagoya': {
        id: 'nagoya',
        name: '名古屋・東海',
        label: 'Nagoya & Tokai (愛知・岐阜・三重・東海)',
        center: [35.1815, 136.9066],
        zoom: 13,
        defaultCity: '名古屋駅',
        prefs: ['aichi', 'gifu', 'mie']
      },
      'all': {
        id: 'all',
        name: '全エリア (全国)',
        label: 'Toàn quốc / 全エリア (Tất cả vùng)',
        center: [34.6937, 135.5023],
        zoom: 10,
        defaultCity: '全エリア',
        prefs: ['osaka', 'aichi', 'kanagawa', 'gifu', 'mie']
      }
    };

    function getRegionForPref(pref) {
      if (!pref) return 'osaka';
      pref = pref.toLowerCase();
      if (pref === 'osaka') return 'osaka';
      if (pref === 'kanagawa' || pref === 'tokyo') return 'tokyo';
      if (pref === 'aichi' || pref === 'gifu' || pref === 'mie' || pref === 'nagoya') return 'nagoya';
      return 'all';
    }

    let savedRegion = localStorage.getItem('poketan_selected_region') || 'osaka';
    if (!REGIONS[savedRegion]) savedRegion = 'osaka';
    let currentRegion = savedRegion;
    let currentPref = REGIONS[currentRegion].prefs[0] || 'osaka';

    let storesDict = {};
    window.REGIONS = REGIONS;
    window.currentRegion = currentRegion;
    window.storesDict = storesDict;
    let hotStatus = {};
    let coldStatus = {};
    let configData = {};
    let mapRegionFilter = currentRegion || 'osaka'; // 'osaka' | 'tokyo' | 'nagoya' | 'all' (Dùng cho Bản đồ)
    let mapStatusFilter = 'all'; // 'all' | 'in' | 'recent' | 'out' | 'onsite' | 'unknown' (Chỉ dùng cho Bản đồ)
    let mapChainFilter = 'all';  // 'all' | 'conbini' | 'seven' | ... (Chỉ dùng cho Bản đồ)
    let mapTimeFilter = 'all';   // 'all' | '1' | '3' | '6' | '24' | '72' (Chỉ dùng cho Bản đồ)
    let activeFilter = 'all';    // backward compatible alias
    let activeChain = 'all';     // backward compatible alias
    let activeRadius = null;
    let activeTime = 'all';
    let listRegionFilter = currentRegion || 'osaka'; // 'osaka' | 'tokyo' | 'nagoya' | 'all' (Dùng cho Báo cáo)
    let listStatusFilter = 'all'; // 'all' | 'in' | 'onsite' | 'out' | 'recent' | 'unknown' (Dùng cho Báo cáo)
    let listChainFilter = 'all';  // 'all' | 'conbini' | 'seven' | ... (Dùng cho Báo cáo)
    let listTimeFilter = 'all';   // 'all' | '1' | '3' | '6' | '24' | '72' (Dùng cho Báo cáo)
    let listRadiusFilter = 'all'; // 'all' | '1' | '3' | '5' | '10' (Dùng cho Báo cáo)
    let listSortMode = 'newest';  // 'newest' | 'nearest' (Dùng cho Báo cáo)
    let latestStockStoreId = null;
    const storeHistoryCache = {};
    const openPopupHistStoreIds = new Set();

    // GPS State
    let userLat = null;
    let userLng = null;
    let userMarker = null;
    let userCircle = null;
    let hasCenteredOnUser = false;

    const prefCenters = {
      'osaka': [34.6937, 135.5023],
      'aichi': [35.1815, 136.9066],
      'kanagawa': [35.4437, 139.6380],
      'gifu': [35.4233, 136.7607],
      'mie': [34.7303, 136.5086],
      'all': [34.6937, 135.5023]
    };

    function isCoordInJapan(lat, lng) {
      return typeof lat === 'number' && typeof lng === 'number' &&
             lat >= 24.0 && lat <= 46.0 && lng >= 122.0 && lng <= 154.0;
    }

    // Determine initial center based on active region
    let initialCenter = REGIONS[currentRegion] ? REGIONS[currentRegion].center : [34.6937, 135.5023];
    let initialZoom = REGIONS[currentRegion] ? REGIONS[currentRegion].zoom : 13;

    try {
      const savedLat = parseFloat(localStorage.getItem('poketan_user_lat') || sessionStorage.getItem('poketan_user_lat'));
      const savedLng = parseFloat(localStorage.getItem('poketan_user_lng') || sessionStorage.getItem('poketan_user_lng'));
      if (!isNaN(savedLat) && !isNaN(savedLng)) {
        userLat = savedLat;
        userLng = savedLng;
        if (isCoordInJapan(userLat, userLng)) {
          initialCenter = [userLat, userLng];
          initialZoom = 14;
          hasCenteredOnUser = true;
        }
      }
    } catch(e) {}

    // 2. LEAFLET MAP WITH GOOGLE MAPS PHYSICS (Ultra-smooth kinetic dragging, high-precision pinch zoom)
    const map = L.map('map', {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      preferCanvas: true,

      // Google Maps-like kinetic inertia & fluid momentum
      inertia: true,
      inertiaDeceleration: 2000, // Natural fluid deceleration matching Google Maps swipe
      inertiaMaxSpeed: 3000,
      easeLinearity: 0.15,

      // Smooth zooming & gesture response
      zoomAnimation: true,
      fadeAnimation: true,
      markerZoomAnimation: true,

      // Crisp zoom & snappy responsiveness
      zoomSnap: 1,
      zoomDelta: 1,
      wheelPxPerZoomLevel: 100,
      wheelDebounceTime: 40,

      touchZoom: true,
      bounceAtZoomLimits: false,
      maxBoundsViscosity: 0
    });
    window.map = map;

    // High performance Google Maps Streets Tiles
    L.tileLayer('https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
      subdomains: ['0', '1', '2', '3'],
      maxZoom: 20,
      maxNativeZoom: 19,
      attribution: '&copy; Google Maps',
      updateWhenIdle: false,
      updateWhenZooming: true,
      keepBuffer: 4,
      crossOrigin: true
    }).addTo(map);

    // GOOGLE MAPS GESTURES: Two-finger trackpad panning & pinch-to-zoom
    let lastTrackpadTime = 0;
    function isTrackpadGesture(e) {
      if (e.ctrlKey) return false; // Ctrl / trackpad pinch -> zoom
      const now = performance.now();
      // Trackpad events have non-zero deltaX, non-integer deltaY, or small continuous deltas
      if (e.deltaX !== 0 || Math.abs(e.deltaY) % 1 !== 0 || Math.abs(e.deltaY) < 50) {
        lastTrackpadTime = now;
        return true;
      }
      if (now - lastTrackpadTime < 250) {
        lastTrackpadTime = now;
        return true;
      }
      return false;
    }

    window.addEventListener('wheel', function(e) {
      const mapEl = document.getElementById('map');
      const isOverMap = mapEl && (mapEl === e.target || mapEl.contains(e.target));

      // If user is pinching (Ctrl key held or trackpad pinch) outside the map -> BLOCK BROWSER PAGE ZOOM!
      if (e.ctrlKey && !isOverMap) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      // Don't intercept wheel if inside an open modal or scrollable sheet
      if (e.target.closest('#filter-modal, #view-list-container, #settings-modal, #bulletin-modal, #store-history-modal, #pref-modal, .filter-chips-scroll')) {
        return;
      }
      if (isTrackpadGesture(e)) {
        // Trackpad 2-finger scroll -> PAN THE MAP (like Google Maps)!
        e.preventDefault();
        e.stopImmediatePropagation();
        map.panBy([e.deltaX, e.deltaY], { animate: false });
      }
      // Traditional mouse wheel or pinch gesture over map -> passes through to Leaflet zoom!
    }, { capture: true, passive: false });

    // PREVENT PAGE-LEVEL ZOOM (Only map zooms, header/footer/page stay fixed 100%)
    // 1. Prevent iOS Safari page-level gesture zoom outside the map
    window.addEventListener('gesturestart', function(e) {
      const mapEl = document.getElementById('map');
      if (!mapEl || !mapEl.contains(e.target)) {
        e.preventDefault();
      }
    }, { passive: false });

    window.addEventListener('gesturechange', function(e) {
      const mapEl = document.getElementById('map');
      if (!mapEl || !mapEl.contains(e.target)) {
        e.preventDefault();
      }
    }, { passive: false });

    window.addEventListener('gestureend', function(e) {
      const mapEl = document.getElementById('map');
      if (!mapEl || !mapEl.contains(e.target)) {
        e.preventDefault();
      }
    }, { passive: false });

    // 2. Prevent multi-touch pinch zoom on header, footer, and page outside the map
    window.addEventListener('touchstart', function(e) {
      if (e.touches && e.touches.length > 1) {
        const mapEl = document.getElementById('map');
        if (!mapEl || !mapEl.contains(e.target)) {
          e.preventDefault();
        }
      }
    }, { passive: false, capture: true });

    window.addEventListener('touchmove', function(e) {
      if (e.touches && e.touches.length > 1) {
        const mapEl = document.getElementById('map');
        if (!mapEl || !mapEl.contains(e.target)) {
          e.preventDefault();
        }
      }
    }, { passive: false, capture: true });

    // 3. Prevent double-tap to zoom outside the map
    let lastTouchEndTime = 0;
    window.addEventListener('touchend', function(e) {
      const now = performance.now();
      const mapEl = document.getElementById('map');
      if (!mapEl || !mapEl.contains(e.target)) {
        if (now - lastTouchEndTime <= 300) {
          e.preventDefault();
        }
      }
      lastTouchEndTime = now;
    }, { passive: false, capture: true });

    // 4. Prevent Ctrl/Cmd + (+/-) keyboard zoom on entire page
    window.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=' || e.key === '-' || e.key === '_' || e.key === '0')) {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
          e.preventDefault();
        }
      }
    }, { passive: false });

    map.on('popupclose', () => {
      openPopupHistStoreIds.clear();
    });

    let prevZoomGroup = map.getZoom() >= 12;
    map.on('zoomend', () => {
      const isClose = map.getZoom() >= 12;
      if (isClose !== prevZoomGroup) {
        prevZoomGroup = isClose;
        renderMapMarkers();
      }
    });

    // 3. MARKER CLUSTERING (Matching PokéTan Image 3: Blue bordered count circles ②, ③)
    let clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 46,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      chunkedLoading: true,
      chunkInterval: 100,
      chunkDelay: 40,
      animate: true,
      animateAddingMarkers: false,
      disableClusteringAtZoom: 17,
      iconCreateFunction: function(cluster) {
        const count = cluster.getChildCount();
        const markers = cluster.getAllChildMarkers();
        const hasStock = markers.some(m => m.options.hasStock);
        const stockClass = hasStock ? 'has-stock' : '';
        return L.divIcon({
          html: `<div class="poketan-cluster ${stockClass}">${count}</div>`,
          className: 'poketan-cluster-wrap',
          iconSize: L.point(32, 32)
        });
      }
    });
    map.addLayer(clusterGroup);

    // Separate Layer for in-stock pins (always on top)
    const stockLayer = L.layerGroup().addTo(map);

    // 4. DECODE STATUS
    function decodeStatus(rawVal) {
      if (!rawVal || typeof rawVal !== 'string') {
        return { code: 'u', label: '不明', packs: [], reported_at: '', timeAgo: '', onsite: false, timestamp: 0 };
      }
      const code = rawVal[0].toLowerCase();
      let rest = rawVal.substring(1);

      let onsite = false;
      if (rest.endsWith('g')) {
        onsite = true;
        rest = rest.slice(0, -1);
      }

      let packs = [];
      const packCodes = configData.packCodes || {};
      for (const [pCode, pName] of Object.entries(packCodes)) {
        if (rest.endsWith(pCode)) {
          packs.push(pName);
          rest = rest.slice(0, -pCode.length);
        }
      }

      let dtStr = '';
      let timeAgo = '';
      let timestamp = 0;
      if (rest.length >= 10) {
        const parsed = parseInt(rest.substring(0, 10), 10);
        if (!isNaN(parsed) && parsed > 0) {
          timestamp = parsed;
          const d = new Date(parsed * 1000);
          const month = d.getMonth() + 1;
          const day = d.getDate();
          const time = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', hour12: false });
          dtStr = `${time} (${month}/${day})`;
          const diffSec = Math.floor(Date.now() / 1000 - parsed);
          if (diffSec < 60) timeAgo = 'たった今';
          else if (diffSec < 3600) timeAgo = `${Math.floor(diffSec / 60)}分前`;
          else if (diffSec < 86400) timeAgo = `${Math.floor(diffSec / 3600)}時間前`;
          else timeAgo = `${Math.floor(diffSec / 86400)}日前`;
        }
      }

      const labelMap = {
        'i': '在庫あり',
        'o': '在庫なし',
        'n': '扱ってない',
        'u': '不明'
      };

      return {
        code,
        label: labelMap[code] || '不明',
        packs,
        reported_at: dtStr,
        timeAgo,
        onsite,
        timestamp
      };
    }

    // 5. DISTANCE
    function calcDistanceKm(lat1, lon1, lat2, lon2) {
      const R = 6371;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    }

    function formatDist(km) {
      if (!km) return '';
      if (km < 1) return `${Math.round(km * 1000)}m`;
      return `${km.toFixed(1)}km`;
    }

    // Fast lightweight reusable marker icons & dynamic in-stock pin with time pill
    function createStockPinIcon(timeAgo) {
      const label = timeAgo || 'たった今';
      return L.divIcon({
        html: `
          <div class="poketan-pin-wrapper">
            <div class="poketan-stock-pin">🟢</div>
            <div class="poketan-pin-time-pill">${escapeHtml(label)}</div>
          </div>
        `,
        className: 'poketan-pin-leaflet-icon',
        iconSize: [90, 28],
        iconAnchor: [14, 14]
      });
    }

    const redDotIcon = L.divIcon({
      html: '<div style="width:10px;height:10px;border-radius:50%;background:#ef4444;border:1.5px solid #ffffff;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>',
      className: 'poketan-dot-wrap',
      iconSize: [10, 10],
      iconAnchor: [5, 5]
    });

    const yellowDotIcon = L.divIcon({
      html: '<div style="width:8px;height:8px;border-radius:50%;background:#eab308;border:1px solid #ffffff;box-shadow:0 1px 2px rgba(0,0,0,0.2);"></div>',
      className: 'poketan-dot-wrap',
      iconSize: [8, 8],
      iconAnchor: [4, 4]
    });

    const grayDotIcon = L.divIcon({
      html: '<div style="width:8px;height:8px;border-radius:50%;background:#94a3b8;border:1px solid #ffffff;box-shadow:0 1px 2px rgba(0,0,0,0.2);"></div>',
      className: 'poketan-dot-wrap',
      iconSize: [8, 8],
      iconAnchor: [4, 4]
    });

    // Brand / Chain matching helper
    function matchesChainFilter(chain, filter) {
      if (!filter || filter === 'all') return true;
      const c = (chain || '').toLowerCase();
      if (filter === 'conbini') {
        return ['seven', 'lawson', 'familymart', 'ministop'].includes(c);
      }
      if (filter === 'specialty') {
        return c === 'specialty';
      }
      if (filter === 'electronics') {
        return ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi'].includes(c);
      }
      return c === filter;
    }

    // 6. RENDER MARKERS (CLUSTERS + IN-STOCK PINS)
    function renderMapMarkers() {
      clusterGroup.clearLayers();
      stockLayer.clearLayers();

      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const now = Math.floor(Date.now() / 1000);

      const clusterBatch = [];
      let newestInStore = null;
      let newestInfo = null;
      let maxTimestamp = 0;

      // Distance center (GPS coordinates or map center)
      const centerLat = userLat !== null ? userLat : (map ? map.getCenter().lat : null);
      const centerLng = userLng !== null ? userLng : (map ? map.getCenter().lng : null);

      const targetMapRegion = mapRegionFilter || currentRegion || 'osaka';
      const allowedMapPrefs = (REGIONS[targetMapRegion] ? REGIONS[targetMapRegion].prefs : [targetMapRegion]) || ['osaka'];

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;

        // 0. Khu vực hiển thị trên Bản đồ
        if (targetMapRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedMapPrefs.includes(storePref)) continue;
        }

        const sid = store.id;
        const raw = effectiveStatus[sid] || effectiveStatus[sid + '_c'];
        const info = decodeStatus(raw);

        // Find the newest in-stock report
        if (info.code === 'i') {
          const ts = info.timestamp || 0;
          if (ts > maxTimestamp) {
            maxTimestamp = ts;
            newestInStore = store;
            newestInfo = info;
          }
        }

        // 1. Trạng thái hàng hóa trên Bản đồ
        if (mapStatusFilter === 'in' && info.code !== 'i') continue;
        if (mapStatusFilter === 'onsite' && (!info.onsite || info.code !== 'i')) continue;
        if (mapStatusFilter === 'out' && info.code !== 'o') continue;
        if (mapStatusFilter === 'recent' && (info.code !== 'i' && !(info.timestamp > 0 && (now - info.timestamp <= 86400 * 7) && info.code !== 'n'))) continue;
        if (mapStatusFilter === 'unknown' && info.code !== 'u' && info.code) continue;

        // 2. Chuỗi cửa hàng / Thương hiệu trên Bản đồ
        if (!matchesChainFilter(store.chain, mapChainFilter)) continue;

        // 3. Thời gian hiển thị báo cáo trên Bản đồ
        if (mapTimeFilter && mapTimeFilter !== 'all') {
          const maxSec = parseInt(mapTimeFilter, 10) * 3600;
          if (!info.timestamp || (now - info.timestamp > maxSec)) continue;
        }

        const currentZoom = map ? map.getZoom() : 13;
        if (info.code === 'i') {
          // If close zoom (>= 12) or filter "Chỉ có hàng", show bouncing green pin with time badge
          const pinIcon = createStockPinIcon(info.timeAgo);
          if (currentZoom >= 12 || mapStatusFilter === 'in') {
            const m = L.marker([store.lat, store.lng], { icon: pinIcon, zIndexOffset: 2000 });
            m.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
            stockLayer.addLayer(m);
          } else {
            // When zoomed out, cluster cleanly with hasStock: true so the cluster ring glows green
            const cm = L.marker([store.lat, store.lng], {
              icon: pinIcon,
              hasStock: true
            });
            cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
            clusterBatch.push(cm);
          }
        } else {
          // Normal stores get added to clusterBatch with L.marker
          let dotIcon = grayDotIcon;
          if (info.code === 'o') dotIcon = redDotIcon;
          else if (info.code === 'n') dotIcon = yellowDotIcon;
          const cm = L.marker([store.lat, store.lng], {
            icon: dotIcon,
            hasStock: false
          });
          cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          clusterBatch.push(cm);
        }
      }

      // Fast batch add to clusterGroup
      if (clusterBatch.length > 0) {
        clusterGroup.addLayers(clusterBatch);
      }

      // Show/update stock alert toast with the NEWEST report
      const toastEl = document.getElementById('live-stock-toast');
      if (newestInStore && newestInStore.id !== dismissedToastStoreId) {
        latestStockStoreId = newestInStore.id;
        const titleEl = document.getElementById('toast-store-title');
        const timeEl = document.getElementById('toast-time');
        if (titleEl) titleEl.innerText = newestInStore.name;
        if (timeEl) timeEl.innerText = newestInfo.timeAgo || 'たった今';
        if (toastEl) toastEl.style.display = 'flex';
      } else {
        if (toastEl) toastEl.style.display = 'none';
      }
      if (typeof updateActiveFilterBadges === 'function') {
        updateActiveFilterBadges();
      }
    }

    // Store Report Counts Cache (🟢 Có hàng / 🔴 Hết hàng)
    const storeCountsCache = {};

    function getStoreCounts(storeId, currentCode) {
      if (storeCountsCache[storeId]) {
        return storeCountsCache[storeId];
      }
      const history = storeHistoryCache[storeId];
      if (history && Array.isArray(history)) {
        const inC = history.filter(x => x.status_code === 'i' || x.status === 'in-stock').length;
        const outC = history.filter(x => x.status_code === 'o' || x.status === 'out-of-stock').length;
        storeCountsCache[storeId] = { in: inC, out: outC, loaded: true };
        return storeCountsCache[storeId];
      }
      const defaultIn = (currentCode === 'i') ? 1 : 0;
      const defaultOut = (currentCode === 'o') ? 1 : 0;
      return { in: defaultIn, out: defaultOut, loaded: false };
    }

    async function loadStoreCounts(storeId) {
      if (storeCountsCache[storeId] && storeCountsCache[storeId].loaded) return;
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }
        if (Array.isArray(history)) {
          const inC = history.filter(x => x.status_code === 'i' || x.status === 'in-stock').length;
          const outC = history.filter(x => x.status_code === 'o' || x.status === 'out-of-stock').length;
          storeCountsCache[storeId] = { in: inC, out: outC, loaded: true };

          const pIn = document.getElementById(`count-in-${storeId}`);
          const pOut = document.getElementById(`count-out-${storeId}`);
          if (pIn) pIn.innerText = inC;
          if (pOut) pOut.innerText = outC;

          const lIn = document.getElementById(`list-count-in-${storeId}`);
          const lOut = document.getElementById(`list-count-out-${storeId}`);
          if (lIn) lIn.innerText = inC;
          if (lOut) lOut.innerText = outC;
        }
      } catch (e) {}
    }

    function createPopupHtml(store, info) {
      let distHtml = '';
      if (userLat !== null && userLng !== null) {
        const d = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        distHtml = `<div style="font-size:0.75rem; color:#4f46e5; font-weight:700; margin-top:2px;">📍 Hiện tại: cách ${formatDist(d)}</div>`;
      }

      let statusBg = '#f1f5f9';
      let statusColor = '#64748b';
      let statusText = '⚪ Chưa rõ / Không bán';
      if (info.code === 'i') {
        statusBg = '#dcfce7'; statusColor = '#15803d'; statusText = '🟢 Có hàng (In Stock)';
      } else if (info.code === 'o') {
        statusBg = '#fee2e2'; statusColor = '#b91c1c'; statusText = '🔴 Hết hàng (Out of Stock)';
      }

      const packs = (info.packs && info.packs.length) ? `<div style="font-size:0.74rem; margin-top:4px;"><b>📦 Gói:</b> ${info.packs.join(', ')}</div>` : '';
      const time = info.timeAgo ? `<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">🕒 Báo: <b>${escapeHtml(info.timeAgo)}</b> • ${escapeHtml(info.reported_at)}</div>` : '';
      const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
      const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((store.name || '') + ' ' + (store.address || ''))}`;

      const counts = getStoreCounts(store.id, info.code);
      setTimeout(() => loadStoreCounts(store.id), 25);

      const isHistOpen = openPopupHistStoreIds.has(store.id);
      const histDisplay = isHistOpen ? 'flex' : 'none';
      const histArrow = isHistOpen ? '▲' : '▼';
      const cachedHist = storeHistoryCache[store.id];
      const histInner = (isHistOpen && cachedHist) ? renderPopupHistoryItemsHtml(store.id, cachedHist) : '';

      return `
        <div>
          <div class="popup-store-title">${escapeHtml(store.name || '')}</div>
          <div class="popup-store-chain">${escapeHtml(chain)}</div>
          <div class="popup-status-badge" style="background:${statusBg}; color:${statusColor};">${statusText}</div>
          <div class="popup-report-counts-bar" id="popup-counts-${store.id}">
            <div class="report-count-tag tag-green" title="Số lần báo cáo có hàng">
              <span class="count-badge-icon">🟢</span>
              <span class="count-badge-label">Có hàng:</span>
              <b class="count-badge-val" id="count-in-${store.id}">${counts.in}</b> lần
            </div>
            <div class="report-count-tag tag-red" title="Số lần báo cáo hết hàng">
              <span class="count-badge-icon">🔴</span>
              <span class="count-badge-label">Hết hàng:</span>
              <b class="count-badge-val" id="count-out-${store.id}">${counts.out}</b> lần
            </div>
          </div>
          ${distHtml}
          ${time}
          ${packs}
          <div class="popup-actions-grid">
            <a href="${mapsUrl}" target="_blank" class="btn-popup-maps">🗺️ Chỉ đường ↗</a>
            <button type="button" class="btn-popup-hist" id="btn-hist-toggle-${store.id}" onclick="event.stopPropagation(); togglePopupHistory('${store.id}', this)">
              📜 入荷履歴 <span id="arrow-hist-${store.id}">${histArrow}</span>
            </button>
          </div>
          <div id="popup-hist-container-${store.id}" class="popup-hist-scroll" style="display:${histDisplay};">${histInner}</div>
        </div>
      `;
    }

    // 7. TOAST INTERACTIONS
    let dismissedToastStoreId = null;

    function focusStockStore() {
      if (!latestStockStoreId || !storesDict[latestStockStoreId]) return;
      const s = storesDict[latestStockStoreId];
      map.flyTo([s.lat, s.lng], 16, { duration: 0.8 });
      setTimeout(() => {
        stockLayer.eachLayer(m => {
          const ll = m.getLatLng();
          if (Math.abs(ll.lat - s.lat) < 0.0001 && Math.abs(ll.lng - s.lng) < 0.0001) {
            m.openPopup();
          }
        });
      }, 850);
    }
    window.focusStockStore = focusStockStore;

    function hideToast() {
      dismissedToastStoreId = latestStockStoreId;
      const toastEl = document.getElementById('live-stock-toast');
      if (toastEl) toastEl.style.display = 'none';
    }
    window.hideToast = hideToast;

    // 8. FILTER & SORT MODAL HANDLERS (Dành riêng cho Trang Báo Cáo - Khu vực + 5 Tiêu chí)
    let modalTempRegion = currentRegion || 'osaka';
    let modalTempFilter = 'all';
    let modalTempChain = 'all';
    let modalTempTime = 'all';
    let modalTempRadius = 'all';
    let modalTempSort = 'newest';

    function openFilterModal() {
      modalTempRegion = listRegionFilter || currentRegion || 'osaka';
      modalTempFilter = listStatusFilter || 'all';
      modalTempChain = listChainFilter || 'all';
      modalTempTime = String(listTimeFilter || 'all');
      modalTempRadius = String(listRadiusFilter || 'all');
      modalTempSort = listSortMode || 'newest';
      syncFilterModalUI();
      const modal = document.getElementById('filter-modal');
      if (modal) modal.classList.add('open');
    }
    window.openFilterModal = openFilterModal;

    function closeFilterModal() {
      const modal = document.getElementById('filter-modal');
      if (modal) modal.classList.remove('open');
    }
    window.closeFilterModal = closeFilterModal;

    function syncFilterModalUI() {
      // 0. Khu vực hiển thị
      document.querySelectorAll('#modal-region-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempRegion);
      });
      // 1. Trạng thái hàng hóa
      document.querySelectorAll('#modal-status-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempFilter);
      });
      // 2. Chuỗi & Thương hiệu
      document.querySelectorAll('#modal-chain-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempChain);
      });
      // 3. Thời gian hiển thị
      document.querySelectorAll('#modal-time-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempTime);
      });
      // 4. Bán kính khoảng cách
      document.querySelectorAll('#modal-radius-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempRadius);
      });
      // 5. Thứ tự sắp xếp
      document.querySelectorAll('#modal-sort-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === modalTempSort);
      });
    }

    function selectModalRegion(val) {
      modalTempRegion = val;
      syncFilterModalUI();
    }
    window.selectModalRegion = selectModalRegion;

    function selectModalStatus(val) {
      modalTempFilter = val;
      syncFilterModalUI();
    }
    window.selectModalStatus = selectModalStatus;

    function selectModalChain(val) {
      modalTempChain = val;
      syncFilterModalUI();
    }
    window.selectModalChain = selectModalChain;

    function selectModalTime(val) {
      modalTempTime = val;
      syncFilterModalUI();
    }
    window.selectModalTime = selectModalTime;

    function selectModalRadius(val) {
      modalTempRadius = val;
      if (val !== 'all' && userLat === null && typeof locateUser === 'function') {
        locateUser(false);
      }
      syncFilterModalUI();
    }
    window.selectModalRadius = selectModalRadius;

    function selectModalSort(val) {
      modalTempSort = val;
      if (val === 'nearest' && userLat === null && typeof locateUser === 'function') {
        locateUser(false);
      }
      syncFilterModalUI();
    }
    window.selectModalSort = selectModalSort;

    function resetAllFilters() {
      modalTempRegion = currentRegion || 'osaka';
      modalTempFilter = 'all';
      modalTempChain = 'all';
      modalTempTime = 'all';
      modalTempRadius = 'all';
      modalTempSort = 'newest';
      syncFilterModalUI();
    }
    window.resetAllFilters = resetAllFilters;

    function applyAndCloseFilterModal() {
      listRegionFilter = modalTempRegion;
      listStatusFilter = modalTempFilter;
      listChainFilter = modalTempChain;
      listTimeFilter = modalTempTime;
      listRadiusFilter = modalTempRadius;
      listSortMode = modalTempSort;

      const chainSel = document.getElementById('list-chain-select');
      if (chainSel) chainSel.value = listChainFilter;
      const timeSel = document.getElementById('list-time-select');
      if (timeSel) timeSel.value = listTimeFilter;

      // Update list sort mode buttons
      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.remove('active'));
      const activeSortBtn = document.getElementById(`sort-btn-${listSortMode}`);
      if (activeSortBtn) activeSortBtn.classList.add('active');

      updateListFilterBadges();
      closeFilterModal();

      // Chỉ lọc lại danh sách báo cáo, KHÔNG làm mất ghim trên bản đồ!
      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.applyAndCloseFilterModal = applyAndCloseFilterModal;

    function updateListFilterBadges() {
      let count = 0;
      if (listRegionFilter && listRegionFilter !== 'all') count++;
      if (listStatusFilter && listStatusFilter !== 'all') count++;
      if (listChainFilter && listChainFilter !== 'all') count++;
      if (listTimeFilter && listTimeFilter !== 'all') count++;
      if (listRadiusFilter && listRadiusFilter !== 'all') count++;
      if (listSortMode && listSortMode !== 'newest') count++;

      ['list-filter-active-badge', 'list-filter-active-badge-2'].forEach(id => {
        const b = document.getElementById(id);
        if (b) {
          if (count > 0) {
            b.innerText = count;
            b.style.display = 'inline-block';
          } else {
            b.style.display = 'none';
          }
        }
      });

      // Update list tabs
      const tabs = ['all', 'in', 'onsite', 'out', 'recent', 'unknown'];
      tabs.forEach(t => {
        const btn = document.getElementById(`list-tab-${t}`);
        if (btn) btn.classList.toggle('active', listStatusFilter === t || (t === 'all' && listStatusFilter === 'hidenone'));
      });
    }
    window.updateListFilterBadges = updateListFilterBadges;

    // 7. MAP FILTER MODAL HANDLERS (Dành riêng cho Bản đồ: Khu vực + Trạng thái + Chuỗi + Thời gian)
    let mapModalTempRegion = currentRegion || 'osaka';
    let mapModalTempStatus = 'all';
    let mapModalTempChain = 'all';
    let mapModalTempTime = 'all';

    function openMapFilterModal() {
      mapModalTempRegion = mapRegionFilter || currentRegion || 'osaka';
      mapModalTempStatus = mapStatusFilter || 'all';
      mapModalTempChain = mapChainFilter || 'all';
      mapModalTempTime = String(mapTimeFilter || 'all');
      syncMapFilterModalUI();
      const modal = document.getElementById('map-filter-modal');
      if (modal) modal.classList.add('open');
    }
    window.openMapFilterModal = openMapFilterModal;

    function closeMapFilterModal() {
      const modal = document.getElementById('map-filter-modal');
      if (modal) modal.classList.remove('open');
    }
    window.closeMapFilterModal = closeMapFilterModal;

    function syncMapFilterModalUI() {
      document.querySelectorAll('#map-modal-region-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempRegion);
      });
      document.querySelectorAll('#map-modal-status-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempStatus);
      });
      document.querySelectorAll('#map-modal-chain-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempChain);
      });
      document.querySelectorAll('#map-modal-time-group .filter-option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempTime);
      });
    }

    function selectMapModalRegion(val) {
      mapModalTempRegion = val;
      syncMapFilterModalUI();
    }
    window.selectMapModalRegion = selectMapModalRegion;

    function selectMapModalStatus(val) {
      mapModalTempStatus = val;
      syncMapFilterModalUI();
    }
    window.selectMapModalStatus = selectMapModalStatus;

    function selectMapModalChain(val) {
      mapModalTempChain = val;
      syncMapFilterModalUI();
    }
    window.selectMapModalChain = selectMapModalChain;

    function selectMapModalTime(val) {
      mapModalTempTime = val;
      syncMapFilterModalUI();
    }
    window.selectMapModalTime = selectMapModalTime;

    function resetMapFilters() {
      mapModalTempRegion = currentRegion || 'osaka';
      mapModalTempStatus = 'all';
      mapModalTempChain = 'all';
      mapModalTempTime = 'all';
      syncMapFilterModalUI();
    }
    window.resetMapFilters = resetMapFilters;

    function applyAndCloseMapFilterModal() {
      const regionChanged = (mapRegionFilter !== mapModalTempRegion);
      mapRegionFilter = mapModalTempRegion;
      mapStatusFilter = mapModalTempStatus;
      mapChainFilter = mapModalTempChain;
      mapTimeFilter = mapModalTempTime;

      closeMapFilterModal();
      updateMapFilterUI();

      if (regionChanged && mapRegionFilter !== 'all') {
        selectRegion(mapRegionFilter, true);
      } else {
        renderMapMarkers();
      }
    }
    window.applyAndCloseMapFilterModal = applyAndCloseMapFilterModal;

    // MAP FILTER HANDLERS (Dành riêng cho Bản đồ: Phím tắt chip nhanh ngoài bản đồ)
    function setMapStatusFilter(st) {
      mapStatusFilter = st;
      activeFilter = st;
      updateMapFilterUI();
      renderMapMarkers();
    }
    window.setMapStatusFilter = setMapStatusFilter;

    function setMapChainFilter(chain) {
      mapChainFilter = chain;
      activeChain = chain;
      updateMapFilterUI();
      renderMapMarkers();
    }
    window.setMapChainFilter = setMapChainFilter;

    function updateMapFilterUI() {
      ['all', 'in', 'recent', 'out'].forEach(st => {
        const btn = document.getElementById(`map-chip-${st}`);
        if (btn) btn.classList.toggle('active', mapStatusFilter === st);
      });
      const sel = document.getElementById('map-chain-select');
      if (sel) {
        sel.value = mapChainFilter;
        sel.classList.toggle('active', mapChainFilter !== 'all');
      }

      // Update badge on map filter button
      let count = 0;
      if (mapRegionFilter && mapRegionFilter !== 'all' && mapRegionFilter !== currentRegion) count++;
      if (mapStatusFilter && mapStatusFilter !== 'all') count++;
      if (mapChainFilter && mapChainFilter !== 'all') count++;
      if (mapTimeFilter && mapTimeFilter !== 'all') count++;
      const badge = document.getElementById('map-filter-badge');
      if (badge) {
        badge.innerText = count;
        badge.style.display = count > 0 ? 'inline-flex' : 'none';
      }
    }
    window.updateMapFilterUI = updateMapFilterUI;

    function updateActiveFilterBadges() {
      updateMapFilterUI();
      updateListFilterBadges();
    }
    window.updateActiveFilterBadges = updateActiveFilterBadges;

    // Backward-compatible individual handlers
    function quickSelectStatus(st) {
      setMapStatusFilter(st);
    }
    window.quickSelectStatus = quickSelectStatus;

    function setStatusFilter(filterName) {
      setMapStatusFilter(filterName);
    }
    window.setStatusFilter = setStatusFilter;

    function setChainFilter(chain) {
      setMapChainFilter(chain);
    }
    window.setChainFilter = setChainFilter;

    function toggleFilter(filterName) {
      setMapStatusFilter(mapStatusFilter === filterName ? 'all' : filterName);
    }
    window.toggleFilter = toggleFilter;

    function setRadiusFilter(km) {
      setListRadiusFilter(km);
    }
    window.setRadiusFilter = setRadiusFilter;

    function setTimeFilter(val) {
      setListTimeFilter(val);
    }
    window.setTimeFilter = setTimeFilter;

    function setListRadiusFilter(val) {
      listRadiusFilter = String(val);
      if (listRadiusFilter !== 'all' && userLat === null && typeof locateUser === 'function') {
        locateUser(false);
      }
      updateListFilterBadges();
      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.setListRadiusFilter = setListRadiusFilter;

    function setListTimeFilter(val) {
      listTimeFilter = String(val);
      updateListFilterBadges();
      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.setListTimeFilter = setListTimeFilter;

    // 9. GACHI MEGURI (⚡ Săn thẻ - Instant Quick Hunt)
    function triggerGachiMeguri() {
      // Switch filter to only in-stock stores & reset other filters
      setStatusFilter('in');
      setChainFilter('all');
      activeRadius = null;
      setTimeFilter('all');
      [1, 3, 5, 10].forEach(d => {
        const btn = document.getElementById(`chip-dist-${d}`);
        if (btn) btn.classList.remove('active');
      });

      renderMapMarkers();
      switchFooterTab('map');

      // Find nearest in-stock store or first in-stock store
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const inStockStores = Object.values(storesDict).filter(s => {
        if (currentPref !== 'all' && s.pref !== currentPref) return false;
        const info = decodeStatus(effectiveStatus[s.id] || effectiveStatus[s.id + '_c']);
        return info.code === 'i';
      });

      if (inStockStores.length > 0) {
        let target = inStockStores[0];
        if (userLat !== null && userLng !== null) {
          inStockStores.sort((a,b) => calcDistanceKm(userLat, userLng, a.lat, a.lng) - calcDistanceKm(userLat, userLng, b.lat, b.lng));
          target = inStockStores[0];
        }
        map.flyTo([target.lat, target.lng], 16, { duration: 1.0 });
      } else {
        alert('現在、選択したエリアに在庫あり店舗はありません。');
      }
    }
    window.triggerGachiMeguri = triggerGachiMeguri;

    // 10. FOOTER NAVIGATION TABS
    function switchFooterTab(tab) {
      document.querySelectorAll('.footer-tab-btn').forEach(b => b.classList.remove('active'));

      if (tab === 'map') {
        document.getElementById('f-tab-map').classList.add('active');
        document.getElementById('view-list-container').classList.remove('open');
        setTimeout(() => map.invalidateSize(), 50);
      } else if (tab === 'list') {
        document.getElementById('f-tab-list').classList.add('active');
        renderStoreList();
        document.getElementById('view-list-container').classList.add('open');
      }
    }
    window.switchFooterTab = switchFooterTab;

    let listOnlyInStock = false;

    function setListSortMode(mode) {
      listSortMode = mode;
      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`sort-btn-${mode}`);
      if (activeBtn) activeBtn.classList.add('active');

      if (mode === 'nearest') {
        if (userLat === null || userLng === null) {
          locateUser(false);
        }
      }

      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.setListSortMode = setListSortMode;

    function setListStatusTab(tab) {
      listStatusFilter = tab;
      const tabs = ['all', 'in', 'onsite', 'out', 'recent', 'unknown'];
      tabs.forEach(t => {
        const btn = document.getElementById(`list-tab-${t}`);
        if (btn) {
          if (t === tab) btn.classList.add('active');
          else btn.classList.remove('active');
        }
      });
      updateListFilterBadges();
      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.setListStatusTab = setListStatusTab;

    function setListChainFilter(chain) {
      listChainFilter = chain;
      const selectEl = document.getElementById('list-chain-select');
      if (selectEl && selectEl.value !== chain) {
        selectEl.value = chain;
      }
      updateListFilterBadges();
      const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(q);
    }
    window.setListChainFilter = setListChainFilter;

    function toggleListInStockFilter() {
      setListStatusTab(listStatusFilter === 'in' ? 'all' : 'in');
    }
    window.toggleListInStockFilter = toggleListInStockFilter;

    // 11. STORE LIST VIEW (一覧 • Cập nhật thông tin báo cáo)
    function renderStoreList(query = '') {
      const listContainer = document.getElementById('store-cards-list');
      if (!listContainer) return;
      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const now = Math.floor(Date.now() / 1000);
      const q = query.toLowerCase().trim();

      // Update real-time synchronization banner text matching active list filters
      // 0. Khu vực / Vùng hiển thị (Region Filter)
      const targetRegion = listRegionFilter || currentRegion || 'osaka';
      let regName = 'Osaka';
      if (targetRegion === 'tokyo') regName = 'Tokyo & Kanagawa';
      else if (targetRegion === 'nagoya') regName = 'Nagoya & Tokai';
      else if (targetRegion === 'all') regName = 'Toàn quốc';

      // Update real-time synchronization banner text matching active list filters
      const bannerTextEl = document.getElementById('list-active-settings-text');
      if (bannerTextEl) {
        let statusName = 'Tất cả trạng thái';
        if (listStatusFilter === 'in') statusName = '🟢 Có hàng';
        else if (listStatusFilter === 'onsite') statusName = '📍 Tại quán (GPS)';
        else if (listStatusFilter === 'hidenone') statusName = '⚪ Ẩn quán ko bán';
        else if (listStatusFilter === 'out') statusName = '🔴 Hết hàng';
        else if (listStatusFilter === 'recent') statusName = '★ Từng có gần đây';
        else if (listStatusFilter === 'unknown') statusName = '⚪ Chưa rõ';

        let chainName = 'Tất cả chuỗi';
        if (listChainFilter && listChainFilter !== 'all') {
          const cNames = {
            'conbini': 'Conbini', 'seven': '7-Eleven', 'lawson': 'Lawson',
            'familymart': 'FamilyMart', 'ministop': 'Ministop',
            'specialty': 'Card Shop', 'electronics': 'Điện máy'
          };
          chainName = cNames[listChainFilter] || listChainFilter;
        }

        let timeName = 'Toàn thời gian';
        if (listTimeFilter && listTimeFilter !== 'all') {
          timeName = (listTimeFilter === '72') ? '3 ngày qua' : `${listTimeFilter}h qua`;
        }

        let radiusName = 'Không giới hạn bán kính';
        if (listRadiusFilter && listRadiusFilter !== 'all') {
          radiusName = `Bán kính ${listRadiusFilter}km`;
        }

        bannerTextEl.innerText = `${regName} • ${statusName} • ${chainName} • ${timeName} • ${radiusName}`;
      }

      const tgTag = document.getElementById('list-tg-status-tag');
      if (tgTag) {
        const isTgOn = !!configData.telegramEnabled;
        tgTag.innerText = isTgOn ? '✈️ Telegram: BẬT' : '✈️ Telegram: TẮT';
        tgTag.style.background = isTgOn ? '#dcfce7' : '#fee2e2';
        tgTag.style.color = isTgOn ? '#15803d' : '#b91c1c';
      }

      let matched = [];
      const allowedPrefs = (REGIONS[targetRegion] ? REGIONS[targetRegion].prefs : [targetRegion]) || ['osaka'];

      for (const store of allStores) {
        // 0. Lọc đúng khu vực / vùng đã chọn (Ví dụ: Osaka chỉ hiện quán ở Osaka!)
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }

        const info = decodeStatus(effectiveStatus[store.id] || effectiveStatus[store.id + '_c']);

        // 1. Trạng thái hàng hóa (List Status Tab / Modal Filter)
        if (listStatusFilter === 'in' && info.code !== 'i') continue;
        if (listStatusFilter === 'onsite' && (!info.onsite || info.code !== 'i')) continue;
        if (listStatusFilter === 'hidenone' && info.code === 'n') continue;
        if (listStatusFilter === 'out' && info.code !== 'o') continue;
        if (listStatusFilter === 'recent' && (info.code !== 'i' && !(info.timestamp > 0 && (now - info.timestamp <= 86400 * 7) && info.code !== 'n'))) continue;
        if (listStatusFilter === 'unknown' && info.code !== 'u' && info.code) continue;

        // 2. Chuỗi cửa hàng & Thương hiệu
        if (!matchesChainFilter(store.chain, listChainFilter)) continue;

        // 3. Thời gian hiển thị báo cáo
        if (listTimeFilter && listTimeFilter !== 'all') {
          const maxSec = parseInt(listTimeFilter, 10) * 3600;
          if (!info.timestamp || (now - info.timestamp > maxSec)) continue;
        }

        if (q) {
          const mName = (store.name || '').toLowerCase().includes(q);
          const mAddr = (store.address || '').toLowerCase().includes(q);
          if (!mName && !mAddr) continue;
        }

        // 4. Bán kính khoảng cách quanh bạn
        let dist = null;
        if (userLat !== null && userLng !== null && store.lat && store.lng) {
          dist = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        }
        if (listRadiusFilter && listRadiusFilter !== 'all') {
          const maxKm = parseFloat(listRadiusFilter);
          if (dist === null || dist > maxKm) continue;
        }

        matched.push({ store, info, dist });
      }

      // Update count badge
      const countBadge = document.getElementById('list-count-badge');
      if (countBadge) {
        countBadge.innerText = `${matched.length.toLocaleString()} quán`;
      }

      // 5. Thứ tự sắp xếp danh sách (Mới nhất hoặc Gần nhất)
      matched.sort((a,b) => {
        if (a.info.code === 'i' && b.info.code !== 'i') return -1;
        if (b.info.code === 'i' && a.info.code !== 'i') return 1;

        if (listSortMode === 'nearest') {
          if (a.dist !== null && b.dist !== null) return a.dist - b.dist;
          if (a.dist !== null) return -1;
          if (b.dist !== null) return 1;
          return (b.info.timestamp || 0) - (a.info.timestamp || 0);
        } else {
          // 'newest' by report timestamp
          const diffTs = (b.info.timestamp || 0) - (a.info.timestamp || 0);
          if (diffTs !== 0) return diffTs;
          if (a.dist !== null && b.dist !== null) return a.dist - b.dist;
          return 0;
        }
      });

      if (matched.length === 0) {
        if (listRadiusFilter && listRadiusFilter !== 'all' && (userLat === null || userLng === null)) {
          listContainer.innerHTML = `
            <div style="text-align:center; padding:36px 12px; color:#64748b;">
              <div style="font-size:2rem; margin-bottom:8px;">📍</div>
              <div style="font-weight:700; color:#334155; font-size:0.88rem;">Chưa xác định được vị trí GPS của bạn</div>
              <div style="font-size:0.75rem; margin-top:4px;">Bạn đang lọc theo bán kính ${listRadiusFilter} km. Vui lòng bấm nút dưới đây để lấy vị trí GPS hoặc tắt bộ lọc bán kính.</div>
              <button onclick="locateUser(true)" style="margin-top:12px; background:#4f46e5; color:#ffffff; border:none; padding:8px 16px; border-radius:8px; font-weight:800; cursor:pointer;">📍 Xác định vị trí ngay</button>
            </div>
          `;
        } else {
          listContainer.innerHTML = `
            <div style="text-align:center; padding:36px 12px; color:#64748b;">
              <div style="font-size:2rem; margin-bottom:8px;">📭</div>
              <div style="font-weight:700; color:#334155; font-size:0.88rem;">Không tìm thấy báo cáo cửa hàng phù hợp</div>
              <div style="font-size:0.75rem; margin-top:4px;">Thử đổi từ khóa hoặc bấm [⚙️ Bộ lọc & Sắp xếp] để điều chỉnh tiêu chí.</div>
            </div>
          `;
        }
        return;
      }

      // Limit 120 for instant performance
      const renderSlice = matched.slice(0, 120);

      listContainer.innerHTML = renderSlice.map(item => {
        const { store, info, dist } = item;
        let badgeClass = 'badge-none';
        let badgeText = '⚪ Chưa rõ';
        if (info.code === 'i') { badgeClass = 'badge-in'; badgeText = '🟢 Có hàng'; }
        else if (info.code === 'o') { badgeClass = 'badge-out'; badgeText = '🔴 Hết hàng'; }
        else if (info.code === 'n') { badgeClass = 'badge-none'; badgeText = '⚪ Không bán'; }

        const onsiteBadge = (info.onsite && info.code === 'i')
          ? `<span class="card-badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; padding:2px 6px; font-size:0.68rem; margin-left:0;">📸 Tại chỗ</span>`
          : '';

        const counts = getStoreCounts(store.id, info.code);

        const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
        const distStr = dist !== null ? ` • 📍 Cách ${formatDist(dist)}` : '';
        const timeStr = info.timeAgo ? ` • 🕒 ${escapeHtml(info.timeAgo)}${info.reported_at ? ` • ${escapeHtml(info.reported_at)}` : ''}` : '';
        const packHtml = (info.packs && info.packs.length > 0)
          ? `<div style="font-size:0.72rem; color:#2563eb; font-weight:700; margin-top:3px;">📦 ${escapeHtml(info.packs.join(', '))}</div>`
          : '';

        return `
          <div class="store-list-card" onclick="focusStoreFromList('${store.id}')">
            <div class="card-left-info">
              <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span class="card-badge ${badgeClass}" style="margin-left:0; padding:2px 6px; font-size:0.68rem;">${badgeText}</span>
                ${onsiteBadge}
                <div class="card-store-name">${escapeHtml(store.name || '')}</div>
              </div>
              <div class="card-chain-time">${escapeHtml(chain)}${distStr}${timeStr}</div>
              <div class="popup-report-counts-bar" style="margin:4px 0 2px 0;">
                <span class="report-count-tag tag-green" style="padding:1px 7px; font-size:0.67rem; border-radius:10px;">
                  <span class="count-badge-icon" style="font-size:0.7rem;">🟢</span>
                  <span>Có: <b id="list-count-in-${store.id}">${counts.in}</b> lần</span>
                </span>
                <span class="report-count-tag tag-red" style="padding:1px 7px; font-size:0.67rem; border-radius:10px;">
                  <span class="count-badge-icon" style="font-size:0.7rem;">🔴</span>
                  <span>Hết: <b id="list-count-out-${store.id}">${counts.out}</b> lần</span>
                </span>
              </div>
              ${packHtml}
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:5px; flex-shrink:0;">
              <button type="button" onclick="event.stopPropagation(); focusStoreFromList('${store.id}')"
                      style="background:#4f46e5; color:white; border:none; border-radius:6px; padding:4px 8px; font-size:0.68rem; font-weight:700; cursor:pointer;">
                🗺️ Bản đồ
              </button>
              <button type="button" onclick="event.stopPropagation(); openStoreHistoryModal('${store.id}')"
                      style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:6px; padding:3px 8px; font-size:0.65rem; font-weight:700; color:#334155; cursor:pointer;">
                📜 Lịch sử
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function onListSearch(val) {
      renderStoreList(val);
    }
    window.onListSearch = onListSearch;

    function focusStoreFromList(storeId) {
      switchFooterTab('map');
      const store = storesDict[storeId];
      if (store) {
        map.flyTo([store.lat, store.lng], 16, { duration: 0.8 });
      }
    }
    window.focusStoreFromList = focusStoreFromList;

    // 12. PREFECTURE & AREA MODAL (PokéTan replica handlers)
    let currentCity = 'なんば';

    function openPrefModal() {
      document.getElementById('pref-modal').classList.add('open');
      const input = document.getElementById('area-search-input');
      if (input) {
        setTimeout(() => input.focus(), 150);
      }
    }
    window.openPrefModal = openPrefModal;

    function closePrefModal() {
      document.getElementById('pref-modal').classList.remove('open');
    }
    window.closePrefModal = closePrefModal;

    // REGION TOAST & SELECTOR HANDLERS
    let regionToastTimer = null;
    function showRegionToast(msg, icon = '🔄') {
      const toast = document.getElementById('region-load-toast');
      if (!toast) return;
      if (regionToastTimer) clearTimeout(regionToastTimer);
      const iconEl = document.getElementById('region-load-icon');
      const textEl = document.getElementById('region-load-text');
      if (iconEl) iconEl.innerText = icon;
      if (textEl) textEl.innerText = msg;
      toast.style.display = 'inline-flex';
    }
    window.showRegionToast = showRegionToast;

    function hideRegionToast(delay = 0) {
      if (regionToastTimer) clearTimeout(regionToastTimer);
      if (delay > 0) {
        regionToastTimer = setTimeout(() => {
          const toast = document.getElementById('region-load-toast');
          if (toast) toast.style.display = 'none';
        }, delay);
      } else {
        const toast = document.getElementById('region-load-toast');
        if (toast) toast.style.display = 'none';
      }
    }
    window.hideRegionToast = hideRegionToast;

    let isRegionLoading = false;
    async function selectRegion(regionId, flyToRegion = true) {
      if (!REGIONS[regionId]) regionId = 'osaka';
      if (isRegionLoading) return;

      currentRegion = regionId;
      window.currentRegion = currentRegion;
      mapRegionFilter = regionId;
      listRegionFilter = regionId;
      localStorage.setItem('poketan_selected_region', regionId);
      updateSettings('currentRegion', regionId);

      // Sync radio in Settings Modal
      const radios = document.querySelectorAll('input[name="set-region-radio"]');
      radios.forEach(r => {
        r.checked = (r.value === regionId);
      });

      const regObj = REGIONS[regionId];
      currentPref = regObj.prefs[0] || 'osaka';
      if (flyToRegion) {
        currentCity = regObj.defaultCity;
        const headerLoc = document.getElementById('header-loc-name');
        if (headerLoc) {
          headerLoc.innerText = (regObj.id === 'all') ? '全エリア' : `${regObj.defaultCity}周辺`;
        }
        if (regObj.center) {
          map.flyTo(regObj.center, regObj.zoom, { animate: true, duration: 1.0 });
        }
      }

      // If storesDict is not fully loaded, load all stores
      if (!storesDict || Object.keys(storesDict).length === 0) {
        showRegionToast(`Đang tải dữ liệu toàn quốc...`, '⏳');
        isRegionLoading = true;
        try {
          const [storesRes, hotRes, coldRes] = await Promise.all([
            fetch('/api/stores_data?region=all'),
            fetch('/api/hot_status?region=all').catch(() => null),
            fetch('/api/cold_status?region=all').catch(() => null)
          ]);

          if (storesRes && storesRes.ok) {
            storesDict = await storesRes.json();
            window.storesDict = storesDict;
          }
          if (hotRes && hotRes.ok) {
            try { hotStatus = await hotRes.json(); } catch(e) {}
          }
          if (coldRes && coldRes.ok) {
            try { coldStatus = await coldRes.json(); } catch(e) {}
          }
        } catch (err) {
          console.error('Error loading data:', err);
        } finally {
          isRegionLoading = false;
        }
      }

      // Render markers on map
      renderMapMarkers();
      const listContainer = document.getElementById('view-list-container');
      if (listContainer && listContainer.classList.contains('open')) {
        renderStoreList();
      }

      const count = Object.keys(storesDict).length;
      showRegionToast(`Đã chuyển tới ${regObj.name} (${count} quán)`, '⚡');
      hideRegionToast(2000);
    }
    window.selectRegion = selectRegion;

    async function selectCityArea(pref, cityName, lat, lng, zoom) {
      const targetRegion = getRegionForPref(pref);
      if (currentRegion !== 'all' && currentRegion !== targetRegion) {
        await selectRegion(targetRegion, false);
      }

      currentPref = pref;
      currentCity = cityName;
      dismissedToastStoreId = null;

      // Update location pill title in header
      const locLabel = (cityName === '全エリア' || cityName === '全国') ? '全エリア' : `${cityName}周辺`;
      const headerLoc = document.getElementById('header-loc-name');
      if (headerLoc) headerLoc.innerText = locLabel;

      // Update active chip state
      document.querySelectorAll('.area-chip').forEach(chip => {
        if (chip.getAttribute('data-city') === cityName) {
          chip.classList.add('active');
        } else {
          chip.classList.remove('active');
        }
      });

      // Fly map to area
      if (lat && lng) {
        map.flyTo([lat, lng], zoom || 14, { animate: true, duration: 1.0 });
      }

      // Re-render markers for the area
      renderMapMarkers();

      // Close modal
      closePrefModal();
    }
    window.selectCityArea = selectCityArea;

    function useGpsLocation() {
      closePrefModal();
      locateUser(true);
      const headerLoc = document.getElementById('header-loc-name');
      if (headerLoc) headerLoc.innerText = '現在地周辺';
      document.querySelectorAll('.area-chip').forEach(c => c.classList.remove('active'));
    }
    window.useGpsLocation = useGpsLocation;

    function searchAreaLocation() {
      const input = document.getElementById('area-search-input');
      if (!input) return;
      const q = input.value.trim().toLowerCase();
      if (!q) return;

      // 1. Check known cities
      const cityMap = {
        '名古屋': ['aichi', '名古屋駅', 35.1709, 136.8815, 14],
        '栄': ['aichi', '栄', 35.1698, 136.9084, 14],
        '豊田': ['aichi', '豊田', 35.0833, 137.1500, 13],
        '岡崎': ['aichi', '岡崎', 34.9550, 137.1683, 13],
        '一宮': ['aichi', '一宮', 35.3039, 136.8000, 13],
        '豊橋': ['aichi', '豊橋', 34.7628, 137.3817, 13],
        '梅田': ['osaka', '梅田', 34.7024, 135.4959, 14],
        'なんば': ['osaka', 'なんば', 34.6669, 135.5013, 14],
        '難波': ['osaka', 'なんば', 34.6669, 135.5013, 14],
        '天王寺': ['osaka', '天王寺', 34.6472, 135.5139, 14],
        '堺': ['osaka', '堺', 34.5733, 135.4830, 13],
        '枚方': ['osaka', '枚方', 34.8148, 135.6508, 13],
        '大阪': ['osaka', 'なんば', 34.6669, 135.5013, 14],
        '愛知': ['aichi', '名古屋駅', 35.1709, 136.8815, 14],
        '神奈川': ['kanagawa', '横浜', 35.4437, 139.6380, 14],
        '横浜': ['kanagawa', '横浜', 35.4437, 139.6380, 14],
        '川崎': ['kanagawa', '川崎', 35.5308, 139.7029, 14],
        '相模原': ['kanagawa', '相模原', 35.5714, 139.3732, 13],
        '藤沢': ['kanagawa', '藤沢', 35.3389, 139.4889, 13]
      };

      for (const [key, val] of Object.entries(cityMap)) {
        if (key.includes(q) || q.includes(key)) {
          selectCityArea(val[0], val[1], val[2], val[3], val[4]);
          return;
        }
      }

      // 2. Search in allStores
      const allStores = Object.values(storesDict);
      const matched = allStores.find(s => 
        (s.name && s.name.toLowerCase().includes(q)) || 
        (s.address && s.address.toLowerCase().includes(q))
      );
      if (matched) {
        selectCityArea(matched.pref || 'osaka', matched.name, matched.lat, matched.lng, 16);
        return;
      }

      alert('「' + input.value + '」に一致するエリアや店舗が見つかりませんでした。別のキーワードをお試しください。');
    }
    window.searchAreaLocation = searchAreaLocation;

    function voteForNewPrefecture() {
      alert('🗳️ 投票を受け付けました！\\n今後のエリア拡大リクエストありがとうございます。');
    }
    window.voteForNewPrefecture = voteForNewPrefecture;

    function selectPrefecture(pref, label) {
      const cityMap = {
        'osaka': ['なんば', 34.6669, 135.5013, 14],
        'aichi': ['名古屋駅', 35.1709, 136.8815, 14],
        'kanagawa': ['横浜', 35.4437, 139.6380, 14],
        'gifu': ['岐阜', 35.4233, 136.7607, 12],
        'mie': ['三重', 34.7303, 136.5086, 12],
        'all': ['全エリア', 34.6937, 135.5023, 10]
      };
      const info = cityMap[pref] || ['全エリア', 34.6937, 135.5023, 10];
      selectCityArea(pref, info[0], info[1], info[2], info[3]);
    }
    window.selectPrefecture = selectPrefecture;

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
      });
    }

    // 13. BULLETIN MODAL (💬 掲示板)
    function openBulletinModal() {
      const container = document.getElementById('bulletin-list');
      const allStores = Object.values(storesDict);
      const effectiveStatus = Object.assign({}, coldStatus, hotStatus);
      
      const targetPrefs = REGIONS[currentRegion] ? REGIONS[currentRegion].prefs : ['osaka'];
      const inStockList = allStores.filter(s => {
        if (currentRegion !== 'all' && !targetPrefs.includes(s.pref) && s.pref !== currentPref) return false;
        const info = decodeStatus(effectiveStatus[s.id] || effectiveStatus[s.id + '_c']);
        return info.code === 'i';
      });

      inStockList.sort((a, b) => {
        const infoA = decodeStatus(effectiveStatus[a.id] || effectiveStatus[a.id + '_c']);
        const infoB = decodeStatus(effectiveStatus[b.id] || effectiveStatus[b.id + '_c']);
        return (infoB.timestamp || 0) - (infoA.timestamp || 0);
      });

      if (inStockList.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:32px 12px; color:#64748b;">
            <div style="font-size:2.2rem; margin-bottom:8px;">📭</div>
            <div style="font-weight:700; color:#334155; font-size:0.9rem;">現在、選択エリアに入荷速報はありません</div>
            <div style="font-size:0.75rem; margin-top:4px;">Telegramやユーザーからの新着情報を受信するとここに表示されます。</div>
            <button onclick="refreshData();" style="margin-top:16px; padding:8px 18px; background:#4f46e5; color:white; border:none; border-radius:8px; font-weight:700; cursor:pointer;">
              🔄 最新データを再読込
            </button>
          </div>
        `;
      } else {
        const prefName = document.getElementById('header-loc-name') ? document.getElementById('header-loc-name').innerText : 'エリア';
        container.innerHTML = `
          <div style="margin-bottom:12px; font-size:0.75rem; color:#64748b; font-weight:700;">
            🔔 ${prefName} の入荷速報 (${inStockList.length}店舗)
          </div>
        ` + inStockList.map(s => {
          const info = decodeStatus(effectiveStatus[s.id]);
          const packs = (info.packs && info.packs.length > 0) ? info.packs.join(', ') : 'ポケモンカード';
          const safeName = escapeHtml(s.name);
          const safePacks = escapeHtml(packs);
          const safeAddr = escapeHtml(s.address || '');
          const time = info.timeAgo ? escapeHtml(info.timeAgo) : '新着';
          return `
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px; margin-bottom:10px; cursor:pointer; transition:transform 0.1s;"
                 onclick="closeBulletinModal(); focusStoreFromList('${s.id}');">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <b style="font-size:0.85rem; color:#1e293b;">${safeName}</b>
                <span class="badge-in" style="flex-shrink:0;">🟢 在庫あり</span>
              </div>
              <div style="font-size:0.75rem; color:#475569; margin-top:4px;">📦 ${safePacks}</div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:0.7rem; color:#94a3b8;">
                <span>📍 ${safeAddr}</span>
                <span style="color:#4f46e5; font-weight:700;">🕒 ${time} (地図で見る →)</span>
              </div>
            </div>
          `;
        }).join('');
      }
      document.getElementById('bulletin-modal').classList.add('open');
    }
    window.openBulletinModal = openBulletinModal;

    function closeBulletinModal() {
      document.getElementById('bulletin-modal').classList.remove('open');
    }
    window.closeBulletinModal = closeBulletinModal;

    // 14. SETTINGS MODAL (⚙️ 設定 & カスタマイズ)
    function openSettingsModal() {
      // 1. Sync filter radio
      const radios = document.getElementsByName('set-filter-radio');
      if (radios) {
        radios.forEach(r => {
          r.checked = (r.value === activeFilter || (r.value === 'none' && activeFilter === 'all'));
        });
      }

      // 2. Sync time select
      const timeSelect = document.getElementById('settings-time-select');
      if (timeSelect) {
        timeSelect.value = String(activeTime);
      }

      // 3. Sync region radios
      const regionRadios = document.getElementsByName('set-region-radio');
      if (regionRadios) {
        regionRadios.forEach(r => {
          r.checked = (r.value === currentRegion);
        });
      }

      // 4. Sync Telegram UI badge
      updateTelegramUIBadge();

      // 5. Sync Sound checkbox
      const soundCheck = document.getElementById('set-sound-check');
      if (soundCheck) {
        soundCheck.checked = configData.soundEnabled !== false;
      }

      // 6. Sync location name
      const prefLabelEl = document.getElementById('header-loc-name');
      const setPrefEl = document.getElementById('settings-current-pref');
      if (prefLabelEl && setPrefEl) {
        setPrefEl.innerText = prefLabelEl.innerText;
      }

      document.getElementById('settings-modal').classList.add('open');
    }
    window.openSettingsModal = openSettingsModal;

    function closeSettingsModal() {
      document.getElementById('settings-modal').classList.remove('open');
    }
    window.closeSettingsModal = closeSettingsModal;

    // TELEGRAM NOTIFICATION & CONFIGURATION MODAL HANDLERS
    function updateTelegramUIBadge() {
      const isTg = !!configData.telegramEnabled;
      const tgTag = document.getElementById('list-tg-status-tag');
      if (tgTag) {
        tgTag.innerText = isTg ? '✈️ Telegram: BẬT' : '✈️ Telegram: TẮT';
        tgTag.style.background = isTg ? '#dcfce7' : '#fee2e2';
        tgTag.style.color = isTg ? '#15803d' : '#b91c1c';
      }
      const tgPill = document.getElementById('set-tg-status-pill');
      if (tgPill) {
        tgPill.innerText = isTg ? '✈️ Đang bật' : '✈️ Đang tắt';
        tgPill.style.background = isTg ? '#dcfce7' : '#fee2e2';
        tgPill.style.color = isTg ? '#15803d' : '#b91c1c';
      }
      const tgEnabledCheck = document.getElementById('tg-cfg-enabled');
      if (tgEnabledCheck) {
        tgEnabledCheck.checked = isTg;
      }
    }
    window.updateTelegramUIBadge = updateTelegramUIBadge;

    function openTelegramModal() {
      const tokenEl = document.getElementById('tg-cfg-token');
      const chatIdEl = document.getElementById('tg-cfg-chatid');
      const enabledEl = document.getElementById('tg-cfg-enabled');
      const statusEl = document.getElementById('tg-cfg-status');
      const chainEl = document.getElementById('tg-cfg-chain');
      const timeEl = document.getElementById('tg-cfg-time');
      const regionEl = document.getElementById('tg-cfg-region');
      const resEl = document.getElementById('modal-test-tg-result');

      if (tokenEl) tokenEl.value = configData.telegramBotToken || '';
      if (chatIdEl) chatIdEl.value = configData.telegramChatId || '';
      if (enabledEl) enabledEl.checked = !!configData.telegramEnabled;
      if (statusEl) statusEl.value = configData.telegramStatus || 'in';
      if (chainEl) chainEl.value = configData.telegramChain || 'all';
      if (timeEl) timeEl.value = String(configData.telegramTime || '24');
      if (regionEl) regionEl.value = configData.telegramRegion || 'osaka';
      if (resEl) resEl.style.display = 'none';

      const saveResEl = document.getElementById('modal-save-tg-result');
      if (saveResEl) saveResEl.style.display = 'none';
      const saveBtn = document.getElementById('btn-save-tg');
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<span>💾 Lưu cấu hình Telegram</span>';
        saveBtn.style.background = '#0284c7';
        saveBtn.style.borderColor = '#0284c7';
      }

      document.getElementById('telegram-modal').classList.add('open');
    }
    window.openTelegramModal = openTelegramModal;

    function closeTelegramModal() {
      const modal = document.getElementById('telegram-modal');
      if (modal) modal.classList.remove('open');
    }
    window.closeTelegramModal = closeTelegramModal;

    function onTelegramToggleChanged(enabled) {
      configData.telegramEnabled = enabled;
      updateTelegramUIBadge();
      updateSettings('telegramEnabled', enabled);
    }
    window.onTelegramToggleChanged = onTelegramToggleChanged;

    async function testTelegramInModal() {
      const btn = document.getElementById('btn-modal-test-tg');
      const resEl = document.getElementById('modal-test-tg-result');
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();

      if (!btn || !resEl) return;

      if (!token || !chatId) {
        resEl.style.display = 'block';
        resEl.style.background = '#fef3c7';
        resEl.style.color = '#92400e';
        resEl.innerHTML = '⚠️ Vui lòng nhập cả <b>Telegram Bot Token</b> và <b>Telegram Chat ID</b> trước khi gửi thử.';
        return;
      }

      btn.disabled = true;
      btn.innerHTML = '<span>⏳ Đang gửi tin nhắn thử nghiệm...</span>';
      resEl.style.display = 'block';
      resEl.style.background = '#f1f5f9';
      resEl.style.color = '#475569';
      resEl.innerText = 'Đang kết nối tới Telegram API...';

      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            notifications: {
              telegramBotToken: token,
              telegramChatId: chatId
            }
          })
        });
        configData.telegramBotToken = token;
        configData.telegramChatId = chatId;

        const res = await fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            is_test: true,
            store: {
              id: 'test_store_webhook',
              name: 'Pokémon Center Osaka DX (Tin nhắn thử nghiệm)',
              chain: 'specialty',
              chain_label: 'Pokémon Center',
              address: 'Osaka, Chuo Ward, Shinsaibashisuji 1-7-1',
              lat: 34.6732,
              lng: 135.5008,
              pref: 'osaka'
            },
            info: {
              status_code: 'i',
              code: 'i',
              onsite: true,
              reported_at: 'Vừa xong',
              timeAgo: 'Vừa cập nhật',
              packs: ['Terastal Festival ex (High Class Pack)', 'Battle Partners']
            }
          })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          resEl.style.background = '#dcfce7';
          resEl.style.color = '#15803d';
          resEl.innerHTML = '✅ <b>Thành công!</b> Đã gửi tin nhắn test tới Telegram. Vui lòng kiểm tra app Telegram của bạn.';
        } else {
          resEl.style.background = '#fee2e2';
          resEl.style.color = '#b91c1c';
          resEl.innerHTML = `❌ <b>Lỗi gửi tin:</b> ${data.error || data.reason || JSON.stringify(data)}`;
        }
      } catch (err) {
        resEl.style.background = '#fee2e2';
        resEl.style.color = '#b91c1c';
        resEl.innerHTML = `❌ <b>Không thể kết nối máy chủ:</b> ${err.message}`;
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🧪 Gửi tin nhắn thử nghiệm (Test Bot)</span>';
      }
    }
    window.testTelegramInModal = testTelegramInModal;

    async function saveTelegramSettings() {
      const btn = document.getElementById('btn-save-tg');
      const resEl = document.getElementById('modal-save-tg-result');
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();
      const enabled = document.getElementById('tg-cfg-enabled') ? document.getElementById('tg-cfg-enabled').checked : false;
      const status = document.getElementById('tg-cfg-status') ? document.getElementById('tg-cfg-status').value : 'in';
      const chain = document.getElementById('tg-cfg-chain') ? document.getElementById('tg-cfg-chain').value : 'all';
      const time = document.getElementById('tg-cfg-time') ? document.getElementById('tg-cfg-time').value : '24';
      const region = document.getElementById('tg-cfg-region') ? document.getElementById('tg-cfg-region').value : 'osaka';

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳ Đang lưu...</span>';
      }
      if (resEl) {
        resEl.style.display = 'block';
        resEl.style.background = '#f0f9ff';
        resEl.style.color = '#0369a1';
        resEl.style.border = '1px solid #bae6fd';
        resEl.innerHTML = '⏳ Đang lưu cài đặt Telegram...';
      }

      configData.telegramBotToken = token;
      configData.telegramChatId = chatId;
      configData.telegramEnabled = enabled;
      configData.telegramStatus = status;
      configData.telegramChain = chain;
      configData.telegramTime = time;
      configData.telegramRegion = region;

      try {
        const response = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            notifications: {
              telegramBotToken: token,
              telegramChatId: chatId,
              telegramEnabled: enabled,
              telegramStatus: status,
              telegramChain: chain,
              telegramTime: time,
              telegramRegion: region
            }
          })
        });

        const data = await response.json();
        if (data.status === 'ok') {
          updateTelegramUIBadge();
          if (btn) {
            btn.innerHTML = '<span>✅ Đã lưu thành công!</span>';
            btn.style.background = '#16a34a';
            btn.style.borderColor = '#16a34a';
          }
          if (resEl) {
            resEl.style.display = 'block';
            resEl.style.background = '#dcfce7';
            resEl.style.color = '#15803d';
            resEl.style.border = '1px solid #86efac';
            resEl.innerHTML = '✅ <b>Đã lưu cấu hình thành công!</b> Cài đặt Telegram & bộ lọc cảnh báo đã có hiệu lực.';
          }
          if (typeof showRegionToast === 'function') {
            showRegionToast('Đã lưu cấu hình Telegram thành công! ✅', '✈️');
            if (typeof hideRegionToast === 'function') hideRegionToast(2500);
          }
          setTimeout(() => {
            closeTelegramModal();
            if (btn) {
              btn.disabled = false;
              btn.innerHTML = '<span>💾 Lưu cấu hình Telegram</span>';
              btn.style.background = '#0284c7';
              btn.style.borderColor = '#0284c7';
            }
            if (resEl) resEl.style.display = 'none';
          }, 1200);
        } else {
          throw new Error(data.error || 'Máy chủ phản hồi không thành công');
        }
      } catch (err) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>💾 Thử lưu lại</span>';
        }
        if (resEl) {
          resEl.style.display = 'block';
          resEl.style.background = '#fee2e2';
          resEl.style.color = '#b91c1c';
          resEl.style.border = '1px solid #fca5a5';
          resEl.innerHTML = `❌ <b>Lỗi lưu cấu hình:</b> ${err.message}`;
        }
      }
    }
    window.saveTelegramSettings = saveTelegramSettings;

    // Backward-compatible individual handlers
    function toggleTelegramNotification(enabled) {
      onTelegramToggleChanged(enabled);
    }
    window.toggleTelegramNotification = toggleTelegramNotification;

    function sendTestTelegramNotification() {
      testTelegramInModal();
    }
    window.sendTestTelegramNotification = sendTestTelegramNotification;

    function setSettingsFilter(filterName) {
      const actual = (filterName === 'none') ? 'all' : filterName;
      mapStatusFilter = actual;
      updateMapFilterUI();
      renderMapMarkers();
      updateSettings('activeFilter', actual);
    }
    window.setSettingsFilter = setSettingsFilter;

    function openSearchModal() {
      openPrefModal();
    }
    window.openSearchModal = openSearchModal;

    function updateSettings(key, val) {
      const payload = {};
      const tgKeys = ['telegramEnabled', 'soundEnabled', 'telegramBotToken', 'telegramChatId', 'telegramStatus', 'telegramChain', 'telegramTime', 'telegramRegion'];
      if (tgKeys.includes(key)) {
        payload.notifications = { [key]: val };
      } else {
        payload[key] = val;
      }
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).catch(e => console.warn(e));
    }
    window.updateSettings = updateSettings;

    // 13c. STORE HISTORY & POPUP ACCORDION (📜 入荷履歴 / Lịch sử báo cáo)
    function renderPopupHistoryItemsHtml(storeId, history) {
      const effectiveStatus = Object.assign({}, coldStatus, hotStatus);
      const currentRaw = effectiveStatus[storeId] || effectiveStatus[storeId + '_c'];
      const info = decodeStatus(currentRaw);

      if (!history || history.length === 0) {
        let statusBadge = '⚪ Không rõ';
        let itemBg = '#f8fafc';
        let itemBorder = '#e2e8f0';
        let itemColor = '#475569';

        if (info.code === 'i') {
          statusBadge = '🟢 Có hàng (在庫あり)';
          itemBg = '#f0fdf4';
          itemBorder = '#bbf7d0';
          itemColor = '#15803d';
        } else if (info.code === 'o') {
          statusBadge = '🔴 Hết hàng (売り切れ)';
          itemBg = '#fef2f2';
          itemBorder = '#fecaca';
          itemColor = '#b91c1c';
        } else if (info.code === 'n') {
          statusBadge = '⚪ Không bán thẻ (扱無)';
          itemBg = '#f8fafc';
          itemBorder = '#e2e8f0';
          itemColor = '#64748b';
        }

        const packName = (info.packs && info.packs.length > 0) ? info.packs.join(', ') : '';

        return `
          <div style="background:${itemBg}; border:1px solid ${itemBorder}; border-radius:8px; padding:7px 10px; font-size:0.73rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <b style="color:${itemColor};">${statusBadge}</b>
              <span style="color:#64748b; font-size:0.68rem; font-weight:600;">🕒 ${escapeHtml(info.timeAgo || info.reported_at || 'Mới nhất')}</span>
            </div>
            ${packName ? `<div style="color:#0f172a; font-weight:700; font-size:0.72rem; margin-top:3px;">📦 Sản phẩm: <span style="color:#2563eb;">${escapeHtml(packName)}</span></div>` : ''}
            <div style="color:#64748b; font-size:0.67rem; margin-top:3px;">👤 Người báo: <b>Ẩn danh (Hệ thống)</b></div>
          </div>
          <div style="font-size:0.68rem; color:#94a3b8; text-align:center; padding:3px;">(Chưa có lịch sử các lần báo trước)</div>
        `;
      }

      return history.map(item => {
        let statusBadge = '⚪ Không rõ';
        let itemBg = '#f8fafc';
        let itemBorder = '#e2e8f0';
        let itemColor = '#475569';

        if (item.status_code === 'i') {
          statusBadge = '🟢 Có hàng (在庫あり)';
          itemBg = '#f0fdf4';
          itemBorder = '#bbf7d0';
          itemColor = '#15803d';
        } else if (item.status_code === 'o') {
          statusBadge = '🔴 Hết hàng (売り切れ)';
          itemBg = '#fef2f2';
          itemBorder = '#fecaca';
          itemColor = '#b91c1c';
        } else if (item.status_code === 'n') {
          statusBadge = '⚪ Không bán thẻ (扱無)';
          itemBg = '#f8fafc';
          itemBorder = '#e2e8f0';
          itemColor = '#64748b';
        }

        const noteHtml = item.note ? `<div style="color:#0f172a; font-weight:700; font-size:0.72rem; margin-top:3px;">📦 Sản phẩm: <span style="color:#2563eb;">${escapeHtml(item.note)}</span></div>` : '';
        const reporterName = item.user || 'Ẩn danh';
        const userHtml = `👤 Người báo: <b>${escapeHtml(reporterName)}</b>${item.onsite ? ' • <span style="color:#16a34a; font-weight:700;">📸 Tại chỗ</span>' : ''}`;

        return `
          <div style="background:${itemBg}; border:1px solid ${itemBorder}; border-radius:8px; padding:7px 10px; font-size:0.73rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <b style="color:${itemColor};">${statusBadge}</b>
              <span style="color:#64748b; font-size:0.68rem; font-weight:600;">🕒 ${escapeHtml(item.formatted_time || '')}</span>
            </div>
            ${noteHtml}
            <div style="color:#64748b; font-size:0.67rem; margin-top:3px;">${userHtml}</div>
          </div>
        `;
      }).join('');
    }

    function renderPopupHistoryContent(storeId, containerEl, history) {
      if (containerEl) {
        containerEl.innerHTML = renderPopupHistoryItemsHtml(storeId, history);
      }
    }

    async function togglePopupHistory(storeId, btn) {
      const popupEl = (btn && btn.closest('.leaflet-popup-content')) || document;
      const containerEl = popupEl.querySelector(`#popup-hist-container-${storeId}`) || document.getElementById(`popup-hist-container-${storeId}`);
      const arrowEl = popupEl.querySelector(`#arrow-hist-${storeId}`) || document.getElementById(`arrow-hist-${storeId}`);
      if (!containerEl) return;

      const isCurrentlyOpen = openPopupHistStoreIds.has(storeId) || containerEl.style.display !== 'none';
      if (isCurrentlyOpen) {
        openPopupHistStoreIds.delete(storeId);
        containerEl.style.display = 'none';
        if (arrowEl) arrowEl.innerText = '▼';
        return;
      }

      openPopupHistStoreIds.add(storeId);
      containerEl.style.display = 'flex';
      if (arrowEl) arrowEl.innerText = '▲';

      let history = storeHistoryCache[storeId];
      if (!history) {
        containerEl.innerHTML = `
          <div style="text-align:center; padding:10px 4px; color:#64748b; font-size:0.73rem;">
            <span style="display:inline-block; animation:pulse 1s infinite;">⏳</span>
            <div style="margin-top:2px; font-weight:600;">Đang tải lịch sử báo cáo...</div>
          </div>
        `;

        try {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
          if (Array.isArray(history)) {
            const inC = history.filter(x => x.status_code === 'i' || x.status === 'in-stock').length;
            const outC = history.filter(x => x.status_code === 'o' || x.status === 'out-of-stock').length;
            storeCountsCache[storeId] = { in: inC, out: outC, loaded: true };
            const pIn = document.getElementById(`count-in-${storeId}`);
            const pOut = document.getElementById(`count-out-${storeId}`);
            if (pIn) pIn.innerText = inC;
            if (pOut) pOut.innerText = outC;
            const lIn = document.getElementById(`list-count-in-${storeId}`);
            const lOut = document.getElementById(`list-count-out-${storeId}`);
            if (lIn) lIn.innerText = inC;
            if (lOut) lOut.innerText = outC;
          }
        } catch (err) {
          containerEl.innerHTML = `
            <div style="color:#ef4444; font-size:0.72rem; padding:6px; text-align:center;">
              ⚠️ Lỗi tải lịch sử: ${escapeHtml(err.message)}
            </div>
          `;
          return;
        }
      }

      if (openPopupHistStoreIds.has(storeId)) {
        containerEl.innerHTML = renderPopupHistoryItemsHtml(storeId, history);
      }
    }
    window.togglePopupHistory = togglePopupHistory;

    async function openStoreHistoryModal(storeId) {
      const modal = document.getElementById('store-history-modal');
      const titleEl = document.getElementById('hist-modal-title');
      const subEl = document.getElementById('hist-modal-subtitle');
      const currEl = document.getElementById('hist-modal-current');
      const countEl = document.getElementById('hist-modal-count');
      const timelineEl = document.getElementById('hist-modal-timeline');
      const mapsLinkEl = document.getElementById('hist-modal-maps-link');

      if (!modal) return;

      const store = storesDict[storeId] || { name: '店舗情報', address: '' };
      const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'コンビニ・カード店';

      if (titleEl) titleEl.innerText = store.name;
      
      let subText = `${chain} • 📍 ${store.address || 'エリア'}`;
      if (userLat !== null && userLng !== null && store.lat && store.lng) {
        const d = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        subText += ` • 現在地から ${formatDist(d)}`;
      }
      if (subEl) subEl.innerText = subText;

      const mapsQuery = encodeURIComponent((store.name || '') + ' ' + (store.address || ''));
      if (mapsLinkEl) {
        mapsLinkEl.href = `https://www.google.com/maps/dir/?api=1&destination=${mapsQuery}`;
      }

      // Current status summary banner
      const effectiveStatus = Object.assign({}, coldStatus, hotStatus);
      const currentRaw = effectiveStatus[storeId] || effectiveStatus[storeId + '_c'];
      const info = decodeStatus(currentRaw);

      let currentStatusBadge = '⚪ 不明 / 扱無';
      let currentBg = '#f1f5f9';
      let currentColor = '#475569';
      if (info.code === 'i') {
        currentStatusBadge = '🟢 在庫あり (In Stock)';
        currentBg = '#dcfce7';
        currentColor = '#15803d';
      } else if (info.code === 'o') {
        currentStatusBadge = '🔴 在庫なし (Out of Stock)';
        currentBg = '#fee2e2';
        currentColor = '#b91c1c';
      } else if (info.code === 'n') {
        currentStatusBadge = '⚪ 扱ってない (Not handled)';
        currentBg = '#f1f5f9';
        currentColor = '#64748b';
      }

      const packInfo = info.packs.length ? `<div style="margin-top:4px; font-weight:700; color:#1e293b; font-size:0.75rem;">📦 パック: ${escapeHtml(info.packs.join(', '))}</div>` : '';
      const timeInfo = info.timeAgo ? `<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">🕒 直近報告: ${escapeHtml(info.timeAgo)} (${escapeHtml(info.reported_at)})</div>` : '';

      const counts = getStoreCounts(storeId, info.code);

      if (currEl) {
        currEl.innerHTML = `
          <div style="background:${currentBg}; border:1px solid #cbd5e1; border-radius:8px; padding:10px 12px;">
            <div style="font-weight:800; font-size:0.86rem; color:${currentColor};">${currentStatusBadge}</div>
            <div class="popup-report-counts-bar" style="margin:6px 0 4px 0;">
              <span class="report-count-tag tag-green">
                <span class="count-badge-icon">🟢</span>
                <span>Có hàng: <b id="hist-modal-count-in">${counts.in}</b> lần</span>
              </span>
              <span class="report-count-tag tag-red">
                <span class="count-badge-icon">🔴</span>
                <span>Hết hàng: <b id="hist-modal-count-out">${counts.out}</b> lần</span>
              </span>
            </div>
            ${packInfo}
            ${timeInfo}
          </div>
        `;
      }

      // Show modal immediately
      modal.classList.add('open');

      if (!storeHistoryCache[storeId]) {
        if (timelineEl) {
          timelineEl.innerHTML = `
            <div style="text-align:center; padding:24px 8px; color:#64748b;">
              <div style="font-size:1.6rem; animation:pulse 1s infinite;">⏳</div>
              <div style="margin-top:6px; font-weight:600;">過去の入荷履歴を読込中...</div>
            </div>
          `;
        }
        if (countEl) countEl.innerText = '';
      }

      // Fetch history data from backend API
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }

        if (Array.isArray(history)) {
          const inC = history.filter(x => x.status_code === 'i' || x.status === 'in-stock').length;
          const outC = history.filter(x => x.status_code === 'o' || x.status === 'out-of-stock').length;
          storeCountsCache[storeId] = { in: inC, out: outC, loaded: true };
          const hmIn = document.getElementById('hist-modal-count-in');
          const hmOut = document.getElementById('hist-modal-count-out');
          if (hmIn) hmIn.innerText = inC;
          if (hmOut) hmOut.innerText = outC;
        }

        renderStoreTimeline(history, info);
      } catch (err) {
        if (timelineEl) {
          timelineEl.innerHTML = `
            <div style="color:#ef4444; font-size:0.75rem; padding:12px; text-align:center;">
              ⚠️ 履歴の取得に失敗しました: ${escapeHtml(err.message)}
            </div>
          `;
        }
      }
    }
    window.openStoreHistoryModal = openStoreHistoryModal;

    function renderStoreTimeline(historyList, currentInfo) {
      const countEl = document.getElementById('hist-modal-count');
      const timelineEl = document.getElementById('hist-modal-timeline');
      if (!timelineEl) return;

      if (!historyList || historyList.length === 0) {
        if (countEl) countEl.innerText = '0件';
        timelineEl.innerHTML = `
          <div style="text-align:center; padding:20px 8px; background:#f8fafc; border-radius:8px; border:1px dashed #cbd5e1; color:#64748b;">
            <div style="font-size:1.4rem; margin-bottom:4px;">📭</div>
            <div style="font-weight:700; color:#334155;">過去の報告ログはありません</div>
            <div style="font-size:0.72rem; margin-top:2px;">今後の新着入荷報告や目撃情報を受信するとここに記録されます。</div>
          </div>
        `;
        return;
      }

      if (countEl) countEl.innerText = `${historyList.length}件の記録`;

      timelineEl.innerHTML = historyList.map(item => {
        let badgeBg = '#f1f5f9';
        let badgeColor = '#475569';
        let badgeLabel = '⚪ 不明';
        let borderAccent = '#cbd5e1';

        if (item.status_code === 'i') {
          badgeBg = '#dcfce7'; badgeColor = '#15803d'; badgeLabel = '🟢 在庫あり'; borderAccent = '#22c55e';
        } else if (item.status_code === 'o') {
          badgeBg = '#fee2e2'; badgeColor = '#b91c1c'; badgeLabel = '🔴 売り切れ'; borderAccent = '#ef4444';
        } else if (item.status_code === 'n') {
          badgeBg = '#f1f5f9'; badgeColor = '#64748b'; badgeLabel = '⚪ 扱無'; borderAccent = '#94a3b8';
        }

        const noteHtml = item.note ? `<div style="font-size:0.75rem; color:#1e293b; margin-top:4px; font-weight:700;">📦 ${escapeHtml(item.note)}</div>` : '';
        const userHtml = item.user ? `<span style="color:#64748b;">👤 ${escapeHtml(item.user)}</span>` : '';
        const onsiteHtml = item.onsite ? `<span style="color:#16a34a; font-weight:700;"> • 📸 現地確認</span>` : '';

        return `
          <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid ${borderAccent}; border-radius:8px; padding:10px 12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
              <span style="font-size:0.76rem; font-weight:800; background:${badgeBg}; color:${badgeColor}; padding:3px 8px; border-radius:6px;">
                ${badgeLabel}
              </span>
              <span style="font-size:0.7rem; color:#64748b; font-weight:600;">
                🕒 ${escapeHtml(item.formatted_time || '')}
              </span>
            </div>
            ${noteHtml}
            <div style="font-size:0.7rem; margin-top:5px; color:#94a3b8; display:flex; justify-content:space-between; align-items:center;">
              <div>${userHtml}${onsiteHtml}</div>
              ${item.who ? `<span style="font-family:monospace; font-size:0.65rem; color:#94a3b8;">ID: ${escapeHtml(item.who)}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }

    function closeStoreHistoryModal() {
      const modal = document.getElementById('store-history-modal');
      if (modal) modal.classList.remove('open');
    }
    window.closeStoreHistoryModal = closeStoreHistoryModal;

    // 14. ROBUST GPS USER LOCATION (Smooth, non-jittering, one-time centering)
    function updateUserMarker(lat, lng, accuracy = 30) {
      const displayRadius = Math.min(Math.max(accuracy, 15), 150);
      if (!userMarker) {
        const icon = L.divIcon({
          className: 'user-location-marker',
          iconSize: [18, 18],
          iconAnchor: [9, 9]
        });
        userMarker = L.marker([lat, lng], { icon, zIndexOffset: 2000 }).addTo(map);
        userMarker.bindPopup('📍 <b>あなたの現在地</b><br><span style="font-size:0.75rem;color:#64748b;">(Vị trí hiện tại của bạn)</span>');
        userCircle = L.circle([lat, lng], {
          radius: displayRadius,
          color: '#4f46e5',
          fillColor: '#818cf8',
          fillOpacity: 0.15,
          weight: 1
        }).addTo(map);
      } else {
        userMarker.setLatLng([lat, lng]);
        if (userCircle) {
          userCircle.setLatLng([lat, lng]);
          userCircle.setRadius(displayRadius);
        }
      }
    }

    function onGpsSuccess(pos, userInitiated = false) {
      userLat = pos.coords.latitude;
      userLng = pos.coords.longitude;
      const accuracy = pos.coords.accuracy || 30;

      // Save to storage for instant recall on next launch
      try {
        localStorage.setItem('poketan_user_lat', String(userLat));
        localStorage.setItem('poketan_user_lng', String(userLng));
      } catch(e) {}

      updateUserMarker(userLat, userLng, accuracy);

      const btn = document.getElementById('gps-btn');
      if (btn) {
        btn.classList.remove('locating');
        btn.innerHTML = '📍';
      }

      const inJapan = isCoordInJapan(userLat, userLng);

      // Only fly/pan if user explicitly clicked GPS button, OR if this is the very first auto-fix in Japan
      if (userInitiated) {
        map.flyTo([userLat, userLng], 15, { duration: 0.8 });
      } else if (!hasCenteredOnUser && inJapan) {
        hasCenteredOnUser = true;
        const curCenter = map.getCenter();
        const d = calcDistanceKm(curCenter.lat, curCenter.lng, userLat, userLng);
        if (d > 0.1) {
          map.panTo([userLat, userLng], { animate: true, duration: 0.6 });
        }
      }

      // If store list is open, re-sort and update distances quietly (no marker re-cluster)
      const listContainer = document.getElementById('view-list-container');
      if (listContainer && listContainer.classList.contains('open')) {
        renderStoreList();
      }
    }

    function locateUser(userInitiated = true) {
      const btn = document.getElementById('gps-btn');
      if (btn && userInitiated) {
        btn.classList.add('locating');
        btn.innerHTML = '⏳';
      }

      if (!navigator.geolocation) {
        if (btn) {
          btn.classList.remove('locating');
          btn.innerHTML = '📍';
        }
        if (userInitiated) alert('お使いのブラウザはGPS位置情報に対応していません。(Trình duyệt không hỗ trợ GPS)');
        return;
      }

      // Fast response: If user clicked and we already have coordinates, fly immediately!
      if (userInitiated && userLat !== null && userLng !== null) {
        updateUserMarker(userLat, userLng, 30);
        map.flyTo([userLat, userLng], 15, { duration: 0.8 });
        if (btn) {
          btn.classList.remove('locating');
          btn.innerHTML = '📍';
        }
      }

      // High accuracy GPS request
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          onGpsSuccess(pos, userInitiated);
        },
        (err1) => {
          console.warn('High-accuracy GPS notice:', err1.message);
          // Fallback to low accuracy (WiFi/Cellular/IP)
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              onGpsSuccess(pos, userInitiated);
            },
            (err2) => {
              console.warn('All GPS attempts failed:', err2.message);
              if (btn) {
                btn.classList.remove('locating');
                btn.innerHTML = '📍';
              }
              if (userInitiated && (userLat === null || userLng === null)) {
                alert("現在地を取得できませんでした。ブラウザの位置情報の権限（アクセス許可）を確認してください。 (Không thể lấy vị trí. Vui lòng cho phép quyền vị trí trong trình duyệt.)");
              }
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
          );
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 30000 }
      );
    }
    window.locateUser = locateUser;

    // Continuous background watchPosition: purely updates the blue marker dot as user moves, NEVER interrupts map view!
    function startContinuousGpsWatch() {
      if (!navigator.geolocation) return;
      navigator.geolocation.watchPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          updateUserMarker(userLat, userLng, pos.coords.accuracy || 30);
          const listContainer = document.getElementById('view-list-container');
          if (listContainer && listContainer.classList.contains('open')) {
            renderStoreList();
          }
        },
        (err) => console.warn('Continuous GPS watch notice:', err.message),
        { enableHighAccuracy: true, maximumAge: 15000 }
      );
    }

    // 15. DATA INITIALIZATION & REALTIME FIRESTORE LISTENER
    async function initData() {
      const safetyTimer = setTimeout(() => {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.remove();
      }, 2500);

      try {
        // Sync radio button in settings modal
        const activeRadio = document.querySelector(`input[name="set-region-radio"][value="${currentRegion}"]`);
        if (activeRadio) activeRadio.checked = true;

        if (REGIONS[currentRegion]) {
          const headerLoc = document.getElementById('header-loc-name');
          if (headerLoc) {
            headerLoc.innerText = (currentRegion === 'all') ? '全エリア' : `${REGIONS[currentRegion].defaultCity}周辺`;
          }
        }

        // Show cached marker on map if available
        if (userLat !== null && userLng !== null) {
          updateUserMarker(userLat, userLng);
        }

        // Silent GPS check on startup (userInitiated = false, zero jerky jumps)
        locateUser(false);
        startContinuousGpsWatch();

        // Step 1: Fetch config, stores, hot_status, and cold_status ALL IN PARALLEL for all Japan!
        const [cfgRes, storesRes, hotRes, coldRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data?region=all'),
          fetch('/api/hot_status?region=all').catch(() => null),
          fetch('/api/cold_status?region=all').catch(() => null)
        ]);

        configData = await cfgRes.json();
        storesDict = await storesRes.json();
        window.storesDict = storesDict;

        // Sync Telegram UI Badges
        updateTelegramUIBadge();

        if (hotRes && hotRes.ok) {
          try { hotStatus = await hotRes.json(); } catch(e) {}
        }
        if (coldRes && coldRes.ok) {
          try { coldStatus = await coldRes.json(); } catch(e) {}
        }

        // Render markers for map based purely on map filters
        renderMapMarkers();

        // Prefetch precomputed report counts for in-stock stores
        fetch('/api/report_counts?region=all').then(r => r.json()).then(data => {
          if (data && typeof data === 'object') {
            for (const [sid, c] of Object.entries(data)) {
              storeCountsCache[sid] = { in: c.in, out: c.out, loaded: true };
              const pIn = document.getElementById(`count-in-${sid}`);
              const pOut = document.getElementById(`count-out-${sid}`);
              if (pIn) pIn.innerText = c.in;
              if (pOut) pOut.innerText = c.out;

              const lIn = document.getElementById(`list-count-in-${sid}`);
              const lOut = document.getElementById(`list-count-out-${sid}`);
              if (lIn) lIn.innerText = c.in;
              if (lOut) lOut.innerText = c.out;
            }
          }
        }).catch(() => {});

        // Direct URL routing for /thongbao and /stores
        if (window.location.pathname === '/thongbao' || window.location.pathname === '/stores') {
          switchFooterTab('list');
        }

        // Dismiss loading screen right away
        clearTimeout(safetyTimer);
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
          overlay.style.opacity = '0';
          setTimeout(() => overlay.remove(), 150);
        }

        // Ensure Leaflet recalculates container size and loads all tiles
        map.invalidateSize();
        setTimeout(() => map.invalidateSize(), 150);
        setTimeout(() => map.invalidateSize(), 500);

        // Realtime Firestore sync for all prefectures
        setupRealtime();
      } catch (e) {
        console.error('Init error:', e);
        clearTimeout(safetyTimer);
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.remove();
      }
    }

    function refreshData() {
      Promise.all([
        fetch('/api/hot_status?region=all').then(r => r.json()).catch(() => ({})),
        fetch('/api/cold_status?region=all').then(r => r.json()).catch(() => ({}))
      ]).then(([hot, cold]) => {
        hotStatus = hot;
        coldStatus = cold;
        renderMapMarkers();
        const listContainer = document.getElementById('view-list-container');
        if (listContainer && listContainer.classList.contains('open')) {
          renderStoreList();
        }
      });
    }
    window.refreshData = refreshData;

    let renderDebounceTimer = null;
    function requestRenderMarkers() {
      if (renderDebounceTimer) cancelAnimationFrame(renderDebounceTimer);
      renderDebounceTimer = requestAnimationFrame(() => {
        renderMapMarkers();
      });
    }

    const notifiedRealtimeKeys = new Set();
    function processRealtimeTelegramAlerts(newData, pref) {
      if (!configData.telegramEnabled) return;
      if (!newData || typeof newData !== 'object') return;

      const tgRegion = configData.telegramRegion || 'osaka';
      let allowedPrefs = ['osaka'];
      if (tgRegion === 'tokyo') allowedPrefs = ['kanagawa', 'tokyo'];
      else if (tgRegion === 'nagoya') allowedPrefs = ['aichi', 'gifu', 'mie'];
      else if (tgRegion === 'all') allowedPrefs = ['osaka', 'kanagawa', 'aichi', 'gifu', 'mie'];
      else if (REGIONS[tgRegion] && REGIONS[tgRegion].prefs) allowedPrefs = REGIONS[tgRegion].prefs;

      if (tgRegion !== 'all' && (!pref || !allowedPrefs.includes(pref.toLowerCase()))) return;

      const tgStatus = configData.telegramStatus || 'in';
      const tgChain = configData.telegramChain || 'all';
      const tgTime = configData.telegramTime || '24';
      const nowSec = Math.floor(Date.now() / 1000);
      const maxAgeSec = (tgTime !== 'all') ? parseInt(tgTime, 10) * 3600 : 86400 * 30;

      for (const [sid, raw] of Object.entries(newData)) {
        const info = decodeStatus(raw);
        if (!info) continue;

        // Dedicated Telegram status filter
        if (tgStatus === 'in' && info.code !== 'i') continue;
        if (tgStatus === 'onsite' && (info.code !== 'i' || !info.onsite)) continue;
        if (tgStatus === 'recent' && (info.code !== 'i' && !(info.timestamp > 0 && (nowSec - info.timestamp <= 86400 * 7) && info.code !== 'n'))) continue;

        // Dedicated Telegram time window check
        if (info.timestamp && (nowSec - info.timestamp > maxAgeSec)) continue;

        const store = storesDict[sid] || { id: sid, name: sid, pref: pref };
        const storePref = (store.pref || pref || '').toLowerCase();
        if (tgRegion !== 'all' && !allowedPrefs.includes(storePref)) continue;

        // Dedicated Telegram chain filter check
        if (!matchesChainFilter(store.chain, tgChain)) continue;

        const notifKey = `${sid}_${info.timestamp || ''}`;
        if (notifiedRealtimeKeys.has(notifKey)) continue;
        notifiedRealtimeKeys.add(notifKey);

        fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            store: {
              id: store.id,
              name: store.name,
              chain: store.chain,
              address: store.address,
              lat: store.lat,
              lng: store.lng,
              pref: store.pref || pref
            },
            info: {
              status_code: info.code,
              code: info.code,
              onsite: !!info.onsite,
              reported_at: info.reported_at || 'Vừa xong',
              timeAgo: info.timeAgo || 'Vừa xong',
              timestamp: info.timestamp,
              packs: info.packs || []
            }
          })
        }).catch(err => console.warn('Telegram webhook push failed:', err));
      }
    }

    let realtimeDb = null;
    let realtimeUnsubscribes = [];

    function setupRealtime() {
      if (!window.FirebaseInit || !configData.apiKey) return;
      try {
        const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
        if (!realtimeDb) {
          const app = initializeApp({ apiKey: configData.apiKey, projectId: configData.projectId });
          realtimeDb = initializeFirestore(app, {});
        }

        // Unsubscribe old listeners
        realtimeUnsubscribes.forEach(unsub => {
          try { unsub(); } catch(e) {}
        });
        realtimeUnsubscribes = [];

        // Listen to all prefectures nationwide
        const targetPrefs = ['osaka', 'kanagawa', 'aichi', 'gifu', 'mie'];
        targetPrefs.forEach(p => {
          let isInitial = true;
          const unsub = onSnapshot(doc(realtimeDb, 'status', p), (snap) => {
            if (snap.exists()) {
              const data = snap.data();
              if (isInitial) {
                // Seed initial keys so past reports on page load are NOT alerted
                for (const [sid, raw] of Object.entries(data)) {
                  const info = decodeStatus(raw);
                  if (info && info.timestamp) {
                    notifiedRealtimeKeys.add(`${sid}_${info.timestamp}`);
                  }
                }
                isInitial = false;
              } else {
                processRealtimeTelegramAlerts(data, p);
              }
              Object.assign(hotStatus, data);
              requestRenderMarkers();
              const listContainer = document.getElementById('view-list-container');
              if (listContainer && listContainer.classList.contains('open')) {
                renderStoreList();
              }
            }
          });
          realtimeUnsubscribes.push(unsub);
        });
      } catch(e) {
        console.warn('Realtime sync setup error:', e);
      }
    }

    if (document.readyState === 'loading') {
      window.addEventListener('DOMContentLoaded', initData);
    } else {
      initData();
    }
    window.addEventListener('resize', () => map.invalidateSize());
  </script>
</body>
</html>"""


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
