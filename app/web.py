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
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
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
    get_report_counts as db_get_report_counts,
    register_on_report_added
)
import threading
from concurrent.futures import ThreadPoolExecutor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize local SQLite database and populate stores on startup
    init_db()
    seed_stores_if_empty()
    threading.Thread(target=backfill_all_poketan_statuses, daemon=True).start()
    start_background_watcher()
    yield

app = FastAPI(title="BAWUI POKE APP - Real-Time Stock & Lottery Tracker", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
    "showExpired": False,
    "currentRegion": "all",
    "stockPinEffectHours": "24"
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
        import time
        data = await request.json()
        current = load_user_settings()
        
        # Check if telegramEnabled is transitioning to True
        old_notif = current.get("notifications", {})
        new_notif = data.get("notifications", {})
        was_tg_enabled = bool(old_notif.get("telegramEnabled", False))
        is_tg_enabled = new_notif.get("telegramEnabled") if isinstance(new_notif, dict) else None
        if is_tg_enabled is True and not was_tg_enabled:
            # User just turned Telegram ON! Record exact activation timestamp
            if not isinstance(data.get("notifications"), dict):
                data["notifications"] = {}
            data["notifications"]["telegramEnabledAt"] = int(time.time())
            print(f"  [Settings] Telegram bật lúc {data['notifications']['telegramEnabledAt']} - chỉ gửi báo cáo phát sinh sau thời điểm này!")
        elif is_tg_enabled is False:
            if not isinstance(data.get("notifications"), dict):
                data["notifications"] = {}
            data["notifications"]["telegramEnabledAt"] = 0

        deep_update_dict(current, data)
        save_user_settings(current)
        return JSONResponse(content={"status": "ok", "settings": current})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# All available prefectures on PokéTan
ALL_PREFS = ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"]

# Defined core regions + all (matching user specification)
REGION_PREFS = {
    "osaka": ["osaka"],
    "tokyo": ["tokyo", "kanagawa", "chiba"],
    "kanagawa": ["kanagawa"],
    "chiba": ["chiba"],
    "nagoya": ["aichi", "gifu", "mie"],
    "aichi": ["aichi", "gifu", "mie"],
    "all": ["osaka", "tokyo", "kanagawa", "chiba", "aichi", "gifu", "mie"],
}

_recent_notified_keys = {}

def send_telegram_alert(store: dict, info: dict, notif_cfg: dict, is_test: bool = False) -> dict:
    """
    Send formatted alert to Telegram bot matching configured channel.
    Concise 5-field format requested by user:
    1. Tên cửa hàng (Chuỗi)
    2. Thời gian có báo cáo (JST)
    3. Trạng thái (Có hàng / Hết hàng...)
    4. Khoảng cách (từ ga JR Imamiya hoặc định vị)
    5. Địa chỉ kèm link mở vị trí trên PokéMap
    """
    import urllib.request
    import urllib.parse
    import json
    import math

    tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
    tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()
    tg_enabled = notif_cfg.get("telegramEnabled", False) or is_test

    if not (tg_token and tg_chat_id):
        return {"status": "no_credentials"}
    if not tg_enabled:
        return {"status": "disabled"}

    # Calculate distance to JR Imamiya Station (lat=34.6540, lng=135.4925)
    imamiya_dist_str = "Chưa rõ vị trí"
    st_lat = store.get("lat")
    st_lng = store.get("lng")
    if st_lat is not None and st_lng is not None:
        try:
            lat1, lon1 = float(st_lat), float(st_lng)
            lat2, lon2 = 34.6540, 135.4925
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            dist_km = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist_km < 1.0:
                imamiya_dist_str = f"~{int(round(dist_km * 1000))} m (từ ga JR Imamiya)"
            else:
                imamiya_dist_str = f"~{dist_km:.1f} km (từ ga JR Imamiya)"
        except Exception:
            pass

    store_name = store.get('name', 'Cửa hàng')
    store_chain = store.get('chain_label') or store.get('chain') or 'Tiện lợi'
    store_addr = store.get('address') or 'Khu vực đang chọn'
    store_id = store.get("id") or info.get("store_id") or ""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id

    # Format time (JST)
    ts = info.get("timestamp") or 0
    time_display = info.get("reported_at") or info.get("formatted_time") or ""
    if ts and ts > 0:
        try:
            from datetime import datetime, timezone, timedelta
            JST = timezone(timedelta(hours=9))
            dt = datetime.fromtimestamp(ts, tz=JST)
            time_display = dt.strftime("%H:%M:%S %d/%m/%Y")
        except Exception:
            pass
    if not time_display:
        time_display = "Vừa xong"

    # Status label
    code = info.get("status_code") or info.get("status") or "i"
    if code == "i":
        status_label = "🟢📸 Có hàng (Xác nhận tại chỗ)" if info.get("onsite") else "🟢 Có hàng (In stock)"
    elif code == "o":
        status_label = "🔴 Hết hàng (Sold out)"
    elif code == "n":
        status_label = "🟡 Không bán thẻ (No stock)"
    else:
        status_label = "⚪ Chưa có tin"

    # Link to PokéMap location
    pokemap_url = f"https://pokemap.bawui.com/?focus={clean_id}"
    if st_lat is not None and st_lng is not None:
        pokemap_url += f"&lat={st_lat}&lng={st_lng}&zoom=17"

    header = "🧪 <b>[THÔNG BÁO THỬ NGHIỆM]</b>\n" if is_test else ""
    msg_lines = [
        f"{header}🏪 <b>Tên cửa hàng:</b> {store_name} ({store_chain})",
        f"⏱ <b>Thời gian có báo cáo:</b> {time_display}",
        f"⚡ <b>Trạng thái:</b> {status_label}",
        f"📍 <b>Khoảng cách:</b> {imamiya_dist_str}",
        f"🗺️ <b>Địa chỉ:</b> <a href=\"{pokemap_url}\">{store_addr} (Mở PokéMap ↗)</a>"
    ]

    tg_payload = {
        "chat_id": tg_chat_id,
        "text": "\n".join(msg_lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
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


def on_csdl_report_added(store: dict, entry: dict):
    """
    CSDL Event Hook:
    Triggered ONLY when a brand-new report is officially committed into SQLite database.
    Decoupled 100% from external data fetching.
    """
    try:
        settings = load_user_settings()
        notif_cfg = settings.get("notifications", {})
        if not notif_cfg.get("telegramEnabled", False):
            return

        now_ts = int(time.time())
        rep_ts = int(entry.get("timestamp") or 0)
        # 1. Freshness guard: Chỉ gửi báo cáo mới tức thì (vừa báo trong vòng 5 phút)
        # Bất kỳ ai vừa báo có hàng là bắn tin về Telegram ngay lập tức
        if rep_ts <= 0 or (now_ts - rep_ts > 300):
            print(f"  [CSDL -> Telegram] Bỏ qua báo cáo cũ (không mới tức thì): ts={rep_ts}, tuổi={(now_ts - rep_ts)/60:.1f} phút (> 5 phút)")
            return

        # 2. Telegram enabled time guard:
        # Only notify reports submitted AFTER the user turned on Telegram notifications
        tg_enabled_at = notif_cfg.get("telegramEnabledAt") or 0
        if tg_enabled_at > 0 and rep_ts < (tg_enabled_at - 120):
            print(f"  [CSDL -> Telegram] Bỏ qua báo cáo phát sinh trước khi bật Telegram: ts={rep_ts} < enabled_at={tg_enabled_at}")
            return

        # 3. Check region filter (supporting multi-prefecture regions)
        tg_reg = (notif_cfg.get("telegramRegion") or "osaka").lower()
        store_pref = (store.get("pref") or "osaka").lower()
        allowed_prefs = REGION_PREFS.get(tg_reg, [tg_reg])
        if tg_reg != "all" and store_pref not in allowed_prefs:
            return

        # 4. Check status filter
        code = entry.get("status_code", "i")
        tg_status = (notif_cfg.get("telegramStatus") or "in").lower()
        if tg_status == "in" and code != "i":
            return
        if tg_status == "onsite" and (code != "i" or not entry.get("onsite")):
            return
        if tg_status == "recent" and code not in ["i", "w", "c"]:
            return

        # 5. Check chain filter
        tg_chain = (notif_cfg.get("telegramChain") or "all").lower()
        st_chain = (store.get("chain") or "").lower()
        if tg_chain != "all":
            if tg_chain == "conbini" and st_chain not in ["seven", "lawson", "familymart", "ministop"]:
                return
            elif tg_chain == "specialty" and st_chain != "specialty":
                return
            elif tg_chain == "electronics" and st_chain not in ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi']:
                return
            elif tg_chain not in ["conbini", "specialty", "electronics"] and st_chain != tg_chain:
                return

        print(f"  [CSDL -> Telegram] ⚡ BẢN GHI MỚI VỪA ADD VÀO CSDL: {store.get('name')} (pref={store_pref}, ts={entry.get('timestamp')}, code={code})")
        res = send_telegram_alert(store, entry, notif_cfg, is_test=False)
        print(f"  [CSDL -> Telegram] Kết quả gửi: {res}")
    except Exception as e:
        print(f"  [CSDL -> Telegram] Lỗi dispatch alert: {e}")

# Register event hook
register_on_report_added(on_csdl_report_added)


@app.post("/api/notify/webhook")
async def send_webhook_notification(request: Request):
    """
    Test or manual notification endpoint.
    If is_test: tests Telegram connection directly without polluting SQLite CSDL.
    If not is_test: ingests into SQLite, which dispatches CSDL event if new.
    """
    try:
        body = await request.json()
        store = body.get("store") or {}
        info = body.get("info") or {}
        is_test = bool(body.get("is_test", False))
        
        user_settings = load_user_settings()
        notif_cfg = {**user_settings.get("notifications", {}), **(body.get("notifications") or {})}

        if is_test:
            test_store = store or {
                "id": "test_store",
                "name": "Pokémon Center Osaka",
                "chain": "specialty",
                "chain_label": "Pokémon Center",
                "address": "Osaka, Kita Ward, Umeda 3-1-1",
                "lat": 34.7025,
                "lng": 135.4959,
                "pref": "osaka"
            }
            test_info = info or {
                "status_code": "i",
                "timestamp": int(time.time()),
                "onsite": True,
                "note": "Kiểm tra kết nối Telegram Bot thành công"
            }
            res = send_telegram_alert(test_store, test_info, notif_cfg, is_test=True)
            st = res.get("status", "ok")
            if st == "ok":
                return JSONResponse(content={"status": "ok", "results": {"telegram": "ok"}})
            else:
                return JSONResponse(content={"status": "error", "error": f"Telegram API: {st}", "results": {"telegram": st}})

        # Ingest into SQLite database
        sid = store.get("id") or info.get("store_id")
        if sid:
            status_code_raw = info.get("status_code") or info.get("code") or "i"
            timestamp_raw = info.get("timestamp") or int(time.time())
            is_new, rep = record_new_report(
                store_id=sid,
                status_code=status_code_raw,
                timestamp=timestamp_raw,
                onsite=bool(info.get("onsite", False)),
                packs=info.get("packs") or [],
                note=info.get("note") or "",
                user=info.get("user") or "匿名トレーナー",
                formatted_time=info.get("reported_at") or "",
                source="webhook",
                pref=store.get("pref") or "osaka"
            )
            return JSONResponse(content={"status": "ok", "is_new": is_new, "report": rep})

        return JSONResponse(content={"status": "no_store_id"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


def _backfill_store_history_safe(store_id: str, pref: str = "osaka"):
    """Safely fetch full history from PokéTan and save to SQLite in background."""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    try:
        remote_hist = fetch_store_history(clean_id)
        if remote_hist:
            save_bulk_history(clean_id, remote_hist, source="poketan", pref=pref)
    except Exception as e:
        print(f"  [DB] Background history backfill error for {clean_id}: {e}")


def telegram_background_watcher():
    """
    Background worker thread to continuously ingest hot reports from PokéTan into SQLite CSDL.
    Purely ingests data into SQLite via record_new_report().
    Telegram notifications are handled strictly by CSDL database events (when is_new == True).
    """
    import time
    import threading
    time.sleep(5)
    print("  [DataSyncDaemon] Background daemon started (syncing reports into SQLite CSDL)")
    while True:
        try:
            # Poll all active prefectures concurrently for ultra-fast background sync (~0.4s)
            pref_data_map = {}
            try:
                with ThreadPoolExecutor(max_workers=min(6, len(ALL_PREFS))) as executor:
                    futs = {executor.submit(fetch_realtime_status, p, False): p for p in ALL_PREFS}
                    pref_data_map = {p: f.result() for f, p in futs.items()}
            except Exception:
                pass

            for pref, hot_data in pref_data_map.items():
                if not hot_data:
                    continue
                for k, raw in hot_data.items():
                    try:
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
                        confirms = parsed.get("confirms") or 1
                        packs = parsed.get("packs") or []
                        rep_time = parsed.get("reported_at") or ""

                        # Ingest report into SQLite database (fires on_csdl_report_added if is_new)
                        is_new, rep = record_new_report(
                            store_id=sid,
                            status_code=code,
                            timestamp=ts,
                            onsite=onsite,
                            confirms=confirms,
                            packs=packs,
                            formatted_time=rep_time,
                            source="poketan",
                            pref=pref
                        )

                        if is_new and code == "i":
                            # Backfill rich history with notes/packs in background
                            threading.Thread(target=_backfill_store_history_safe, args=(sid, pref), daemon=True).start()

                    except Exception as pe:
                        continue

        except Exception as e:
            pass
        time.sleep(15)


_watcher_thread = None
_watcher_lock = threading.Lock()

def start_background_watcher():
    """Start background watcher daemon thread if not already running."""
    global _watcher_thread
    with _watcher_lock:
        if _watcher_thread is None or not _watcher_thread.is_alive():
            _watcher_thread = threading.Thread(target=telegram_background_watcher, daemon=True)
            _watcher_thread.start()
            return _watcher_thread
    return _watcher_thread



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
        confirms = int(body.get("confirms") or 1)
        conf_raw = body.get("conf_raw") or body.get("conf")
        if conf_raw:
            try:
                parsed = parse_store_status(f"{status_code}{timestamp}", str(conf_raw))
                if parsed:
                    onsite = parsed.get("onsite", onsite)
                    confirms = parsed.get("confirms", confirms)
                    if not packs and parsed.get("packs"):
                        packs = parsed.get("packs")
            except Exception:
                pass

        existing_s = db_get_store_by_id(store_id)
        store_pref = existing_s.get("pref") if existing_s else "osaka"

        is_new, rep = record_new_report(
            store_id=store_id,
            status_code=status_code,
            timestamp=timestamp,
            onsite=onsite,
            confirms=confirms,
            packs=packs,
            note=note,
            user=user,
            who=who,
            formatted_time=formatted_time,
            source=source,
            pref=store_pref
        )

        if is_new and status_code == "i":
            threading.Thread(target=_backfill_store_history_safe, args=(store_id, store_pref), daemon=True).start()

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
        local_hist = db_get_store_history(clean_id, limit=100)
        # If fewer than 2 records, backfill from PokéTan and save into SQLite
        if len(local_hist) < 2:
            try:
                existing_s = db_get_store_by_id(clean_id)
                store_pref = existing_s.get("pref") if existing_s else "osaka"
                remote_hist = fetch_store_history(clean_id)
                if remote_hist:
                    save_bulk_history(clean_id, remote_hist, source="poketan", pref=store_pref)
                    local_hist = db_get_store_history(clean_id, limit=100)
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


@app.get("/api/analytics/store/{store_id}")
def get_store_analytics(store_id: str):
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    try:
        from .db import get_store_restock_analytics
        data = get_store_restock_analytics(clean_id)
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error fetching analytics for {clean_id}:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/latest_reports")
def get_latest_reports_route(since: int = 0, limit: int = 50):
    try:
        from .db import get_recent_reports
        reports = get_recent_reports(since_created_at=since, limit=limit)
        return JSONResponse(content=reports)
    except Exception as e:
        print("[DB] Error fetching latest reports:", e)
        return JSONResponse(content=[])



@app.post("/api/admin/harvest_all")
def trigger_harvest_all():
    """Admin endpoint to trigger full backfill from PokéTan into SQLite CSDL."""
    from .harvester import harvest_all_to_csdl
    try:
        res = harvest_all_to_csdl()
        return JSONResponse(content={"status": "ok", "result": res})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


@app.get("/api/config")
def get_config():
    import time
    user_settings = load_user_settings()
    notif = user_settings.get("notifications", {})
    return {
        "serverTime": int(time.time()),
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
        "currentRegion": user_settings.get("currentRegion", "all"),
        "activeFilter": user_settings.get("activeFilter", "all"),
        "activeTime": user_settings.get("activeTime", "all"),
        "stockPinEffectHours": str(user_settings.get("stockPinEffectHours", "24"))
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

    uvicorn.run("app.web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
