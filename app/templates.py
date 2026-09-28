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
      position: relative;
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
    .footer-unread-badge {
      position: absolute;
      top: 2px;
      right: 50%;
      transform: translateX(14px);
      background: #ef4444;
      color: #ffffff;
      font-size: 0.58rem;
      font-weight: 800;
      min-width: 17px;
      height: 17px;
      line-height: 17px;
      padding: 0 4px;
      border-radius: 9px;
      text-align: center;
      box-shadow: 0 2px 6px rgba(239, 68, 68, 0.45);
      border: 1.5px solid #ffffff;
      pointer-events: none;
      z-index: 10;
      display: none;
      align-items: center;
      justify-content: center;
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
    .badge-not { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
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

    /* SETTINGS MODAL TAB BAR & PANES */
    .settings-tab-bar {
      display: flex;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      padding: 0 12px;
      gap: 4px;
      flex-shrink: 0;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }
    .settings-tab-btn {
      padding: 11px 14px;
      font-weight: 700;
      font-size: 0.82rem;
      border: none;
      background: none;
      cursor: pointer;
      border-bottom: 3px solid transparent;
      color: #64748b;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .settings-tab-btn:hover {
      color: #0f172a;
    }
    .settings-tab-btn.active {
      color: #2563eb;
      border-bottom-color: #2563eb;
      font-weight: 800;
      background: rgba(37, 99, 235, 0.04);
    }
    .settings-tab-pane {
      display: none;
    }
    .settings-tab-pane.active {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    /* REGION TOAST */
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
    /* COMPACT PILL TOAST (POKETAN BANNER STYLE) */
    .poketan-pill-toast {
      pointer-events: auto;
      background: rgba(255, 255, 255, 0.98);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 9999px;
      padding: 6px 14px 6px 12px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), 0 1px 3px rgba(0, 0, 0, 0.06);
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 0.8rem;
      color: #334155;
      cursor: pointer;
      user-select: none;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      animation: pillSlideDown 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      max-width: 95vw;
      box-sizing: border-box;
      white-space: nowrap;
    }
    .poketan-pill-toast:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.16);
    }
    .poketan-pill-toast.stock-pill {
      border-color: rgba(34, 197, 94, 0.5);
      background: rgba(255, 255, 255, 0.98);
      box-shadow: 0 4px 16px rgba(34, 197, 94, 0.25), 0 1px 3px rgba(0, 0, 0, 0.06);
    }
    @keyframes pillSlideDown {
      from { opacity: 0; transform: translateY(-12px) scale(0.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .pill-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
      display: inline-block;
    }
    .pill-dot.dot-in {
      background: #16a34a;
      box-shadow: 0 0 6px rgba(22, 163, 74, 0.6);
    }
    .pill-dot.dot-out {
      background: #dc2626;
      box-shadow: 0 0 6px rgba(220, 38, 38, 0.5);
    }
    .pill-dot.dot-not {
      background: #f59e0b;
      box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
    }
    .pill-store-name {
      font-weight: 700;
      color: #0f172a;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .pill-text {
      color: #64748b;
      font-weight: 500;
    }
    .pill-status {
      font-weight: 800;
    }
    .pill-status.status-in {
      color: #16a34a;
    }
    .pill-status.status-out {
      color: #dc2626;
    }
    .pill-status.status-not {
      color: #d97706;
    }
    .pill-time {
      color: #64748b;
      font-size: 0.74rem;
      font-weight: 500;
    }
    .pill-close-btn {
      border: none;
      background: transparent;
      color: #94a3b8;
      font-size: 14px;
      line-height: 1;
      padding: 2px 4px;
      margin-left: 4px;
      cursor: pointer;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
    }
    .pill-close-btn:hover {
      color: #1e293b;
      background: #e2e8f0;
    }
  </style>
"""


def render_shared_header() -> str:
    return ""


def render_shared_footer(active_page: str) -> str:
    map_active = " active" if active_page == "map" else ""
    list_active = " active" if active_page == "thongbao" else ""
    return f"""
  <!-- 5. FOOTER BOTTOM NAVIGATION -->
  <footer id="poketan-footer">
    <a href="/map" class="footer-tab-btn{map_active}" id="f-tab-map" title="Bản đồ (地図)">
      <span class="tab-icon">🗺️</span>
      <span class="tab-label">Bản đồ</span>
    </a>

    <a href="/thongbao" class="footer-tab-btn{list_active}" id="f-tab-list" title="Thông báo &amp; Danh sách (一覧)">
      <span class="tab-icon">📋</span>
      <span class="tab-label">Thông báo</span>
      <span id="footer-unread-badge" class="footer-unread-badge" style="display:none;">0</span>
    </a>

    <button type="button" class="footer-tab-btn" id="f-tab-settings" onclick="openSettingsModal()" title="Cài đặt hệ thống &amp; Telegram">
      <span class="tab-icon">⚙️</span>
      <span class="tab-label">Cài đặt</span>
    </button>
  </footer>
"""


SHARED_MODALS_HTML = """
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

  <!-- 8. SETTINGS MODAL (⚙️ Cài đặt & Bộ lọc PokéMap) -->
  <div id="settings-modal" class="modal-overlay" onclick="if(event.target===this) closeSettingsModal()">
    <div class="modal-card" style="max-width:520px; width:95%; max-height:88vh; max-height:88dvh; display:flex; flex-direction:column; padding:0; overflow:hidden;">
      <div class="modal-header" style="background:#0f172a; color:#ffffff; padding:14px 18px; flex-shrink:0;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.15rem;">⚙️</span>
          <div>
            <h3 style="font-weight:800; font-size:1.02rem; color:#ffffff; margin:0;">Cài đặt &amp; Bộ lọc</h3>
            <div style="font-size:0.7rem; color:#94a3b8; font-weight:600; margin-top:1px;">Bộ lọc bản đồ, thông báo Telegram 24/7 &amp; tùy chọn hệ thống</div>
          </div>
        </div>
        <button class="modal-close-btn" style="color:#ffffff;" onclick="closeSettingsModal()">✕</button>
      </div>

      <!-- TAB NAVIGATION -->
      <div class="settings-tab-bar">
        <button type="button" class="settings-tab-btn active" id="tab-btn-set-map" data-tab="map" onclick="switchSettingsTab('map')">
          <span>🗺️</span> <span>Bộ lọc Bản đồ</span>
        </button>
        <button type="button" class="settings-tab-btn" id="tab-btn-set-telegram" data-tab="telegram" onclick="switchSettingsTab('telegram')">
          <span>✈️</span> <span>Telegram 24/7</span>
        </button>
        <button type="button" class="settings-tab-btn" id="tab-btn-set-system" data-tab="system" onclick="switchSettingsTab('system')">
          <span>⚙️</span> <span>Cài đặt chung</span>
        </button>
      </div>

      <!-- TAB CONTENT PANES -->
      <div class="modal-body" style="font-size:0.82rem; max-height:75vh; overflow-y:auto; flex:1; padding:16px;">
        
        <!-- PANE 1: BỘ LỌC BẢN ĐỒ -->
        <div id="settings-pane-map" class="settings-tab-pane active" style="display:flex; flex-direction:column; gap:16px;">
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

          <!-- HIỆU LỰC GHIM CÓ HÀNG -->
          <div style="border:1px solid #bbf7d0; background:#f0fdf4; border-radius:12px; padding:12px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-size:1.1rem;">🎯</span>
                <span style="font-weight:800; font-size:0.88rem; color:#15803d;">Ghim có hàng (In-Stock Pin)</span>
              </div>
            </div>
            <div style="font-size:0.72rem; color:#166534; margin-bottom:8px; line-height:1.4;">
              Thời gian hiển thị hiệu ứng chớp nháy mục tiêu cho các quán đang có hàng.
            </div>
            <div>
              <select id="set-stock-pin-hours" onchange="updateStockPinHours(this.value)" style="width:100%; border:1px solid #86efac; border-radius:8px; padding:7px 10px; font-size:0.78rem; font-weight:700; color:#14532d; background:#ffffff; outline:none; box-shadow:0 1px 2px rgba(0,0,0,0.05); cursor:pointer;">
                <option value="1">⚡ Trong vòng 1 giờ (báo mới nhất)</option>
                <option value="3">⏱️ Trong vòng 3 giờ</option>
                <option value="6">⏱️ Trong vòng 6 giờ</option>
                <option value="12">⏱️ Trong vòng 12 giờ</option>
                <option value="24" selected>📅 Trong vòng 24 giờ (mặc định)</option>
                <option value="all">✨ Luôn luôn có hiệu ứng (tất cả quán có hàng)</option>
                <option value="0">🚫 Tắt hiệu ứng chớp nháy (chỉ hiện chấm xanh tĩnh)</option>
              </select>
            </div>
          </div>

          <!-- FOOTER BUTTONS CHO BỘ LỌC BẢN ĐỒ -->
          <div style="padding-top:10px; border-top:1px solid #e2e8f0; display:flex; gap:10px; margin-top:4px;">
            <button type="button" class="btn-reset-filter" onclick="resetMapFilters()" style="flex:1; padding:9px 12px; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:8px; font-weight:700; font-size:0.8rem; cursor:pointer;">
              🔄 Đặt lại
            </button>
            <button type="button" class="btn-apply-filter" onclick="applyAndCloseMapFilterModal()" style="flex:2; padding:9px 12px; background:#2563eb; color:#ffffff; border:none; border-radius:8px; font-weight:800; font-size:0.8rem; cursor:pointer;">
              ✅ Áp dụng bộ lọc
            </button>
          </div>
        </div>

        <!-- PANE 2: CẤU HÌNH THÔNG BÁO TELEGRAM 24/7 -->
        <div id="settings-pane-telegram" class="settings-tab-pane" style="display:none; flex-direction:column; gap:16px;">
          <div style="border:1px solid #bae6fd; background:#f0f9ff; border-radius:12px; padding:14px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-size:1.15rem;">✈️</span>
                <span style="font-weight:800; font-size:0.92rem; color:#0369a1;">Thông báo Telegram 24/7</span>
              </div>
              <!-- Switch toggle -->
              <label style="position:relative; display:inline-block; width:44px; height:24px; margin:0; flex-shrink:0;">
                <input type="checkbox" id="tg-cfg-enabled" onchange="onTelegramToggleChange(this.checked)" style="opacity:0; width:0; height:0;">
                <span style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:#cbd5e1; transition:.3s; border-radius:24px;" id="tg-cfg-slider"></span>
              </label>
            </div>

            <div style="font-size:0.72rem; color:#0369a1; margin-bottom:12px; line-height:1.4;">
              Tự động gửi tin nhắn báo quán có hàng vào chat hoặc nhóm Telegram ngay khi phát hiện.
            </div>

            <!-- Token & Chat ID -->
            <div style="display:flex; flex-direction:column; gap:10px; margin-bottom:12px;">
              <div>
                <label style="font-weight:800; font-size:0.75rem; color:#334155; display:block; margin-bottom:4px;">Telegram Bot Token:</label>
                <input type="text" id="tg-cfg-token" placeholder="Ví dụ: 123456789:ABCdefGhIJKlmNoPQRstuVWXyz..." style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; font-size:0.8rem; outline:none; background:#ffffff;" />
              </div>
              <div>
                <label style="font-weight:800; font-size:0.75rem; color:#334155; display:block; margin-bottom:4px;">Telegram Chat ID (Nhóm hoặc Cá nhân):</label>
                <input type="text" id="tg-cfg-chatid" placeholder="Ví dụ: -1001234567890 hoặc 987654321" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; font-size:0.8rem; outline:none; background:#ffffff;" />
              </div>
            </div>

            <!-- Bộ lọc tin nhắn gửi Telegram -->
            <div style="border-top:1px dashed #bae6fd; padding-top:10px; margin-bottom:10px;">
              <div style="font-weight:800; color:#0f172a; font-size:0.78rem; margin-bottom:8px; display:flex; align-items:center; gap:5px;">
                <span>🎯</span> <span>Bộ lọc cảnh báo gửi Telegram:</span>
              </div>

              <!-- Grid 2 cột -->
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div>
                  <label style="font-size:0.7rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">📍 Khu vực:</label>
                  <select id="tg-cfg-region" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.75rem; font-weight:700; color:#1e293b; background:#ffffff;">
                    <option value="osaka">📍 Osaka &amp; Kansai</option>
                    <option value="tokyo">📍 Tokyo &amp; Kanto</option>
                    <option value="nagoya">📍 Nagoya &amp; Tokai</option>
                    <option value="all">🗾 Toàn quốc</option>
                  </select>
                </div>

                <div>
                  <label style="font-size:0.7rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">📊 Trạng thái:</label>
                  <select id="tg-cfg-status" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.75rem; font-weight:700; color:#1e293b; background:#ffffff;">
                    <option value="in">🟢 Chỉ khi có hàng</option>
                    <option value="onsite">📸 Chỉ tin tại quán (GPS)</option>
                    <option value="recent">★ Có hàng &amp; Từng có</option>
                    <option value="all">🌐 Nhận tất cả tin</option>
                  </select>
                </div>

                <div>
                  <label style="font-size:0.7rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">🏢 Chuỗi:</label>
                  <select id="tg-cfg-chain" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.75rem; font-weight:700; color:#1e293b; background:#ffffff;">
                    <option value="all">🏢 Tất cả các chuỗi</option>
                    <option value="conbini">🏪 Tất cả Conbini</option>
                    <option value="seven">🏪 7-Eleven</option>
                    <option value="lawson">🏪 Lawson</option>
                    <option value="familymart">🏪 FamilyMart</option>
                    <option value="ministop">🏪 Ministop</option>
                    <option value="specialty">🃏 Card Shop chuyên</option>
                    <option value="electronics">🎮 Điện máy, GEO</option>
                  </select>
                </div>

                <div>
                  <label style="font-size:0.7rem; font-weight:700; color:#475569; display:block; margin-bottom:3px;">⏱️ Độ mới:</label>
                  <select id="tg-cfg-time" style="width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:6px 8px; font-size:0.75rem; font-weight:700; color:#1e293b; background:#ffffff;">
                    <option value="1">⚡ Trong vòng 1 giờ</option>
                    <option value="3">⏱ Trong vòng 3 giờ</option>
                    <option value="6">⏱ Trong vòng 6 giờ</option>
                    <option value="24" selected>📅 Trong vòng 24 giờ</option>
                    <option value="all">⏳ Toàn bộ thời gian</option>
                  </select>
                </div>
              </div>
            </div>

            <div id="tg-test-result" style="display:none; padding:8px 10px; border-radius:8px; font-size:0.75rem; font-weight:700; margin-top:8px;"></div>

            <!-- Buttons test & save -->
            <div style="display:flex; gap:8px; margin-top:10px;">
              <button type="button" onclick="testTelegramWebhook()" style="flex:1; padding:9px 10px; background:#ffffff; color:#0369a1; border:1px solid #bae6fd; border-radius:8px; font-weight:800; font-size:0.78rem; cursor:pointer;">
                🔔 Gửi test
              </button>
              <button type="button" onclick="saveTelegramConfig()" style="flex:2; padding:9px 10px; background:#0284c7; color:#ffffff; border:none; border-radius:8px; font-weight:800; font-size:0.78rem; cursor:pointer;">
                💾 Lưu cấu hình Telegram
              </button>
            </div>
          </div>
        </div>

        <!-- PANE 3: CÀI ĐẶT CHUNG HỆ THỐNG -->
        <div id="settings-pane-system" class="settings-tab-pane" style="display:none; flex-direction:column; gap:16px;">
          <!-- SECTION 2: ÂM THANH TRÊN WEB -->
          <div>
            <div class="filter-group-title">🔔 Thông báo âm thanh trên Web</div>
            <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer; font-weight:700; background:#f8fafc; padding:10px 12px; border-radius:8px; border:1px solid #e2e8f0;">
              <span>🔊 Âm thanh khi phát hiện có hàng</span>
              <input type="checkbox" id="set-sound-check" onchange="updateSettings('soundEnabled', this.checked)">
            </label>
          </div>

          <!-- SECTION 3: VÙNG DỮ LIỆU HIỂN THỊ -->
          <div>
            <div class="filter-group-title">📍 Vùng dữ liệu mặc định (地域・エリア)</div>
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

          <!-- SECTION 4: CẬP NHẬT DỮ LIỆU -->
          <div>
            <button type="button" onclick="refreshData(); closeSettingsModal();" style="width:100%; padding:10px 14px; background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; border-radius:10px; font-weight:800; font-size:0.82rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px;">
              <span>🔄 Cập nhật dữ liệu mới nhất</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- 9. STORE HISTORY MODAL (📜 入荷履歴 / Lịch sử báo cáo & Phân tích) -->
  <div id="store-history-modal" class="modal-overlay" onclick="if(event.target===this) closeStoreHistoryModal()">
    <div class="modal-card" style="max-width:500px; width:95%; max-height:85vh; display:flex; flex-direction:column; padding:0; overflow:hidden;">
      <div class="modal-header" style="padding:14px 16px; border-bottom:1px solid #f1f5f9; flex-shrink:0;">
        <h3 id="hist-modal-title" style="font-size:0.95rem; font-weight:800; display:flex; align-items:center; gap:6px; margin:0;">
          <span>📜</span> <span id="hist-modal-store-name">Lịch sử & Phân tích quy luật</span>
        </h3>
        <button class="modal-close-btn" onclick="closeStoreHistoryModal()">✕</button>
      </div>
      
      <!-- Sub-tabs for switching between History List and Restock Analytics -->
      <div style="display:flex; border-bottom:1px solid #e2e8f0; background:#f8fafc; padding:0 12px; gap:8px; flex-shrink:0;">
        <button type="button" id="tab-btn-hist-list" onclick="switchHistTab('list')" style="padding:10px 14px; font-weight:700; font-size:0.8rem; border:none; background:none; cursor:pointer; border-bottom:2px solid #ef4444; color:#ef4444; display:flex; align-items:center; gap:5px;">
          <span>📜</span> Lịch sử báo cáo
        </button>
        <button type="button" id="tab-btn-hist-analytics" onclick="switchHistTab('analytics')" style="padding:10px 14px; font-weight:600; font-size:0.8rem; border:none; background:none; cursor:pointer; border-bottom:2px solid transparent; color:#64748b; display:flex; align-items:center; gap:5px;">
          <span>📊</span> Phân tích giờ & ngày hàng về
        </button>
      </div>

      <div class="modal-body" style="font-size:0.82rem; overflow-y:auto; flex:1; padding:12px;" id="hist-modal-body">
        <div style="text-align:center; padding:20px; color:#64748b;">Đang tải lịch sử...</div>
      </div>

      <div class="modal-body" style="font-size:0.82rem; overflow-y:auto; flex:1; padding:12px; display:none;" id="hist-modal-analytics">
        <div style="text-align:center; padding:20px; color:#64748b;">Đang phân tích quy luật hàng về...</div>
      </div>
    </div>
  </div>

  <!-- Real-time Live Toast Container for Database updates -->
  <div id="live-report-toast-container" style="position:fixed; top:68px; left:50%; transform:translateX(-50%); z-index:9999; display:flex; flex-direction:column; align-items:center; gap:6px; pointer-events:none; width:max-content; max-width:calc(100vw - 20px);"></div>
"""


# ==============================================================================
# 1. MAP PAGE RENDERER (GET / and GET /map)
# ==============================================================================

MAP_PAGE_CSS = """
  <style>
    /* TOP HEADER: CHỈ HIỂN THỊ LOGO BAWUI TENPAI MAP */
    #poketan-header.map-top-bar {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1100;
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 4px 22px rgba(0, 0, 0, 0.35);
      padding: 0 16px;
      height: 52px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
    }

    .map-top-bar-inner {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .header-brand-center {
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
    }

    .brand-logo-area {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      text-decoration: none;
      user-select: none;
      -webkit-user-select: none;
    }

    .brand-logo-icon {
      flex-shrink: 0;
      filter: drop-shadow(0 2px 8px rgba(56, 189, 248, 0.4));
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .brand-logo-area:hover .brand-logo-icon {
      transform: rotate(20deg) scale(1.08);
    }

    .brand-title-text {
      font-size: 1.15rem;
      font-weight: 900;
      letter-spacing: 0.04em;
      line-height: 1;
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }

    .brand-bawui {
      background: linear-gradient(135deg, #ffffff 40%, #e2e8f0 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-weight: 900;
      letter-spacing: 0.05em;
    }

    .brand-tenpai {
      background: linear-gradient(135deg, #38bdf8 0%, #60a5fa 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.45));
      font-weight: 900;
      letter-spacing: 0.03em;
    }

    @media (max-width: 480px) {
      .brand-title-text {
        font-size: 1.05rem;
        gap: 5px;
      }
      .brand-logo-icon {
        width: 24px;
        height: 24px;
      }
    }

    .stat-seg {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
      padding: 2px 5px;
      border-radius: 6px;
      transition: background 0.15s ease;
    }
    .stat-seg:hover {
      background: rgba(255, 255, 255, 0.12);
    }
    .stat-seg b {
      font-weight: 800;
    }
    .stat-sep {
      color: rgba(255, 255, 255, 0.3);
      font-size: 0.75rem;
      pointer-events: none;
    }

    .stat-total { color: #f8fafc; }
    .stat-in { color: #4ade80; }
    .stat-in b { color: #22c55e; }
    .stat-out { color: #f87171; }
    .stat-out b { color: #ef4444; }
    .stat-not { color: #fbbf24; }
    .stat-not b { color: #f59e0b; }
    .stat-unk { color: #cbd5e1; }
    .stat-unk b { color: #e2e8f0; }

    /* LEAFLET CONTROLS OFFSET BELOW HEADER */
    .leaflet-top {
      top: 60px !important;
    }
    #live-report-toast-container {
      top: 62px !important;
    }
    #region-load-toast {
      position: fixed;
      top: 60px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 1500;
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
    #gps-btn.tracking {
      background: #2563eb;
      color: #ffffff;
      border-color: #ffffff;
      box-shadow: 0 0 16px rgba(37, 99, 235, 0.85), 0 4px 18px rgba(0, 0, 0, 0.28);
    }
    #gps-btn.locating {
      border-color: #3b82f6;
      animation: gpsPulseAnim 0.8s infinite alternate;
    }
    @keyframes gpsPulseAnim {
      from { transform: scale(1); box-shadow: 0 0 6px rgba(59, 130, 246, 0.5); }
      to { transform: scale(1.1); box-shadow: 0 0 18px rgba(59, 130, 246, 0.9); }
    }

    /* USER LOCATION MARKER WITH LIVE PULSE */
    .user-location-marker {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #2563eb;
      border: 3px solid #ffffff;
      box-shadow: 0 0 10px rgba(37, 99, 235, 0.85);
      position: relative;
    }
    .user-location-marker::after {
      content: '';
      position: absolute;
      top: -8px;
      left: -8px;
      right: -8px;
      bottom: -8px;
      border-radius: 50%;
      background: rgba(37, 99, 235, 0.4);
      animation: userPulse 2s ease-out infinite;
      pointer-events: none;
    }
    @keyframes userPulse {
      0% { transform: scale(0.6); opacity: 0.9; }
      100% { transform: scale(2.6); opacity: 0; }
    }

    /* MARKER CLUSTERS & IN-STOCK PIN */
    .poketan-cluster-wrap { background: transparent; border: none; }
    .poketan-cluster {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid #4338ca;
      color: #1e1b4b;
      font-weight: 800;
      font-size: 0.78rem;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
      transition: all 0.15s ease;
    }
    .poketan-cluster.has-stock {
      border-color: #16a34a;
      box-shadow: 0 0 14px rgba(22, 163, 74, 0.85), 0 2px 6px rgba(0,0,0,0.25);
      background: #16a34a;
      color: #ffffff;
    }

    /* POKETAN STOCK PIN (CONCENTRIC CIRCLE TARGET + TIME PILL) */
    .poketan-pin-wrap {
      background: transparent;
      border: none;
    }
    .poketan-stock-pin-v2 {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      cursor: pointer;
      white-space: nowrap;
      z-index: 3000 !important;
    }
    .stock-circle-target {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: rgba(16, 185, 129, 0.28);
      border: 2.5px solid #10b981;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 16px rgba(16, 185, 129, 0.9), 0 2px 6px rgba(0,0,0,0.35);
      position: relative;
    }
    .stock-circle-target::before, .stock-circle-target::after {
      content: '';
      position: absolute;
      top: -5px;
      left: -5px;
      right: -5px;
      bottom: -5px;
      border-radius: 50%;
      border: 2px solid #10b981;
      animation: stockRipple 2s cubic-bezier(0, 0.2, 0.8, 1) infinite;
      pointer-events: none;
    }
    .stock-circle-target::after {
      animation-delay: 1s;
    }
    @keyframes stockRipple {
      0% { transform: scale(0.6); opacity: 1; border-color: #34d399; }
      100% { transform: scale(2.4); opacity: 0; border-color: #059669; }
    }
    .stock-circle-inner {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #34d399;
    }
    .stock-time-badge {
      background: rgba(15, 23, 42, 0.94);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      color: #34d399;
      border: 1px solid rgba(52, 211, 153, 0.45);
      font-size: 0.72rem;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 9999px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.35);
      letter-spacing: -0.2px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    /* CONBINI CIRCULAR DOT PINS - 100% CLEAN CIRCLES, NO LETTERS */
    .chain-pin-wrap {
      background: transparent;
      border: none;
    }
    .chain-pin {
      border-radius: 50%;
      border: 2px solid #ffffff;
      cursor: pointer;
      position: relative;
      transition: transform 0.15s ease;
      user-select: none;
    }
    .chain-pin:hover, .chain-pin-mini:hover {
      transform: scale(1.6);
      z-index: 1000 !important;
    }

    /* STATUS COLORS FOR CIRCULAR PINS (ZOOM >= 16) */
    .chain-pin.status-in {
      width: 14px;
      height: 14px;
      background: #16a34a !important;
      border-color: #ffffff;
      box-shadow: 0 0 10px rgba(22, 163, 74, 0.85);
    }
    .chain-pin.status-out {
      width: 11px;
      height: 11px;
      background: #ef4444 !important;
      border-color: #ffffff;
      box-shadow: 0 1px 4px rgba(239, 68, 68, 0.5);
    }
    .chain-pin.status-not {
      width: 10px;
      height: 10px;
      background: #f59e0b !important;
      border-color: #ffffff;
      box-shadow: 0 1px 4px rgba(245, 158, 11, 0.5);
    }
    .chain-pin.status-unk {
      width: 9px;
      height: 9px;
      background: #94a3b8 !important;
      border-color: #ffffff;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    }

    /* CIRCULAR MINI DOT PINS (ZOOM 14 - 15) */
    .chain-pin-mini {
      border-radius: 50%;
      border: 1.5px solid #ffffff;
      cursor: pointer;
      transition: transform 0.15s ease;
    }
    .chain-pin-mini.status-in {
      width: 12px;
      height: 12px;
      background: #16a34a !important;
      box-shadow: 0 0 8px rgba(22, 163, 74, 0.8);
    }
    .chain-pin-mini.status-out {
      width: 10px;
      height: 10px;
      background: #ef4444 !important;
      box-shadow: 0 1px 3px rgba(239, 68, 68, 0.45);
    }
    .chain-pin-mini.status-not {
      width: 9px;
      height: 9px;
      background: #f59e0b !important;
      box-shadow: 0 1px 3px rgba(245, 158, 11, 0.45);
    }
    .chain-pin-mini.status-unk {
      width: 7px;
      height: 7px;
      background: #94a3b8 !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
      opacity: 0.85;
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
      gap: 5px;
      padding: 9px 8px;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      text-decoration: none;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.76rem;
      border: none;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
      transition: all 0.15s ease;
    }
    .btn-popup-maps:hover {
      background: linear-gradient(135deg, #1d4ed8, #1e40af);
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.5);
      transform: translateY(-1px);
    }
    .btn-popup-maps:active {
      transform: translateY(0);
    }
    .btn-popup-hist {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      padding: 9px 8px;
      background: linear-gradient(135deg, #0f172a, #1e293b);
      color: white;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.76rem;
      border: 1px solid rgba(255, 255, 255, 0.12);
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.25);
      transition: all 0.15s ease;
    }
    .btn-popup-hist:hover {
      background: linear-gradient(135deg, #1e293b, #334155);
      transform: translateY(-1px);
    }
    .btn-popup-hist:active {
      transform: translateY(0);
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
    footer = render_shared_footer("map")

    map_filter_modal = """
  <!-- MAP FILTER MODAL CONTAINER (Aliased to Settings Modal Map Tab) -->
  <div id="map-filter-modal" style="display:none;"></div>
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
  <!-- TOP HEADER (CHỈ HIỂN THỊ LOGO BAWUI TENPAI MAP) -->
  <header id="poketan-header" class="map-top-bar">
    <div class="map-top-bar-inner header-brand-center">
      <a href="/" class="brand-logo-area" title="BAWUI TENPAI MAP">
        <svg class="brand-logo-icon" width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="15" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
          <path d="M1 16 A15 15 0 0 1 31 16 Z" fill="url(#pokeTopGrad)"/>
          <path d="M1 16 A15 15 0 0 0 31 16 Z" fill="#ffffff"/>
          <line x1="1" y1="16" x2="31" y2="16" stroke="#0f172a" stroke-width="2.5"/>
          <circle cx="16" cy="16" r="5" fill="#0f172a"/>
          <circle cx="16" cy="16" r="3.2" fill="#ffffff"/>
          <circle cx="16" cy="16" r="1.5" fill="#38bdf8"/>
          <defs>
            <linearGradient id="pokeTopGrad" x1="1" y1="1" x2="31" y2="16" gradientUnits="userSpaceOnUse">
              <stop stop-color="#ef4444"/>
              <stop offset="1" stop-color="#dc2626"/>
            </linearGradient>
          </defs>
        </svg>
        <span class="brand-title-text"><span class="brand-bawui">BAWUI</span> <span class="brand-tenpai">TENPAI MAP</span></span>
      </a>
    </div>
  </header>
  <!-- Hidden elements for test and script compatibility -->
  <div id="map-counter-pill" style="display:none !important;"></div>
  <div id="btn-map-filter-clear" style="display:none !important;"></div>
  <div id="map-filter-badge" style="display:none !important;"></div>

  <!-- Region loading toast -->
  <div id="region-load-toast" style="display:none;">
    <span id="region-load-icon">⚡</span>
    <span id="region-load-text">Đang chuyển vùng...</span>
  </div>

  <main id="app-main">
    <div id="map"></div>
    <button id="gps-btn" class="tracking" onclick="locateUser(true)" title="現在地を表示">
      📍
    </button>
  </main>
""" + footer + map_filter_modal + SHARED_MODALS_HTML + """
  <script>
    // 1. APP STATE & REGIONS
    const REGIONS = {
      'osaka': { id: 'osaka', name: '大阪・関西', center: [34.6937, 135.5023], zoom: 13, defaultCity: 'なんば', prefs: ['osaka'] },
      'tokyo': { id: 'tokyo', name: '東京・神奈川', center: [35.6895, 139.6917], zoom: 13, defaultCity: '横浜', prefs: ['tokyo', 'kanagawa'] },
      'nagoya': { id: 'nagoya', name: '名古屋・東海', center: [35.1815, 136.9066], zoom: 13, defaultCity: '名古屋駅', prefs: ['aichi', 'gifu', 'mie'] },
      'all': { id: 'all', name: '全エリア (全国)', center: [34.6937, 135.5023], zoom: 10, defaultCity: '全エリア', prefs: ['osaka', 'tokyo', 'kanagawa', 'aichi', 'gifu', 'mie'] }
    };

    const urlRegion = new URLSearchParams(window.location.search).get('region');
    let currentRegion = (urlRegion && REGIONS[urlRegion]) ? urlRegion : (localStorage.getItem('poketan_selected_region') || localStorage.getItem('poketan_map_region') || 'osaka');
    if (!REGIONS[currentRegion]) currentRegion = 'osaka';
    if (urlRegion && REGIONS[urlRegion]) {
      try {
        localStorage.setItem('poketan_selected_region', currentRegion);
        localStorage.setItem('poketan_map_region', currentRegion);
      } catch(e) {}
    }
    let currentPref = REGIONS[currentRegion].prefs[0] || 'osaka';

    let storesDict = {};
    let configData = {};
    let serverTimeOffset = 0; // seconds: serverNow - browserNow

    function getServerNowSec() {
      return Math.floor(Date.now() / 1000) + serverTimeOffset;
    }

    let mapRegionFilter = currentRegion;
    let mapChainFilter = localStorage.getItem('poketan_map_chain') || 'all';
    let mapStatusFilter = localStorage.getItem('poketan_map_status') || 'all';
    let mapTimeFilter = localStorage.getItem('poketan_map_time') || 'all';

    function saveMapFiltersToStorage() {
      try {
        if (mapRegionFilter) {
          localStorage.setItem('poketan_selected_region', mapRegionFilter);
          localStorage.setItem('poketan_map_region', mapRegionFilter);
        }
        localStorage.setItem('poketan_map_chain', mapChainFilter || 'all');
        localStorage.setItem('poketan_map_status', mapStatusFilter || 'all');
        localStorage.setItem('poketan_map_time', String(mapTimeFilter || 'all'));
      } catch(e) {}
    }

    let userLat = null, userLng = null, userMarker = null, userCircle = null, hasCenteredOnUser = false;
    let gpsWatchId = null;
    let isFollowingUser = true;
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
      // Auto-center on GPS if user is within ~80km of the region center
      const dLat = Math.abs(userLat - initialCenter[0]);
      const dLng = Math.abs(userLng - initialCenter[1]);
      if (dLat < 0.8 && dLng < 0.8) {
        initialCenter = [userLat, userLng];
        initialZoom = 15;
        hasCenteredOnUser = true;
      }
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

    // Map drag listener: pause auto-following so user can explore freely
    map.on('dragstart', () => {
      isFollowingUser = false;
      updateGpsBtnState();
    });

    // Automatically prefetch store history and dynamically update count bar when popup opens
    map.on('popupopen', (e) => {
      try {
        const popupNode = e.popup.getElement();
        if (!popupNode) return;
        const countBar = popupNode.querySelector('[id^="popup-counts-"]');
        if (!countBar) return;
        const storeId = countBar.id.replace('popup-counts-', '');
        if (!storeId) return;

        if (!storeHistoryCache[storeId]) {
          fetch(`/api/store_history/${storeId}`)
            .then(r => r.ok ? r.json() : null)
            .then(hist => {
              if (!hist || !Array.isArray(hist)) return;
              storeHistoryCache[storeId] = hist;
              let cIn = 0, cOut = 0;
              const seenIn = new Set(), seenOut = new Set();
              hist.forEach(item => {
                const ts = item.timestamp || item.formatted_time;
                if (item.status_code === 'i') {
                  if (!seenIn.has(ts)) { seenIn.add(ts); cIn++; }
                } else if (item.status_code === 'o') {
                  if (!seenOut.has(ts)) { seenOut.add(ts); cOut++; }
                }
              });
              storeCountsCache[storeId] = { in: cIn, out: cOut };
              const activeBar = document.getElementById(`popup-counts-${storeId}`);
              if (activeBar) {
                activeBar.innerHTML = `
                  <span class="report-count-tag tag-green">🟢 Có: <b>${cIn}</b> lần</span>
                  <span class="report-count-tag tag-red">🔴 Hết: <b>${cOut}</b> lần</span>
                `;
              }
            })
            .catch(() => {});
        }
      } catch (err) {
        console.warn('Popup count sync error:', err);
      }
    });

    let clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 52,
      disableClusteringAtZoom: 17,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      iconCreateFunction: function(cluster) {
        const count = cluster.getChildCount();
        const hasStock = cluster.getAllChildMarkers().some(m => m.options.hasStock);
        return L.divIcon({
          html: `<div class="poketan-cluster ${hasStock ? 'has-stock' : ''}">${count}</div>`,
          className: 'poketan-cluster-wrap',
          iconSize: L.point(30, 30)
        });
      }
    });
    map.addLayer(clusterGroup);
    const stockLayer = L.layerGroup().addTo(map);

    // 3. STORE STATUS & ICONS

    function getStoreStatusInfo(store) {
      let code = (store.status || 'u').toLowerCase();
      let timestamp = Number(store.last_timestamp) || 0;
      let onsite = !!store.onsite;
      let packs = Array.isArray(store.packs) ? store.packs : [];
      let reported_at = store.last_reported_at || '';

      let timeAgo = '';
      if (timestamp > 0) {
        if (!reported_at) {
          const jstDate = new Date((timestamp + 9 * 3600) * 1000);
          reported_at = `${String(jstDate.getUTCHours()).padStart(2, '0')}:${String(jstDate.getUTCMinutes()).padStart(2, '0')} (${jstDate.getUTCMonth()+1}/${jstDate.getUTCDate()})`;
        }
        timeAgo = formatTimeAgoJp(timestamp);
      }
      const labelMap = { 'i': '在庫あり', 'o': '在庫なし', 'n': '扱ってない', 'u': '未確認' };
      return {
        code,
        label: labelMap[code] || '未確認',
        packs,
        reported_at,
        timeAgo,
        onsite,
        timestamp
      };
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

    const CHAIN_META = {
      'seven': { label: '7-Eleven', short: '7E', icon: '🏪', bg: '#00843d', border: '#ea580c', color: '#fff' },
      'lawson': { label: 'Lawson', short: 'LAW', icon: '🏪', bg: '#0284c7', border: '#38bdf8', color: '#fff' },
      'familymart': { label: 'FamilyMart', short: 'FM', icon: '🏪', bg: '#10b981', border: '#0284c7', color: '#fff' },
      'ministop': { label: 'Ministop', short: 'MS', icon: '🏪', bg: '#f59e0b', border: '#1e3a8a', color: '#1e293b' },
      'specialty': { label: 'Card Shop', short: '🃏', icon: '🃏', bg: '#8b5cf6', border: '#c084fc', color: '#fff' },
      'geo': { label: 'GEO', short: 'GEO', icon: '🎮', bg: '#4f46e5', border: '#818cf8', color: '#fff' },
      'joshin': { label: 'Joshin', short: 'JS', icon: '🎮', bg: '#ef4444', border: '#fca5a5', color: '#fff' },
      'edion': { label: 'EDION', short: 'ED', icon: '🎮', bg: '#2563eb', border: '#93c5fd', color: '#fff' },
      'aeon': { label: 'AEON', short: 'AE', icon: '🛒', bg: '#db2777', border: '#f472b6', color: '#fff' },
      'yamada': { label: 'Yamada', short: 'YM', icon: '🎮', bg: '#dc2626', border: '#f87171', color: '#fff' },
      'biccamera': { label: 'BicCamera', short: 'BC', icon: '🎮', bg: '#dc2626', border: '#f87171', color: '#fff' },
      'yodobashi': { label: 'Yodobashi', short: 'YD', icon: '🎮', bg: '#0f172a', border: '#e11d48', color: '#fff' },
      'toysrus': { label: 'Toys"R"Us', short: 'TRU', icon: '🧸', bg: '#2563eb', border: '#f59e0b', color: '#fff' },
      'ks': { label: "K's", short: 'KS', icon: '🎮', bg: '#dc2626', border: '#f87171', color: '#fff' },
      'other': { label: 'Store', short: '🏪', icon: '🏪', bg: '#475569', border: '#94a3b8', color: '#fff' }
    };

    // UNIFORM STATUS THEMES (Same for ALL conbinis)
    // 🟢 Green = Có hàng | 🔴 Red = Không có | 🟡 Yellow = Không bán | ⚪ Gray = Chưa có báo cáo
    function getStatusTheme(code, isFresh = true) {
      if (code === 'i') {
        return { bg: '#16a34a', cls: 'status-in', label: 'Có hàng' };
      } else if (code === 'o') {
        return { bg: '#ef4444', cls: 'status-out', label: 'Không có' };
      } else if (code === 'n') {
        return { bg: '#f59e0b', cls: 'status-not', label: 'Không bán thẻ' };
      } else {
        return { bg: '#94a3b8', cls: 'status-unk', label: 'Chưa có báo cáo' };
      }
    }

    function createStockPinIcon(timeAgo, timestamp) {
      return L.divIcon({
        html: `<div class="poketan-pin-wrapper">
                 <div class="poketan-stock-pin-v2" title="Có hàng">
                   <div class="stock-circle-target">
                     <div class="stock-circle-inner"></div>
                   </div>
                   <div class="stock-time-badge" data-timestamp="${timestamp || 0}">${escapeHtml(timeAgo || 'たった今')}</div>
                 </div>
               </div>`,
        className: 'poketan-pin-wrap',
        iconSize: [85, 24],
        iconAnchor: [11, 12]
      });
    }

    function createMiniChainPinIcon(store, info, isFresh = true) {
      const theme = getStatusTheme(info.code, isFresh);
      const size = (info.code === 'i' && isFresh) ? 12 : (info.code === 'o' ? 10 : (info.code === 'n' ? 9 : 7));
      const half = size / 2;
      return L.divIcon({
        html: `<div class="chain-pin-mini ${theme.cls}" title="${escapeHtml(store.name)} (${theme.label})"></div>`,
        className: 'chain-pin-wrap',
        iconSize: [size, size],
        iconAnchor: [half, half]
      });
    }

    function createChainPinIcon(store, info, isFresh = true) {
      const theme = getStatusTheme(info.code, isFresh);
      const size = (info.code === 'i' && isFresh) ? 14 : (info.code === 'o' ? 11 : (info.code === 'n' ? 10 : 9));
      const half = size / 2;

      return L.divIcon({
        html: `<div class="chain-pin ${theme.cls}" title="${escapeHtml(store.name)} (${theme.label})"></div>`,
        className: 'chain-pin-wrap',
        iconSize: [size, size],
        iconAnchor: [half, half]
      });
    }

    const greenDotIcon = L.divIcon({ html: '<div style="width:9px;height:9px;border-radius:50%;background:#16a34a;border:1.5px solid #fff;box-shadow:0 0 8px rgba(22,163,74,0.85);"></div>', className: 'd-wrap', iconSize: [9, 9], iconAnchor: [4.5, 4.5] });
    const redDotIcon = L.divIcon({ html: '<div style="width:8px;height:8px;border-radius:50%;background:#ef4444;border:1.5px solid #fff;box-shadow:0 1px 3px rgba(239,68,68,0.5);"></div>', className: 'd-wrap', iconSize: [8, 8], iconAnchor: [4, 4] });
    const yellowDotIcon = L.divIcon({ html: '<div style="width:8px;height:8px;border-radius:50%;background:#f59e0b;border:1.5px solid #fff;box-shadow:0 1px 3px rgba(245,158,11,0.5);"></div>', className: 'd-wrap', iconSize: [8, 8], iconAnchor: [4, 4] });
    const grayDotIcon = L.divIcon({ html: '<div style="width:6px;height:6px;border-radius:50%;background:#94a3b8;border:1px solid #fff;opacity:0.85;"></div>', className: 'd-wrap', iconSize: [6, 6], iconAnchor: [3, 3] });

    function matchesChainFilter(chain, filter) {
      if (!filter || filter === 'all') return true;
      const c = (chain || '').toLowerCase().trim();
      if (filter === 'conbini') return ['seven', 'lawson', 'familymart', 'ministop'].includes(c);
      if (filter === 'seven') return c === 'seven';
      if (filter === 'lawson') return c === 'lawson';
      if (filter === 'familymart') return c === 'familymart';
      if (filter === 'ministop') return c === 'ministop';
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
      const now = Math.floor(Date.now() / 1000);
      const clusterBatch = [];
      let newestInStore = null, maxTimestamp = 0;
      let visibleCount = 0, inStockVisibleCount = 0;
      let outCount = 0, notCount = 0, unkCount = 0;

      const targetRegion = mapRegionFilter || currentRegion || 'osaka';
      const allowedPrefs = (REGIONS[targetRegion] ? REGIONS[targetRegion].prefs : [targetRegion]) || ['osaka'];

      const maxSec = (mapTimeFilter !== 'all') ? parseInt(mapTimeFilter, 10) * 3600 : null;

      for (const store of allStores) {
        if (!store.lat || !store.lng) continue;
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }

        const info = getStoreStatusInfo(store);
        const reportAge = (info.timestamp > 0) ? (now - info.timestamp) : Infinity;

        // Time filter: if user selected a time filter (e.g. 1h, 3h, 6h, 12h, 24h), hide stores older than maxSec
        if (maxSec !== null && info.timestamp > 0 && reportAge > maxSec) {
          continue;
        }

        // Status filter
        if (mapStatusFilter === 'in') {
          if (info.code !== 'i') continue;
        } else if (mapStatusFilter === 'onsite') {
          if (!info.onsite || info.code !== 'i') continue;
        } else if (mapStatusFilter === 'out') {
          if (info.code !== 'o') continue;
        } else if (mapStatusFilter === 'n') {
          if (info.code !== 'n') continue;
        } else if (mapStatusFilter === 'recent') {
          const isRecentReport = info.timestamp > 0 && reportAge <= 86400 * 7;
          if (!isRecentReport) continue;
        } else if (mapStatusFilter === 'unknown') {
          if (info.code !== 'u' && info.timestamp > 0) continue;
        }

        // Chain filter
        if (!matchesChainFilter(store.chain, mapChainFilter)) continue;

        visibleCount++;
        if (info.code === 'i') inStockVisibleCount++;
        else if (info.code === 'o') outCount++;
        else if (info.code === 'n') notCount++;
        else unkCount++;

        if (info.code === 'i' && info.timestamp > maxTimestamp) {
          maxTimestamp = info.timestamp;
          newestInStore = store;
        }

        const currentZoom = map.getZoom();

        // 🟢 CÓ HÀNG (i): Kiểm tra hiệu lực thời gian hiệu ứng Ghim Có hàng (In-Stock Pin)
        const stockEffectSetting = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
        let hasStockEffect = false;
        if (info.code === 'i') {
          if (stockEffectSetting === 'all') {
            hasStockEffect = true;
          } else if (stockEffectSetting === '0' || stockEffectSetting === 'off') {
            hasStockEffect = false;
          } else {
            const effectMaxSec = (parseInt(stockEffectSetting, 10) || 24) * 3600;
            hasStockEffect = (info.timestamp > 0) ? (reportAge <= effectMaxSec) : true;
          }
        }

        if (info.code === 'i' && hasStockEffect) {
          // Có hàng và trong thời gian hiệu lực -> Hiện vòng tròn mục tiêu chớp nháy + thanh thời gian nổi
          const pinIcon = createStockPinIcon(info.timeAgo, info.timestamp);
          const m = L.marker([store.lat, store.lng], { icon: pinIcon, zIndexOffset: 3000 });
          m.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          stockLayer.addLayer(m);
        } else if (info.code === 'i') {
          // Có hàng nhưng đã quá hạn thời gian hiệu ứng -> Hiện chấm ghim xanh tĩnh không chớp nháy
          let pin;
          if (currentZoom >= 16 || mapChainFilter !== 'all') {
            pin = createChainPinIcon(store, info, false);
          } else if (currentZoom >= 14) {
            pin = createMiniChainPinIcon(store, info, false);
          } else {
            pin = greenDotIcon;
          }
          const sm = L.marker([store.lat, store.lng], { icon: pin, hasStock: true, zIndexOffset: 2500 });
          sm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          stockLayer.addLayer(sm);
        } else {
          // 🔴 ĐỎ: HẾT HÀNG (o) | 🟡 VÀNG: KHÔNG BÁN THẺ (n) | ⚪ XÁM: CHƯA CÓ BÁO CÁO (u)
          let pin;
          if (currentZoom >= 16 || mapChainFilter !== 'all') {
            pin = createChainPinIcon(store, info, false);
          } else if (currentZoom >= 14) {
            pin = createMiniChainPinIcon(store, info, false);
          } else {
            if (info.code === 'o') pin = redDotIcon;
            else if (info.code === 'n') pin = yellowDotIcon;
            else pin = grayDotIcon;
          }
          const cm = L.marker([store.lat, store.lng], { icon: pin, hasStock: false });
          cm.bindPopup(() => createPopupHtml(store, info), { maxWidth: 300 });
          clusterBatch.push(cm);
        }
      }

      if (clusterBatch.length > 0) clusterGroup.addLayers(clusterBatch);

      // Update counter pill with clear breakdown exactly matching user's design
      const counterEl = document.getElementById('map-counter-pill');
      if (counterEl) {
        let html = `<span class="stat-seg stat-total" onclick="quickFilterMapStatus('all')" title="Xem tất cả"><b>${visibleCount.toLocaleString()}</b> quán</span>`;
        if (inStockVisibleCount > 0) {
          html += `<span class="stat-sep">•</span><span class="stat-seg stat-in" onclick="quickFilterMapStatus('in')" title="Lọc: Có hàng">🟢 <b>${inStockVisibleCount}</b> có</span>`;
        }
        if (outCount > 0) {
          html += `<span class="stat-sep">•</span><span class="stat-seg stat-out" onclick="quickFilterMapStatus('out')" title="Lọc: Hết hàng">🔴 <b>${outCount}</b> hết</span>`;
        }
        if (notCount > 0) {
          html += `<span class="stat-sep">•</span><span class="stat-seg stat-not" onclick="quickFilterMapStatus('n')" title="Lọc: Không bán thẻ">🟡 <b>${notCount}</b> ko bán</span>`;
        }
        if (unkCount > 0) {
          html += `<span class="stat-sep">•</span><span class="stat-seg stat-unk" onclick="quickFilterMapStatus('unknown')" title="Lọc: Chưa rõ">⚪ <b>${unkCount}</b> chưa tin</span>`;
        }
        counterEl.innerHTML = html;
      }

      // Update footer unread notifications badge
      updateFooterUnreadBadge();
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
      let statusBg = '#f1f5f9', statusColor = '#64748b', statusText = '⚪ Chưa có báo cáo (未確認)';
      if (info.code === 'i') {
        statusBg = '#dcfce7'; statusColor = '#15803d'; statusText = '🟢 Có hàng (あった)';
      } else if (info.code === 'o') {
        statusBg = '#fee2e2'; statusColor = '#b91c1c'; statusText = '🔴 Không có / Hết (なかった)';
      } else if (info.code === 'n') {
        statusBg = '#fef3c7'; statusColor = '#b45309'; statusText = '🟡 Không bán thẻ (扱ってない)';
      }

      const packs = info.packs.length ? `<div style="font-size:0.74rem; margin-top:4px;"><b>📦 Gói:</b> ${escapeHtml(info.packs.join(', '))}</div>` : '';
      const time = (info.timestamp > 0 && info.timeAgo) ? `<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">🕒 Báo: <b class="popup-time-ago" data-timestamp="${info.timestamp}">${escapeHtml(info.timeAgo)}</b> (${escapeHtml(info.reported_at)})</div>` : '';
      const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
      const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((store.name || '') + ' ' + (store.address || ''))}`;

      let counts = storeCountsCache[store.id];
      if (!counts && storeHistoryCache[store.id]) {
        let cIn = 0, cOut = 0;
        const sIn = new Set(), sOut = new Set();
        storeHistoryCache[store.id].forEach(item => {
          const ts = item.timestamp || item.formatted_time;
          if (item.status_code === 'i') { if (!sIn.has(ts)) { sIn.add(ts); cIn++; } }
          else if (item.status_code === 'o') { if (!sOut.has(ts)) { sOut.add(ts); cOut++; } }
        });
        counts = { in: cIn, out: cOut };
        storeCountsCache[store.id] = counts;
      }
      if (!counts) {
        counts = { in: info.code === 'i' ? 1 : 0, out: info.code === 'o' ? 1 : 0 };
      }

      return `
        <div>
          <div class="popup-store-title">${escapeHtml(store.name || '')}</div>
          <div class="popup-store-chain">${escapeHtml(chain)}</div>
          <div class="popup-status-badge" style="background:${statusBg}; color:${statusColor};">${statusText}</div>
          <div class="popup-report-counts-bar" id="popup-counts-${escapeHtml(store.id)}">
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

    // 5.5 FOOTER UNREAD NOTIFICATIONS BADGE
    function updateFooterUnreadBadge() {
      const badgeEl = document.getElementById('footer-unread-badge');
      if (!badgeEl) return;

      const lastReadTs = parseInt(localStorage.getItem('poketan_last_read_ts') || '0', 10);
      const allStores = Object.values(storesDict);
      const targetRegion = mapRegionFilter || currentRegion || 'osaka';
      const allowedPrefs = (REGIONS[targetRegion] ? REGIONS[targetRegion].prefs : [targetRegion]) || ['osaka'];

      let unreadCount = 0;
      for (const store of allStores) {
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }
        const info = getStoreStatusInfo(store);
        if (info && info.code === 'i') {
          const ts = info.timestamp || 0;
          if (lastReadTs === 0 || ts > lastReadTs) {
            unreadCount++;
          }
        }
      }

      if (unreadCount > 0) {
        badgeEl.innerText = unreadCount > 99 ? '99+' : String(unreadCount);
        badgeEl.style.display = 'inline-flex';
      } else {
        badgeEl.style.display = 'none';
      }
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
    function setMapTimeFilter(tm) {
      mapTimeFilter = tm;
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }
    function updateMapFilterUI() {
      ['all', 'in', 'recent', 'onsite', 'out', 'n', 'unknown'].forEach(st => {
        const btn = document.getElementById(`map-chip-${st}`);
        if (btn) btn.classList.toggle('active', mapStatusFilter === st);
      });
      let count = 0;
      if (mapStatusFilter !== 'all') count++;
      if (mapChainFilter !== 'all') count++;
      if (mapTimeFilter !== 'all') count++;
      const badge = document.getElementById('map-filter-badge');
      if (badge) {
        badge.innerText = count;
        badge.style.display = count > 0 ? 'inline-flex' : 'none';
      }
      const clearBtn = document.getElementById('btn-map-filter-clear');
      if (clearBtn) {
        clearBtn.style.display = count > 0 ? 'inline-flex' : 'none';
      }
    }

    function resetAndClearMapFilters() {
      mapStatusFilter = 'all';
      mapChainFilter = 'all';
      mapTimeFilter = 'all';
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }

    function quickFilterMapStatus(status) {
      if (mapStatusFilter === status) {
        mapStatusFilter = 'all';
      } else {
        mapStatusFilter = status;
      }
      saveMapFiltersToStorage();
      updateMapFilterUI();
      renderMapMarkers();
    }

    let lastRenderZoom = map.getZoom();
    map.on('zoomend', () => {
      const z = map.getZoom();
      const oldTier = lastRenderZoom < 14 ? 0 : (lastRenderZoom < 16 ? 1 : 2);
      const newTier = z < 14 ? 0 : (z < 16 ? 1 : 2);
      if (oldTier !== newTier) {
        lastRenderZoom = z;
        renderMapMarkers();
      }
    });

    // Dynamic Region Store Loader
    const loadedRegions = new Set();
    async function ensureStoresLoadedForRegion(reg) {
      if (!reg) return;
      if (loadedRegions.has(reg)) return;
      if (reg === 'all' && loadedRegions.has('all')) return;
      try {
        const res = await fetch('/api/stores_data?region=' + encodeURIComponent(reg));
        if (res.ok) {
          const newStores = await res.json();
          Object.assign(storesDict, newStores);
          loadedRegions.add(reg);
          for (const sid in newStores) {
            const s = newStores[sid];
            if (s && s.status === 'i' && s.last_timestamp) {
              seenToastKeys.add(`${sid}_${s.last_timestamp}_i`);
            }
          }
          fetch('/api/report_counts?region=' + encodeURIComponent(reg))
            .then(r => r.ok ? r.json() : null)
            .then(c => { if (c) Object.assign(storeCountsCache, c); })
            .catch(() => {});
          renderMapMarkers();
        }
      } catch (e) {
        console.warn('Error loading stores for region:', reg, e);
      }
    }

    // Map Filter Modal (Integrated as tab in Settings Modal: Region, Chain & In-Stock Pin)
    let mapModalTempRegion = currentRegion, mapModalTempChain = 'all';
    function openMapFilterModal() {
      mapModalTempRegion = mapRegionFilter || currentRegion;
      mapModalTempChain = mapChainFilter;
      openSettingsModal('map');
    }
    function closeMapFilterModal() {
      closeSettingsModal();
    }
    function syncMapFilterModalUI() {
      document.querySelectorAll('#map-modal-region-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempRegion));
      document.querySelectorAll('#map-modal-chain-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempChain));
      const pinSelect = document.getElementById('set-stock-pin-hours');
      if (pinSelect) {
        const curHours = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
        pinSelect.value = curHours;
      }
    }
    function selectMapModalRegion(val) { mapModalTempRegion = val; syncMapFilterModalUI(); }
    function selectMapModalChain(val) { mapModalTempChain = val; syncMapFilterModalUI(); }
    function selectMapModalStatus(val) {}
    function selectMapModalTime(val) {}
    function resetMapFilters() {
      mapModalTempRegion = 'osaka';
      mapModalTempChain = 'all';
      const pinSelect = document.getElementById('set-stock-pin-hours');
      if (pinSelect) pinSelect.value = '24';
      syncMapFilterModalUI();
    }
    function applyAndCloseMapFilterModal() {
      const regionChanged = (mapModalTempRegion !== mapRegionFilter);
      mapRegionFilter = mapModalTempRegion;
      currentRegion = mapModalTempRegion;
      mapChainFilter = mapModalTempChain;
      mapStatusFilter = 'all';
      mapTimeFilter = 'all';
      saveMapFiltersToStorage();
      if (regionChanged && REGIONS[mapRegionFilter]) {
        isFollowingUser = false;
        map.flyTo(REGIONS[mapRegionFilter].center, REGIONS[mapRegionFilter].zoom || 13, { duration: 1.0 });
      }
      const pinSelect = document.getElementById('set-stock-pin-hours');
      const stockHours = pinSelect ? pinSelect.value : (localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
      updateStockPinHours(stockHours);
      closeMapFilterModal();
      updateMapFilterUI();
      renderMapMarkers();
      if (regionChanged && typeof ensureStoresLoadedForRegion === 'function') {
        ensureStoresLoadedForRegion(mapRegionFilter);
      }
    }

    // 7. GACHI MEGURI (⚡)
    function triggerGachiMeguri() {
      setMapStatusFilter('in');
      setMapChainFilter('all');
      const inStockStores = Object.values(storesDict).filter(s => {
        const info = getStoreStatusInfo(s);
        return info.code === 'i';
      });
      if (inStockStores.length > 0) {
        let target = inStockStores[0];
        if (userLat !== null && userLng !== null) {
          inStockStores.sort((a,b) => calcDistanceKm(userLat, userLng, a.lat, a.lng) - calcDistanceKm(userLat, userLng, b.lat, b.lng));
          target = inStockStores[0];
        }
        isFollowingUser = false;
        updateGpsBtnState();
        map.flyTo([target.lat, target.lng], 16, { duration: 1.0 });
      } else {
        alert('現在、在庫あり店舗は見つかりませんでした。');
      }
    }

    // 8. GPS USER LOCATION & REAL-TIME TRACKING
    function updateUserMarker(lat, lng, accuracy = 25) {
      if (!userMarker) {
        const icon = L.divIcon({ className: 'user-location-marker', iconSize: [18, 18], iconAnchor: [9, 9] });
        userMarker = L.marker([lat, lng], { icon, zIndexOffset: 2000 }).addTo(map);
        userCircle = L.circle([lat, lng], { radius: Math.max(accuracy, 20), color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.15, weight: 1 }).addTo(map);
      } else {
        userMarker.setLatLng([lat, lng]);
        if (userCircle) {
          userCircle.setLatLng([lat, lng]);
          userCircle.setRadius(Math.max(accuracy, 20));
        }
      }
    }

    function updateGpsBtnState() {
      const btn = document.getElementById('gps-btn');
      if (btn) btn.classList.toggle('tracking', !!isFollowingUser);
    }

    function startGpsTracking(autoFly = true) {
      if (!navigator.geolocation) return;
      const btn = document.getElementById('gps-btn');
      if (btn) {
        btn.classList.add('locating');
        updateGpsBtnState();
      }

      // 1. Initial immediate location fix
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          try {
            localStorage.setItem('poketan_user_lat', String(userLat));
            localStorage.setItem('poketan_user_lng', String(userLng));
          } catch(e) {}
          updateUserMarker(userLat, userLng, pos.coords.accuracy || 25);
          if (btn) {
            btn.classList.remove('locating');
            updateGpsBtnState();
          }
          const urlParams = new URLSearchParams(window.location.search);
          if (autoFly && !urlParams.get('focus') && urlParams.get('hunt') !== '1') {
            map.flyTo([userLat, userLng], 15, { duration: 1.0 });
          }
        },
        (err) => {
          if (btn) {
            btn.classList.remove('locating');
            updateGpsBtnState();
          }
          console.warn('GPS initial fix warning:', err);
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );

      // 2. Real-time continuous tracking as device moves
      if (gpsWatchId !== null) {
        navigator.geolocation.clearWatch(gpsWatchId);
      }
      gpsWatchId = navigator.geolocation.watchPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          try {
            localStorage.setItem('poketan_user_lat', String(userLat));
            localStorage.setItem('poketan_user_lng', String(userLng));
          } catch(e) {}
          updateUserMarker(userLat, userLng, pos.coords.accuracy || 25);
          if (isFollowingUser) {
            map.panTo([userLat, userLng], { animate: true, duration: 0.5 });
          }
        },
        (err) => {
          console.warn('GPS watch error:', err);
        },
        { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 }
      );
    }

    function locateUser(userInitiated = true) {
      isFollowingUser = true;
      updateGpsBtnState();
      if (userLat !== null && userLng !== null) {
        map.flyTo([userLat, userLng], 15, { duration: 0.8 });
        updateUserMarker(userLat, userLng);
      }
      startGpsTracking(userInitiated);
    }

    // 9. AREA & REGION SELECTION
    function openPrefModal() { document.getElementById('pref-modal').classList.add('open'); }
    function closePrefModal() { document.getElementById('pref-modal').classList.remove('open'); }
    function selectCityArea(pref, cityName, lat, lng, zoom) {
      currentRegion = pref;
      mapRegionFilter = pref;
      isFollowingUser = false;
      updateGpsBtnState();
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      if (lat && lng) map.flyTo([lat, lng], zoom || 14, { duration: 1.0 });
      closePrefModal();
      renderMapMarkers();
      if (typeof ensureStoresLoadedForRegion === 'function') ensureStoresLoadedForRegion(pref);
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

    // 10. MODALS: TELEGRAM & SETTINGS, HISTORY, BULLETIN
    function onTelegramToggleChange(checked) {
      const slider = document.getElementById('tg-cfg-slider');
      if (slider) slider.style.background = checked ? '#0284c7' : '#cbd5e1';
    }

    function openTelegramModal() {
      openSettingsModal('telegram');
    }
    function closeTelegramModal() {
      closeSettingsModal();
    }

    function switchSettingsTab(tabName) {
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const isActive = (btn.dataset.tab === tabName || btn.id === `tab-btn-set-${tabName}`);
        btn.classList.toggle('active', isActive);
      });
      document.querySelectorAll('.settings-tab-pane').forEach(pane => {
        const isTarget = (pane.id === `settings-pane-${tabName}`);
        pane.classList.toggle('active', isTarget);
        pane.style.display = isTarget ? 'flex' : 'none';
      });
      if (tabName === 'map' && typeof syncMapFilterModalUI === 'function') {
        syncMapFilterModalUI();
      }
    }

    function openSettingsModal(initialTab = 'map') {
      const tokenEl = document.getElementById('tg-cfg-token');
      const chatIdEl = document.getElementById('tg-cfg-chatid');
      const enabledEl = document.getElementById('tg-cfg-enabled');
      const statusEl = document.getElementById('tg-cfg-status');
      const chainEl = document.getElementById('tg-cfg-chain');
      const timeEl = document.getElementById('tg-cfg-time');
      const regionEl = document.getElementById('tg-cfg-region');

      if (tokenEl) tokenEl.value = configData.telegramBotToken || '';
      if (chatIdEl) chatIdEl.value = configData.telegramChatId || '';
      if (enabledEl) {
        enabledEl.checked = !!configData.telegramEnabled;
        onTelegramToggleChange(!!configData.telegramEnabled);
      }
      if (statusEl) statusEl.value = configData.telegramStatus || 'in';
      if (chainEl) chainEl.value = configData.telegramChain || 'all';
      if (timeEl) timeEl.value = String(configData.telegramTime || '24');
      if (regionEl) regionEl.value = configData.telegramRegion || 'osaka';

      const rad = document.querySelector(`input[name="set-region-radio"][value="${currentRegion}"]`);
      if (rad) rad.checked = true;

      const soundCheck = document.getElementById('set-sound-check');
      if (soundCheck) {
        if (configData.notifications && typeof configData.notifications.soundEnabled !== 'undefined') {
          soundCheck.checked = !!configData.notifications.soundEnabled;
        } else if (typeof configData.soundEnabled !== 'undefined') {
          soundCheck.checked = !!configData.soundEnabled;
        } else {
          soundCheck.checked = true;
        }
      }

      const pinHoursSelect = document.getElementById('set-stock-pin-hours');
      if (pinHoursSelect) {
        const curHours = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
        pinHoursSelect.value = curHours;
      }

      mapModalTempRegion = mapRegionFilter || currentRegion;
      mapModalTempChain = mapChainFilter;

      switchSettingsTab(initialTab || 'map');
      document.getElementById('settings-modal').classList.add('open');
    }
    function closeSettingsModal() { document.getElementById('settings-modal').classList.remove('open'); }

    function updateStockPinHours(val) {
      configData.stockPinEffectHours = String(val);
      try { localStorage.setItem('poketan_stock_pin_hours', String(val)); } catch(e) {}
      if (typeof renderMapMarkers === 'function') {
        renderMapMarkers();
      }
    }

    function updateSettings(key, val) {
      if (!configData.notifications) configData.notifications = {};
      configData.notifications[key] = val;
      configData[key] = val;
      try { localStorage.setItem('poketan_config', JSON.stringify(configData)); } catch(e) {}
      try {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notifications: { [key]: val } })
        }).catch(() => {});
      } catch(e) {}
    }

    function selectRegion(pref) {
      currentRegion = pref;
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      mapRegionFilter = pref;
      if (typeof REGIONS !== 'undefined' && REGIONS[pref] && window.map) {
        map.flyTo(REGIONS[pref].center, REGIONS[pref].zoom || 13, { duration: 1.0 });
      }
      updateMapFilterUI();
      renderMapMarkers();
      closeSettingsModal();
      if (typeof ensureStoresLoadedForRegion === 'function') ensureStoresLoadedForRegion(pref);
    }

    function refreshData() {
      if (typeof initData === 'function') initData();
    }

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

    function openBulletinModal() { document.getElementById('bulletin-modal').classList.add('open'); }
    function closeBulletinModal() { document.getElementById('bulletin-modal').classList.remove('open'); }
    function openSearchModal() { openPrefModal(); }

    function switchHistTab(tab) {
      const btnList = document.getElementById('tab-btn-hist-list');
      const btnAnalytics = document.getElementById('tab-btn-hist-analytics');
      const bodyList = document.getElementById('hist-modal-body');
      const bodyAnalytics = document.getElementById('hist-modal-analytics');
      if (!btnList || !btnAnalytics || !bodyList || !bodyAnalytics) return;

      if (tab === 'analytics') {
        btnAnalytics.style.borderBottom = '2px solid #ef4444';
        btnAnalytics.style.color = '#ef4444';
        btnAnalytics.style.fontWeight = '700';
        btnList.style.borderBottom = '2px solid transparent';
        btnList.style.color = '#64748b';
        btnList.style.fontWeight = '600';
        bodyList.style.display = 'none';
        bodyAnalytics.style.display = 'block';
      } else {
        btnList.style.borderBottom = '2px solid #ef4444';
        btnList.style.color = '#ef4444';
        btnList.style.fontWeight = '700';
        btnAnalytics.style.borderBottom = '2px solid transparent';
        btnAnalytics.style.color = '#64748b';
        btnAnalytics.style.fontWeight = '600';
        bodyList.style.display = 'block';
        bodyAnalytics.style.display = 'none';
      }
    }

    const storeAnalyticsCache = {};

    function renderAnalyticsHtml(data) {
      if (!data || data.total_reports === 0) {
        return '<div style="text-align:center; padding:30px 15px; color:#64748b;">Chưa có dữ liệu thống kê báo cáo nào cho cửa hàng này.</div>';
      }

      const totalRep = data.total_reports || 0;
      const inRep = data.in_stock_reports || 0;
      const ratePct = data.in_stock_rate_pct || 0;
      const peakHours = data.peak_hours || [];
      const peakDays = data.peak_weekdays || [];
      const hourly = data.hourly_distribution || [];
      const weekday = data.weekday_distribution || [];
      const topPacks = data.top_packs || [];

      let maxHrCount = 1;
      hourly.forEach(h => { if (h.count > maxHrCount) maxHrCount = h.count; });

      const hourlyBarsHtml = hourly.map(h => {
        const heightPct = Math.round((h.count / maxHrCount) * 100);
        const isPeak = heightPct >= 70 && h.count > 0;
        const barColor = isPeak ? '#ef4444' : (h.count > 0 ? '#10b981' : '#e2e8f0');
        return `
          <div style="flex:1; display:flex; flex-direction:column; align-items:center; min-width:11px;" title="${h.hour}:00 JST - ${h.count} lần có hàng">
            <div style="font-size:0.55rem; color:${isPeak ? '#ef4444' : '#64748b'}; font-weight:700; height:12px;">${h.count > 0 ? h.count : ''}</div>
            <div style="width:100%; max-width:10px; height:60px; background:#f1f5f9; border-radius:3px; display:flex; align-items:flex-end; overflow:hidden;">
              <div style="width:100%; height:${heightPct}%; background:${barColor}; border-radius:2px; transition:height 0.3s;"></div>
            </div>
            <div style="font-size:0.55rem; color:#94a3b8; margin-top:3px;">${parseInt(h.hour)}</div>
          </div>
        `;
      }).join('');

      let maxWdCount = 1;
      weekday.forEach(w => { if (w.count > maxWdCount) maxWdCount = w.count; });

      const weekdayBarsHtml = weekday.map(w => {
        const widthPct = Math.round((w.count / maxWdCount) * 100);
        const isPeak = widthPct >= 75 && w.count > 0;
        const barColor = isPeak ? '#ef4444' : (w.count > 0 ? '#3b82f6' : '#cbd5e1');
        return `
          <div style="margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; font-weight:700; margin-bottom:2px;">
              <span style="color:${isPeak ? '#ef4444' : '#334155'};">${w.day}</span>
              <span style="color:#64748b;">${w.count} lần có hàng</span>
            </div>
            <div style="width:100%; height:8px; background:#f1f5f9; border-radius:4px; overflow:hidden;">
              <div style="width:${widthPct}%; height:100%; background:${barColor}; border-radius:4px; transition:width 0.3s;"></div>
            </div>
          </div>
        `;
      }).join('');

      const peakHoursHtml = peakHours.length > 0 
        ? peakHours.map(ph => `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-weight:700; font-size:0.72rem; padding:3px 8px; border-radius:6px; display:inline-flex; align-items:center; gap:3px;">🔥 ${ph}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa có đủ mẫu</span>';

      const peakDaysHtml = peakDays.length > 0
        ? peakDays.map(pd => `<span style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:700; font-size:0.72rem; padding:3px 8px; border-radius:6px; display:inline-flex; align-items:center; gap:3px;">📅 ${pd}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa có đủ mẫu</span>';

      const topPacksHtml = topPacks.length > 0
        ? topPacks.map(tp => `<span style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-weight:700; font-size:0.7rem; padding:2px 7px; border-radius:4px;">🎁 ${escapeHtml(tp)}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa ghi nhận mã pack</span>';

      return `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px; text-align:center;">
              <div style="font-size:0.68rem; color:#166534; font-weight:600; text-transform:uppercase;">Tỉ lệ có hàng</div>
              <div style="font-size:1.4rem; font-weight:900; color:#15803d; line-height:1.2; margin-top:2px;">${ratePct}%</div>
              <div style="font-size:0.68rem; color:#166534; font-weight:600; margin-top:2px;">${inRep} / ${totalRep} báo cáo</div>
            </div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; text-align:center;">
              <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">Có hàng gần nhất</div>
              <div style="font-size:0.85rem; font-weight:800; color:#1e293b; line-height:1.3; margin-top:6px;">${data.last_in_stock_time || 'Chưa có'}</div>
              <div style="font-size:0.65rem; color:#94a3b8; margin-top:2px;">(Giờ Nhật Bản JST)</div>
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:6px; display:flex; align-items:center; gap:5px;">
              <span>⚡</span> Khung giờ vàng hàng về (Peak Hours JST):
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${peakHoursHtml}
            </div>

            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-top:10px; margin-bottom:6px; display:flex; align-items:center; gap:5px;">
              <span>🗓️</span> Ngày trong tuần hay có hàng nhất:
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${peakDaysHtml}
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:0.75rem; font-weight:800; color:#1e293b;">🕒 Phân bố giờ có hàng (0h - 23h JST)</span>
              <span style="font-size:0.65rem; color:#64748b;">(Cột càng cao = Hàng về càng nhiều)</span>
            </div>
            <div style="display:flex; gap:2px; align-items:flex-end; height:75px; padding:0 2px; border-bottom:1px solid #e2e8f0;">
              ${hourlyBarsHtml}
            </div>
            <div style="text-align:center; font-size:0.62rem; color:#94a3b8; margin-top:4px;">0h = Nửa đêm • 12h = Trưa • 23h = Đêm (Giờ JST)</div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:8px;">
              📅 Phân bố ngày trong tuần (Thứ Hai → Chủ Nhật)
            </div>
            ${weekdayBarsHtml}
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:6px;">
              🎁 Các gói thẻ ghi nhận từng về tại quán:
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:5px;">
              ${topPacksHtml}
            </div>
          </div>
        </div>
      `;
    }

    async function openStoreHistoryModal(storeId) {
      const modal = document.getElementById('store-history-modal');
      const bodyEl = document.getElementById('hist-modal-body');
      const analyticsEl = document.getElementById('hist-modal-analytics');
      const nameEl = document.getElementById('hist-modal-store-name');

      switchHistTab('list');
      modal.classList.add('open');
      bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang tải lịch sử báo cáo...</div>';
      analyticsEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang phân tích quy luật hàng về...</div>';

      const stName = (typeof storesDict !== 'undefined' && storesDict[storeId]) ? storesDict[storeId].name : 'Cửa hàng';
      if (nameEl) nameEl.textContent = stName;

      // 1. Fetch History List
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }
        if (!history || history.length === 0) {
          bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">Chưa có lịch sử báo cáo nào.</div>';
        } else {
          // Synchronize storeCountsCache with distinct counts from history
          let countIn = 0, countOut = 0;
          const seenInTs = new Set(), seenOutTs = new Set();
          history.forEach(item => {
            const ts = item.timestamp || item.formatted_time;
            if (item.status_code === 'i') {
              if (!seenInTs.has(ts)) { seenInTs.add(ts); countIn++; }
            } else if (item.status_code === 'o') {
              if (!seenOutTs.has(ts)) { seenOutTs.add(ts); countOut++; }
            }
          });
          storeCountsCache[storeId] = { in: countIn, out: countOut };

          // Dynamically synchronize count tag in active map popup if currently open
          const openPopupBar = document.getElementById(`popup-counts-${storeId}`);
          if (openPopupBar) {
            openPopupBar.innerHTML = `
              <span class="report-count-tag tag-green">🟢 Có: <b>${countIn}</b> lần</span>
              <span class="report-count-tag tag-red">🔴 Hết: <b>${countOut}</b> lần</span>
            `;
          }

          // Propagate newest history record to local store object and refresh map marker
          if (typeof storesDict !== 'undefined' && storesDict[storeId]) {
            const newest = history[0];
            const st = storesDict[storeId];
            const histTs = Number(newest.timestamp) || 0;
            if (histTs >= (st.last_timestamp || 0) || st.status === 'u') {
              st.status = newest.status_code || newest.status || 'u';
              st.last_timestamp = histTs;
              st.last_reported_at = newest.formatted_time || '';
              st.onsite = !!newest.onsite;
              st.packs = newest.packs || [];
              if (typeof renderMapMarkers === 'function') {
                renderMapMarkers();
              }
            }
          }
          bodyEl.innerHTML = history.map(item => {
            let histColor = '#64748b', histText = '⚪ Chưa rõ';
            if (item.status_code === 'i') { histColor = '#15803d'; histText = '🟢 Có hàng'; }
            else if (item.status_code === 'o') { histColor = '#b91c1c'; histText = '🔴 Hết hàng'; }
            else if (item.status_code === 'n') { histColor = '#b45309'; histText = '🟡 Không bán thẻ'; }

            const packsHtml = (item.packs && item.packs.length > 0)
              ? `<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:6px;">
                  ${item.packs.map(p => `
                    <span style="display:inline-flex; align-items:center; gap:3px; background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-size:0.68rem; font-weight:700; padding:2px 7px; border-radius:4px;">
                      🎁 ${escapeHtml(p)}
                    </span>
                  `).join('')}
                </div>`
              : '';

            const onsiteHtml = item.onsite
              ? `<span style="display:inline-flex; align-items:center; gap:2px; background:#dcfce7; color:#15803d; border:1px solid #86efac; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:10px;">
                  📍 Tại quán (GPS)
                </span>`
              : '';

            const confirmsCount = Number(item.confirms) || 1;
            const confirmsHtml = (confirmsCount > 1)
              ? `<span style="display:inline-flex; align-items:center; gap:2px; background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:10px;">
                  👍 ${confirmsCount} xác nhận
                </span>`
              : '';

            return `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:10px 12px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
              <div style="display:flex; justify-content:space-between; align-items:center; font-weight:800; font-size:0.8rem;">
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                  <span style="color:${histColor}; font-weight:800;">${histText}</span>
                  ${onsiteHtml}
                  ${confirmsHtml}
                </div>
                <span style="color:#64748b; font-size:0.7rem; font-weight:500;">🕒 ${escapeHtml(item.formatted_time || '')}</span>
              </div>
              ${packsHtml}
              ${item.note ? `<div style="font-size:0.75rem; color:#1e293b; background:#f8fafc; border:1px solid #f1f5f9; border-radius:6px; padding:5px 8px; margin-top:6px;">💬 ${escapeHtml(item.note)}</div>` : ''}
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.68rem; color:#94a3b8; margin-top:6px;">
                <span>👤 Người báo: <b>${escapeHtml(item.user || 'Ẩn danh')}</b>${item.who ? ` <span style="font-size:0.62rem; color:#cbd5e1;">(#${escapeHtml(item.who)})</span>` : ''}</span>
                ${item.source ? `<span style="font-size:0.62rem; color:#94a3b8; text-transform:uppercase;">[${escapeHtml(item.source)}]</span>` : ''}
              </div>
            </div>
          `;
          }).join('');
        }
      } catch(e) {
        bodyEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi tải lịch sử.</div>';
      }

      // 2. Fetch Analytics
      try {
        let analytics = storeAnalyticsCache[storeId];
        if (!analytics) {
          const aRes = await fetch(`/api/analytics/store/${storeId}`);
          analytics = await aRes.json();
          storeAnalyticsCache[storeId] = analytics;
        }
        analyticsEl.innerHTML = renderAnalyticsHtml(analytics);
      } catch(e) {
        analyticsEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi phân tích quy luật.</div>';
      }
    }
    function closeStoreHistoryModal() { document.getElementById('store-history-modal').classList.remove('open'); }

    let audioCtx = null;
    function playAudioAlert() {
      try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
        osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.12); // A5
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);
        osc.start(audioCtx.currentTime);
        osc.stop(audioCtx.currentTime + 0.45);
      } catch(e) {}
    }
    document.addEventListener('click', () => {
      if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    }, { passive: true });


    function formatTimeAgoJp(timestamp) {
      if (!timestamp) return 'たった今';
      const diffSec = getServerNowSec() - timestamp;
      if (diffSec < 0) return 'たった今';
      if (diffSec <= 120) return 'たった今';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分前`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}時間前`;
      return `${Math.floor(diffSec / 86400)}日前`;
    }

    function showNewReportToast(rep) {
      const container = document.getElementById('live-report-toast-container');
      if (!container) return;

      // 1. Remove any existing toast for this exact store so the store never appears twice
      const existingSameStore = container.querySelector(`[data-store-id="${rep.store_id}"]`);
      if (existingSameStore) {
        existingSameStore.remove();
      }

      const st = storesDict[rep.store_id];
      const name = st ? st.name : (rep.store_name || '店舗');
      const isStock = rep.status_code === 'i';
      const isOut = rep.status_code === 'o';

      const dotClass = isStock ? 'dot-in' : (isOut ? 'dot-out' : 'dot-not');
      const statusClass = isStock ? 'status-in' : (isOut ? 'status-out' : 'status-not');
      const statusLabel = isStock ? '在庫あり' : (isOut ? '在庫なし' : '扱ってない');
      const repTs = Number(rep.timestamp) || 0;
      const repAgeSec = repTs > 0 ? (getServerNowSec() - repTs) : 0;
      const timeAgo = (repTs > 0 && repAgeSec >= 0 && repAgeSec <= 120) ? 'たった今' : (repTs > 0 ? formatTimeAgoJp(repTs) : 'たった今');

      const toast = document.createElement('div');
      toast.className = `poketan-pill-toast ${isStock ? 'stock-pill' : ''}`;
      toast.dataset.storeId = rep.store_id;
      toast.dataset.ts = repTs;
      toast.onclick = () => focusStoreOnMap(rep.store_id);
      toast.innerHTML = `
        <span class="pill-dot ${dotClass}"></span>
        <span class="pill-store-name">${escapeHtml(name)}</span>
        <span class="pill-text">で</span>
        <span class="pill-status ${statusClass}">${statusLabel}</span>
        <span class="pill-text">の報告</span>
        <span class="pill-time" data-timestamp="${repTs}">${escapeHtml(timeAgo)}</span>
        <button type="button" class="pill-close-btn" onclick="event.stopPropagation(); this.closest('.poketan-pill-toast').remove();" title="閉じる">✕</button>
      `;

      // 2. Insert in strict chronological order: NEWEST (highest timestamp) at TOP, older below
      const existingToasts = Array.from(container.children);
      let inserted = false;
      for (const existing of existingToasts) {
        const existingTs = Number(existing.dataset.ts) || 0;
        if (repTs >= existingTs) {
          container.insertBefore(toast, existing);
          inserted = true;
          break;
        }
      }
      if (!inserted) {
        container.appendChild(toast);
      }

      // 3. Keep at most 3 visible toasts to keep screen clean and avoid covering UI
      while (container.children.length > 3) {
        container.lastElementChild.remove();
      }

      // 4. Auto-dismiss after 6 seconds
      setTimeout(() => {
        if (toast.parentElement) {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(-10px) scale(0.96)';
          setTimeout(() => toast.remove(), 250);
        }
      }, 6000);
    }

    function checkStockPinEffectTransitions() {
      const stockEffectSetting = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
      if (stockEffectSetting === 'all' || stockEffectSetting === '0' || stockEffectSetting === 'off') return;
      const effectMaxSec = (parseInt(stockEffectSetting, 10) || 24) * 3600;
      const now = getServerNowSec();

      let needsRerender = false;
      document.querySelectorAll('.poketan-stock-pin-v2 .stock-time-badge[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0 && (now - ts) > effectMaxSec) {
          needsRerender = true;
        }
      });

      if (needsRerender && typeof renderMapMarkers === 'function') {
        renderMapMarkers();
      }
    }

    function updateLiveRelativeTimes() {
      // 1. Update In-Stock Pin badges on Leaflet markers
      document.querySelectorAll('.stock-time-badge[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0) {
          const newStr = formatTimeAgoJp(ts);
          if (el.textContent !== newStr) {
            el.textContent = newStr;
          }
        }
      });

      // 2. Update popup relative time if popup is open
      document.querySelectorAll('.popup-time-ago[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0) {
          const newStr = formatTimeAgoJp(ts);
          if (el.textContent !== newStr) {
            el.textContent = newStr;
          }
        }
      });

      // 3. Update pill toasts (if any)
      document.querySelectorAll('.pill-time[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0) {
          const newStr = formatTimeAgoJp(ts);
          if (el.textContent !== newStr) {
            el.textContent = newStr;
          }
        }
      });

      // 4. Check if any In-Stock Pin has aged beyond stockPinEffectHours
      checkStockPinEffectTransitions();
    }

    window.focusStoreOnMap = function(sid) {
      const s = storesDict[sid];
      if (!s || !s.lat || !s.lng) return;
      map.flyTo([s.lat, s.lng], 16, { duration: 0.8 });
      setTimeout(() => {
        stockLayer.eachLayer(m => {
          const ll = m.getLatLng();
          if (Math.abs(ll.lat - s.lat) < 0.0001 && Math.abs(ll.lng - s.lng) < 0.0001) m.openPopup();
        });
      }, 850);
    };

    const seenToastKeys = new Set();
    let lastDbPollTs = 0;

    async function pollDatabaseUpdates() {
      if (!lastDbPollTs) return;
      try {
        const res = await fetch(`/api/latest_reports?since=${lastDbPollTs}&limit=50`);
        if (!res.ok) return;
        const reports = await res.json();
        if (Array.isArray(reports) && reports.length > 0) {
          let hasNewStock = false;
          let shouldReRender = false;
          const nowSec = getServerNowSec();
          const candidateStockReps = [];

          for (const rep of reports) {
            // Strictly advance polling timestamp using SQLite created_at
            if (rep.created_at && rep.created_at > lastDbPollTs) {
              lastDbPollTs = rep.created_at;
            }

            const sid = rep.store_id;
            let st = storesDict[sid];
            if (!st && rep.lat && rep.lng) {
              storesDict[sid] = {
                id: sid,
                name: rep.store_name,
                chain: rep.chain,
                lat: rep.lat,
                lng: rep.lng,
                address: rep.address,
                pref: rep.pref,
                status: rep.status_code,
                last_timestamp: rep.timestamp,
                onsite: !!rep.onsite,
                packs: rep.packs || [],
                last_reported_at: rep.reported_at || rep.formatted_time || ''
              };
              st = storesDict[sid];
              shouldReRender = true;
            } else if (st) {
              if (!st.last_timestamp || (rep.timestamp && rep.timestamp >= st.last_timestamp)) {
                st.status = rep.status_code;
                st.last_timestamp = rep.timestamp;
                st.onsite = !!rep.onsite;
                st.packs = rep.packs || [];
                st.last_reported_at = rep.reported_at || rep.formatted_time || '';
                shouldReRender = true;
              }
            }

            // Real-time toast check:
            // 1. Must be in-stock (i)
            // 2. Deduplicate strictly by composite key (store_id, timestamp, status_code)
            // 3. Must be genuinely real-time: reported within the last 120 seconds (2 minutes)
            const toastKey = `${rep.store_id}_${rep.timestamp}_${rep.status_code}`;
            const reportAgeSec = rep.timestamp > 0 ? (nowSec - rep.timestamp) : 0;
            const isFreshRealtime = reportAgeSec >= 0 && reportAgeSec <= 120;

            if (rep.status_code === 'i' && !seenToastKeys.has(toastKey) && isFreshRealtime) {
              seenToastKeys.add(toastKey);
              candidateStockReps.push(rep);
            }
          }

          // Sort candidate stock reports strictly by timestamp DESC (newest first)
          if (candidateStockReps.length > 0) {
            candidateStockReps.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
            // Show at most 3 fresh toasts to avoid flooding screen
            for (const rep of candidateStockReps.slice(0, 3)) {
              hasNewStock = true;
              showNewReportToast(rep);
            }
          }

          if (hasNewStock && configData.soundEnabled) {
            playAudioAlert();
          }
          if (shouldReRender) {
            renderMapMarkers();
          }
        }
      } catch (e) {
        console.warn('DB Poll error:', e);
      }
    }

    // 11. INIT DATA & URL QUERY PARAMS
    async function initData() {
      try {
        const reqRegion = currentRegion || 'osaka';
        const [cfgRes, storesRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data?region=' + encodeURIComponent(reqRegion))
        ]);
        configData = await cfgRes.json();
        storesDict = await storesRes.json();
        loadedRegions.add(reqRegion);

        // Fetch report counts asynchronously in background (does not block initial map render)
        fetch('/api/report_counts?region=' + encodeURIComponent(reqRegion))
          .then(r => r.ok ? r.json() : null)
          .then(countsData => {
            if (countsData) Object.assign(storeCountsCache, countsData);
          })
          .catch(() => {});

        // Calibrate server time offset to correct browser clock drift
        if (configData.serverTime) {
          serverTimeOffset = configData.serverTime - Math.floor(Date.now() / 1000);
        }

        // Pre-fill seenToastKeys with all stores currently in stock so page load NEVER triggers old toast alerts!
        for (const sid in storesDict) {
          const s = storesDict[sid];
          if (s && s.status === 'i' && s.last_timestamp) {
            seenToastKeys.add(`${sid}_${s.last_timestamp}_i`);
          }
        }

        updateMapFilterUI();
        renderMapMarkers();
        if (typeof syncMapFilterModalUI === 'function') {
          syncMapFilterModalUI();
        }

        // Initialize DB poll timestamp to current time so only future/real-time reports trigger alerts
        lastDbPollTs = getServerNowSec();
        if (!window._dbPollInterval) {
          window._dbPollInterval = setInterval(pollDatabaseUpdates, 5000);
        }
        if (!window._liveTimeInterval) {
          window._liveTimeInterval = setInterval(updateLiveRelativeTimes, 15000);
        }

        // Check URL Query String: ?focus=store_id or ?store_id=... or ?hunt=1
        const urlParams = new URLSearchParams(window.location.search);
        const focusId = urlParams.get('focus') || urlParams.get('store_id');
        const isHunt = urlParams.get('hunt');
        const targetLat = parseFloat(urlParams.get('lat'));
        const targetLng = parseFloat(urlParams.get('lng'));

        if (focusId && storesDict[focusId]) {
          isFollowingUser = false;
          updateGpsBtnState();
          const s = storesDict[focusId];
          const flyLat = (!isNaN(targetLat) && targetLat) ? targetLat : s.lat;
          const flyLng = (!isNaN(targetLng) && targetLng) ? targetLng : s.lng;
          map.flyTo([flyLat, flyLng], 17, { duration: 0.8 });
          setTimeout(() => {
            let opened = false;
            stockLayer.eachLayer(m => {
              const ll = m.getLatLng();
              if (Math.abs(ll.lat - s.lat) < 0.0002 && Math.abs(ll.lng - s.lng) < 0.0002) {
                m.openPopup();
                opened = true;
              }
            });
            if (!opened && circleLayer) {
              circleLayer.eachLayer(m => {
                const ll = m.getLatLng();
                if (Math.abs(ll.lat - s.lat) < 0.0002 && Math.abs(ll.lng - s.lng) < 0.0002) {
                  m.openPopup();
                }
              });
            }
          }, 850);
        } else if (isHunt === '1') {
          isFollowingUser = false;
          updateGpsBtnState();
          triggerGachiMeguri();
        }
      } catch(e) {
        console.error('Init error:', e);
      } finally {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.opacity = '0';
        setTimeout(() => overlay && overlay.remove(), 150);
        map.invalidateSize();
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      initData();
      if (userLat !== null && userLng !== null) {
        updateUserMarker(userLat, userLng, 25);
      }
      const urlParams = new URLSearchParams(window.location.search);
      const shouldAutoFly = !urlParams.get('focus') && !urlParams.get('store_id') && urlParams.get('hunt') !== '1';
      startGpsTracking(shouldAutoFly);
    });
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

    /* REPORT TIME PILL */
    .card-time-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: #f0f7ff;
      color: #1e3a8a;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid #bfdbfe;
      margin-top: 3px;
    }
    .card-time-pill b {
      color: #1d4ed8;
      font-weight: 800;
    }
    .card-time-pill .time-ago-highlight {
      color: #1e40af;
      font-weight: 800;
      background: #dbeafe;
      padding: 1px 6px;
      border-radius: 4px;
    }

    /* PAGINATION STYLES */
    .pagination-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      padding: 18px 12px 28px 12px;
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      margin-top: 8px;
      border-radius: 12px;
    }
    .pagination-info {
      font-size: 0.75rem;
      color: #475569;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .pagination-buttons {
      display: flex;
      align-items: center;
      gap: 5px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .page-btn {
      min-width: 36px;
      height: 36px;
      padding: 0 10px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
      user-select: none;
    }
    .page-btn:hover:not(:disabled) {
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
    }
    .page-btn.active {
      background: #2563eb;
      border-color: #2563eb;
      color: #ffffff;
      font-weight: 800;
      box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
    }
    .page-btn:disabled {
      opacity: 0.35;
      cursor: not-allowed;
      background: #f8fafc;
      border-color: #e2e8f0;
    }
    .page-size-select {
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid #cbd5e1;
      font-size: 0.72rem;
      font-weight: 800;
      color: #1e293b;
      background: #ffffff;
      outline: none;
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
              <span class="chip-dot dot-green"></span> 🟢 Có hàng (あった)
            </button>
            <button class="filter-option-btn" data-val="out" onclick="selectModalStatus('out')">
              <span class="chip-dot dot-red"></span> 🔴 Không có (なかった)
            </button>
            <button class="filter-option-btn" data-val="n" onclick="selectModalStatus('n')">
              <span class="chip-dot" style="background:#f59e0b;"></span> 🟡 Không bán thẻ (扱ってない)
            </button>
            <button class="filter-option-btn" data-val="unknown" onclick="selectModalStatus('unknown')">
              <span class="chip-dot dot-gray"></span> ⚪ Chưa có báo cáo (未確認)
            </button>
            <button class="filter-option-btn" data-val="onsite" onclick="selectModalStatus('onsite')">
              📍 Báo cáo tại quán (GPS)
            </button>
            <button class="filter-option-btn" data-val="recent" onclick="selectModalStatus('recent')">
              ⚡ Có tin báo gần đây (7 ngày)
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

  <!-- Real-time Live Toast Container for Database updates -->
  <div id="live-report-toast-container" style="position:fixed; top:68px; left:50%; transform:translateX(-50%); z-index:9999; display:flex; flex-direction:column; align-items:center; gap:6px; pointer-events:none; width:max-content; max-width:calc(100vw - 20px);"></div>

  <!-- Search row -->
    <div class="list-search-row">
      <div class="list-search-box">
        <span class="icon">🔍</span>
        <input type="text" id="list-search-input" placeholder="Tìm tên quán, địa chỉ..." oninput="onListSearch(this.value)" />
      </div>
      <button onclick="openFilterModal()" class="list-sort-btn" style="background:#0f172a; color:#ffffff; padding:7px 11px; border-radius:8px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;">
        <span>⚙️ Lọc</span>
        <span id="list-filter-active-badge-2" class="filter-count-pill" style="display:none;">0</span>
      </button>
      <button id="list-filter-clear-btn" onclick="resetAllFiltersAndApply()" style="display:none; color:#ef4444; border:1px solid #fca5a5; background:#ffffff; font-size:0.75rem; font-weight:700; border-radius:8px; padding:6px 10px; cursor:pointer;">
        ✕ Xóa lọc
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
      'tokyo': { id: 'tokyo', name: '東京・神奈川', center: [35.6895, 139.6917], zoom: 13, defaultCity: '横浜', prefs: ['tokyo', 'kanagawa'] },
      'nagoya': { id: 'nagoya', name: '名古屋・東海', center: [35.1815, 136.9066], zoom: 13, defaultCity: '名古屋駅', prefs: ['aichi', 'gifu', 'mie'] },
      'all': { id: 'all', name: '全エリア (全国)', center: [34.6937, 135.5023], zoom: 10, defaultCity: '全エリア', prefs: ['osaka', 'tokyo', 'kanagawa', 'aichi', 'gifu', 'mie'] }
    };

    const urlRegion = new URLSearchParams(window.location.search).get('region');
    let currentRegion = (urlRegion && REGIONS[urlRegion]) ? urlRegion : (localStorage.getItem('poketan_selected_region') || 'osaka');
    if (!REGIONS[currentRegion]) currentRegion = 'osaka';
    if (urlRegion && REGIONS[urlRegion]) {
      try {
        localStorage.setItem('poketan_selected_region', currentRegion);
        localStorage.setItem('poketan_map_region', currentRegion);
      } catch(e) {}
    }
    let currentPref = REGIONS[currentRegion].prefs[0] || 'osaka';

    let storesDict = {};
    let configData = {};
    const storeHistoryCache = {};
    const storeCountsCache = {};
    let serverTimeOffset = 0; // seconds: serverNow - browserNow

    function getServerNowSec() {
      return Math.floor(Date.now() / 1000) + serverTimeOffset;
    }

    let listRegionFilter = currentRegion;
    let listStatusFilter = 'all';
    try {
      localStorage.removeItem('poketan_list_status'); // Clear legacy lock
      const savedSt = localStorage.getItem('poketan_list_status_v3');
      if (savedSt) listStatusFilter = savedSt;
    } catch(e) {}
    let listChainFilter = localStorage.getItem('poketan_list_chain') || 'all';
    let listTimeFilter = localStorage.getItem('poketan_list_time') || 'all';
    let listRadiusFilter = localStorage.getItem('poketan_list_radius') || 'all';
    let listSortMode = localStorage.getItem('poketan_list_sort') || 'newest';
    let listCurrentPage = 1;
    let listPageSize = 20;

    function saveListFiltersToStorage() {
      try {
        localStorage.setItem('poketan_list_status_v3', listStatusFilter);
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
    function formatTimeAgoVi(timestamp) {
      if (!timestamp) return 'Vừa xong';
      const diffSec = Math.max(0, getServerNowSec() - Number(timestamp));
      if (diffSec < 60) return 'Vừa xong';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`;
      return `${Math.floor(diffSec / 86400)} ngày trước`;
    }

    function getStoreStatusInfo(store) {
      let code = (store.status || 'u').toLowerCase();
      let timestamp = Number(store.last_timestamp) || 0;
      let onsite = !!store.onsite;
      let packs = Array.isArray(store.packs) ? store.packs : [];
      let reported_at = store.last_reported_at || '';

      let dtStr = '', timeAgo = '', timeOnly = '', dateOnly = '';
      if (timestamp > 0) {
        const jst = new Date((timestamp + 9 * 3600) * 1000);
        const hours = String(jst.getUTCHours()).padStart(2, '0');
        const minutes = String(jst.getUTCMinutes()).padStart(2, '0');
        const seconds = String(jst.getUTCSeconds()).padStart(2, '0');
        const day = String(jst.getUTCDate()).padStart(2, '0');
        const month = String(jst.getUTCMonth() + 1).padStart(2, '0');
        timeOnly = `${hours}:${minutes}:${seconds}`;
        dateOnly = `${day}/${month}`;
        if (!reported_at) reported_at = `${hours}:${minutes} (${day}/${month})`;

        timeAgo = formatTimeAgoVi(timestamp);
      }
      const labelMap = { 'i': 'Có hàng', 'o': 'Không có', 'n': 'Không bán thẻ', 'u': 'Chưa có tin' };
      return {
        code,
        label: labelMap[code] || 'Chưa có tin',
        packs,
        reported_at: reported_at || dtStr,
        timeOnly,
        dateOnly,
        timeAgo,
        onsite,
        timestamp
      };
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
      const c = (chain || '').toLowerCase().trim();
      if (filter === 'conbini') return ['seven', 'lawson', 'familymart', 'ministop'].includes(c);
      if (filter === 'seven') return c === 'seven';
      if (filter === 'lawson') return c === 'lawson';
      if (filter === 'familymart') return c === 'familymart';
      if (filter === 'ministop') return c === 'ministop';
      if (filter === 'specialty') return c === 'specialty';
      if (filter === 'electronics') return ['geo', 'joshin', 'edion', 'aeon', 'yamada', 'ks', 'toysrus', 'biccamera', 'yodobashi'].includes(c);
      return c === filter;
    }

    // 3. RENDER STORE LIST CARDS
    function renderStoreList(query = '') {
      const listContainer = document.getElementById('store-cards-list');
      if (!listContainer) return;

      const allStores = Object.values(storesDict);
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

      const maxSec = (listTimeFilter !== 'all') ? parseInt(listTimeFilter, 10) * 3600 : null;

      for (const store of allStores) {
        if (targetRegion !== 'all') {
          const storePref = (store.pref || '').toLowerCase();
          if (!allowedPrefs.includes(storePref)) continue;
        }

        const info = getStoreStatusInfo(store);

        // Check time filter if specified (e.g. 1h, 3h, 6h, 24h)
        if (maxSec !== null) {
          if (!info.timestamp || (now - info.timestamp > maxSec)) continue;
        }

        // Status filter
        if (listStatusFilter === 'in') {
          if (info.code !== 'i') continue;
        } else if (listStatusFilter === 'onsite') {
          if (!info.onsite || info.code !== 'i') continue;
        } else if (listStatusFilter === 'out') {
          if (info.code !== 'o') continue;
        } else if (listStatusFilter === 'n') {
          if (info.code !== 'n') continue;
        } else if (listStatusFilter === 'recent') {
          const isRecentReport = info.timestamp > 0 && (now - info.timestamp <= 86400 * 7);
          if (!isRecentReport) continue;
        } else if (listStatusFilter === 'unknown') {
          if (info.code !== 'u' && info.timestamp > 0) continue;
        }

        // Chain
        if (!matchesChainFilter(store.chain, listChainFilter)) continue;

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

      // Sort
      matched.sort((a,b) => {
        if (listSortMode === 'nearest') {
          if (a.dist !== null && b.dist !== null) {
            const dDiff = a.dist - b.dist;
            if (Math.abs(dDiff) > 0.05) return dDiff;
          }
          if (a.dist !== null && b.dist === null) return -1;
          if (b.dist !== null && a.dist === null) return 1;
          return (b.info.timestamp || 0) - (a.info.timestamp || 0);
        } else {
          // Newest first (Báo cáo mới nhất trước)
          const tsA = a.info.timestamp || 0;
          const tsB = b.info.timestamp || 0;
          if (tsA > 0 && tsB > 0) return tsB - tsA;
          if (tsA > 0) return -1;
          if (tsB > 0) return 1;
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

      const totalItems = matched.length;
      const totalPages = Math.max(1, Math.ceil(totalItems / listPageSize));
      if (listCurrentPage > totalPages) listCurrentPage = totalPages;
      if (listCurrentPage < 1) listCurrentPage = 1;

      const startIndex = (listCurrentPage - 1) * listPageSize;
      const endIndex = Math.min(startIndex + listPageSize, totalItems);
      const pageSlice = matched.slice(startIndex, endIndex);

      // Update count badge in sort bar
      const countBadge = document.getElementById('list-count-badge');
      if (countBadge) {
        countBadge.innerText = totalItems > 0
          ? `Trang ${listCurrentPage}/${totalPages} (${totalItems.toLocaleString()} quán)`
          : '0 quán';
      }

      const cardsHtml = pageSlice.map((item, idx) => {
        const { store, info, dist } = item;
        let badgeClass = 'badge-none', badgeText = '🔘 Chưa có tin';
        if (info.code === 'i') { badgeClass = 'badge-in'; badgeText = '🟢 Có hàng'; }
        else if (info.code === 'o') { badgeClass = 'badge-out'; badgeText = '🔴 Không có'; }
        else if (info.code === 'n') { badgeClass = 'badge-not'; badgeText = '🟡 Không bán thẻ'; }

        const onsiteBadge = (info.onsite && info.code === 'i')
          ? `<span class="card-badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; padding:2px 6px; font-size:0.68rem;">📸 Tại chỗ</span>`
          : '';

        let counts = storeCountsCache[store.id];
        if (!counts && storeHistoryCache[store.id]) {
          let cIn = 0, cOut = 0;
          const sIn = new Set(), sOut = new Set();
          storeHistoryCache[store.id].forEach(item => {
            const ts = item.timestamp || item.formatted_time;
            if (item.status_code === 'i') { if (!sIn.has(ts)) { sIn.add(ts); cIn++; } }
            else if (item.status_code === 'o') { if (!sOut.has(ts)) { sOut.add(ts); cOut++; } }
          });
          counts = { in: cIn, out: cOut };
          storeCountsCache[store.id] = counts;
        }
        if (!counts) {
          counts = { in: info.code === 'i' ? 1 : 0, out: info.code === 'o' ? 1 : 0 };
        }
        const chain = (configData.chainNames && configData.chainNames[store.chain]) || store.chain || 'Cửa hàng';
        const distStr = dist !== null ? ` • 📍 Cách ${formatDist(dist)}` : '';
        
        let timeReportHtml = '';
        if (info.timestamp > 0) {
          timeReportHtml = `
            <div style="margin:4px 0 2px 0;">
              <span class="card-time-pill" title="Thời gian người dùng gửi báo cáo">
                <span>🕒 Báo lúc:</span>
                <b>${escapeHtml(info.timeOnly || info.reported_at)}</b>
                ${info.dateOnly ? `<span style="color:#64748b; font-size:0.68rem;">(${escapeHtml(info.dateOnly)})</span>` : ''}
                <span>•</span>
                <span class="time-ago-highlight" data-timestamp="${info.timestamp || 0}">${escapeHtml(info.timeAgo)}</span>
              </span>
            </div>
          `;
        }

        const packHtml = info.packs.length ? `<div style="font-size:0.72rem; color:#2563eb; font-weight:700; margin-top:3px;">📦 ${escapeHtml(info.packs.join(', '))}</div>` : '';

        let countsHtml = '';
        if (counts.in > 0 || counts.out > 0) {
          countsHtml = `
            <div class="popup-report-counts-bar" style="margin:4px 0 2px 0;">
              <span class="report-count-tag tag-green" style="font-size:0.67rem; padding:1px 6px;">🟢 Có: <b>${counts.in}</b> lần</span>
              <span class="report-count-tag tag-red" style="font-size:0.67rem; padding:1px 6px;">🔴 Hết: <b>${counts.out}</b> lần</span>
            </div>
          `;
        }

        const itemNum = startIndex + idx + 1;

        return `
          <div class="store-list-card">
            <div class="card-left-info">
              <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span style="font-size:0.68rem; color:#94a3b8; font-weight:700;">#${itemNum}</span>
                <span class="card-badge ${badgeClass}">${badgeText}</span>
                ${onsiteBadge}
                <div class="card-store-name">${escapeHtml(store.name || '')}</div>
              </div>
              <div class="card-chain-time">${escapeHtml(chain)}${distStr}</div>
              ${timeReportHtml}
              ${countsHtml}
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

      const paginationHtml = renderPaginationHtml(totalItems, listCurrentPage, listPageSize);

      listContainer.innerHTML = cardsHtml + paginationHtml;
    }

    function renderPaginationHtml(totalItems, currentPage, pageSize) {
      if (totalItems <= 0) return '';
      const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
      const startItem = (currentPage - 1) * pageSize + 1;
      const endItem = Math.min(currentPage * pageSize, totalItems);

      let buttonsHtml = '';

      buttonsHtml += `
        <button type="button" class="page-btn" onclick="setListPage(1)" ${currentPage === 1 ? 'disabled' : ''} title="Trang đầu">⏮</button>
        <button type="button" class="page-btn" onclick="setListPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''} title="Trang trước">◀</button>
      `;

      let pageNumbers = [];
      if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) pageNumbers.push(i);
      } else {
        if (currentPage <= 4) {
          pageNumbers = [1, 2, 3, 4, 5, '...', totalPages];
        } else if (currentPage >= totalPages - 3) {
          pageNumbers = [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        } else {
          pageNumbers = [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages];
        }
      }

      for (const p of pageNumbers) {
        if (p === '...') {
          buttonsHtml += `<span style="padding:0 4px; color:#94a3b8; font-weight:700;">...</span>`;
        } else {
          const isActive = p === currentPage ? 'active' : '';
          buttonsHtml += `<button type="button" class="page-btn ${isActive}" onclick="setListPage(${p})">${p}</button>`;
        }
      }

      buttonsHtml += `
        <button type="button" class="page-btn" onclick="setListPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''} title="Trang sau">▶</button>
        <button type="button" class="page-btn" onclick="setListPage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''} title="Trang cuối">⏭</button>
      `;

      return `
        <div class="pagination-container">
          <div class="pagination-info">
            <span>Hiển thị <b>${startItem.toLocaleString()} - ${endItem.toLocaleString()}</b> / <b>${totalItems.toLocaleString()}</b> quán</span>
            <span>•</span>
            <span>Trang <b>${currentPage}</b> / <b>${totalPages}</b></span>
            <span>•</span>
            <label style="display:inline-flex; align-items:center; gap:4px; font-size:0.72rem;">
              <span>Mỗi trang:</span>
              <select class="page-size-select" onchange="setListPageSize(this.value)">
                <option value="20" ${pageSize === 20 ? 'selected' : ''}>20 quán</option>
                <option value="50" ${pageSize === 50 ? 'selected' : ''}>50 quán</option>
                <option value="100" ${pageSize === 100 ? 'selected' : ''}>100 quán</option>
              </select>
            </label>
          </div>
          <div class="pagination-buttons">
            ${buttonsHtml}
          </div>
        </div>
      `;
    }

    function setListPage(page) {
      listCurrentPage = Math.max(1, parseInt(page, 10) || 1);
      renderStoreList(document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '');
      const scrollEl = document.getElementById('store-cards-list');
      if (scrollEl) scrollEl.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function setListPageSize(size) {
      listPageSize = parseInt(size, 10) || 20;
      listCurrentPage = 1;
      renderStoreList(document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '');
      const scrollEl = document.getElementById('store-cards-list');
      if (scrollEl) scrollEl.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // 4. FILTER CONTROLS & HANDLERS
    function setListStatusTab(tab) {
      listStatusFilter = tab;
      listCurrentPage = 1;
      saveListFiltersToStorage();
      document.querySelectorAll('.list-tab-chip').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`list-tab-${tab}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function setListRadiusFilter(val) {
      listRadiusFilter = String(val);
      listCurrentPage = 1;
      saveListFiltersToStorage();
      document.querySelectorAll('.list-radius-chip').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`list-radius-chip-${val}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function setListSortMode(mode) {
      listSortMode = mode;
      listCurrentPage = 1;
      saveListFiltersToStorage();
      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`sort-btn-${mode}`);
      if (activeBtn) activeBtn.classList.add('active');
      renderStoreList(document.getElementById('list-search-input').value);
    }

    function onListSearch(val) {
      listCurrentPage = 1;
      renderStoreList(val);
    }

    // Dynamic Region Store Loader
    const loadedRegions = new Set();
    async function ensureStoresLoadedForRegion(reg) {
      if (!reg) return;
      if (loadedRegions.has(reg)) return;
      if (reg === 'all' && loadedRegions.has('all')) return;
      try {
        const res = await fetch('/api/stores_data?region=' + encodeURIComponent(reg));
        if (res.ok) {
          const newStores = await res.json();
          Object.assign(storesDict, newStores);
          loadedRegions.add(reg);
          for (const sid in newStores) {
            const s = newStores[sid];
            if (s && s.status === 'i' && s.last_timestamp) {
              seenToastKeys.add(`${sid}_${s.last_timestamp}_i`);
            }
          }
          fetch('/api/report_counts?region=' + encodeURIComponent(reg))
            .then(r => r.ok ? r.json() : null)
            .then(c => {
              if (c) {
                if (typeof reportCounts !== 'undefined') Object.assign(reportCounts, c);
                if (typeof storeCountsCache !== 'undefined') Object.assign(storeCountsCache, c);
              }
            })
            .catch(() => {});
          const searchVal = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
          renderStoreList(searchVal);
        }
      } catch (e) {
        console.warn('Error loading stores for region:', reg, e);
      }
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
    function resetAllFiltersAndApply() {
      resetAllFilters();
      applyAndCloseFilterModal();
    }
    function updateListFilterBadgeUI() {
      let count = 0;
      if (listStatusFilter !== 'all') count++;
      if (listChainFilter !== 'all') count++;
      if (listTimeFilter !== 'all') count++;
      if (listRadiusFilter !== 'all') count++;
      if (listRegionFilter !== currentRegion) count++;

      ['list-filter-active-badge', 'list-filter-active-badge-2'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.innerText = count; el.style.display = count > 0 ? 'inline-flex' : 'none'; }
      });
      const clearBtn = document.getElementById('list-filter-clear-btn');
      if (clearBtn) clearBtn.style.display = count > 0 ? 'inline-flex' : 'none';
    }
    function applyAndCloseFilterModal() {
      listRegionFilter = modalTempRegion;
      listStatusFilter = modalTempFilter;
      listChainFilter = modalTempChain;
      listTimeFilter = modalTempTime;
      listRadiusFilter = modalTempRadius;
      listSortMode = modalTempSort;
      saveListFiltersToStorage();

      document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.toggle('active', b.id === `sort-btn-${listSortMode}`));
      updateListFilterBadgeUI();

      closeFilterModal();
      listCurrentPage = 1;
      const searchVal = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(searchVal);
      if (typeof ensureStoresLoadedForRegion === 'function') ensureStoresLoadedForRegion(listRegionFilter);
    }

    // 5. AREA & MODALS
    function openPrefModal() { document.getElementById('pref-modal').classList.add('open'); }
    function closePrefModal() { document.getElementById('pref-modal').classList.remove('open'); }
    function selectCityArea(pref, cityName, lat, lng, zoom) {
      currentRegion = pref;
      listRegionFilter = pref;
      listCurrentPage = 1;
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      closePrefModal();
      renderStoreList();
      if (typeof ensureStoresLoadedForRegion === 'function') ensureStoresLoadedForRegion(pref);
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

    function onTelegramToggleChange(checked) {
      const slider = document.getElementById('tg-cfg-slider');
      if (slider) slider.style.background = checked ? '#0284c7' : '#cbd5e1';
    }

    function openTelegramModal() {
      openSettingsModal('telegram');
    }
    function closeTelegramModal() {
      closeSettingsModal();
    }

    // Settings Modal Tab Switcher & Map Filter Handlers for /thongbao
    function switchSettingsTab(tabName) {
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const isActive = (btn.dataset.tab === tabName || btn.id === `tab-btn-set-${tabName}`);
        btn.classList.toggle('active', isActive);
      });
      document.querySelectorAll('.settings-tab-pane').forEach(pane => {
        const isTarget = (pane.id === `settings-pane-${tabName}`);
        pane.classList.toggle('active', isTarget);
        pane.style.display = isTarget ? 'flex' : 'none';
      });
      if (tabName === 'map' && typeof syncMapFilterModalUI === 'function') {
        syncMapFilterModalUI();
      }
    }

    let mapModalTempRegion = currentRegion, mapModalTempChain = 'all';
    try {
      mapModalTempRegion = localStorage.getItem('poketan_map_region') || currentRegion;
      mapModalTempChain = localStorage.getItem('poketan_map_chain') || 'all';
    } catch(e) {}

    function syncMapFilterModalUI() {
      document.querySelectorAll('#map-modal-region-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempRegion));
      document.querySelectorAll('#map-modal-chain-group .filter-option-btn').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-val') === mapModalTempChain));
      const pinSelect = document.getElementById('set-stock-pin-hours');
      if (pinSelect) {
        const curHours = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
        pinSelect.value = curHours;
      }
    }
    function selectMapModalRegion(val) { mapModalTempRegion = val; syncMapFilterModalUI(); }
    function selectMapModalChain(val) { mapModalTempChain = val; syncMapFilterModalUI(); }
    function selectMapModalStatus(val) {}
    function selectMapModalTime(val) {}
    function resetMapFilters() {
      mapModalTempRegion = 'osaka';
      mapModalTempChain = 'all';
      const pinSelect = document.getElementById('set-stock-pin-hours');
      if (pinSelect) pinSelect.value = '24';
      syncMapFilterModalUI();
    }
    function applyAndCloseMapFilterModal() {
      try {
        localStorage.setItem('poketan_selected_region', mapModalTempRegion);
        localStorage.setItem('poketan_map_region', mapModalTempRegion);
        localStorage.setItem('poketan_map_chain', mapModalTempChain);
      } catch(e) {}
      const pinSelect = document.getElementById('set-stock-pin-hours');
      const stockHours = pinSelect ? pinSelect.value : (localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
      updateStockPinHours(stockHours);
      closeSettingsModal();
      window.location.href = `/?region=${encodeURIComponent(mapModalTempRegion)}`;
    }

    function openSettingsModal(initialTab = 'map') {
      const tokenEl = document.getElementById('tg-cfg-token');
      const chatIdEl = document.getElementById('tg-cfg-chatid');
      const enabledEl = document.getElementById('tg-cfg-enabled');
      const statusEl = document.getElementById('tg-cfg-status');
      const chainEl = document.getElementById('tg-cfg-chain');
      const timeEl = document.getElementById('tg-cfg-time');
      const regionEl = document.getElementById('tg-cfg-region');

      if (tokenEl) tokenEl.value = configData.telegramBotToken || '';
      if (chatIdEl) chatIdEl.value = configData.telegramChatId || '';
      if (enabledEl) {
        enabledEl.checked = !!configData.telegramEnabled;
        onTelegramToggleChange(!!configData.telegramEnabled);
      }
      if (statusEl) statusEl.value = configData.telegramStatus || 'in';
      if (chainEl) chainEl.value = configData.telegramChain || 'all';
      if (timeEl) timeEl.value = String(configData.telegramTime || '24');
      if (regionEl) regionEl.value = configData.telegramRegion || 'osaka';

      const rad = document.querySelector(`input[name="set-region-radio"][value="${currentRegion}"]`);
      if (rad) rad.checked = true;

      const soundCheck = document.getElementById('set-sound-check');
      if (soundCheck) {
        if (configData.notifications && typeof configData.notifications.soundEnabled !== 'undefined') {
          soundCheck.checked = !!configData.notifications.soundEnabled;
        } else if (typeof configData.soundEnabled !== 'undefined') {
          soundCheck.checked = !!configData.soundEnabled;
        } else {
          soundCheck.checked = true;
        }
      }

      const pinHoursSelect = document.getElementById('set-stock-pin-hours');
      if (pinHoursSelect) {
        const curHours = String(localStorage.getItem('poketan_stock_pin_hours') || configData.stockPinEffectHours || '24');
        pinHoursSelect.value = curHours;
      }

      try {
        mapModalTempRegion = localStorage.getItem('poketan_map_region') || currentRegion;
        mapModalTempChain = localStorage.getItem('poketan_map_chain') || 'all';
      } catch(e) {}

      switchSettingsTab(initialTab || 'map');
      document.getElementById('settings-modal').classList.add('open');
    }
    function closeSettingsModal() { document.getElementById('settings-modal').classList.remove('open'); }

    function updateStockPinHours(val) {
      configData.stockPinEffectHours = String(val);
      try { localStorage.setItem('poketan_stock_pin_hours', String(val)); } catch(e) {}
    }

    function updateSettings(key, val) {
      if (!configData.notifications) configData.notifications = {};
      configData.notifications[key] = val;
      configData[key] = val;
      try { localStorage.setItem('poketan_config', JSON.stringify(configData)); } catch(e) {}
      try {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notifications: { [key]: val } })
        }).catch(() => {});
      } catch(e) {}
    }

    function selectRegion(pref) {
      currentRegion = pref;
      try { localStorage.setItem('poketan_selected_region', pref); } catch(e) {}
      listRegionFilter = pref;
      listCurrentPage = 1;
      updateListFilterBadgeUI();
      const searchVal = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
      renderStoreList(searchVal);
      closeSettingsModal();
      if (typeof ensureStoresLoadedForRegion === 'function') ensureStoresLoadedForRegion(pref);
    }

    function refreshData() {
      if (typeof initData === 'function') initData();
    }

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
    function openBulletinModal() { document.getElementById('bulletin-modal').classList.add('open'); }
    function closeBulletinModal() { document.getElementById('bulletin-modal').classList.remove('open'); }
    function openSearchModal() { openPrefModal(); }

    function switchHistTab(tab) {
      const btnList = document.getElementById('tab-btn-hist-list');
      const btnAnalytics = document.getElementById('tab-btn-hist-analytics');
      const bodyList = document.getElementById('hist-modal-body');
      const bodyAnalytics = document.getElementById('hist-modal-analytics');
      if (!btnList || !btnAnalytics || !bodyList || !bodyAnalytics) return;

      if (tab === 'analytics') {
        btnAnalytics.style.borderBottom = '2px solid #ef4444';
        btnAnalytics.style.color = '#ef4444';
        btnAnalytics.style.fontWeight = '700';
        btnList.style.borderBottom = '2px solid transparent';
        btnList.style.color = '#64748b';
        btnList.style.fontWeight = '600';
        bodyList.style.display = 'none';
        bodyAnalytics.style.display = 'block';
      } else {
        btnList.style.borderBottom = '2px solid #ef4444';
        btnList.style.color = '#ef4444';
        btnList.style.fontWeight = '700';
        btnAnalytics.style.borderBottom = '2px solid transparent';
        btnAnalytics.style.color = '#64748b';
        btnAnalytics.style.fontWeight = '600';
        bodyList.style.display = 'block';
        bodyAnalytics.style.display = 'none';
      }
    }

    const storeAnalyticsCache = {};

    function renderAnalyticsHtml(data) {
      if (!data || data.total_reports === 0) {
        return '<div style="text-align:center; padding:30px 15px; color:#64748b;">Chưa có dữ liệu thống kê báo cáo nào cho cửa hàng này.</div>';
      }

      const totalRep = data.total_reports || 0;
      const inRep = data.in_stock_reports || 0;
      const ratePct = data.in_stock_rate_pct || 0;
      const peakHours = data.peak_hours || [];
      const peakDays = data.peak_weekdays || [];
      const hourly = data.hourly_distribution || [];
      const weekday = data.weekday_distribution || [];
      const topPacks = data.top_packs || [];

      let maxHrCount = 1;
      hourly.forEach(h => { if (h.count > maxHrCount) maxHrCount = h.count; });

      const hourlyBarsHtml = hourly.map(h => {
        const heightPct = Math.round((h.count / maxHrCount) * 100);
        const isPeak = heightPct >= 70 && h.count > 0;
        const barColor = isPeak ? '#ef4444' : (h.count > 0 ? '#10b981' : '#e2e8f0');
        return `
          <div style="flex:1; display:flex; flex-direction:column; align-items:center; min-width:11px;" title="${h.hour}:00 JST - ${h.count} lần có hàng">
            <div style="font-size:0.55rem; color:${isPeak ? '#ef4444' : '#64748b'}; font-weight:700; height:12px;">${h.count > 0 ? h.count : ''}</div>
            <div style="width:100%; max-width:10px; height:60px; background:#f1f5f9; border-radius:3px; display:flex; align-items:flex-end; overflow:hidden;">
              <div style="width:100%; height:${heightPct}%; background:${barColor}; border-radius:2px; transition:height 0.3s;"></div>
            </div>
            <div style="font-size:0.55rem; color:#94a3b8; margin-top:3px;">${parseInt(h.hour)}</div>
          </div>
        `;
      }).join('');

      let maxWdCount = 1;
      weekday.forEach(w => { if (w.count > maxWdCount) maxWdCount = w.count; });

      const weekdayBarsHtml = weekday.map(w => {
        const widthPct = Math.round((w.count / maxWdCount) * 100);
        const isPeak = widthPct >= 75 && w.count > 0;
        const barColor = isPeak ? '#ef4444' : (w.count > 0 ? '#3b82f6' : '#cbd5e1');
        return `
          <div style="margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; font-weight:700; margin-bottom:2px;">
              <span style="color:${isPeak ? '#ef4444' : '#334155'};">${w.day}</span>
              <span style="color:#64748b;">${w.count} lần có hàng</span>
            </div>
            <div style="width:100%; height:8px; background:#f1f5f9; border-radius:4px; overflow:hidden;">
              <div style="width:${widthPct}%; height:100%; background:${barColor}; border-radius:4px; transition:width 0.3s;"></div>
            </div>
          </div>
        `;
      }).join('');

      const peakHoursHtml = peakHours.length > 0 
        ? peakHours.map(ph => `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-weight:700; font-size:0.72rem; padding:3px 8px; border-radius:6px; display:inline-flex; align-items:center; gap:3px;">🔥 ${ph}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa có đủ mẫu</span>';

      const peakDaysHtml = peakDays.length > 0
        ? peakDays.map(pd => `<span style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:700; font-size:0.72rem; padding:3px 8px; border-radius:6px; display:inline-flex; align-items:center; gap:3px;">📅 ${pd}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa có đủ mẫu</span>';

      const topPacksHtml = topPacks.length > 0
        ? topPacks.map(tp => `<span style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-weight:700; font-size:0.7rem; padding:2px 7px; border-radius:4px;">🎁 ${escapeHtml(tp)}</span>`).join(' ')
        : '<span style="color:#94a3b8; font-size:0.75rem;">Chưa ghi nhận mã pack</span>';

      return `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px; text-align:center;">
              <div style="font-size:0.68rem; color:#166534; font-weight:600; text-transform:uppercase;">Tỉ lệ có hàng</div>
              <div style="font-size:1.4rem; font-weight:900; color:#15803d; line-height:1.2; margin-top:2px;">${ratePct}%</div>
              <div style="font-size:0.68rem; color:#166534; font-weight:600; margin-top:2px;">${inRep} / ${totalRep} báo cáo</div>
            </div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; text-align:center;">
              <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">Có hàng gần nhất</div>
              <div style="font-size:0.85rem; font-weight:800; color:#1e293b; line-height:1.3; margin-top:6px;">${data.last_in_stock_time || 'Chưa có'}</div>
              <div style="font-size:0.65rem; color:#94a3b8; margin-top:2px;">(Giờ Nhật Bản JST)</div>
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:6px; display:flex; align-items:center; gap:5px;">
              <span>⚡</span> Khung giờ vàng hàng về (Peak Hours JST):
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${peakHoursHtml}
            </div>

            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-top:10px; margin-bottom:6px; display:flex; align-items:center; gap:5px;">
              <span>🗓️</span> Ngày trong tuần hay có hàng nhất:
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${peakDaysHtml}
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:0.75rem; font-weight:800; color:#1e293b;">🕒 Phân bố giờ có hàng (0h - 23h JST)</span>
              <span style="font-size:0.65rem; color:#64748b;">(Cột càng cao = Hàng về càng nhiều)</span>
            </div>
            <div style="display:flex; gap:2px; align-items:flex-end; height:75px; padding:0 2px; border-bottom:1px solid #e2e8f0;">
              ${hourlyBarsHtml}
            </div>
            <div style="text-align:center; font-size:0.62rem; color:#94a3b8; margin-top:4px;">0h = Nửa đêm • 12h = Trưa • 23h = Đêm (Giờ JST)</div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:8px;">
              📅 Phân bố ngày trong tuần (Thứ Hai → Chủ Nhật)
            </div>
            ${weekdayBarsHtml}
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px;">
            <div style="font-size:0.75rem; font-weight:800; color:#1e293b; margin-bottom:6px;">
              🎁 Các gói thẻ ghi nhận từng về tại quán:
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:5px;">
              ${topPacksHtml}
            </div>
          </div>
        </div>
      `;
    }

    async function openStoreHistoryModal(storeId) {
      const modal = document.getElementById('store-history-modal');
      const bodyEl = document.getElementById('hist-modal-body');
      const analyticsEl = document.getElementById('hist-modal-analytics');
      const nameEl = document.getElementById('hist-modal-store-name');

      switchHistTab('list');
      modal.classList.add('open');
      bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang tải lịch sử báo cáo...</div>';
      analyticsEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">⏳ Đang phân tích quy luật hàng về...</div>';

      const stName = (typeof storesDict !== 'undefined' && storesDict[storeId]) ? storesDict[storeId].name : 'Cửa hàng';
      if (nameEl) nameEl.textContent = stName;

      // 1. Fetch History List
      try {
        let history = storeHistoryCache[storeId];
        if (!history) {
          const res = await fetch(`/api/store_history/${storeId}`);
          history = await res.json();
          storeHistoryCache[storeId] = history;
        }
        if (!history || history.length === 0) {
          bodyEl.innerHTML = '<div style="text-align:center; padding:20px; color:#64748b;">Chưa có lịch sử báo cáo nào.</div>';
        } else {
          // Synchronize reportCounts with distinct counts from history
          let countIn = 0, countOut = 0;
          const seenInTs = new Set(), seenOutTs = new Set();
          history.forEach(item => {
            const ts = item.timestamp || item.formatted_time;
            if (item.status_code === 'i') {
              if (!seenInTs.has(ts)) { seenInTs.add(ts); countIn++; }
            } else if (item.status_code === 'o') {
              if (!seenOutTs.has(ts)) { seenOutTs.add(ts); countOut++; }
            }
          });
          if (typeof storeCountsCache !== 'undefined') {
            storeCountsCache[storeId] = { in: countIn, out: countOut };
          }
          if (typeof reportCounts !== 'undefined') {
            reportCounts[storeId] = { in: countIn, out: countOut };
          }
          if (typeof renderStoreList === 'function') {
            renderStoreList();
          }

          // Propagate newest history record to local store object and refresh list
          if (typeof storesDict !== 'undefined' && storesDict[storeId]) {
            const newest = history[0];
            const st = storesDict[storeId];
            const histTs = Number(newest.timestamp) || 0;
            if (histTs >= (st.last_timestamp || 0) || st.status === 'u') {
              st.status = newest.status_code || newest.status || 'u';
              st.last_timestamp = histTs;
              st.last_reported_at = newest.formatted_time || '';
              st.onsite = !!newest.onsite;
              st.packs = newest.packs || [];
              if (typeof renderStoreList === 'function') {
                renderStoreList();
              }
            }
          }
          bodyEl.innerHTML = history.map(item => {
            let histColor = '#64748b', histText = '⚪ Chưa rõ';
            if (item.status_code === 'i') { histColor = '#15803d'; histText = '🟢 Có hàng'; }
            else if (item.status_code === 'o') { histColor = '#b91c1c'; histText = '🔴 Hết hàng'; }
            else if (item.status_code === 'n') { histColor = '#b45309'; histText = '🟡 Không bán thẻ'; }

            const packsHtml = (item.packs && item.packs.length > 0)
              ? `<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:6px;">
                  ${item.packs.map(p => `
                    <span style="display:inline-flex; align-items:center; gap:3px; background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-size:0.68rem; font-weight:700; padding:2px 7px; border-radius:4px;">
                      🎁 ${escapeHtml(p)}
                    </span>
                  `).join('')}
                </div>`
              : '';

            const onsiteHtml = item.onsite
              ? `<span style="display:inline-flex; align-items:center; gap:2px; background:#dcfce7; color:#15803d; border:1px solid #86efac; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:10px;">
                  📍 Tại quán (GPS)
                </span>`
              : '';

            const confirmsCount = Number(item.confirms) || 1;
            const confirmsHtml = (confirmsCount > 1)
              ? `<span style="display:inline-flex; align-items:center; gap:2px; background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:10px;">
                  👍 ${confirmsCount} xác nhận
                </span>`
              : '';

            return `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:10px 12px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
              <div style="display:flex; justify-content:space-between; align-items:center; font-weight:800; font-size:0.8rem;">
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                  <span style="color:${histColor}; font-weight:800;">${histText}</span>
                  ${onsiteHtml}
                  ${confirmsHtml}
                </div>
                <span style="color:#64748b; font-size:0.7rem; font-weight:500;">🕒 ${escapeHtml(item.formatted_time || '')}</span>
              </div>
              ${packsHtml}
              ${item.note ? `<div style="font-size:0.75rem; color:#1e293b; background:#f8fafc; border:1px solid #f1f5f9; border-radius:6px; padding:5px 8px; margin-top:6px;">💬 ${escapeHtml(item.note)}</div>` : ''}
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.68rem; color:#94a3b8; margin-top:6px;">
                <span>👤 Người báo: <b>${escapeHtml(item.user || 'Ẩn danh')}</b>${item.who ? ` <span style="font-size:0.62rem; color:#cbd5e1;">(#${escapeHtml(item.who)})</span>` : ''}</span>
                ${item.source ? `<span style="font-size:0.62rem; color:#94a3b8; text-transform:uppercase;">[${escapeHtml(item.source)}]</span>` : ''}
              </div>
            </div>
          `;
          }).join('');
        }
      } catch(e) {
        bodyEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi tải lịch sử.</div>';
      }

      // 2. Fetch Analytics
      try {
        let analytics = storeAnalyticsCache[storeId];
        if (!analytics) {
          const aRes = await fetch(`/api/analytics/store/${storeId}`);
          analytics = await aRes.json();
          storeAnalyticsCache[storeId] = analytics;
        }
        analyticsEl.innerHTML = renderAnalyticsHtml(analytics);
      } catch(e) {
        analyticsEl.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi phân tích quy luật.</div>';
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
        { enableHighAccuracy: true, timeout: 6000 }
      );
    }

    let audioCtx = null;
    function playAudioAlert() {
      try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
        osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.12); // A5
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);
        osc.start(audioCtx.currentTime);
        osc.stop(audioCtx.currentTime + 0.45);
      } catch(e) {}
    }
    document.addEventListener('click', () => {
      if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    }, { passive: true });


    function formatTimeAgoJp(timestamp) {
      if (!timestamp) return 'たった今';
      const diffSec = getServerNowSec() - timestamp;
      if (diffSec < 0) return 'たった今';
      if (diffSec <= 120) return 'たった今';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分前`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}時間前`;
      return `${Math.floor(diffSec / 86400)}日前`;
    }

    function showNewReportToast(rep) {
      const container = document.getElementById('live-report-toast-container');
      if (!container) return;

      // 1. Remove any existing toast for this exact store so the store never appears twice
      const existingSameStore = container.querySelector(`[data-store-id="${rep.store_id}"]`);
      if (existingSameStore) {
        existingSameStore.remove();
      }

      const st = storesDict[rep.store_id];
      const name = st ? st.name : (rep.store_name || '店舗');
      const isStock = rep.status_code === 'i';
      const isOut = rep.status_code === 'o';

      const dotClass = isStock ? 'dot-in' : (isOut ? 'dot-out' : 'dot-not');
      const statusClass = isStock ? 'status-in' : (isOut ? 'status-out' : 'status-not');
      const statusLabel = isStock ? '在庫あり' : (isOut ? '在庫なし' : '扱ってない');
      const repTs = Number(rep.timestamp) || 0;
      const repAgeSec = repTs > 0 ? (getServerNowSec() - repTs) : 0;
      const timeAgo = (repTs > 0 && repAgeSec >= 0 && repAgeSec <= 120) ? 'たった今' : (repTs > 0 ? formatTimeAgoJp(repTs) : 'たった今');

      const toast = document.createElement('div');
      toast.className = `poketan-pill-toast ${isStock ? 'stock-pill' : ''}`;
      toast.dataset.storeId = rep.store_id;
      toast.dataset.ts = repTs;
      toast.onclick = () => { window.location.href = `/map?focus=${rep.store_id}`; };
      toast.innerHTML = `
        <span class="pill-dot ${dotClass}"></span>
        <span class="pill-store-name">${escapeHtml(name)}</span>
        <span class="pill-text">で</span>
        <span class="pill-status ${statusClass}">${statusLabel}</span>
        <span class="pill-text">の報告</span>
        <span class="pill-time" data-timestamp="${repTs}">${escapeHtml(timeAgo)}</span>
        <button type="button" class="pill-close-btn" onclick="event.stopPropagation(); this.closest('.poketan-pill-toast').remove();" title="閉じる">✕</button>
      `;

      // 2. Insert in strict chronological order: NEWEST (highest timestamp) at TOP, older below
      const existingToasts = Array.from(container.children);
      let inserted = false;
      for (const existing of existingToasts) {
        const existingTs = Number(existing.dataset.ts) || 0;
        if (repTs >= existingTs) {
          container.insertBefore(toast, existing);
          inserted = true;
          break;
        }
      }
      if (!inserted) {
        container.appendChild(toast);
      }

      // 3. Keep at most 3 visible toasts to keep screen clean and avoid covering UI
      while (container.children.length > 3) {
        container.lastElementChild.remove();
      }

      // 4. Auto-dismiss after 6 seconds
      setTimeout(() => {
        if (toast.parentElement) {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(-10px) scale(0.96)';
          setTimeout(() => toast.remove(), 250);
        }
      }, 6000);
    }

    function updateLiveRelativeTimes() {
      // 1. Update relative time pills on store list cards
      document.querySelectorAll('.time-ago-highlight[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0) {
          const newStr = formatTimeAgoVi(ts);
          if (el.textContent !== newStr) {
            el.textContent = newStr;
          }
        }
      });

      // 2. Update pill toasts (if any)
      document.querySelectorAll('.pill-time[data-timestamp]').forEach(el => {
        const ts = Number(el.getAttribute('data-timestamp')) || 0;
        if (ts > 0) {
          const newStr = formatTimeAgoJp(ts);
          if (el.textContent !== newStr) {
            el.textContent = newStr;
          }
        }
      });
    }

    const seenToastKeys = new Set();
    let lastDbPollTs = 0;

    async function pollDatabaseUpdates() {
      if (!lastDbPollTs) return;
      try {
        const res = await fetch(`/api/latest_reports?since=${lastDbPollTs}&limit=50`);
        if (!res.ok) return;
        const reports = await res.json();
        if (Array.isArray(reports) && reports.length > 0) {
          let hasNewStock = false;
          let shouldReRender = false;
          const nowSec = getServerNowSec();
          const candidateStockReps = [];

          for (const rep of reports) {
            // Strictly advance polling timestamp using SQLite created_at
            if (rep.created_at && rep.created_at > lastDbPollTs) {
              lastDbPollTs = rep.created_at;
            }

            const sid = rep.store_id;
            let st = storesDict[sid];
            if (!st && rep.lat && rep.lng) {
              storesDict[sid] = {
                id: sid,
                name: rep.store_name,
                chain: rep.chain,
                lat: rep.lat,
                lng: rep.lng,
                address: rep.address,
                pref: rep.pref,
                status: rep.status_code,
                last_timestamp: rep.timestamp,
                onsite: !!rep.onsite,
                packs: rep.packs || [],
                last_reported_at: rep.reported_at || rep.formatted_time || ''
              };
              st = storesDict[sid];
              shouldReRender = true;
            } else if (st) {
              if (!st.last_timestamp || (rep.timestamp && rep.timestamp >= st.last_timestamp)) {
                st.status = rep.status_code;
                st.last_timestamp = rep.timestamp;
                st.onsite = !!rep.onsite;
                st.packs = rep.packs || [];
                st.last_reported_at = rep.reported_at || rep.formatted_time || '';
                shouldReRender = true;
              }
            }

            // Real-time toast check:
            // 1. Must be in-stock (i)
            // 2. Deduplicate strictly by composite key (store_id, timestamp, status_code)
            // 3. Must be genuinely real-time: reported within the last 120 seconds (2 minutes)
            const toastKey = `${rep.store_id}_${rep.timestamp}_${rep.status_code}`;
            const reportAgeSec = rep.timestamp > 0 ? (nowSec - rep.timestamp) : 0;
            const isFreshRealtime = reportAgeSec >= 0 && reportAgeSec <= 120;

            if (rep.status_code === 'i' && !seenToastKeys.has(toastKey) && isFreshRealtime) {
              seenToastKeys.add(toastKey);
              candidateStockReps.push(rep);
            }
          }

          // Sort candidate stock reports strictly by timestamp DESC (newest first)
          if (candidateStockReps.length > 0) {
            candidateStockReps.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
            // Show at most 3 fresh toasts to avoid flooding screen
            for (const rep of candidateStockReps.slice(0, 3)) {
              hasNewStock = true;
              showNewReportToast(rep);
            }
          }

          if (hasNewStock && configData.soundEnabled) {
            playAudioAlert();
          }
          if (shouldReRender) {
            const q = document.getElementById('list-search-input') ? document.getElementById('list-search-input').value : '';
            renderStoreList(q);
          }
        }
      } catch (e) {
        console.warn('DB Poll error:', e);
      }
    }

    async function initData() {
      checkGpsSilently();
      try {
        const reqRegion = currentRegion || 'osaka';
        const [cfgRes, storesRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/stores_data?region=' + encodeURIComponent(reqRegion))
        ]);
        configData = await cfgRes.json();
        storesDict = await storesRes.json();
        loadedRegions.add(reqRegion);

        // Fetch report counts asynchronously in background (does not block list render)
        fetch('/api/report_counts?region=' + encodeURIComponent(reqRegion))
          .then(r => r.ok ? r.json() : null)
          .then(countsData => {
            if (countsData) {
              if (typeof reportCounts !== 'undefined') Object.assign(reportCounts, countsData);
              if (typeof storeCountsCache !== 'undefined') Object.assign(storeCountsCache, countsData);
            }
          })
          .catch(() => {});

        // Calibrate server time offset to correct browser clock drift
        if (configData.serverTime) {
          serverTimeOffset = configData.serverTime - Math.floor(Date.now() / 1000);
        }

        // Pre-fill seenToastKeys with all stores currently in stock so page load NEVER triggers old toast alerts!
        for (const sid in storesDict) {
          const s = storesDict[sid];
          if (s && s.status === 'i' && s.last_timestamp) {
            seenToastKeys.add(`${sid}_${s.last_timestamp}_i`);
          }
        }

        // Sync initial UI badges
        document.querySelectorAll('.list-sort-btn').forEach(b => b.classList.toggle('active', b.id === `sort-btn-${listSortMode}`));
        updateListFilterBadgeUI();

        renderStoreList();

        // Initialize DB poll timestamp to current time so only future/real-time reports trigger alerts
        lastDbPollTs = getServerNowSec();
        if (!window._dbPollInterval) {
          window._dbPollInterval = setInterval(pollDatabaseUpdates, 5000);
        }
        if (!window._liveTimeInterval) {
          window._liveTimeInterval = setInterval(updateLiveRelativeTimes, 15000);
        }

        // Mark all notifications as read when viewing Thongbao page
        localStorage.setItem('poketan_last_read_ts', String(Math.floor(Date.now() / 1000)));
        const badgeEl = document.getElementById('footer-unread-badge');
        if (badgeEl) badgeEl.style.display = 'none';
      } catch(e) {
        console.error('Init error:', e);
      } finally {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.opacity = '0';
        setTimeout(() => overlay && overlay.remove(), 150);
      }
    }

    window.addEventListener('DOMContentLoaded', initData);
  </script>
</body>
</html>"""
