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


from concurrent.futures import ThreadPoolExecutor

def fetch_single_pref_status(pref, is_cold=False):
    doc_path = f"status/{pref}_cold" if is_cold else f"status/{pref}"
    try:
        return fetch_firestore_document(doc_path)
    except Exception as e:
        return {}

@app.get("/api/cold_status")
def get_cold_status():
    global _cold_cache
    if _cold_cache is None:
        _cold_cache = {}
        try:
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(fetch_single_pref_status, p, True) for p in ALL_PREFS]
                for f in futures:
                    _cold_cache.update(f.result())
        except Exception as e:
            print("Cold status error:", e)
    return JSONResponse(content=_cold_cache)


@app.get("/api/hot_status")
def get_hot_status():
    try:
        merged = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(fetch_single_pref_status, p, False) for p in ALL_PREFS]
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
      z-index: 500;
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

    .chip-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    .dot-green { background: #22c55e; }
    .dot-yellow { background: #eab308; }
    .dot-red { background: #ef4444; }

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

    /* 3. MAIN MAP AREA */
    #app-main {
      flex: 1;
      width: 100%;
      position: relative;
      overflow: hidden;
    }

    #map {
      width: 100%;
      height: 100%;
      position: absolute;
      top: 0;
      left: 0;
      z-index: 1;
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

    /* IN-STOCK PIN MARKER */
    .poketan-pin-wrap {
      background: transparent;
      border: none;
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

    /* 7. PREFECTURE MODAL (Area Changer) */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0,0,0,0.5);
      z-index: 2000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .modal-overlay.open {
      display: flex;
    }
    .modal-card {
      background: white;
      border-radius: 16px;
      width: 100%;
      max-width: 400px;
      overflow: hidden;
      box-shadow: 0 12px 36px rgba(0,0,0,0.25);
      animation: modalFadeIn 0.2s ease;
    }
    @keyframes modalFadeIn {
      from { transform: scale(0.95); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .modal-header {
      padding: 14px 18px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-header h3 {
      font-size: 0.95rem;
      font-weight: 800;
      color: #0f172a;
    }
    .modal-close-btn {
      background: none;
      border: none;
      font-size: 1.1rem;
      color: #64748b;
      cursor: pointer;
    }
    .modal-body {
      padding: 12px 18px;
      max-height: 65vh;
      overflow-y: auto;
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
      min-width: 240px;
      max-width: 320px;
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
      margin: 8px 0;
      width: 100%;
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
          <span id="header-loc-name">大阪府</span>
          <span style="font-size:0.6rem; color:#64748b;">▼</span>
        </div>
        <div class="loc-sub-title">エリアを変える</div>
      </div>
    </div>

    <!-- Right Hamburger Menu Button -->
    <button class="header-menu-btn" onclick="openSettingsModal()" title="メニュー">
      ☰
    </button>
  </header>

  <!-- 2. SUB-HEADER FLOATING FILTER BAR (Exact Image 3 replica) -->
  <div id="filter-bar-container">
    <div class="filter-chips-scroll">
      <button class="poketan-chip" id="chip-in" onclick="toggleFilter('in')">
        <span class="chip-dot dot-green"></span> 在庫あり
      </button>
      <button class="poketan-chip" id="chip-onsite" onclick="toggleFilter('onsite')">
        <span class="chip-dot dot-green"></span> 現地の在庫あり
      </button>
      <button class="poketan-chip" id="chip-recent" onclick="toggleFilter('recent')">
        <span style="color:#eab308;font-size:0.75rem;">★</span> 実績あり
      </button>
      <button class="poketan-chip" id="chip-hidenone" onclick="toggleFilter('hidenone')">
        <span class="chip-dot dot-yellow"></span> 扱ってない店を隠す
      </button>
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
  </div>

  <!-- 3. MAIN MAP AREA -->
  <main id="app-main">
    <div id="map"></div>

    <!-- Floating GPS Locate Button -->
    <button id="gps-btn" onclick="locateUser(true)" title="現在地を表示">
      📍
    </button>
  </main>

  <!-- 4. LIST VIEW SHEET -->
  <div id="view-list-container">
    <div class="list-header-bar">
      <div class="list-search-box">
        <span class="icon">🔍</span>
        <input type="text" id="list-search-input" placeholder="店舗名・駅名で検索..." oninput="onListSearch(this.value)" />
      </div>
      <button style="background:none;border:none;font-weight:700;color:#4f46e5;font-size:0.85rem;cursor:pointer;" onclick="switchFooterTab('map')">
        ✕ 閉じる
      </button>
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

  <!-- 6. PREFECTURE SELECTION MODAL -->
  <div id="pref-modal" class="modal-overlay" onclick="if(event.target===this) closePrefModal()">
    <div class="modal-card">
      <div class="modal-header">
        <h3>🗾 エリアを選択</h3>
        <button class="modal-close-btn" onclick="closePrefModal()">✕</button>
      </div>
      <div class="modal-body">
        <button class="pref-item-btn selected" id="pref-btn-osaka" onclick="selectPrefecture('osaka', '大阪府')">
          <span>🏯 大阪府 (Osaka)</span>
          <span style="font-size:0.75rem; color:#64748b;">4,050店舗</span>
        </button>
        <button class="pref-item-btn" id="pref-btn-aichi" onclick="selectPrefecture('aichi', '愛知県')">
          <span>🏯 愛知県 (Aichi)</span>
          <span style="font-size:0.75rem; color:#64748b;">3,849店舗</span>
        </button>
        <button class="pref-item-btn" id="pref-btn-kanagawa" onclick="selectPrefecture('kanagawa', '神奈川県')">
          <span>🏯 神奈川県 (Kanagawa)</span>
          <span style="font-size:0.75rem; color:#64748b;">4,044店舗</span>
        </button>
        <button class="pref-item-btn" id="pref-btn-gifu" onclick="selectPrefecture('gifu', '岐阜県')">
          <span>🏯 岐阜県 (Gifu)</span>
          <span style="font-size:0.75rem; color:#64748b;">21店舗</span>
        </button>
        <button class="pref-item-btn" id="pref-btn-mie" onclick="selectPrefecture('mie', '三重県')">
          <span>🏯 三重県 (Mie)</span>
          <span style="font-size:0.75rem; color:#64748b;">4店舗</span>
        </button>
        <button class="pref-item-btn" id="pref-btn-all" onclick="selectPrefecture('all', '全エリア')">
          <span>🗾 全エリア (全国)</span>
          <span style="font-size:0.75rem; color:#64748b;">11,968店舗</span>
        </button>
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
      <div class="modal-body" style="font-size:0.82rem; max-height:75vh; overflow-y:auto;">
        <!-- Store Display Filter Section -->
        <div style="margin-bottom:14px;">
          <div style="font-weight:800; font-size:0.85rem; color:#1e293b; margin-bottom:6px;">🗺️ Cài đặt hiển thị bản đồ / 表示設定</div>
          <div style="display:flex; flex-direction:column; gap:6px;">
            <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; cursor:pointer; font-weight:600;">
              <input type="radio" name="set-filter-radio" value="none" onchange="setSettingsFilter('none')">
              <span>🌐 Hiện tất cả cửa hàng (全店舗)</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; cursor:pointer; font-weight:600;">
              <input type="radio" name="set-filter-radio" value="in" onchange="setSettingsFilter('in')">
              <span>🟢 Chỉ hiện có hàng (在庫ありのみ)</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; cursor:pointer; font-weight:600;">
              <input type="radio" name="set-filter-radio" value="onsite" onchange="setSettingsFilter('onsite')">
              <span>📸 Có hàng tại chỗ / 現地確認済</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; cursor:pointer; font-weight:600;">
              <input type="radio" name="set-filter-radio" value="hidenone" onchange="setSettingsFilter('hidenone')">
              <span>⚪ Ẩn cửa hàng không có thông tin (扱無を非表示)</span>
            </label>
          </div>
        </div>

        <!-- Area / Prefecture Selection -->
        <div style="margin-bottom:14px;">
          <div style="font-weight:800; font-size:0.85rem; color:#1e293b; margin-bottom:6px;">🗾 Khu vực tỉnh thành / エリア</div>
          <button onclick="closeSettingsModal(); openPrefModal();" style="width:100%; display:flex; justify-content:space-between; align-items:center; padding:9px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; font-weight:700; color:#334155; cursor:pointer;">
            <span>📍 Khu vực đang chọn: <b id="settings-current-pref" style="color:#4f46e5;">大阪府</b></span>
            <span>Thay đổi ❯</span>
          </button>
        </div>

        <!-- Telegram & Notifications -->
        <div style="margin-bottom:14px;">
          <div style="font-weight:800; font-size:0.85rem; color:#1e293b; margin-bottom:4px;">🔔 Thông báo / 通知連携</div>
          <div style="font-size:0.73rem;color:#64748b;margin-bottom:8px;">Tự động thông báo khi có báo cáo có hàng.</div>

          <div style="background:#f8fafc;padding:10px;border-radius:8px;border:1px solid #e2e8f0;margin-bottom:8px;">
            <label style="display:flex;align-items:center;gap:8px;font-weight:700;cursor:pointer;">
              <input type="checkbox" id="set-tg-check" onchange="updateSettings('telegramEnabled', this.checked)">
              <span>✈️ Bật thông báo Telegram (Telegram通知)</span>
            </label>
          </div>
          <div style="background:#f8fafc;padding:10px;border-radius:8px;border:1px solid #e2e8f0;">
            <label style="display:flex;align-items:center;gap:8px;font-weight:700;cursor:pointer;">
              <input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)" checked>
              <span>🔊 Âm thanh thông báo (音声アラート)</span>
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
    // 1. APP STATE
    let storesDict = {};
    let hotStatus = {};
    let coldStatus = {};
    let configData = {};
    let currentPref = 'osaka';
    let activeFilter = 'none'; // 'none' | 'in' | 'onsite' | 'recent' | 'hidenone'
    let latestStockStoreId = null;

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

    // Determine initial center before map creation (avoids sudden jumps)
    let initialCenter = prefCenters[currentPref] || [34.6937, 135.5023];
    let initialZoom = 13;

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

    // 2. LEAFLET MAP WITH GOOGLE MAPS TILES (Smooth, buffered, zero watermarks)
    const map = L.map('map', {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      preferCanvas: true,
      zoomAnimation: true,
      fadeAnimation: true,
      markerZoomAnimation: true
    });

    // High performance Google Maps Streets Tiles with pre-buffering
    L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      attribution: '&copy; Google Maps',
      updateWhenIdle: true,
      keepBuffer: 3
    }).addTo(map);

    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // 3. MARKER CLUSTERING (Matching PokéTan Image 3: Blue bordered count circles ②, ③)
    let clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 46,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
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
          dtStr = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
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

    // Fast lightweight reusable marker icons
    const stockPinIcon = L.divIcon({
      html: '<div class="poketan-stock-pin">🟢</div>',
      className: 'poketan-pin-wrap',
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    const redDotIcon = L.divIcon({
      html: '<div style="width:10px;height:10px;border-radius:50%;background:#ef4444;border:1.5px solid #ffffff;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>',
      className: 'poketan-dot-wrap',
      iconSize: [10, 10],
      iconAnchor: [5, 5]
    });

    const grayDotIcon = L.divIcon({
      html: '<div style="width:8px;height:8px;border-radius:50%;background:#94a3b8;border:1px solid #ffffff;box-shadow:0 1px 2px rgba(0,0,0,0.2);"></div>',
      className: 'poketan-dot-wrap',
      iconSize: [8, 8],
      iconAnchor: [4, 4]
    });

    // 6. RENDER MARKERS (CLUSTERS + IN-STOCK PINS)
    function renderMapMarkers() {
      clusterGroup.clearLayers();
      stockLayer.clearLayers();

      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const now = Math.floor(Date.now() / 1000);

      const clusterBatch = [];
      let firstInStore = null;

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;
        if (currentPref !== 'all' && store.pref !== currentPref) continue;

        const sid = store.id;
        const raw = effectiveStatus[sid];
        const info = decodeStatus(raw);

        // Chip Filters
        if (activeFilter === 'in' && info.code !== 'i') continue;
        if (activeFilter === 'onsite' && (!info.onsite || info.code !== 'i')) continue;
        if (activeFilter === 'recent' && (info.code !== 'i' && (now - info.timestamp > 86400))) continue;
        if (activeFilter === 'hidenone' && info.code === 'n') continue;

        if (info.code === 'i') {
          if (!firstInStore) firstInStore = store;
          // In-Stock Store gets a prominent bouncing green pin on stockLayer (always unclustered & on top)
          const m = L.marker([store.lat, store.lng], { icon: stockPinIcon, zIndexOffset: 2000 });
          m.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          stockLayer.addLayer(m);
        } else {
          // Normal stores get added to clusterBatch with L.marker (NOT L.circleMarker)
          const dotIcon = info.code === 'o' ? redDotIcon : grayDotIcon;
          const cm = L.marker([store.lat, store.lng], {
            icon: dotIcon,
            hasStock: false
          });
          cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          clusterBatch.push(cm);
        }
      }

      // Fast batch add to clusterGroup (takes ~15ms!)
      if (clusterBatch.length > 0) {
        clusterGroup.addLayers(clusterBatch);
      }

      // Show/update stock toast if there are stores in stock
      const toastEl = document.getElementById('live-stock-toast');
      if (firstInStore) {
        latestStockStoreId = firstInStore.id;
        const info = decodeStatus(effectiveStatus[firstInStore.id]);
        const titleEl = document.getElementById('toast-store-title');
        const timeEl = document.getElementById('toast-time');
        if (titleEl) titleEl.innerText = firstInStore.name;
        if (timeEl) timeEl.innerText = info.timeAgo || '新着';
        if (toastEl) toastEl.style.display = 'flex';
      } else {
        if (toastEl) toastEl.style.display = 'none';
      }
    }

    function createPopupHtml(store, info) {
      let distHtml = '';
      if (userLat !== null && userLng !== null) {
        const d = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        distHtml = `<div style="font-size:0.75rem; color:#4f46e5; font-weight:700; margin-top:2px;">📍 現在地から ${formatDist(d)}</div>`;
      }

      let statusBg = '#f1f5f9';
      let statusColor = '#64748b';
      let statusText = '⚪ 扱ってない / 不明';
      if (info.code === 'i') {
        statusBg = '#dcfce7'; statusColor = '#15803d'; statusText = '🟢 在庫あり (In Stock)';
      } else if (info.code === 'o') {
        statusBg = '#fee2e2'; statusColor = '#b91c1c'; statusText = '🔴 在庫なし (Out of Stock)';
      }

      const packs = info.packs.length ? `<div style="font-size:0.74rem; margin-top:4px;"><b>📦 パック:</b> ${info.packs.join(', ')}</div>` : '';
      const time = info.timeAgo ? `<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">🕒 報告: ${info.timeAgo} (${info.reported_at})</div>` : '';
      const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'コンビニ・カード店';
      const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((store.name || '') + ' ' + (store.address || ''))}`;

      return `
        <div>
          <div class="popup-store-title">${store.name}</div>
          <div class="popup-store-chain">${chain}</div>
          <div class="popup-status-badge" style="background:${statusBg}; color:${statusColor};">${statusText}</div>
          ${distHtml}
          ${time}
          ${packs}
          <div class="popup-actions-grid">
            <a href="${mapsUrl}" target="_blank" class="btn-popup-maps">🗺️ ルート案内 ↗</a>
            <button type="button" class="btn-popup-hist" onclick="openStoreHistoryModal('${store.id}')">📜 入荷履歴 ❯</button>
          </div>
        </div>
      `;
    }

    // 7. TOAST INTERACTIONS
    function focusStockStore() {
      if (!latestStockStoreId || !storesDict[latestStockStoreId]) return;
      const s = storesDict[latestStockStoreId];
      map.flyTo([s.lat, s.lng], 16, { duration: 0.8 });
    }
    window.focusStockStore = focusStockStore;

    function hideToast() {
      document.getElementById('live-stock-toast').style.display = 'none';
    }
    window.hideToast = hideToast;

    // 8. FILTER CHIP HANDLERS
    function toggleFilter(filterName) {
      if (activeFilter === filterName) {
        activeFilter = 'none';
      } else {
        activeFilter = filterName;
      }
      // Update UI active states
      document.querySelectorAll('.poketan-chip').forEach(b => b.classList.remove('active'));
      if (activeFilter !== 'none') {
        const btn = document.getElementById(`chip-${activeFilter}`);
        if (btn) btn.classList.add('active');
      }
      renderMapMarkers();
    }
    window.toggleFilter = toggleFilter;

    // 9. GACHI MEGURI (⚡ Săn thẻ - Instant Quick Hunt)
    function triggerGachiMeguri() {
      // Switch filter to only in-stock stores
      activeFilter = 'in';
      document.querySelectorAll('.poketan-chip').forEach(b => b.classList.remove('active'));
      const chipIn = document.getElementById('chip-in');
      if (chipIn) chipIn.classList.add('active');

      renderMapMarkers();
      switchFooterTab('map');

      // Find nearest in-stock store or first in-stock store
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const inStockStores = Object.values(storesDict).filter(s => {
        if (currentPref !== 'all' && s.pref !== currentPref) return false;
        const info = decodeStatus(effectiveStatus[s.id]);
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

    // 11. STORE LIST VIEW
    function renderStoreList(query = '') {
      const listContainer = document.getElementById('store-cards-list');
      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const q = query.toLowerCase().trim();

      let matched = [];
      for (const store of allStores) {
        if (currentPref !== 'all' && store.pref !== currentPref) continue;
        const info = decodeStatus(effectiveStatus[store.id]);

        if (q) {
          const mName = (store.name || '').toLowerCase().includes(q);
          const mAddr = (store.address || '').toLowerCase().includes(q);
          if (!mName && !mAddr) continue;
        }

        let dist = null;
        if (userLat !== null && userLng !== null && store.lat && store.lng) {
          dist = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        }
        matched.push({ store, info, dist });
      }

      // Sort: in-stock first, then nearest or newest
      matched.sort((a,b) => {
        if (a.info.code === 'i' && b.info.code !== 'i') return -1;
        if (b.info.code === 'i' && a.info.code !== 'i') return 1;
        if (a.dist !== null && b.dist !== null) return a.dist - b.dist;
        return (b.info.timestamp || 0) - (a.info.timestamp || 0);
      });

      // Limit 120 for instant performance
      const renderSlice = matched.slice(0, 120);

      listContainer.innerHTML = renderSlice.map(item => {
        const { store, info, dist } = item;
        let badgeClass = 'badge-none';
        let badgeText = '不明';
        if (info.code === 'i') { badgeClass = 'badge-in'; badgeText = '🟢 在庫あり'; }
        else if (info.code === 'o') { badgeClass = 'badge-out'; badgeText = '🔴 在庫なし'; }
        else if (info.code === 'n') { badgeClass = 'badge-none'; badgeText = '⚪ 扱無'; }

        const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'コンビニ';
        const distStr = dist !== null ? ` • 📍 ${formatDist(dist)}` : '';
        const timeStr = info.timeAgo ? ` • 🕒 ${info.timeAgo}` : '';

        return `
          <div class="store-list-card" onclick="focusStoreFromList('${store.id}')">
            <div class="card-left-info">
              <div class="card-store-name">${store.name}</div>
              <div class="card-chain-time">${chain}${distStr}${timeStr}</div>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex-shrink:0;">
              <div class="card-badge ${badgeClass}">${badgeText}</div>
              <button type="button" onclick="event.stopPropagation(); openStoreHistoryModal('${store.id}')"
                      style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:2px 6px; font-size:0.62rem; font-weight:700; color:#334155; cursor:pointer;">
                📜 履歴
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

    // 12. PREFECTURE MODAL
    function openPrefModal() {
      document.getElementById('pref-modal').classList.add('open');
    }
    window.openPrefModal = openPrefModal;

    function closePrefModal() {
      document.getElementById('pref-modal').classList.remove('open');
    }
    window.closePrefModal = closePrefModal;

    function selectPrefecture(pref, label) {
      currentPref = pref;
      document.getElementById('header-loc-name').innerText = label;
      document.querySelectorAll('.pref-item-btn').forEach(b => b.classList.remove('selected'));
      const activeBtn = document.getElementById(`pref-btn-${pref}`);
      if (activeBtn) activeBtn.classList.add('selected');
      closePrefModal();

      const prefCenters = {
        'osaka': [34.6937, 135.5023],
        'aichi': [35.1815, 136.9066],
        'kanagawa': [35.4437, 139.6380],
        'gifu': [35.4233, 136.7607],
        'mie': [34.7303, 136.5086]
      };
      if (prefCenters[pref]) {
        map.flyTo(prefCenters[pref], 12, { duration: 0.8 });
      }
      renderMapMarkers();
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
      
      const inStockList = allStores.filter(s => {
        if (currentPref !== 'all' && s.pref !== currentPref) return false;
        const info = decodeStatus(effectiveStatus[s.id]);
        return info.code === 'i';
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
      const radios = document.getElementsByName('set-filter-radio');
      if (radios) {
        radios.forEach(r => {
          r.checked = (r.value === activeFilter);
        });
      }
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

    function setSettingsFilter(filterName) {
      activeFilter = filterName;
      document.querySelectorAll('.poketan-chip').forEach(b => b.classList.remove('active'));
      if (activeFilter !== 'none') {
        const btn = document.getElementById(`chip-${activeFilter}`);
        if (btn) btn.classList.add('active');
      }
      renderMapMarkers();
    }
    window.setSettingsFilter = setSettingsFilter;

    function openSearchModal() {
      switchFooterTab('list');
      const input = document.getElementById('list-search-input');
      if (input) input.focus();
    }
    window.openSearchModal = openSearchModal;

    function updateSettings(key, val) {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notifications: { [key]: val } })
      }).catch(e => console.warn(e));
    }
    window.updateSettings = updateSettings;

    // 13c. STORE HISTORY MODAL (📜 入荷履歴 / Lịch sử báo cáo)
    const storeHistoryCache = {};

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

      if (currEl) {
        currEl.innerHTML = `
          <div style="background:${currentBg}; border:1px solid #cbd5e1; border-radius:8px; padding:10px 12px;">
            <div style="font-weight:800; font-size:0.86rem; color:${currentColor};">${currentStatusBadge}</div>
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
        // Show cached marker on map if available
        if (userLat !== null && userLng !== null) {
          updateUserMarker(userLat, userLng);
        }

        // Silent GPS check on startup (userInitiated = false, zero jerky jumps)
        locateUser(false);
        startContinuousGpsWatch();

        // Step 1: Fetch config, stores, hot_status, and cold_status ALL IN PARALLEL!
        const [cfgRes, storesRes, hotRes, coldRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data'),
          fetch('/api/hot_status').catch(() => null),
          fetch('/api/cold_status').catch(() => null)
        ]);

        configData = await cfgRes.json();
        storesDict = await storesRes.json();

        if (hotRes && hotRes.ok) {
          try { hotStatus = await hotRes.json(); } catch(e) {}
        }
        if (coldRes && coldRes.ok) {
          try { coldStatus = await coldRes.json(); } catch(e) {}
        }

        // Render ALL markers once - smooth, instant, zero redundant cluster re-builds!
        renderMapMarkers();

        // Dismiss loading screen right away
        clearTimeout(safetyTimer);
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
          overlay.style.opacity = '0';
          setTimeout(() => overlay.remove(), 150);
        }

        // Realtime Firestore sync (debounced)
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
        fetch('/api/hot_status').then(r => r.json()).catch(() => ({})),
        fetch('/api/cold_status').then(r => r.json()).catch(() => ({}))
      ]).then(([hot, cold]) => {
        hotStatus = hot;
        coldStatus = cold;
        renderMapMarkers();
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

    function setupRealtime() {
      if (!window.FirebaseInit || !configData.apiKey) return;
      try {
        const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
        const app = initializeApp({ apiKey: configData.apiKey, projectId: configData.projectId });
        const db = initializeFirestore(app, {});

        ['osaka', 'aichi', 'kanagawa', 'gifu', 'mie'].forEach(p => {
          onSnapshot(doc(db, 'status', p), (snap) => {
            if (snap.exists()) {
              Object.assign(hotStatus, snap.data());
              requestRenderMarkers();
            }
          });
        });
      } catch(e) {}
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
    uvicorn.run("app.web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
