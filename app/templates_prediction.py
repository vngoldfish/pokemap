"""
HTML Template and Page Renderer for PokéMap AI Restock Prediction Dashboard
Routes: GET /dudoan, GET /goiy, GET /radar, GET /predict
Real-time Restock Timing Predictions by Hour, Day of Week & Distance Radius (KM).
"""

def render_dudoan_page() -> str:
    from .templates import get_shared_head, SHARED_BASE_CSS, render_shared_footer, SHARED_MODALS_HTML

    shared_head = get_shared_head("🎯 Dự Đoán Restock Theo Giờ & Bán Kính - AI Pokédar Tracker", include_leaflet=False)
    shared_footer = render_shared_footer("dudoan")

    html = """__SHARED_HEAD__
__SHARED_BASE_CSS__
  <style>
    /* CUSTOM STYLES FOR PREDICTION DASHBOARD */
    html, body {
      width: 100%;
      height: 100%;
      height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      background: #0b1120;
      color: #f1f5f9;
      margin: 0;
      padding: 0;
    }

    #radar-header {
      height: 52px;
      background: #0f172a;
      border-bottom: 1px solid #1e293b;
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      z-index: 100;
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }

    .radar-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: #ffffff;
    }
    .radar-brand .logo-badge {
      background: linear-gradient(135deg, #ef4444, #f59e0b);
      color: #fff;
      font-size: 0.75rem;
      font-weight: 900;
      padding: 4px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
      box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
    }
    .radar-title {
      font-size: 0.98rem;
      font-weight: 800;
      color: #f8fafc;
      letter-spacing: -0.3px;
    }
    .radar-subtitle {
      font-size: 0.68rem;
      color: #94a3b8;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 5px;
    }

    .radar-actions {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .radar-btn {
      padding: 6px 11px;
      border-radius: 8px;
      font-size: 0.75rem;
      font-weight: 700;
      border: 1px solid transparent;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .radar-btn-primary {
      background: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }
    .radar-btn-primary:hover {
      background: #1d4ed8;
    }
    .radar-btn-outline {
      background: #1e293b;
      color: #cbd5e1;
      border-color: #334155;
    }
    .radar-btn-outline:hover {
      background: #334155;
      color: #ffffff;
    }
    .radar-btn-gps.active {
      background: #065f46;
      border-color: #10b981;
      color: #6ee7b7;
    }

    /* MAIN CONTAINER */
    #radar-container {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      padding: 12px 14px 24px 14px;
      max-width: 1100px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
      -webkit-overflow-scrolling: touch;
    }

    /* LIVE STATUS BANNER */
    .radar-status-banner {
      background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95));
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 12px 14px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    }
    .status-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .pulse-radar-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
      animation: pulse-green 1.8s infinite;
      flex-shrink: 0;
    }
    @keyframes pulse-green {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .status-info-title {
      font-size: 0.85rem;
      font-weight: 800;
      color: #f8fafc;
    }
    .status-info-desc {
      font-size: 0.72rem;
      color: #94a3b8;
    }
    .status-badge-time {
      background: #0284c7;
      color: #f0f9ff;
      font-size: 0.75rem;
      font-weight: 800;
      padding: 4px 10px;
      border-radius: 20px;
      border: 1px solid #38bdf8;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    /* RADIUS CONTROL & LOCAL STATS SECTION */
    .radius-bar-card {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
    }
    .radius-header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
      flex-wrap: wrap;
      gap: 6px;
    }
    .radius-title {
      font-size: 0.78rem;
      font-weight: 800;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .radius-chips-row {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      margin-bottom: 4px;
      -webkit-overflow-scrolling: touch;
    }
    .radius-chip {
      padding: 6px 12px;
      border-radius: 8px;
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      font-size: 0.72rem;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .radius-chip:hover {
      background: #334155;
      color: #ffffff;
    }
    .radius-chip.active {
      background: #059669;
      border-color: #10b981;
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
    }

    /* RADIUS KPI GRID */
    .radius-kpi-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-top: 10px;
    }
    @media (min-width: 640px) {
      .radius-kpi-grid {
        grid-template-columns: repeat(4, 1fr);
      }
    }
    .radius-kpi-box {
      background: #141e33;
      border: 1px solid #1e293b;
      border-radius: 10px;
      padding: 10px;
      position: relative;
      overflow: hidden;
    }
    .radius-kpi-box::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 3px;
      bottom: 0;
      background: #38bdf8;
    }
    .kpi-accent-green::before { background: #10b981; }
    .kpi-accent-amber::before { background: #f59e0b; }
    .kpi-accent-red::before { background: #ef4444; }
    .kpi-accent-purple::before { background: #8b5cf6; }

    .radius-kpi-val {
      font-size: 1.25rem;
      font-weight: 900;
      color: #f8fafc;
      line-height: 1.1;
    }
    .radius-kpi-label {
      font-size: 0.68rem;
      font-weight: 800;
      color: #94a3b8;
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }
    .radius-kpi-sub {
      font-size: 0.62rem;
      color: #cbd5e1;
      margin-top: 2px;
    }

    /* TIMELINE & HOUR FILTER BAR */
    .timeline-card {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
    }
    .timeline-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .timeline-title {
      font-size: 0.78rem;
      font-weight: 800;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .timeline-presets {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 6px;
      margin-bottom: 8px;
      -webkit-overflow-scrolling: touch;
    }
    .preset-chip {
      padding: 5px 11px;
      border-radius: 8px;
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      font-size: 0.72rem;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .preset-chip:hover {
      background: #334155;
      color: #ffffff;
    }
    .preset-chip.active {
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }

    /* 24-HOUR SCROLLER */
    .hour-scroller {
      display: flex;
      gap: 5px;
      overflow-x: auto;
      padding: 4px 2px 8px 2px;
      -webkit-overflow-scrolling: touch;
    }
    .hour-pill {
      min-width: 50px;
      padding: 6px 4px;
      border-radius: 8px;
      background: #1e293b;
      border: 1px solid #334155;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 3px;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.15s ease;
      position: relative;
    }
    .hour-pill:hover {
      background: #273549;
    }
    .hour-pill.active {
      background: #1d4ed8;
      border-color: #60a5fa;
      box-shadow: 0 0 10px rgba(96, 165, 250, 0.4);
    }
    .hour-pill.is-now {
      border-color: #10b981;
    }
    .hour-pill.is-now::after {
      content: 'NOW';
      position: absolute;
      top: -6px;
      right: -2px;
      background: #10b981;
      color: #042f2e;
      font-size: 0.48rem;
      font-weight: 900;
      padding: 1px 3px;
      border-radius: 4px;
      line-height: 1;
    }
    .hour-label {
      font-size: 0.7rem;
      font-weight: 800;
      color: #f1f5f9;
    }
    .hour-bar-wrap {
      width: 26px;
      height: 4px;
      background: #334155;
      border-radius: 2px;
      overflow: hidden;
    }
    .hour-bar-fill {
      height: 100%;
      background: #38bdf8;
      border-radius: 2px;
    }
    .hour-freq {
      font-size: 0.58rem;
      color: #94a3b8;
      font-weight: 600;
    }

    /* FILTER BAR */
    .radar-filters-card {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 10px 12px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .radar-select {
      background: #1e293b;
      color: #f1f5f9;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 0.75rem;
      font-weight: 700;
      outline: none;
      cursor: pointer;
    }
    .radar-select:focus {
      border-color: #3b82f6;
    }
    .filter-count-badge {
      margin-left: auto;
      font-size: 0.72rem;
      font-weight: 700;
      color: #94a3b8;
    }
    .filter-count-badge strong {
      color: #38bdf8;
    }

    /* PREDICTION CARDS LIST */
    #prediction-list {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    @media (min-width: 768px) {
      #prediction-list {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .pred-card {
      background: #141e33;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      position: relative;
      overflow: hidden;
      transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .pred-card:hover {
      border-color: #3b82f6;
      box-shadow: 0 6px 20px rgba(0,0,0,0.35);
      transform: translateY(-1px);
    }
    .pred-card.card-prime {
      border-color: rgba(239, 68, 68, 0.45);
      background: linear-gradient(135deg, rgba(30, 27, 75, 0.4), rgba(20, 30, 51, 0.95));
    }
    .pred-card.card-prime::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, #ef4444, #f59e0b);
    }

    /* FLASHING 30-MIN IN-STOCK & OUT-OF-STOCK CARDS */
    @keyframes pulse-green-glow {
      0% {
        box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.75);
        border-color: #10b981;
      }
      50% {
        box-shadow: 0 0 20px 5px rgba(16, 185, 129, 0.9);
        border-color: #34d399;
      }
      100% {
        box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.75);
        border-color: #10b981;
      }
    }
    @keyframes pulse-red-glow {
      0% {
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.75);
        border-color: #ef4444;
      }
      50% {
        box-shadow: 0 0 20px 5px rgba(239, 68, 68, 0.9);
        border-color: #f87171;
      }
      100% {
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.75);
        border-color: #ef4444;
      }
    }
    @keyframes badge-blink {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.7; transform: scale(1.05); }
    }

    .pred-card.card-flash-green {
      border: 2px solid #10b981 !important;
      background: linear-gradient(135deg, rgba(6, 78, 59, 0.65), rgba(15, 23, 42, 0.96)) !important;
      animation: pulse-green-glow 1.4s infinite ease-in-out;
    }
    .pred-card.card-flash-green::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, #10b981, #34d399, #10b981);
    }

    .pred-card.card-flash-red {
      border: 2px solid #ef4444 !important;
      background: linear-gradient(135deg, rgba(127, 29, 29, 0.65), rgba(15, 23, 42, 0.96)) !important;
      animation: pulse-red-glow 1.4s infinite ease-in-out;
    }
    .pred-card.card-flash-red::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, #ef4444, #f87171, #ef4444);
    }

    .score-badge-flash-green {
      background: linear-gradient(135deg, #059669, #10b981) !important;
      color: #ffffff !important;
      animation: badge-blink 1.2s infinite ease-in-out;
      font-size: 0.74rem !important;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.6);
    }
    .score-badge-flash-red {
      background: linear-gradient(135deg, #b91c1c, #ef4444) !important;
      color: #ffffff !important;
      animation: badge-blink 1.2s infinite ease-in-out;
      font-size: 0.74rem !important;
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
    }

    /* STATUS TABS FOR REAL-TIME & PREDICTIONS */
    .status-filter-tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
      overflow-x: auto;
      padding-bottom: 4px;
      -webkit-overflow-scrolling: touch;
    }
    .status-tab-btn {
      padding: 7px 12px;
      border-radius: 9px;
      background: #0f172a;
      border: 1px solid #1e293b;
      color: #cbd5e1;
      font-size: 0.75rem;
      font-weight: 800;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      transition: all 0.15s ease;
    }
    .status-tab-btn:hover {
      background: #1e293b;
      color: #ffffff;
      border-color: #334155;
    }
    .status-tab-btn.active {
      background: #1e293b;
      border-color: #38bdf8;
      color: #ffffff;
      box-shadow: 0 2px 10px rgba(56, 189, 248, 0.25);
    }
    .status-tab-btn.active.tab-green {
      border-color: #10b981;
      box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3);
      color: #34d399;
    }
    .status-tab-btn.active.tab-truck {
      border-color: #f59e0b;
      box-shadow: 0 2px 10px rgba(245, 158, 11, 0.3);
      color: #fbbf24;
    }
    .status-tab-btn.active.tab-red {
      border-color: #ef4444;
      box-shadow: 0 2px 10px rgba(239, 68, 68, 0.3);
      color: #f87171;
    }
    .status-tab-badge {
      padding: 1px 6px;
      border-radius: 999px;
      font-size: 0.65rem;
      font-weight: 900;
    }
    .badge-tab-all { background: #334155; color: #f1f5f9; }
    .badge-tab-green { background: #065f46; color: #6ee7b7; border: 1px solid #059669; }
    .badge-tab-truck { background: #78350f; color: #fde68a; border: 1px solid #d97706; }
    .badge-tab-red { background: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c; }

    /* TRUCK EN-ROUTE BADGE & CARD HIGHLIGHT */
    .card-truck-route {
      border-color: rgba(245, 158, 11, 0.5) !important;
      box-shadow: 0 4px 18px rgba(245, 158, 11, 0.15) !important;
    }
    .truck-enroute-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.68rem;
      font-weight: 800;
      background: linear-gradient(135deg, rgba(217, 119, 6, 0.25), rgba(180, 83, 9, 0.35));
      border: 1px solid #f59e0b;
      color: #fef3c7;
      letter-spacing: 0.2px;
    }
    .pulse-truck-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #f59e0b;
      box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7);
      animation: pulse-amber 1.8s infinite;
      flex-shrink: 0;
    }
    @keyframes pulse-amber {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
    }

    /* DATA RELIABILITY BADGE & STARS */
    .reliability-row {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 4px;
    }
    .reliability-stars {
      color: #fbbf24;
      font-size: 0.68rem;
      letter-spacing: 1px;
    }
    .reliability-label {
      font-size: 0.64rem;
      color: #94a3b8;
      font-weight: 600;
    }

    /* ACTIONABLE RECOMMENDATION TIP BOX */
    .card-action-tip {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 8px;
      background: rgba(30, 41, 59, 0.75);
      border: 1px dashed rgba(148, 163, 184, 0.35);
      margin: 8px 0 4px 0;
    }
    .tip-icon {
      font-size: 0.85rem;
      line-height: 1.2;
      flex-shrink: 0;
    }
    .tip-text {
      font-size: 0.7rem;
      font-weight: 700;
      color: #e2e8f0;
      line-height: 1.35;
    }

    /* CARD HEADER */
    .card-top-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
    }
    .score-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.3px;
    }
    .score-badge-prime {
      background: linear-gradient(135deg, #ef4444, #b91c1c);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
    }
    .score-badge-high {
      background: linear-gradient(135deg, #f59e0b, #b45309);
      color: #ffffff;
    }
    .score-badge-medium {
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      color: #ffffff;
    }

    .window-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #1e293b;
      border: 1px solid #334155;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 800;
      color: #f8fafc;
    }
    .window-badge.active-now {
      background: #064e3b;
      border-color: #059669;
      color: #6ee7b7;
      box-shadow: 0 0 8px rgba(16, 185, 129, 0.3);
    }

    /* CARD STORE INFO */
    .card-store-name {
      font-size: 0.95rem;
      font-weight: 800;
      color: #f8fafc;
      line-height: 1.35;
      cursor: pointer;
    }
    .card-store-name:hover {
      color: #60a5fa;
    }
    .card-meta-row {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .chain-badge {
      background: #1e293b;
      color: #94a3b8;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 1px 6px;
      font-size: 0.65rem;
      font-weight: 700;
    }
    .pref-badge {
      background: #0f172a;
      color: #38bdf8;
      border: 1px solid #0284c7;
      border-radius: 4px;
      padding: 1px 6px;
      font-size: 0.65rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .dist-badge {
      background: #064e3b;
      color: #6ee7b7;
      border-radius: 4px;
      padding: 1px 6px;
      font-size: 0.65rem;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }

    .card-address {
      font-size: 0.68rem;
      color: #94a3b8;
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    /* AI REASON BOX */
    .ai-reasons-box {
      background: #0b1120;
      border-left: 3px solid #3b82f6;
      border-radius: 0 6px 6px 0;
      padding: 7px 10px;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .ai-reason-item {
      font-size: 0.68rem;
      color: #cbd5e1;
      display: flex;
      align-items: flex-start;
      gap: 4px;
      line-height: 1.3;
    }

    /* CARD ACTIONS */
    .card-actions-row {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 2px;
      padding-top: 8px;
      border-top: 1px solid #1e293b;
    }
    .card-action-btn {
      flex: 1;
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      text-align: center;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .btn-map-link {
      background: #1e293b;
      color: #38bdf8;
      border-color: #0284c7;
    }
    .btn-map-link:hover {
      background: #0284c7;
      color: #ffffff;
    }
    .btn-gmaps-link {
      background: #064e3b;
      color: #6ee7b7;
      border-color: #059669;
    }
    .btn-gmaps-link:hover {
      background: #059669;
      color: #ffffff;
    }
    .btn-hist-link {
      background: #1e293b;
      color: #cbd5e1;
      border-color: #334155;
    }
    .btn-hist-link:hover {
      background: #334155;
      color: #ffffff;
    }
    .btn-ai-explain {
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2));
      color: #c084fc;
      border-color: #8b5cf6;
      font-weight: 800;
    }
    .btn-ai-explain:hover {
      background: linear-gradient(135deg, #6366f1, #a855f7);
      color: #ffffff;
      box-shadow: 0 0 12px rgba(168, 85, 247, 0.5);
    }

    /* HOUR SCROLLER TOOLTIP & PRIME BADGES */
    .hour-tooltip {
      position: absolute;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #38bdf8;
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 0.72rem;
      color: #f1f5f9;
      pointer-events: none;
      z-index: 500;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(8px);
      line-height: 1.5;
      max-width: 290px;
      transition: opacity 0.12s ease;
    }
    .hour-pill.is-prime-window {
      border-color: #f59e0b;
      box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
    }
    .hour-pill.is-prime-window::after {
      content: 'PRIME';
      position: absolute;
      top: -6px;
      left: -2px;
      background: #f59e0b;
      color: #000000;
      font-size: 0.46rem;
      font-weight: 900;
      padding: 1px 3px;
      border-radius: 4px;
      line-height: 1;
    }

    /* ALGORITHM EXPLANATION CARD */
    .algo-explainer-card {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 14px;
      margin-top: 20px;
    }
    .algo-explainer-title {
      font-size: 0.85rem;
      font-weight: 800;
      color: #f8fafc;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .algo-weights-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-top: 10px;
    }
    @media (min-width: 640px) {
      .algo-weights-grid {
        grid-template-columns: repeat(4, 1fr);
      }
    }
    .algo-weight-box {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 8px;
      text-align: center;
    }
    .algo-weight-pct {
      font-size: 1.1rem;
      font-weight: 900;
      color: #38bdf8;
    }
    .algo-weight-name {
      font-size: 0.68rem;
      font-weight: 700;
      color: #cbd5e1;
      margin-top: 2px;
    }
    .algo-weight-desc {
      font-size: 0.6rem;
      color: #94a3b8;
      margin-top: 2px;
    }

    /* LOADING & EMPTY STATES */
    .state-box {
      text-align: center;
      padding: 40px 20px;
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      color: #94a3b8;
    }
    .spinner {
      width: 32px;
      height: 32px;
      border: 3px solid #334155;
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 12px auto;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* COMPREHENSIVE MOBILE OPTIMIZATIONS (ULTRA-COMPACT DENSE VIEW) */
    @media (max-width: 640px) {
      #radar-header {
        padding: 0 8px;
        height: 40px;
      }
      .radar-brand {
        gap: 5px;
        min-width: 0;
        flex: 1;
        overflow: hidden;
      }
      .radar-brand .logo-badge {
        font-size: 0.62rem;
        padding: 2px 5px;
        border-radius: 4px;
        flex-shrink: 0;
      }
      .radar-title {
        font-size: 0.76rem;
        font-weight: 800;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .radar-subtitle {
        display: none !important;
      }
      .radar-actions {
        gap: 3px;
        flex-shrink: 0;
      }
      .radar-btn {
        padding: 4px 6px;
        font-size: 0.68rem;
        border-radius: 5px;
      }
      .hide-sm {
        display: none !important;
      }

      /* Container */
      #radar-container {
        padding: 6px 6px 20px 6px;
      }

      /* Live Status Banner */
      .radar-status-banner {
        padding: 5px 8px;
        margin-bottom: 6px;
        gap: 4px;
        border-radius: 8px;
      }
      .status-left {
        gap: 6px;
      }
      .status-info-title {
        font-size: 0.72rem;
        line-height: 1.2;
      }
      .status-info-desc {
        display: none !important;
      }
      .status-badge-time {
        font-size: 0.65rem;
        padding: 2px 6px;
      }

      /* Radius Section */
      .radius-card {
        padding: 6px 8px;
        margin-bottom: 6px;
        border-radius: 8px;
      }
      .radius-header-row {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        gap: 4px;
        margin-bottom: 5px;
      }
      .radius-title {
        font-size: 0.72rem;
      }
      #anchor-select {
        width: auto;
        max-width: 140px;
        font-size: 0.7rem;
        padding: 3px 6px;
        height: 28px;
        border-radius: 6px;
      }
      .radius-chips-row {
        gap: 4px;
        padding-bottom: 2px;
        margin-bottom: 2px;
        scrollbar-width: none;
      }
      .radius-chips-row::-webkit-scrollbar {
        display: none;
      }
      .radius-chip {
        padding: 3px 7px;
        font-size: 0.66rem;
        border-radius: 6px;
      }

      /* Radius KPI Grid - 2x2 Ultra Compact */
      .radius-kpi-grid {
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 4px !important;
        margin-top: 5px !important;
      }
      .radius-kpi-box {
        padding: 4px 6px !important;
        border-radius: 6px !important;
      }
      .radius-kpi-val {
        font-size: 0.95rem !important;
        line-height: 1.1 !important;
      }
      .radius-kpi-label {
        font-size: 0.56rem !important;
        margin-top: 1px !important;
      }
      .radius-kpi-sub {
        font-size: 0.54rem !important;
        margin-top: 0 !important;
      }

      /* Timeline Card */
      .timeline-card {
        padding: 6px 8px;
        margin-bottom: 6px;
        border-radius: 8px;
      }
      .timeline-title-row {
        margin-bottom: 4px;
      }
      .timeline-title {
        font-size: 0.72rem;
      }
      .timeline-presets {
        scrollbar-width: none;
        gap: 4px;
        padding-bottom: 2px;
        margin-bottom: 4px;
      }
      .timeline-presets::-webkit-scrollbar {
        display: none;
      }
      .preset-chip {
        padding: 3px 6px;
        font-size: 0.66rem;
        border-radius: 5px;
      }
      .hour-scroller {
        scrollbar-width: none;
        padding-bottom: 2px;
        gap: 3px;
      }
      .hour-scroller::-webkit-scrollbar {
        display: none;
      }
      .hour-pill {
        min-width: 36px;
        padding: 3px 2px;
        border-radius: 6px;
      }
      .hour-label {
        font-size: 0.64rem;
      }
      .hour-freq {
        font-size: 0.52rem;
      }

      /* Filter bar */
      .radar-filters-card {
        padding: 5px 8px;
        margin-bottom: 6px;
        gap: 4px;
        border-radius: 8px;
      }
      .radar-select {
        height: 28px;
        padding: 3px 6px;
        font-size: 0.7rem;
        border-radius: 6px;
      }
      .filter-count-badge {
        font-size: 0.68rem;
      }

      /* Status Tabs */
      .status-filter-tabs {
        scrollbar-width: none;
        gap: 4px;
        margin-bottom: 6px;
        padding-bottom: 2px;
      }
      .status-filter-tabs::-webkit-scrollbar {
        display: none;
      }
      .status-tab-btn {
        padding: 4px 7px;
        font-size: 0.68rem;
        border-radius: 6px;
      }

      /* Prediction Cards - Ultra Compact */
      .pred-card {
        padding: 7px 9px !important;
        gap: 4px !important;
        border-radius: 8px !important;
      }
      .card-store-name {
        font-size: 0.82rem !important;
        line-height: 1.25 !important;
      }
      .score-badge {
        font-size: 0.64rem !important;
        padding: 2px 5px !important;
      }
      .window-badge {
        font-size: 0.64rem !important;
        padding: 2px 5px !important;
      }
      .card-meta-row {
        gap: 4px !important;
        margin-top: 2px !important;
      }
      .chain-badge, .pref-badge, .dist-badge {
        font-size: 0.6rem !important;
        padding: 1px 4px !important;
      }
      .reliability-row {
        margin-top: 2px !important;
        gap: 4px !important;
      }
      .reliability-stars {
        font-size: 0.6rem !important;
      }
      .reliability-label {
        font-size: 0.58rem !important;
      }
      .card-address {
        font-size: 0.64rem !important;
        -webkit-line-clamp: 1 !important;
      }
      .card-action-tip {
        padding: 3px 6px !important;
        margin: 3px 0 2px 0 !important;
        border-radius: 6px !important;
      }
      .tip-icon {
        font-size: 0.72rem !important;
      }
      .tip-text {
        font-size: 0.64rem !important;
        line-height: 1.25 !important;
      }
      .ai-reasons-box {
        padding: 4px 6px !important;
        gap: 2px !important;
        border-radius: 0 4px 4px 0 !important;
      }
      .ai-reason-item {
        font-size: 0.63rem !important;
        line-height: 1.2 !important;
      }
      .card-actions-row {
        gap: 4px !important;
        padding-top: 4px !important;
        margin-top: 2px !important;
      }
      .card-action-btn {
        padding: 4px 5px !important;
        font-size: 0.66rem !important;
        border-radius: 5px !important;
      }
    }

    /* ULTRA COMPACT MOBILE (<400px) */
    @media (max-width: 400px) {
      #radar-header {
        height: 38px !important;
        padding: 0 6px !important;
      }
      .radar-brand .logo-badge {
        display: none !important;
      }
      .radar-title {
        font-size: 0.78rem !important;
        white-space: nowrap !important;
      }
      .radar-subtitle {
        display: none !important;
      }
      .radar-actions .radar-btn {
        padding: 4px 6px !important;
        font-size: 0.72rem !important;
      }
      /* Compact filter dropdowns into a 2x2 grid so they don't monopolize the screen */
      #radar-filters-card,
      .radar-filters-card {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 4px !important;
        padding: 5px 6px !important;
        margin-bottom: 6px !important;
      }
      #radar-filters-card > div,
      .radar-filters-card > div {
        width: 100% !important;
        min-width: 0 !important;
      }
      #radar-filters-card > div.filter-count-badge,
      .radar-filters-card > div.filter-count-badge {
        grid-column: 1 / -1 !important;
        margin-left: 0 !important;
        text-align: right !important;
        font-size: 0.65rem !important;
        padding-top: 2px !important;
      }
      .radar-select {
        width: 100% !important;
        height: 26px !important;
        padding: 2px 4px !important;
        font-size: 0.68rem !important;
        box-sizing: border-box !important;
        text-overflow: ellipsis;
      }
    }
  </style>

  <!-- 1. TOP HEADER -->
  <header id="radar-header">
    <div class="radar-brand">
      <span class="logo-badge">POKÉDAR AI</span>
      <div>
        <div class="radar-title">🎯 Dự Đoán Restock Theo Giờ</div>
        <div class="radar-subtitle">
          <span>Hệ thống phân tích tỉ lệ &amp; chu kỳ restock theo bán kính</span>
        </div>
      </div>
    </div>
    <div class="radar-actions">
      <button type="button" class="radar-btn radar-btn-outline radar-btn-gps" id="btn-gps-toggle" onclick="toggleGPSLocation()" title="Lấy định vị GPS của bạn để đo lường bán kính chính xác">
        <span id="gps-icon">📍</span>
        <span id="gps-label"><span class="hide-sm">Định vị </span>GPS</span>
      </button>
      <button type="button" class="radar-btn radar-btn-primary" onclick="loadPredictions()" title="Tải lại dự đoán mới nhất">
        <span>🔄</span>
        <span class="hide-sm">Làm mới</span>
      </button>
    </div>
  </header>

  <!-- 2. MAIN CONTENT -->
  <main id="radar-container">
    
    <!-- Live Status Banner -->
    <div class="radar-status-banner">
      <div class="status-left">
        <div class="pulse-radar-dot"></div>
        <div>
          <div class="status-info-title" id="banner-status-title">Đang kết nối CSDL và chạy mô hình phân tích...</div>
          <div class="status-info-desc" id="banner-status-desc">Dựa trên 27.000+ bản ghi lịch sử và chu kỳ giao hàng ngày hôm nay</div>
        </div>
      </div>
      <div class="status-badge-time" id="banner-clock-badge">
        <span>🇯🇵</span>
        <span id="live-jst-time">--:-- JST</span>
      </div>
    </div>

    <!-- Radius Selector & Local Rate Measurement Card -->
    <div class="radius-bar-card">
      <div class="radius-header-row">
        <div class="radius-title">
          <span>📍 BÁN KÍNH TỪ VỊ TRÍ CỦA BẠN &amp; ĐO LƯỜNG TỈ LỆ CÓ HÀNG</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <select id="anchor-select" class="radar-select" onchange="onAnchorSelectChange()" style="font-size:0.7rem; padding:4px 8px;">
            <option value="gps">📍 Vị trí GPS của tôi (Tự động)</option>
            <option value="namba" selected>📍 Ga Namba (Osaka)</option>
            <option value="umeda">📍 Ga Umeda / Osaka</option>
            <option value="imamiya">📍 Ga Imamiya (Osaka)</option>
            <option value="ota">📍 Ota Road (Nipponbashi)</option>
            <option value="tennoji">📍 Ga Tennoji (Osaka)</option>
            <option value="shinjuku">📍 Ga Shinjuku (Tokyo)</option>
            <option value="akiba">📍 Ga Akihabara (Tokyo)</option>
            <option value="shibuya">📍 Ga Shibuya (Tokyo)</option>
            <option value="nagoya">📍 Ga Nagoya (Aichi)</option>
            <option value="yokohama">📍 Ga Yokohama (Kanagawa)</option>
          </select>
        </div>
      </div>

      <!-- Quick Radius Chips -->
      <div class="radius-chips-row">
        <button class="radius-chip" data-radius="1" onclick="selectRadiusKm(1)">📍 1 km</button>
        <button class="radius-chip" data-radius="2" onclick="selectRadiusKm(2)">📍 2 km</button>
        <button class="radius-chip active" data-radius="3" onclick="selectRadiusKm(3)">📍 3 km</button>
        <button class="radius-chip" data-radius="5" onclick="selectRadiusKm(5)">📍 5 km</button>
        <button class="radius-chip" data-radius="10" onclick="selectRadiusKm(10)">📍 10 km</button>
        <button class="radius-chip" data-radius="20" onclick="selectRadiusKm(20)">📍 20 km</button>
        <button class="radius-chip" data-radius="" onclick="selectRadiusKm('')">🗾 Toàn vùng</button>
      </div>

      <!-- Local Radius KPIs -->
      <div id="radius-kpi-container" class="radius-kpi-grid" style="display:none;">
        <div class="radius-kpi-box kpi-accent-green">
          <div class="radius-kpi-val" id="kpi-rate-now" style="color:#34d399;">0%</div>
          <div class="radius-kpi-label">Có hàng lúc này</div>
          <div class="radius-kpi-sub" id="kpi-sub-now">0 / 0 quán</div>
        </div>
        <div class="radius-kpi-box kpi-accent-amber">
          <div class="radius-kpi-val" id="kpi-rate-ever" style="color:#fbbf24;">0%</div>
          <div class="radius-kpi-label">Từng về hàng</div>
          <div class="radius-kpi-sub" id="kpi-sub-ever">0 / 0 quán trong bán kính</div>
        </div>
        <div class="radius-kpi-box kpi-accent-purple">
          <div class="radius-kpi-val" id="kpi-peak-hour" style="color:#c084fc; font-size:1.05rem;">--:-- JST</div>
          <div class="radius-kpi-label">Giờ vàng bán kính này</div>
          <div class="radius-kpi-sub" id="kpi-sub-peak">Khung giờ xe tải trả hàng</div>
        </div>
        <div class="radius-kpi-box kpi-accent-red">
          <div class="radius-kpi-val" id="kpi-prime-today" style="color:#f87171;">0 quán</div>
          <div class="radius-kpi-label">Có thể có hàng hôm nay</div>
          <div class="radius-kpi-sub" id="kpi-sub-prime">Xác suất cao (≥70%)</div>
        </div>
      </div>
      <div id="radius-kpi-empty" style="font-size:0.7rem; color:#94a3b8; margin-top:8px; display:block;">
        💡 Chọn bán kính km từ vị trí của bạn để hệ thống đo lường chính xác tỉ lệ có hàng và chu kỳ xe tải riêng trong khu vực bạn!
      </div>
    </div>

    <!-- Timeline & Hour Bar -->
    <div class="timeline-card">
      <div class="timeline-title-row">
        <div class="timeline-title">
          <span id="timeline-card-heading">⏰ KHUNG GIỜ SĂN THẺ THEO LỊCH SỬ</span>
        </div>
        <span style="font-size:0.68rem; color:#94a3b8;" id="timeline-current-dow">Hôm nay</span>
      </div>

      <!-- Quick Preset Windows -->
      <div class="timeline-presets">
        <button class="preset-chip active" data-window="now" onclick="selectTimeWindow('now')">⚡ Giờ này &amp; 2h tới</button>
        <button class="preset-chip" data-window="morning" onclick="selectTimeWindow('morning')">🌅 Sáng (06-11h)</button>
        <button class="preset-chip" data-window="noon" onclick="selectTimeWindow('noon')">☀️ Trưa (11-14h)</button>
        <button class="preset-chip" data-window="afternoon" onclick="selectTimeWindow('afternoon')">🌇 Chiều (14-18h)</button>
        <button class="preset-chip" data-window="evening" onclick="selectTimeWindow('evening')">🌙 Tối (18-24h)</button>
        <button class="preset-chip" data-window="all" onclick="selectTimeWindow('all')">📅 Cả ngày hôm nay</button>
      </div>

      <!-- 24-Hour Scroller -->
      <div style="position:relative;">
        <div class="hour-scroller" id="hour-scroller-bar">
          <!-- Generated by JS -->
        </div>
        <div id="hour-tooltip" class="hour-tooltip" style="display:none;"></div>
      </div>
    </div>

    <!-- Filter & Sort Controls -->
    <div class="radar-filters-card" id="radar-filters-card">
      <div>
        <select id="filter-pref" class="radar-select" onchange="onFilterChange()">
          <option value="all">🗾 Tất cả Tỉnh</option>
          <option value="osaka" selected>📍 Osaka (大阪)</option>
          <option value="tokyo">📍 Tokyo (東京)</option>
          <option value="aichi">📍 Aichi (愛知)</option>
          <option value="kanagawa">📍 Kanagawa (神奈川)</option>
          <option value="gifu">📍 Gifu (岐阜)</option>
          <option value="mie">📍 Mie (三重)</option>
        </select>
      </div>

      <div>
        <select id="filter-chain" class="radar-select" onchange="onFilterChange()">
          <option value="all">🏪 Tất cả chuỗi cửa hàng</option>
          <option value="seven">7-Eleven (セブン)</option>
          <option value="lawson">Lawson (ローソン)</option>
          <option value="familymart">FamilyMart (ファミマ)</option>
          <option value="ministop">Ministop (ミニストップ)</option>
          <option value="geo">GEO (ゲオ)</option>
          <option value="biccamera">Bic Camera (ビックカメラ)</option>
          <option value="yodobashi">Yodobashi (ヨドバシ)</option>
          <option value="aeon">AEON Mall (イオン)</option>
          <option value="specialty">Shop thẻ bài (Card Shop)</option>
        </select>
      </div>

      <div>
        <select id="filter-sort" class="radar-select" onchange="onFilterChange()">
          <option value="distance" selected>📍 Gần tôi nhất (Khoảng cách GPS)</option>
          <option value="score">🔥 Xác suất cao nhất (Score)</option>
          <option value="time">⏰ Giờ restock sớm nhất</option>
        </select>
      </div>

      <div>
        <select id="filter-score" class="radar-select" onchange="onFilterChange()">
          <option value="0">🎯 Mọi độ tin cậy (Tất cả)</option>
          <option value="70">⭐ Khuyên dùng (≥70%)</option>
          <option value="85">🔥 Cực cao (≥85%)</option>
          <option value="stars2">⭐⭐ Độ tin cậy cao (≥ 2 sao)</option>
        </select>
      </div>

      <div class="filter-count-badge">
        Tìm thấy <strong id="res-count-num">0</strong> quán tiềm năng
      </div>
    </div>

    <!-- Real-time 30-min Status Filter Tabs -->
    <div class="status-filter-tabs">
      <button type="button" class="status-tab-btn active" data-status="all" onclick="selectStatusFilter('all')">
        <span>⚡ Tất cả</span>
        <span class="status-tab-badge badge-tab-all" id="tab-count-all">0</span>
      </button>
      <button type="button" class="status-tab-btn tab-green" data-status="green" onclick="selectStatusFilter('green')">
        <span class="pulse-radar-dot" style="width:7px; height:7px;"></span>
        <span>🟢 Chắc chắn có hàng (&lt; 30p)</span>
        <span class="status-tab-badge badge-tab-green" id="tab-count-green">0</span>
      </button>
      <button type="button" class="status-tab-btn tab-truck" data-status="truck" onclick="selectStatusFilter('truck')">
        <span class="pulse-truck-dot" style="width:7px; height:7px;"></span>
        <span>🚚 Xe trên tuyến (&lt; 1.8km)</span>
        <span class="status-tab-badge badge-tab-truck" id="tab-count-truck">0</span>
      </button>
      <button type="button" class="status-tab-btn tab-red" data-status="red" onclick="selectStatusFilter('red')">
        <span>🚨 Vừa hết hàng (&lt; 30p)</span>
        <span class="status-tab-badge badge-tab-red" id="tab-count-red">0</span>
      </button>
      <button type="button" class="status-tab-btn" data-status="predictions" onclick="selectStatusFilter('predictions')">
        <span>🎯 Dự đoán xác suất cao</span>
      </button>
    </div>

    <!-- Prediction Results List -->
    <div id="prediction-list">
      <div class="state-box">
        <div class="spinner"></div>
        <div>Đang phân tích dữ liệu lịch sử và lập mô hình dự đoán...</div>
      </div>
    </div>

    <!-- Algorithm Explainer Section -->
    <div class="algo-explainer-card">
      <div class="algo-explainer-title">
        <span>🤖 Thuật toán PokéDar AI đo lường tỉ lệ &amp; dự đoán như thế nào?</span>
      </div>
      <p style="font-size:0.72rem; color:#94a3b8; line-height:1.45;">
        Hệ thống không chỉ dự đoán chung chung toàn tỉnh, mà bóc tách theo từng <strong>bán kính khoảng cách cụ thể từ vị trí của bạn</strong>. Tỉ lệ có hàng và biểu đồ giờ được tính riêng cho các cửa hàng quanh khu vực bạn sinh sống để đạt độ chính xác thực tế cao nhất:
      </p>
      <div class="algo-weights-grid">
        <div class="algo-weight-box">
          <div class="algo-weight-pct">35%</div>
          <div class="algo-weight-name">Khung giờ &amp; Chuỗi</div>
          <div class="algo-weight-desc">Bayesian Shrinkage theo tuyến xe đặc thù (7-Eleven, Lawson, FM...)</div>
        </div>
        <div class="algo-weight-box">
          <div class="algo-weight-pct">25%</div>
          <div class="algo-weight-name">Phân rã thời gian</div>
          <div class="algo-weight-desc">Ưu tiên cao báo cáo trong 21 ngày gần nhất (Half-life = 21d)</div>
        </div>
        <div class="algo-weight-box">
          <div class="algo-weight-pct">25%</div>
          <div class="algo-weight-name">Tuyến xe &amp; Chu kỳ</div>
          <div class="algo-weight-desc">Nhận diện xe hàng tiếp vận lân cận (&le; 1.8km) &amp; điểm rơi chu kỳ</div>
        </div>
        <div class="algo-weight-box">
          <div class="algo-weight-pct">15%</div>
          <div class="algo-weight-name">Kệ trống &amp; Độ tin cậy</div>
          <div class="algo-weight-desc">Kệ sạch chờ đón đợt mới, lọc quán không bán thẻ Pokémon</div>
        </div>
      </div>
    </div>

  </main>

  <!-- STORE DETAIL MODAL -->
  <div id="pred-store-modal" class="modal-overlay" onclick="if(event.target===this) closePredStoreModal()" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:2000; align-items:center; justify-content:center; padding:16px;">
    <div class="modal-card" style="background:#0f172a; border:1px solid #334155; border-radius:14px; max-width:560px; width:100%; max-height:85vh; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
      <div class="modal-header" style="padding:12px 16px; border-bottom:1px solid #1e293b; display:flex; align-items:center; justify-content:space-between;">
        <h3 id="modal-store-name" style="font-size:0.95rem; font-weight:800; color:#f8fafc; margin:0;">Chi tiết quán</h3>
        <button onclick="closePredStoreModal()" style="background:none; border:none; color:#94a3b8; font-size:1.2rem; cursor:pointer;">✕</button>
      </div>
      <div class="modal-body" id="modal-store-body" style="padding:14px; overflow-y:auto; flex:1; -webkit-overflow-scrolling:touch;">
        <!-- Filled by JS -->
      </div>
    </div>
  </div>

  <!-- AI EXPLANATION MODAL -->
  <div id="ai-explain-modal" class="modal-overlay" onclick="if(event.target===this) closeAiExplainModal()" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:2100; align-items:center; justify-content:center; padding:16px;">
    <div class="modal-card" style="background:#0f172a; border:1px solid #8b5cf6; border-radius:14px; max-width:580px; width:100%; max-height:85vh; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 10px 35px rgba(139,92,246,0.3);">
      <div class="modal-header" style="padding:12px 16px; border-bottom:1px solid #1e293b; display:flex; align-items:center; justify-content:space-between; background:linear-gradient(90deg, rgba(99,102,241,0.15), rgba(168,85,247,0.15));">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.1rem;">✨</span>
          <div>
            <h3 style="font-size:0.92rem; font-weight:800; color:#f8fafc; margin:0;">AI Restock Intelligence</h3>
            <div style="font-size:0.68rem; color:#c084fc; font-weight:700;">Mô hình kết hợp Gemini AI &amp; Thuật toán Xác suất Bayesian</div>
          </div>
        </div>
        <button onclick="closeAiExplainModal()" style="background:none; border:none; color:#94a3b8; font-size:1.2rem; cursor:pointer;">✕</button>
      </div>
      <div class="modal-body" id="ai-explain-modal-body" style="padding:16px; overflow-y:auto; flex:1; -webkit-overflow-scrolling:touch;">
        <!-- Filled by JS -->
      </div>
    </div>
  </div>

  __SHARED_MODALS_HTML__
  __SHARED_FOOTER__

  <script>
    // Known anchor coordinates
    const ANCHOR_COORDS = {
      namba: { lat: 34.6667, lng: 135.5000, name: 'Ga Namba (Osaka)', pref: 'osaka' },
      umeda: { lat: 34.7024, lng: 135.4959, name: 'Ga Umeda (Osaka)', pref: 'osaka' },
      imamiya: { lat: 34.6540, lng: 135.4925, name: 'Ga Imamiya (Osaka)', pref: 'osaka' },
      ota: { lat: 34.6628, lng: 135.5058, name: 'Nipponbashi Ota Road', pref: 'osaka' },
      tennoji: { lat: 34.6472, lng: 135.5140, name: 'Ga Tennoji (Osaka)', pref: 'osaka' },
      shinjuku: { lat: 35.6896, lng: 139.7006, name: 'Ga Shinjuku (Tokyo)', pref: 'tokyo' },
      akiba: { lat: 35.6983, lng: 139.7731, name: 'Ga Akihabara (Tokyo)', pref: 'tokyo' },
      shibuya: { lat: 35.6580, lng: 139.7016, name: 'Ga Shibuya (Tokyo)', pref: 'tokyo' },
      nagoya: { lat: 35.1709, lng: 136.8815, name: 'Ga Nagoya (Aichi)', pref: 'aichi' },
      yokohama: { lat: 35.4658, lng: 139.6227, name: 'Ga Yokohama (Kanagawa)', pref: 'kanagawa' }
    };

    // State
    let currentWindow = 'now';
    let currentTargetHour = null;
    let currentStatusFilter = 'all';
    let selectedRadiusKm = 3.0; // Default: 3km radius
    let userLat = 34.6667; // Default Namba
    let userLng = 135.5000;
    let isGpsActive = false;
    let hourlyDistData = [];

    function selectStatusFilter(status) {
      currentStatusFilter = status;
      document.querySelectorAll('.status-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-status') === status);
      });
      loadPredictions();
    }

    // Attempt to read cached GPS coordinates from local storage
    try {
      const savedLat = localStorage.getItem('user_last_lat');
      const savedLng = localStorage.getItem('user_last_lng');
      if (savedLat && savedLng) {
        userLat = parseFloat(savedLat);
        userLng = parseFloat(savedLng);
        isGpsActive = true;
        const anchorSel = document.getElementById('anchor-select');
        if (anchorSel) anchorSel.value = 'gps';
        updateGpsButtonUI();
      }
    } catch(e) {}

    function updateGpsButtonUI() {
      const btn = document.getElementById('btn-gps-toggle');
      const lbl = document.getElementById('gps-label');
      if (isGpsActive && userLat) {
        btn.classList.add('active');
        lbl.textContent = '📍 Đã có GPS';
      } else {
        btn.classList.remove('active');
        lbl.textContent = 'Định vị GPS';
      }
    }

    function toggleGPSLocation() {
      if (isGpsActive) {
        // Switch to anchor Namba
        isGpsActive = false;
        try {
          localStorage.removeItem('user_last_lat');
          localStorage.removeItem('user_last_lng');
        } catch(e) {}
        updateGpsButtonUI();
        const anchorSel = document.getElementById('anchor-select');
        if (anchorSel) anchorSel.value = 'namba';
        onAnchorSelectChange();
        return;
      }

      if (!navigator.geolocation) {
        alert('Trình duyệt của bạn không hỗ trợ định vị GPS.');
        return;
      }

      const lbl = document.getElementById('gps-label');
      lbl.textContent = '⏳ Đang dò...';

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          isGpsActive = true;
          try {
            localStorage.setItem('user_last_lat', String(userLat));
            localStorage.setItem('user_last_lng', String(userLng));
            fetch('/api/settings', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                notifications: {
                  telegramLocationName: 'Vị trí của bạn (GPS)',
                  telegramLat: userLat,
                  telegramLng: userLng,
                  telegramAutoSyncGps: true
                }
              })
            }).catch(() => {});
          } catch(e) {}
          updateGpsButtonUI();
          const anchorSel = document.getElementById('anchor-select');
          if (anchorSel) anchorSel.value = 'gps';
          loadPredictions();
        },
        (err) => {
          alert('Không thể lấy vị trí GPS. Đang sử dụng điểm neo gần nhất.');
          lbl.textContent = 'Định vị GPS';
          isGpsActive = false;
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    }

    function onAnchorSelectChange() {
      const val = document.getElementById('anchor-select').value;
      if (val === 'gps') {
        toggleGPSLocation();
        return;
      }
      const coords = ANCHOR_COORDS[val];
      if (coords) {
        userLat = coords.lat;
        userLng = coords.lng;
        isGpsActive = false;
        updateGpsButtonUI();
        if (coords.pref) {
          const prefEl = document.getElementById('filter-pref');
          if (prefEl) prefEl.value = coords.pref;
        }
        loadPredictions();
      }
    }

    function selectRadiusKm(r) {
      selectedRadiusKm = r === '' ? null : parseFloat(r);
      document.querySelectorAll('.radius-chip').forEach(btn => {
        const btnR = btn.getAttribute('data-radius');
        btn.classList.toggle('active', (r === '' && btnR === '') || (btnR !== '' && parseFloat(btnR) === selectedRadiusKm));
      });
      loadPredictions();
    }

    function selectTimeWindow(win) {
      currentWindow = win;
      currentTargetHour = null;
      document.querySelectorAll('.preset-chip').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-window') === win);
      });
      document.querySelectorAll('.hour-pill').forEach(pill => {
        pill.classList.remove('active');
      });
      loadPredictions();
    }

    function selectSpecificHour(h) {
      currentTargetHour = h;
      currentWindow = null;
      document.querySelectorAll('.preset-chip').forEach(btn => {
        btn.classList.remove('active');
      });
      document.querySelectorAll('.hour-pill').forEach(pill => {
        pill.classList.toggle('active', parseInt(pill.getAttribute('data-hour')) === h);
      });
      loadPredictions();
    }

    function onFilterChange() {
      loadPredictions();
    }

    async function loadPredictions() {
      const pref = document.getElementById('filter-pref').value;
      const chain = document.getElementById('filter-chain').value;
      const sort = document.getElementById('filter-sort').value;
      const scoreFilter = document.getElementById('filter-score') ? document.getElementById('filter-score').value : '0';

      const listEl = document.getElementById('prediction-list');
      listEl.innerHTML = `
        <div class="state-box" style="grid-column: 1 / -1;">
          <div class="spinner"></div>
          <div>Đang đo lường tỉ lệ có hàng và nạp gợi ý từ mô hình dự đoán PokéDar...</div>
        </div>
      `;

      let minScoreParam = 40;
      if (scoreFilter === '70') minScoreParam = 70;
      else if (scoreFilter === '85') minScoreParam = 85;

      let url = `/api/stats/predictions?pref=${encodeURIComponent(pref)}&chain=${encodeURIComponent(chain)}&sort=${encodeURIComponent(sort)}&status=${encodeURIComponent(currentStatusFilter)}&min_score=${minScoreParam}`;
      if (currentTargetHour !== null) {
        url += `&hour=${currentTargetHour}`;
      } else if (currentWindow) {
        url += `&window=${encodeURIComponent(currentWindow)}`;
      }

      if (userLat !== null && userLng !== null) {
        url += `&user_lat=${userLat}&user_lng=${userLng}`;
        if (selectedRadiusKm !== null) {
          url += `&max_dist_km=${selectedRadiusKm}`;
        }
      }

      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        renderPredictionResults(data);
      } catch (e) {
        listEl.innerHTML = `
          <div class="state-box" style="grid-column: 1 / -1; border-color:#ef4444; color:#fca5a5;">
            <div style="font-size:1.5rem; margin-bottom:8px;">⚠️</div>
            <div>Không thể tải dữ liệu dự đoán: ${e.message}</div>
            <button onclick="loadPredictions()" class="radar-btn radar-btn-primary" style="margin-top:12px;">Thử lại</button>
          </div>
        `;
      }
    }

    function renderPredictionResults(data) {
      // 1. Update clock and header stats
      document.getElementById('live-jst-time').textContent = `${data.server_time_jst || ''} JST`;
      document.getElementById('timeline-current-dow').textContent = `${data.current_dow_name || 'Hôm nay'} (${data.current_dow_jp || ''})`;

      // Filter predictions by selected confidence/score selector
      const scoreFilter = document.getElementById('filter-score') ? document.getElementById('filter-score').value : '0';
      let items = data.predictions || [];
      if (scoreFilter === '70') {
        items = items.filter(p => p.score >= 70);
      } else if (scoreFilter === '85') {
        items = items.filter(p => p.score >= 85);
      } else if (scoreFilter === 'stars2') {
        items = items.filter(p => (p.reliability_stars || 1) >= 2);
      }
      document.getElementById('res-count-num').textContent = items.length;

      // Update tab counter badges
      const green30m = (data.radius_stats && data.radius_stats.green_30m_count !== undefined) ? data.radius_stats.green_30m_count : 0;
      const red30m = (data.radius_stats && data.radius_stats.red_30m_count !== undefined) ? data.radius_stats.red_30m_count : 0;
      const truckCount = (data.radius_stats && data.radius_stats.truck_count !== undefined) ? data.radius_stats.truck_count : 0;
      const tabAllEl = document.getElementById('tab-count-all');
      const tabGreenEl = document.getElementById('tab-count-green');
      const tabTruckEl = document.getElementById('tab-count-truck');
      const tabRedEl = document.getElementById('tab-count-red');
      if (tabAllEl) tabAllEl.textContent = items.length;
      if (tabGreenEl) tabGreenEl.textContent = green30m;
      if (tabTruckEl) tabTruckEl.textContent = truckCount;
      if (tabRedEl) tabRedEl.textContent = red30m;

      // 2. Render Radius KPIs Widget
      renderRadiusStats(data.radius_stats);

      // 3. Update banner text
      const curH = data.current_hour !== undefined ? data.current_hour : 9;
      const curHStr = curH < 10 ? '0' + curH : String(curH);
      const bannerTitle = document.getElementById('banner-status-title');
      const bannerDesc = document.getElementById('banner-status-desc');

      if (curH >= 6 && curH < 11) {
        bannerTitle.textContent = `⚡ Khung giờ vàng Restock sáng (${curHStr}h JST)`;
        bannerDesc.textContent = `Các xe tải giao hàng 7-Eleven, Bic Camera và siêu thị đang trả hàng đợt 1.`;
      } else if (curH >= 11 && curH < 14) {
        bannerTitle.textContent = `☀️ Khung giờ Restock trưa (${curHStr}h JST)`;
        bannerDesc.textContent = `Các cửa hàng FamilyMart & Lawson thường nhận lô hàng bổ sung giờ ăn trưa.`;
      } else if (curH >= 14 && curH < 18) {
        bannerTitle.textContent = `🌇 Giờ cao điểm Restock chiều (${curHStr}h JST - Đỉnh điểm trong ngày!)`;
        bannerDesc.textContent = `Khoản 14h - 16h là khung giờ có số lượt báo cáo có hàng cao nhất lịch sử.`;
      } else if (curH >= 18 && curH < 23) {
        bannerTitle.textContent = `🌙 Khung giờ săn thẻ tối & đêm (${curHStr}h JST)`;
        bannerDesc.textContent = `Các cửa hàng tiện lợi khui kiện hàng đêm và các shop thẻ bài xả hàng tồn.`;
      } else {
        bannerTitle.textContent = `💤 Khung giờ đêm khuya (${curHStr}h JST)`;
        bannerDesc.textContent = `Đang phân tích chu kỳ giao hàng sớm cho buổi sáng hôm nay.`;
      }

      // 4. Render 24-hour scroller
      renderHourScroller(data.hourly_distribution, curH, data.radius_stats);

      // 5. Render prediction cards
      const listEl = document.getElementById('prediction-list');

      if (items.length === 0) {
        listEl.innerHTML = `
          <div class="state-box" style="grid-column: 1 / -1;">
            <div style="font-size:2rem; margin-bottom:10px;">🔍</div>
            <div style="font-size:0.95rem; font-weight:800; color:#f8fafc;">Không tìm thấy cửa hàng phù hợp trong điều kiện lọc này</div>
            <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">Hãy thử nới lỏng bộ lọc xác suất, mở rộng bán kính lên 5km hoặc 10km.</div>
          </div>
        `;
        return;
      }

      listEl.innerHTML = items.map(p => {
        const isFlashGreen = p.flash_mode === 'green';
        const isFlashRed = p.flash_mode === 'red';
        const isTruckRoute = !!p.truck_en_route;
        const isPrime = p.score >= 85;

        let cardClass = 'pred-card';
        if (isTruckRoute && !isFlashGreen && !isFlashRed) {
          cardClass += ' card-truck-route';
        }

        let scoreBadgeClass = 'score-badge';
        let scoreIcon = '🎯';
        let scoreText = `${p.score}% XÁC SUẤT`;
        let windowBadgeHtml = '';

        if (isFlashGreen) {
          cardClass += ' card-flash-green';
          scoreBadgeClass += ' score-badge-flash-green';
          scoreIcon = '⚡🟢';
          scoreText = '100% CÓ HÀNG';
          const minText = p.recent_min_ago !== undefined ? `${p.recent_min_ago}p trước` : 'vừa xong';
          windowBadgeHtml = `
            <span class="window-badge active-now" style="background:#064e3b; border-color:#10b981; color:#6ee7b7; box-shadow:0 0 10px rgba(16,185,129,0.4);">
              <span class="pulse-radar-dot" style="width:7px; height:7px;"></span>
              <span>100% CÓ HÀNG (${minText})</span>
            </span>
          `;
        } else if (isFlashRed) {
          cardClass += ' card-flash-red';
          scoreBadgeClass += ' score-badge-flash-red';
          scoreIcon = '🚨🔴';
          scoreText = '0% - ĐÃ HẾT HÀNG';
          const minText = p.recent_min_ago !== undefined ? `${p.recent_min_ago}p trước` : 'vừa xong';
          windowBadgeHtml = `
            <span class="window-badge" style="background:#7f1d1d; border-color:#ef4444; color:#fca5a5; box-shadow:0 0 10px rgba(239,68,68,0.4);">
              <span>🚨</span>
              <span>VỪA BÁO HẾT (${minText} - ĐỪNG ĐI!)</span>
            </span>
          `;
        } else {
          if (isPrime) cardClass += ' card-prime';
          scoreBadgeClass += isPrime ? ' score-badge-prime' : (p.score >= 70 ? ' score-badge-high' : ' score-badge-medium');
          scoreIcon = isPrime ? '🔥' : (p.score >= 70 ? '⚡' : '🎯');

          const isNowClass = p.is_prime_now ? ' active-now' : '';
          const nowNotice = p.is_prime_now ? '<span style="color:#34d399; font-weight:900;">• Sắp / Đang đến giờ!</span>' : '';
          windowBadgeHtml = `
            <span class="window-badge${isNowClass}">
              <span>⏰</span>
              <span>${p.predicted_window}</span>
              ${nowNotice}
            </span>
          `;
        }

        const truckBadgeHtml = isTruckRoute ? `
          <span class="truck-enroute-badge" title="Tuyến xe hàng lân cận vừa trả hàng quán cùng chuỗi">
            <span class="pulse-truck-dot"></span>
            <span>🚚 Xe trên tuyến (&lt; 1.8km)</span>
          </span>
        ` : '';

        const starsCount = p.reliability_stars || 1;
        const starsStr = '⭐'.repeat(starsCount);
        const relText = p.reliability_text || 'Độ tin cậy';
        const reliabilityHtml = `
          <div class="reliability-row" title="${relText}">
            <span class="reliability-stars">${starsStr}</span>
            <span class="reliability-label">${relText}</span>
          </div>
        `;

        const actionTipHtml = p.action_tip ? `
          <div class="card-action-tip">
            <span class="tip-icon">💡</span>
            <span class="tip-text">${p.action_tip}</span>
          </div>
        ` : '';

        const anchorSel = document.getElementById('anchor-select');
        const anchorName = isGpsActive ? 'bạn' : (anchorSel && anchorSel.options[anchorSel.selectedIndex] ? anchorSel.options[anchorSel.selectedIndex].text.replace(/\\s*\\([^)]*\\)/, '') : 'mốc');
        const travelText = p.travel_time_str || (p.walk_time_min ? `~${p.walk_time_min}p đi bộ` : '');
        const displayDist = p.road_str ? `${p.road_str} (${p.distance_str} thẳng)` : p.distance_str;

        const distHtml = p.distance_str ? `
          <span class="dist-badge" title="Khoảng cách tính từ ${anchorName}: quãng đường đi ${p.road_str || p.distance_str}, đường chim bay ${p.distance_str}">
            📍 ${displayDist} • ${anchorName} ${travelText ? `• ${travelText}` : ''}
          </span>
        ` : '';

        const reasonBoxStyle = isFlashGreen 
          ? ' style="border-left-color:#10b981; background:rgba(6, 78, 59, 0.35);"' 
          : (isFlashRed ? ' style="border-left-color:#ef4444; background:rgba(127, 29, 29, 0.35);"' : '');

        const reasonsHtml = (p.reasons || []).map(r => `
          <div class="ai-reason-item">
            <span>${r}</span>
          </div>
        `).join('');

        const encodedQuery = encodeURIComponent(p.name + ' ' + (p.address || ''));
        const gmapsWalkingUrl = (p.lat && p.lng) 
          ? `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`
          : `https://www.google.com/maps/search/?api=1&query=${encodedQuery}`;

        return `
          <div class="${cardClass}">
            <div class="card-top-row">
              <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span class="${scoreBadgeClass}">
                  <span>${scoreIcon}</span>
                  <span>${scoreText}</span>
                </span>
                ${truckBadgeHtml}
              </div>
              ${windowBadgeHtml}
            </div>

            <div>
              <div class="card-store-name" onclick="openPredStoreModal('${p.store_id}')">
                ${p.name}
              </div>
              <div class="card-meta-row" style="margin-top:4px;">
                <span class="chain-badge">${p.chain_name || p.chain}</span>
                <span class="pref-badge">${p.pref}</span>
                ${distHtml}
              </div>
              ${reliabilityHtml}
            </div>

            <div class="card-address">
              📍 ${p.address || 'Đang cập nhật địa chỉ'}
            </div>

            ${actionTipHtml}

            <div class="ai-reasons-box"${reasonBoxStyle}>
              ${reasonsHtml}
            </div>

            <div class="card-actions-row">
              <button type="button" class="card-action-btn btn-ai-explain" onclick="openAiExplainModal('${p.store_id}')">
                <span>✨ AI Phân tích</span>
              </button>
              <a href="/map?focus=${encodeURIComponent(p.store_id)}" class="card-action-btn btn-map-link">
                <span>🗺️</span>
                <span>Bản đồ</span>
              </a>
              <a href="${gmapsWalkingUrl}" target="_blank" rel="noopener noreferrer" class="card-action-btn btn-gmaps-link">
                <span>🧭</span>
                <span>Chỉ đường</span>
              </a>
              <button type="button" class="card-action-btn btn-hist-link" onclick="openPredStoreModal('${p.store_id}')">
                <span>📜</span>
                <span>Lịch sử</span>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderRadiusStats(radStats) {
      const container = document.getElementById('radius-kpi-container');
      const emptyMsg = document.getElementById('radius-kpi-empty');
      const headingEl = document.getElementById('timeline-card-heading');

      if (!radStats || !radStats.is_active) {
        container.style.display = 'none';
        emptyMsg.style.display = 'block';
        headingEl.textContent = '⏰ KHUNG GIỜ SĂN THẺ TOÀN VÙNG (TỔNG HỢP)';
        return;
      }

      container.style.display = 'grid';
      emptyMsg.style.display = 'none';
      headingEl.textContent = `⏰ KHUNG GIỜ RESTOCK TRONG BÁN KÍNH ${radStats.radius_km} KM QUANH BẠN`;

      // Fill values
      document.getElementById('kpi-rate-now').textContent = `${radStats.in_stock_rate}%`;
      const greenText = (radStats.green_30m_count && radStats.green_30m_count > 0) ? ` • ⚡🟢 ${radStats.green_30m_count} quán < 30p` : '';
      document.getElementById('kpi-sub-now').textContent = `${radStats.in_stock_now} / ${radStats.total_stores} quán có hàng${greenText}`;

      document.getElementById('kpi-rate-ever').textContent = `${radStats.ever_restocked_rate}%`;
      document.getElementById('kpi-sub-ever').textContent = `${radStats.ever_restocked} / ${radStats.total_stores} quán từng về hàng`;

      const peakWindowText = radStats.peak_window || '--:-- JST';
      document.getElementById('kpi-peak-hour').textContent = peakWindowText;
      document.getElementById('kpi-sub-peak').textContent = `Đỉnh điểm ${radStats.peak_hour_count} đợt xe trả hàng`;

      document.getElementById('kpi-prime-today').textContent = `${radStats.prime_stores_today} quán`;
      const redText = (radStats.red_30m_count && radStats.red_30m_count > 0) ? ` • 🚨 ${radStats.red_30m_count} vừa hết` : '';
      document.getElementById('kpi-sub-prime').textContent = `Xác suất cao (≥70%)${redText}`;
    }

    function showHourTooltip(e, h, count, pct, isPrime, isNow) {
      const tt = document.getElementById('hour-tooltip');
      if (!tt) return;
      const nextH = (h + 1) % 24;
      const hStr = (h < 10 ? '0' + h : h) + ':00';
      const nextHStr = (nextH < 10 ? '0' + nextH : nextH) + ':00';
      
      let primeBadge = '';
      if (isPrime) {
        primeBadge = '<div style="color:#fbbf24; font-weight:800; margin-top:3px;">🔥 KHUNG GIỜ VÀNG (Prime Restock Window)</div>';
      } else if (isNow) {
        primeBadge = '<div style="color:#34d399; font-weight:800; margin-top:3px;">⚡ GIỜ HIỆN TẠI ĐANG DIỄN RA</div>';
      }

      let tip = isPrime 
        ? '💡 Tần suất xe giao hàng rất cao. Nên có mặt sớm 15-20 phút tại các combini mục tiêu!'
        : (count > 0 ? '💡 Có thể có đợt trả hàng rải rác nhưng không phải đỉnh điểm.' : '💡 Khung giờ ít biến động theo dữ liệu lịch sử.');

      tt.innerHTML = `
        <div style="font-weight:800; color:#38bdf8; font-size:0.75rem;">⏰ Khung giờ: ${hStr} - ${nextHStr} JST</div>
        ${primeBadge}
        <div style="margin-top:4px; font-size:0.7rem; color:#e2e8f0;">
          📊 Tần suất: <strong>${count}</strong> đợt restock (${pct}% so với giờ đỉnh)
        </div>
        <div style="margin-top:4px; font-size:0.68rem; color:#94a3b8; line-height:1.4;">
          ${tip}
        </div>
      `;

      tt.style.display = 'block';
      const pill = e.currentTarget;
      const scroller = document.getElementById('hour-scroller-bar');
      if (pill && scroller) {
        const left = Math.max(8, Math.min(scroller.offsetWidth - 260, pill.offsetLeft - 80));
        tt.style.left = left + 'px';
        tt.style.top = '-115px';
      }
    }

    function hideHourTooltip() {
      const tt = document.getElementById('hour-tooltip');
      if (tt) tt.style.display = 'none';
    }

    function renderHourScroller(distArray, currentHour, radStats) {
      const scroller = document.getElementById('hour-scroller-bar');
      if (!distArray || distArray.length < 24) return;

      const maxVal = Math.max(...distArray, 1);
      const hoursToDisplay = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23];
      const primeThreshold = Math.max(2, Math.round(maxVal * 0.65));

      scroller.innerHTML = hoursToDisplay.map(h => {
        const count = distArray[h] || 0;
        const pct = Math.max(10, Math.round((count / maxVal) * 100));
        const isNow = h === currentHour;
        const isActive = currentTargetHour === h;
        const isPrime = count >= primeThreshold;
        const nowClass = isNow ? ' is-now' : '';
        const activeClass = isActive ? ' active' : '';
        const primeClass = isPrime ? ' is-prime-window' : '';

        return `
          <div class="hour-pill${nowClass}${activeClass}${primeClass}" 
               data-hour="${h}" 
               onclick="selectSpecificHour(${h})"
               onmouseenter="showHourTooltip(event, ${h}, ${count}, ${pct}, ${isPrime}, ${isNow})"
               onmouseleave="hideHourTooltip()"
               title="${h}:00 JST - ${count} đợt restock ghi nhận${isPrime ? ' (Prime Window)' : ''}">
            <span class="hour-label">${h < 10 ? '0' + h : h}:00</span>
            <div class="hour-bar-wrap">
              <div class="hour-bar-fill" style="width:${pct}%;"></div>
            </div>
            <span class="hour-freq">${count}</span>
          </div>
        `;
      }).join('');
    }

    async function openAiExplainModal(storeId) {
      const modal = document.getElementById('ai-explain-modal');
      const bodyEl = document.getElementById('ai-explain-modal-body');
      if (!modal || !bodyEl) return;

      modal.style.display = 'flex';
      bodyEl.innerHTML = `
        <div style="text-align:center; padding:35px 12px; color:#cbd5e1;">
          <div class="spinner" style="border-top-color:#a855f7; margin-bottom:12px;"></div>
          <div style="font-weight:700; font-size:0.85rem; color:#c084fc;">Đang phân tích thông minh với Gemini &amp; Bayesian Model...</div>
          <div style="font-size:0.72rem; color:#94a3b8; margin-top:4px;">Truy vấn lịch sử restock, nhịp tuyến xe hàng và chu kỳ bổ sung thẻ</div>
        </div>
      `;

      try {
        const res = await fetch(`/api/predictions/${encodeURIComponent(storeId)}/explain`);
        if (!res.ok) {
          throw new Error(`Máy chủ phản hồi mã ${res.status}`);
        }
        const data = await res.json();
        renderAiExplainContent(data);
      } catch (err) {
        bodyEl.innerHTML = `
          <div style="text-align:center; padding:25px 15px; color:#ef4444;">
            <div style="font-size:1.8rem; margin-bottom:8px;">⚠️</div>
            <div style="font-weight:700; font-size:0.85rem;">Không thể nạp phân tích AI lúc này</div>
            <div style="font-size:0.72rem; color:#94a3b8; margin-top:4px;">${err.message || 'Lỗi kết nối'}</div>
          </div>
        `;
      }
    }

    function closeAiExplainModal() {
      const modal = document.getElementById('ai-explain-modal');
      if (modal) modal.style.display = 'none';
    }

    function renderAiExplainContent(data) {
      const bodyEl = document.getElementById('ai-explain-modal-body');
      if (!bodyEl || !data) return;

      const isGemini = data.source === 'gemini';
      const sourceBadge = isGemini 
        ? '<span style="background:linear-gradient(135deg,#6366f1,#a855f7); color:#fff; font-size:0.62rem; font-weight:800; padding:2px 8px; border-radius:999px;">✨ Gemini AI Pro</span>'
        : '<span style="background:#1e293b; border:1px solid #3b82f6; color:#60a5fa; font-size:0.62rem; font-weight:800; padding:2px 8px; border-radius:999px;">⚡ Bayesian Intelligence</span>';

      const reasonsList = (data.reasons || []).map(r => `
        <div style="display:flex; align-items:flex-start; gap:8px; font-size:0.75rem; color:#cbd5e1; margin-bottom:6px;">
          <span style="color:#a855f7; font-weight:800; line-height:1.2;">•</span>
          <span style="line-height:1.4;">${r}</span>
        </div>
      `).join('');

      bodyEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; border-bottom:1px solid #1e293b; padding-bottom:10px;">
          <div>
            <div style="font-size:0.95rem; font-weight:800; color:#f8fafc;">${data.store_name || data.store_id}</div>
            <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">
              <span style="color:#e2e8f0; font-weight:700;">${data.chain || ''}</span>
              ${data.pref ? ` • 📍 ${data.pref}` : ''}
            </div>
          </div>
          <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
            ${sourceBadge}
            <div style="font-size:0.8rem; font-weight:900; color:${data.score >= 70 ? '#34d399' : '#f59e0b'};">
              Điểm: ${data.score}%
            </div>
          </div>
        </div>

        <div style="background:rgba(139, 92, 246, 0.08); border-left:3px solid #8b5cf6; padding:10px 12px; border-radius:6px; margin-bottom:14px;">
          <div style="font-size:0.68rem; font-weight:800; color:#c084fc; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
            💬 Tóm tắt nhận định
          </div>
          <div style="font-size:0.78rem; color:#f1f5f9; line-height:1.5;">
            ${data.summary || 'Chưa có tóm tắt.'}
          </div>
        </div>

        <div style="margin-bottom:14px;">
          <div style="font-size:0.68rem; font-weight:800; color:#38bdf8; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
            📊 Cơ sở phân tích dữ liệu
          </div>
          <div style="background:#0b1120; border:1px solid #1e293b; border-radius:8px; padding:10px 12px;">
            ${reasonsList || '<div style="color:#94a3b8; font-size:0.72rem;">Không có dữ liệu chi tiết</div>'}
          </div>
        </div>

        ${data.action_tip ? `
          <div style="background:rgba(16, 185, 129, 0.1); border:1px solid #059669; border-radius:8px; padding:10px 12px;">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
              <span style="font-size:0.9rem;">💡</span>
              <span style="font-size:0.7rem; font-weight:800; color:#34d399; text-transform:uppercase;">Lời khuyên săn thẻ</span>
            </div>
            <div style="font-size:0.76rem; color:#d1fae5; line-height:1.45;">
              ${data.action_tip}
            </div>
          </div>
        ` : ''}
      `;
    }

    async function openPredStoreModal(storeId) {
      const modal = document.getElementById('pred-store-modal');
      const nameEl = document.getElementById('modal-store-name');
      const bodyEl = document.getElementById('modal-store-body');

      modal.style.display = 'flex';
      nameEl.textContent = 'Đang tải lịch sử quán...';
      bodyEl.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:#94a3b8;">
          <div class="spinner"></div>
          <div>Đang nạp dữ liệu lịch sử từ CSDL SQLite...</div>
        </div>
      `;

      try {
        const res = await fetch(`/api/store_history/${encodeURIComponent(storeId)}`);
        const reports = await res.json();

        if (!reports || reports.length === 0) {
          nameEl.textContent = storeId;
          bodyEl.innerHTML = `<div style="text-align:center; padding:20px; color:#94a3b8;">Chưa có báo cáo chi tiết nào được ghi nhận.</div>`;
          return;
        }

        const first = reports[0];
        nameEl.textContent = first.name || storeId;

        const inStockReports = reports.filter(r => r.status_code === 'i');
        const outStockReports = reports.filter(r => r.status_code === 'o');

        bodyEl.innerHTML = `
          <div style="margin-bottom:12px; font-size:0.75rem; color:#cbd5e1;">
            <div>📍 <strong>Địa chỉ:</strong> ${first.address || 'Chưa rõ'}</div>
            <div style="margin-top:4px;">📊 <strong>Thống kê:</strong> ${reports.length} lần báo cáo • <span style="color:#4ade80;">🟢 ${inStockReports.length} lần có hàng</span> • <span style="color:#f87171;">🔴 ${outStockReports.length} lần hết hàng</span></div>
          </div>
          <div style="border-top:1px solid #1e293b; padding-top:10px;">
            <div style="font-size:0.75rem; font-weight:800; color:#38bdf8; margin-bottom:8px;">NHẬT KÝ BÁO CÁO GẦN ĐÂY:</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${reports.map(r => {
                const isI = r.status_code === 'i';
                const statusColor = isI ? '#22c55e' : (r.status_code === 'o' ? '#ef4444' : '#64748b');
                const statusSymbol = isI ? '🟢' : (r.status_code === 'o' ? '🔴' : '⚪');
                const packsStr = (r.packs && r.packs.length > 0) ? `🃏 ${r.packs.join(', ')}` : '';
                return `
                  <div style="background:#1e293b; border-left:3px solid ${statusColor}; padding:8px 10px; border-radius:4px; font-size:0.72rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                      <span style="font-weight:800; color:${statusColor};">${statusSymbol} ${r.status_label || r.status_code}</span>
                      <span style="color:#94a3b8; font-size:0.65rem;">${r.formatted_time || ''}</span>
                    </div>
                    ${packsStr ? `<div style="margin-top:3px; color:#38bdf8; font-weight:700;">${packsStr}</div>` : ''}
                    ${r.note ? `<div style="margin-top:2px; color:#cbd5e1;">💬 "${r.note}"</div>` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      } catch (e) {
        bodyEl.innerHTML = `<div style="color:#ef4444; padding:20px; text-align:center;">Lỗi nạp lịch sử: ${e.message}</div>`;
      }
    }

    function closePredStoreModal() {
      document.getElementById('pred-store-modal').style.display = 'none';
    }

    // Auto-boot on load with immediate GPS check if available
    document.addEventListener('DOMContentLoaded', () => {
      if (navigator.geolocation && !isGpsActive) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            userLat = pos.coords.latitude;
            userLng = pos.coords.longitude;
            isGpsActive = true;
            try {
              localStorage.setItem('user_last_lat', String(userLat));
              localStorage.setItem('user_last_lng', String(userLng));
              fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  notifications: {
                    telegramLocationName: 'Vị trí của bạn (GPS)',
                    telegramLat: userLat,
                    telegramLng: userLng,
                    telegramAutoSyncGps: true
                  }
                })
              }).catch(() => {});
            } catch(e) {}
            updateGpsButtonUI();
            const anchorSel = document.getElementById('anchor-select');
            if (anchorSel) anchorSel.value = 'gps';
            loadPredictions();
          },
          (err) => {
            loadPredictions();
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
      } else {
        loadPredictions();
      }
    });
  </script>
</body>
</html>"""

    return html.replace("__SHARED_HEAD__", shared_head)\
               .replace("__SHARED_BASE_CSS__", SHARED_BASE_CSS)\
               .replace("__SHARED_MODALS_HTML__", SHARED_MODALS_HTML)\
               .replace("__SHARED_FOOTER__", shared_footer)
