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
        "mode": "all",              # 'all' = hiện tất cả 4,050 cửa hàng, 'only_in' = chỉ hiện điểm có hàng, 'with_out' = hiện có hàng & hết hàng
        "chain": "",                # Lọc chuỗi trên bản đồ ("" = tất cả)
        "includeCold": True         # Nạp dữ liệu lịch sử (>24h)
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
        "telegramEnabled": False      # Bật gửi Telegram khi có hàng
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

        # 1. DISCORD WEBHOOK
        discord_url = (cfg.get("discordWebhookUrl") or "").strip()
        discord_enabled = cfg.get("discordEnabled", False) or is_test
        
        if discord_url and discord_enabled:
            try:
                packs_text = ", ".join(info.get("packs", [])) if info.get("packs") else "Gói thẻ Pokémon (Xem tại quán)"
                maps_url = f"https://www.google.com/maps/search/?api=1&query={store.get('lat')},{store.get('lng')}" if store.get('lat') and store.get('lng') else ""
                
                embed = {
                    "title": f"{'🧪 [TEST] ' if is_test else '🔥 '}{store.get('name', 'Cửa hàng')}",
                    "description": f"**Trạng thái:** 🟢 Có hàng (In Stock)\n**Chuỗi:** {store.get('chain_label', 'Tiện lợi')}",
                    "color": 0x16a34a,
                    "fields": [
                        {"name": "📦 Sản phẩm", "value": packs_text, "inline": False},
                        {"name": "⏱ Thời gian báo", "value": f"{info.get('reported_at', 'Vừa xong')} ({info.get('timeAgo', '')})", "inline": True},
                        {"name": "📍 Địa chỉ", "value": store.get('address') or "Khu vực Osaka", "inline": False}
                    ],
                    "footer": {
                        "text": "BAWUI POKE APP • Osaka Stock Radar"
                    }
                }
                if maps_url:
                    embed["fields"].append({"name": "🗺️ Google Maps", "value": f"[Mở bản đồ dẫn đường]({maps_url})", "inline": True})

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
                packs_text = ", ".join(info.get("packs", [])) if info.get("packs") else "Gói thẻ Pokémon (Xem tại quán)"
                maps_url = f"https://www.google.com/maps/search/?api=1&query={store.get('lat')},{store.get('lng')}" if store.get('lat') and store.get('lng') else ""
                
                header_prefix = "🧪 <b>[THÔNG BÁO THỬ NGHIỆM]</b>\n" if is_test else "🔥 <b>CÓ HÀNG MỚI TẠI OSAKA!</b>\n"
                msg_lines = [
                    f"{header_prefix}",
                    f"🏪 <b>{store.get('name', 'Cửa hàng')}</b> ({store.get('chain_label', 'Tiện lợi')})",
                    f"🟢 <b>Trạng thái:</b> Có hàng (In Stock)",
                    f"📦 <b>Sản phẩm:</b> {packs_text}",
                    f"⏱ <b>Thời gian:</b> {info.get('reported_at', 'Vừa xong')} ({info.get('timeAgo', '')})",
                    f"📍 <b>Địa chỉ:</b> {store.get('address') or 'Khu vực Osaka'}"
                ]
                if maps_url:
                    msg_lines.append(f"\n🗺️ <a href=\"{maps_url}\">Mở Google Maps chỉ đường</a>")
                
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


def get_stores_metadata():
    global _stores_cache
    if _stores_cache is None:
        _stores_cache = fetch_stores(pref="osaka")
    return _stores_cache


@app.get("/api/stores_data")
def get_stores_data():
    stores = get_stores_metadata()
    return JSONResponse(content=stores)


@app.get("/api/cold_status")
def get_cold_status():
    global _cold_cache
    if _cold_cache is None:
        try:
            _cold_cache = fetch_firestore_document("status/osaka_cold")
        except Exception as e:
            print("Error fetching cold status:", e)
            _cold_cache = {}
    return JSONResponse(content=_cold_cache)


