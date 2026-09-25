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

from .fetcher import fetch_stores, fetch_firestore_document, DEFAULT_CACHE_DIR, fetch_store_history
from .parser import merge_stores_with_status
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
        "discordEnabled": False,      # Bật gửi Discord khi có hàng
        "telegramBotToken": "",       # Token bot Telegram (từ @BotFather)
        "telegramChatId": "",         # ID chat hoặc nhóm Telegram
        "telegramEnabled": False,     # Bật gửi Telegram khi có hàng
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


@app.post("/api/notify/webhook")
async def send_webhook_notification(request: Request):
    """
    Dispatch in-stock notifications to Discord Webhook and Telegram Bot.
    Payload: {
        "store": { "id", "name", "chain_label", "address", "lat", "lng" },
        "info": { "label", "packs", "reported_at", "timeAgo", "confirms", "onsite" },
        "is_test": bool
    }
    """
    import urllib.request
    import urllib.parse
    
    try:
        body = await request.json()
        store = body.get("store") or {}
        info = body.get("info") or {}
        is_test = bool(body.get("is_test", False))
        
        cfg = load_user_settings().get("notifications", {})
        results = {}

        # Check prefecture filter for notifications
        store_pref = store.get("pref") or ""
        allowed_prefs = cfg.get("notifyPrefs")
        if not is_test and allowed_prefs and store_pref and store_pref not in allowed_prefs:
            return JSONResponse(content={"status": "filtered", "reason": f"pref '{store_pref}' not in allowed notification prefectures"})

        # Fetch store report history if store_id available
        store_id = store.get("id") or ""
        history_list = []
        if store_id and store_id != "test_store_webhook":
            try:
                history_list = fetch_store_history(store_id) or []
            except Exception as he:
                print("Could not fetch history for webhook:", he)
        elif is_test:
            # Demo history entries for test notification
            history_list = [
                {
                    "status_code": "o",
                    "status_label": "🔴 Hết hàng",
                    "note": "Hết đợt Terastal Festival",
                    "formatted_time": "14:20 24/09",
                    "timestamp": 1727155200,
                    "user": "Trainer_A"
                },
                {
                    "status_code": "i",
                    "status_label": "🟢 Có hàng",
                    "note": "Về 2 box Terastal",
                    "formatted_time": "09:15 24/09",
                    "timestamp": 1727136900,
                    "user": "Trainer_B"
                }
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

        # Build concise history text for Telegram and Discord
        hist_text_tg_lines = []
        hist_fields_discord = []
        if filtered_hist:
            for item in filtered_hist:
                s_icon = "🟢" if item.get("status_code") == "i" else ("🔴" if item.get("status_code") == "o" else "⚪")
                t_str = item.get("formatted_time") or "Trước đó"
                note_str = f" ({item.get('note')})" if item.get("note") else ""
                hist_text_tg_lines.append(f"- {s_icon} {t_str}: {item.get('status_label', '')}{note_str}")
                hist_fields_discord.append(f"- {s_icon} `{t_str}`: {item.get('status_label', '')}{note_str}")

        packs_text = ", ".join(info.get("packs", [])) if info.get("packs") else "Gói thẻ Pokémon (Xem tại quán)"
        store_name = store.get('name', 'Cửa hàng')
        store_chain = store.get('chain_label') or store.get('chain') or 'Tiện lợi'
        store_addr = store.get('address') or 'Khu vực Osaka'
        maps_query = urllib.parse.quote_plus(f"{store_name} {store_addr}".strip())
        maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}" if maps_query else ""
        time_display = info.get('reported_at', 'Vừa xong')
        if info.get('timeAgo'):
            time_display += f" ({info.get('timeAgo')})"

        dist_line_tg = f"🚶 <b>Khoảng cách cách ga Imamiya:</b> ~{imamiya_dist_str}" if imamiya_dist_str else ""

        # 1. DISCORD WEBHOOK
        discord_url = (cfg.get("discordWebhookUrl") or "").strip()
        discord_enabled = cfg.get("discordEnabled", False) or is_test
        
        if discord_url and discord_enabled:
            try:
                embed_fields = [
                    {"name": "📍 Địa chỉ", "value": store_addr, "inline": False}
                ]
                if imamiya_dist_str:
                    embed_fields.append({"name": "🚶 Khoảng cách cách ga Imamiya", "value": f"~{imamiya_dist_str}", "inline": True})
                embed_fields.extend([
                    {"name": "📦 Sản phẩm", "value": packs_text, "inline": False},
                    {"name": "⏱ Báo lúc", "value": time_display, "inline": True}
                ])
                if hist_fields_discord:
                    embed_fields.append({
                        "name": "📜 Lịch sử các lần báo trước:",
                        "value": "\n".join(hist_fields_discord),
                        "inline": False
                    })
                if maps_url:
                    embed_fields.append({
                        "name": "🗺️ Chỉ đường",
                        "value": f"[Mở Google Maps dẫn đường chính xác]({maps_url})",
                        "inline": False
                    })

                embed = {
                    "title": f"{'🧪 [TEST] ' if is_test else '🔥 '}{store_name} ({store_chain})",
                    "description": f"📍 **{store_addr}**\n🚶 **Khoảng cách cách ga Imamiya:** ~{imamiya_dist_str if imamiya_dist_str else 'N/A'}\n\n🟢 **TRẠNG THÁI: CÓ HÀNG (IN STOCK)**",
                    "color": 0x16a34a,
                    "fields": embed_fields,
                    "footer": {
                        "text": "BAWUI POKE APP • Osaka Stock Radar"
                    }
                }

                payload = {
                    "username": "BAWUI Poke Radar",
                    "avatar_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png",
                    "embeds": [embed]
                }
                req = urllib.request.Request(
                    discord_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "BAWUI-PokeApp"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    results["discord"] = "ok"
            except Exception as de:
                results["discord"] = f"error: {str(de)}"
        elif not discord_url:
            results["discord"] = "no_url"

        # 2. TELEGRAM BOT
        tg_token = (cfg.get("telegramBotToken") or "").strip()
        tg_chat_id = (cfg.get("telegramChatId") or "").strip()
        tg_enabled = cfg.get("telegramEnabled", False) or is_test
        
        if tg_token and tg_chat_id and tg_enabled:
            try:
                header_prefix = "🧪 <b>[THÔNG BÁO THỬ NGHIỆM]</b>\n" if is_test else "🔥 <b>CÓ HÀNG MỚI!</b>\n"
                
                # Format đúng chuẩn theo yêu cầu:
                # 1. Tên cửa hàng
                # 2. Địa chỉ
                # 3. Khoảng cách cách ga Imamiya
                # 4. Trạng thái & Sản phẩm
                # 5. Xuống dòng
                # 6. - Lịch sử: Xuống dòng từng dòng với dấu gạch ngang (-)
                # 7. Link mở Google Maps
                # Format ngắn gọn giống toast trên bản đồ
                dist_part = f" • 📍 ~{imamiya_dist_str}" if imamiya_dist_str else ""
                msg_lines = [
                    f"🔥 <b>{store_name}</b> - CÓ HÀNG!",
                    f"📦 {packs_text}{dist_part} • ⏱ {time_display}",
                ]
                app_url = body.get("app_url") or ""
                if app_url:
                    msg_lines.append(f"⚡ <a href=\"{app_url}\">Mở trên PokéMap App ↗</a>")
                
                tg_payload = {
                    "chat_id": tg_chat_id,
                    "text": "\n".join(msg_lines),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
                tg_api_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                req = urllib.request.Request(
                    tg_api_url,
                    data=json.dumps(tg_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    results["telegram"] = "ok"
            except Exception as te:
                results["telegram"] = f"error: {str(te)}"
        elif not (tg_token and tg_chat_id):
            results["telegram"] = "no_credentials"

        return JSONResponse(content={"status": "ok", "results": results})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


_stores_cache = None
_cold_cache = None

# All available prefectures on PokéTan
ALL_PREFS = ["osaka", "aichi", "kanagawa", "gifu", "mie"]


def get_stores_metadata():
    global _stores_cache
    if _stores_cache is None:
        all_stores = {}
        for pref in ALL_PREFS:
            try:
                stores = fetch_stores(pref=pref)
                # Tag each store with its prefecture
                for sid, store in stores.items():
                    store["pref"] = pref
                all_stores.update(stores)
                print(f"  Loaded {len(stores)} stores from {pref}")
            except Exception as e:
                print(f"  Error loading stores from {pref}: {e}")
        _stores_cache = all_stores
        print(f"Total stores loaded: {len(all_stores)}")
    return _stores_cache


@app.get("/api/stores_data")
def get_stores_data():
    stores = get_stores_metadata()
    return JSONResponse(content=stores)


@app.get("/api/cold_status")
def get_cold_status():
    global _cold_cache
    if _cold_cache is None:
        _cold_cache = {}
        for pref in ALL_PREFS:
            try:
                data = fetch_firestore_document(f"status/{pref}_cold")
                _cold_cache.update(data)
            except Exception as e:
                print(f"Cold status {pref}: {e}")
    return JSONResponse(content=_cold_cache)


@app.get("/api/hot_status")
def get_hot_status():
    try:
        merged = {}
        for pref in ALL_PREFS:
            try:
                data = fetch_firestore_document(f"status/{pref}")
                merged.update(data)
            except Exception:
                pass
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



@app.get("/api/config")
def get_config():
    return {
        "apiKey": FIREBASE_API_KEY,
        "projectId": PROJECT_ID,
        "chainNames": CHAIN_NAMES,
        "packCodes": PACK_CODES
    }


@app.get("/api/calendar")
def get_calendar(include_expired: bool = False):
    return fetch_calendar_events(include_expired=include_expired)


@app.get("/", response_class=HTMLResponse)
@app.get("/map", response_class=HTMLResponse)
@app.get("/stores", response_class=HTMLResponse)
@app.get("/calendar", response_class=HTMLResponse)
@app.get("/events", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>⚡ PokéMap - Bản Đồ Thẻ Pokémon</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
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
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      -webkit-tap-highlight-color: transparent;
    }
    html, body {
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #0f172a;
    }

    #map {
      width: 100%;
      height: 100%;
      position: absolute;
      top: 0;
      left: 0;
      z-index: 1;
    }

    /* TOP FLOATING HEADER */
    #top-bar {
      position: absolute;
      top: 12px;
      left: 12px;
      right: 12px;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      gap: 8px;
      pointer-events: none;
      max-width: 680px;
      margin: 0 auto;
    }

    .top-panel {
      pointer-events: auto;
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 14px;
      padding: 10px 14px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
      color: white;
    }

    .top-row-1 {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .brand-title {
      font-weight: 900;
      font-size: 1.05rem;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 6px;
      color: #f8fafc;
    }
    .brand-title span.badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 2px 6px;
      background: #2563eb;
      border-radius: 6px;
      text-transform: uppercase;
    }

    .pref-select {
      background: #1e293b;
      color: #f8fafc;
      border: 1px solid #334155;
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      outline: none;
      cursor: pointer;
    }

    /* FILTER BUTTONS ROW */
    .filter-pills {
      display: flex;
      gap: 6px;
      margin-top: 8px;
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      padding-bottom: 2px;
    }
    .filter-pills::-webkit-scrollbar { display: none; }

    .pill-btn {
      flex: 1;
      min-width: fit-content;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      padding: 6px 10px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: #1e293b;
      color: #94a3b8;
      font-size: 0.74rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .pill-btn:hover {
      background: #334155;
      color: white;
    }
    .pill-btn.active {
      background: #2563eb;
      border-color: #3b82f6;
      color: white;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }
    .pill-btn .cnt {
      font-size: 0.7rem;
      font-weight: 800;
      opacity: 0.9;
    }

    /* SEARCH BAR */
    .search-row {
      margin-top: 8px;
      position: relative;
    }
    .search-input {
      width: 100%;
      height: 34px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 0 10px 0 32px;
      font-size: 0.78rem;
      color: white;
      outline: none;
    }
    .search-input:focus {
      border-color: #3b82f6;
    }
    .search-icon {
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 0.75rem;
      color: #64748b;
    }

    /* GPS FLOATING BUTTON */
    #gps-btn {
      position: absolute;
      bottom: 24px;
      right: 20px;
      z-index: 1000;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #2563eb;
      box-shadow: 0 4px 18px rgba(0,0,0,0.3);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.3rem;
      transition: transform 0.2s, background 0.2s;
    }
    #gps-btn:active {
      transform: scale(0.92);
      background: #eff6ff;
    }

    /* USER LOCATION PULSE */
    .user-location-marker {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #2563eb;
      border: 3px solid #ffffff;
      box-shadow: 0 0 12px rgba(37, 99, 235, 0.8);
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
      border: 2px solid #3b82f6;
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 1; }
      100% { transform: scale(2.2); opacity: 0; }
    }

    /* LEAFLET POPUP STYLES */
    .leaflet-popup-content-wrapper {
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.25);
      padding: 0;
      overflow: hidden;
    }
    .leaflet-popup-content {
      margin: 0;
      padding: 14px 16px;
      font-family: 'Inter', sans-serif;
      min-width: 240px;
      max-width: 320px;
      color: #0f172a;
    }
    .store-popup-title {
      font-weight: 800;
      font-size: 0.95rem;
      line-height: 1.3;
      color: #0f172a;
    }
    .store-popup-chain {
      font-size: 0.72rem;
      color: #0284c7;
      font-weight: 700;
      margin-top: 2px;
    }
    .store-popup-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 800;
      font-size: 0.84rem;
      padding: 5px 10px;
      border-radius: 8px;
      margin: 8px 0;
      width: 100%;
    }
    .status-in {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }
    .status-out {
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #fca5a5;
    }
    .status-unknown {
      background: #f1f5f9;
      color: #64748b;
      border: 1px solid #e2e8f0;
    }

    .store-popup-meta {
      font-size: 0.74rem;
      color: #475569;
      line-height: 1.4;
      margin-bottom: 4px;
    }
    .store-popup-addr {
      font-size: 0.73rem;
      color: #64748b;
      background: #f8fafc;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
      margin-top: 6px;
      line-height: 1.35;
    }
    .btn-maps-dir {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      width: 100%;
      padding: 8px 12px;
      margin-top: 10px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.78rem;
      box-shadow: 0 2px 6px rgba(37,99,235,0.3);
    }
    .btn-maps-dir:hover {
      background: #1d4ed8;
    }

    /* LOADING SPINNER */
    #loading-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: #0f172a;
      z-index: 2000;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: white;
      transition: opacity 0.3s ease;
    }
    .spinner {
      width: 38px;
      height: 38px;
      border: 3.5px solid rgba(255,255,255,0.2);
      border-top-color: #3b82f6;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  </style>
</head>
<body>

  <!-- LOADING OVERLAY -->
  <div id="loading-overlay">
    <div class="spinner"></div>
    <div style="margin-top: 14px; font-weight: 700; font-size: 0.9rem;" id="loading-text">
      Đang tải bản đồ & dữ liệu cửa hàng...
    </div>
  </div>

  <!-- TOP BAR -->
  <div id="top-bar">
    <div class="top-panel">
      <!-- ROW 1: BRAND & PREFECTURE SELECTOR -->
      <div class="top-row-1">
        <div class="brand-title">
          <span>⚡ PokéMap</span>
          <span class="badge" id="live-indicator">LIVE</span>
        </div>
        <select class="pref-select" id="pref-select" onchange="changePrefecture(this.value)">
          <option value="all" selected>🗾 Tất cả tỉnh (11,968)</option>
          <option value="osaka">🏯 大阪府 Osaka (4,050)</option>
          <option value="aichi">🏯 愛知県 Aichi (3,849)</option>
          <option value="kanagawa">🏯 神奈川県 Kanagawa (4,044)</option>
          <option value="gifu">🏯 岐阜県 Gifu (21)</option>
          <option value="mie">🏯 三重県 Mie (4)</option>
        </select>
      </div>

      <!-- ROW 2: 3 STATUS FILTER PILLS -->
      <div class="filter-pills">
        <button class="pill-btn active" id="btn-filter-all" onclick="setStatusFilter('all')">
          <span>🏢 Tất cả</span>
          <span class="cnt" id="cnt-all">...</span>
        </button>
        <button class="pill-btn" id="btn-filter-in" onclick="setStatusFilter('in')">
          <span>🟢 Có hàng</span>
          <span class="cnt" id="cnt-in">0</span>
        </button>
        <button class="pill-btn" id="btn-filter-out" onclick="setStatusFilter('out')">
          <span>🔴 Hết hàng</span>
          <span class="cnt" id="cnt-out">0</span>
        </button>
        <button class="pill-btn" id="btn-filter-unknown" onclick="setStatusFilter('unknown')">
          <span>🔘 Chưa có tin</span>
          <span class="cnt" id="cnt-unknown">...</span>
        </button>
      </div>

      <!-- ROW 3: SEARCH -->
      <div class="search-row">
        <span class="search-icon">🔍</span>
        <input type="text" class="search-input" id="search-input" placeholder="Tìm tên cửa hàng, ga tàu, địa chỉ..." oninput="onSearch(this.value)" />
      </div>
    </div>
  </div>

  <!-- MAP -->
  <div id="map"></div>

  <!-- GPS BUTTON -->
  <button id="gps-btn" onclick="locateUser(true)" title="Định vị vị trí của tôi">
    📍
  </button>

  <script>
    // 1. STATE & DATA
    let storesDict = {};         // All store metadata
    let hotStatus = {};           // Real-time status
    let coldStatus = {};          // Historical / cold status
    let configData = {};          // Pack codes & Chain names
    let currentPref = 'all';      // 'all' | 'osaka' | 'aichi' | ...
    let currentFilter = 'all';    // 'all' | 'in' | 'out' | 'unknown'
    let searchQuery = '';
    
    // GPS State
    let userLat = null;
    let userLng = null;
    let userMarker = null;
    let userCircle = null;

    // 2. LEAFLET MAP INITIALIZATION
    const map = L.map('map', {
      center: [34.6937, 135.5023], // Osaka center
      zoom: 12,
      zoomControl: false,
      preferCanvas: true
    });

    // Clean, crisp basemap tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap, &copy; CARTO'
    }).addTo(map);

    // Zoom control at bottom left
    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // Canvas layer for maximum 60fps rendering performance
    const canvasRenderer = L.canvas({ padding: 0.5 });
    const markersLayer = L.layerGroup().addTo(map);

    // 3. STATUS DECODER
    function decodeStatus(rawVal) {
      if (!rawVal || typeof rawVal !== 'string') {
        return { code: 'u', label: 'Chưa có thông tin gần đây', packs: [], reported_at: '', timeAgo: '' };
      }
      const code = rawVal[0].toLowerCase();
      let rest = rawVal.substring(1);

      if (rest.endsWith('g')) rest = rest.slice(0, -1);

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
      if (rest.length >= 10) {
        const parsed = parseInt(rest.substring(0, 10), 10);
        if (!isNaN(parsed) && parsed > 0) {
          const d = new Date(parsed * 1000);
          dtStr = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) + ' ' +
                  d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' });
          const diffSec = Math.floor(Date.now() / 1000 - parsed);
          if (diffSec < 60) timeAgo = 'Vừa xong';
          else if (diffSec < 3600) timeAgo = `${Math.floor(diffSec / 60)} phút trước`;
          else if (diffSec < 86400) timeAgo = `${Math.floor(diffSec / 3600)} giờ trước`;
          else timeAgo = `${Math.floor(diffSec / 86400)} ngày trước`;
        }
      }

      const labelMap = {
        'i': '🟢 Có hàng (In Stock)',
        'o': '🔴 Hết hàng (Out of Stock)',
        'n': '⚪ Không bán thẻ',
        'u': '🔘 Chưa có thông tin'
      };

      return {
        code,
        label: labelMap[code] || 'Chưa rõ',
        packs,
        reported_at: dtStr,
        timeAgo
      };
    }

    // 4. DISTANCE CALCULATION
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
      if (km === null || isNaN(km)) return '';
      if (km < 1) return `${Math.round(km * 1000)}m`;
      return `${km.toFixed(1)}km`;
    }

    // 5. RENDER ALL STORE MARKERS
    function renderMarkers() {
      markersLayer.clearLayers();

      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };

      let cntIn = 0;
      let cntOut = 0;
      let cntUnknown = 0;
      let cntTotal = 0;

      const q = searchQuery.toLowerCase().trim();

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;

        // Prefecture Filter
        if (currentPref !== 'all' && store.pref !== currentPref) continue;

        const sid = store.id;
        const raw = effectiveStatus[sid];
        const info = decodeStatus(raw);

        // Count totals for current prefecture
        cntTotal++;
        if (info.code === 'i') cntIn++;
        else if (info.code === 'o') cntOut++;
        else cntUnknown++;

        // Status Filter
        if (currentFilter === 'in' && info.code !== 'i') continue;
        if (currentFilter === 'out' && info.code !== 'o') continue;
        if (currentFilter === 'unknown' && info.code === 'i') continue;

        // Search Filter
        if (q) {
          const matchName = (store.name || '').toLowerCase().includes(q);
          const matchAddr = (store.address || '').toLowerCase().includes(q);
          if (!matchName && !matchAddr) continue;
        }

        // Marker Style by Status
        let radius = 4.5;
        let fillColor = '#94a3b8';
        let strokeColor = '#64748b';
        let weight = 1;
        let fillOpacity = 0.65;

        if (info.code === 'i') {
          // 🟢 CÓ HÀNG
          radius = 8.5;
          fillColor = '#16a34a';
          strokeColor = '#ffffff';
          weight = 2.5;
          fillOpacity = 1;
        } else if (info.code === 'o') {
          // 🔴 HẾT HÀNG
          radius = 6;
          fillColor = '#ef4444';
          strokeColor = '#b91c1c';
          weight = 1.5;
          fillOpacity = 0.85;
        }

        const marker = L.circleMarker([store.lat, store.lng], {
          renderer: canvasRenderer,
          radius,
          fillColor,
          color: strokeColor,
          weight,
          fillOpacity
        });

        // Popup Content
        marker.bindPopup(() => {
          let distHtml = '';
          if (userLat !== null && userLng !== null) {
            const d = calcDistanceKm(userLat, userLng, store.lat, store.lng);
            distHtml = `<div style="font-size:0.75rem; color:#2563eb; font-weight:700; margin-top:2px;">📍 Cách bạn: ${formatDist(d)}</div>`;
          }

          let statusClass = 'status-unknown';
          let statusText = '🔘 Chưa có thông tin gần đây';
          if (info.code === 'i') {
            statusClass = 'status-in';
            statusText = '🟢 Có hàng (In Stock)';
          } else if (info.code === 'o') {
            statusClass = 'status-out';
            statusText = '🔴 Hết hàng (Out of Stock)';
          } else if (info.code === 'n') {
            statusClass = 'status-unknown';
            statusText = '⚪ Không bán thẻ Pokémon';
          }

          const packsHtml = info.packs.length ? `<div style="font-size:0.75rem; margin-top:4px;"><b>📦 Packs:</b> ${info.packs.join(', ')}</div>` : '';
          const timeHtml = info.timeAgo ? `<div style="font-size:0.73rem; color:#64748b; margin-top:3px;">🕒 Báo cáo: ${info.timeAgo} (${info.reported_at})</div>` : '';

          const chainLabel = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
          const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((store.name || '') + ' ' + (store.address || ''))}`;

          return `
            <div>
              <div class="store-popup-title">${store.name}</div>
              <div class="store-popup-chain">${chainLabel}</div>
              <div class="store-popup-status ${statusClass}">${statusText}</div>
              ${distHtml}
              ${timeHtml}
              ${packsHtml}
              <div class="store-popup-addr">📍 ${store.address || 'Khu vực Nhật Bản'}</div>
              <a href="${mapsUrl}" target="_blank" class="btn-maps-dir">🗺️ Chỉ đường Google Maps ↗</a>
            </div>
          `;
        }, { maxWidth: 320 });

        markersLayer.addLayer(marker);
      }

      // Update counters in top bar
      document.getElementById('cnt-all').innerText = cntTotal.toLocaleString();
      document.getElementById('cnt-in').innerText = cntIn.toLocaleString();
      document.getElementById('cnt-out').innerText = cntOut.toLocaleString();
      document.getElementById('cnt-unknown').innerText = cntUnknown.toLocaleString();
    }

    // 6. FILTER CONTROLS
    function setStatusFilter(filter) {
      currentFilter = filter;
      document.querySelectorAll('.pill-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.getElementById(`btn-filter-${filter}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderMarkers();
    }
    window.setStatusFilter = setStatusFilter;

    function changePrefecture(pref) {
      currentPref = pref;
      renderMarkers();

      // Pan map to center of selected prefecture
      const prefCenters = {
        'osaka': [34.6937, 135.5023],
        'aichi': [35.1815, 136.9066],
        'kanagawa': [35.4437, 139.6380],
        'gifu': [35.4233, 136.7607],
        'mie': [34.7303, 136.5086]
      };
      if (prefCenters[pref]) {
        map.flyTo(prefCenters[pref], 12, { duration: 1.0 });
      }
    }
    window.changePrefecture = changePrefecture;

    let searchTimer = null;
    function onSearch(val) {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchQuery = val;
        renderMarkers();
      }, 150);
    }
    window.onSearch = onSearch;

    // 7. GPS USER LOCATION TRACKING
    function locateUser(fly = true) {
      if (!navigator.geolocation) {
        alert('Trình duyệt của bạn không hỗ trợ GPS.');
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          const accuracy = pos.coords.accuracy;

          if (!userMarker) {
            const icon = L.divIcon({
              className: 'user-location-marker',
              iconSize: [18, 18],
              iconAnchor: [9, 9]
            });
            userMarker = L.marker([userLat, userLng], { icon, zIndexOffset: 2000 }).addTo(map);
            userMarker.bindPopup('📍 Vị trí hiện tại của bạn');
            userCircle = L.circle([userLat, userLng], {
              radius: accuracy,
              color: '#3b82f6',
              fillColor: '#93c5fd',
              fillOpacity: 0.15,
              weight: 1
            }).addTo(map);
          } else {
            userMarker.setLatLng([userLat, userLng]);
            userCircle.setLatLng([userLat, userLng]);
            userCircle.setRadius(accuracy);
          }

          if (fly) {
            map.flyTo([userLat, userLng], 14, { duration: 1.2 });
          }
        },
        (err) => {
          console.warn('GPS error:', err.message);
          if (fly) alert('Không thể lấy vị trí GPS. Hãy kiểm tra quyền truy cập vị trí trên trình duyệt.');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 10000 }
      );
    }
    window.locateUser = locateUser;

    // Watch position continuously
    if (navigator.geolocation) {
      navigator.geolocation.watchPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          if (userMarker) {
            userMarker.setLatLng([userLat, userLng]);
            if (userCircle) userCircle.setLatLng([userLat, userLng]);
          }
        },
        null,
        { enableHighAccuracy: true, maximumAge: 10000 }
      );
    }

    // 8. DATA INITIALIZATION & REAL-TIME FIRESTORE LISTENER
    async function initData() {
      try {
        const loadingText = document.getElementById('loading-text');

        // Step 1: Config
        const cfgRes = await fetch('/api/config');
        configData = await cfgRes.json();

        // Step 2: Stores Metadata
        if (loadingText) loadingText.innerText = 'Đang tải 11,968 cửa hàng...';
        const storesRes = await fetch('/api/stores_data');
        storesDict = await storesRes.json();

        // Step 3: Statuses
        if (loadingText) loadingText.innerText = 'Đang nạp trạng thái hàng thực tế...';
        const [hotRes, coldRes] = await Promise.all([
          fetch('/api/hot_status'),
          fetch('/api/cold_status')
        ]);
        hotStatus = await hotRes.json();
        coldStatus = await coldRes.json();

        // Render markers
        renderMarkers();

        // Hide loading screen
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
          overlay.style.opacity = '0';
          setTimeout(() => overlay.remove(), 350);
        }

        // Auto locate once on startup (quietly)
        locateUser(false);

        // Step 4: Real-time listener via Firebase SDK
        setupFirebaseRealtime();

      } catch (err) {
        console.error('Initialization error:', err);
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.innerHTML = `<div style="color:#ef4444; font-weight:700;">Lỗi tải dữ liệu: ${err.message}</div>`;
      }
    }

    function setupFirebaseRealtime() {
      if (!window.FirebaseInit || !configData.apiKey || !configData.projectId) return;
      try {
        const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
        const fbApp = initializeApp({
          apiKey: configData.apiKey,
          projectId: configData.projectId
        });
        const db = initializeFirestore(fbApp, {});

        const prefs = ['osaka', 'aichi', 'kanagawa', 'gifu', 'mie'];
        prefs.forEach(p => {
          const docRef = doc(db, 'status', p);
          onSnapshot(docRef, (snapshot) => {
            if (snapshot.exists()) {
              const data = snapshot.data();
              Object.assign(hotStatus, data);
              renderMarkers();
            }
          }, (err) => {
            console.warn('Realtime listener notice:', err.message);
          });
        });
      } catch (e) {
        console.warn('Realtime setup error:', e);
      }
    }

    window.addEventListener('DOMContentLoaded', initData);
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
    uvicorn.run("app.web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
