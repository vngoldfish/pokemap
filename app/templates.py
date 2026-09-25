"""
HTML Templates and Page Renderers for BAWUI POKE APP
Separated Multi-Page Architecture (MPA):
- Map Page: GET / and GET /map (Leaflet map, Map filter toolbar, Map filter modal)
- Notification Page: GET /thongbao and GET /stores (Report list, Distance radius filter, 6-level filter modal)
All navigated via standard HTTP link routing (<a href="...">) without hidden layer stacking.
"""

def get_shared_head(title: str, include_leaflet: bool = False) -> str:
    leaflet_tags = """
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  
  <!-- Leaflet MarkerCluster -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
""" if include_leaflet else ""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  {leaflet_tags}
  <!-- Font Inter -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  
  <!-- Firebase JS SDK for real-time Firestore sync -->
  <script type="module">
    import {{ initializeApp }} from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js';
    import {{ initializeFirestore, doc, onSnapshot }} from 'https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js';
    window.FirebaseInit = {{ initializeApp, initializeFirestore, doc, onSnapshot }};
  </script>
"""


SHARED_BASE_CSS = """
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

    /* 1. TOP HEADER */
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
      cursor: pointer;
      text-decoration: none;
    }

    .brand-pin-icon {
      width: 22px;
      height: 22px;
      background: #ef4444;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      display: inline-block;
      position: relative;
      box-shadow: 0 2px 4px rgba(239, 68, 68, 0.4);
    }
    .brand-pin-icon::after {
      content: '';
      width: 8px;
      height: 8px;
      background: white;
      position: absolute;
      border-radius: 50%;
      top: 7px;
      left: 7px;
    }

    .brand-title-text {
      font-size: 1.15rem;
      font-weight: 900;
      color: #0f172a;
      letter-spacing: -0.5px;
    }

    .location-pill {
      display: inline-flex;
      flex-direction: column;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 3px 8px;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .location-pill:hover {
      background: #e2e8f0;
    }
    .loc-main-title {
      font-size: 0.72rem;
      font-weight: 800;
      color: #1e293b;
      display: flex;
      align-items: center;
      gap: 3px;
    }
    .loc-sub-title {
      font-size: 0.58rem;
      color: #64748b;
      font-weight: 600;
      margin-top: -1px;
    }

    .header-menu-btn {
      width: 34px;
      height: 34px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
      color: #334155;
      font-size: 1.1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      transition: background 0.15s;
    }
    .header-menu-btn:hover {
      background: #f1f5f9;
    }

    /* FOOTER NAVIGATION BAR */
    #poketan-footer {
      height: 56px;
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: space-around;
      padding: 0 4px calc(env(safe-area-inset-bottom, 0px) / 2);
      z-index: 1000;
      flex-shrink: 0;
      box-shadow: 0 -2px 10px rgba(0,0,0,0.04);
      position: relative;
    }

    .footer-tab-btn {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: none;
      border: none;
      color: #64748b;
      font-size: 0.65rem;
      font-weight: 700;
      cursor: pointer;
      padding: 4px 0;
      gap: 2px;
      text-decoration: none;
      -webkit-tap-highlight-color: transparent;
      transition: all 0.15s ease;
    }
    .footer-tab-btn .tab-icon {
      font-size: 1.22rem;
      line-height: 1;
    }
    .footer-tab-btn .tab-label {
      font-size: 0.62rem;
    }
    .footer-tab-btn.active {
      color: #2563eb;
      font-weight: 900;
    }
    .footer-tab-btn.active .tab-icon {
      transform: scale(1.1);
    }

    .gachi-meguri-wrap {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      margin-top: -16px;
      text-decoration: none;
    }
    .gachi-meguri-btn {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, #f59e0b, #d97706);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(217, 119, 6, 0.4);
      border: 3px solid #ffffff;
      transition: transform 0.15s ease;
    }
    .gachi-meguri-wrap:active .gachi-meguri-btn {
      transform: scale(0.92);
    }
    .gachi-meguri-btn .btn-icon {
      font-size: 1.35rem;
      color: #ffffff;
    }
    .gachi-meguri-label {
      font-size: 0.6rem;
      font-weight: 800;
      color: #d97706;
      margin-top: 1px;
      white-space: nowrap;
    }

    /* BADGES, CHIPS & STATUS DOTS */
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

    .card-badge {
      display: inline-flex;
      align-items: center;
      border-radius: 6px;
      padding: 2px 7px;
      font-size: 0.68rem;
      font-weight: 800;
      white-space: nowrap;
    }
    .badge-in { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .badge-out { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .badge-recent { background: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }
    .badge-none { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

    .report-count-tag {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-weight: 700;
    }
    .tag-green { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
    .tag-red { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

    /* MODAL BASE STYLES */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 5000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 12px;
    }
    .modal-overlay.open {
      display: flex;
    }
    .modal-card {
      background: #ffffff;
      border-radius: 16px;
      width: 100%;
      max-width: 480px;
      max-height: 88vh;
      max-height: 88dvh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
      overflow: hidden;
      animation: modalSlideUp 0.22s ease-out;
    }
    @keyframes modalSlideUp {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .modal-header {
      padding: 14px 16px;
      border-bottom: 1px solid #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .modal-header h3 {
      font-size: 0.98rem;
      font-weight: 800;
      color: #0f172a;
    }
    .modal-close-btn {
      background: none;
      border: none;
      font-size: 1.15rem;
      color: #64748b;
      cursor: pointer;
      padding: 2px 6px;
      font-weight: 700;
    }
    .modal-body {
      padding: 14px 16px;
      overflow-y: auto;
      flex: 1;
      -webkit-overflow-scrolling: touch;
    }
    .filter-group-title {
      font-size: 0.76rem;
      font-weight: 800;
      color: #334155;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .filter-options-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
      margin-bottom: 16px;
    }
    .filter-options-grid-3 {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      margin-bottom: 16px;
    }
    .filter-option-btn {
      padding: 8px 10px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      font-size: 0.76rem;
      font-weight: 700;
      color: #475569;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      text-align: left;
      transition: all 0.15s ease;
    }
    .filter-option-btn:hover {
      background: #f1f5f9;
      border-color: #cbd5e1;
    }
    .filter-option-btn.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      font-weight: 800;
      box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
    }

    .btn-reset-filter {
      flex: 1;
      padding: 9px 12px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      font-weight: 800;
      font-size: 0.8rem;
      color: #475569;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .btn-reset-filter:hover {
      background: #e2e8f0;
      color: #1e293b;
    }
    .btn-apply-filter {
      flex: 2;
      padding: 9px 16px;
      background: #2563eb;
      border: none;
      border-radius: 10px;
      font-weight: 800;
      font-size: 0.82rem;
      color: #ffffff;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }
    .btn-apply-filter:hover {
      background: #1d4ed8;
    }

    /* TOAST ALERTS */
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

    /* AREA MODAL SECTION STYLES */
    .area-region-section {
      margin-bottom: 12px;
    }
    .area-region-title {
      font-size: 0.78rem;
      font-weight: 800;
      color: #1e293b;
      margin-bottom: 6px;
    }
    .area-chips-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .area-chip {
      padding: 6px 12px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 700;
      color: #334155;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .area-chip:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }
    .area-chip.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      font-weight: 800;
      box-shadow: 0 1px 4px rgba(59, 130, 246, 0.25);
    }

    /* LOADING SCREEN */
    #loading-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: #ffffff;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #1e293b;
      transition: opacity 0.2s ease;
    }
    .spinner {
      width: 38px;
      height: 38px;
      border: 3px solid #e2e8f0;
      border-top-color: #3b82f6;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
"""


def render_shared_header() -> str:
    return """
  <!-- 1. TOP HEADER -->
  <header id="poketan-header">
    <div class="header-brand-group">
      <a href="/map" class="brand-logo-area">
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
"""


def render_shared_footer(active_page: str) -> str:
    map_active = " active" if active_page == "map" else ""
    list_active = " active" if active_page == "thongbao" else ""
    return f"""
  <!-- 5. FOOTER BOTTOM NAVIGATION -->
  <footer id="poketan-footer">
    <a href="/map" class="footer-tab-btn{map_active}" id="f-tab-map" title="地図 / Bản đồ">
      <span class="tab-icon">🗺️</span>
      <span class="tab-label">地図</span>
    </a>

    <a href="/thongbao" class="footer-tab-btn{list_active}" id="f-tab-list" title="一覧 / Danh sách thông báo">
      <span class="tab-icon">📋</span>
      <span class="tab-label">一覧</span>
    </a>

    <!-- Center Elevated Button: Gachi Meguri (⚡) -->
    <a href="/map?hunt=1" class="gachi-meguri-wrap" title="ガチ巡り (在庫あり店舗へ直行)">
      <div class="gachi-meguri-btn">
        <span class="btn-icon">⚡</span>
      </div>
      <span class="gachi-meguri-label">ガチ巡り</span>
    </a>

    <button type="button" class="footer-tab-btn" id="f-tab-search" onclick="openSearchModal()" title="さがす / Tìm kiếm">
      <span class="tab-icon">🔍</span>
      <span class="tab-label">さがす</span>
    </button>

    <button type="button" class="footer-tab-btn" id="f-tab-bulletin" onclick="openBulletinModal()" title="掲示板 / Bảng tin">
      <span class="tab-icon">💬</span>
      <span class="tab-label">掲示板</span>
    </button>

    <button type="button" class="footer-tab-btn" id="f-tab-settings" onclick="openSettingsModal()" title="設定 / Cài đặt">
      <span class="tab-icon">⚙️</span>
      <span class="tab-label">設定</span>
    </button>
  </footer>
"""


SHARED_MODALS_HTML = """
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
      <div class="modal-body" style="font-size:0.82rem; padding:16px; overflow-y:auto;">
        
        <div style="margin-bottom:14px; background:#f0f9ff; border:1px solid #bae6fd; border-radius:10px; padding:10px 12px; font-size:0.75rem; color:#0369a1;">
          💡 <b>Hướng dẫn nhận thông báo Telegram 24/7:</b>
          <ol style="margin-top:4px; padding-left:16px; line-height:1.5;">
            <li>Mở Telegram tìm bot <b>@BotFather</b> để tạo bot mới và lấy <code>Bot Token</code>.</li>
            <li>Tạo một nhóm chat, thêm bot vừa tạo vào nhóm và lấy <code>Chat ID</code> (hoặc ID tài khoản cá nhân).</li>
            <li>Bật công tắc bên dưới và bấm <b>Lưu cấu hình</b> để hệ thống tự động bắn tin có hàng.</li>
          </ol>
        </div>

        <!-- Công tắc bật/tắt gửi Telegram -->
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:12px 14px; margin-bottom:14px; display:flex; align-items:center; justify-content:space-between;">
          <div>
            <div style="font-weight:800; color:#0f172a; font-size:0.88rem;">Bật đẩy thông báo qua Telegram</div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Tự động gửi tin nhắn báo quán có hàng vào chat/nhóm Telegram</div>
          </div>
          <label style="position:relative; display:inline-block; width:44px; height:24px; margin:0; flex-shrink:0;">
            <input type="checkbox" id="tg-cfg-enabled" onchange="onTelegramToggleChange(this.checked)" style="opacity:0; width:0; height:0;">
            <span style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:#cbd5e1; transition:.3s; border-radius:24px;" id="tg-cfg-slider"></span>
          </label>
        </div>

        <!-- Token & Chat ID -->
        <div style="display:flex; flex-direction:column; gap:10px; margin-bottom:16px;">
          <div>
            <label style="font-weight:800; font-size:0.75rem; color:#334155; display:block; margin-bottom:4px;">Telegram Bot Token:</label>
            <input type="text" id="tg-cfg-token" placeholder="Ví dụ: 123456789:ABCdefGhIJKlmNoPQRstuVWXyz..." style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; font-size:0.8rem; outline:none;" />
          </div>
          <div>
            <label style="font-weight:800; font-size:0.75rem; color:#334155; display:block; margin-bottom:4px;">Telegram Chat ID (Nhóm hoặc Cá nhân):</label>
            <input type="text" id="tg-cfg-chatid" placeholder="Ví dụ: -1001234567890 hoặc 987654321" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; font-size:0.8rem; outline:none;" />
          </div>
        </div>

        <!-- Bộ lọc cảnh báo gửi tin -->
        <div style="border-top:1px dashed #cbd5e1; padding-top:14px; margin-bottom:14px;">
          <div style="font-weight:800; color:#0f172a; font-size:0.82rem; margin-bottom:8px; display:flex; align-items:center; gap:5px;">
            <span>🎯</span> <span>Bộ lọc cảnh báo tin nhắn gửi Telegram:</span>
          </div>

          <!-- Khu vực nhận tin -->
          <div style="margin-bottom:10px;">
            <label style="font-size:0.73rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">📍 Khu vực nhận tin:</label>
            <select id="tg-cfg-region" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.78rem; font-weight:700; color:#1e293b; background:#ffffff;">
              <option value="osaka">📍 Osaka & Kansai (大阪府周辺)</option>
              <option value="tokyo">📍 Tokyo & Kanto (東京都・神奈川)</option>
              <option value="nagoya">📍 Nagoya & Tokai (愛知県・岐阜・三重)</option>
              <option value="all">🗾 Toàn quốc (全国エリア)</option>
            </select>
          </div>

          <!-- Trạng thái nhận tin -->
          <div style="margin-bottom:10px;">
            <label style="font-size:0.73rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">📊 Trạng thái nhận tin:</label>
            <select id="tg-cfg-status" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.78rem; font-weight:700; color:#1e293b; background:#ffffff;">
              <option value="in">🟢 Chỉ gửi khi có hàng (Khuyên dùng)</option>
              <option value="onsite">📸 Chỉ gửi tin báo tại quán (GPS)</option>
              <option value="recent">★ Gửi cả tin có hàng & từng có hàng</option>
              <option value="all">🌐 Nhận tất cả thông báo (Bao gồm hết hàng)</option>
            </select>
          </div>

          <!-- Lọc chuỗi -->
          <div style="margin-bottom:10px;">
            <label style="font-size:0.73rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">🏢 Chuỗi cửa hàng:</label>
            <select id="tg-cfg-chain" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.78rem; font-weight:700; color:#1e293b; background:#ffffff;">
              <option value="all">🏢 Tất cả các chuỗi</option>
              <option value="conbini">🏪 Tất cả Conbini</option>
              <option value="seven">🏪 7-Eleven</option>
              <option value="lawson">🏪 Lawson</option>
              <option value="familymart">🏪 FamilyMart</option>
              <option value="ministop">🏪 Ministop</option>
              <option value="specialty">🃏 Card Shop chuyên biệt</option>
              <option value="electronics">🎮 Điện máy, GEO, Tsutaya</option>
            </select>
          </div>

          <!-- Độ mới tin báo -->
          <div>
            <label style="font-size:0.73rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">⏱️ Độ tươi mới của tin báo:</label>
            <select id="tg-cfg-time" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.78rem; font-weight:700; color:#1e293b; background:#ffffff;">
              <option value="1">⚡ Siêu mới: Trong vòng 1 giờ</option>
              <option value="3">⏱ Trong vòng 3 giờ</option>
              <option value="6">⏱ Trong vòng 6 giờ</option>
              <option value="24" selected>📅 Trong vòng 24 giờ</option>
              <option value="all">⏳ Toàn bộ thời gian</option>
            </select>
          </div>
        </div>

        <!-- Nút test webhook & kết quả -->
        <div style="margin-top:10px; display:flex; flex-direction:column; gap:6px;">
          <button type="button" onclick="testTelegramWebhook()" id="btn-test-tg" style="width:100%; padding:8px 12px; background:#f0fdf4; border:1px solid #86efac; border-radius:8px; font-weight:800; font-size:0.78rem; color:#166534; cursor:pointer;">
            🔔 Gửi thử tin nhắn test tới Telegram ngay
          </button>
          <div id="tg-test-result" style="display:none; font-size:0.72rem; padding:6px 10px; border-radius:6px; margin-top:4px;"></div>
        </div>

      </div>
      <div style="padding:12px 16px; border-top:1px solid #e2e8f0; background:#f8fafc; display:flex; gap:8px;">
        <button type="button" class="btn-reset-filter" onclick="closeTelegramModal()">
          Đóng
        </button>
        <button type="button" class="btn-apply-filter" onclick="saveTelegramConfig()" id="btn-save-tg" style="background:#0284c7;">
          💾 Lưu cấu hình Telegram
        </button>
      </div>
    </div>
  </div>

  <!-- 6. PREFECTURE & CITY AREA SELECTOR MODAL (なんば周辺 / エリア変更) -->
  <div id="pref-modal" class="modal-overlay" onclick="if(event.target===this) closePrefModal()">
    <div class="modal-card">
      <div class="modal-header">
        <h3>📍 エリアを選択 / Chọn khu vực săn thẻ</h3>
        <button class="modal-close-btn" onclick="closePrefModal()">✕</button>
      </div>
      <div class="modal-body">
        
        <!-- Search area input -->
        <div style="position:relative; margin-bottom:12px;">
          <input type="text" id="area-search-input" placeholder="🔍 Tỉnh thành, ga tàu, khu vực (Osaka, Namba, Tokyo...)" 
                 oninput="filterAreaList(this.value)"
                 style="width:100%; padding:9px 12px; border-radius:10px; border:1px solid #cbd5e1; font-size:0.82rem; font-weight:700; outline:none;" />
        </div>

        <!-- 1. Kansai / Osaka -->
        <div class="area-region-section" data-region="osaka">
          <div class="area-region-title">📍 Kansai / Osaka (大阪府周辺)</div>
          <div class="area-chips-grid">
            <button class="area-chip active" data-pref="osaka" data-city="なんば" onclick="selectCityArea('osaka', 'なんば', 34.6667, 135.5000, 15)">なんば (難波)</button>
            <button class="area-chip" data-pref="osaka" data-city="梅田" onclick="selectCityArea('osaka', '梅田', 34.7024, 135.4959, 15)">梅田 (大阪駅)</button>
            <button class="area-chip" data-pref="osaka" data-city="日本橋" onclick="selectCityArea('osaka', '日本橋', 34.6628, 135.5058, 16)">オタロード (日本橋)</button>
            <button class="area-chip" data-pref="osaka" data-city="天王寺" onclick="selectCityArea('osaka', '天王寺', 34.6472, 135.5140, 14)">天王寺</button>
            <button class="area-chip" data-pref="osaka" data-city="心斎橋" onclick="selectCityArea('osaka', '心斎橋', 34.6750, 135.5005, 15)">心斎橋</button>
            <button class="area-chip" data-pref="osaka" data-city="全域" onclick="selectCityArea('osaka', '大阪全域', 34.6937, 135.5023, 11)">🗾 大阪府全域</button>
          </div>
        </div>

        <!-- 2. Kanto / Tokyo & Kanagawa -->
        <div class="area-region-section" data-region="tokyo" style="margin-top:14px;">
          <div class="area-region-title">🗼 Kanto / Tokyo &amp; Kanagawa (東京都・神奈川)</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="tokyo" data-city="秋葉原" onclick="selectCityArea('tokyo', '秋葉原', 35.6983, 139.7731, 16)">秋葉原 (Card Shop)</button>
            <button class="area-chip" data-pref="tokyo" data-city="新宿" onclick="selectCityArea('tokyo', '新宿', 35.6909, 139.7003, 15)">新宿</button>
            <button class="area-chip" data-pref="tokyo" data-city="渋谷" onclick="selectCityArea('tokyo', '渋谷', 35.6580, 139.7016, 15)">渋谷</button>
            <button class="area-chip" data-pref="tokyo" data-city="池袋" onclick="selectCityArea('tokyo', '池袋', 35.7295, 139.7109, 15)">池袋</button>
            <button class="area-chip" data-pref="tokyo" data-city="東京全域" onclick="selectCityArea('tokyo', '東京全域', 35.6895, 139.6917, 12)">🗼 東京都全域</button>
            <button class="area-chip" data-pref="kanagawa" data-city="横浜" onclick="selectCityArea('kanagawa', '横浜', 35.4437, 139.6380, 14)">横浜</button>
            <button class="area-chip" data-pref="kanagawa" data-city="川崎" onclick="selectCityArea('kanagawa', '川崎', 35.5308, 139.7029, 14)">川崎</button>
          </div>
        </div>

        <!-- 3. Tokai / Aichi & Nagoya -->
        <div class="area-region-section" data-region="nagoya" style="margin-top:14px;">
          <div class="area-region-title">🏯 Tokai / Aichi, Gifu, Mie (名古屋・愛知・東海)</div>
          <div class="area-chips-grid">
            <button class="area-chip" data-pref="aichi" data-city="大須" onclick="selectCityArea('aichi', '大須', 35.1583, 136.9039, 16)">大須 (Card Shop)</button>
            <button class="area-chip" data-pref="aichi" data-city="名駅" onclick="selectCityArea('aichi', '名古屋駅', 35.1709, 136.8815, 15)">名古屋駅 (名駅)</button>
            <button class="area-chip" data-pref="aichi" data-city="栄" onclick="selectCityArea('aichi', '栄', 35.1693, 136.9083, 15)">栄</button>
            <button class="area-chip" data-pref="aichi" data-city="金山" onclick="selectCityArea('aichi', '金山', 35.1430, 136.9011, 14)">金山</button>
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
        
        <!-- Vùng dữ liệu hiển thị -->
        <div>
          <div class="filter-group-title">📍 Vùng dữ liệu hiển thị (地域・エリア)</div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:700;">
              <input type="radio" name="set-region-radio" value="osaka" onchange="selectRegion('osaka')">
              <span>📍 Osaka &amp; Kansai (大阪府周辺 - 4,050 quán)</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:700;">
              <input type="radio" name="set-region-radio" value="tokyo" onchange="selectRegion('tokyo')">
              <span>🗼 Tokyo &amp; Kanto (東京都・神奈川 - 9,450 quán)</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:700;">
              <input type="radio" name="set-region-radio" value="nagoya" onchange="selectRegion('nagoya')">
              <span>🏯 Nagoya &amp; Tokai (愛知県・岐阜・三重 - 6,360 quán)</span>
            </label>
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:700;">
              <input type="radio" name="set-region-radio" value="all" onchange="selectRegion('all')">
              <span>🗾 Toàn quốc (全国エリア - 19,860+ quán)</span>
            </label>
          </div>
        </div>

        <!-- Cấu hình Telegram & Âm thanh -->
        <div>
          <div class="filter-group-title">🔔 Thông báo & Cảnh báo</div>
          <div style="display:flex; flex-direction:column; gap:10px;">
            <button type="button" onclick="closeSettingsModal(); openTelegramModal();" style="width:100%; padding:10px 14px; background:#0284c7; color:#ffffff; border:none; border-radius:10px; font-weight:800; font-size:0.82rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px;">
              <span>✈️ Cấu hình Telegram & Bộ lọc cảnh báo 24/7</span>
            </button>
            <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer; font-weight:700; background:#f8fafc; padding:10px 12px; border-radius:8px; border:1px solid #e2e8f0;">
              <span>🔊 Âm thanh thông báo trên web</span>
              <input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)">
            </label>
          </div>
        </div>

        <!-- Cập nhật dữ liệu -->
        <div>
          <button type="button" onclick="refreshData(); closeSettingsModal();" style="width:100%; padding:10px 14px; background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; border-radius:10px; font-weight:800; font-size:0.82rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px;">
            <span>🔄 Cập nhật dữ liệu mới nhất</span>
          </button>
        </div>

      </div>
    </div>
  </div>

  <!-- 9. STORE HISTORY MODAL (📜 入荷履歴 / Lịch sử báo cáo quán) -->
  <div id="store-history-modal" class="modal-overlay" onclick="if(event.target===this) closeStoreHistoryModal()">
    <div class="modal-card" style="max-width:440px;">
      <div class="modal-header">
        <h3 id="hist-modal-title">📜 Lịch sử báo cáo cửa hàng</h3>
        <button class="modal-close-btn" onclick="closeStoreHistoryModal()">✕</button>
      </div>
      <div class="modal-body" style="font-size:0.82rem; max-height:75vh; overflow-y:auto;" id="hist-modal-body">
        <div style="text-align:center; padding:20px; color:#64748b;">Đang tải lịch sử...</div>
      </div>
    </div>
  </div>
"""


# ==============================================================================
# 1. MAP PAGE RENDERER (GET / and GET /map)
# ==============================================================================

MAP_PAGE_CSS = """
  <style>
    /* FLOATING FILTER BAR ON MAP */
    #filter-bar-container {
      position: absolute;
      top: 10px;
      left: 10px;
      right: 10px;
      z-index: 1000;
      pointer-events: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .filter-chips-scroll {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      pointer-events: auto;
      padding-bottom: 2px;
    }
    .filter-chips-scroll::-webkit-scrollbar {
      display: none;
    }
    .poketan-chip {
      height: 36px;
      padding: 0 12px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 9999px;
      font-size: 0.74rem;
      font-weight: 700;
      color: #334155;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      white-space: nowrap;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,0.12);
      transition: all 0.15s ease;
      flex-shrink: 0;
    }
    .poketan-chip:hover {
      background: #f8fafc;
      border-color: #94a3b8;
    }
    .poketan-chip.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      box-shadow: 0 2px 10px rgba(59, 130, 246, 0.28);
    }
    .poketan-chip.chip-main-filter {
      background: #0f172a;
      color: #ffffff;
      border-color: #0f172a;
    }
    .poketan-chip.chip-main-filter:hover {
      background: #1e293b;
    }
    .filter-count-pill {
      background: #38bdf8;
      color: #0f172a;
      font-size: 0.65rem;
      font-weight: 800;
      padding: 1px 6px;
      border-radius: 99px;
    }

    /* SELECT CHIP */
    select.poketan-chip {
      appearance: none;
      -webkit-appearance: none;
      padding-right: 24px;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' fill='%23475569' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: calc(100% - 8px) center;
      cursor: pointer;
    }

    /* MAIN MAP CANVAS */
    #app-main {
      flex: 1;
      width: 100%;
      height: 100%;
      position: relative;
      overflow: hidden;
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
    }
    .leaflet-tile {
      image-rendering: -webkit-optimize-contrast;
    }

    /* FLOATING GPS BUTTON */
    #gps-btn {
      position: absolute;
      bottom: 20px;
      right: 18px;
      z-index: 1500;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #2563eb;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.28);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.35rem;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    #gps-btn:hover {
      background: #eff6ff;
      transform: scale(1.08);
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
      background: #2563eb;
      border: 3px solid #ffffff;
      box-shadow: 0 0 10px rgba(37, 99, 235, 0.8);
      position: relative;
    }

    /* MARKER CLUSTERS & IN-STOCK PIN */
    .poketan-cluster-wrap { background: transparent; border: none; }
    .poketan-cluster {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #2563eb;
      color: #0f172a;
      font-weight: 800;
      font-size: 0.82rem;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
    }
    .poketan-cluster.has-stock {
      border-color: #16a34a;
      box-shadow: 0 0 12px rgba(22, 163, 74, 0.7);
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
    }
    @keyframes bouncePin {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    /* LEAFLET POPUP */
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
      color: #2563eb;
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
      background: #2563eb;
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.74rem;
      border: none;
      cursor: pointer;
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
  </style>
"""


def render_map_page() -> str:
    head = get_shared_head("ポケ探 - ポケモンカード在庫マップ", include_leaflet=True)
    header = render_shared_header()
    footer = render_shared_footer("map")

    map_filter_modal = """
  <!-- MAP FILTER MODAL (⚙️ Bộ lọc bản đồ) -->
  <div id="map-filter-modal" class="modal-overlay" onclick="if(event.target===this) closeMapFilterModal()">
    <div class="modal-card">
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

      <div class="modal-body" style="display:flex; flex-direction:column; gap:16px;">
        <!-- KHU VỰC BẢN ĐỒ -->
        <div>
          <div class="filter-group-title">📍 Khu vực hiển thị (地域・エリア)</div>
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
              🌐 Toàn quốc (19.860+ quán)
            </button>
          </div>
        </div>

        <!-- TRẠNG THÁI HÀNG HÓA -->
        <div>
          <div class="filter-group-title">📊 Trạng thái hàng hóa (在庫状況)</div>
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
            <button class="filter-option-btn" data-val="n" onclick="selectMapModalStatus('n')">
              <span class="chip-dot dot-gray"></span> ⚪ Quán không bán thẻ (扱無)
            </button>
            <button class="filter-option-btn" data-val="unknown" onclick="selectMapModalStatus('unknown')">
              🔘 Chưa có tin báo nào
            </button>
          </div>
        </div>

        <!-- CHUỖI & THƯƠNG HIỆU -->
        <div>
          <div class="filter-group-title">🏢 Chuỗi cửa hàng & Thương hiệu</div>
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
              🃏 Card Shop chuyên
            </button>
            <button class="filter-option-btn" data-val="electronics" onclick="selectMapModalChain('electronics')">
              🎮 Điện máy, GEO
            </button>
          </div>
        </div>

        <!-- THỜI GIAN / ĐỘ MỚI TIN BÁO -->
        <div>
          <div class="filter-group-title">⏱️ Độ mới tin báo (報告の経過時間)</div>
          <div class="filter-options-grid" id="map-modal-time-group">
            <button class="filter-option-btn" data-val="1" onclick="selectMapModalTime('1')">
              ⚡ Trong 1 giờ qua
            </button>
            <button class="filter-option-btn" data-val="3" onclick="selectMapModalTime('3')">
              ⏱ Trong 3 giờ qua
            </button>
            <button class="filter-option-btn" data-val="6" onclick="selectMapModalTime('6')">
              ⏱ Trong 6 giờ qua
            </button>
            <button class="filter-option-btn" data-val="24" onclick="selectMapModalTime('24')">
              📅 Trong 24 giờ qua
            </button>
            <button class="filter-option-btn active" data-val="all" onclick="selectMapModalTime('all')">
              ⏳ Toàn bộ thời gian
            </button>
          </div>
        </div>
      </div>

      <div style="padding:12px 16px; border-top:1px solid #f1f5f9; background:#f8fafc; display:flex; gap:10px;">
        <button type="button" class="btn-reset-filter" onclick="resetMapFilters()">
          🔄 Đặt lại
        </button>
        <button type="button" class="btn-apply-filter" onclick="applyAndCloseMapFilterModal()">
          ✅ Áp dụng bộ lọc
        </button>
      </div>
    </div>
  </div>
"""

    return head + SHARED_BASE_CSS + MAP_PAGE_CSS + """
</head>
<body>
  <!-- LOADING SCREEN -->
  <div id="loading-overlay">
    <div class="spinner"></div>
    <div style="margin-top: 12px; font-weight: 800; font-size: 0.85rem;" id="loading-text">
      店舗データを読み込み中...
    </div>
  </div>
""" + header + """
  <!-- MAP PAGE MAIN VIEW -->
  <div id="filter-bar-container">
    <div class="filter-chips-scroll">
      <!-- Nút mở Modal Bộ lọc Bản đồ -->
      <button class="poketan-chip chip-main-filter" id="btn-map-filter" onclick="openMapFilterModal()" title="Mở bộ lọc bản đồ">
        <span>⚙️ Bộ lọc</span>
        <span id="map-filter-badge" class="filter-count-pill" style="display:none;">0</span>
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
      <select class="poketan-chip" id="map-chain-select" onchange="setMapChainFilter(this.value)" title="Chuỗi cửa hàng & Thương hiệu">
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

  <main id="app-main">
    <div id="map"></div>
    <button id="gps-btn" onclick="locateUser(true)" title="現在地を表示">
      📍
    </button>
  </main>
""" + footer + map_filter_modal + SHARED_MODALS_HTML + """
  <script>
    // 1. APP STATE & REGIONS
    const REGIONS = {
      'osaka': { id: 'osaka', name: '大阪・関西', center: [34.6937, 135.5023], zoom: 13, defaultCity: 'なんば', prefs: ['osaka'] },
      'tokyo': { id: 'tokyo', name: '東京・神奈川', center: [35.4437, 139.6380], zoom: 13, defaultCity: '横浜', prefs: ['kanagawa'] },
      'nagoya': { id: 'nagoya', name: '名古屋・東海', center: [35.1815, 136.9066], zoom: 13, defaultCity: '名古屋駅', prefs: ['aichi', 'gifu', 'mie'] },
      'all': { id: 'all', name: '全エリア (全国)', center: [34.6937, 135.5023], zoom: 10, defaultCity: '全エリア', prefs: ['osaka', 'aichi', 'kanagawa', 'gifu', 'mie'] }
    };

    let currentRegion = localStorage.getItem('poketan_selected_region') || 'osaka';
    if (!REGIONS[currentRegion]) currentRegion = 'osaka';
    let currentPref = REGIONS[currentRegion].prefs[0] || 'osaka';

    let storesDict = {};
    let hotStatus = {};
    let coldStatus = {};
    let configData = {};

    let mapRegionFilter = currentRegion;
    let mapStatusFilter = localStorage.getItem('poketan_map_status') || 'all';
    let mapChainFilter = localStorage.getItem('poketan_map_chain') || 'all';
    let mapTimeFilter = localStorage.getItem('poketan_map_time') || 'all';

    function saveMapFiltersToStorage() {
      try {
        localStorage.setItem('poketan_map_status', mapStatusFilter);
        localStorage.setItem('poketan_map_chain', mapChainFilter);
        localStorage.setItem('poketan_map_time', String(mapTimeFilter));
      } catch(e) {}
    }

    let userLat = null, userLng = null, userMarker = null, userCircle = null, hasCenteredOnUser = false;
    try {
      const savedLat = parseFloat(localStorage.getItem('poketan_user_lat'));
      const savedLng = parseFloat(localStorage.getItem('poketan_user_lng'));
      if (!isNaN(savedLat) && !isNaN(savedLng)) {
        userLat = savedLat; userLng = savedLng;
      }
    } catch(e) {}

    let initialCenter = REGIONS[currentRegion].center;
    let initialZoom = REGIONS[currentRegion].zoom;
    if (userLat !== null && userLng !== null) {
      initialCenter = [userLat, userLng];
      initialZoom = 14;
      hasCenteredOnUser = true;
    }

    // 2. LEAFLET MAP
    const map = L.map('map', {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      preferCanvas: true,
      inertia: true,
      inertiaDeceleration: 2000,
      zoomAnimation: true
    });
    window.map = map;

    L.tileLayer('https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
      subdomains: ['0', '1', '2', '3'],
      maxZoom: 20,
      attribution: '&copy; Google Maps'
    }).addTo(map);

    let clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 46,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      iconCreateFunction: function(cluster) {
        const count = cluster.getChildCount();
        const hasStock = cluster.getAllChildMarkers().some(m => m.options.hasStock);
        return L.divIcon({
          html: `<div class="poketan-cluster ${hasStock ? 'has-stock' : ''}">${count}</div>`,
          className: 'poketan-cluster-wrap',
          iconSize: L.point(32, 32)
        });
      }
    });
    map.addLayer(clusterGroup);
    const stockLayer = L.layerGroup().addTo(map);

    // 3. DECODE STATUS & ICONS
    function decodeStatus(rawVal) {
      if (!rawVal || typeof rawVal !== 'string') {
        return { code: 'u', label: '不明', packs: [], reported_at: '', timeAgo: '', onsite: false, timestamp: 0 };
      }
      const code = rawVal[0].toLowerCase();
      let rest = rawVal.substring(1);
      let onsite = false;
      if (rest.endsWith('g')) { onsite = true; rest = rest.slice(0, -1); }
      let packs = [];
      const packCodes = configData.packCodes || {};
      for (const [pCode, pName] of Object.entries(packCodes)) {
        if (rest.endsWith(pCode)) { packs.push(pName); rest = rest.slice(0, -pCode.length); }
      }
      let dtStr = '', timeAgo = '', timestamp = 0;
      if (rest.length >= 10) {
        const parsed = parseInt(rest.substring(0, 10), 10);
        if (!isNaN(parsed) && parsed > 0) {
          timestamp = parsed;
          const d = new Date(parsed * 1000);
          dtStr = `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')} (${d.getMonth()+1}/${d.getDate()})`;
          const diffSec = Math.floor(Date.now() / 1000 - parsed);
          if (diffSec < 60) timeAgo = 'たった今';
          else if (diffSec < 3600) timeAgo = `${Math.floor(diffSec / 60)}分前`;
          else if (diffSec < 86400) timeAgo = `${Math.floor(diffSec / 3600)}時間前`;
          else timeAgo = `${Math.floor(diffSec / 86400)}日前`;
        }
      }
      const labelMap = { 'i': '在庫あり', 'o': '在庫なし', 'n': '扱ってない', 'u': '未確認' };
      return { code, label: labelMap[code] || '未確認', packs, reported_at: dtStr, timeAgo, onsite, timestamp };
    }

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
      return km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
    }

    function createStockPinIcon(timeAgo) {
      return L.divIcon({
        html: `<div class="poketan-pin-wrapper"><div class="poketan-stock-pin">🟢</div><div class="poketan-pin-time-pill">${escapeHtml(timeAgo || 'たった今')}</div></div>`,
        className: 'poketan-pin-wrap',
        iconSize: [90, 28],
        iconAnchor: [14, 14]
      });
    }

    const redDotIcon = L.divIcon({ html: '<div style="width:10px;height:10px;border-radius:50%;background:#ef4444;border:1.5px solid #fff;"></div>', className: 'd-wrap', iconSize: [10, 10], iconAnchor: [5, 5] });
    const yellowDotIcon = L.divIcon({ html: '<div style="width:8px;height:8px;border-radius:50%;background:#eab308;border:1px solid #fff;"></div>', className: 'd-wrap', iconSize: [8, 8], iconAnchor: [4, 4] });
    const grayDotIcon = L.divIcon({ html: '<div style="width:8px;height:8px;border-radius:50%;background:#94a3b8;border:1px solid #fff;"></div>', className: 'd-wrap', iconSize: [8, 8], iconAnchor: [4, 4] });

    function matchesChainFilter(chain, filter) {
      if (!filter || filter === 'all') return true;
      const c = (chain || '').toLowerCase();
      if (filter === 'conbini') return ['seven', 'lawson', 'familymart', 'ministop'].includes(c);
      if (filter === 'specialty') return c === 'specialty';
      if (filter === 'electronics') return ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi'].includes(c);
      return c === filter;
    }

    // 4. RENDER MARKERS
    let latestStockStoreId = null;
    let dismissedToastStoreId = null;

    function renderMapMarkers() {
      clusterGroup.clearLayers();
      stockLayer.clearLayers();

      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const now = Math.floor(Date.now() / 1000);
      const clusterBatch = [];
      let newestInStore = null, maxTimestamp = 0;

      const targetRegion = mapRegionFilter || currentRegion || 'osaka';
      const allowedPrefs = (REGIONS[targetRegion] ? REGIONS[targetRegion].prefs : [targetRegion]) || ['osaka'];

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }

        const raw = effectiveStatus[store.id] || effectiveStatus[store.id + '_c'];
        const info = decodeStatus(raw);

        if (info.code === 'i' && info.timestamp > maxTimestamp) {
          maxTimestamp = info.timestamp;
          newestInStore = store;
        }

        // Status filter
        if (mapStatusFilter === 'in' && info.code !== 'i') continue;
        if (mapStatusFilter === 'onsite' && (!info.onsite || info.code !== 'i')) continue;
        if (mapStatusFilter === 'out' && info.code !== 'o') continue;
        if (mapStatusFilter === 'n' && info.code !== 'n') continue;
        if (mapStatusFilter === 'recent' && (info.code !== 'i' && !(info.timestamp > 0 && (now - info.timestamp <= 86400 * 7) && info.code !== 'n'))) continue;
        if (mapStatusFilter === 'unknown' && info.timestamp > 0) continue;

        // Chain filter
        if (!matchesChainFilter(store.chain, mapChainFilter)) continue;

        // Time filter
        if (mapTimeFilter !== 'all') {
          const maxSec = parseInt(mapTimeFilter, 10) * 3600;
          if (!info.timestamp || (now - info.timestamp > maxSec)) continue;
        }

        const currentZoom = map.getZoom();
        if (info.code === 'i') {
          const pinIcon = createStockPinIcon(info.timeAgo);
          if (currentZoom >= 12 || mapStatusFilter === 'in') {
            const m = L.marker([store.lat, store.lng], { icon: pinIcon, zIndexOffset: 2000 });
            m.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
            stockLayer.addLayer(m);
          } else {
            const cm = L.marker([store.lat, store.lng], { icon: pinIcon, hasStock: true });
            cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
            clusterBatch.push(cm);
          }
        } else {
          let dotIcon = grayDotIcon;
          if (info.code === 'o') dotIcon = redDotIcon;
          else if (info.code === 'n') dotIcon = yellowDotIcon;
          const cm = L.marker([store.lat, store.lng], { icon: dotIcon, hasStock: false });
          cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          clusterBatch.push(cm);
        }
      }

      if (clusterBatch.length > 0) clusterGroup.addLayers(clusterBatch);

      // Toast alert for newest in-stock store
      const toastEl = document.getElementById('live-stock-toast');
      if (newestInStore && newestInStore.id !== dismissedToastStoreId) {
        latestStockStoreId = newestInStore.id;
        const titleEl = document.getElementById('toast-store-title');
        const timeEl = document.getElementById('toast-time');
        if (titleEl) titleEl.innerText = newestInStore.name;
        if (timeEl) timeEl.innerText = decodeStatus(effectiveStatus[newestInStore.id]).timeAgo || 'たった今';
        if (toastEl) toastEl.style.display = 'flex';
      } else {
        if (toastEl) toastEl.style.display = 'none';
      }
    }

    // 5. POPUP HTML
    const storeCountsCache = {};
    const storeHistoryCache = {};
    const openPopupHistStoreIds = new Set();

    function createPopupHtml(store, info) {
      let distHtml = '';
      if (userLat !== null && userLng !== null) {
        const d = calcDistanceKm(userLat, userLng, store.lat, store.lng);
        distHtml = `<div style="font-size:0.75rem; color:#2563eb; font-weight:700; margin-top:2px;">📍 Cách vị trí bạn: ${formatDist(d)}</div>`;
      }
      let statusBg = '#f1f5f9', statusColor = '#64748b', statusText = '🔘 Chưa có tin (未確認)';
      if (info.code === 'i') { statusBg = '#dcfce7'; statusColor = '#15803d'; statusText = '🟢 Có hàng (In Stock)'; }
      else if (info.code === 'o') { statusBg = '#fee2e2'; statusColor = '#b91c1c'; statusText = '🔴 Hết hàng (Out of Stock)'; }
      else if (info.code === 'n') { statusBg = '#f1f5f9'; statusColor = '#475569'; statusText = '⚪ Không bán thẻ (扱ってない)'; }

      const packs = info.packs.length ? `<div style="font-size:0.74rem; margin-top:4px;"><b>📦 Gói:</b> ${escapeHtml(info.packs.join(', '))}</div>` : '';
      const time = (info.timestamp > 0 && info.timeAgo) ? `<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">🕒 Báo: <b>${escapeHtml(info.timeAgo)}</b> (${escapeHtml(info.reported_at)})</div>` : '';
      const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
      const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((store.name || '') + ' ' + (store.address || ''))}`;

      const counts = storeCountsCache[store.id] || { in: info.code === 'i' ? 1 : 0, out: info.code === 'o' ? 1 : 0 };

      return `
        <div>
          <div class="popup-store-title">${escapeHtml(store.name || '')}</div>
          <div class="popup-store-chain">${escapeHtml(chain)}</div>
          <div class="popup-status-badge" style="background:${statusBg}; color:${statusColor};">${statusText}</div>
          <div class="popup-report-counts-bar">
            <span class="report-count-tag tag-green">🟢 Có: <b>${counts.in}</b> lần</span>
            <span class="report-count-tag tag-red">🔴 Hết: <b>${counts.out}</b> lần</span>
          </div>
          ${distHtml}
          ${time}
          ${packs}
          <div class="popup-actions-grid">
            <a href="${mapsUrl}" target="_blank" class="btn-popup-maps">🗺️ Chỉ đường ↗</a>
            <button type="button" class="btn-popup-hist" onclick="openStoreHistoryModal('${store.id}')">📜 Lịch sử</button>
          </div>
        </div>
      `;
    }

    function focusStockStore() {
      if (!latestStockStoreId || !storesDict[latestStockStoreId]) return;
      const s = storesDict[latestStockStoreId];
      map.flyTo([s.lat, s.lng], 16, { duration: 0.8 });
      setTimeout(() => {
        stockLayer.eachLayer(m => {
          const ll = m.getLatLng();
          if (Math.abs(ll.lat - s.lat) < 0.0001 && Math.abs(ll.lng - s.lng) < 0.0001) m.openPopup();
        });
      }, 850);
    }
    function hideToast() {
      dismissedToastStoreId = latestStockStoreId;
      const toastEl = document.getElementById('live-stock-toast');
      if (toastEl) toastEl.style.display = 'none';
    }

    // 6. MAP FILTERS UI & HANDLERS
    function setMapStatusFilter(st) {
      mapStatusFilter = st;
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }
    function setMapChainFilter(chain) {
      mapChainFilter = chain;
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }
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
      let count = 0;
      if (mapStatusFilter !== 'all') count++;
      if (mapChainFilter !== 'all') count++;
      if (mapTimeFilter !== 'all') count++;
      const badge = document.getElementById('map-filter-badge');
      if (badge) {
        badge.innerText = count;
        badge.style.display = count > 0 ? 'inline-flex' : 'none';
      }
    }

    // Map Filter Modal
    let mapModalTempRegion = currentRegion, mapModalTempStatus = 'all', mapModalTempChain = 'all', mapModalTempTime = 'all';
    function openMapFilterModal() {
      mapModalTempRegion = mapRegionFilter || currentRegion;
      mapModalTempStatus = mapStatusFilter;
      mapModalTempChain = mapChainFilter;
      mapModalTempTime = mapTimeFilter;
      syncMapFilterModalUI();
      document.getElementById('map-filter-modal').classList.add('open');
    }
    function closeMapFilterModal() {
      document.getElementById('map-filter-modal').classList.remove('open');
    }
    function syncMapFilterModalUI() {
      document.querySelectorAll('#map-modal-region-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempRegion));
      document.querySelectorAll('#map-modal-status-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempStatus));
      document.querySelectorAll('#map-modal-chain-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempChain));
      document.querySelectorAll('#map-modal-time-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempTime));
    }
    function selectMapModalRegion(val) { mapModalTempRegion = val; syncMapFilterModalUI(); }
    function selectMapModalStatus(val) { mapModalTempStatus = val; syncMapFilterModalUI(); }
    function selectMapModalChain(val) { mapModalTempChain = val; syncMapFilterModalUI(); }
    function selectMapModalTime(val) { mapModalTempTime = val; syncMapFilterModalUI(); }
    function resetMapFilters() {
      mapModalTempRegion = currentRegion;
      mapModalTempStatus = 'all';
      mapModalTempChain = 'all';
      mapModalTempTime = 'all';
      syncMapFilterModalUI();
    }
    function applyAndCloseMapFilterModal() {
      mapRegionFilter = mapModalTempRegion;
      mapStatusFilter = mapModalTempStatus;
      mapChainFilter = mapModalTempChain;
      mapTimeFilter = mapModalTempTime;
      saveMapFiltersToStorage();
      closeMapFilterModal();
      updateMapFilterUI();
      renderMapMarkers();
    }

    // 7. GACHI MEGURI (⚡)
    function triggerGachiMeguri() {
      setMapStatusFilter('in');
      setMapChainFilter('all');
      const inStockStores = Object.values(storesDict).filter(s => {
        const info = decodeStatus((coldStatus[s.id] || hotStatus[s.id]));
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
        alert('現在、在庫あり店舗は見つかりませんでした。');
      }
    }

    // 8. GPS USER LOCATION
    function updateUserMarker(lat, lng, accuracy = 30) {
      if (!userMarker) {
        const icon = L.divIcon({ className: 'user-location-marker', iconSize: [18, 18], iconAnchor: [9, 9] });
        userMarker = L.marker([lat, lng], { icon, zIndexOffset: 2000 }).addTo(map);
        userCircle = L.circle([lat, lng], { radius: Math.max(accuracy, 25), color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.15, weight: 1 }).addTo(map);
      } else {
        userMarker.setLatLng([lat, lng]);
        if (userCircle) userCircle.setLatLng([lat, lng]);
      }
    }

    function locateUser(userInitiated = true) {
      const btn = document.getElementById('gps-btn');
      if (btn && userInitiated) btn.classList.add('locating');
      if (!navigator.geolocation) return;

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          try {
            localStorage.setItem('poketan_user_lat', String(userLat));
            localStorage.setItem('poketan_user_lng', String(userLng));
          } catch(e) {}
          updateUserMarker(userLat, userLng, pos.coords.accuracy || 30);
          if (btn) btn.classList.remove('locating');
          if (userInitiated) map.flyTo([userLat, userLng], 15, { duration: 0.8 });
        },
        (err) => {
          if (btn) btn.classList.remove('locating');
        },
        { enableHighAccuracy: true, timeout: 6000 }
      );
    }

    // 9. AREA & REGION SELECTION
    function openPrefModal() { document.getElementById('pref-modal').classList.add('open'); }
    function closePrefModal() { document.getElementById('pref-modal').classList.remove('open'); }
    function selectCityArea(pref, cityName, lat, lng, zoom) {
      currentRegion = pref;
      mapRegionFilter = pref;
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      const headerLoc = document.getElementById('header-loc-name');
      if (headerLoc) headerLoc.innerText = `${cityName}周辺`;
      if (lat && lng) map.flyTo([lat, lng], zoom || 14, { duration: 1.0 });
      closePrefModal();
      renderMapMarkers();
    }
    function filterAreaList(query) {
      const q = query.toLowerCase().trim();
      document.querySelectorAll('.area-region-section').forEach(sec => {
        let hasMatch = false;
        sec.querySelectorAll('.area-chip').forEach(chip => {
          const match = chip.innerText.toLowerCase().includes(q);
          chip.style.display = match ? 'inline-block' : 'none';
          if (match) hasMatch = true;
        });
        sec.style.display = hasMatch ? 'block' : 'none';
      });
    }

    // 10. MODALS: TELEGRAM, SETTINGS, HISTORY, BULLETIN
    function openTelegramModal() {
      const tokenEl = document.getElementById('tg-cfg-token');
      const chatIdEl = document.getElementById('tg-cfg-chatid');
      const enabledEl = document.getElementById('tg-cfg-enabled');
      const statusEl = document.getElementById('tg-cfg-status');
      const chainEl = document.getElementById('tg-cfg-chain');
      const timeEl = document.getElementById('tg-cfg-time');
      const regionEl = document.getElementById('tg-cfg-region');

      if (tokenEl) tokenEl.value = configData.telegramBotToken || '';
      if (chatIdEl) chatIdEl.value = configData.telegramChatId || '';
      if (enabledEl) enabledEl.checked = !!configData.telegramEnabled;
      if (statusEl) statusEl.value = configData.telegramStatus || 'in';
      if (chainEl) chainEl.value = configData.telegramChain || 'all';
      if (timeEl) timeEl.value = String(configData.telegramTime || '24');
      if (regionEl) regionEl.value = configData.telegramRegion || 'osaka';

      document.getElementById('telegram-modal').classList.add('open');
    }
    function closeTelegramModal() { document.getElementById('telegram-modal').classList.remove('open'); }

    async function saveTelegramConfig() {
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();
      const enabled = document.getElementById('tg-cfg-enabled') ? document.getElementById('tg-cfg-enabled').checked : false;
      const status = document.getElementById('tg-cfg-status') ? document.getElementById('tg-cfg-status').value : 'in';
      const chain = document.getElementById('tg-cfg-chain') ? document.getElementById('tg-cfg-chain').value : 'all';
      const time = document.getElementById('tg-cfg-time') ? document.getElementById('tg-cfg-time').value : '24';
      const region = document.getElementById('tg-cfg-region') ? document.getElementById('tg-cfg-region').value : 'osaka';

      configData.telegramBotToken = token;
      configData.telegramChatId = chatId;
      configData.telegramEnabled = enabled;
      configData.telegramStatus = status;
      configData.telegramChain = chain;
      configData.telegramTime = time;
      configData.telegramRegion = region;

      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notifications: {
            telegramBotToken: token, telegramChatId: chatId, telegramEnabled: enabled,
            telegramStatus: status, telegramChain: chain, telegramTime: time, telegramRegion: region
          }
        })
      });
      alert('Đã lưu cấu hình Telegram thành công! ✅');
      closeTelegramModal();
    }

    async function testTelegramWebhook() {
      const resEl = document.getElementById('tg-test-result');
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();
      if (!token || !chatId) {
        alert('Vui lòng nhập Token và Chat ID trước khi gửi test!');
        return;
      }
      resEl.style.display = 'block';
      resEl.style.background = '#f1f5f9';
      resEl.innerText = 'Đang gửi tin test...';
      try {
        const res = await fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            is_test: true,
            store: { id: 'test', name: 'Pokémon Center Test', chain: 'specialty', address: 'Osaka Namba', lat: 34.6667, lng: 135.5000, pref: 'osaka' },
            info: { status_code: 'i', code: 'i', onsite: true, reported_at: 'Vừa xong', timeAgo: 'Vừa xong', packs: ['Terastal Festival'] }
          })
        });
        const d = await res.json();
        resEl.style.background = d.status === 'ok' ? '#dcfce7' : '#fee2e2';
        resEl.innerText = d.status === 'ok' ? '✅ Gửi test thành công!' : `❌ Lỗi: ${JSON.stringify(d)}`;
      } catch(e) {
        resEl.style.background = '#fee2e2';
        resEl.innerText = '❌ Không thể kết nối máy chủ';
      }
    }

    function openSettingsModal() { document.getElementById('settings-modal').classList.add('open'); }
    function closeSettingsModal() { document.getElementById('settings-modal').classList.remove('open'); }
    function openBulletinModal() { document.getElementById('bulletin-modal').classList.add('open'); }
    function closeBulletinModal() { document.getElementById('bulletin-modal').classList.remove('open'); }
    function openSearchModal() { openPrefModal(); }

    async function openStoreHistoryModal(storeId) {
      const modal = document.getElementById('store-history-modal');
      const bodyEl = document.getElementById('hist-modal-body');
      modal.classList.add('open');
      bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang tải lịch sử báo cáo...</div>';
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }
        if (!history || history.length === 0) {
          bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">Chưa có lịch sử báo cáo nào.</div>';
          return;
        }
        bodyEl.innerHTML = history.map(item => `
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-weight:800; font-size:0.78rem;">
              <span style="color:${item.status_code === 'i' ? '#15803d' : '#b91c1c'};">${item.status_code === 'i' ? '🟢 Có hàng' : '🔴 Hết hàng'}</span>
              <span style="color:#64748b; font-size:0.7rem;">🕒 ${escapeHtml(item.formatted_time || '')}</span>
            </div>
            ${item.note ? `<div style="font-size:0.74rem; color:#1e293b; margin-top:3px;">📦 ${escapeHtml(item.note)}</div>` : ''}
            <div style="font-size:0.68rem; color:#94a3b8; margin-top:3px;">👤 Người báo: <b>${escapeHtml(item.user || 'Ẩn danh')}</b></div>
          </div>
        `).join('');
      } catch(e) {
        bodyEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi tải dữ liệu.</div>';
      }
    }
    function closeStoreHistoryModal() { document.getElementById('store-history-modal').classList.remove('open'); }

    // 11. INIT DATA & URL QUERY PARAMS
    async function initData() {
      try {
        const [cfgRes, storesRes, hotRes, coldRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data?region=all'),
          fetch('/api/hot_status?region=all').catch(() => null),
          fetch('/api/cold_status?region=all').catch(() => null)
        ]);
        configData = await cfgRes.json();
        storesDict = await storesRes.json();
        if (hotRes && hotRes.ok) hotStatus = await hotRes.json();
        if (coldRes && coldRes.ok) coldStatus = await coldRes.json();

        updateMapFilterUI();
        renderMapMarkers();

        // Check URL Query String: ?focus=store_id or ?hunt=1
        const urlParams = new URLSearchParams(window.location.search);
        const focusId = urlParams.get('focus');
        const isHunt = urlParams.get('hunt');

        if (focusId && storesDict[focusId]) {
          const s = storesDict[focusId];
          map.flyTo([s.lat, s.lng], 16, { duration: 0.8 });
          setTimeout(() => {
            stockLayer.eachLayer(m => {
              const ll = m.getLatLng();
              if (Math.abs(ll.lat - s.lat) < 0.0001 && Math.abs(ll.lng - s.lng) < 0.0001) m.openPopup();
            });
          }, 850);
        } else if (isHunt === '1') {
          triggerGachiMeguri();
        }

        // Realtime Firestore sync
        setupRealtime();
      } catch(e) {
        console.error('Init error:', e);
      } finally {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.opacity = '0';
        setTimeout(() => overlay && overlay.remove(), 150);
        map.invalidateSize();
      }
    }

    function setupRealtime() {
      if (!window.FirebaseInit || !configData.apiKey) return;
      try {
        const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
        const app = initializeApp({ apiKey: configData.apiKey, projectId: configData.projectId });
        const db = initializeFirestore(app, {});
        ['osaka', 'kanagawa', 'aichi', 'gifu', 'mie'].forEach(p => {
          onSnapshot(doc(db, 'status', p), (snap) => {
            if (snap.exists()) {
              Object.assign(hotStatus, snap.data());
              renderMapMarkers();
            }
          });
        });
      } catch(e) {}
    }

    window.addEventListener('DOMContentLoaded', initData);
  </script>
</body>
</html>"""


# ==============================================================================
# 2. NOTIFICATION & REPORT LIST PAGE RENDERER (GET /thongbao and GET /stores)
# ==============================================================================

THONGBAO_PAGE_CSS = """
  <style>
    /* DEDICATED REPORT LIST CONTAINER (NO LEAFLET MAP) */
    #thongbao-page-container {
      flex: 1;
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      background: #ffffff;
      overflow: hidden;
      min-height: 0;
    }

    .list-header-bar {
      padding: 10px 14px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      background: #ffffff;
      flex-shrink: 0;
    }

    /* REALTIME SETTINGS SYNCHRONIZATION BANNER */
    #list-active-settings-banner {
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      padding: 6px 12px;
      font-size: 0.72rem;
      color: #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 6px;
      flex-shrink: 0;
    }

    /* STATUS TABS ROW */
    .list-tabs-row {
      padding: 8px 12px 6px 12px;
      display: flex;
      gap: 6px;
      overflow-x: auto;
      background: #ffffff;
      border-bottom: 1px solid #f1f5f9;
      scrollbar-width: none;
      flex-shrink: 0;
    }
    .list-tabs-row::-webkit-scrollbar { display: none; }
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
      box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
    }

    /* RADIUS / DISTANCE FILTER ROW */
    .list-radius-row {
      padding: 6px 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      scrollbar-width: none;
      flex-shrink: 0;
    }
    .list-radius-row::-webkit-scrollbar { display: none; }
    .list-radius-chip {
      padding: 4px 10px;
      border-radius: 99px;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #475569;
      font-size: 0.72rem;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .list-radius-chip:hover {
      background: #f1f5f9;
    }
    .list-radius-chip.active {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
      font-weight: 800;
      box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
    }

    /* SEARCH & FILTER TRIGGER */
    .list-search-row {
      padding: 8px 12px;
      border-bottom: 1px solid #f1f5f9;
      display: flex;
      gap: 6px;
      align-items: center;
      background: #fafafa;
      flex-shrink: 0;
    }
    .list-search-box {
      flex: 1;
      position: relative;
    }
    .list-search-box input {
      width: 100%;
      height: 36px;
      background: #ffffff;
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

    /* SORT BAR */
    .list-sort-bar {
      padding: 7px 14px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #ffffff;
      flex-shrink: 0;
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
    }
    .list-sort-btn.active {
      background: #2563eb;
      border-color: #2563eb;
      color: #ffffff;
    }

    /* CARDS SCROLL LIST */
    .list-cards-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 8px 12px;
      -webkit-overflow-scrolling: touch;
    }
    .store-list-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 10px 12px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
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
    .card-actions-col {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 5px;
      flex-shrink: 0;
      margin-left: 10px;
    }
    .card-btn-map {
      background: #2563eb;
      color: #ffffff;
      border: none;
      border-radius: 6px;
      padding: 5px 9px;
      font-size: 0.7rem;
      font-weight: 800;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }
    .card-btn-hist {
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 0.67rem;
      font-weight: 700;
      color: #334155;
      cursor: pointer;
    }
  </style>
"""


def render_thongbao_page() -> str:
    head = get_shared_head("ポケ探 - 入荷速報 & 店舗一覧", include_leaflet=False)
    header = render_shared_header()
    footer = render_shared_footer("thongbao")

    thongbao_filter_modal = """
  <!-- 5.5 NOTIFICATION / REPORT LIST FILTER MODAL (6 Criteria) -->
  <div id="filter-modal" class="modal-overlay" onclick="if(event.target===this) closeFilterModal()">
    <div class="modal-card">
      <div class="modal-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.15rem;">⚙️</span>
          <div>
            <h3 style="font-weight:800; font-size:1.02rem; color:#0f172a; margin:0;">Bộ lọc &amp; Sắp xếp Thông báo</h3>
            <div style="font-size:0.7rem; color:#64748b; font-weight:600; margin-top:1px;">Lọc danh sách báo cáo theo tiêu chí riêng</div>
          </div>
        </div>
        <button class="modal-close-btn" onclick="closeFilterModal()">✕</button>
      </div>

      <div class="modal-body" style="display:flex; flex-direction:column; gap:16px;">
        <!-- SECTION 0: KHU VỰC HIỂN THỊ -->
        <div>
          <div class="filter-group-title">📍 Khu vực hiển thị (地域・エリア)</div>
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
              🌐 Toàn quốc (19.860+ quán)
            </button>
          </div>
        </div>

        <!-- SECTION 1: TRẠNG THÁI HÀNG HÓA -->
        <div>
          <div class="filter-group-title">📊 Trạng thái hàng hóa (在庫状況)</div>
          <div class="filter-options-grid" id="modal-status-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalStatus('all')">
              🌐 Tất cả trạng thái
            </button>
            <button class="filter-option-btn" data-val="in" onclick="selectModalStatus('in')">
              <span class="chip-dot dot-green"></span> 🟢 Chỉ điểm có hàng
            </button>
            <button class="filter-option-btn" data-val="onsite" onclick="selectModalStatus('onsite')">
              📍 Báo cáo tại quán (GPS)
            </button>
            <button class="filter-option-btn" data-val="recent" onclick="selectModalStatus('recent')">
              <span style="color:#eab308;font-size:0.75rem;">★</span> Từng có gần đây
            </button>
            <button class="filter-option-btn" data-val="out" onclick="selectModalStatus('out')">
              <span class="chip-dot dot-red"></span> 🔴 Báo hết hàng
            </button>
            <button class="filter-option-btn" data-val="n" onclick="selectModalStatus('n')">
              <span class="chip-dot dot-gray"></span> ⚪ Quán không bán thẻ (扱無)
            </button>
            <button class="filter-option-btn" data-val="unknown" onclick="selectModalStatus('unknown')">
              🔘 Chưa có tin báo nào
            </button>
          </div>
        </div>

        <!-- SECTION 2: CHUỖI CỬA HÀNG -->
        <div>
          <div class="filter-group-title">🏢 Chuỗi cửa hàng &amp; Thương hiệu</div>
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
              🃏 Card Shop chuyên
            </button>
            <button class="filter-option-btn" data-val="electronics" onclick="selectModalChain('electronics')">
              🎮 Điện máy, GEO
            </button>
          </div>
        </div>

        <!-- SECTION 3: THỜI GIAN HIỂN THỊ -->
        <div>
          <div class="filter-group-title">⏱️ Độ tươi mới của tin báo</div>
          <div class="filter-options-grid" id="modal-time-group">
            <button class="filter-option-btn" data-val="1" onclick="selectModalTime('1')">
              ⚡ Trong 1 giờ qua
            </button>
            <button class="filter-option-btn" data-val="3" onclick="selectModalTime('3')">
              ⏱ Trong 3 giờ qua
            </button>
            <button class="filter-option-btn" data-val="6" onclick="selectModalTime('6')">
              ⏱ Trong 6 giờ qua
            </button>
            <button class="filter-option-btn" data-val="24" onclick="selectModalTime('24')">
              📅 Trong 24 giờ qua
            </button>
            <button class="filter-option-btn active" data-val="all" onclick="selectModalTime('all')">
              ⏳ Toàn bộ thời gian
            </button>
          </div>
        </div>

        <!-- SECTION 4: BÁN KÍNH KHOẢNG CÁCH -->
        <div>
          <div class="filter-group-title">📍 Bán kính khoảng cách quanh bạn</div>
          <div class="filter-options-grid" id="modal-radius-group">
            <button class="filter-option-btn active" data-val="all" onclick="selectModalRadius('all')">
              🌐 Toàn khu vực (Không giới hạn)
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
          <div class="filter-group-title">🔃 Thứ tự sắp xếp danh sách</div>
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

      <div style="padding:12px 16px; border-top:1px solid #f1f5f9; background:#f8fafc; display:flex; gap:10px;">
        <button type="button" class="btn-reset-filter" onclick="resetAllFilters()">
          🔄 Đặt lại
        </button>
        <button type="button" class="btn-apply-filter" onclick="applyAndCloseFilterModal()">
          ✅ Áp dụng bộ lọc
        </button>
      </div>
    </div>
  </div>
"""

    return head + SHARED_BASE_CSS + THONGBAO_PAGE_CSS + """
</head>
<body>
  <!-- LOADING SCREEN -->
  <div id="loading-overlay">
    <div class="spinner"></div>
    <div style="margin-top: 12px; font-weight: 800; font-size: 0.85rem;" id="loading-text">
      店舗データを読み込み中...
    </div>
  </div>
""" + header + """
  <!-- THONG BAO / REPORT LIST PAGE (NO LEAFLET MAP) -->
  <div id="thongbao-page-container">
    <div class="list-header-bar">
      <div style="font-weight:800; font-size:0.92rem; color:#0f172a; display:flex; align-items:center; gap:6px;">
        <span>📋</span>
        <span>一覧 • Báo cáo &amp; Điểm có hàng</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <button onclick="openFilterModal()" class="list-sort-btn" style="display:inline-flex; align-items:center; gap:5px; font-weight:800; background:#0f172a; color:#ffffff; border:1px solid #0f172a; padding:6px 12px; border-radius:8px; cursor:pointer;">
          <span>⚙️ Bộ lọc &amp; Sắp xếp</span>
          <span id="list-filter-active-badge" class="filter-count-pill" style="display:none;">0</span>
        </button>
      </div>
    </div>

    <!-- Active settings banner -->
    <div id="list-active-settings-banner">
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="font-weight:800; color:#0f172a;">📍 Đang lọc:</span>
        <span id="list-active-settings-text" style="color:#2563eb; font-weight:700;">Osaka • Tất cả • Toàn thời gian</span>
      </div>
      <div style="display:flex; align-items:center; gap:6px;">
        <span id="list-tg-status-tag" onclick="openTelegramModal()" style="font-size:0.65rem; background:#dcfce7; color:#15803d; font-weight:800; padding:2px 7px; border-radius:6px; cursor:pointer;">✈️ Telegram: BẬT</span>
        <button type="button" onclick="openTelegramModal()" style="background:#0284c7; border:none; border-radius:4px; font-size:0.68rem; font-weight:700; color:#ffffff; padding:2px 8px; cursor:pointer;">Cấu hình</button>
      </div>
    </div>

    <!-- Status tabs -->
    <div class="list-tabs-row">
      <button class="list-tab-chip active" id="list-tab-all" onclick="setListStatusTab('all')">🌐 Tất cả</button>
      <button class="list-tab-chip" id="list-tab-in" onclick="setListStatusTab('in')">🟢 Có hàng</button>
      <button class="list-tab-chip" id="list-tab-onsite" onclick="setListStatusTab('onsite')">📍 Tại quán (GPS)</button>
      <button class="list-tab-chip" id="list-tab-out" onclick="setListStatusTab('out')">🔴 Hết hàng</button>
      <button class="list-tab-chip" id="list-tab-n" onclick="setListStatusTab('n')">⚪ Không bán thẻ</button>
      <button class="list-tab-chip" id="list-tab-recent" onclick="setListStatusTab('recent')">★ Từng có</button>
      <button class="list-tab-chip" id="list-tab-unknown" onclick="setListStatusTab('unknown')">🔘 Chưa có tin</button>
    </div>

    <!-- Radius filter row -->
    <div class="list-radius-row">
      <span style="font-size: 0.72rem; font-weight: 800; color: #334155; white-space: nowrap; display: flex; align-items: center; gap: 3px;">
        <span>📍 Khoảng cách:</span>
      </span>
      <button class="list-radius-chip active" id="list-radius-chip-all" onclick="setListRadiusFilter('all')">🌐 Tất cả</button>
      <button class="list-radius-chip" id="list-radius-chip-1" onclick="setListRadiusFilter('1')">📍 1 km</button>
      <button class="list-radius-chip" id="list-radius-chip-3" onclick="setListRadiusFilter('3')">📍 3 km</button>
      <button class="list-radius-chip" id="list-radius-chip-5" onclick="setListRadiusFilter('5')">📍 5 km</button>
      <button class="list-radius-chip" id="list-radius-chip-10" onclick="setListRadiusFilter('10')">📍 10 km</button>
    </div>

    <!-- Search row -->
    <div class="list-search-row">
      <div class="list-search-box">
        <span class="icon">🔍</span>
        <input type="text" id="list-search-input" placeholder="Tìm tên quán, địa chỉ..." oninput="onListSearch(this.value)" />
      </div>
      <button onclick="openFilterModal()" class="list-sort-btn" style="background:#0f172a; color:#ffffff; padding:7px 11px; border-radius:8px; cursor:pointer;">
        <span>⚙️ Lọc</span>
        <span id="list-filter-active-badge-2" class="filter-count-pill" style="display:none;">0</span>
      </button>
    </div>

    <!-- Sort controls bar -->
    <div class="list-sort-bar">
      <span style="font-size:0.72rem; color:#64748b; font-weight:700;">Sắp xếp theo:</span>
      <div style="display:flex; gap:6px;">
        <button id="sort-btn-newest" onclick="setListSortMode('newest')" class="list-sort-btn active">🕒 Mới nhất</button>
        <button id="sort-btn-nearest" onclick="setListSortMode('nearest')" class="list-sort-btn">📍 Gần nhất</button>
      </div>
      <span id="list-count-badge" style="margin-left:auto; font-size:0.72rem; color:#2563eb; font-weight:800;">
        0 quán
      </span>
    </div>

    <!-- Store cards scroll container -->
    <div class="list-cards-scroll" id="store-cards-list"></div>
  </div>
""" + footer + thongbao_filter_modal + SHARED_MODALS_HTML + """
  <script>
    // 1. APP STATE & REGIONS
    const REGIONS = {
      'osaka': { id: 'osaka', name: '大阪・関西', center: [34.6937, 135.5023], zoom: 13, defaultCity: 'なんば', prefs: ['osaka'] },
      'tokyo': { id: 'tokyo', name: '東京・神奈川', center: [35.4437, 139.6380], zoom: 13, defaultCity: '横浜', prefs: ['kanagawa'] },
      'nagoya': { id: 'nagoya', name: '名古屋・東海', center: [35.1815, 136.9066], zoom: 13, defaultCity: '名古屋駅', prefs: ['aichi', 'gifu', 'mie'] },
      'all': { id: 'all', name: '全エリア (全国)', center: [34.6937, 135.5023], zoom: 10, defaultCity: '全エリア', prefs: ['osaka', 'aichi', 'kanagawa', 'gifu', 'mie'] }
    };

    let currentRegion = localStorage.getItem('poketan_selected_region') || 'osaka';
    if (!REGIONS[currentRegion]) currentRegion = 'osaka';
    let currentPref = REGIONS[currentRegion].prefs[0] || 'osaka';

    let storesDict = {};
    let hotStatus = {};
    let coldStatus = {};
    let configData = {};
    const storeHistoryCache = {};
    const storeCountsCache = {};

    let listRegionFilter = currentRegion;
    let listStatusFilter = localStorage.getItem('poketan_list_status') || 'all';
    let listChainFilter = localStorage.getItem('poketan_list_chain') || 'all';
    let listTimeFilter = localStorage.getItem('poketan_list_time') || 'all';
    let listRadiusFilter = localStorage.getItem('poketan_list_radius') || 'all';
    let listSortMode = localStorage.getItem('poketan_list_sort') || 'newest';

    function saveListFiltersToStorage() {
      try {
        localStorage.setItem('poketan_list_status', listStatusFilter);
        localStorage.setItem('poketan_list_chain', listChainFilter);
        localStorage.setItem('poketan_list_time', String(listTimeFilter));
        localStorage.setItem('poketan_list_radius', String(listRadiusFilter));
        localStorage.setItem('poketan_list_sort', listSortMode);
      } catch(e) {}
    }

    let userLat = null, userLng = null;
    try {
      const savedLat = parseFloat(localStorage.getItem('poketan_user_lat'));
      const savedLng = parseFloat(localStorage.getItem('poketan_user_lng'));
      if (!isNaN(savedLat) && !isNaN(savedLng)) {
        userLat = savedLat; userLng = savedLng;
      }
    } catch(e) {}

    // 2. HELPERS
    function decodeStatus(rawVal) {
      if (!rawVal || typeof rawVal !== 'string') {
        return { code: 'u', label: '不明', packs: [], reported_at: '', timeAgo: '', onsite: false, timestamp: 0 };
      }
      const code = rawVal[0].toLowerCase();
      let rest = rawVal.substring(1);
      let onsite = false;
      if (rest.endsWith('g')) { onsite = true; rest = rest.slice(0, -1); }
      let packs = [];
      const packCodes = configData.packCodes || {};
      for (const [pCode, pName] of Object.entries(packCodes)) {
        if (rest.endsWith(pCode)) { packs.push(pName); rest = rest.slice(0, -pCode.length); }
      }
      let dtStr = '', timeAgo = '', timestamp = 0;
      if (rest.length >= 10) {
        const parsed = parseInt(rest.substring(0, 10), 10);
        if (!isNaN(parsed) && parsed > 0) {
          timestamp = parsed;
          const d = new Date(parsed * 1000);
          dtStr = `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')} (${d.getMonth()+1}/${d.getDate()})`;
          const diffSec = Math.floor(Date.now() / 1000 - parsed);
          if (diffSec < 60) timeAgo = 'たった今';
          else if (diffSec < 3600) timeAgo = `${Math.floor(diffSec / 60)}分前`;
          else if (diffSec < 86400) timeAgo = `${Math.floor(diffSec / 3600)}時間前`;
          else timeAgo = `${Math.floor(diffSec / 86400)}日前`;
        }
      }
      const labelMap = { 'i': '在庫あり', 'o': '在庫なし', 'n': '扱ってない', 'u': '未確認' };
      return { code, label: labelMap[code] || '未確認', packs, reported_at: dtStr, timeAgo, onsite, timestamp };
    }

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
      return km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
    }

    function matchesChainFilter(chain, filter) {
      if (!filter || filter === 'all') return true;
      const c = (chain || '').toLowerCase();
      if (filter === 'conbini') return ['seven', 'lawson', 'familymart', 'ministop'].includes(c);
      if (filter === 'specialty') return c === 'specialty';
      if (filter === 'electronics') return ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi'].includes(c);
      return c === filter;
    }

    // 3. RENDER STORE LIST CARDS
    function renderStoreList(query = '') {
      const listContainer = document.getElementById('store-cards-list');
      if (!listContainer) return;

      const allStores = Object.values(storesDict);
      const effectiveStatus = { ...coldStatus, ...hotStatus };
      const now = Math.floor(Date.now() / 1000);
      const q = query.toLowerCase().trim();

      // Banner text
      const targetRegion = listRegionFilter || currentRegion || 'osaka';
      let regName = 'Osaka';
      if (targetRegion === 'tokyo') regName = 'Tokyo & Kanto';
      else if (targetRegion === 'nagoya') regName = 'Nagoya & Tokai';
      else if (targetRegion === 'all') regName = 'Toàn quốc';

      const bannerTextEl = document.getElementById('list-active-settings-text');
      if (bannerTextEl) {
        let stName = 'Tất cả';
        if (listStatusFilter === 'in') stName = '🟢 Có hàng';
        else if (listStatusFilter === 'onsite') stName = '📍 Tại quán (GPS)';
        else if (listStatusFilter === 'out') stName = '🔴 Hết hàng';
        else if (listStatusFilter === 'n') stName = '⚪ Không bán thẻ';
        else if (listStatusFilter === 'recent') stName = '★ Từng có';
        else if (listStatusFilter === 'unknown') stName = '🔘 Chưa có tin';

        let rName = listRadiusFilter === 'all' ? 'Toàn khu vực' : `Bán kính ${listRadiusFilter}km`;
        bannerTextEl.innerText = `${regName} • ${stName} • ${rName}`;
      }

      const tgTag = document.getElementById('list-tg-status-tag');
      if (tgTag) {
        const isTg = !!configData.telegramEnabled;
        tgTag.innerText = isTg ? '✈️ Telegram: BẬT' : '✈️ Telegram: TẮT';
        tgTag.style.background = isTg ? '#dcfce7' : '#fee2e2';
        tgTag.style.color = isTg ? '#15803d' : '#b91c1c';
      }

      let matched = [];
      const allowedPrefs = (REGIONS[targetRegion] ? REGIONS[targetRegion].prefs : [targetRegion]) || ['osaka'];

      let refLat = userLat, refLng = userLng;
      if (refLat === null && REGIONS[targetRegion]) {
        refLat = REGIONS[targetRegion].center[0];
        refLng = REGIONS[targetRegion].center[1];
      }

      for (const store of allStores) {
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }

        const info = decodeStatus(effectiveStatus[store.id] || effectiveStatus[store.id + '_c']);

        // Status
        if (listStatusFilter === 'in' && info.code !== 'i') continue;
        if (listStatusFilter === 'onsite' && (!info.onsite || info.code !== 'i')) continue;
        if (listStatusFilter === 'out' && info.code !== 'o') continue;
        if (listStatusFilter === 'n' && info.code !== 'n') continue;
        if (listStatusFilter === 'recent' && (info.code !== 'i' && !(info.timestamp > 0 && (now - info.timestamp <= 86400 * 7) && info.code !== 'n'))) continue;
        if (listStatusFilter === 'unknown' && info.timestamp > 0) continue;

        // Chain
        if (!matchesChainFilter(store.chain, listChainFilter)) continue;

        // Time
        if (listTimeFilter !== 'all') {
          const maxSec = parseInt(listTimeFilter, 10) * 3600;
          if (!info.timestamp || (now - info.timestamp > maxSec)) continue;
        }

        // Search
        if (q) {
          const mName = (store.name || '').toLowerCase().includes(q);
          const mAddr = (store.address || '').toLowerCase().includes(q);
          if (!mName && !mAddr) continue;
        }

        // Distance
        let dist = null;
        if (refLat !== null && refLng !== null && store.lat && store.lng) {
          dist = calcDistanceKm(refLat, refLng, store.lat, store.lng);
        }
        if (listRadiusFilter !== 'all') {
          const maxKm = parseFloat(listRadiusFilter);
          if (dist === null || dist > maxKm) continue;
        }

        matched.push({ store, info, dist });
      }

      // Update count badge
      const countBadge = document.getElementById('list-count-badge');
      if (countBadge) countBadge.innerText = `${matched.length.toLocaleString()} quán`;

      // Sort
      matched.sort((a,b) => {
        if (a.info.code === 'i' && b.info.code !== 'i') return -1;
        if (b.info.code === 'i' && a.info.code !== 'i') return 1;
        if (listSortMode === 'nearest') {
          if (a.dist !== null && b.dist !== null) return a.dist - b.dist;
          if (a.dist !== null) return -1;
          if (b.dist !== null) return 1;
          return (b.info.timestamp || 0) - (a.info.timestamp || 0);
        } else {
          const diffTs = (b.info.timestamp || 0) - (a.info.timestamp || 0);
          if (diffTs !== 0) return diffTs;
          if (a.dist !== null && b.dist !== null) return a.dist - b.dist;
          return 0;
        }
      });

      if (matched.length === 0) {
        listContainer.innerHTML = `
          <div style="text-align:center; padding:36px 12px; color:#64748b;">
            <div style="font-size:2rem; margin-bottom:8px;">📭</div>
            <div style="font-weight:700; color:#334155; font-size:0.88rem;">Không tìm thấy quán nào phù hợp</div>
            <div style="font-size:0.75rem; margin-top:4px;">Thử đổi từ khóa hoặc mở rộng bán kính tìm kiếm.</div>
          </div>
        `;
        return;
      }

      const renderSlice = matched.slice(0, 120);

      listContainer.innerHTML = renderSlice.map(item => {
        const { store, info, dist } = item;
        let badgeClass = 'badge-none', badgeText = '🔘 Chưa có tin';
        if (info.code === 'i') { badgeClass = 'badge-in'; badgeText = '🟢 Có hàng'; }
        else if (info.code === 'o') { badgeClass = 'badge-out'; badgeText = '🔴 Hết hàng'; }
        else if (info.code === 'n') { badgeClass = 'badge-none'; badgeText = '⚪ Không bán thẻ'; }

        const onsiteBadge = (info.onsite && info.code === 'i')
          ? `<span class="card-badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; padding:2px 6px; font-size:0.68rem;">📸 Tại chỗ</span>`
          : '';

        const counts = storeCountsCache[store.id] || { in: info.code === 'i' ? 1 : 0, out: info.code === 'o' ? 1 : 0 };
        const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
        const distStr = dist !== null ? ` • 📍 Cách ${formatDist(dist)}` : '';
        const timeStr = (info.timestamp > 0 && info.timeAgo) ? ` • 🕒 ${escapeHtml(info.timeAgo)}` : '';
        const packHtml = info.packs.length ? `<div style="font-size:0.72rem; color:#2563eb; font-weight:700; margin-top:3px;">📦 ${escapeHtml(info.packs.join(', '))}</div>` : '';

        return `
          <div class="store-list-card">
            <div class="card-left-info">
              <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span class="card-badge ${badgeClass}">${badgeText}</span>
                ${onsiteBadge}
                <div class="card-store-name">${escapeHtml(store.name || '')}</div>
              </div>
              <div class="card-chain-time">${escapeHtml(chain)}${distStr}${timeStr}</div>
              <div class="popup-report-counts-bar" style="margin:4px 0 2px 0;">
                <span class="report-count-tag tag-green" style="font-size:0.67rem; padding:1px 6px;">🟢 Có: <b>${counts.in}</b> lần</span>
                <span class="report-count-tag tag-red" style="font-size:0.67rem; padding:1px 6px;">🔴 Hết: <b>${counts.out}</b> lần</span>
              </div>
              ${packHtml}
            </div>
            <div class="card-actions-col">
              <a href="/map?focus=${store.id}" class="card-btn-map" title="Xem trên bản đồ">
                🗺️ Bản đồ
              </a>
              <button type="button" onclick="openStoreHistoryModal('${store.id}')" class="card-btn-hist">
                📜 Lịch sử
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // 4. FILTER CONTROLS & HANDLERS
    function setListStatusTab(tab) {
      listStatusFilter = tab;
      saveListFiltersToStorage();
      document.querySelectorAll('.list-tab-chip').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`list-tab-${tab}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function setListRadiusFilter(val) {
      listRadiusFilter = String(val);
      saveListFiltersToStorage();
      document.querySelectorAll('.list-radius-chip').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`list-radius-chip-${val}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function setListSortMode(mode) {
      listSortMode = mode;
      saveListFiltersToStorage();
      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`sort-btn-${mode}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function onListSearch(val) {
      renderStoreList(val);
    }

    // Filter Modal (6 Criteria)
    let modalTempRegion = currentRegion, modalTempFilter = 'all', modalTempChain = 'all', modalTempTime = 'all', modalTempRadius = 'all', modalTempSort = 'newest';
    function openFilterModal() {
      modalTempRegion = listRegionFilter || currentRegion;
      modalTempFilter = listStatusFilter;
      modalTempChain = listChainFilter;
      modalTempTime = listTimeFilter;
      modalTempRadius = listRadiusFilter;
      modalTempSort = listSortMode;
      syncFilterModalUI();
      document.getElementById('filter-modal').classList.add('open');
    }
    function closeFilterModal() { document.getElementById('filter-modal').classList.remove('open'); }
    function syncFilterModalUI() {
      document.querySelectorAll('#modal-region-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempRegion));
      document.querySelectorAll('#modal-status-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempFilter));
      document.querySelectorAll('#modal-chain-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempChain));
      document.querySelectorAll('#modal-time-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempTime));
      document.querySelectorAll('#modal-radius-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempRadius));
      document.querySelectorAll('#modal-sort-group .filter-option-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === modalTempSort));
    }
    function selectModalRegion(v) { modalTempRegion = v; syncFilterModalUI(); }
    function selectModalStatus(v) { modalTempFilter = v; syncFilterModalUI(); }
    function selectModalChain(v) { modalTempChain = v; syncFilterModalUI(); }
    function selectModalTime(v) { modalTempTime = v; syncFilterModalUI(); }
    function selectModalRadius(v) { modalTempRadius = v; syncFilterModalUI(); }
    function selectModalSort(v) { modalTempSort = v; syncFilterModalUI(); }
    function resetAllFilters() {
      modalTempRegion = currentRegion;
      modalTempFilter = 'all'; modalTempChain = 'all'; modalTempTime = 'all'; modalTempRadius = 'all'; modalTempSort = 'newest';
      syncFilterModalUI();
    }
    function applyAndCloseFilterModal() {
      listRegionFilter = modalTempRegion;
      listStatusFilter = modalTempFilter;
      listChainFilter = modalTempChain;
      listTimeFilter = modalTempTime;
      listRadiusFilter = modalTempRadius;
      listSortMode = modalTempSort;
      saveListFiltersToStorage();

      document.querySelectorAll('.list-tab-chip').forEach(b => b.classList.toggle('active', b.id === `list-tab-${listStatusFilter}`));
      document.querySelectorAll('.list-radius-chip').forEach(b => b.classList.toggle('active', b.id === `list-radius-chip-${listRadiusFilter}`));
      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.toggle('active', b.id === `sort-btn-${listSortMode}`));

      closeFilterModal();
      renderStoreList(document.getElementById('list-search-input').value);
    }

    // 5. AREA & MODALS
    function openPrefModal() { document.getElementById('pref-modal').classList.add('open'); }
    function closePrefModal() { document.getElementById('pref-modal').classList.remove('open'); }
    function selectCityArea(pref, cityName, lat, lng, zoom) {
      currentRegion = pref;
      listRegionFilter = pref;
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      const headerLoc = document.getElementById('header-loc-name');
      if (headerLoc) headerLoc.innerText = `${cityName}周辺`;
      closePrefModal();
      renderStoreList();
    }
    function filterAreaList(query) {
      const q = query.toLowerCase().trim();
      document.querySelectorAll('.area-region-section').forEach(sec => {
        let hasMatch = false;
        sec.querySelectorAll('.area-chip').forEach(chip => {
          const match = chip.innerText.toLowerCase().includes(q);
          chip.style.display = match ? 'inline-block' : 'none';
          if (match) hasMatch = true;
        });
        sec.style.display = hasMatch ? 'block' : 'none';
      });
    }

    function openTelegramModal() {
      const tokenEl = document.getElementById('tg-cfg-token');
      const chatIdEl = document.getElementById('tg-cfg-chatid');
      const enabledEl = document.getElementById('tg-cfg-enabled');
      const statusEl = document.getElementById('tg-cfg-status');
      const chainEl = document.getElementById('tg-cfg-chain');
      const timeEl = document.getElementById('tg-cfg-time');
      const regionEl = document.getElementById('tg-cfg-region');

      if (tokenEl) tokenEl.value = configData.telegramBotToken || '';
      if (chatIdEl) chatIdEl.value = configData.telegramChatId || '';
      if (enabledEl) enabledEl.checked = !!configData.telegramEnabled;
      if (statusEl) statusEl.value = configData.telegramStatus || 'in';
      if (chainEl) chainEl.value = configData.telegramChain || 'all';
      if (timeEl) timeEl.value = String(configData.telegramTime || '24');
      if (regionEl) regionEl.value = configData.telegramRegion || 'osaka';

      document.getElementById('telegram-modal').classList.add('open');
    }
    function closeTelegramModal() { document.getElementById('telegram-modal').classList.remove('open'); }

    async function saveTelegramConfig() {
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();
      const enabled = document.getElementById('tg-cfg-enabled') ? document.getElementById('tg-cfg-enabled').checked : false;
      const status = document.getElementById('tg-cfg-status') ? document.getElementById('tg-cfg-status').value : 'in';
      const chain = document.getElementById('tg-cfg-chain') ? document.getElementById('tg-cfg-chain').value : 'all';
      const time = document.getElementById('tg-cfg-time') ? document.getElementById('tg-cfg-time').value : '24';
      const region = document.getElementById('tg-cfg-region') ? document.getElementById('tg-cfg-region').value : 'osaka';

      configData.telegramBotToken = token;
      configData.telegramChatId = chatId;
      configData.telegramEnabled = enabled;
      configData.telegramStatus = status;
      configData.telegramChain = chain;
      configData.telegramTime = time;
      configData.telegramRegion = region;

      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notifications: {
            telegramBotToken: token, telegramChatId: chatId, telegramEnabled: enabled,
            telegramStatus: status, telegramChain: chain, telegramTime: time, telegramRegion: region
          }
        })
      });
      alert('Đã lưu cấu hình Telegram thành công! ✅');
      closeTelegramModal();
      renderStoreList();
    }

    async function testTelegramWebhook() {
      const resEl = document.getElementById('tg-test-result');
      const token = (document.getElementById('tg-cfg-token') ? document.getElementById('tg-cfg-token').value : '').trim();
      const chatId = (document.getElementById('tg-cfg-chatid') ? document.getElementById('tg-cfg-chatid').value : '').trim();
      if (!token || !chatId) {
        alert('Vui lòng nhập Token và Chat ID trước khi gửi test!');
        return;
      }
      resEl.style.display = 'block';
      resEl.style.background = '#f1f5f9';
      resEl.innerText = 'Đang gửi tin test...';
      try {
        const res = await fetch('/api/notify/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            is_test: true,
            store: { id: 'test', name: 'Pokémon Center Test', chain: 'specialty', address: 'Osaka Namba', lat: 34.6667, lng: 135.5000, pref: 'osaka' },
            info: { status_code: 'i', code: 'i', onsite: true, reported_at: 'Vừa xong', timeAgo: 'Vừa xong', packs: ['Terastal Festival'] }
          })
        });
        const d = await res.json();
        resEl.style.background = d.status === 'ok' ? '#dcfce7' : '#fee2e2';
        resEl.innerText = d.status === 'ok' ? '✅ Gửi test thành công!' : `❌ Lỗi: ${JSON.stringify(d)}`;
      } catch(e) {
        resEl.style.background = '#fee2e2';
        resEl.innerText = '❌ Không thể kết nối máy chủ';
      }
    }

    function openSettingsModal() { document.getElementById('settings-modal').classList.add('open'); }
    function closeSettingsModal() { document.getElementById('settings-modal').classList.remove('open'); }
    function openBulletinModal() { document.getElementById('bulletin-modal').classList.add('open'); }
    function closeBulletinModal() { document.getElementById('bulletin-modal').classList.remove('open'); }
    function openSearchModal() { openPrefModal(); }

    async function openStoreHistoryModal(storeId) {
      const modal = document.getElementById('store-history-modal');
      const bodyEl = document.getElementById('hist-modal-body');
      modal.classList.add('open');
      bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang tải lịch sử báo cáo...</div>';
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }
        if (!history || history.length === 0) {
          bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">Chưa có lịch sử báo cáo nào.</div>';
          return;
        }
        bodyEl.innerHTML = history.map(item => `
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-weight:800; font-size:0.78rem;">
              <span style="color:${item.status_code === 'i' ? '#15803d' : '#b91c1c'};">${item.status_code === 'i' ? '🟢 Có hàng' : '🔴 Hết hàng'}</span>
              <span style="color:#64748b; font-size:0.7rem;">🕒 ${escapeHtml(item.formatted_time || '')}</span>
            </div>
            ${item.note ? `<div style="font-size:0.74rem; color:#1e293b; margin-top:3px;">📦 ${escapeHtml(item.note)}</div>` : ''}
            <div style="font-size:0.68rem; color:#94a3b8; margin-top:3px;">👤 Người báo: <b>${escapeHtml(item.user || 'Ẩn danh')}</b></div>
          </div>
        `).join('');
      } catch(e) {
        bodyEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi tải dữ liệu.</div>';
      }
    }
    function closeStoreHistoryModal() { document.getElementById('store-history-modal').classList.remove('open'); }

    // 6. SILENT GPS CHECK & INIT DATA
    function checkGpsSilently() {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          try {
            localStorage.setItem('poketan_user_lat', String(userLat));
            localStorage.setItem('poketan_user_lng', String(userLng));
          } catch(e) {}
          renderStoreList(document.getElementById('list-search-input').value);
        },
        (err) => {},
        { enableHighAccuracy: false, timeout: 5000 }
      );
    }

    async function initData() {
      checkGpsSilently();
      try {
        const [cfgRes, storesRes, hotRes, coldRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data?region=all'),
          fetch('/api/hot_status?region=all').catch(() => null),
          fetch('/api/cold_status?region=all').catch(() => null)
        ]);
        configData = await cfgRes.json();
        storesDict = await storesRes.json();
        if (hotRes && hotRes.ok) hotStatus = await hotRes.json();
        if (coldRes && coldRes.ok) coldStatus = await coldRes.json();

        // Sync initial UI badges
        document.querySelectorAll('.list-tab-chip').forEach(b => b.classList.toggle('active', b.id === `list-tab-${listStatusFilter}`));
        document.querySelectorAll('.list-radius-chip').forEach(b => b.classList.toggle('active', b.id === `list-radius-chip-${listRadiusFilter}`));
        document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.toggle('active', b.id === `sort-btn-${listSortMode}`));

        renderStoreList();
        setupRealtime();
      } catch(e) {
        console.error('Init error:', e);
      } finally {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.opacity = '0';
        setTimeout(() => overlay && overlay.remove(), 150);
      }
    }

    function setupRealtime() {
      if (!window.FirebaseInit || !configData.apiKey) return;
      try {
        const { initializeApp, initializeFirestore, doc, onSnapshot } = window.FirebaseInit;
        const app = initializeApp({ apiKey: configData.apiKey, projectId: configData.projectId });
        const db = initializeFirestore(app, {});
        ['osaka', 'kanagawa', 'aichi', 'gifu', 'mie'].forEach(p => {
          onSnapshot(doc(db, 'status', p), (snap) => {
            if (snap.exists()) {
              Object.assign(hotStatus, snap.data());
              renderStoreList(document.getElementById('list-search-input').value);
            }
          });
        });
      } catch(e) {}
    }

    window.addEventListener('DOMContentLoaded', initData);
  </script>
</body>
</html>"""