@app.get("/api/hot_status")
def get_hot_status():
    try:
        return JSONResponse(content=fetch_firestore_document("status/osaka"))
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
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>BAWUI POKE APP - Định Vị, Tồn Kho & Lịch Bốc Thăm Thẻ Pokémon</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    html, body {
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      background: #f8fafc;
      color: #1e293b;
    }
    
    /* 1. TOP GLOBAL APPLICATION NAVBAR */
    #top-navbar {
      height: 60px;
      background: #0f172a;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid #1e293b;
      z-index: 2000;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
      flex-shrink: 0;
    }
    
    .navbar-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .brand-logo {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      cursor: pointer;
    }
    .brand-icon {
      font-size: 1.5rem;
      filter: drop-shadow(0 0 8px rgba(250, 204, 21, 0.7));
    }
    .brand-text {
      display: flex;
      flex-direction: column;
    }
    .brand-title {
      font-size: 1.15rem;
      font-weight: 900;
      letter-spacing: -0.01em;
      color: #ffffff;
    }
    .brand-sub {
      font-size: 0.65rem;
      color: #38bdf8;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    
    .live-pill {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.7rem;
      background: rgba(34, 197, 94, 0.15);
      color: #4ade80;
      padding: 4px 10px;
      border-radius: 20px;
      border: 1px solid rgba(74, 222, 128, 0.35);
      font-weight: 700;
    }
    .live-dot {
      width: 7px;
      height: 7px;
      background: #22c55e;
      border-radius: 50%;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
      70% { transform: scale(1.1); opacity: 0.8; box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
      100% { transform: scale(0.9); opacity: 1; }
    }

    /* CENTER MENU ITEMS ON HEADER (REAL NAVIGATION LINKS) */
    .navbar-menu {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(30, 41, 59, 0.75);
      padding: 4px;
      border-radius: 10px;
      border: 1px solid #334155;
    }
    .nav-menu-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 7px 18px;
      border-radius: 7px;
      color: #94a3b8;
      font-size: 0.84rem;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      user-select: none;
    }
    .nav-menu-link:hover {
      color: #f8fafc;
      background: rgba(255, 255, 255, 0.08);
    }
    .nav-menu-link.active {
      color: #ffffff;
      background: #2563eb;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }
    .nav-icon {
      font-size: 0.95rem;
    }
    .nav-text {
      white-space: nowrap;
    }
    .nav-badge {
      font-size: 0.7rem;
      padding: 2px 8px;
      border-radius: 10px;
      font-weight: 800;
    }
    .stock-badge {
      background: #16a34a;
      color: white;
    }
    .cal-badge {
      background: #f59e0b;
      color: white;
    }

    /* RIGHT CONTROLS ON HEADER */
    .navbar-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .header-gps-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid #334155;
      padding: 6px 12px;
      border-radius: 8px;
      color: #93c5fd;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .header-gps-btn:hover {
      background: #1e293b;
      border-color: #60a5fa;
      color: white;
    }
    .header-action-btn {
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid #334155;
      padding: 6px 10px;
      border-radius: 8px;
      color: #cbd5e1;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s;
    }
    .header-action-btn:hover {
      background: #1e293b;
      color: white;
      border-color: #64748b;
    }

    /* 2. APP CONTAINER & VIEW SWITCHER */
    #app-container {
      flex: 1;
      display: flex;
      overflow: hidden;
      position: relative;
    }
    .app-view {
      width: 100%;
      height: 100%;
      display: none;
    }
    .app-view.active {
      display: flex;
    }

    /* VIEW 1: STORE STOCK & MAP */
    #view-stores-mode {
      flex-direction: row;
      position: relative;
    }
    #sidebar {
      width: 540px;
      height: 100%;
      display: flex;
      flex-direction: column;
      background: white;
      border-right: 1px solid #e2e8f0;
      box-shadow: 2px 0 12px rgba(0,0,0,0.05);
      z-index: 1000;
      flex-shrink: 0;
      transition: margin-left 0.28s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    #sidebar.desktop-collapsed {
      margin-left: -540px;
    }

    /* Floating toggle button for sidebar */
    .sidebar-collapse-trigger {
      position: absolute;
      top: 14px;
      left: 540px;
      z-index: 1200;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 38px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-left: none;
      border-radius: 0 8px 8px 0;
      box-shadow: 3px 2px 8px rgba(0,0,0,0.12);
      cursor: pointer;
      font-size: 0.85rem;
      color: #334155;
      font-weight: bold;
      transition: left 0.28s cubic-bezier(0.4, 0, 0.2, 1), background 0.15s, color 0.15s;
    }
    .sidebar-collapse-trigger:hover {
      background: #f1f5f9;
      color: #2563eb;
    }
    #view-stores-mode.sidebar-hidden .sidebar-collapse-trigger {
      left: 0;
      border-left: 1px solid #cbd5e1;
    }

    @media (max-width: 768px) {
      .sidebar-collapse-trigger {
        display: none !important;
      }
    }
    
    .location-bar {
      padding: 8px 16px;
      background: #eff6ff;
      border-bottom: 1px solid #dbeafe;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.78rem;
    }
    .location-info {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #1e40af;
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .loc-btn {
      padding: 4px 10px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 0.72rem;
      cursor: pointer;
      font-weight: 700;
      transition: background 0.2s;
    }
    .loc-btn:hover { background: #1d4ed8; }
    
    /* SIDEBAR TAB SWITCHER (TÁCH BIỆT BÁO CÓ HÀNG & TRA CỨU TOÀN BỘ) */
    .sidebar-tab-switcher {
      display: flex;
      background: #f1f5f9;
      padding: 6px 12px;
      gap: 6px;
      border-bottom: 1px solid #e2e8f0;
    }
    .sidebar-tab-btn {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 8px 10px;
      border: 1.5px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: #64748b;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s ease;
      user-select: none;
    }
    .sidebar-tab-btn:hover {
      color: #0f172a;
      background: rgba(255, 255, 255, 0.7);
    }
    .sidebar-tab-btn.active {
      background: white;
      color: #0f172a;
      border-color: #cbd5e1;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
    }
    .tab-pill-badge {
      font-size: 0.68rem;
      padding: 1px 7px;
      border-radius: 12px;
      background: #16a34a;
      color: white;
      font-weight: 800;
    }
    .tab-pill-badge.muted {
      background: #94a3b8;
    }

    .stats-bar {
      display: flex;
      padding: 10px 16px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      gap: 8px;
    }
    .stat-badge {
      flex: 1;
      background: white;
      padding: 8px;
      border-radius: 8px;
      text-align: center;
      border: 1px solid #e2e8f0;
      cursor: pointer;
      transition: all 0.15s;
    }
    .stat-badge:hover { border-color: #2563eb; transform: translateY(-1px); }
    .stat-badge .num { font-size: 1.18rem; font-weight: 800; }
    .stat-badge .label { font-size: 0.68rem; color: #64748b; font-weight: 600; margin-top: 2px; }
    .stat-in { color: #16a34a; }
    .stat-out { color: #dc2626; }
    
    /* CONTROLS BAR WITH SEARCH, TIME FILTER & SETTINGS ICON */
    .controls {
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .search-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .search-box {
      flex: 1;
      padding: 9px 14px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font-size: 0.88rem;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-box:focus { border-color: #2563eb; }
    
    .settings-icon-btn {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      color: #334155;
      font-size: 1.15rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
      flex-shrink: 0;
    }
    .settings-icon-btn:hover {
      background: #0f172a;
      color: white;
      border-color: #0f172a;
      transform: rotate(45deg);
    }
    .settings-icon-btn.active {
      background: #2563eb;
      color: white;
      border-color: #2563eb;
    }

    /* COMPACT CONTROLS GRID (ZERO HORIZONTAL SCROLLBARS) */
    .controls-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      width: 100%;
    }
    .control-box {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
    }
    .control-box-label {
      font-size: 0.72rem;
      font-weight: 700;
      color: #475569;
      display: flex;
      align-items: center;
      gap: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .control-dropdown {
      width: 100%;
      height: 38px;
      padding: 0 10px;
      border-radius: 8px;
      border: 1.5px solid #cbd5e1;
      background-color: white;
      font-size: 0.8rem;
      font-weight: 600;
      color: #1e293b;
      outline: none;
      cursor: pointer;
      text-overflow: ellipsis;
      white-space: nowrap;
      overflow: hidden;
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23334155' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 10px center;
      padding-right: 28px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      transition: all 0.15s ease;
    }
    .control-dropdown:hover {
      border-color: #3b82f6;
      background-color: #f8fafc;
    }
    .control-dropdown:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
      background-color: white;
    }

    .status-quick-btn {
      padding: 5px 11px;
      border-radius: 16px;
      border: 1px solid #cbd5e1;
      background: white;
      font-size: 0.74rem;
      font-weight: 700;
      color: #475569;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }

    .filter-status-banner {
      background: #f1f5f9;
      padding: 7px 14px;
      font-size: 0.75rem;
      color: #475569;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #e2e8f0;
    }
    
    #store-list {
      flex: 1;
      overflow-y: auto;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    
    .store-card {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 12px 14px;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .store-card:hover {
      border-color: #2563eb;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
      transform: translateY(-1px);
    }
    /* ========================================================
       POKETAN STYLE LIST & PILL FILTERS
       ======================================================== */
    .poketan-chips-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      margin-bottom: 10px;
    }
    .poketan-chip {
      padding: 6px 14px;
      border-radius: 9999px;
      border: 1px solid #e2e8f0;
      background: #f8fafc;
      font-size: 0.78rem;
      font-weight: 700;
      color: #475569;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .poketan-chip:hover {
      background: #e2e8f0;
      color: #0f172a;
    }
    .poketan-chip.active {
      background: #0f172a;
      color: #ffffff;
      border-color: #0f172a;
    }
    .poketan-chip.active-in {
      background: #15803d;
      color: #ffffff;
      border-color: #15803d;
    }
    .poketan-chip.active-out {
      background: #dc2626;
      color: #ffffff;
      border-color: #dc2626;
    }

    .poketan-header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 4px 8px 4px;
      border-bottom: 1px solid #f1f5f9;
      margin-bottom: 6px;
    }
    .poketan-header-title {
      font-size: 0.78rem;
      font-weight: 800;
      color: #334155;
    }
    .poketan-sort-btn {
      font-size: 0.72rem;
      font-weight: 700;
      color: #64748b;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 3px 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .poketan-sort-btn:hover {
      background: #e2e8f0;
      color: #0f172a;
    }

    /* POKETAN CLEAN ROW */
    .poketan-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 10px;
      border-bottom: 1px solid #f1f5f9;
      cursor: pointer;
      transition: background 0.15s ease;
      gap: 12px;
      background: #ffffff;
      border-radius: 8px;
    }
    .poketan-row:hover {
      background: #f8fafc;
    }
    .poketan-row.active-store-card {
      background: #eff6ff !important;
      outline: 2px solid #3b82f6;
    }
    .poketan-row-left {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      min-width: 0;
      flex: 1;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
      margin-top: 5px;
    }
    .dot-in {
      background: #16a34a;
      box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.2);
    }
    .dot-out {
      background: #dc2626;
    }
    .dot-none {
      background: #d97706;
    }
    .dot-u {
      background: #94a3b8;
    }

    .poketan-row-main {
      min-width: 0;
      flex: 1;
    }
    .poketan-store-title-line {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .poketan-store-name {
      font-size: 0.88rem;
      font-weight: 700;
      color: #0f172a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .poketan-new-badge {
      background: #dc2626;
      color: #ffffff;
      font-size: 0.65rem;
      font-weight: 800;
      padding: 1px 5px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }
    .poketan-row-subline {
      font-size: 0.74rem;
      color: #64748b;
      margin-top: 3px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .poketan-meta-pack {
      color: #15803d;
      font-weight: 600;
      background: #f0fdf4;
      padding: 1px 6px;
      border-radius: 4px;
    }

    /* POKETAN STATUS BADGES ON THE RIGHT */
    .poketan-status-badge {
      padding: 5px 12px;
      border-radius: 9999px;
      font-size: 0.74rem;
      font-weight: 700;
      white-space: nowrap;
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .poketan-badge-in {
      background: #ecfdf5;
      color: #059669;
      border: 1px solid #a7f3d0;
    }
    .poketan-badge-out {
      background: #fef2f2;
      color: #dc2626;
      border: 1px solid #fecaca;
    }
    .poketan-badge-none {
      background: #fefce8;
      color: #ca8a04;
      border: 1px solid #fef08a;
    }
    .poketan-badge-u {
      background: #f1f5f9;
      color: #64748b;
      border: 1px solid #e2e8f0;
    }
    .store-hist-btn:hover,
    .store-accordion-toggle:hover {
      background: #2563eb;
      color: white;
      border-color: #2563eb;
      box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
    }
    .store-accordion-toggle.expanded {
      background: #1e40af;
      color: white;
      border-color: #1e3a8a;
      box-shadow: 0 2px 6px rgba(30, 64, 175, 0.3);
    }
    .accordion-arrow {
      font-size: 0.72rem;
      font-weight: 900;
      display: inline-block;
      line-height: 1;
      transition: transform 0.2s ease;
    }
    
    /* ACCORDION COLLAPSIBLE BODY (EXPANDS CARD HEIGHT IN-PLACE) */
    .store-accordion-body {
      margin-top: 8px;
      background: #f8fafc;
      border: 1.5px solid #cbd5e1;
      border-radius: 8px;
      padding: 10px 12px;
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.04);
      cursor: default;
      max-height: 320px;
      overflow-y: auto;
      animation: accordionExpand 0.22s ease-out;
    }
    .store-accordion-body::-webkit-scrollbar,
    .popup-accordion-body::-webkit-scrollbar {
      width: 5px;
    }
    .store-accordion-body::-webkit-scrollbar-thumb,
    .popup-accordion-body::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 3px;
    }
    .store-accordion-body::-webkit-scrollbar-thumb:hover,
    .popup-accordion-body::-webkit-scrollbar-thumb:hover {
      background: #94a3b8;
    }
    @keyframes accordionExpand {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .accordion-hist-entry {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 8px 10px;
      margin-bottom: 6px;
      display: flex;
      flex-direction: column;
      gap: 3px;
      transition: border-color 0.15s ease;
    }
    .accordion-hist-entry:hover {
      border-color: #94a3b8;
    }
    .accordion-hist-entry.entry-in {
      border-left: 4px solid #16a34a;
      background: #f0fdf4;
    }
    .accordion-hist-entry.entry-out {
      border-left: 4px solid #dc2626;
      background: #fef2f2;
    }
    .accordion-hist-entry.entry-none {
      border-left: 4px solid #94a3b8;
      background: #f8fafc;
    }
    .accordion-hist-entry:last-child {
      margin-bottom: 0;
    }

    .hist-mini-badge {
      font-size: 0.72rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 10px;
      display: inline-block;
      white-space: nowrap;
    }
    .hist-mini-badge.mini-in {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }
    .hist-mini-badge.mini-out {
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #fca5a5;
    }
    .hist-mini-badge.mini-none {
      background: #f1f5f9;
      color: #64748b;
      border: 1px solid #cbd5e1;
    }

    .popup-accordion-body {
      background: #f8fafc;
      border-radius: 6px;
      padding: 8px;
    }

    #map {
      flex: 1;
      height: 100%;
      position: relative;
    }
    .map-controls-box {
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .floating-btn {
      background: white;
      border: 1px solid #cbd5e1;
      box-shadow: 0 4px 10px rgba(0,0,0,0.1);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      color: #1e293b;
      transition: all 0.2s;
    }
    .floating-btn:hover {
      background: #f8fafc;
      border-color: #2563eb;
      color: #2563eb;
    }
    
    /* 3. DEDICATED CALENDAR VIEW & HEADER */
    #view-calendar-mode {
      flex-direction: column;
      background: #f8fafc;
      overflow-y: auto;
    }

    #calendar-dedicated-header {
      background: white;
      border-bottom: 1px solid #e2e8f0;
      padding: 20px 32px 16px 32px;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
      position: sticky;
      top: 0;
      z-index: 500;
    }
    .cal-header-row-1 {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 16px;
    }
    .cal-header-title-group h2 {
      font-size: 1.35rem;
      font-weight: 800;
      color: #0f172a;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .cal-header-title-group p {
      font-size: 0.84rem;
      color: #64748b;
      margin-top: 4px;
      font-weight: 500;
    }
    .cal-header-actions-group {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .cal-stat-pill {
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .cal-stat-pill.open { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .cal-stat-pill.upcoming { background: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }
    .cal-stat-pill.expired { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }

    .cal-btn-toggle-expired {
      padding: 7px 16px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 700;
      color: #334155;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .cal-btn-toggle-expired:hover {
      background: #e2e8f0;
      border-color: #94a3b8;
      color: #0f172a;
    }

    .cal-filter-toolbar {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      padding-top: 14px;
      border-top: 1px solid #f1f5f9;
    }
    .cal-search-box-wrap {
      position: relative;
      flex: 1;
      min-width: 260px;
      max-width: 440px;
    }
    .cal-search-box-wrap input {
      width: 100%;
      padding: 8px 14px 8px 36px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      font-size: 0.85rem;
      outline: none;
      transition: border-color 0.2s;
    }
    .cal-search-box-wrap input:focus { border-color: #2563eb; }
    .cal-search-box-wrap .search-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 0.85rem;
      color: #94a3b8;
    }

    .cal-chip-group {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }
    .cal-chip {
      padding: 6px 14px;
      border-radius: 18px;
      border: 1px solid #cbd5e1;
      background: white;
      font-size: 0.78rem;
      font-weight: 600;
      color: #475569;
      cursor: pointer;
      transition: all 0.15s;
    }
    .cal-chip:hover { background: #f1f5f9; color: #1e293b; }
    .cal-chip.active { background: #0f172a; color: white; border-color: #0f172a; }

    #calendar-grid-container {
      padding: 28px 32px 60px 32px;
      max-width: 1480px;
      width: 100%;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    #calendar-cards-grid, #calendar-expired-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 18px;
    }
    
    .cal-card {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
      transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
    }
    .cal-card:hover {
      border-color: #3b82f6;
      box-shadow: 0 6px 18px rgba(0,0,0,0.08);
      transform: translateY(-2px);
    }
    .cal-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .cal-status-badge {
      font-size: 0.74rem;
      font-weight: 800;
      padding: 4px 10px;
      border-radius: 14px;
    }
    .cal-open { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .cal-upcoming { background: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }
    .cal-closed { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
    
    .cal-title { font-size: 1.02rem; font-weight: 800; color: #0f172a; line-height: 1.35; }
    .cal-type { font-size: 0.75rem; color: #0284c7; font-weight: 700; }
    .cal-note { font-size: 0.8rem; color: #64748b; background: #f8fafc; padding: 10px; border-radius: 8px; line-height: 1.45; border: 1px solid #f1f5f9; }
    
    .cal-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 6px;
      padding-top: 10px;
      border-top: 1px solid #f1f5f9;
    }
    .cal-link-btn {
      padding: 7px 14px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: background 0.2s;
    }
    .cal-link-btn:hover { background: #1d4ed8; }
    .cal-checkbox-label {
      font-size: 0.78rem;
      color: #475569;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
      font-weight: 600;
    }

    .expired-divider {
      display: flex;
      align-items: center;
      gap: 16px;
      margin: 24px 0 12px 0;
    }
    .expired-divider-line {
      flex: 1;
      height: 1px;
      background: #cbd5e1;
      border-bottom: 1px dashed #cbd5e1;
    }
    .expired-divider-label {
      font-size: 0.8rem;
      font-weight: 800;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* 4. SETTINGS MODAL / POPOVER */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(4px);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .modal-content {
      background: white;
      border-radius: 14px;
      width: 92%;
      max-width: 540px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      animation: modalFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes modalFadeIn {
      from { opacity: 0; transform: scale(0.95); }
      to { opacity: 1; transform: scale(1); }
    }
    .modal-header {
      padding: 16px 20px;
      background: #0f172a;
      color: white;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-header h3 {
      font-size: 1.05rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .modal-close-btn {
      background: rgba(255, 255, 255, 0.15);
      border: none;
      color: white;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      transition: background 0.2s;
    }
    .modal-close-btn:hover { background: rgba(255, 255, 255, 0.3); }
    .modal-body {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      max-height: 80vh;
      overflow-y: auto;
    }
    .setting-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .setting-group-title {
      font-size: 0.72rem;
      font-weight: 800;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .setting-checkbox-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
      cursor: pointer;
      transition: all 0.15s;
    }
    .setting-checkbox-row:hover {
      background: #f1f5f9;
      border-color: #cbd5e1;
    }
    .setting-checkbox-left {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .setting-checkbox-left input[type="checkbox"] {
      width: 18px;
      height: 18px;
      cursor: pointer;
    }
    .status-count-pill {
      font-size: 0.75rem;
      font-weight: 800;
      padding: 3px 9px;
      border-radius: 12px;
    }
    .status-count-pill.in { background: #dcfce7; color: #15803d; }
    .status-count-pill.out { background: #fee2e2; color: #b91c1c; }
    .status-count-pill.none { background: #f1f5f9; color: #64748b; }
    .status-count-pill.u { background: #e0f2fe; color: #0369a1; }

    /* TIME RADIO ROWS */
    .time-radio-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .time-radio-row {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 9px 12px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
      cursor: pointer;
      transition: all 0.15s;
    }
    .time-radio-row:hover {
      background: #f1f5f9;
      border-color: #cbd5e1;
    }
    .time-radio-row input[type="radio"] {
      margin-top: 3px;
      cursor: pointer;
      accent-color: #2563eb;
    }
    .time-desc {
      font-size: 0.72rem;
      color: #64748b;
      margin-top: 2px;
      font-weight: 500;
    }

    .modal-quick-actions {
      display: flex;
      gap: 8px;
      padding-top: 14px;
      border-top: 1px solid #e2e8f0;
      flex-wrap: wrap;
    }
    .btn-preset {
      flex: 1;
      min-width: 130px;
      padding: 9px 12px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      border: 1px solid #cbd5e1;
      background: white;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;
    }
    .btn-preset:hover {
      background: #f8fafc;
      border-color: #2563eb;
      color: #2563eb;
    }
    .btn-preset.active {
      background: #0f172a;
      color: white;
      border-color: #0f172a;
    }

    /* USER LOCATION PULSING MARKER */
    .user-pulse-marker {
      width: 18px;
      height: 18px;
      background: #2563eb;
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 0 10px rgba(37, 99, 235, 0.8);
      position: relative;
    }
    .user-pulse-marker::after {
      content: '';
      position: absolute;
      top: -12px;
      left: -12px;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 2px solid #3b82f6;
      animation: userGpsPulse 2s infinite ease-out;
    }
    @keyframes userGpsPulse {
      0% { transform: scale(0.5); opacity: 1; }
      100% { transform: scale(1.8); opacity: 0; }
    }
    
    /* TOAST NOTIFICATION CONTAINER */
    #toast-container {
      position: fixed;
      top: 72px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 12px;
      pointer-events: none;
    }
    .toast {
      pointer-events: auto;
      width: 380px;
      background: white;
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
      border-left: 6px solid #16a34a;
      display: flex;
      flex-direction: column;
      gap: 6px;
      animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes slideIn {
      from { transform: translateX(120%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    .toast-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 800;
      font-size: 0.95rem;
      color: #16a34a;
    }
    .toast-time { font-size: 0.75rem; color: #94a3b8; }
    .toast-body { font-size: 0.88rem; color: #0f172a; font-weight: 700; }
    .toast-pack { font-size: 0.8rem; color: #b45309; background: #fef3c7; padding: 3px 8px; border-radius: 4px; display: inline-block; width: fit-content; }
    .toast-btn {
      margin-top: 4px;
      align-self: flex-start;
      padding: 5px 12px;
      background: #0f172a;
      color: white;
      font-size: 0.75rem;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 700;
    }

    /* 5. STORE HISTORY MODAL & TIMELINE */
    .btn-store-hist {
      background: #0f172a;
      color: white;
      border: 1px solid #334155;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s ease;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .btn-store-hist:hover {
      background: #2563eb;
      border-color: #2563eb;
      color: white;
    }

    .hist-timeline {
      display: flex;
      flex-direction: column;
      gap: 12px;
      position: relative;
      padding-left: 18px;
    }
    .hist-timeline::before {
      content: '';
      position: absolute;
      left: 6px;
      top: 10px;
      bottom: 10px;
      width: 2px;
      background: #e2e8f0;
    }
    .hist-item {
      position: relative;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .hist-item:hover {
      border-color: #cbd5e1;
      background: white;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .hist-item::before {
      content: '';
      position: absolute;
      left: -17px;
      top: 16px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #94a3b8;
      border: 2px solid white;
      box-shadow: 0 0 0 2px #e2e8f0;
    }
    .hist-item.hist-in {
      border-left: 4px solid #16a34a;
      background: #f0fdf4;
    }
    .hist-item.hist-in::before {
      background: #16a34a;
      box-shadow: 0 0 0 2px #bbf7d0;
    }
    .hist-item.hist-out {
      border-left: 4px solid #dc2626;
      background: #fef2f2;
    }
    .hist-item.hist-out::before {
      background: #dc2626;
      box-shadow: 0 0 0 2px #fecaca;
    }
    .hist-item.hist-none {
      border-left: 4px solid #64748b;
      background: #f8fafc;
    }
    .hist-item.hist-none::before {
      background: #64748b;
      box-shadow: 0 0 0 2px #e2e8f0;
    }

    .hist-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }
    .hist-status-badge {
      font-size: 0.76rem;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 6px;
    }
    .hist-status-in { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .hist-status-out { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .hist-status-none { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
    .hist-status-u { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }

    .hist-time-ago {
      font-size: 0.8rem;
      font-weight: 800;
      color: #0f172a;
    }
    .hist-timestamp {
      font-size: 0.72rem;
      color: #64748b;
    }
    .hist-note {
      font-size: 0.82rem;
      color: #1e293b;
      background: rgba(255, 255, 255, 0.75);
      border: 1px solid rgba(0, 0, 0, 0.06);
      border-radius: 6px;
      padding: 6px 10px;
      line-height: 1.4;
      font-weight: 500;
    }
    .hist-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.72rem;
      color: #64748b;
      margin-top: 2px;
    }
    .hist-badge-onsite {
      background: #e0f2fe;
      color: #0369a1;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      border: 1px solid #bae6fd;
    }

    /* 6. DEDICATED TAB BAR FOR MAP SETTINGS & NOTIFICATION SETTINGS */
    .settings-tab-nav {
      display: flex;
      background: #0f172a;
      padding: 6px 16px 0 16px;
      gap: 8px;
      border-bottom: 2px solid #334155;
    }
    .settings-tab-btn {
      flex: 1;
      padding: 10px 14px;
      border-radius: 8px 8px 0 0;
      border: 1px solid transparent;
      border-bottom: none;
      background: rgba(255, 255, 255, 0.08);
      font-size: 0.82rem;
      font-weight: 700;
      color: #94a3b8;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .settings-tab-btn:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.15);
    }
    .settings-tab-btn.active {
      background: white;
      color: #0f172a;
      border-color: #cbd5e1;
      box-shadow: 0 -2px 6px rgba(0,0,0,0.1);
    }
    .btn-test-action {
      padding: 6px 12px;
      background: #f8fafc;
      color: #1e293b;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 0.76rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s;
    }
    .btn-test-action:hover {
      background: #2563eb;
      color: white;
      border-color: #2563eb;
    }
    .notif-badge-state {
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 12px;
    }
    .notif-badge-granted {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }
    .notif-badge-denied {
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #fca5a5;
    }
    .notif-badge-default {
      background: #fef9c3;
      color: #854d0e;
      border: 1px solid #fde047;
    }
    /* ============================================
       MOBILE BOTTOM NAVIGATION BAR (Hidden on desktop)
       ============================================ */
    #mobile-bottom-nav {
      display: none;
    }

    /* ============================================
       MOBILE RESPONSIVE STYLES (≤ 768px)
       ============================================ */
    @media (max-width: 768px) {

      /* --- GLOBAL MOBILE TOUCH IMPROVEMENTS --- */
      html, body {
        -webkit-text-size-adjust: 100%;
        -webkit-tap-highlight-color: transparent;
      }
      #store-list,
      .modal-body,
      #view-calendar-mode,
      .store-accordion-body,
      .popup-accordion-body {
        -webkit-overflow-scrolling: touch;
        overscroll-behavior: contain;
      }

      /* --- TOP NAVBAR: Compact --- */
      #top-navbar {
        height: 48px;
        padding: 0 12px;
      }
      .navbar-left {
        gap: 8px;
      }
      .brand-icon {
        font-size: 1.25rem;
      }
      .brand-title {
        font-size: 0.95rem;
      }
      .brand-sub,
      .live-pill {
        display: none !important;
      }
      /* Hide desktop center menu on mobile - replaced by bottom nav */
      .navbar-menu {
        display: none !important;
      }
      /* Compact right action buttons: icon only */
      .navbar-right {
        gap: 6px;
      }
      .navbar-right .header-action-btn span,
      .navbar-right .header-gps-btn span#header-loc-summary,
      .navbar-right .header-gps-btn span#sound-text {
        display: none;
      }
      .navbar-right .header-action-btn,
      .navbar-right .header-gps-btn {
        padding: 8px;
        min-width: 40px;
        min-height: 40px;
        justify-content: center;
        font-size: 1.05rem;
      }
      /* Only show emoji/icon, hide text in header buttons */
      .header-action-btn span:first-child,
      .header-gps-btn span:first-child {
        display: inline !important;
        font-size: 1.1rem;
      }
      #btn-header-map,
      #btn-header-notif {
        display: none !important;
      }

      /* --- APP CONTAINER: Stack vertically --- */
      #app-container {
        position: relative;
        overflow: hidden;
      }

      /* --- MAP VIEW: Full screen with sidebar overlay --- */
      #view-stores-mode {
        flex-direction: column;
        position: relative;
      }

      /* Sidebar: full screen overlay, hidden by default on mobile */
      #sidebar {
        position: absolute;
        top: 0;
        left: 0;
        width: 100% !important;
        height: 100% !important;
        z-index: 1500;
        transform: translateX(-100%);
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        border-right: none;
        box-shadow: none;
        will-change: transform;
      }
      #sidebar.mobile-visible {
        transform: translateX(0);
        box-shadow: 4px 0 24px rgba(0,0,0,0.15);
      }

      /* Map: always full area */
      #map {
        width: 100% !important;
        height: 100% !important;
        position: absolute;
        top: 0;
        left: 0;
      }

      /* Map floating controls: compact for mobile */
      .map-controls-box {
        top: 8px;
        right: 8px;
        gap: 6px;
      }
      .floating-btn {
        padding: 8px 10px;
        font-size: 0.75rem;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      }
      .floating-btn span {
        font-size: 0.75rem;
      }

      /* --- SIDEBAR INTERNALS: Mobile optimized --- */
      .location-bar {
        padding: 8px 12px;
      }
      .stats-bar {
        padding: 8px 12px;
        gap: 6px;
      }
      .stat-badge {
        padding: 8px 4px;
        min-height: 54px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
      }
      .stat-badge .num {
        font-size: 1.1rem;
      }
      .stat-badge .label {
        font-size: 0.64rem;
      }

      .controls {
        padding: 10px 12px;
        gap: 8px;
      }
      .search-row {
        gap: 6px;
      }
      .search-box {
        padding: 10px 12px;
        font-size: 16px; /* prevents iOS zoom on focus */
        border-radius: 10px;
      }
      .settings-icon-btn {
        width: 44px;
        height: 44px;
        font-size: 1.2rem;
      }

      .controls-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        width: 100%;
      }
      .control-box {
        min-width: 0;
      }
      .search-box {
        height: 36px;
        padding: 0 10px;
        font-size: 14px;
        border-radius: 8px;
      }
      .control-dropdown {
        height: 36px;
        font-size: 13px;
        padding: 0 6px;
        border-radius: 8px;
        background-position: right 6px center;
        padding-right: 20px;
      }

      .filter-status-banner {
        padding: 6px 12px;
        font-size: 0.72rem;
      }

      #store-list {
        padding: 8px 10px;
        gap: 8px;
        padding-bottom: 80px; /* space for bottom nav */
      }

      /* --- STORE CARDS: Tap-friendly --- */
      .store-card {
        padding: 12px;
        border-radius: 12px;
        gap: 5px;
      }
      .store-name {
        font-size: 0.88rem;
      }
      .store-meta {
        font-size: 0.72rem;
        flex-direction: column;
        gap: 3px;
      }
      .store-addr {
        font-size: 0.72rem;
      }

      /* Accordion body inside cards */
      .store-accordion-body {
        max-height: 260px;
        padding: 8px 10px;
      }
      .store-accordion-toggle,
      .store-hist-btn {
        padding: 6px 12px;
        min-height: 36px;
        font-size: 0.72rem;
      }

      /* --- CALENDAR VIEW: Mobile friendly --- */
      #view-calendar-mode {
        padding-bottom: 72px; /* space for bottom nav */
      }
      #calendar-dedicated-header {
        padding: 14px 14px 12px 14px;
        position: sticky;
        top: 0;
      }
      .cal-header-row-1 {
        gap: 10px;
        margin-bottom: 10px;
      }
      .cal-header-title-group h2 {
        font-size: 1.05rem;
        gap: 6px;
      }
      .cal-header-title-group p {
        font-size: 0.75rem;
        display: none;
      }
      .cal-header-actions-group {
        gap: 6px;
      }
      .cal-stat-pill {
        font-size: 0.7rem;
        padding: 4px 10px;
      }
      .cal-btn-toggle-expired {
        font-size: 0.72rem;
        padding: 6px 12px;
      }
      .cal-filter-toolbar {
        gap: 8px;
        padding-top: 10px;
      }
      .cal-search-box-wrap {
        min-width: unset;
        max-width: unset;
        width: 100%;
      }
      .cal-search-box-wrap input {
        font-size: 16px; /* prevents iOS zoom */
      }
      .cal-chip-group {
        overflow-x: auto;
        flex-wrap: nowrap;
        -webkit-overflow-scrolling: touch;
        padding-bottom: 4px;
      }
      .cal-chip {
        flex-shrink: 0;
      }
      #calendar-grid-container {
        padding: 14px 12px 80px 12px;
      }
      #calendar-cards-grid,
      #calendar-expired-grid {
        grid-template-columns: 1fr;
        gap: 12px;
      }
      .cal-card {
        padding: 14px;
      }

      /* --- MODALS: Full-width mobile --- */
      .modal-overlay {
        align-items: flex-end;
        padding: 0;
      }
      .modal-content {
        width: 100% !important;
        max-width: 100% !important;
        max-height: 92vh;
        border-radius: 18px 18px 0 0;
        animation: modalSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      }
      @keyframes modalSlideUp {
        from { transform: translateY(100%); opacity: 0.5; }
        to { transform: translateY(0); opacity: 1; }
      }
      .modal-header {
        padding: 14px 16px;
        border-radius: 18px 18px 0 0;
        position: relative;
      }
      /* Drag handle indicator on modals */
      .modal-header::before {
        content: '';
        position: absolute;
        top: 6px;
        left: 50%;
        transform: translateX(-50%);
        width: 40px;
        height: 4px;
        background: rgba(255,255,255,0.3);
        border-radius: 2px;
      }
      .modal-header h3 {
        font-size: 0.95rem;
      }
      .modal-close-btn {
        width: 36px;
        height: 36px;
        font-size: 1.1rem;
      }
      .modal-body {
        padding: 16px;
        max-height: 75vh;
        -webkit-overflow-scrolling: touch;
        overscroll-behavior: contain;
        padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
      }

      /* Settings tabs */
      .settings-tab-bar {
        padding: 4px 12px 0 12px;
      }
      .settings-tab-btn {
        padding: 10px 8px;
        font-size: 0.78rem;
      }
      .setting-checkbox-row {
        padding: 12px;
        min-height: 48px;
      }
      .time-radio-row {
        padding: 10px;
        min-height: 44px;
      }
      .modal-quick-actions {
        gap: 6px;
      }
      .btn-preset {
        min-width: 100px;
        padding: 10px 8px;
        font-size: 0.76rem;
      }

      /* History modal */
      .hist-timeline {
        padding-left: 14px;
      }
      .hist-item {
        padding: 10px 12px;
      }

      /* --- TOAST NOTIFICATIONS: Mobile width --- */
      #toast-container {
        top: 56px;
        right: 8px;
        left: 8px;
      }
      .toast {
        width: 100%;
        max-width: 100%;
        padding: 12px;
        border-radius: 10px;
      }
      .toast-header {
        font-size: 0.88rem;
      }
      .toast-body {
        font-size: 0.82rem;
      }

      /* --- MAP POPUPS: Wider on mobile --- */
      .leaflet-popup-content-wrapper {
        max-width: 300px !important;
        border-radius: 12px !important;
      }
      .leaflet-popup-content {
        margin: 12px !important;
        font-size: 0.85rem;
      }

      /* --- MOBILE BOTTOM NAV BAR --- */
      #mobile-bottom-nav {
        display: flex;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60px;
        padding-bottom: env(safe-area-inset-bottom, 0px);
        background: #0f172a;
        border-top: 1px solid #1e293b;
        z-index: 3000;
        align-items: stretch;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.25);
      }
      .mobile-nav-btn {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 3px;
        background: none;
        border: none;
        color: #64748b;
        font-size: 0.65rem;
        font-weight: 700;
        cursor: pointer;
        transition: color 0.15s, background 0.15s;
        position: relative;
        padding: 6px 0;
        -webkit-tap-highlight-color: transparent;
      }
      .mobile-nav-btn .nav-btn-icon {
        font-size: 1.3rem;
        line-height: 1;
      }
      .mobile-nav-btn .nav-btn-label {
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.02em;
      }
      .mobile-nav-btn.active {
        color: #60a5fa;
      }
      .mobile-nav-btn.active::after {
        content: '';
        position: absolute;
        top: 0;
        left: 25%;
        right: 25%;
        height: 3px;
        background: #3b82f6;
        border-radius: 0 0 3px 3px;
      }
      .mobile-nav-btn .nav-btn-badge {
        position: absolute;
        top: 4px;
        right: 50%;
        transform: translateX(calc(50% + 12px));
        background: #16a34a;
        color: white;
        font-size: 0.58rem;
        font-weight: 800;
        padding: 1px 5px;
        border-radius: 8px;
        min-width: 16px;
        text-align: center;
        line-height: 1.3;
      }
      .mobile-nav-btn .nav-btn-badge.cal-badge-color {
        background: #f59e0b;
      }

      /* Space for bottom nav in all views */
      #app-container {
        padding-bottom: calc(60px + env(safe-area-inset-bottom, 0px));
      }

      /* Sidebar mobile swipe hint */
      .mobile-swipe-hint {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 6px;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        font-size: 0.7rem;
        color: #3b82f6;
        font-weight: 600;
        gap: 6px;
        border-bottom: 1px solid #bfdbfe;
      }
    }

    /* Extra small devices (≤ 380px) */
    @media (max-width: 380px) {
      #top-navbar {
        padding: 0 8px;
      }
      .brand-title {
        font-size: 0.85rem;
      }
      .stat-badge .num {
        font-size: 0.95rem;
      }
      .stat-badge .label {
        font-size: 0.58rem;
      }
      .store-name {
        font-size: 0.82rem;
      }
      .controls-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>

  <script type="module">
    import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js';
    import { initializeFirestore, doc, onSnapshot } from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js';

    window.FirebaseInit = { initializeApp, initializeFirestore, doc, onSnapshot };
  </script>
</head>
<body>
  <div id="toast-container"></div>

  <!-- 1. TOP GLOBAL APPLICATION NAVBAR -->
  <header id="top-navbar">
    <div class="navbar-left">
      <a href="/map" class="brand-logo" onclick="event.preventDefault(); navigateMenu('map');">
        <span class="brand-icon">⚡</span>
        <div class="brand-text">
          <span class="brand-title">BAWUI POKE APP</span>
          <span class="brand-sub">Real-Time Stock & Lottery Tracker</span>
        </div>
      </a>
      <div class="live-pill">
        <div class="live-dot"></div>
        <span>FIRESTORE PUSH</span>
      </div>
    </div>

    <!-- MAIN APPLICATION MENU (REAL LINKS SYNCED WITH URL) -->
    <nav class="navbar-menu" id="main-navbar-menu">
      <a href="/map" class="nav-menu-link active" id="menu-map-link" onclick="event.preventDefault(); navigateMenu('map');">
        <span class="nav-icon">🗺️</span>
        <span class="nav-text">Bản Đồ & Kho Thẻ</span>
        <span class="nav-badge stock-badge" id="menu-stock-count">0 Có hàng</span>
      </a>
      <a href="/calendar" class="nav-menu-link" id="menu-cal-link" onclick="event.preventDefault(); navigateMenu('calendar');">
        <span class="nav-icon">📅</span>
        <span class="nav-text">Lịch Bốc Thăm & Sự Kiện</span>
        <span class="nav-badge cal-badge" id="menu-cal-count">11 Đang mở</span>
      </a>
    </nav>

    <!-- RIGHT ACTION CONTROLS -->
    <div class="navbar-right">
      <button class="header-action-btn" id="btn-header-map" onclick="toggleMapSettingsModal()" title="Cài đặt những cửa hàng muốn nhìn thấy trên bản đồ">
        <span>⚙️ Cài đặt cửa hàng bản đồ</span>
      </button>
      <button class="header-action-btn" id="btn-header-notif" onclick="toggleNotifSettingsModal()" title="Cài đặt những thông báo bạn muốn nhận">
        <span id="sound-icon">🔔</span>
        <span id="sound-text">Cài đặt thông báo</span>
      </button>
      <button class="header-gps-btn" id="header-loc-btn" onclick="requestUserLocation(true)" title="Nhấn để định vị GPS">
        <span>📍</span>
        <span id="header-loc-summary">Đang định vị...</span>
      </button>
      <button class="header-action-btn" onclick="refreshAll()" title="Nạp lại dữ liệu">
        <span>🔄 Làm mới</span>
      </button>
    </div>
  </header>

  <!-- 2. MAIN APP CONTAINER -->
  <div id="app-container">

    <!-- VIEW 1: STORES LIST & MAP -->
    <div id="view-stores-mode" class="app-view active">
      <div id="sidebar">
        <div class="controls" style="padding: 10px 12px 6px 12px; border-bottom: 1px solid #f1f5f9;">
          <!-- ROW 1: SEARCH INPUT & CHAIN SELECT (EQUAL 50/50 SPLIT) -->
          <div class="controls-grid" style="margin-bottom: 6px;">
            <div class="control-box">
              <input type="text" id="search-input" class="search-box" placeholder="🔍 Tìm ga, tiệm..." oninput="handleSearchInput(this.value)" style="height:34px; padding: 0 10px; font-size:0.78rem;" />
            </div>
            <div class="control-box">
              <select id="feed-chain-select" class="control-dropdown" onchange="setFeedChain(this.value)" title="Lọc theo chuỗi cửa hàng" style="height:34px; font-size:0.78rem;">
                <option value="" selected>🏢 Tất cả chuỗi</option>
                <option value="seven">🏪 7-Eleven</option>
                <option value="lawson">🏪 Lawson</option>
                <option value="familymart">🏪 FamilyMart</option>
                <option value="ministop">🏪 Ministop</option>
                <option value="specialty">🃏 Shop Pokémon</option>
              </select>
            </div>
          </div>

          <!-- ROW 2: STATUS & FRESHNESS DROPDOWNS (EQUAL 50/50 SPLIT) -->
          <div class="controls-grid">
            <div class="control-box">
              <select id="poketan-status-select" class="control-dropdown" onchange="setPoketanStatusFilter(this.value)" title="Lọc theo trạng thái báo cáo" style="height:34px; font-size:0.78rem; font-weight:700;">
                <option value="i" selected>🟢 在庫あり (Có hàng)</option>
                <option value="all">📋 すべて (Tất cả)</option>
                <option value="o">🔴 在庫なし (Hết hàng)</option>
                <option value="n">⚪ 不明・扱無 (Chưa rõ)</option>
              </select>
            </div>
            <div class="control-box">
              <select id="feed-freshness-select" class="control-dropdown" onchange="setFeedFreshness(this.value)" title="Lọc tin báo theo thời gian" style="height:34px; font-size:0.78rem;">
                <option value="24" selected>📅 24 giờ qua</option>
                <option value="1">⚡ Mới (&lt;1h)</option>
                <option value="3">⏱ Trong 3 giờ</option>
                <option value="6">⏱ Trong 6 giờ</option>
                <option value="12">📅 Trong 12 giờ</option>
                <option value="9999">⏳ Mọi lúc</option>
              </select>
            </div>
          </div>
        </div>

        <!-- POKETAN HEADER ROW: MINNA NO SAISHIN NO HOKOKU & SORT -->
        <div class="poketan-header-row" style="padding: 8px 14px 4px 14px;">
          <div>
            <div class="poketan-header-title">みんなの最新の報告 (Báo cáo mới nhất)</div>
            <div style="font-size:0.68rem; color:#94a3b8;" id="poketan-sub-info">大阪府 4,050店舗から探せます</div>
          </div>
          <button class="poketan-sort-btn" id="btn-poketan-sort" onclick="togglePoketanSort()" title="Đổi cách sắp xếp">
            <span id="poketan-sort-icon">⏱</span>
            <span id="poketan-sort-label">更新順</span>
          </button>
        </div>
        
        <div id="store-list" style="padding: 4px 14px;">
          <div style="text-align: center; color: #94a3b8; padding: 25px;">Đang tải dữ liệu thời gian thực Firestore...</div>
        </div>
      </div>

      <!-- Edge toggle tab button (always accessible) -->
      <button class="sidebar-collapse-trigger" id="sidebar-toggle-edge" onclick="toggleDesktopSidebar()" title="Ẩn / Hiện thanh danh sách">
        ◀
      </button>

      <div id="map">
        <div class="map-controls-box">
          <button class="floating-btn" onclick="requestUserLocation(true)" title="Định vị vị trí GPS hiện tại của tôi">
            <span>📍 Vị trí của tôi</span>
          </button>
        </div>
      </div>
    </div>

    <!-- VIEW 2: DEDICATED CALENDAR & LOTTERIES VIEW -->
    <div id="view-calendar-mode" class="app-view">
      
      <!-- DEDICATED HEADER FOR CALENDAR -->
      <div id="calendar-dedicated-header">
        <div class="cal-header-row-1">
          <div class="cal-header-title-group">
            <h2>📅 Lịch Bốc Thăm & Đặt Trước Thẻ Pokémon</h2>
            <p>Đồng bộ dữ liệu trực tiếp từ Quản trị viên PokéTan • Tự động cảnh báo tức thì khi có bài đăng đợt mới</p>
          </div>
          <div class="cal-header-actions-group">
            <div class="cal-stat-pill open" id="cal-stat-open">🟢 11 Đang nhận đơn</div>
            <div class="cal-stat-pill upcoming" id="cal-stat-upcoming">🟡 1 Sắp mở</div>
            <div class="cal-stat-pill expired" id="cal-stat-expired">⏳ 4 Đã quá hạn</div>
            <button class="cal-btn-toggle-expired" id="cal-header-toggle-expired" onclick="toggleExpiredSection()">
              👁️ Xem 4 sự kiện quá hạn
            </button>
          </div>
        </div>

        <!-- CALENDAR FILTER TOOLBAR -->
        <div class="cal-filter-toolbar">
          <div class="cal-search-box-wrap">
            <span class="search-icon">🔍</span>
            <input type="text" id="cal-search-input" placeholder="Tìm theo nhà bán lẻ (Amazon, Geo, Tsutaya, Toys'R'Us, Yamada...)" oninput="handleCalSearch(this.value)" />
          </div>
          
          <div class="cal-chip-group" id="cal-type-chips">
            <button class="cal-chip active" onclick="setCalTypeFilter('')">Tất cả hình thức</button>
            <button class="cal-chip" onclick="setCalTypeFilter('lottery')">🎲 Bốc thăm quyền mua (Lottery)</button>
            <button class="cal-chip" onclick="setCalTypeFilter('invite')">✉️ Thư mời mua (Invite)</button>
            <button class="cal-chip" onclick="setCalTypeFilter('release')">🎉 Phát hành chính thức (Release)</button>
          </div>

          <div class="cal-chip-group" id="cal-status-chips">
            <button class="cal-chip active" id="chip-status-active" onclick="setCalStatusFilter('active')">🟢 Đang mở & Sắp mở</button>
            <button class="cal-chip" id="chip-status-all" onclick="setCalStatusFilter('all')">📋 Xem tất cả</button>
          </div>
        </div>
      </div>

      <!-- CALENDAR CARDS GRID CONTAINER -->
      <div id="calendar-grid-container">
        <div id="calendar-cards-grid">
          <div style="text-align: center; color: #94a3b8; padding: 40px; grid-column: 1 / -1;">Đang tải lịch bốc thăm và đặt trước...</div>
        </div>

        <!-- EXPIRED EVENTS SEPARATED AT BOTTOM -->
        <div id="calendar-expired-wrapper" style="display: none;">
          <div class="expired-divider">
            <div class="expired-divider-line"></div>
            <span class="expired-divider-label" id="expired-divider-label">── CÁC ĐỢT ĐÃ HẾT HẠN ĐĂNG KÝ (4) ──</span>
            <div class="expired-divider-line"></div>
          </div>
          <div id="calendar-expired-grid"></div>
        </div>
      </div>

    </div>

  </div>

  <!-- 4.1. MAP DISPLAY SETTINGS MODAL (CÀI ĐẶT BẢN ĐỒ TÁCH BIỆT HOÀN TOÀN) -->
  <div id="map-settings-modal" class="modal-overlay" style="display: none;" onclick="if(event.target === this) toggleMapSettingsModal();">
    <div class="modal-content">
      <div class="modal-header">
        <div>
          <h3 style="font-size:1.05rem;display:flex;align-items:center;gap:8px;">⚙️ Cài Đặt Cửa Hàng Bản Đồ</h3>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:2px;">Tùy chọn hiển thị cửa hàng trên bản đồ & danh sách (Hiện tất cả 4,050 điểm / Chỉ có hàng / Hết hàng / Chuỗi)</div>
        </div>
        <button class="modal-close-btn" onclick="toggleMapSettingsModal()">✕</button>
      </div>

      <div class="modal-body">
        <!-- SECTION 1: CHẾ ĐỘ HIỂN THỊ GHIM BẢN ĐỒ -->
        <div class="setting-group">
          <label class="setting-group-title">📍 CHẾ ĐỘ GHIM CỬA HÀNG TRÊN BẢN ĐỒ</label>
          <div class="time-radio-group">
            <label class="time-radio-row">
              <input type="radio" name="map-display-mode" value="all" id="map-mode-all" onchange="setMapMode('all')" checked />
              <div>
                <b style="color:#0284c7;">🏢 Hiện tất cả 4,050 cửa hàng trên bản đồ Osaka (Mặc định)</b>
                <div class="time-desc">Hiển thị trọn vẹn toàn bộ cửa hàng tiện lợi & card shop. Cửa hàng có hàng phát sáng xanh lá 🟢 to nổi bật, hết hàng màu đỏ 🔴.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="map-display-mode" value="only_in" id="map-mode-only_in" onchange="setMapMode('only_in')" />
              <div>
                <b style="color:#16a34a;">🟢 Chỉ ghim các cửa hàng ĐANG CÓ HÀNG</b>
                <div class="time-desc">Ẩn toàn bộ các điểm chưa có báo cáo để bản đồ thoáng gọn, chỉ tập trung vào các điểm có hàng.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="map-display-mode" value="with_out" id="map-mode-with_out" onchange="setMapMode('with_out')" />
              <div>
                <b style="color:#dc2626;">🟢🔴 Ghim cửa hàng CÓ HÀNG & HẾT HÀNG</b>
                <div class="time-desc">Chỉ ghim các điểm vừa có báo cáo biến động mới (có hàng hoặc hết hàng).</div>
              </div>
            </label>
          </div>
        </div>

        <!-- SECTION 2: LỌC CHUỖI TRÊN BẢN ĐỒ -->
        <div class="setting-group">
          <label class="setting-group-title">🏪 LỌC CHUỖI CỬA HÀNG TRÊN BẢN ĐỒ</label>
          <div style="font-size:0.75rem;color:#64748b;margin-bottom:6px;">Chỉ ghim những chuỗi cửa hàng bạn muốn xem trên bản đồ:</div>
          <select id="map-modal-chain-select" class="control-dropdown" onchange="setMapChain(this.value)" style="height:40px;">
            <option value="" selected>🏢 Tất cả các chuỗi cửa hàng (Mặc định)</option>
            <option value="seven">🏪 7-Eleven</option>
            <option value="lawson">🏪 Lawson</option>
            <option value="familymart">🏪 FamilyMart</option>
            <option value="ministop">🏪 Ministop</option>
            <option value="specialty">🃏 Cửa hàng thẻ Pokémon</option>
          </select>
        </div>

        <!-- SECTION 3: NGUỒN DỮ LIỆU LỊCH SỬ -->
        <div class="setting-group">
          <label class="setting-group-title">⏳ NGUỒN DỮ LIỆU TOÀN DIỆN</label>
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="check-include-cold" checked onchange="toggleMapCold(this.checked)" />
              <div>
                <b>Tải toàn bộ 4,050 điểm từ kho dữ liệu Osaka</b>
                <div class="time-desc">Đảm bảo hiển thị đầy đủ mọi cửa hàng tiện lợi và card shop tại Osaka.</div>
              </div>
            </div>
          </label>
        </div>

        <!-- PRESET BUTTONS -->
        <div class="modal-quick-actions">
          <button class="btn-preset active" id="btn-map-preset-all" onclick="setMapMode('all')">
            🏢 Hiện tất cả 4,050 điểm
          </button>
          <button class="btn-preset" id="btn-map-preset-in" onclick="setMapMode('only_in')">
            🟢 Chỉ ghim điểm có hàng
          </button>
          <button class="btn-preset" id="btn-map-preset-both" onclick="setMapMode('with_out')">
            🟢🔴 Có hàng & Hết hàng
          </button>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:10px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:8px;">
          <span style="font-size:0.75rem;color:#16a34a;display:flex;align-items:center;gap:4px;" id="map-save-indicator">
            💾 Đã lưu cấu hình bản đồ vào <b>settings.json</b>
          </span>
          <button type="button" onclick="resetMapSettings()" style="background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;padding:5px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;cursor:pointer;">
            🔄 Khôi phục mặc định bản đồ
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 4.2. NOTIFICATION SETTINGS MODAL (CÀI ĐẶT THÔNG BÁO TÁCH BIỆT HOÀN TOÀN) -->
  <div id="notif-settings-modal" class="modal-overlay" style="display: none;" onclick="if(event.target === this) toggleNotifSettingsModal();">
    <div class="modal-content" style="max-width: 580px;">
      <div class="modal-header">
        <div>
          <h3 style="font-size:1.05rem;display:flex;align-items:center;gap:8px;">🔔 Cài Đặt Thông Báo Có Hàng & Cảnh Báo</h3>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:2px;">Tùy chọn chuông, thông báo nổi & danh sách Báo Có Hàng (Tách biệt hoàn toàn khỏi bản đồ)</div>
        </div>
        <button class="modal-close-btn" onclick="toggleNotifSettingsModal()">✕</button>
      </div>

      <div class="modal-body">
        <!-- SECTION 1: KÊNH THÔNG BÁO -->
        <div class="setting-group">
          <label class="setting-group-title">🔊 KÊNH THÔNG BÁO (ÂM THANH & TRÌNH DUYỆT)</label>
          
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-sound" checked onchange="updateNotifSetting('soundEnabled', this.checked)" />
              <div>
                <b>🔔 Chuông âm thanh cảnh báo</b>
                <div class="time-desc">Phát chuông báo khi phát hiện có biến động hoặc sự kiện mới.</div>
              </div>
            </div>
            <button type="button" class="btn-test-action" onclick="testNotifSound()">🔊 Nghe thử</button>
          </label>

          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-push" checked onchange="updateNotifSetting('pushEnabled', this.checked)" />
              <div>
                <b>🌐 Thông báo nổi máy tính (Web Push)</b>
                <div class="time-desc">Hiện thông báo góc màn hình máy tính (ngay cả khi thu nhỏ trình duyệt).</div>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
              <span id="notif-perm-status" class="notif-badge-state notif-badge-default">Kiểm tra...</span>
              <button type="button" class="btn-test-action" id="btn-request-perm" onclick="requestPushPermission()">Cấp quyền</button>
            </div>
          </label>
        </div>

        <!-- SECTION 2: CHẾ ĐỘ THÔNG BÁO THEO TÌNH TRẠNG -->
        <div class="setting-group">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <label class="setting-group-title" style="margin-bottom:0;">🎯 TÌNH TRẠNG CẦN NHẬN THÔNG BÁO & HIỆN TRONG BÁO CÓ HÀNG</label>
            <div style="display:flex;gap:6px;">
              <button type="button" class="btn-preset active" id="notif-preset-only-in" onclick="applyNotifPreset('only_in')" style="padding:2px 8px;font-size:0.75rem;font-weight:700;">
                🟢 Chỉ báo Có hàng
              </button>
              <button type="button" class="btn-preset" id="notif-preset-all" onclick="applyNotifPreset('all')" style="padding:2px 8px;font-size:0.75rem;font-weight:700;">
                🏢 Báo Tất cả
              </button>
            </div>
          </div>

          <!-- OPTION 1: CÓ HÀNG -->
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-instock" checked onchange="updateNotifSetting('notifyInStock', this.checked)" />
              <div>
                <b style="color:#16a34a;">🟢 Thông báo khi CÓ HÀNG (In Stock) [Mặc định]</b>
                <div class="time-desc">Báo chuông & hiển thị trong danh sách khi có cửa hàng vừa có thẻ Pokémon.</div>
              </div>
            </div>
            <span class="status-count-pill in">Khuyên dùng</span>
          </label>

          <!-- OPTION 2: HẾT HÀNG -->
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-outofstock" onchange="updateNotifSetting('notifyOutOfStock', this.checked)" />
              <div>
                <b style="color:#dc2626;">🔴 Thông báo khi HẾT HÀNG (Out of Stock)</b>
                <div class="time-desc">Nhận thông báo khi cửa hàng đổi sang hết hàng (để tránh đi nhầm).</div>
              </div>
            </div>
            <span class="status-count-pill out">Tùy chọn</span>
          </label>

          <!-- OPTION 3: KHÔNG CÓ HÀNG / KHÔNG BÁN THẺ -->
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-nothandled" onchange="updateNotifSetting('notifyNotHandled', this.checked)" />
              <div>
                <b style="color:#64748b;">⚪ Thông báo khi KHÔNG CÓ HÀNG / KHÔNG BÁN THẺ (Not Handled)</b>
                <div class="time-desc">Nhận thông báo khi cửa hàng báo không kinh doanh hoặc không có thẻ.</div>
              </div>
            </div>
            <span class="status-count-pill none">Tùy chọn</span>
          </label>

          <!-- OPTION 4: LỊCH BỐC THĂM / SỰ KIỆN MỚI -->
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-lottery" checked onchange="updateNotifSetting('notifyLottery', this.checked)" />
              <div>
                <b style="color:#2563eb;">📅 Thông báo LỊCH BỐC THĂM MỚI từ Quản trị viên</b>
                <div class="time-desc">Báo tức thì khi Poketan đăng bài mở đợt bốc thăm mới (Amazon, Geo, Pokemon Center...).</div>
              </div>
            </div>
            <span class="status-count-pill" style="background:#dbeafe;color:#1e40af;">Admin Push</span>
          </label>
        </div>

        <!-- SECTION 3: ĐỘ MỚI BÁO CÁO CÓ HÀNG (LỌC THỜI GIAN - TRÁNH TIN CŨ ĐÃ HẾT HÀNG) -->
        <div class="setting-group">
          <label class="setting-group-title">⏰ ĐỘ MỚI TIN BÁO CÓ HÀNG (TRÁNH TIN LÂU ĐÃ HẾT HÀNG)</label>
          <div class="time-radio-group">
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="1" id="notif-age-1" onchange="setNotifMaxAge(1)" />
              <div>
                <b style="color:#16a34a;">⚡ Siêu mới: Trong vòng 1 giờ</b>
                <div class="time-desc">Khả năng còn hàng cao nhất! Chỉ thông báo & hiện tin vừa đăng tức thì.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="3" id="notif-age-3" onchange="setNotifMaxAge(3)" />
              <div>
                <b style="color:#2563eb;">⏱ Trong vòng 3 giờ</b>
                <div class="time-desc">Khuyên dùng khi bắt đầu đi săn thẻ để tránh đến nơi bị hết hàng.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="6" id="notif-age-6" onchange="setNotifMaxAge(6)" />
              <div>
                <b style="color:#0284c7;">⏱ Trong vòng 6 giờ</b>
                <div class="time-desc">Báo cáo trong nửa ngày (buổi sáng hoặc buổi chiều).</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="12" id="notif-age-12" onchange="setNotifMaxAge(12)" />
              <div>
                <b>📅 Trong vòng 12 giờ</b>
                <div class="time-desc">Tất cả báo cáo trong ngày hôm nay.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="24" id="notif-age-24" checked onchange="setNotifMaxAge(24)" />
              <div>
                <b>📅 Trong vòng 24 giờ (Mặc định)</b>
                <div class="time-desc">Bao gồm tất cả báo cáo trong ngày qua.</div>
              </div>
            </label>
            <label class="time-radio-row">
              <input type="radio" name="notif-max-age" value="0" id="notif-age-0" onchange="setNotifMaxAge(0)" />
              <div>
                <b style="color:#64748b;">⏳ Tất cả thời gian (Bao gồm tin cũ >24h)</b>
                <div class="time-desc">Lưu ý: Tin báo có hàng từ nhiều ngày trước thường đã hết hàng.</div>
              </div>
            </label>
          </div>
        </div>

        <!-- SECTION 4: LỌC THÔNG BÁO THEO CHUỖI -->
        <div class="setting-group">
          <label class="setting-group-title">🏪 LỌC THÔNG BÁO THEO CHUỖI CỬA HÀNG</label>
          <div style="font-size:0.75rem;color:#64748b;margin-bottom:4px;">
            Chỉ nhận thông báo từ chuỗi bạn quan tâm (Bản đồ vẫn hiển thị theo cài đặt bản đồ riêng):
          </div>
          <select id="notif-chain-select" class="control-dropdown" onchange="updateNotifSetting('notifyChain', this.value)" style="height:40px;">
            <option value="" selected>🏢 Nhận thông báo TẤT CẢ các chuỗi cửa hàng (Mặc định)</option>
            <option value="seven">🏪 Chỉ nhận thông báo từ 7-Eleven</option>
            <option value="lawson">🏪 Chỉ nhận thông báo từ Lawson</option>
            <option value="familymart">🏪 Chỉ nhận thông báo từ FamilyMart</option>
            <option value="ministop">🏪 Chỉ nhận thông báo từ Ministop</option>
            <option value="specialty">🃏 Chỉ nhận thông báo từ Cửa hàng thẻ Pokémon</option>
          </select>
        </div>

        <!-- SECTION 5: ĐỘ TIN CẬY -->
        <div class="setting-group">
          <label class="setting-group-title">📍 ĐỘ TIN CẬY & XÁC THỰC VỊ TRÍ</label>
          <label class="setting-checkbox-row">
            <div class="setting-checkbox-left">
              <input type="checkbox" id="notif-check-onsite" onchange="updateNotifSetting('onlyOnsiteGps', this.checked)" />
              <div>
                <b>📍 Chỉ thông báo khi có người xác nhận tại quán (GPS onsite)</b>
                <div class="time-desc">Bỏ qua tin báo từ xa, chỉ báo khi người đăng đứng trực tiếp tại cửa hàng (tránh tin báo ảo).</div>
              </div>
            </div>
          </label>
        </div>

        <!-- SECTION 6: KẾT NỐI DISCORD & TELEGRAM WEBHOOK -->
        <div class="setting-group" style="background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 14px;">
          <label class="setting-group-title" style="color: #0f172a; display: flex; align-items: center; justify-content: space-between;">
            <span>🤖 THÔNG BÁO TỰ ĐỘNG VỀ DISCORD &amp; TELEGRAM</span>
            <span style="font-size: 0.72rem; color: #16a34a; font-weight: 700; background: #dcfce7; padding: 2px 8px; border-radius: 12px;">Mới</span>
          </label>
          <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 12px;">
            Nhận tin báo tức thì khi có cửa hàng vừa có hàng (kèm tên Pack, địa chỉ và link dẫn đường Google Maps).
          </div>

          <!-- DISCORD CONFIG -->
          <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <label style="font-size: 0.82rem; font-weight: 700; color: #5865F2; display: flex; align-items: center; gap: 6px;">
                <input type="checkbox" id="notif-check-discord" onchange="updateNotifSetting('discordEnabled', this.checked)" />
                <span>🎮 Bật gửi về kênh Discord</span>
              </label>
              <button type="button" class="btn-test-action" onclick="testWebhookNotification('discord')" style="font-size:0.72rem; padding: 3px 8px;">
                📨 Test Discord
              </button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <input type="text" id="notif-input-discord-url" class="search-box" placeholder="Dán Discord Webhook URL (https://discord.com/api/webhooks/...)" onchange="updateNotifSetting('discordWebhookUrl', this.value.trim())" style="height:32px; font-size:0.75rem;" />
              <div style="font-size: 0.68rem; color: #94a3b8;">* Cách lấy: Vào Discord Server ➔ Cài đặt kênh ➔ Integrations ➔ Webhooks ➔ Tạo &amp; Copy URL</div>
            </div>
          </div>

          <!-- TELEGRAM CONFIG -->
          <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <label style="font-size: 0.82rem; font-weight: 700; color: #0284c7; display: flex; align-items: center; gap: 6px;">
                <input type="checkbox" id="notif-check-telegram" onchange="updateNotifSetting('telegramEnabled', this.checked)" />
                <span>✈️ Bật gửi về Telegram</span>
              </label>
              <button type="button" class="btn-test-action" onclick="testWebhookNotification('telegram')" style="font-size:0.72rem; padding: 3px 8px;">
                📨 Test Telegram
              </button>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 4px;">
              <input type="text" id="notif-input-tg-token" class="search-box" placeholder="Bot Token (vd: 123456:ABC-DEF...)" onchange="updateNotifSetting('telegramBotToken', this.value.trim())" style="height:32px; font-size:0.75rem;" />
              <input type="text" id="notif-input-tg-chatid" class="search-box" placeholder="Chat ID (vd: 987654321 hoặc @tenkenh)" onchange="updateNotifSetting('telegramChatId', this.value.trim())" style="height:32px; font-size:0.75rem;" />
            </div>
            <div style="font-size: 0.68rem; color: #94a3b8;">* Tạo Bot qua @BotFather để nhận Token, lấy Chat ID cá nhân/nhóm qua @userinfobot</div>
          </div>
        </div>

        <!-- SECTION 7: THỬ NGHIỆM -->
        <div style="display:flex;justify-content:space-between;align-items:center;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;flex-wrap:wrap;gap:8px;">
          <div>
            <div style="font-weight:700;font-size:0.85rem;color:#0f172a;">Kiểm tra chuông & thông báo hoạt động</div>
            <div style="font-size:0.75rem;color:#64748b;">Gửi 1 thông báo mẫu kèm chuông &amp; đẩy thử về Webhook để kiểm tra</div>
          </div>
          <button type="button" class="btn-test-action" onclick="testNotifPopup()" style="background:#2563eb;color:white;border-color:#2563eb;">
            💬 Gửi thông báo mẫu
          </button>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:10px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:8px;">
          <span style="font-size:0.75rem;color:#16a34a;display:flex;align-items:center;gap:4px;" id="notif-save-indicator">
            💾 Đã lưu cấu hình thông báo vào <b>settings.json</b>
          </span>
          <button type="button" onclick="resetNotifSettings()" style="background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;padding:5px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;cursor:pointer;">
            🔄 Khôi phục mặc định thông báo
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- STORE REPORT HISTORY MODAL -->
  <div id="store-history-modal" class="modal-overlay" style="display:none;" onclick="if(event.target===this) closeStoreHistoryModal()">
    <div class="modal-content" style="max-width: 620px;">
      <div class="modal-header">
        <div style="display:flex;align-items:center;gap:10px;min-width:0;">
          <span style="font-size:1.3rem;">📜</span>
          <div style="min-width:0;">
            <h3 id="hist-modal-title" style="font-size:1.02rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Lịch Sử Báo Cáo Cửa Hàng</h3>
            <div id="hist-modal-subtitle" style="font-size:0.75rem;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Đang tải thông tin cửa hàng...</div>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeStoreHistoryModal()" title="Đóng">✕</button>
      </div>

      <div class="modal-body" id="hist-modal-body" style="padding:18px 20px;max-height:75vh;overflow-y:auto;">
        <div style="text-align:center;padding:36px;color:#64748b;">
          <div style="font-size:1.8rem;animation:pulse 1s infinite;">⏳</div>
          <div style="font-weight:700;margin-top:8px;">Đang tải lịch sử báo cáo...</div>
        </div>
      </div>

      <div style="background:#f8fafc;padding:12px 20px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <span style="font-size:0.75rem;color:#64748b;" id="hist-modal-footer-info">Báo cáo cộng đồng từ người dùng Osaka</span>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <a id="hist-modal-dir-btn" href="#" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:6px 12px;background:#2563eb;color:white;text-decoration:none;border-radius:6px;font-size:0.78rem;font-weight:700;">🗺️ Google Maps ↗</a>
          <button type="button" onclick="viewStoreOnMap()" style="display:inline-flex;align-items:center;gap:4px;padding:6px 12px;background:#0284c7;color:white;border:none;border-radius:6px;font-size:0.78rem;font-weight:700;cursor:pointer;">📍 Xem trên bản đồ</button>
          <button type="button" onclick="closeStoreHistoryModal()" style="padding:6px 14px;background:#0f172a;color:white;border:none;border-radius:6px;font-size:0.78rem;font-weight:700;cursor:pointer;">✕ Đóng</button>
        </div>
      </div>
    </div>
  </div>

  <!-- MOBILE BOTTOM NAVIGATION BAR -->
  <nav id="mobile-bottom-nav">
    <button class="mobile-nav-btn active" id="mob-nav-map" onclick="mobileNavTo('map')">
      <span class="nav-btn-icon">🗺️</span>
      <span class="nav-btn-label">Bản đồ</span>
    </button>
    <button class="mobile-nav-btn" id="mob-nav-list" onclick="mobileNavTo('list')">
      <span class="nav-btn-icon">📋</span>
      <span class="nav-btn-label">Danh sách</span>
      <span class="nav-btn-badge" id="mob-badge-stock">0</span>
    </button>
    <button class="mobile-nav-btn" id="mob-nav-cal" onclick="mobileNavTo('calendar')">
      <span class="nav-btn-icon">📅</span>
      <span class="nav-btn-label">Lịch</span>
      <span class="nav-btn-badge cal-badge-color" id="mob-badge-cal">0</span>
    </button>
    <button class="mobile-nav-btn" id="mob-nav-settings" onclick="mobileNavTo('settings')">
      <span class="nav-btn-icon">⚙️</span>
      <span class="nav-btn-label">Cài đặt</span>
    </button>
  </nav>

  <script>
    // 0. NOTIFICATION SETTINGS STATE (TÁCH BIỆT HOÀN TOÀN KHỎI BẢN ĐỒ)
    let notifSettings = {
      soundEnabled: true,
      pushEnabled: true,
      notifyInStock: true,
      notifyOutOfStock: false,
      notifyNotHandled: false,
      notifyLottery: true,
      notifyChain: '',
      onlyOnsiteGps: false,
      discordWebhookUrl: '',
      discordEnabled: false,
      telegramBotToken: '',
      telegramChatId: '',
      telegramEnabled: false
    };

    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then(() => syncNotifUI());
    }

    function syncNotifUI() {
      const soundCheck = document.getElementById('notif-check-sound');
      if (soundCheck) soundCheck.checked = notifSettings.soundEnabled;

      const pushCheck = document.getElementById('notif-check-push');
      if (pushCheck) pushCheck.checked = notifSettings.pushEnabled;

      const inCheck = document.getElementById('notif-check-instock');
      if (inCheck) inCheck.checked = notifSettings.notifyInStock;

      const outCheck = document.getElementById('notif-check-outofstock');
      if (outCheck) outCheck.checked = notifSettings.notifyOutOfStock;

      const notHandledCheck = document.getElementById('notif-check-nothandled');
      if (notHandledCheck) notHandledCheck.checked = notifSettings.notifyNotHandled;

      const allCheck = document.getElementById('notif-check-all');
      if (allCheck) {
        allCheck.checked = !!(notifSettings.notifyInStock && notifSettings.notifyOutOfStock && notifSettings.notifyNotHandled);
      }

      const presetOnlyIn = document.getElementById('notif-preset-only-in');
      const presetAll = document.getElementById('notif-preset-all');
      const isOnlyIn = notifSettings.notifyInStock && !notifSettings.notifyOutOfStock && !notifSettings.notifyNotHandled;
      const isAll = notifSettings.notifyInStock && notifSettings.notifyOutOfStock && notifSettings.notifyNotHandled;
      if (presetOnlyIn) presetOnlyIn.classList.toggle('active', isOnlyIn);
      if (presetAll) presetAll.classList.toggle('active', isAll);

      const lotCheck = document.getElementById('notif-check-lottery');
      if (lotCheck) lotCheck.checked = notifSettings.notifyLottery;

      const chainSelect = document.getElementById('notif-chain-select');
      if (chainSelect) chainSelect.value = notifSettings.notifyChain || '';

      const onsiteCheck = document.getElementById('notif-check-onsite');
      if (onsiteCheck) onsiteCheck.checked = notifSettings.onlyOnsiteGps;

      // Webhook Discord & Telegram UI sync
      const discCheck = document.getElementById('notif-check-discord');
      if (discCheck) discCheck.checked = !!notifSettings.discordEnabled;
      const discUrlInput = document.getElementById('notif-input-discord-url');
      if (discUrlInput && document.activeElement !== discUrlInput) discUrlInput.value = notifSettings.discordWebhookUrl || '';

      const tgCheck = document.getElementById('notif-check-telegram');
      if (tgCheck) tgCheck.checked = !!notifSettings.telegramEnabled;
      const tgTokenInput = document.getElementById('notif-input-tg-token');
      if (tgTokenInput && document.activeElement !== tgTokenInput) tgTokenInput.value = notifSettings.telegramBotToken || '';
      const tgChatIdInput = document.getElementById('notif-input-tg-chatid');
      if (tgChatIdInput && document.activeElement !== tgChatIdInput) tgChatIdInput.value = notifSettings.telegramChatId || '';

      // Sync max report age radio buttons in notif modal
      const ageRadios = document.querySelectorAll('input[name="notif-max-age"]');
      ageRadios.forEach(r => {
        r.checked = (parseFloat(r.value) === notifSettings.maxReportAgeHours);
      });

      if (typeof updateControlsForTab === 'function') {
        updateControlsForTab();
      }

      // Update header button sound icon & label
      const icon = document.getElementById('sound-icon');
      const text = document.getElementById('sound-text');
      if (icon && text) {
        if (notifSettings.soundEnabled) {
          icon.innerText = '🔔';
          text.innerText = 'Thông báo ⚙️';
        } else {
          icon.innerText = '🔕';
          text.innerText = 'Tắt chuông ⚙️';
        }
      }

      // Update browser push permission status badge
      const badge = document.getElementById('notif-perm-status');
      const reqBtn = document.getElementById('btn-request-perm');
      if (badge) {
        if (!("Notification" in window)) {
          badge.className = 'notif-badge-state notif-badge-denied';
          badge.innerText = 'Không hỗ trợ';
          if (reqBtn) reqBtn.style.display = 'none';
        } else if (Notification.permission === 'granted') {
          badge.className = 'notif-badge-state notif-badge-granted';
          badge.innerText = '✅ Đã cấp quyền';
          if (reqBtn) reqBtn.style.display = 'none';
        } else if (Notification.permission === 'denied') {
          badge.className = 'notif-badge-state notif-badge-denied';
          badge.innerText = '❌ Đã chặn';
          if (reqBtn) reqBtn.style.display = 'inline-flex';
        } else {
          badge.className = 'notif-badge-state notif-badge-default';
          badge.innerText = '⚠️ Chưa cấp quyền';
          if (reqBtn) reqBtn.style.display = 'inline-flex';
        }
      }
    }
    window.syncNotifUI = syncNotifUI;

    function applyNotifPreset(preset) {
      if (preset === 'only_in') {
        notifSettings.notifyInStock = true;
        notifSettings.notifyOutOfStock = false;
        notifSettings.notifyNotHandled = false;
      } else if (preset === 'all') {
        notifSettings.notifyInStock = true;
        notifSettings.notifyOutOfStock = true;
        notifSettings.notifyNotHandled = true;
      }
      syncNotifUI();
      saveSettings();
    }
    window.applyNotifPreset = applyNotifPreset;

    function toggleSelectAllNotif(checked) {
      notifSettings.notifyInStock = checked;
      notifSettings.notifyOutOfStock = checked;
      notifSettings.notifyNotHandled = checked;
      syncNotifUI();
      saveSettings();
    }
    window.toggleSelectAllNotif = toggleSelectAllNotif;

    function updateNotifStatusItem(key, checked) {
      notifSettings[key] = checked;
      syncNotifUI();
      saveSettings();
    }
    window.updateNotifStatusItem = updateNotifStatusItem;

    function updateNotifSetting(key, val) {
      notifSettings[key] = val;
      syncNotifUI();
      saveSettings();
    }
    window.updateNotifSetting = updateNotifSetting;

    function toggleSound() {
      updateNotifSetting('soundEnabled', !notifSettings.soundEnabled);
      if (notifSettings.soundEnabled) playChime(true);
    }
    window.toggleSound = toggleSound;

    function requestPushPermission() {
      if (!("Notification" in window)) {
        alert("Trình duyệt này không hỗ trợ Web Notification.");
        return;
      }
      Notification.requestPermission().then(() => {
        syncNotifUI();
      });
    }
    window.requestPushPermission = requestPushPermission;

    function playChime(force = false) {
      if (!force && !notifSettings.soundEnabled) return;
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        const now = ctx.currentTime;
        osc.frequency.setValueAtTime(1046.50, now);
        osc.frequency.setValueAtTime(1318.51, now + 0.12);
        osc.frequency.setValueAtTime(1567.98, now + 0.24);
        gain.gain.setValueAtTime(0.35, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.9);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.9);
      } catch (e) {}
    }
    window.playChime = playChime;

    function testNotifSound() {
      playChime(true);
    }
    window.testNotifSound = testNotifSound;

    async function triggerWebhooks(store, info, isTest = false) {
      if (!isTest && !notifSettings.discordEnabled && !notifSettings.telegramEnabled) return;
      try {
        await fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            store: {
              id: store.id,
              name: store.name,
              chain_label: store.chain_label || store.chain,
              address: store.address || '',
              lat: store.lat,
              lng: store.lng
            },
            info: {
              label: info.label,
              packs: info.packs || [],
              reported_at: info.reported_at,
              timeAgo: info.timeAgo,
              confirms: info.confirms || 0,
              onsite: !!info.onsite
            },
            is_test: isTest
          })
        });
      } catch (err) {
        console.warn("Failed to dispatch webhook:", err);
      }
    }
    window.triggerWebhooks = triggerWebhooks;

    async function testWebhookNotification(platform) {
      const demoStore = {
        id: 'test_store_webhook',
        name: '7-Eleven Ga Osaka (Tin Test Bot)',
        chain: 'seven',
        chain_label: '7-Eleven',
        address: '1-1 Umeda, Kita-ku, Osaka',
        lat: 34.7024,
        lng: 135.4959
      };
      const demoInfo = {
        code: 'i',
        label: 'Có hàng (In Stock)',
        packs: ['Terastal Festival ex', 'Battle Partners'],
        timeAgo: 'Vừa xong',
        reported_at: 'Hôm nay lúc ' + new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }),
        confirms: 5,
        onsite: true
      };

      if (platform === 'discord' && !notifSettings.discordWebhookUrl) {
        alert('⚠️ Vui lòng dán Discord Webhook URL vào ô trước khi bấm Test!');
        return;
      }
      if (platform === 'telegram' && (!notifSettings.telegramBotToken || !notifSettings.telegramChatId)) {
        alert('⚠️ Vui lòng nhập Bot Token và Chat ID của Telegram trước khi bấm Test!');
        return;
      }

      try {
        const resp = await fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            store: demoStore,
            info: demoInfo,
            is_test: true
          })
        });
        const res = await resp.json();
        if (platform === 'discord') {
          if (res.results && res.results.discord === 'ok') {
            alert('✅ Đã gửi tin nhắn mẫu đến Discord thành công! Hãy kiểm tra kênh Discord.');
          } else {
            alert('❌ Gửi Discord thất bại: ' + (res.results ? res.results.discord : 'Lỗi không xác định'));
          }
        } else if (platform === 'telegram') {
          if (res.results && res.results.telegram === 'ok') {
            alert('✅ Đã gửi tin nhắn mẫu đến Telegram thành công! Hãy kiểm tra Telegram.');
          } else {
            alert('❌ Gửi Telegram thất bại: ' + (res.results ? res.results.telegram : 'Lỗi không xác định'));
          }
        }
      } catch (e) {
        alert('❌ Lỗi kết nối máy chủ: ' + e.message);
      }
    }
    window.testWebhookNotification = testWebhookNotification;

    function testNotifPopup() {
      const demoStore = {
        id: 'test_store_1',
        name: '7-Eleven Ga Osaka (Thông Báo Mẫu)',
        chain: 'seven',
        chain_label: '7-Eleven',
        address: '1-1 Umeda, Kita-ku, Osaka',
        lat: 34.7024,
        lng: 135.4959
      };
      const demoInfo = {
        code: 'i',
        label: 'Có hàng (In Stock)',
        packs: ['Terastal Festival ex', 'Battle Partners'],
        timeAgo: 'Vừa xong',
        reported_at: 'Hôm nay lúc ' + new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }),
        confirms: 3,
        onsite: true
      };
      showToast(demoStore, demoInfo, true);
    }
    window.testNotifPopup = testNotifPopup;

    function resetNotifSettings() {
      if (!confirm('Khôi phục toàn bộ cài đặt thông báo về mặc định (Bật chuông, báo có hàng mới & lịch bốc thăm)?')) return;
      notifSettings = {
        soundEnabled: true,
        pushEnabled: true,
        notifyInStock: true,
        notifyOutOfStock: false,
        notifyNotHandled: false,
        notifyLottery: true,
        notifyChain: '',
        onlyOnsiteGps: false,
        discordWebhookUrl: '',
        discordEnabled: false,
        telegramBotToken: '',
        telegramChatId: '',
        telegramEnabled: false
      };
      syncNotifUI();
      saveSettings();
    }
    window.resetNotifSettings = resetNotifSettings;

    // 1. MAP INITIALIZATION
    const map = L.map('map').setView([34.6937, 135.5023], 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    let markersLayer = L.layerGroup().addTo(map);
    let userLocationLayer = L.layerGroup().addTo(map);
    let markerMap = {};
    let storesDict = {};
    let configData = {};
    
    // Status State
    let hotStatus = {};
    let coldStatus = {};
    let latestMergedStatus = {};
    let includeCold = true;
    let coldLoaded = false;
    let previousInStockIds = null;
    let previousRawStatus = null;
    let currentFocusedStoreId = null;
    
    // Store History Cache & Open Accordions State
    const storeHistoryCache = {};
    const openAccordionStoreIds = new Set();
    
    // 1.1 CẤU HÌNH BẢN ĐỒ (CHỈ ĐIỀU KHIỂN GHIM TRÊN BẢN ĐỒ)
    let mapDisplay = {
      mode: 'all',          // 'all' = 4,050 cửa hàng, 'only_in' = chỉ ghim có hàng, 'with_out' = ghim có hàng + hết hàng
      chain: '',            // Lọc chuỗi trên bản đồ: '' = tất cả
      includeCold: true     // Nạp dữ liệu lịch sử (>24h)
    };

    // 1.2 CẤU HÌNH DANH SÁCH SIDEBAR (TÁCH BIỆT HOÀN TOÀN KHỎI BẢN ĐỒ)
    let sidebarTab = 'feed'; // 'feed' (Báo Có Hàng) | 'all' (Tra Cứu Toàn Bộ)

    // Bộ lọc riêng cho Tab 1: Báo Có Hàng (Feed)
    let feedFreshnessHours = 24.0;
    let feedChain = '';
    let feedSortMode = 'newest'; // 'newest' | 'nearest'
    let feedQuery = '';

    // Bộ lọc riêng cho Tab 2: Tra Cứu Toàn Bộ 4,050 Điểm (All)
    let allStatusFilter = 'all'; // 'all' | 'i' | 'o' | 'n' | 'u'
    let allChain = '';
    let allSortMode = 'newest';
    let allQuery = '';

    let visibleLimit = 150;
    let calendarEvents = [];
    let userLat = null;
    let userLng = null;
    let userAccuracy = null;
    let isMockLocation = false;

    // Backward-compat aliases
    let statusFilter = { 'i': true, 'o': true, 'n': true, 'u': true };
    let maxReportAgeHours = 24.0;
    let currentChain = '';

    // 2. CHUYỂN ĐỔI TAB SIDEBAR: BÁO CÓ HÀNG vs TRA CỨU TOÀN BỘ
    function setSidebarTab(tab, subFilter = null) {
      sidebarTab = tab;
      const btnFeed = document.getElementById('tab-btn-feed');
      const btnAll = document.getElementById('tab-btn-all');
      const controlsFeed = document.getElementById('controls-feed-group');
      const controlsAll = document.getElementById('controls-all-group');

      if (btnFeed) btnFeed.classList.toggle('active', tab === 'feed');
      if (btnAll) btnAll.classList.toggle('active', tab === 'all');
      if (controlsFeed) controlsFeed.style.display = (tab === 'feed') ? 'block' : 'none';
      if (controlsAll) controlsAll.style.display = (tab === 'all') ? 'block' : 'none';

      // Cập nhật ô input search
      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.value = (tab === 'feed') ? feedQuery : allQuery;
        searchInput.placeholder = (tab === 'feed') 
          ? "🔍 Tìm trong các điểm có hàng (tên quán, ga, khu vực)..." 
          : "🔍 Tìm trong toàn bộ 4,050 cửa hàng Osaka...";
      }

      if (subFilter && tab === 'all') {
        allStatusFilter = subFilter;
        const allStatusSel = document.getElementById('all-status-select');
        if (allStatusSel) allStatusSel.value = subFilter;
      }

      updateFilterBanner();
      renderSidebarListOnly();
      saveSettings();
    }
    window.setSidebarTab = setSidebarTab;
    window.switchSidebarTab = setSidebarTab; // backward-compat

    // BỘ LỌC CHO TAB BÁO CÓ HÀNG (FEED)
    function setFeedFreshness(val) {
      feedFreshnessHours = parseFloat(val);
      updateFilterBanner();
      renderSidebarListOnly();
      saveSettings();
    }
    window.setFeedFreshness = setFeedFreshness;

    function setFeedChain(val) {
      feedChain = val;
      updateFilterBanner();
      renderSidebarListOnly();
      saveSettings();
    }
    window.setFeedChain = setFeedChain;

    function setFeedSort(val) {
      feedSortMode = val;
      renderSidebarListOnly();
      saveSettings();
    }
    window.setFeedSort = setFeedSort;

    // ======================================
    // POKETAN STYLE PILLS & SORT CONTROLS
    // ======================================
    let poketanStatus = 'i'; // 'all' | 'i' | 'o' | 'n'

    function setPoketanStatusFilter(status) {
      poketanStatus = status;
      const selectEl = document.getElementById('poketan-status-select');
      if (selectEl && selectEl.value !== status) {
        selectEl.value = status;
      }
      renderSidebarListOnly();
      saveSettings();
    }
    window.setPoketanStatusFilter = setPoketanStatusFilter;

    function togglePoketanSort() {
      feedSortMode = (feedSortMode === 'newest') ? 'nearest' : 'newest';
      const label = document.getElementById('poketan-sort-label');
      const icon = document.getElementById('poketan-sort-icon');
      if (feedSortMode === 'nearest') {
        if (label) label.textContent = '距離順 (Gần nhất)';
        if (icon) icon.textContent = '📍';
      } else {
        if (label) label.textContent = '更新順 (Mới nhất)';
        if (icon) icon.textContent = '⏱';
      }
      renderSidebarListOnly();
      saveSettings();
    }
    window.togglePoketanSort = togglePoketanSort;

    function handleSearchInput(val) {
      feedQuery = val;
      allQuery = val;
      renderSidebarListOnly();
    }
    window.handleSearchInput = handleSearchInput;

    // 3. ĐIỀU KHIỂN GHIM TRÊN BẢN ĐỒ (CHỈ TÁC ĐỘNG BẢN ĐỒ LEAFLET, KHÔNG ĐỤNG SIDEBAR)
    function setMapMode(mode) {
      mapDisplay.mode = mode;
      syncMapSettingsUI();
      updateQuickMapModeBtn();
      renderMapMarkersOnly(); // Chỉ vẽ lại ghim bản đồ!
      saveSettings();
    }
    window.setMapMode = setMapMode;

    function setMapChain(chain) {
      mapDisplay.chain = chain;
      currentChain = chain;
      syncMapSettingsUI();
      renderMapMarkersOnly(); // Chỉ vẽ lại ghim bản đồ!
      saveSettings();
    }
    window.setMapChain = setMapChain;

    function toggleQuickMapMode() {
      if (mapDisplay.mode === 'all') {
        setMapMode('only_in');
      } else {
        setMapMode('all');
      }
    }
    window.toggleQuickMapMode = toggleQuickMapMode;

    function updateQuickMapModeBtn() {
      const btnText = document.getElementById('quick-map-mode-text');
      const bannerMap = document.getElementById('banner-map-status');
      let label = '🏢 Bản đồ: Tất cả 4,050 điểm';
      let bannerText = '🗺️ Bản đồ: Toàn cảnh 4,050 điểm';
      if (mapDisplay.mode === 'only_in') {
        label = '🟢 Bản đồ: Chỉ điểm có hàng';
        bannerText = '🗺️ Bản đồ: Chỉ điểm có hàng 🟢';
      } else if (mapDisplay.mode === 'with_out') {
        label = '🟢🔴 Bản đồ: Có & Hết hàng';
        bannerText = '🗺️ Bản đồ: Có hàng & Hết hàng 🟢🔴';
      }
      if (btnText) btnText.innerHTML = label;
      if (bannerMap) bannerMap.innerHTML = bannerText;
    }

    function toggleMapCold(checked) {
      mapDisplay.includeCold = checked;
      includeCold = checked;
      syncMapSettingsUI();
      renderMapMarkersOnly();
      renderSidebarListOnly();
      saveSettings();
    }
    window.toggleMapCold = toggleMapCold;
    window.toggleIncludeCold = toggleMapCold; // backward-compat

    function resetMapSettings() {
      if (!confirm('Khôi phục toàn bộ cài đặt hiển thị bản đồ về mặc định (Hiện tất cả 4,050 điểm)?')) return;
      mapDisplay = { mode: 'all', chain: '', includeCold: true };
      currentChain = '';
      syncMapSettingsUI();
      updateQuickMapModeBtn();
      renderMapMarkersOnly();
      saveSettings();
    }
    window.resetMapSettings = resetMapSettings;
    window.resetToFactorySettings = resetMapSettings; // backward-compat

    function updateFilterBanner() {
      const banner = document.getElementById('banner-filter-text');
      if (!banner) return;
      if (sidebarTab === 'feed') {
        let fText = '24 giờ qua';
        if (feedFreshnessHours === 1) fText = '1 giờ qua 🔥';
        else if (feedFreshnessHours === 3) fText = '3 giờ qua';
        else if (feedFreshnessHours === 6) fText = '6 giờ qua';
        else if (feedFreshnessHours > 9000) fText = 'Tất cả thời gian';

        let cText = feedChain ? ` • Chuỗi ${feedChain}` : '';
        banner.innerHTML = `🟢 Báo Có Hàng (${fText}${cText})`;
      } else {
        let sText = 'Tất cả trạng thái';
        if (allStatusFilter === 'i') sText = 'Chỉ có hàng 🟢';
        else if (allStatusFilter === 'o') sText = 'Chỉ hết hàng 🔴';
        else if (allStatusFilter === 'n') sText = 'Không bán thẻ ⚪';

        let cText = allChain ? ` • Chuỗi ${allChain}` : '';
        banner.innerHTML = `🏢 Tra cứu toàn bộ 4,050 điểm (${sText}${cText})`;
      }
      updateQuickMapModeBtn();
    }
    window.updateFilterBanner = updateFilterBanner;

    function syncMapSettingsUI() {
      const rAll = document.getElementById('map-mode-all');
      const rIn = document.getElementById('map-mode-only_in');
      const rWithOut = document.getElementById('map-mode-with_out');
      if (rAll && mapDisplay.mode === 'all') rAll.checked = true;
      if (rIn && mapDisplay.mode === 'only_in') rIn.checked = true;
      if (rWithOut && mapDisplay.mode === 'with_out') rWithOut.checked = true;

      const pAll = document.getElementById('btn-map-preset-all');
      const pIn = document.getElementById('btn-map-preset-in');
      const pBoth = document.getElementById('btn-map-preset-both');
      if (pAll) pAll.classList.toggle('active', mapDisplay.mode === 'all');
      if (pIn) pIn.classList.toggle('active', mapDisplay.mode === 'only_in');
      if (pBoth) pBoth.classList.toggle('active', mapDisplay.mode === 'with_out');

      const modalChain = document.getElementById('map-modal-chain-select');
      if (modalChain) modalChain.value = mapDisplay.chain || '';

      const checkCold = document.getElementById('check-include-cold');
      if (checkCold) checkCold.checked = mapDisplay.includeCold;

      updateQuickMapModeBtn();
      updateFilterBanner();
    }
    window.syncMapSettingsUI = syncMapSettingsUI;

    // NOTIFICATION ACTIONS
    function setNotifMaxAge(hours) {
      notifSettings.maxReportAgeHours = hours;
      maxReportAgeHours = hours;
      syncNotifUI();
      renderUI();
      saveSettings();
    }
    window.setNotifMaxAge = setNotifMaxAge;
    window.setMaxReportAge = setNotifMaxAge; // backward-compat

    // Backward-compat handlers
    function applyPreset(preset) {
      if (preset === 'only_in') {
        setMapMode('only_in');
        setNotifMaxAge(24);
      } else if (preset === 'fresh_3h') {
        setMapMode('only_in');
        setNotifMaxAge(3);
      } else if (preset === 'show_all') {
        setMapMode('all');
      } else if (preset === 'with_out') {
        setMapMode('with_out');
      }
    }
    window.applyPreset = applyPreset;

    function toggleQuickStatus(code) {
      if (code === 'o') {
        setMapMode(mapDisplay.mode === 'with_out' ? 'all' : 'with_out');
      } else if (code === 'i') {
        setMapMode(mapDisplay.mode === 'only_in' ? 'all' : 'only_in');
      }
    }
    window.toggleQuickStatus = toggleQuickStatus;

    function handleStatusQuickSelect(val) {
      if (val === 'custom') {
        toggleMapSettingsModal();
        return;
      }
      applyPreset(val);
    }
    window.handleStatusQuickSelect = handleStatusQuickSelect;

    function toggleSelectAllStatuses(checked) {
      setMapMode(checked ? 'all' : 'only_in');
    }
    window.toggleSelectAllStatuses = toggleSelectAllStatuses;

    function updateStatusFilter(code, checked) {
      renderUI();
    }
    window.updateStatusFilter = updateStatusFilter;

    function setSortMode(mode) {
      sortMode = mode;
      const sortSelect = document.getElementById('sort-select');
      if (sortSelect) sortSelect.value = mode;
      if (mode === 'nearest' && userLat === null) {
        requestUserLocation(true);
      } else {
        renderUI();
      }
      saveSettings();
    }
    window.setSortMode = setSortMode;

    function toggleMapSettingsModal() {
      const modal = document.getElementById('map-settings-modal');
      const notifModal = document.getElementById('notif-settings-modal');
      if (notifModal) notifModal.style.display = 'none';

      const isVisible = modal.style.display !== 'none';
      modal.style.display = isVisible ? 'none' : 'flex';
      const sideBtn = document.getElementById('btn-sidebar-settings');
      if (sideBtn) sideBtn.classList.toggle('active', !isVisible);
      if (!isVisible) syncMapSettingsUI();
    }
    window.toggleMapSettingsModal = toggleMapSettingsModal;
    window.toggleSettingsModal = toggleMapSettingsModal; // backward-compat

    function toggleNotifSettingsModal() {
      const notifModal = document.getElementById('notif-settings-modal');
      const mapModal = document.getElementById('map-settings-modal');
      if (mapModal) mapModal.style.display = 'none';

      const isVisible = notifModal.style.display !== 'none';
      notifModal.style.display = isVisible ? 'none' : 'flex';
      if (!isVisible) syncNotifUI();
    }
    window.toggleNotifSettingsModal = toggleNotifSettingsModal;

    // 2.1 SETTINGS PERSISTENCE & RESTORE
    function saveSettings() {
      const payload = {
        mapDisplay,
        notifications: notifSettings,
        sidebarTab,
        feedFreshnessHours,
        feedChain,
        feedSortMode,
        allStatusFilter,
        allChain,
        allSortMode,
        statusFilter: {
          'i': true,
          'o': mapDisplay.mode !== 'only_in',
          'n': mapDisplay.mode === 'all',
          'u': mapDisplay.mode === 'all'
        },
        maxReportAgeHours: notifSettings.maxReportAgeHours,
        includeCold: mapDisplay.includeCold,
        currentChain: mapDisplay.chain,
        sortMode,
        showExpired
      };

      try {
        localStorage.setItem('bawui_user_settings', JSON.stringify(payload));
      } catch(e) {}

      const indMap = document.getElementById('map-save-indicator');
      const indNotif = document.getElementById('notif-save-indicator');
      if (indMap) indMap.innerHTML = '💾 Đang lưu...';
      if (indNotif) indNotif.innerHTML = '💾 Đang lưu...';

      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(() => {
        if (indMap) indMap.innerHTML = '💾 Đã lưu cấu hình bản đồ vào <b>settings.json</b>';
        if (indNotif) indNotif.innerHTML = '💾 Đã lưu cấu hình thông báo vào <b>settings.json</b>';
      })
      .catch(err => {
        console.warn('Could not save settings to server:', err);
        if (indMap) indMap.innerHTML = '💾 Đã lưu bộ nhớ trình duyệt';
        if (indNotif) indNotif.innerHTML = '💾 Đã lưu bộ nhớ trình duyệt';
      });
    }
    window.saveSettings = saveSettings;

    function applyLoadedSettings(settings) {
      if (!settings) return;
      if (settings.mapDisplay && typeof settings.mapDisplay === 'object') {
        mapDisplay = { ...mapDisplay, ...settings.mapDisplay };
      } else if (settings.statusFilter) {
        const sf = settings.statusFilter;
        if (sf.i && sf.o && sf.n && sf.u) mapDisplay.mode = 'all';
        else if (sf.i && sf.o) mapDisplay.mode = 'with_out';
        else mapDisplay.mode = 'only_in';
      }

      if (settings.notifications && typeof settings.notifications === 'object') {
        notifSettings = { ...notifSettings, ...settings.notifications };
      } else if (typeof settings.maxReportAgeHours === 'number') {
        notifSettings.maxReportAgeHours = settings.maxReportAgeHours;
      }

      if (typeof settings.sidebarTab === 'string') {
        sidebarTab = settings.sidebarTab;
      }
      if (typeof settings.feedFreshnessHours === 'number') {
        feedFreshnessHours = settings.feedFreshnessHours;
      }
      if (typeof settings.feedChain === 'string') {
        feedChain = settings.feedChain;
      }
      if (typeof settings.feedSortMode === 'string') {
        feedSortMode = settings.feedSortMode;
      }
      if (typeof settings.allStatusFilter === 'string') {
        allStatusFilter = settings.allStatusFilter;
      }
      if (typeof settings.allChain === 'string') {
        allChain = settings.allChain;
      }
      if (typeof settings.allSortMode === 'string') {
        allSortMode = settings.allSortMode;
      }

      const fFreshSel = document.getElementById('feed-freshness-select');
      if (fFreshSel) fFreshSel.value = String(feedFreshnessHours);
      const fChainSel = document.getElementById('feed-chain-select');
      if (fChainSel) fChainSel.value = feedChain;
      const fSortSel = document.getElementById('feed-sort-select');
      if (fSortSel) fSortSel.value = feedSortMode;
      const aStatSel = document.getElementById('all-status-select');
      if (aStatSel) aStatSel.value = allStatusFilter;
      const aChainSel = document.getElementById('all-chain-select');
      if (aChainSel) aChainSel.value = allChain;
      const aSortSel = document.getElementById('all-sort-select');
      if (aSortSel) aSortSel.value = allSortMode;

      if (typeof settings.sortMode === 'string') {
        sortMode = settings.sortMode;
      }
      if (typeof settings.showExpired === 'boolean') {
        showExpired = settings.showExpired;
      }

      setSidebarTab(sidebarTab || 'feed');
      syncMapSettingsUI();
      syncNotifUI();
      renderUI();
    }
    window.applyLoadedSettings = applyLoadedSettings;

    // 3. ROUTING & MENU SYNCHRONIZATION (LINK <-> MENU)
    function getRouteFromUrl() {
      const path = window.location.pathname.toLowerCase();
      const hash = window.location.hash.toLowerCase();
      if (path.includes('/calendar') || path.includes('/events') || hash.includes('calendar') || hash.includes('events')) {
        return 'calendar';
      }
      return 'map';
    }

    function syncMenuAndRoute(route, pushHistory = false) {
      const mapLink = document.getElementById('menu-map-link');
      const calLink = document.getElementById('menu-cal-link');
      const viewMap = document.getElementById('view-stores-mode');
      const viewCal = document.getElementById('view-calendar-mode');

      const targetPath = route === 'calendar' ? '/calendar' : '/map';

      if (pushHistory && window.location.pathname !== targetPath) {
        history.pushState({ route }, '', targetPath);
      }

      if (route === 'calendar') {
        calLink.classList.add('active');
        mapLink.classList.remove('active');
        viewMap.classList.remove('active');
        viewCal.classList.add('active');
        document.title = "Lịch Bốc Thăm & Đặt Trước | BAWUI POKE APP";
        loadCalendar();
      } else {
        mapLink.classList.add('active');
        calLink.classList.remove('active');
        viewMap.classList.add('active');
        viewCal.classList.remove('active');
        document.title = "Bản Đồ & Kho Thẻ Osaka | BAWUI POKE APP";
        setTimeout(() => {
          map.invalidateSize();
        }, 100);
      }
    }

    function navigateMenu(route) {
      syncMenuAndRoute(route, true);
    }
    window.navigateMenu = navigateMenu;
    window.switchTab = navigateMenu; // backward-compat

    window.addEventListener('popstate', () => {
      const currentRoute = getRouteFromUrl();
      syncMenuAndRoute(currentRoute, false);
    });

    window.addEventListener('hashchange', () => {
      const currentRoute = getRouteFromUrl();
      syncMenuAndRoute(currentRoute, false);
    });

    function refreshAll() {
      loadCalendar();
      renderUI();
    }
    window.refreshAll = refreshAll;

    // 4. HAVERSINE DISTANCE FORMULA
    function calcDistanceKm(lat1, lon1, lat2, lon2) {
      if (!lat1 || !lon1 || !lat2 || !lon2) return null;
      const R = 6371;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    }

    function formatDistance(km) {
      if (km === null || isNaN(km)) return '';
      if (km < 1) return Math.round(km * 1000) + ' m';
      return km.toFixed(1) + ' km';
    }
    window.calcDistanceKm = calcDistanceKm;
    window.calculateDistance = calcDistanceKm;

    // 5. USER LOCATION RENDERING
    function renderUserLocation(fly = false) {
      userLocationLayer.clearLayers();
      if (userLat === null || userLng === null) return;

      const userIcon = L.divIcon({
        className: 'user-marker-container',
        html: '<div class="user-pulse-marker" title="Vị trí của bạn"></div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9]
      });

      const userMarker = L.marker([userLat, userLng], { icon: userIcon, zIndexOffset: 2000 });
      const label = isMockLocation ? '📍 Vị trí giả lập: Ga Umeda (Osaka)' : '📍 Vị trí hiện tại của bạn';
      userMarker.bindPopup(`<b>${label}</b><br><span style="font-size:0.8rem;color:#64748b;">Đang tính khoảng cách đến tất cả cửa hàng</span>`);
      userLocationLayer.addLayer(userMarker);

      if (userAccuracy && !isMockLocation) {
        const accuracyCircle = L.circle([userLat, userLng], {
          radius: Math.min(userAccuracy, 2000),
          color: '#3b82f6',
          fillColor: '#93c5fd',
          fillOpacity: 0.15,
          weight: 1
        });
        userLocationLayer.addLayer(accuracyCircle);
      }

      if (fly) {
        map.flyTo([userLat, userLng], 14, { duration: 1.2 });
      }
    }

    function requestUserLocation(fly = true) {
      const headerLoc = document.getElementById('header-loc-summary');
      if (!navigator.geolocation) {
        if (headerLoc) headerLoc.innerText = 'Không hỗ trợ GPS';
        return;
      }

      if (headerLoc) headerLoc.innerText = 'Đang định vị...';

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          isMockLocation = false;
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          userAccuracy = pos.coords.accuracy;

          // Lưu cache vị trí vào sessionStorage để tránh giật bản đồ khi tải lại trang
          try {
            sessionStorage.setItem('bawui_last_lat', String(userLat));
            sessionStorage.setItem('bawui_last_lng', String(userLng));
            sessionStorage.setItem('bawui_last_acc', String(userAccuracy));
          } catch(e) {}

          const distToOsaka = calcDistanceKm(userLat, userLng, 34.6937, 135.5023);
          let note = `(Cách Osaka ~${Math.round(distToOsaka)}km)`;
          if (distToOsaka < 30) note = `(Tại Osaka)`;

          if (headerLoc) headerLoc.innerText = `GPS của bạn ${note}`;
          renderUserLocation(fly);
          renderUI();
        },
        (err) => {
          console.warn("GPS error:", err.message);
          if (headerLoc) headerLoc.innerText = 'Chưa bật GPS';
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: fly ? 0 : 30000 }
      );
    }
    window.requestUserLocation = requestUserLocation;

    // 6. TOAST NOTIFICATIONS & ALERT DISPATCH
    function showToast(store, info, force = false) {
      if (!force) {
        if (!notifSettings.notifyInStock) return;
        if (notifSettings.notifyChain && store.chain !== notifSettings.notifyChain) return;
        if (notifSettings.onlyOnsiteGps && !info.onsite) return;
      }

      playChime(force);

      if ((force || notifSettings.pushEnabled) && "Notification" in window && Notification.permission === "granted") {
        try {
          const packsDesc = info.packs.length ? info.packs.join(', ') : 'Thẻ Pokémon';
          new Notification("🔥 CÓ HÀNG MỚI TẠI OSAKA!", {
            body: `${store.name}\nSản phẩm: ${packsDesc}\nThời gian: ${info.reported_at}`,
            icon: "https://poketan.jp/apple-touch-icon.png"
          });
        } catch(e) {}
      }

      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.innerHTML = `
        <div class="toast-header">
          <span>🟢 VỪA BÁO CÓ HÀNG!</span>
          <span class="toast-time">${info.timeAgo}</span>
        </div>
        <div class="toast-body">${store.name}</div>
        <div class="toast-pack">📦 ${info.packs.length ? info.packs.join(', ') : 'Gói thẻ Pokémon'}</div>
        <button class="toast-btn" onclick="openStoreHistoryModal('${store.id}')">Xem lịch sử & vị trí 📜📍</button>
      `;

      container.appendChild(toast);

      // Tự động đẩy tin báo về Discord Webhook và Telegram Bot nếu được kích hoạt
      triggerWebhooks(store, info, force);

      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 400);
      }, 10000);
    }
    window.showToast = showToast;

    function showOutOfStockToast(store, info) {
      if (!notifSettings.notifyOutOfStock) return;
      if (notifSettings.notifyChain && store.chain !== notifSettings.notifyChain) return;
      if (notifSettings.onlyOnsiteGps && !info.onsite) return;

      playChime();

      if (notifSettings.pushEnabled && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification("🔴 BÁO HẾT HÀNG TẠI OSAKA", {
            body: `${store.name}\nCửa hàng vừa được báo hết thẻ Pokémon.`,
            icon: "https://poketan.jp/apple-touch-icon.png"
          });
        } catch(e) {}
      }

      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.style.borderLeftColor = '#dc2626';
      toast.innerHTML = `
        <div class="toast-header" style="color:#dc2626;">
          <span>🔴 VỪA BÁO HẾT HÀNG!</span>
          <span class="toast-time">${info.timeAgo}</span>
        </div>
        <div class="toast-body">${store.name}</div>
        <div style="font-size:0.75rem;color:#64748b;">Đã hết thẻ Pokémon tại điểm này</div>
        <button class="toast-btn" style="background:#dc2626;" onclick="openStoreHistoryModal('${store.id}')">Xem lịch sử & vị trí 📜📍</button>
      `;

      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 400);
      }, 8000);
    }
    window.showOutOfStockToast = showOutOfStockToast;

    function showNotHandledToast(store, info) {
      if (!notifSettings.notifyNotHandled) return;
      if (notifSettings.notifyChain && store.chain !== notifSettings.notifyChain) return;
      if (notifSettings.onlyOnsiteGps && !info.onsite) return;

      playChime();

      if (notifSettings.pushEnabled && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification("⚪ BÁO KHÔNG CÓ HÀNG TẠI OSAKA", {
            body: `${store.name}\nCửa hàng được báo không có hàng / không bán thẻ Pokémon.`,
            icon: "https://poketan.jp/apple-touch-icon.png"
          });
        } catch(e) {}
      }

      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.style.borderLeftColor = '#64748b';
      toast.innerHTML = `
        <div class="toast-header" style="color:#64748b;">
          <span>⚪ BÁO KHÔNG CÓ HÀNG / KHÔNG BÁN THẺ</span>
          <span class="toast-time">${info.timeAgo}</span>
        </div>
        <div class="toast-body">${store.name}</div>
        <div style="font-size:0.75rem;color:#64748b;">Điểm này hiện không bán thẻ Pokémon</div>
        <button class="toast-btn" style="background:#64748b;" onclick="openStoreHistoryModal('${store.id}')">Xem lịch sử & vị trí 📜📍</button>
      `;

      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 400);
      }, 8000);
    }
    window.showNotHandledToast = showNotHandledToast;

    // 7. TIME AGO & FRESHNESS EVALUATION
    function formatTimeAgo(timestamp) {
      if (!timestamp || timestamp <= 0) return 'Chưa rõ';
      const now = Math.floor(Date.now() / 1000);
      const diff = now - timestamp;
      if (diff < 60) return 'Vừa xong';
      if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
      if (diff < 86400) {
        const hours = Math.floor(diff / 3600);
        const mins = Math.floor((diff % 3600) / 60);
        return mins > 0 ? `${hours}h ${mins}p trước` : `${hours} giờ trước`;
      }
      const days = Math.floor(diff / 86400);
      return `${days} ngày trước`;
    }

    function getFreshnessInfo(code, timestamp) {
      if (code !== 'i') return null;
      if (!timestamp || timestamp <= 0) {
        return {
          level: 'stale',
          badgeClass: 'freshness-stale',
          tagText: '⚠️ Báo cáo đã lâu - Khả năng cao đã hết hàng',
          popupWarning: '<div style="background:#fee2e2;color:#991b1b;padding:6px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;margin:6px 0;">⚠️ Cảnh báo: Báo cáo đã lâu, khả năng cao đã hết hàng!</div>'
        };
      }
      const now = Math.floor(Date.now() / 1000);
      const diffHours = (now - timestamp) / 3600;
      
      if (diffHours <= 1.0) {
        return {
          level: 'fresh',
          badgeClass: 'freshness-fresh',
          tagText: '🔥 Vừa báo (<1h) - Khả năng còn hàng RẤT CAO!',
          popupWarning: '<div style="background:#dcfce7;color:#15803d;padding:6px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;margin:6px 0;">🔥 Tin siêu mới (<1h)! Khả năng còn hàng rất cao, nên đến ngay!</div>'
        };
      } else if (diffHours <= 3.0) {
        return {
          level: 'moderate',
          badgeClass: 'freshness-moderate',
          tagText: `⚡ Báo ${formatTimeAgo(timestamp)} - Khả năng còn hàng`,
          popupWarning: `<div style="background:#fef9c3;color:#854d0e;padding:6px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;margin:6px 0;">⚡ Báo ${formatTimeAgo(timestamp)}. Thẻ có thể sắp hết, nên đến sớm!</div>`
        };
      } else if (diffHours <= 6.0) {
        return {
          level: 'aging',
          badgeClass: 'freshness-aging',
          tagText: `⚠️ Báo ${formatTimeAgo(timestamp)} - Có thể đã hết hàng`,
          popupWarning: `<div style="background:#ffedd5;color:#9a3412;padding:6px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;margin:6px 0;">⚠️ Báo ${formatTimeAgo(timestamp)}. Thẻ Pokémon thường bán hết nhanh, có thể đã hết hàng!</div>`
        };
      } else {
        return {
          level: 'stale',
          badgeClass: 'freshness-stale',
          tagText: `⛔ Báo ${formatTimeAgo(timestamp)} - Thời gian quá lâu, có thể đã hết`,
          popupWarning: `<div style="background:#fee2e2;color:#991b1b;padding:6px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;margin:6px 0;">⛔ Cảnh báo: Báo cáo cách đây ${formatTimeAgo(timestamp)}! Thời gian quá lâu, khả năng rất cao đã hết hàng.</div>`
        };
      }
    }

    // 8. STATUS DECODER
    function decodeStatus(val, conf) {
      if (!val || typeof val !== 'string') {
        return {
          code: 'u',
          label: 'Chưa có báo cáo',
          packs: [],
          timestamp: 0,
          reported_at: 'Chưa rõ',
          timeAgo: 'Chưa có báo cáo',
          confirms: 0,
          onsite: false,
          freshness: null
        };
      }
      const rawCode = val[0];
      const code = rawCode.toLowerCase();
      let rest = val.substring(1);

      let onsite = false;
      if (rest.endsWith('g')) {
        onsite = true;
        rest = rest.slice(0, -1);
      }

      let packs = [];
      let packCodes = configData.packCodes || {};
      for (const [pCode, pName] of Object.entries(packCodes)) {
        if (rest.endsWith(pCode)) {
          packs.push(pName);
          rest = rest.slice(0, -pCode.length);
        }
      }

      let dtStr = '-';
      let timestamp = 0;
      if (rest.length >= 10) {
        const timeSub = rest.substring(0, 10);
        const parsed = parseInt(timeSub, 10);
        if (!isNaN(parsed)) {
          timestamp = parsed;
          const d = new Date(parsed * 1000);
          dtStr = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) + ' ' +
                  d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' });
        }
      }

      const labelMap = {
        'i': 'Có hàng (In Stock)',
        'o': 'Hết hàng (Out of Stock)',
        'n': 'Không bán thẻ',
        'u': 'Chưa có báo cáo'
      };

      const timeAgo = formatTimeAgo(timestamp);
      const freshness = getFreshnessInfo(code, timestamp);

      return {
        code,
        label: labelMap[code] || 'Chưa rõ',
        packs,
        timestamp,
        reported_at: dtStr,
        timeAgo,
        confirms: conf || 0,
        onsite,
        freshness
      };
    }

    // 9. RENDER ALL STORES WITH COMPLETELY DECOUPLED MAP & NOTIFICATION FEED
    function renderMapMarkersOnly() {
      markersLayer.clearLayers();
      markerMap = {};

      const allStores = Object.values(storesDict);
      const effectiveStatus = mapDisplay.includeCold ? latestMergedStatus : hotStatus;

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;

        // Check mapDisplay chain filter
        if (mapDisplay.chain && store.chain !== mapDisplay.chain) continue;

        const sid = store.id;
        const rawVal = effectiveStatus[sid];
        const info = decodeStatus(rawVal, effectiveStatus[sid + '_c']);

        // Check mapDisplay mode filter (CHỈ LỌC CHO BẢN ĐỒ)
        if (mapDisplay.mode === 'only_in' && info.code !== 'i') continue;
        if (mapDisplay.mode === 'with_out' && info.code !== 'i' && info.code !== 'o') continue;

        let distanceKm = null;
        if (userLat !== null && userLng !== null) {
          distanceKm = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        }

        const dirUrl = (userLat && userLng) 
          ? `https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${store.lat},${store.lng}&travelmode=walking`
          : `https://www.google.com/maps/search/?api=1&query=${store.lat},${store.lng}`;

        const distHtml = distanceKm !== null ? `<div style="color:#2563eb;font-weight:700;font-size:0.8rem;margin:4px 0;">📍 Cách bạn: ${formatDistance(distanceKm)}</div>` : '';

        let statusBadgeHtml = '';
        if (info.code === 'i') statusBadgeHtml = '<div style="color:#16a34a;font-weight:800;margin:4px 0;">🟢 Đang có hàng (In Stock)</div>';
        else if (info.code === 'o') statusBadgeHtml = '<div style="color:#dc2626;font-weight:800;margin:4px 0;">🔴 Hết hàng (Out of Stock)</div>';
        else if (info.code === 'n') statusBadgeHtml = '<div style="color:#64748b;font-weight:700;margin:4px 0;">⚪ Không bán thẻ Pokémon</div>';
        else statusBadgeHtml = '<div style="color:#94a3b8;font-weight:600;margin:4px 0;">🔘 Chưa có báo cáo gần đây</div>';

        const packsHtml = info.packs.length ? `<div style="margin-top:6px;"><b>Packs:</b> ${info.packs.join(', ')}</div>` : '';
        const reportTimeHtml = info.reported_at !== '-' && info.reported_at !== 'Chưa rõ' 
          ? `<div style="font-size:0.75rem;margin-top:4px;"><b>Báo cáo:</b> ${info.reported_at} <span style="color:#2563eb;font-weight:700;">(${info.timeAgo})</span></div>` 
          : '';

        const freshnessWarning = info.freshness ? info.freshness.popupWarning : '';

        const popupContent = `
          <div style="font-family:'Inter',sans-serif;min-width:220px;">
            <b style="font-size:0.95rem;color:#0f172a;">${store.name}</b>
            <div style="font-size:0.75rem;color:#0284c7;font-weight:700;">${store.chain_label || store.chain}</div>
            ${statusBadgeHtml}
            ${freshnessWarning}
            ${distHtml}
            <div style="font-size:0.75rem;color:#64748b;margin-top:2px;">${store.address || ''}</div>
            ${reportTimeHtml}
            ${packsHtml}
            <div style="margin-top:8px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
              <a href="${dirUrl}" target="_blank" style="display:inline-block;padding:5px 11px;background:#2563eb;color:white;text-decoration:none;border-radius:5px;font-size:0.75rem;font-weight:700;">Chỉ đường Maps ↗</a>
              <button type="button" id="popup-btn-${store.id}" onclick="event.stopPropagation(); togglePopupHistoryAccordion('${store.id}', event)" style="display:inline-flex;align-items:center;gap:5px;padding:6px 12px;background:#0f172a;color:white;border:none;border-radius:6px;font-size:0.75rem;font-weight:700;cursor:pointer;">
                <span id="popup-arrow-${store.id}" style="font-weight:900;">▶</span> Lịch sử báo cáo
              </button>
            </div>
            <div id="popup-accordion-${store.id}" class="popup-accordion-body" style="display:none;margin-top:8px;padding-top:8px;border-top:1px dashed #cbd5e1;max-height:250px;overflow-y:auto;">
            </div>
          </div>
        `;

        let marker;
        if (info.code === 'i') {
          const isFresh = info.freshness && info.freshness.level === 'fresh';
          const shadowStyle = isFresh ? 'box-shadow:0 0 12px #22c55e;' : 'box-shadow:0 0 8px rgba(22,163,74,0.8);';
          const greenIcon = L.divIcon({
            className: 'custom-pin-in',
            html: `<div style="background:#16a34a;width:26px;height:26px;border-radius:50%;border:2px solid white;${shadowStyle}display:flex;align-items:center;justify-content:center;color:white;font-size:13px;font-weight:bold;">🟢</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
          });
          marker = L.marker([store.lat, store.lng], { icon: greenIcon, zIndexOffset: 1500 });
        } else if (info.code === 'o') {
          marker = L.circleMarker([store.lat, store.lng], {
            radius: 6,
            color: '#991b1b',
            fillColor: '#dc2626',
            fillOpacity: 0.85,
            weight: 1.5
          });
        } else if (info.code === 'n') {
          marker = L.circleMarker([store.lat, store.lng], {
            radius: 5,
            color: '#64748b',
            fillColor: '#94a3b8',
            fillOpacity: 0.7,
            weight: 1
          });
        } else {
          marker = L.circleMarker([store.lat, store.lng], {
            radius: 4,
            color: '#94a3b8',
            fillColor: '#cbd5e1',
            fillOpacity: 0.5,
            weight: 1
          });
        }

        marker.bindPopup(popupContent);
        marker.on('click', () => {
          currentFocusedStoreId = store.id;
          document.querySelectorAll('.store-card').forEach(c => c.classList.remove('active-store-card'));
          const card = document.getElementById('card-' + store.id);
          if (card) {
            card.classList.add('active-store-card');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        });
        markersLayer.addLayer(marker);
        markerMap[sid] = marker;
      }

      updateQuickMapModeBtn();
    }
    window.renderMapMarkersOnly = renderMapMarkersOnly;

    // RENDER SIDEBAR LIST (TÁCH BIỆT HOÀN TOÀN: BÁO CÓ HÀNG vs TRA CỨU TOÀN BỘ)
    function renderSidebarListOnly() {
      const storeList = document.getElementById('store-list');
      if (!storeList) return;

      const now = Math.floor(Date.now() / 1000);
      const allStores = Object.values(storesDict);
      const effectiveStatus = mapDisplay.includeCold ? latestMergedStatus : hotStatus;

      // 1. TÍNH TOÁN CÁC CON SỐ THỐNG KÊ TOÀN CỤC
      let countI = 0;
      let countO = 0;
      let countN = 0;
      let countU = 0;

      for (const store of allStores) {
        const raw = effectiveStatus[store.id];
        const code = (raw && typeof raw === 'string') ? raw[0].toLowerCase() : 'u';
        if (code === 'i') countI++;
        else if (code === 'o') countO++;
        else if (code === 'n') countN++;
        else countU++;
      }

      const statInEl = document.getElementById('stat-in');
      if (statInEl) statInEl.innerText = countI;
      const statOutEl = document.getElementById('stat-out');
      if (statOutEl) statOutEl.innerText = countO;
      const statTotEl = document.getElementById('stat-total');
      if (statTotEl) statTotEl.innerText = allStores.length ? allStores.length.toLocaleString() : '4,050';
      const menuStockEl = document.getElementById('menu-stock-count');
      if (menuStockEl) menuStockEl.innerText = `${countI} Có hàng`;

      const feedBadge = document.getElementById('feed-tab-count');
      if (feedBadge) feedBadge.innerText = countI;
      const allBadge = document.getElementById('all-tab-count');
      if (allBadge) allBadge.innerText = allStores.length ? allStores.length.toLocaleString() : '4,050';
      const mobStockBadge = document.getElementById('mob-badge-stock');
      if (mobStockBadge) mobStockBadge.innerText = countI;

      let listToRender = [];

      for (const store of allStores) {
        const sid = store.id;
        const rawVal = effectiveStatus[sid];
        const info = decodeStatus(rawVal, effectiveStatus[sid + '_c']);

        // 1. Lọc theo trạng thái PokéTan (tất cả / có hàng / hết hàng / chưa rõ)
        if (poketanStatus !== 'all') {
          if (poketanStatus === 'i' && info.code !== 'i') continue;
          if (poketanStatus === 'o' && info.code !== 'o') continue;
          if (poketanStatus === 'n' && (info.code !== 'n' && info.code !== 'u')) continue;
        }

        // 2. Lọc theo độ mới tin báo (feedFreshnessHours)
        if (feedFreshnessHours < 9000 && info.timestamp > 0) {
          const ageHours = (now - info.timestamp) / 3600;
          if (ageHours > feedFreshnessHours) continue;
        }

        // 3. Lọc theo chuỗi
        if (feedChain && store.chain !== feedChain) continue;

        // 4. Tính khoảng cách GPS
        let distanceKm = null;
        if (userLat !== null && userLng !== null && store.lat && store.lng) {
          distanceKm = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        }

        // 5. Lọc theo từ khóa tìm kiếm
        if (feedQuery) {
          const q = feedQuery.toLowerCase();
          const matchName = (store.name || '').toLowerCase().includes(q);
          const matchAddr = (store.address || '').toLowerCase().includes(q);
          if (!matchName && !matchAddr) continue;
        }

        listToRender.push({ store, info, distanceKm });
      }

      // Sắp xếp danh sách
      if (feedSortMode === 'nearest') {
        listToRender.sort((a, b) => {
          if (a.distanceKm === null) return 1;
          if (b.distanceKm === null) return -1;
          return a.distanceKm - b.distanceKm;
        });
      } else {
        // Cập nhật mới nhất trước (hoặc ưu tiên có hàng)
        listToRender.sort((a, b) => {
          const timeA = a.info.timestamp || 0;
          const timeB = b.info.timestamp || 0;
          return timeB - timeA;
        });
      }

      const subInfoEl = document.getElementById('poketan-sub-info');
      if (subInfoEl) {
        subInfoEl.textContent = `大阪府 ${listToRender.length.toLocaleString()}店舗から探せます`;
      }

      if (listToRender.length === 0) {
        storeList.innerHTML = `
          <div style="text-align:center;color:#64748b;padding:36px 16px;">
            <div style="font-size:2.2rem;margin-bottom:8px;">🔍</div>
            <b style="font-size:0.95rem;color:#0f172a;">Không có báo cáo nào phù hợp.</b>
            <div style="font-size:0.8rem;margin-top:6px;color:#64748b;">Hãy thử đổi bộ lọc trạng thái sang 'すべて' hoặc mở rộng mốc thời gian.</div>
          </div>
        `;
        return;
      }

      const renderSlice = listToRender.slice(0, visibleLimit);
      let html = '';
      for (const item of renderSlice) {
        html += renderSingleStoreCard(item);
      }

      if (listToRender.length > renderSlice.length) {
        html += `
          <div style="text-align:center;padding:12px 0;">
            <button type="button" onclick="loadMoreStores()" style="width:100%;padding:10px;font-size:0.82rem;font-weight:700;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:6px;cursor:pointer;">
              ⬇️ Tải thêm 150 báo cáo tiếp theo (Đang xem ${renderSlice.length} / ${listToRender.length.toLocaleString()})
            </button>
          </div>
        `;
      }

      storeList.innerHTML = html;
    }
    window.renderSidebarListOnly = renderSidebarListOnly;

    function renderSingleStoreCard(item) {
      const { store, info, distanceKm } = item;
      
      // Status dot and badge mapping exactly as Poketan
      let dotClass = 'dot-in';
      let badgeClass = 'poketan-badge-in';
      let badgeText = '在庫あり';

      if (info.code === 'o') {
        dotClass = 'dot-out';
        badgeClass = 'poketan-badge-out';
        badgeText = '在庫なし';
      } else if (info.code === 'n') {
        dotClass = 'dot-none';
        badgeClass = 'poketan-badge-none';
        badgeText = '扱ってない';
      } else if (info.code === 'u') {
        dotClass = 'dot-u';
        badgeClass = 'poketan-badge-u';
        badgeText = '不明';
      }

      // Check if newly reported (< 1h)
      const isNew = info.timestamp > 0 && ((Date.now() / 1000 - info.timestamp) < 3600);
      const newBadge = isNew ? `<span class="poketan-new-badge">NEW</span>` : '';

      // Format distance
      const distStr = distanceKm !== null ? `📍 ${formatDistance(distanceKm)}` : '';
      
      // Format time
      const timeStr = info.timeAgo || 'Vừa cập nhật';

      // Packs or note
      const packStr = info.packs.length ? `<span class="poketan-meta-pack">📦 ${info.packs.join(', ')}</span>` : '';
      const confirmStr = info.confirms ? `👥 ${info.confirms} người báo` : '匿名トレーナー';

      return `
        <div class="poketan-row" id="card-${store.id}" onclick="focusStore('${store.id}')" title="Bấm để xem vị trí trên bản đồ">
          <div class="poketan-row-left">
            <div class="status-dot ${dotClass}"></div>
            <div class="poketan-row-main">
              <div class="poketan-store-title-line">
                <span class="poketan-store-name">${store.name}</span>
                ${newBadge}
              </div>
              <div class="poketan-row-subline">
                <span>⏱ ${timeStr}</span>
                ${distStr ? `<span>• ${distStr}</span>` : ''}
                ${packStr ? `<span>• ${packStr}</span>` : ''}
                <span>• ${confirmStr}</span>
              </div>
            </div>
          </div>
          <div class="poketan-status-badge ${badgeClass}">
            ${badgeText}
          </div>
        </div>
      `;
    }

    function renderUI() {
      renderMapMarkersOnly();
      renderSidebarListOnly();
    }
    window.renderUI = renderUI;

    function loadMoreStores() {
      visibleLimit += 150;
      renderSidebarListOnly();
    }
    window.loadMoreStores = loadMoreStores;

    function loadAllStores() {
      visibleLimit = 5000;
      renderSidebarListOnly();
    }
    window.loadAllStores = loadAllStores;

    function focusStore(sid, openPopup = true) {
      navigateMenu('map');
      const store = storesDict[sid];
      if (store && store.lat && store.lng) {
        map.flyTo([store.lat, store.lng], 16, { duration: 0.8 });
        if (openPopup && markerMap[sid]) {
          setTimeout(() => markerMap[sid].openPopup(), 400);
        }
      }
    }
    window.focusStore = focusStore;

    function focusStoreOnMap(sid) {
      currentFocusedStoreId = sid;
      document.querySelectorAll('.store-card').forEach(c => c.classList.remove('active-store-card'));
      const card = document.getElementById('card-' + sid);
      if (card) {
        card.classList.add('active-store-card');
      }
      focusStore(sid, true);
    }
    window.focusStoreOnMap = focusStoreOnMap;
    // ----------------------------------------------------
    // STORE REPORT HISTORY ACCORDION & TIMELINE LOGIC
    // ----------------------------------------------------
    function buildStoreTimelineHtml(storeId, rawHistory, currentInfo, isPopup = false) {
      let timelineList = Array.isArray(rawHistory) ? [...rawHistory] : [];

      // Merge current realtime info if not present
      if (currentInfo && (currentInfo.code === 'i' || currentInfo.code === 'o' || currentInfo.timestamp > 0)) {
        const exists = timelineList.some(item => (currentInfo.timestamp > 0 && Math.abs((item.timestamp || 0) - currentInfo.timestamp) < 300));
        if (!exists) {
          timelineList.unshift({
            id: 'current_realtime',
            status: currentInfo.code === 'i' ? 'in-stock' : (currentInfo.code === 'o' ? 'out-of-stock' : 'not-handled'),
            status_code: currentInfo.code,
            status_label: currentInfo.code === 'i' ? '🟢 Có hàng (Trạng thái hiện tại)' : (currentInfo.code === 'o' ? '🔴 Hết hàng' : '⚪ Không bán'),
            note: currentInfo.packs.length ? currentInfo.packs.join(', ') : 'Ghi nhận trực tiếp realtime',
            user: 'Cộng đồng Poketan Osaka',
            who: currentInfo.confirms ? `${currentInfo.confirms} xác nhận` : '',
            onsite: currentInfo.onsite,
            timestamp: currentInfo.timestamp,
            formatted_time: (currentInfo.reported_at && currentInfo.reported_at !== '-') ? currentInfo.reported_at : ''
          });
        }
      }

      if (timelineList.length === 0) {
        return `
          <div style="background:white;border:1px dashed #cbd5e1;border-radius:6px;padding:12px;text-align:center;color:#64748b;font-size:0.75rem;">
            <div style="font-weight:700;color:#0f172a;margin-bottom:2px;">📋 Chưa có thêm báo cáo cũ</div>
            <div>Trạng thái hiện tại ghi nhận từ hệ thống Poketan.</div>
          </div>
        `;
      }

      let entriesHtml = '';
      for (const item of timelineList) {
        const itemTimeAgo = item.timestamp ? formatTimeAgo(item.timestamp) : 'Chưa rõ';
        let entryClass = 'entry-none';
        let badgeClass = 'mini-none';
        if (item.status_code === 'i') {
          entryClass = 'entry-in';
          badgeClass = 'mini-in';
        } else if (item.status_code === 'o') {
          entryClass = 'entry-out';
          badgeClass = 'mini-out';
        }

        let dateStr = item.formatted_time || '';
        if (item.timestamp && !dateStr) {
          const d = new Date(item.timestamp * 1000);
          dateStr = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) + ' ' +
                    d.toLocaleDateString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }

        const onsiteBadge = item.onsite ? `<span style="background:#e0f2fe;color:#0284c7;padding:1px 5px;border-radius:4px;font-size:0.68rem;font-weight:700;">📍 Tại quán</span>` : '';
        const userStr = item.user || 'Người dùng ẩn danh';
        const whoStr = item.who ? `(${item.who})` : '';

        entriesHtml += `
          <div class="accordion-hist-entry ${entryClass}">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:4px;">
              <span class="hist-mini-badge ${badgeClass}">${item.status_label}</span>
              <span style="font-size:0.72rem;font-weight:700;color:#2563eb;">⏱ ${itemTimeAgo}</span>
            </div>
            ${item.note ? `<div style="font-size:0.73rem;color:#1e293b;margin-top:2px;">📝 <b>Sản phẩm:</b> ${item.note}</div>` : ''}
            <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.68rem;color:#64748b;margin-top:2px;">
              <span>👤 ${userStr} ${whoStr} ${onsiteBadge}</span>
              <span>${dateStr}</span>
            </div>
          </div>
        `;
      }

      const store = storesDict[storeId];
      const dirUrl = (store && store.lat && store.lng) 
        ? ((userLat && userLng) 
            ? `https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${store.lat},${store.lng}&travelmode=walking`
            : `https://www.google.com/maps/search/?api=1&query=${store.lat},${store.lng}`)
        : '';

      const actionsBar = isPopup ? '' : `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;padding-top:6px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:6px;">
          ${dirUrl ? `<a href="${dirUrl}" target="_blank" style="font-size:0.72rem;color:#2563eb;font-weight:700;text-decoration:none;">🗺️ Chỉ đường Google Maps ↗</a>` : ''}
          <button type="button" onclick="openStoreHistoryModal('${storeId}')" style="background:none;border:none;color:#64748b;font-size:0.72rem;cursor:pointer;text-decoration:underline;">
            🔍 Phóng to toàn màn hình ↗
          </button>
        </div>
      `;

      return `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0;">
          <span style="font-size:0.74rem;font-weight:800;color:#0f172a;">📜 LỊCH SỬ BÁO CÁO</span>
          <span style="font-size:0.7rem;color:#2563eb;font-weight:700;">${timelineList.length} lượt</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;">
          ${entriesHtml}
        </div>
        ${actionsBar}
      `;
    }

    function renderAccordionContent(storeId, containerEl, historyData, isPopup = false) {
      const effectiveStatus = (mapDisplay && mapDisplay.includeCold) ? latestMergedStatus : hotStatus;
      const currentRaw = effectiveStatus[storeId];
      const currentInfo = decodeStatus(currentRaw, effectiveStatus[storeId + '_c']);

      const html = buildStoreTimelineHtml(storeId, historyData, currentInfo, isPopup);
      containerEl.innerHTML = html;
    }

    async function loadAndRenderAccordion(storeId, bodyEl) {
      if (!bodyEl) return;
      bodyEl.innerHTML = `
        <div style="text-align:center;padding:14px 8px;color:#64748b;font-size:0.75rem;">
          <span style="font-size:1.1rem;display:inline-block;animation:pulse 1s infinite;">⏳</span>
          <div style="margin-top:4px;font-weight:600;">Đang tải lịch sử báo cáo...</div>
        </div>
      `;

      try {
        const res = await fetch(`/api/store_history/${storeId}`);
        const data = await res.json();
        storeHistoryCache[storeId] = data;
        renderAccordionContent(storeId, bodyEl, data);
      } catch (err) {
        bodyEl.innerHTML = `
          <div style="color:#ef4444;font-size:0.75rem;padding:8px;text-align:center;">
            ⚠️ Không thể tải lịch sử: ${err.message}
          </div>
        `;
      }
    }

    async function toggleStoreHistoryAccordion(storeId) {
      const bodyEl = document.getElementById(`accordion-${storeId}`);
      const arrowEl = document.getElementById(`arrow-${storeId}`);
      const labelEl = document.getElementById(`toggle-label-${storeId}`);
      const btnEl = document.getElementById(`toggle-btn-${storeId}`);

      if (!bodyEl) return;

      const isOpen = bodyEl.style.display !== 'none';
      if (isOpen) {
        // Thu gọn: đổi mũi tên sang ngang ▶, card trở về kích thước ban đầu
        bodyEl.style.display = 'none';
        openAccordionStoreIds.delete(storeId);
        if (arrowEl) arrowEl.innerText = '▶';
        if (labelEl) labelEl.innerText = 'Lịch sử';
        if (btnEl) {
          btnEl.classList.remove('expanded');
          btnEl.title = 'Bấm để mở lịch sử báo cáo';
        }
        return;
      }

      // Mở rộng: đổi mũi tên hướng xuống ▼, card cao hơn để hiển thị lịch sử
      bodyEl.style.display = 'block';
      openAccordionStoreIds.add(storeId);
      if (arrowEl) arrowEl.innerText = '▼';
      if (labelEl) labelEl.innerText = 'Thu gọn';
      if (btnEl) {
        btnEl.classList.add('expanded');
        btnEl.title = 'Bấm để thu gọn lịch sử báo cáo';
      }

      if (storeHistoryCache[storeId]) {
        renderAccordionContent(storeId, bodyEl, storeHistoryCache[storeId]);
      } else {
        await loadAndRenderAccordion(storeId, bodyEl);
      }
    }
    window.toggleStoreHistoryAccordion = toggleStoreHistoryAccordion;

    function adjustLeafletPopup(storeId) {
      const marker = markerMap[storeId];
      if (marker && marker.getPopup()) {
        const pop = marker.getPopup();
        if (pop._updateLayout) pop._updateLayout();
        if (pop._updatePosition) pop._updatePosition();
        if (pop._adjustPan) pop._adjustPan();
      }
    }
    window.adjustLeafletPopup = adjustLeafletPopup;

    async function togglePopupHistoryAccordion(storeId, ev) {
      if (ev) {
        try {
          ev.stopPropagation();
          ev.preventDefault();
        } catch(e) {}
      }
      const bodyEl = document.getElementById(`popup-accordion-${storeId}`);
      const btnEl = document.getElementById(`popup-btn-${storeId}`);

      if (!bodyEl) return;

      const isOpen = bodyEl.style.display !== 'none';
      if (isOpen) {
        bodyEl.style.display = 'none';
        if (btnEl) btnEl.innerHTML = `<span id="popup-arrow-${storeId}" style="font-weight:900;">▶</span> Lịch sử báo cáo`;
        adjustLeafletPopup(storeId);
        return;
      }

      bodyEl.style.display = 'block';
      if (btnEl) btnEl.innerHTML = `<span id="popup-arrow-${storeId}" style="font-weight:900;">▼</span> Thu gọn lịch sử`;
      adjustLeafletPopup(storeId);

      if (storeHistoryCache[storeId]) {
        renderAccordionContent(storeId, bodyEl, storeHistoryCache[storeId], true);
        adjustLeafletPopup(storeId);
      } else {
        bodyEl.innerHTML = `
          <div style="text-align:center;padding:12px;color:#64748b;font-size:0.75rem;">
            ⏳ Đang tải lịch sử báo cáo...
          </div>
        `;
        adjustLeafletPopup(storeId);

        try {
          const res = await fetch(`/api/store_history/${storeId}`);
          const data = await res.json();
          storeHistoryCache[storeId] = data;
          renderAccordionContent(storeId, bodyEl, data, true);
          adjustLeafletPopup(storeId);
        } catch (err) {
          bodyEl.innerHTML = `
            <div style="color:#ef4444;font-size:0.75rem;padding:8px;text-align:center;">
              ⚠️ Không thể tải lịch sử: ${err.message}
            </div>
          `;
          adjustLeafletPopup(storeId);
        }
      }
    }
    window.togglePopupHistoryAccordion = togglePopupHistoryAccordion;

    // STORE REPORT HISTORY MODAL LOGIC
    async function openStoreHistoryModal(storeId) {
      currentFocusedStoreId = storeId;

      const modal = document.getElementById('store-history-modal');
      const titleEl = document.getElementById('hist-modal-title');
      const subEl = document.getElementById('hist-modal-subtitle');
      const bodyEl = document.getElementById('hist-modal-body');
      const footerEl = document.getElementById('hist-modal-footer-info');
      const dirBtn = document.getElementById('hist-modal-dir-btn');

      if (!modal) return;

      // Highlight active card in store list
      document.querySelectorAll('.store-card').forEach(c => c.classList.remove('active-store-card'));
      const activeCard = document.getElementById('card-' + storeId);
      if (activeCard) {
        activeCard.classList.add('active-store-card');
      }

      // Fly map to store in background without opening popup over modal
      try {
        focusStore(storeId, false);
      } catch(e) {}

      const store = storesDict[storeId] || { name: 'Cửa hàng ' + storeId, address: '' };
      if (titleEl) titleEl.innerText = store.name || 'Cửa hàng Osaka';

      let subText = (store.chain_label || store.chain || '');
      if (store.address) subText += ' • ' + store.address;
      if (userLat !== null && userLng !== null && store.lat && store.lng) {
        try {
          const d = (typeof calcDistanceKm === 'function') ? calcDistanceKm(userLat, userLng, store.lat, store.lng) : null;
          if (d !== null) subText += ` • 📍 Cách bạn: ${formatDistance(d)}`;
        } catch(e) {}
      }
      if (subEl) subEl.innerText = subText;

      if (dirBtn && store.lat && store.lng) {
        const dirUrl = (userLat && userLng) 
          ? `https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${store.lat},${store.lng}&travelmode=walking`
          : `https://www.google.com/maps/search/?api=1&query=${store.lat},${store.lng}`;
        dirBtn.href = dirUrl;
        dirBtn.style.display = 'inline-flex';
      } else if (dirBtn) {
        dirBtn.style.display = 'none';
      }

      // Open modal immediately to provide instant feedback
      modal.style.display = 'flex';
      if (!storeHistoryCache[storeId] && bodyEl) {
        bodyEl.innerHTML = `
          <div style="text-align:center;padding:36px;color:#64748b;">
            <div style="font-size:1.8rem;animation:pulse 1s infinite;">⏳</div>
            <div style="font-weight:700;margin-top:8px;">Đang tải lịch sử báo cáo từ Poketan Cloud...</div>
          </div>
        `;
      }

      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }

        // Get latest decoded status from cache for reference
        const effectiveStatus = (mapDisplay && mapDisplay.includeCold) ? latestMergedStatus : hotStatus;
        const currentRaw = effectiveStatus[storeId];
        const currentInfo = decodeStatus(currentRaw, effectiveStatus[storeId + '_c']);

        let currentStatusHtml = '';
        if (currentInfo.code === 'i') {
          const packDesc = currentInfo.packs.length ? currentInfo.packs.join(', ') : 'Thẻ Pokémon';
          currentStatusHtml = `<span class="hist-status-badge hist-status-in">🟢 Có hàng: ${packDesc}</span>`;
        } else if (currentInfo.code === 'o') {
          currentStatusHtml = `<span class="hist-status-badge hist-status-out">🔴 Hết hàng</span>`;
        } else if (currentInfo.code === 'n') {
          currentStatusHtml = `<span class="hist-status-badge hist-status-none">⚪ Không bán thẻ Pokémon</span>`;
        } else {
          currentStatusHtml = `<span class="hist-status-badge hist-status-u">🔘 Chưa có dữ liệu gần đây</span>`;
        }

        const summaryBox = `
          <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;padding:12px 14px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:gap:8px;">
            <div>
              <div style="font-size:0.75rem;color:#64748b;font-weight:700;">TÌNH TRẠNG MỚI NHẤT HIỆN TẠI:</div>
              <div style="margin-top:4px;">${currentStatusHtml}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:0.75rem;color:#64748b;font-weight:700;">THỜI GIAN BÁO CÁO:</div>
              <div style="font-size:0.85rem;font-weight:800;color:#2563eb;margin-top:2px;">${currentInfo.timeAgo || 'Chưa rõ'}</div>
              <div style="font-size:0.72rem;color:#94a3b8;">${currentInfo.reported_at || ''}</div>
            </div>
          </div>
        `;

        let timelineList = Array.isArray(history) ? [...history] : [];

        // Nếu timeline từ subcollection chưa có bản ghi hiện tại nhưng cửa hàng đang có trạng thái (có hàng / hết hàng)
        if (currentInfo && (currentInfo.code === 'i' || currentInfo.code === 'o' || currentInfo.timestamp > 0)) {
          const exists = timelineList.some(item => (currentInfo.timestamp > 0 && Math.abs((item.timestamp || 0) - currentInfo.timestamp) < 300));
          if (!exists) {
            timelineList.unshift({
              id: 'current_realtime',
              status: currentInfo.code === 'i' ? 'in-stock' : (currentInfo.code === 'o' ? 'out-of-stock' : 'not-handled'),
              status_code: currentInfo.code,
              status_label: currentInfo.code === 'i' ? '🟢 Có hàng (Trạng thái hiện tại)' : (currentInfo.code === 'o' ? '🔴 Hết hàng' : '⚪ Không bán'),
              note: currentInfo.packs.length ? currentInfo.packs.join(', ') : 'Ghi nhận trực tiếp Firestore',
              user: 'Cộng đồng Poketan Osaka',
              who: currentInfo.confirms ? `${currentInfo.confirms} xác nhận` : '',
              onsite: currentInfo.onsite,
              timestamp: currentInfo.timestamp,
              formatted_time: (currentInfo.reported_at && currentInfo.reported_at !== '-') ? currentInfo.reported_at : ''
            });
          }
        }

        if (timelineList.length === 0) {
          if (bodyEl) {
            bodyEl.innerHTML = `
              ${summaryBox}
              <div style="background:white;border:1px dashed #cbd5e1;border-radius:10px;padding:24px;text-align:center;color:#475569;">
                <div style="font-size:1.8rem;margin-bottom:6px;">📋</div>
                <div style="font-weight:700;font-size:0.9rem;color:#0f172a;margin-bottom:4px;">Chưa có chi tiết từng lượt báo cáo cũ trên Firestore</div>
                <div style="font-size:0.78rem;color:#64748b;line-height:1.5;">
                  Cửa hàng này hiện được ghi nhận qua trạng thái tổng hợp mới nhất từ cộng đồng Poketan.
                </div>
              </div>
            `;
          }
          if (footerEl) footerEl.innerText = `Dữ liệu trạng thái tổng hợp hệ thống`;
          return;
        }

        if (footerEl) footerEl.innerText = `Tìm thấy ${timelineList.length} lượt báo cáo lịch sử từ cộng đồng`;

        let html = `
          ${summaryBox}
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:0.78rem;font-weight:800;color:#475569;">TIMELINE LỊCH SỬ CÁC LƯỢT BÁO CÁO</span>
            <span style="font-size:0.75rem;color:#2563eb;font-weight:700;">Tổng cộng: ${timelineList.length} lượt</span>
          </div>
          <div class="hist-timeline">
        `;

        for (const item of timelineList) {
          const itemTimeAgo = item.timestamp ? formatTimeAgo(item.timestamp) : 'Chưa rõ';
          let itemClass = 'hist-none';
          let badgeClass = 'hist-status-none';
          if (item.status_code === 'i') {
            itemClass = 'hist-in';
            badgeClass = 'hist-status-in';
          } else if (item.status_code === 'o') {
            itemClass = 'hist-out';
            badgeClass = 'hist-status-out';
          }

          let dateStr = item.formatted_time || '';
          if (item.timestamp && !dateStr) {
            const d = new Date(item.timestamp * 1000);
            dateStr = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) + ' ' +
                      d.toLocaleDateString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit' });
          }

          const onsiteBadge = item.onsite ? `<span class="hist-badge-onsite">📍 Xác nhận tại quán (GPS)</span>` : '';
          const userStr = item.user || 'Người dùng ẩn danh';
          const whoStr = item.who ? `[${item.who}]` : '';

          html += `
            <div class="hist-item ${itemClass}">
              <div class="hist-header">
                <span class="hist-status-badge ${badgeClass}">${item.status_label}</span>
                <span class="hist-time-ago">⏱ ${itemTimeAgo}</span>
              </div>
              ${item.note ? `<div class="hist-note">📝 <b>Ghi chú / Sản phẩm:</b> ${item.note}</div>` : ''}
              <div class="hist-meta">
                <span style="font-weight:600;display:flex;align-items:center;gap:6px;">
                  👤 ${userStr} <span style="color:#94a3b8;font-size:0.7rem;">${whoStr}</span>
                  ${onsiteBadge}
                </span>
                <span class="hist-timestamp">${dateStr}</span>
              </div>
            </div>
          `;
        }

        html += `</div>`;
        if (bodyEl) bodyEl.innerHTML = html;

      } catch (err) {
        console.error("Error loading store history:", err);
        if (bodyEl) {
          bodyEl.innerHTML = `
            <div style="text-align:center;padding:30px;color:#ef4444;">
              <div style="font-size:1.8rem;margin-bottom:8px;">⚠️</div>
              <b>Lỗi kết nối khi tải lịch sử cửa hàng</b>
              <div style="font-size:0.8rem;color:#64748b;margin-top:6px;">${err.message}</div>
            </div>
          `;
        }
      }
    }
    window.openStoreHistoryModal = openStoreHistoryModal;

    function viewStoreOnMap() {
      closeStoreHistoryModal();
      if (currentFocusedStoreId) {
        focusStore(currentFocusedStoreId, true);
      }
    }
    window.viewStoreOnMap = viewStoreOnMap;

    function closeStoreHistoryModal() {
      const modal = document.getElementById('store-history-modal');
      if (modal) modal.style.display = 'none';
    }
    window.closeStoreHistoryModal = closeStoreHistoryModal;

    // Handle ESC key to close open modals
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const histModal = document.getElementById('store-history-modal');
        if (histModal && histModal.style.display !== 'none') {
          closeStoreHistoryModal();
          return;
        }
        const mapModal = document.getElementById('map-settings-modal');
        if (mapModal && mapModal.style.display !== 'none') {
          toggleMapSettingsModal();
          return;
        }
        const notifModal = document.getElementById('notif-settings-modal');
        if (notifModal && notifModal.style.display !== 'none') {
          toggleNotifSettingsModal();
          return;
        }
      }
    });

    function handleStatusQuickSelect(val) {
      if (val === 'custom') {
        toggleMapSettingsModal();
        return;
      }
      applyPreset(val);
    }
    window.handleStatusQuickSelect = handleStatusQuickSelect;

    function setChain(chain) {
      currentChain = chain;
      const chainSelect = document.getElementById('chain-select');
      if (chainSelect) chainSelect.value = chain;
      renderUI();
      saveSettings();
    }
    window.setChain = setChain;

    function setSortMode(mode) {
      sortMode = mode;
      const sortSelect = document.getElementById('sort-select');
      if (sortSelect) sortSelect.value = mode;
      if (mode === 'nearest' && userLat === null) {
        requestUserLocation(true);
      } else {
        renderUI();
      }
      saveSettings();
    }
    window.setSortMode = setSortMode;

    document.getElementById('search-input').addEventListener('input', (e) => {
      currentQuery = e.target.value;
      renderUI();
    });

    // 10. DEDICATED CALENDAR LOGIC
    let showExpired = false;
    let knownCalendarEventIds = null;
    let calSearchQuery = '';
    let calTypeFilter = '';
    let calStatusFilter = 'active';

    async function loadCalendar() {
      try {
        const res = await fetch('/api/calendar?include_expired=true');
        calendarEvents = await res.json();
        
        const activeEvents = calendarEvents.filter(e => !e.is_expired);
        const expiredEvents = calendarEvents.filter(e => e.is_expired);
        const openEvents = calendarEvents.filter(e => e.category === 'OPEN');
        const upcomingEvents = calendarEvents.filter(e => e.category === 'UPCOMING');

        document.getElementById('menu-cal-count').innerText = `${activeEvents.length} Đang mở`;
        document.getElementById('cal-stat-open').innerText = `🟢 ${openEvents.length} Đang nhận đơn`;
        document.getElementById('cal-stat-upcoming').innerText = `🟡 ${upcomingEvents.length} Sắp mở`;
        document.getElementById('cal-stat-expired').innerText = `⏳ ${expiredEvents.length} Đã quá hạn`;
        document.getElementById('expired-divider-label').innerText = `── CÁC ĐỢT ĐÃ HẾT HẠN ĐĂNG KÝ (${expiredEvents.length}) ──`;

        if (knownCalendarEventIds !== null) {
          const newEvents = calendarEvents.filter(e => !knownCalendarEventIds.has(e.id));
          if (newEvents.length > 0) {
            newEvents.forEach(e => {
              showCalendarToast(e);
            });
          }
        }
        knownCalendarEventIds = new Set(calendarEvents.map(e => e.id));

        renderCalendar();
      } catch (e) {
        console.error("Calendar Load Error:", e);
      }
    }

    function showCalendarToast(event) {
      if (!notifSettings.notifyLottery) return;

      playChime();

      if (notifSettings.pushEnabled && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification("🎉 QUẢN TRỊ VIÊN VỪA ĐĂNG ĐỢT BỐC THĂM MỚI!", {
            body: `${event.title} (${event.type_label})\nSản phẩm: ${event.products.join(', ')}\n${event.category_label}`,
            icon: "https://poketan.jp/apple-touch-icon.png"
          });
        } catch(e) {}
      }

      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.style.borderLeftColor = '#2563eb';
      toast.innerHTML = `
        <div class="toast-header" style="color:#2563eb;">
          <span>🎉 LỊCH BỐC THĂM MỚI TỪ QUẢN TRỊ!</span>
          <span class="toast-time">Vừa đăng</span>
        </div>
        <div class="toast-body">${event.title}</div>
        <div style="font-size:0.78rem;color:#0284c7;font-weight:700;">${event.type_label}</div>
        <div class="toast-pack" style="background:#dbeafe;color:#1e40af;">🎁 ${event.products.join(', ')}</div>
        <div style="font-size:0.75rem;color:#64748b;">${event.category_label}</div>
        <button class="toast-btn" style="background:#2563eb;" onclick="navigateMenu('calendar')">Xem lịch ngay 📅</button>
      `;

      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 400);
      }, 12000);
    }

    function handleCalSearch(val) {
      calSearchQuery = val.trim().toLowerCase();
      renderCalendar();
    }
    window.handleCalSearch = handleCalSearch;

    function setCalTypeFilter(type) {
      calTypeFilter = type;
      document.querySelectorAll('#cal-type-chips .cal-chip').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      renderCalendar();
    }
    window.setCalTypeFilter = setCalTypeFilter;

    function setCalStatusFilter(status) {
      calStatusFilter = status;
      document.querySelectorAll('#cal-status-chips .cal-chip').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      if (status === 'all') {
        showExpired = true;
      }
      renderCalendar();
    }
    window.setCalStatusFilter = setCalStatusFilter;

    function toggleExpiredSection() {
      showExpired = !showExpired;
      renderCalendar();
      saveSettings();
    }
    window.toggleExpiredSection = toggleExpiredSection;

    setInterval(loadCalendar, 30000);

    function renderEventCard(e) {
      let badgeClass = 'cal-open';
      if (e.category === 'UPCOMING') badgeClass = 'cal-upcoming';
      else if (e.is_expired) badgeClass = 'cal-closed';

      const isChecked = localStorage.getItem('applied_' + e.id) === '1';

      const linkHtml = e.url 
        ? `<a href="${e.url}" target="_blank" class="cal-link-btn">Đăng ký tham gia ↗</a>` 
        : `<span style="font-size:0.75rem;color:#94a3b8;">Đăng ký tại cửa hàng / App riêng</span>`;

      const cardStyle = e.is_expired ? 'opacity: 0.65; background: #f8fafc; border-style: dashed;' : '';

      return `
        <div class="cal-card" style="${cardStyle}">
          <div class="cal-top">
            <span class="cal-status-badge ${badgeClass}">${e.category_label}</span>
            <span class="cal-type">${e.type_label}</span>
          </div>
          <div class="cal-title">${e.title}</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;">
            ${e.products.map(p => `<span class="pack-tag" style="background:#e0f2fe;color:#0369a1;border-color:#bae6fd;">📦 ${p}</span>`).join('')}
          </div>
          ${e.note ? `<div class="cal-note">${e.note}</div>` : ''}
          <div class="cal-actions">
            ${linkHtml}
            <label class="cal-checkbox-label">
              <input type="checkbox" onchange="toggleApplied('${e.id}', this.checked)" ${isChecked ? 'checked' : ''} />
              <span>Đã nộp đơn</span>
            </label>
          </div>
        </div>
      `;
    }

    function renderCalendar() {
      const grid = document.getElementById('calendar-cards-grid');
      const expiredGrid = document.getElementById('calendar-expired-grid');
      const expiredWrapper = document.getElementById('calendar-expired-wrapper');
      const toggleBtn = document.getElementById('cal-header-toggle-expired');

      if (!calendarEvents.length) {
        grid.innerHTML = '<div style="padding:40px;text-align:center;grid-column:1/-1;">Không có sự kiện nào.</div>';
        return;
      }

      let filtered = calendarEvents.filter(e => {
        if (calTypeFilter && e.type !== calTypeFilter) return false;
        if (calSearchQuery) {
          const matchTitle = (e.title || '').toLowerCase().includes(calSearchQuery);
          const matchProd = (e.products || []).some(p => p.toLowerCase().includes(calSearchQuery));
          const matchNote = (e.note || '').toLowerCase().includes(calSearchQuery);
          if (!matchTitle && !matchProd && !matchNote) return false;
        }
        return true;
      });

      const activeEvents = filtered.filter(e => !e.is_expired);
      const expiredEvents = filtered.filter(e => e.is_expired);

      if (activeEvents.length > 0) {
        grid.innerHTML = activeEvents.map(renderEventCard).join('');
      } else {
        grid.innerHTML = '<div style="padding:40px;text-align:center;color:#94a3b8;grid-column:1/-1;">Không có đợt bốc thăm nào đang mở phù hợp bộ lọc.</div>';
      }

      if (expiredEvents.length > 0 && showExpired) {
        expiredWrapper.style.display = 'block';
        expiredGrid.innerHTML = expiredEvents.map(renderEventCard).join('');
        toggleBtn.innerText = `👆 Ẩn ${expiredEvents.length} sự kiện quá hạn`;
      } else {
        expiredWrapper.style.display = 'none';
        toggleBtn.innerText = `👁️ Xem ${expiredEvents.length} sự kiện quá hạn`;
      }
    }

    function toggleApplied(id, checked) {
      if (checked) {
        localStorage.setItem('applied_' + id, '1');
      } else {
        localStorage.removeItem('applied_' + id);
      }
    }
    window.toggleApplied = toggleApplied;

    // 11. ENGINE INITIALIZATION
    async function startRealtimeEngine() {
      // Khôi phục vị trí cache gần nhất để không bị nhảy bản đồ sang nơi khác
      try {
        const cachedLat = sessionStorage.getItem('bawui_last_lat');
        const cachedLng = sessionStorage.getItem('bawui_last_lng');
        const cachedAcc = sessionStorage.getItem('bawui_last_acc');
        if (cachedLat && cachedLng) {
          userLat = parseFloat(cachedLat);
          userLng = parseFloat(cachedLng);
          userAccuracy = cachedAcc ? parseFloat(cachedAcc) : 50;
          renderUserLocation(false);
        }
      } catch(e) {}

      requestUserLocation(false);
      loadCalendar();

      // Immediately apply saved settings from localStorage (if any) to prevent layout shift
      try {
        const localSettings = JSON.parse(localStorage.getItem('bawui_user_settings') || 'null');
        if (localSettings) applyLoadedSettings(localSettings);
      } catch (e) {}

      // Immediately synchronize menu with the current browser URL on page load
      const startRoute = getRouteFromUrl();
      syncMenuAndRoute(startRoute, false);

      // Fetch store metadata, config, cold status, hot status, and persistent settings.json concurrently
      const [storesRes, configRes, coldRes, hotRes, settingsRes] = await Promise.all([
        fetch('/api/stores_data'),
        fetch('/api/config'),
        fetch('/api/cold_status').catch(() => ({ json: () => ({}) })),
        fetch('/api/hot_status').catch(() => ({ json: () => ({}) })),
        fetch('/api/settings').catch(() => ({ json: () => ({}) }))
      ]);
      storesDict = await storesRes.json();
      configData = await configRes.json();
      try {
        const serverSettings = await settingsRes.json();
        if (serverSettings && typeof serverSettings === 'object') {
          applyLoadedSettings(serverSettings);
        }
      } catch (e) {}
      try {
        coldStatus = await coldRes.json();
        coldLoaded = true;
      } catch(e) {
        coldStatus = {};
      }
      try {
        hotStatus = await hotRes.json();
        previousRawStatus = { ...hotStatus };
      } catch(e) {
        hotStatus = {};
        previousRawStatus = {};
      }

      latestMergedStatus = { ...coldStatus, ...hotStatus };
      renderUI();

      const checkSdk = setInterval(() => {
        if (window.FirebaseInit) {
          clearInterval(checkSdk);
          setupFirestoreListener();
        }
      }, 50);
    }

    function setupFirestoreListener() {
      const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
      
      const app = initializeApp({
        apiKey: configData.apiKey,
        projectId: configData.projectId
      });
      const db = initializeFirestore(app, {});

      onSnapshot(doc(db, 'status', 'osaka'), (docSnap) => {
        if (!docSnap.exists()) return;
        const nextData = docSnap.data();
        hotStatus = nextData;

        const currentInStockIds = new Set();
        for (const [k, v] of Object.entries(nextData)) {
          if (typeof v === 'string' && v.length > 0 && v[0].toLowerCase() === 'i') {
            currentInStockIds.add(k);
          }
        }

        if (previousRawStatus !== null) {
          for (const [k, v] of Object.entries(nextData)) {
            if (k.endsWith('_c')) continue;
            const prevV = previousRawStatus[k];
            if (prevV !== v) {
              const store = storesDict[k] || { id: k, name: 'Cửa hàng', chain: 'other', address: '', lat: null, lng: null };
              const info = decodeStatus(v, nextData[k + '_c']);
              if (info) {
                if (info.code === 'i') {
                  showToast(store, info);
                  setTimeout(() => {
                    const card = document.getElementById('card-' + k);
                    if (card) card.classList.add('just-updated');
                  }, 300);
                } else if (info.code === 'o') {
                  showOutOfStockToast(store, info);
                } else if (info.code === 'n') {
                  showNotHandledToast(store, info);
                }
              }
            }
          }
        }

        previousRawStatus = { ...nextData };
        previousInStockIds = currentInStockIds;

        latestMergedStatus = { ...coldStatus, ...hotStatus };
        renderUI();
      }, (err) => {
        console.error("Firestore Listen Error:", err);
      });
    }

    // ======================================
    // MOBILE UI: Bottom Nav, Swipe, Sidebar Toggle
    // ======================================
    const isMobileViewport = () => window.innerWidth <= 768;
    let currentMobileTab = 'map'; // 'map' | 'list' | 'calendar'

    function mobileNavTo(tab) {
      if (!isMobileViewport()) {
        // On desktop, just use existing navigation
        if (tab === 'calendar') navigateMenu('calendar');
        else if (tab === 'settings') toggleNotifSettingsModal();
        else navigateMenu('map');
        return;
      }

      const sidebar = document.getElementById('sidebar');
      const btns = document.querySelectorAll('.mobile-nav-btn');
      btns.forEach(b => b.classList.remove('active'));

      if (tab === 'map') {
        currentMobileTab = 'map';
        navigateMenu('map');
        sidebar.classList.remove('mobile-visible');
        document.getElementById('mob-nav-map').classList.add('active');
        setTimeout(() => map.invalidateSize(), 150);
      } else if (tab === 'list') {
        currentMobileTab = 'list';
        navigateMenu('map'); // ensure we're on map view (which contains sidebar)
        sidebar.classList.add('mobile-visible');
        document.getElementById('mob-nav-list').classList.add('active');
      } else if (tab === 'calendar') {
        currentMobileTab = 'calendar';
        sidebar.classList.remove('mobile-visible');
        navigateMenu('calendar');
        document.getElementById('mob-nav-cal').classList.add('active');
      } else if (tab === 'settings') {
        document.getElementById('mob-nav-settings').classList.add('active');
        toggleNotifSettingsModal();
        // Restore previous active tab after short delay
        setTimeout(() => {
          document.getElementById('mob-nav-settings').classList.remove('active');
          const prevBtn = document.getElementById('mob-nav-' + (currentMobileTab === 'list' ? 'list' : currentMobileTab === 'calendar' ? 'cal' : 'map'));
          if (prevBtn) prevBtn.classList.add('active');
        }, 300);
        return;
      }
    }
    window.mobileNavTo = mobileNavTo;

    // Sync mobile bottom nav badges with stock counts
    function syncMobileBadges() {
      const mobStock = document.getElementById('mob-badge-stock');
      const mobCal = document.getElementById('mob-badge-cal');
      const desktopStock = document.getElementById('menu-stock-count');
      const desktopCal = document.getElementById('menu-cal-count');
      if (mobStock && desktopStock) {
        const match = desktopStock.textContent.match(/(\d+)/);
        if (match) mobStock.textContent = match[1];
      }
      if (mobCal && desktopCal) {
        const match = desktopCal.textContent.match(/(\d+)/);
        if (match) mobCal.textContent = match[1];
      }
    }

    // Patch existing syncMenuAndRoute to also sync mobile nav state
    const _origSyncMenuAndRoute = syncMenuAndRoute;
    // Override will be applied after syncMenuAndRoute is available (it's already defined above)

    // Observe DOM changes on desktop badge to sync mobile badges
    const stockBadgeEl = document.getElementById('menu-stock-count');
    if (stockBadgeEl) {
      const observer = new MutationObserver(syncMobileBadges);
      observer.observe(stockBadgeEl, { childList: true, characterData: true, subtree: true });
    }
    const calBadgeEl = document.getElementById('menu-cal-count');
    if (calBadgeEl) {
      const observer = new MutationObserver(syncMobileBadges);
      observer.observe(calBadgeEl, { childList: true, characterData: true, subtree: true });
    }
    // Initial sync
    syncMobileBadges();

    // ======================================
    // TOUCH SWIPE GESTURES
    // ======================================
    let touchStartX = 0;
    let touchStartY = 0;
    let touchStartTime = 0;
    const SWIPE_THRESHOLD = 60;
    const SWIPE_MAX_TIME = 400;
    const SWIPE_MAX_VERTICAL = 80;

    // Sidebar swipe: swipe left on sidebar to close, swipe right on map edge to open
    document.addEventListener('touchstart', (e) => {
      if (!isMobileViewport()) return;
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = Date.now();
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
      if (!isMobileViewport()) return;
      const touchEndX = e.changedTouches[0].clientX;
      const touchEndY = e.changedTouches[0].clientY;
      const deltaX = touchEndX - touchStartX;
      const deltaY = touchEndY - touchStartY;
      const elapsed = Date.now() - touchStartTime;

      // Only process horizontal swipes
      if (elapsed > SWIPE_MAX_TIME) return;
      if (Math.abs(deltaY) > SWIPE_MAX_VERTICAL) return;
      if (Math.abs(deltaX) < SWIPE_THRESHOLD) return;

      const sidebar = document.getElementById('sidebar');
      // Check if we're in map/list view (not calendar)
      const viewStores = document.getElementById('view-stores-mode');
      if (!viewStores || !viewStores.classList.contains('active')) return;

      if (deltaX < -SWIPE_THRESHOLD && sidebar.classList.contains('mobile-visible')) {
        // Swipe left → hide sidebar (show map)
        mobileNavTo('map');
      } else if (deltaX > SWIPE_THRESHOLD && !sidebar.classList.contains('mobile-visible')) {
        // Swipe right from left edge → show sidebar (store list)
        if (touchStartX < 40) {
          mobileNavTo('list');
        }
      }
    }, { passive: true });

    // Modal swipe-down to close
    document.addEventListener('touchstart', function(e) {
      if (!isMobileViewport()) return;
      const modal = e.target.closest('.modal-overlay');
      if (!modal) return;
      modal._swipeStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', function(e) {
      if (!isMobileViewport()) return;
      const modal = e.target.closest('.modal-overlay');
      if (!modal || !modal._swipeStartY) return;
      const deltaY = e.changedTouches[0].clientY - modal._swipeStartY;
      if (deltaY > 100) {
        // Swipe down → close modal
        modal.style.display = 'none';
      }
      modal._swipeStartY = null;
    }, { passive: true });

    // On resize: clean up mobile state if switching to desktop
    window.addEventListener('resize', () => {
      const sidebar = document.getElementById('sidebar');
      if (!isMobileViewport()) {
        sidebar.classList.remove('mobile-visible');
      } else {
        // Ensure map is properly sized
        setTimeout(() => map.invalidateSize(), 200);
      }
    });

    // ======================================
    // DESKTOP SIDEBAR COLLAPSE / EXPAND TOGGLE
    // ======================================
    let isDesktopSidebarCollapsed = false;

    function toggleDesktopSidebar() {
      if (isMobileViewport()) {
        mobileNavTo(currentMobileTab === 'list' ? 'map' : 'list');
        return;
      }
      isDesktopSidebarCollapsed = !isDesktopSidebarCollapsed;
      const sidebar = document.getElementById('sidebar');
      const view = document.getElementById('view-stores-mode');
      const edgeBtn = document.getElementById('sidebar-toggle-edge');
      const mapBtnText = document.getElementById('btn-toggle-sidebar-map-text');
      const headerBtn = document.getElementById('btn-hide-sidebar-header');

      if (isDesktopSidebarCollapsed) {
        sidebar.classList.add('desktop-collapsed');
        view.classList.add('sidebar-hidden');
        if (edgeBtn) {
          edgeBtn.innerHTML = '▶';
          edgeBtn.title = 'Hiện danh sách cửa hàng';
        }
        if (headerBtn) headerBtn.textContent = '▶';
      } else {
        sidebar.classList.remove('desktop-collapsed');
        view.classList.remove('sidebar-hidden');
        if (edgeBtn) {
          edgeBtn.innerHTML = '◀';
          edgeBtn.title = 'Ẩn danh sách cửa hàng';
        }
        if (headerBtn) headerBtn.textContent = '◀ Ẩn';
      }

      // Smoothly trigger Leaflet map resize
      setTimeout(() => {
        if (map) map.invalidateSize();
      }, 300);
    }
    window.toggleDesktopSidebar = toggleDesktopSidebar;

    // Keyboard shortcut: Press '[' or ']' to toggle sidebar
    document.addEventListener('keydown', (e) => {
      // Don't trigger if user is typing in an input
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
      if (e.key === '[' || e.key === ']') {
        toggleDesktopSidebar();
      }
    });

    // On initial load: set mobile state if needed
    if (isMobileViewport()) {
      const sidebar = document.getElementById('sidebar');
      sidebar.classList.remove('mobile-visible');
      currentMobileTab = 'map';
      setTimeout(() => { if (map) map.invalidateSize(); }, 300);
    }

    startRealtimeEngine();
  </script>
</body>
</html>
    """


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
