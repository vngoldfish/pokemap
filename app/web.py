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
    get_report_counts as db_get_report_counts,
    register_on_report_added
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
    global _tg_enabled_since
    try:
        data = await request.json()
        current = load_user_settings()
        old_tg = bool(current.get("notifications", {}).get("telegramEnabled", False))
        deep_update_dict(current, data)
        save_user_settings(current)
        new_tg = bool(current.get("notifications", {}).get("telegramEnabled", False))
        if new_tg and not old_tg:
            import time
            _tg_enabled_since = time.time()
            print(f"  [TelegramSettings] Telegram enabled at {_tg_enabled_since}. Silencing prior backlog.")
        return JSONResponse(content={"status": "ok", "settings": current})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import time

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
_daemon_start_time = time.time()
_tg_enabled_since = time.time()
_last_tg_enabled = False

def send_telegram_alert(store: dict, info: dict, notif_cfg: dict, is_test: bool = False) -> dict:
    """Send concise formatted alert to Telegram bot with 5 key data points."""
    import urllib.request
    import urllib.parse
    import json
    import time
    import datetime

    tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
    tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()
    tg_enabled = notif_cfg.get("telegramEnabled", False) or is_test

    if not (tg_token and tg_chat_id):
        return {"status": "no_credentials"}
    if not tg_enabled:
        return {"status": "disabled"}

    # 1. Tên cửa hàng & Chuỗi
    store_name = store.get('name', 'Cửa hàng')
    store_chain = store.get('chain_label') or store.get('chain') or ''
    chain_tag = f" ({store_chain})" if store_chain and store_chain != 'unknown' else ""

    # 2. Thời gian có báo cáo (chuẩn múi giờ Nhật Bản JST UTC+9)
    rep_ts = info.get('timestamp') or 0
    cur_t = time.time()
    if rep_ts > 0:
        import datetime
        jst = datetime.timezone(datetime.timedelta(hours=9))
        dt_jst = datetime.datetime.fromtimestamp(rep_ts, tz=jst)
        diff_sec = max(0, int(cur_t - rep_ts))
        time_clock = dt_jst.strftime("%H:%M:%S")
        if diff_sec < 60:
            time_display = f"{time_clock} (Vừa xong)"
        elif diff_sec < 3600:
            time_display = f"{time_clock} ({diff_sec // 60} phút trước)"
        else:
            time_display = f"{time_clock} ({dt_jst.strftime('%d/%m')})"
    else:
        time_display = info.get('reported_at', 'Vừa xong')
        if info.get('timeAgo'):
            time_display += f" ({info.get('timeAgo')})"

    # 3. Trạng thái
    status_code = info.get("status_code") or info.get("code") or "i"
    packs_text = ", ".join(info.get("packs", [])) if info.get("packs") else ""
    if status_code == "i":
        status_label = "🟢 Có hàng (Xác nhận tại chỗ)" if info.get("onsite") else "🟢 Có hàng"
        if packs_text:
            status_label += f" • {packs_text}"
    elif status_code == "o":
        status_label = "🔴 Hết hàng"
    elif status_code == "n":
        status_label = "⚪ Không kinh doanh thẻ"
    else:
        status_label = "🟢 Có hàng"

    # 4. Khoảng cách (cách toạ độ định vị người dùng hoặc toạ độ cố định)
    # Mặc định toạ độ cố định: Ga JR Imamiya (lat=34.6540, lng=135.4925) hoặc cấu hình anchor trong settings
    ref_lat = float(info.get("userLat") or store.get("userLat") or notif_cfg.get("anchorLat") or 34.6540)
    ref_lng = float(info.get("userLng") or store.get("userLng") or notif_cfg.get("anchorLng") or 135.4925)
    ref_name = notif_cfg.get("anchorName") or ("Vị trí của bạn" if (info.get("userLat") or store.get("userLat")) else "ga JR Imamiya")

    dist_str = ""
    st_lat = store.get("lat")
    st_lng = store.get("lng")
    if st_lat is not None and st_lng is not None:
        try:
            import math
            lat1, lon1 = float(st_lat), float(st_lng)
            lat2, lon2 = ref_lat, ref_lng
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            dist_km = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist_km < 1.0:
                dist_str = f"{int(round(dist_km * 1000))} m"
            else:
                dist_str = f"{dist_km:.1f} km"
        except Exception:
            pass
    dist_display = f"~{dist_str} (từ {ref_name})" if dist_str else "Chưa rõ toạ độ"

    # 5. Link vị trí trong PokéMap (pokemap.bawui.com) -> từ đó ấn nút ra Google Maps
    store_id = store.get("id") or info.get("store_id") or ""
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    pokemap_params = []
    if clean_id:
        pokemap_params.append(f"focus={clean_id}")
    if st_lat is not None and st_lng is not None:
        pokemap_params.append(f"lat={st_lat}&lng={st_lng}")

    query_str = ("?" + "&".join(pokemap_params)) if pokemap_params else ""
    pokemap_url = f"https://pokemap.bawui.com/{query_str}"

    store_addr = store.get('address') or 'Khu vực đang chọn'
    addr_display = f"<a href=\"{pokemap_url}\">{store_addr}</a> (🗺️ <a href=\"{pokemap_url}\">Mở PokéMap</a>)"

    test_prefix = "🧪 <b>[TEST]</b> " if is_test else ""
    msg_lines = [
        f"{test_prefix}🏪 <b>Cửa hàng:</b> <a href=\"{pokemap_url}\">{store_name}</a>{chain_tag}",
        f"⏱ <b>Thời gian:</b> {time_display}",
        f"📊 <b>Trạng thái:</b> {status_label}",
        f"📍 <b>Khoảng cách:</b> {dist_display}",
        f"🏠 <b>Địa chỉ:</b> {addr_display}"
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


def maybe_dispatch_telegram_alert(
    store_id: str,
    status_code: str,
    timestamp: int,
    onsite: bool = False,
    packs: list = None,
    note: str = "",
    formatted_time: str = None,
    source: str = "poketan",
    force_test: bool = False
) -> dict:
    """
    Unified dispatcher for Telegram alerts.
    Safely verifies all activation thresholds, freshness, deduplication, and user filters
    before dispatching. Called by both record_report_endpoint and background watcher.
    """
    global _recent_notified_keys, _daemon_start_time, _tg_enabled_since
    import time

    if not store_id or not status_code:
        return {"status": "invalid_args"}

    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    code = status_code.lower()
    ts = int(timestamp) if timestamp else int(time.time())
    now_sec = time.time()

    # 1. Deduplication check
    report_key = f"{clean_id}_{ts}_{code}"
    if report_key in _recent_notified_keys:
        return {"status": "duplicate", "reason": "already_notified"}

    # 2. Activation threshold: Never notify reports created before daemon started or TG enabled
    activation_threshold = max(_daemon_start_time - 60, _tg_enabled_since - 30)
    if not force_test and ts < activation_threshold:
        _recent_notified_keys[report_key] = now_sec
        return {"status": "too_old", "reason": f"report ts {ts} < activation threshold {activation_threshold}"}

    # 3. Freshness check: Must be reported within last 5 minutes (300 seconds)
    if not force_test and (now_sec - ts) > 300:
        _recent_notified_keys[report_key] = now_sec
        return {"status": "stale", "reason": f"report is {(now_sec - ts):.0f}s old (> 300s)"}

    # 4. Anti-spam per store: do not spam the exact same store & status within 10 minutes
    cooldown_key = f"cooldown_{clean_id}_{code}"
    last_notified = _recent_notified_keys.get(cooldown_key, 0)
    if not force_test and (now_sec - last_notified < 600):
        _recent_notified_keys[report_key] = now_sec
        return {"status": "cooldown", "reason": f"store {clean_id} notified {(now_sec - last_notified):.0f}s ago"}

    # 5. Check user notification settings
    settings = load_user_settings()
    notif_cfg = settings.get("notifications", {})
    tg_enabled = bool(notif_cfg.get("telegramEnabled", False)) or force_test
    tg_token = (notif_cfg.get("telegramBotToken") or "").strip()
    tg_chat_id = (notif_cfg.get("telegramChatId") or "").strip()

    if not tg_enabled:
        return {"status": "disabled", "reason": "telegram notifications disabled"}
    if not (tg_token and tg_chat_id):
        return {"status": "no_credentials", "reason": "missing bot token or chat_id"}

    # 6. Status filter check
    tg_status = notif_cfg.get("telegramStatus", "in")
    if not force_test:
        if tg_status == "in" and code != "i":
            return {"status": "filtered", "reason": f"status '{code}' != 'i'"}
        if tg_status == "onsite" and (code != "i" or not onsite):
            return {"status": "filtered", "reason": "not onsite in-stock"}
        if tg_status == "recent" and (code != "i" and not (ts > 0 and code != "n")):
            return {"status": "filtered", "reason": "not recent or in-stock"}

    # 7. Store resolution & Region filter
    st = db_get_store_by_id(clean_id)
    if not st:
        for p_name in ALL_PREFS:
            p_stores = get_stores_by_pref(p_name)
            if clean_id in p_stores:
                st = dict(p_stores[clean_id])
                st["pref"] = p_name
                break
    if not st:
        st = {"id": clean_id, "name": clean_id, "pref": "osaka"}

    store_pref = (st.get("pref") or "osaka").lower()
    tg_reg = notif_cfg.get("telegramRegion", "osaka")
    tg_target_prefs = REGION_PREFS.get(tg_reg, ["osaka"]) if tg_reg != "all" else ALL_PREFS

    if not force_test and tg_reg != "all" and store_pref not in tg_target_prefs:
        return {"status": "filtered", "reason": f"store pref '{store_pref}' not in '{tg_reg}'"}

    # 8. Chain filter check
    tg_chain = notif_cfg.get("telegramChain", "all")
    st_chain = (st.get("chain") or "").lower()
    if not force_test and tg_chain != "all":
        if tg_chain == "conbini" and st_chain not in ["seven", "lawson", "familymart", "ministop"]:
            return {"status": "filtered", "reason": f"chain '{st_chain}' not in conbini"}
        elif tg_chain == "specialty" and st_chain != "specialty":
            return {"status": "filtered", "reason": f"chain '{st_chain}' not specialty"}
        elif tg_chain == "electronics" and st_chain not in ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi']:
            return {"status": "filtered", "reason": f"chain '{st_chain}' not electronics"}
        elif tg_chain not in ["conbini", "specialty", "electronics"] and st_chain != tg_chain:
            return {"status": "filtered", "reason": f"chain '{st_chain}' != '{tg_chain}'"}

    # Mark as notified to avoid duplicate dispatch
    _recent_notified_keys[report_key] = now_sec
    _recent_notified_keys[cooldown_key] = now_sec

    # 9. Format info payload and send
    info_payload = {
        "status_code": code,
        "code": code,
        "timestamp": ts,
        "onsite": onsite,
        "packs": packs or [],
        "note": note or "",
        "reported_at": formatted_time or ""
    }

    print(f"  [CSDL -> Telegram] ⚡ BẢN GHI MỚI VỪA ADD VÀO CSDL: {st.get('name')} (pref={store_pref}, ts={ts}, code={code})")
    res = send_telegram_alert(st, info_payload, notif_cfg, is_test=force_test)
    print(f"  [CSDL -> Telegram] Kết quả gửi: {res}")
    return res


def on_csdl_report_added(entry: dict):
    """
    Event listener triggered ONLY when a report is newly committed into SQLite CSDL.
    External data fetching is purely to add data into CSDL; notifications are triggered from CSDL.
    """
    store_id = entry.get("store_id")
    status_code = entry.get("status_code") or "u"
    timestamp = entry.get("timestamp") or 0
    onsite = bool(entry.get("onsite", False))
    packs = entry.get("packs") or []
    note = entry.get("note") or ""
    formatted_time = entry.get("formatted_time") or ""
    source = entry.get("source") or "csdl"

    # Safely backfill full history in background if in-stock
    if status_code == "i" and store_id:
        threading.Thread(target=_backfill_store_history_safe, args=(store_id,), daemon=True).start()

    # Trigger Telegram alert check & dispatch for the new CSDL entry
    maybe_dispatch_telegram_alert(
        store_id=store_id,
        status_code=status_code,
        timestamp=timestamp,
        onsite=onsite,
        packs=packs,
        note=note,
        formatted_time=formatted_time,
        source=source
    )

# Register the CSDL hook immediately
register_on_report_added(on_csdl_report_added)


@app.post("/api/notify/webhook")
async def send_webhook_notification(request: Request):
    """
    Test or manual webhook notification endpoint.
    If is_test is True, directly validates Telegram bot credentials and sends a test message.
    Otherwise ingests report into SQLite CSDL.
    """
    try:
        body = await request.json()
        store = body.get("store") or {}
        info = body.get("info") or {}
        is_test = bool(body.get("is_test", False))
        
        user_settings = load_user_settings()
        notif_cfg = user_settings.get("notifications", {})
        
        if is_test:
            tg_res = send_telegram_alert(store, info, notif_cfg, is_test=True)
            return JSONResponse(content={"status": "ok", "results": {"telegram": tg_res.get("status", "error")}})

        # Normal webhook: Ingest into SQLite CSDL (CSDL handles new report notification event automatically)
        sid = store.get("id") or info.get("store_id")
        if sid:
            record_new_report(
                store_id=sid,
                status_code=info.get("status_code") or info.get("code") or "i",
                timestamp=info.get("timestamp") or int(time.time()),
                onsite=bool(info.get("onsite", False)),
                packs=info.get("packs") or [],
                note=info.get("note") or "",
                user=info.get("user") or "匿名トレーナー",
                formatted_time=info.get("reported_at") or "",
                source="webhook"
            )

        return JSONResponse(content={"status": "ok"})
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


def background_data_sync_daemon():
    """
    24/7 background worker running on VPS.
    Purpose: Continuously ingest external data into local SQLite CSDL.
    Completely decoupled from notifications - it ONLY adds new reports to CSDL.
    CSDL commit triggers notifications automatically via register_on_report_added.
    """
    import time
    global _daemon_start_time, _recent_notified_keys
    time.sleep(3)

    _daemon_start_time = time.time()
    print(f"  [DataSync] 24/7 External data ingestion started at {_daemon_start_time} (saving to SQLite CSDL)...")

    # Baseline scan: silence existing reports so only new ones arriving from now on are notified
    print("  [DataSync] Initializing baseline scan: silencing all existing reports...")
    for pref in ALL_PREFS:
        try:
            init_hot = fetch_realtime_status(pref, include_cold=False)
            for k, raw in init_hot.items():
                if k.endswith("_c"):
                    continue
                parsed = parse_store_status(str(raw), None)
                if parsed:
                    p_ts = parsed.get("timestamp") or 0
                    p_code = parsed.get("status_code") or "u"
                    _recent_notified_keys[f"{k}_{p_ts}_{p_code}"] = _daemon_start_time
        except Exception:
            pass
    print(f"  [DataSync] Baseline scan complete ({len(_recent_notified_keys)} reports initialized).")

    while True:
        try:
            now_sec = time.time()
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

                        # ONLY PURPOSE: Ingest into SQLite CSDL!
                        # When a report is newly added to CSDL (is_new == True),
                        # CSDL automatically triggers on_csdl_report_added callback.
                        record_new_report(
                            store_id=sid,
                            status_code=code,
                            timestamp=ts,
                            onsite=onsite,
                            packs=packs,
                            formatted_time=rep_time,
                            source="poketan"
                        )
                except Exception:
                    pass

            if len(_recent_notified_keys) > 1000:
                _recent_notified_keys = {k: v for k, v in _recent_notified_keys.items() if now_sec - v < 7200}

        except Exception as e:
            pass
        time.sleep(15)


@app.post("/api/record_report")
async def record_report_endpoint(request: Request):
    """
    Ingest a newly observed report into local SQLite store_history and update store status.
    Called when Firestore onSnapshot fires on the client or via external reporting.
    External data is only added to CSDL. CSDL automatically triggers notification hooks.
    """
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


_data_sync_started = False

@app.on_event("startup")
def startup_event():
    global _data_sync_started
    if not _data_sync_started:
        _data_sync_started = True
        import threading
        threading.Thread(target=background_data_sync_daemon, daemon=True).start()


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

    # Start 24/7 background external data ingestion worker
    startup_event()

    uvicorn.run("app.web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
