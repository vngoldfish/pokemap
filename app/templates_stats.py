"""
HTML Template and Page Renderer for PokéMap Admin & Analytics Dashboard
Routes: GET /thongke, GET /admin, GET /quanly
Comprehensive Store History, Report Counts, Analytics & KPIs.
"""

def render_thongke_page() -> str:
    from .templates import get_shared_head, SHARED_BASE_CSS, render_shared_footer, SHARED_MODALS_HTML

    shared_head = get_shared_head("Quản lý Lịch sử & Thống kê - PokéMap Tracker", include_leaflet=False)
    shared_footer = render_shared_footer("thongke")

    html = """__SHARED_HEAD__
__SHARED_BASE_CSS__
  <style>
    /* CUSTOM STYLES FOR STATS & ADMIN DASHBOARD */
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

    #stats-top-header {
      height: 52px;
      background: #0f172a;
      border-bottom: 1px solid #1e293b;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      flex-shrink: 0;
      z-index: 100;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }

    .stats-header-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: #ffffff;
    }
    .stats-header-brand .logo-badge {
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      color: #fff;
      font-size: 0.75rem;
      font-weight: 800;
      padding: 4px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }
    .stats-header-title {
      font-size: 1rem;
      font-weight: 800;
      color: #f8fafc;
      letter-spacing: -0.3px;
    }

    .stats-header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .stats-btn {
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      border: 1px solid transparent;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .stats-btn-primary {
      background: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }
    .stats-btn-primary:hover {
      background: #1d4ed8;
    }
    .stats-btn-outline {
      background: #1e293b;
      color: #cbd5e1;
      border-color: #334155;
    }
    .stats-btn-outline:hover {
      background: #334155;
      color: #ffffff;
    }

    /* SUB TABS BAR */
    #stats-nav-tabs {
      background: #0f172a;
      border-bottom: 1px solid #1e293b;
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 0 16px;
      overflow-x: auto;
      flex-shrink: 0;
      scrollbar-width: none;
    }
    #stats-nav-tabs::-webkit-scrollbar { display: none; }

    .nav-tab-btn {
      padding: 11px 14px;
      font-size: 0.82rem;
      font-weight: 700;
      color: #94a3b8;
      background: none;
      border: none;
      border-bottom: 3px solid transparent;
      cursor: pointer;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .nav-tab-btn:hover {
      color: #e2e8f0;
    }
    .nav-tab-btn.active {
      color: #38bdf8;
      border-bottom-color: #38bdf8;
    }

    /* MAIN SCROLLABLE WRAPPER */
    #stats-body-wrapper {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      max-width: 1280px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
      -webkit-overflow-scrolling: touch;
    }

    /* KPI CARDS GRID */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .kpi-card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);
    }
    .kpi-card .kpi-label {
      font-size: 0.72rem;
      font-weight: 700;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .kpi-card .kpi-val {
      font-size: 1.6rem;
      font-weight: 900;
      color: #ffffff;
      line-height: 1.2;
    }
    .kpi-card .kpi-sub {
      font-size: 0.7rem;
      color: #64748b;
      font-weight: 600;
    }

    /* PANE CONTAINERS */
    .stats-pane {
      display: none;
    }
    .stats-pane.active {
      display: block;
    }

    /* CONTENT PANELS / CARDS */
    .panel-card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 20px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.25);
    }
    .panel-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .panel-title {
      font-size: 0.95rem;
      font-weight: 800;
      color: #f8fafc;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .panel-sub {
      font-size: 0.72rem;
      color: #94a3b8;
      font-weight: 500;
    }

    /* FILTER TOOLBAR */
    .filter-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 14px;
      background: #0f172a;
      padding: 10px 14px;
      border-radius: 10px;
      border: 1px solid #334155;
    }
    .filter-input, .filter-select {
      background: #1e293b;
      border: 1px solid #475569;
      color: #f1f5f9;
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      outline: none;
    }
    .filter-input:focus, .filter-select:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 0 2px rgba(56,189,248,0.2);
    }

    /* MODERN TABLES */
    .stats-table-wrapper {
      width: 100%;
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid #334155;
    }
    .stats-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
      text-align: left;
      white-space: nowrap;
    }
    .stats-table th {
      background: #0f172a;
      color: #94a3b8;
      font-weight: 700;
      padding: 10px 14px;
      border-bottom: 1px solid #334155;
      font-size: 0.73rem;
      letter-spacing: 0.3px;
    }
    .stats-table td {
      padding: 10px 14px;
      border-bottom: 1px solid #273549;
      color: #cbd5e1;
      vertical-align: middle;
    }
    .stats-table tr:hover td {
      background: #24344d;
    }

    /* STATUS BADGES */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 800;
    }
    .badge-in {
      background: rgba(34, 197, 94, 0.15);
      color: #4ade80;
      border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .badge-out {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-none {
      background: rgba(148, 163, 184, 0.15);
      color: #94a3b8;
      border: 1px solid rgba(148, 163, 184, 0.3);
    }
    .badge-pack {
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.68rem;
      font-weight: 700;
      margin-right: 4px;
      display: inline-block;
    }

    /* INTERACTIVE SVG CHART & 2D HEATMAP CSS (0ms LOAD, 100% OFFLINE) */
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-bottom: 20px;
    }
    .interactive-chart-container {
      position: relative;
      width: 100%;
      height: 220px;
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 10px;
      padding: 10px 8px 6px;
      box-sizing: border-box;
      margin-bottom: 8px;
    }
    .svg-chart {
      width: 100%;
      height: 100%;
      overflow: visible;
      display: block;
    }
    .svg-grid-line {
      stroke: #1e293b;
      stroke-dasharray: 4 4;
      stroke-width: 1;
    }
    .svg-axis-text {
      fill: #64748b;
      font-size: 10.5px;
      font-weight: 700;
      text-anchor: middle;
      font-family: inherit;
    }
    .svg-bar-total {
      fill: #1e293b;
      rx: 3;
      ry: 3;
      transition: all 0.3s ease;
    }
    .svg-bar-instock {
      fill: url(#instock-grad);
      rx: 3;
      ry: 3;
      transition: all 0.3s ease;
      cursor: pointer;
    }
    .svg-bar-instock.peak {
      fill: url(#peak-grad);
      filter: drop-shadow(0 0 5px rgba(245, 158, 11, 0.6));
    }
    .svg-col-hover-rect {
      fill: transparent;
      cursor: pointer;
      transition: fill 0.15s ease;
    }
    .svg-col-hover-rect:hover {
      fill: rgba(56, 189, 248, 0.12);
    }

    /* FLOATING TOOLTIPS */
    .chart-tooltip {
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

    /* CHAIN & RADIUS CHIPS */
    .chain-chip, .radius-chip {
      background: #0f172a;
      border: 1px solid #334155;
      color: #cbd5e1;
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 0.73rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .chain-chip:hover, .radius-chip:hover {
      background: #1e293b;
      color: #38bdf8;
      border-color: #38bdf8;
    }
    .chain-chip.active, .radius-chip.active {
      background: rgba(37, 99, 235, 0.25);
      border-color: #3b82f6;
      color: #60a5fa;
      box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
    }

    /* 2D HEATMAP MATRIX */
    .heatmap-scroll-wrapper {
      width: 100%;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      position: relative;
      border-radius: 8px;
      border: 1px solid #1e293b;
      background: #0f172a;
      padding: 10px;
      box-sizing: border-box;
    }
    .heatmap-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 4px;
      min-width: 720px;
      font-size: 0.72rem;
    }
    .heatmap-table th {
      background: #090e17;
      color: #94a3b8;
      font-size: 0.65rem;
      padding: 6px 2px;
      text-align: center;
      font-weight: 700;
      border-radius: 4px;
    }
    .heatmap-row-label {
      background: #1e293b;
      color: #f1f5f9;
      font-weight: 800;
      padding: 7px 10px;
      border-radius: 6px;
      white-space: nowrap;
      position: sticky;
      left: 0;
      z-index: 2;
      border: 1px solid #334155;
      font-size: 0.75rem;
    }
    .heatmap-cell {
      text-align: center;
      border-radius: 4px;
      padding: 6px 0;
      color: #cbd5e1;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
      user-select: none;
      position: relative;
      border: 1px solid transparent;
      min-width: 24px;
    }
    .heatmap-cell:hover {
      transform: scale(1.18);
      z-index: 10;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.7);
      outline: 1px solid #38bdf8;
    }
    .heatmap-cell.golden-cell {
      border: 1px solid #f59e0b !important;
      box-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
      color: #ffffff;
      font-weight: 900;
    }
    .dist-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: #38bdf8;
      font-size: 0.68rem;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
    }

    /* PROGRESS BARS */
    .progress-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
      font-size: 0.78rem;
    }
    .progress-label {
      width: 110px;
      font-weight: 700;
      color: #cbd5e1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .progress-track {
      flex: 1;
      height: 9px;
      background: #0f172a;
      border-radius: 5px;
      overflow: hidden;
      border: 1px solid #334155;
    }
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #38bdf8);
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .progress-val {
      width: 60px;
      text-align: right;
      font-weight: 800;
      color: #94a3b8;
      font-size: 0.75rem;
    }

    /* PAGINATION */
    .pagination-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .page-btn {
      padding: 6px 12px;
      background: #0f172a;
      border: 1px solid #334155;
      color: #cbd5e1;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s;
    }
    .page-btn:hover:not(:disabled) {
      background: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }
    .page-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    /* DETAIL MODAL */
    .stats-modal {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
      backdrop-filter: blur(4px);
      z-index: 2000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .stats-modal.open {
      display: flex;
    }
    .stats-modal-card {
      background: #1e293b;
      border: 1px solid #475569;
      border-radius: 14px;
      width: 100%;
      max-width: 680px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      overflow: hidden;
    }
    .stats-modal-header {
      background: #0f172a;
      padding: 14px 18px;
      border-bottom: 1px solid #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .stats-modal-body {
      padding: 16px;
      overflow-y: auto;
      flex: 1;
    }

    /* COMPREHENSIVE MOBILE OPTIMIZATIONS (ULTRA-COMPACT DENSE VIEW) */
    @media (max-width: 640px) {
      #stats-top-header {
        height: 40px;
        padding: 0 8px;
      }
      .stats-header-brand {
        gap: 5px;
        min-width: 0;
        flex: 1;
        overflow: hidden;
      }
      .stats-header-brand .logo-badge {
        font-size: 0.62rem;
        padding: 2px 5px;
        border-radius: 4px;
        flex-shrink: 0;
      }
      .stats-header-title {
        font-size: 0.76rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .stats-header-actions {
        gap: 3px;
        flex-shrink: 0;
      }
      .stats-btn {
        padding: 4px 6px;
        font-size: 0.68rem;
        border-radius: 5px;
      }
      .hide-sm {
        display: none !important;
      }

      /* Navigation Tabs */
      #stats-nav-tabs {
        padding: 0 6px;
        gap: 2px;
      }
      .nav-tab-btn {
        padding: 6px 8px;
        font-size: 0.72rem;
        gap: 3px;
      }

      /* KPI Cards 2x2 Grid - Ultra Compact */
      #stats-body-wrapper {
        padding: 6px 6px 20px 6px;
      }
      .kpi-grid {
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 5px !important;
        margin-bottom: 8px !important;
      }
      .kpi-card {
        padding: 6px 8px !important;
        border-radius: 8px !important;
        gap: 1px !important;
      }
      .kpi-card .kpi-label {
        font-size: 0.58rem !important;
        font-weight: 700 !important;
      }
      .kpi-card .kpi-val {
        font-size: 1.05rem !important;
        font-weight: 900 !important;
        line-height: 1.15 !important;
      }
      .kpi-card .kpi-sub {
        font-size: 0.55rem !important;
        margin-top: 1px !important;
      }

      /* Panels */
      .panel-card {
        padding: 8px 9px !important;
        border-radius: 8px !important;
        margin-bottom: 8px !important;
      }
      .panel-title {
        font-size: 0.78rem !important;
        gap: 5px !important;
      }
      .panel-sub {
        display: none !important;
      }
      .panel-card-header {
        margin-bottom: 6px !important;
        gap: 4px !important;
      }

      /* Filter Toolbar - Compact 2-column inline grid */
      .filter-bar {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 4px !important;
        padding: 5px 6px !important;
        margin-bottom: 8px !important;
        border-radius: 6px !important;
      }
      .filter-input {
        grid-column: 1 / -1 !important;
        font-size: 0.72rem !important;
        padding: 4px 7px !important;
        height: 28px !important;
        width: 100% !important;
        box-sizing: border-box !important;
      }
      .filter-select,
      .filter-bar select,
      .filter-bar select.filter-select,
      .filter-bar select.filter-input {
        grid-column: auto !important;
        font-size: 0.7rem !important;
        padding: 3px 6px !important;
        height: 28px !important;
        width: 100% !important;
        box-sizing: border-box !important;
      }

      /* Table Mobile Card Wrap (<640px) */
      .stats-table-wrapper {
        overflow-x: auto;
      }
      #leaderboard-table thead,
      #history-table thead {
        display: none !important;
      }
      #leaderboard-table,
      #leaderboard-table tbody,
      #history-table,
      #history-tbody {
        display: block !important;
        width: 100% !important;
      }
      #leaderboard-table tbody tr,
      #history-tbody tr {
        display: block !important;
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        padding: 10px 12px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
      }
      #leaderboard-table tbody td,
      #history-tbody td {
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        padding: 5px 0 !important;
        border: none !important;
        border-bottom: 1px solid rgba(51, 65, 85, 0.4) !important;
        font-size: 0.78rem !important;
        white-space: normal !important;
        text-align: right !important;
      }
      #leaderboard-table tbody td::before,
      #history-tbody td::before {
        content: attr(data-label);
        font-size: 0.72rem;
        font-weight: 700;
        color: #94a3b8;
        text-align: left;
        margin-right: 8px;
        flex-shrink: 0;
      }
      #leaderboard-table tbody td:nth-child(2),
      #history-tbody td:nth-child(2) {
        flex-direction: column !important;
        align-items: flex-start !important;
        text-align: left !important;
      }
      #leaderboard-table tbody td:nth-child(2)::before,
      #history-tbody td:nth-child(2)::before {
        margin-bottom: 4px;
      }
      #leaderboard-table tbody td:last-child,
      #history-tbody td:last-child {
        border-bottom: none !important;
        padding-top: 8px !important;
        justify-content: flex-end !important;
      }
      #leaderboard-table .stats-btn,
      #history-tbody .stats-btn {
        padding: 6px 12px !important;
        min-height: 32px !important;
        font-size: 0.78rem !important;
      }
      .stats-table .badge {
        padding: 2px 6px !important;
        font-size: 0.68rem !important;
      }
      
      /* Progress bars */
      .chart-grid {
        gap: 8px !important;
        margin-bottom: 10px !important;
      }
      .hourly-bar-container {
        height: 120px !important;
        padding-bottom: 18px !important;
      }
      .progress-label {
        width: 75px !important;
        font-size: 0.68rem !important;
      }
      .progress-val {
        width: 40px !important;
        font-size: 0.66rem !important;
      }
      .pagination-bar {
        margin-top: 8px !important;
        gap: 6px !important;
      }
      .page-btn {
        padding: 4px 8px !important;
        font-size: 0.7rem !important;
      }

      /* Detail Modal */
      .stats-modal {
        padding: 6px !important;
      }
      .stats-modal-card {
        max-height: 94vh !important;
        border-radius: 8px !important;
      }
      .stats-modal-header {
        padding: 8px 10px !important;
      }
      .stats-modal-body {
        padding: 8px 10px !important;
      }
    }

    /* ULTRA COMPACT MOBILE (<400px) */
    @media (max-width: 400px) {
      #stats-top-header {
        height: 38px !important;
        padding: 0 6px !important;
      }
      .stats-header-brand {
        gap: 4px !important;
      }
      .stats-header-brand .logo-badge {
        display: none !important; /* Hide badge on <400px to give ample space for title */
      }
      .stats-header-title {
        font-size: 0.78rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.2px !important;
        white-space: nowrap !important;
      }
      .stats-header-actions {
        gap: 3px !important;
      }
      .stats-header-actions .stats-btn {
        padding: 4px 6px !important;
        font-size: 0.72rem !important;
      }
    }
  </style>
</head>
<body>

  <!-- TOP HEADER -->
  <header id="stats-top-header">
    <a href="/thongke" class="stats-header-brand">
      <div class="logo-badge">POKÉMAP</div>
      <div class="stats-header-title">📊 Quản Lý &amp; Thống Kê</div>
    </a>
    <div class="stats-header-actions">
      <button class="stats-btn stats-btn-outline" onclick="loadAllStats()" title="Làm mới số liệu">
        <span>🔄</span> <span class="hide-sm">Làm mới</span>
      </button>
      <a href="/api/stats/export_csv" class="stats-btn stats-btn-primary" target="_blank" title="Tải file CSV lịch sử">
        <span>📥</span> <span class="hide-sm">Xuất CSV</span>
      </a>
      <a href="/map" class="stats-btn stats-btn-outline" title="Quay lại Bản đồ">
        <span>🗺️</span> <span class="hide-sm">Bản đồ</span>
      </a>
    </div>
  </header>

  <!-- SUB NAVIGATION TABS -->
  <nav id="stats-nav-tabs">
    <button class="nav-tab-btn active" id="tab-leaderboard-btn" onclick="switchStatsTab('leaderboard')">
      <span>🏆</span> <span>BXH Báo Cáo</span>
    </button>
    <button class="nav-tab-btn" id="tab-history-btn" onclick="switchStatsTab('history')">
      <span>📜</span> <span>Nhật Ký Lịch Sử</span>
    </button>
    <button class="nav-tab-btn" id="tab-analytics-btn" onclick="switchStatsTab('analytics')">
      <span>📈</span> <span>Biểu Đồ Phân Tích</span>
    </button>
    <button class="nav-tab-btn" id="tab-db-btn" onclick="switchStatsTab('db')">
      <span>⚡</span> <span>Hệ Thống &amp; CSDL</span>
    </button>
  </nav>

  <!-- MAIN SCROLLABLE CONTENT -->
  <main id="stats-body-wrapper">

    <!-- KPI OVERVIEW CARDS -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">
          <span>🏪 Tổng Cửa Hàng</span>
          <span>🇯🇵</span>
        </div>
        <div class="kpi-val" id="kpi-total-stores">--</div>
        <div class="kpi-sub">Bao phủ toàn bộ nước Nhật</div>
      </div>

      <div class="kpi-card" style="border-color:#16a34a;">
        <div class="kpi-label">
          <span style="color:#4ade80;">🟢 Đang Có Hàng</span>
          <span>⚡</span>
        </div>
        <div class="kpi-val" style="color:#4ade80;" id="kpi-in-stock">--</div>
        <div class="kpi-sub" id="kpi-in-rate">Tỷ lệ: --%</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">
          <span>📝 Lượt Báo Cáo CSDL</span>
          <span>💾</span>
        </div>
        <div class="kpi-val" id="kpi-total-reports">--</div>
        <div class="kpi-sub" id="kpi-active-stores">Ghi nhận: -- quán</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">
          <span>⏰ Báo Cáo Mới Nhất</span>
          <span>JST</span>
        </div>
        <div class="kpi-val" style="font-size:1.15rem;" id="kpi-latest-time">--</div>
        <div class="kpi-sub" id="kpi-latest-ago">Tự động nạp mỗi 15s</div>
      </div>
    </div>

    <!-- PANE 1: LEADERBOARD (BXH CỬA HÀNG) -->
    <section id="pane-leaderboard" class="stats-pane active">
      <div class="panel-card">
        <div class="panel-card-header">
          <div>
            <div class="panel-title">🏆 Bảng Xếp Hạng Cửa Hàng Được Báo Cáo Nhiều Nhất</div>
            <div class="panel-sub">Top những điểm nóng restock thẻ Pokémon bài có nhiều người săn và gửi thông tin nhất</div>
          </div>
          <div style="font-size:0.75rem; color:#94a3b8; font-weight:700;">
            Hiển thị Top <span id="lb-count-display">50</span> điểm nóng
          </div>
        </div>

        <!-- Filter Toolbar -->
        <div class="filter-bar">
          <input type="text" class="filter-input" id="lb-search" placeholder="🔍 Lọc nhanh tên / địa chỉ..." oninput="filterLeaderboardClient()" style="min-width:200px; flex:1;">
          <select class="filter-select" id="lb-pref-select" onchange="fetchLeaderboard()">
            <option value="">📍 Tất cả Tỉnh thành</option>
            <option value="osaka">大阪 Osaka</option>
            <option value="tokyo">東京 Tokyo</option>
            <option value="kanagawa">神奈川 Kanagawa</option>
            <option value="aichi">愛知 Aichi</option>
            <option value="chiba">千葉 Chiba</option>
            <option value="gifu">岐阜 Gifu</option>
            <option value="mie">三重 Mie</option>
          </select>
          <select class="filter-select" id="lb-chain-select" onchange="fetchLeaderboard()">
            <option value="">🏢 Tất cả Chuỗi</option>
            <option value="seven">7-Eleven</option>
            <option value="lawson">Lawson</option>
            <option value="familymart">FamilyMart</option>
            <option value="ministop">Ministop</option>
            <option value="specialty">Shop Thẻ Bài</option>
            <option value="joshin">Joshin</option>
            <option value="aeon">AEON</option>
            <option value="yodobashi">Yodobashi Camera</option>
            <option value="biccamera">Bic Camera</option>
          </select>
          <select class="filter-select" id="lb-anchor-select" onchange="onLbAnchorChange()">
            <option value="all">🗾 Tất cả (Không đo khoảng cách)</option>
            <option value="gps">📍 Vị trí GPS của tôi (Browser GPS)</option>
            <option value="namba">📍 Ga Namba (Osaka)</option>
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
          <select class="filter-select" id="lb-sort-select" onchange="filterLeaderboardClient()">
            <option value="reports">🔥 Sắp xếp: Nhiều báo cáo nhất</option>
            <option value="rate">🟢 Sắp xếp: Tỉ lệ có hàng cao nhất</option>
            <option value="distance">📍 Sắp xếp: Gần vị trí neo nhất</option>
          </select>
        </div>

        <!-- Radius Filter Chips Row -->
        <div class="radius-chips-bar" id="lb-radius-chips-bar" style="display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-bottom:12px; padding:0 4px;">
          <span style="font-size:0.75rem; color:#94a3b8; font-weight:700;">📍 Bán kính lọc:</span>
          <button type="button" class="radius-chip active" data-radius="" onclick="selectLbRadius('')">Tất cả</button>
          <button type="button" class="radius-chip" data-radius="1" onclick="selectLbRadius(1)">1 km</button>
          <button type="button" class="radius-chip" data-radius="2" onclick="selectLbRadius(2)">2 km</button>
          <button type="button" class="radius-chip" data-radius="3" onclick="selectLbRadius(3)">3 km</button>
          <button type="button" class="radius-chip" data-radius="5" onclick="selectLbRadius(5)">5 km</button>
          <button type="button" class="radius-chip" data-radius="10" onclick="selectLbRadius(10)">10 km</button>
        </div>

        <!-- Table -->
        <div class="stats-table-wrapper">
          <table class="stats-table" id="leaderboard-table">
            <thead>
              <tr>
                <th style="width:40px;">#</th>
                <th>Cửa Hàng</th>
                <th>Khu Vực &amp; Khoảng Cách</th>
                <th>Chuỗi</th>
                <th style="text-align:center;">Tổng Báo Cáo</th>
                <th>Tỷ Lệ Có Hàng</th>
                <th>Lần Cuối Báo Cáo (JST)</th>
                <th style="text-align:center;">Thao Tác</th>
              </tr>
            </thead>
            <tbody id="leaderboard-tbody">
              <tr><td colspan="8" style="text-align:center; padding:30px; color:#64748b;">Đang tải dữ liệu xếp hạng...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- PANE 2: HISTORY LOGS (NHẬT KÝ LỊCH SỬ TOÀN DIỆN) -->
    <section id="pane-history" class="stats-pane">
      <div class="panel-card">
        <div class="panel-card-header">
          <div>
            <div class="panel-title">📜 Tra Cứu Nhật Ký Báo Cáo Toàn Diện</div>
            <div class="panel-sub">Xem chi tiết toàn bộ các lần restock, ghi chú, loại pack và người gửi tin trong CSDL</div>
          </div>
          <div id="hist-total-display" style="font-size:0.78rem; color:#38bdf8; font-weight:800;">
            Đang tải...
          </div>
        </div>

        <!-- Filter Bar -->
        <div class="filter-bar">
          <input type="text" class="filter-input" id="hist-q" placeholder="🔍 Tên quán, địa chỉ, ghi chú, ID..." style="min-width:220px; flex:1;" onkeydown="if(event.key==='Enter') fetchHistoryPage(1)">
          <select class="filter-select" id="hist-status" onchange="fetchHistoryPage(1)">
            <option value="">🎯 Tất cả Trạng thái</option>
            <option value="i">🟢 Có hàng (In Stock)</option>
            <option value="o">🔴 Hết hàng (Out of Stock)</option>
            <option value="n">⚪ Không bán thẻ (Not Handled)</option>
          </select>
          <select class="filter-select" id="hist-pref" onchange="fetchHistoryPage(1)">
            <option value="">📍 Tất cả Tỉnh</option>
            <option value="osaka">Osaka</option>
            <option value="tokyo">Tokyo</option>
            <option value="kanagawa">Kanagawa</option>
            <option value="aichi">Aichi</option>
            <option value="chiba">Chiba</option>
            <option value="gifu">Gifu</option>
            <option value="mie">Mie</option>
          </select>
          <select class="filter-select" id="hist-chain" onchange="fetchHistoryPage(1)">
            <option value="">🏢 Tất cả Chuỗi</option>
            <option value="seven">7-Eleven</option>
            <option value="lawson">Lawson</option>
            <option value="familymart">FamilyMart</option>
            <option value="ministop">Ministop</option>
            <option value="specialty">Card Shop</option>
            <option value="joshin">Joshin</option>
            <option value="aeon">AEON</option>
          </select>
          <select class="filter-select" id="hist-anchor-select" onchange="onHistAnchorChange()">
            <option value="all">🗾 Mọi khoảng cách</option>
            <option value="gps">📍 GPS của tôi</option>
            <option value="namba">📍 Ga Namba</option>
            <option value="umeda">📍 Ga Umeda</option>
            <option value="imamiya">📍 Ga Imamiya</option>
            <option value="ota">📍 Ota Road</option>
            <option value="shinjuku">📍 Ga Shinjuku</option>
            <option value="akiba">📍 Ga Akiba</option>
            <option value="nagoya">📍 Ga Nagoya</option>
          </select>
          <button class="stats-btn stats-btn-primary" onclick="fetchHistoryPage(1)">
            <span>🔍</span> <span>Tìm kiếm</span>
          </button>
        </div>

        <!-- History Radius Filter Chips -->
        <div class="radius-chips-bar" id="hist-radius-chips-bar" style="display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-bottom:12px; padding:0 4px;">
          <span style="font-size:0.75rem; color:#94a3b8; font-weight:700;">📍 Bán kính:</span>
          <button type="button" class="radius-chip active" data-radius="" onclick="selectHistRadius('')">Tất cả</button>
          <button type="button" class="radius-chip" data-radius="2" onclick="selectHistRadius(2)">2 km</button>
          <button type="button" class="radius-chip" data-radius="5" onclick="selectHistRadius(5)">5 km</button>
          <button type="button" class="radius-chip" data-radius="10" onclick="selectHistRadius(10)">10 km</button>
        </div>

        <!-- Table -->
        <div class="stats-table-wrapper">
          <table class="stats-table">
            <thead>
              <tr>
                <th>Thời Gian (JST)</th>
                <th>Cửa Hàng &amp; Địa Chỉ</th>
                <th>Trạng Thái</th>
                <th>Packs Thẻ Kèm Theo</th>
                <th>Ghi Chú Người Dùng</th>
                <th>Người Báo Cáo</th>
                <th style="text-align:center;">Thao Tác</th>
              </tr>
            </thead>
            <tbody id="history-tbody">
              <tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">Đang tải nhật ký...</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div class="pagination-bar">
          <div style="font-size:0.75rem; color:#94a3b8;" id="hist-page-info">Trang 1 / 1</div>
          <div style="display:flex; gap:6px;">
            <button class="page-btn" id="btn-prev-page" onclick="prevHistoryPage()" disabled>◀ Trang trước</button>
            <button class="page-btn" id="btn-next-page" onclick="nextHistoryPage()">Trang sau ▶</button>
          </div>
        </div>
      </div>
    </section>

    <!-- PANE 3: ANALYTICS (BIỂU ĐỒ & PHÂN TÍCH) -->
    <section id="pane-analytics" class="stats-pane">
      <!-- 1. Interactive SVG Hourly Peak Chart -->
      <div class="panel-card" id="hourly-chart-card">
        <div class="panel-card-header">
          <div>
            <div class="panel-title">📊 Biểu Đồ Trực Quan Tương Tác Khung Giờ Restock (24h JST)</div>
            <div class="panel-sub">Thống kê tần suất và tỷ lệ có hàng theo từng giờ, phân tích so sánh chi tiết theo chuỗi combini</div>
          </div>
          <div class="chart-golden-badge" style="font-size:0.75rem; color:#f59e0b; font-weight:800; background:rgba(245,158,11,0.15); border:1px solid #f59e0b; padding:4px 10px; border-radius:8px;">
            🔥 Giờ cao điểm: 09:00 - 15:00 JST
          </div>
        </div>

        <!-- Interactive Combini Chain Toggle Chips -->
        <div class="chart-chain-selector" style="display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin-bottom:12px;">
          <span style="font-size:0.75rem; color:#94a3b8; font-weight:700;">🏢 So sánh chuỗi:</span>
          <button type="button" class="chain-chip active" data-chain="" onclick="selectChartChain('')">🌐 Tất cả chuỗi</button>
          <button type="button" class="chain-chip" data-chain="seven" onclick="selectChartChain('seven')">7️⃣ 7-Eleven</button>
          <button type="button" class="chain-chip" data-chain="familymart" onclick="selectChartChain('familymart')">🟢 FamilyMart</button>
          <button type="button" class="chain-chip" data-chain="lawson" onclick="selectChartChain('lawson')">🔵 Lawson</button>
          <button type="button" class="chain-chip" data-chain="ministop" onclick="selectChartChain('ministop')">🟡 Ministop</button>
          <button type="button" class="chain-chip" data-chain="specialty" onclick="selectChartChain('specialty')">🃏 Shop Thẻ Bài</button>
        </div>

        <!-- Interactive SVG Chart Container -->
        <div class="interactive-chart-container" id="interactive-chart-container">
          <div id="hourly-chart-bars" style="width:100%; height:100%;">
            <!-- Dynamic SVG Chart generated by JS -->
          </div>
          <!-- Chart Floating Tooltip -->
          <div id="chart-tooltip" class="chart-tooltip" style="display:none;"></div>
        </div>
      </div>

      <!-- 2. 2D Prime Time Heatmap Matrix -->
      <div class="panel-card" id="heatmap-card">
        <div class="panel-card-header">
          <div>
            <div class="panel-title">🗺️ Ma Trận Khung Giờ Vàng Restock 2D (Heatmap Matrix)</div>
            <div class="panel-sub">Mật độ restock thực tế kết hợp 2 chiều: Chuỗi cửa hàng / Thứ trong tuần × 24 Khung giờ (00:00 - 23:00 JST)</div>
          </div>
          <!-- Mode Switch Buttons -->
          <div style="display:flex; gap:6px;">
            <button type="button" class="stats-btn stats-btn-primary" id="btn-hm-chain" onclick="switchHeatmapMode('chain')">🏢 Theo Chuỗi Combini</button>
            <button type="button" class="stats-btn stats-btn-outline" id="btn-hm-dow" onclick="switchHeatmapMode('dow')">📅 Theo Thứ Trong Tuần</button>
          </div>
        </div>

        <!-- Heatmap Legend -->
        <div class="heatmap-legend" style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:12px; font-size:0.72rem; color:#94a3b8;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span>Mật độ hàng về:</span>
            <span style="display:inline-flex; align-items:center; gap:4px;"><span style="display:inline-block; width:12px; height:12px; background:#0f172a; border:1px solid #334155; border-radius:3px;"></span> 0/Thấp</span>
            <span style="display:inline-flex; align-items:center; gap:4px;"><span style="display:inline-block; width:12px; height:12px; background:#0369a1; border-radius:3px;"></span> Trung bình</span>
            <span style="display:inline-flex; align-items:center; gap:4px;"><span style="display:inline-block; width:12px; height:12px; background:#10b981; border-radius:3px;"></span> Cao</span>
            <span style="display:inline-flex; align-items:center; gap:4px;"><span style="display:inline-block; width:12px; height:12px; background:linear-gradient(135deg, #f59e0b, #ef4444); border-radius:3px; box-shadow:0 0 6px #f59e0b;"></span> ⭐ Giờ vàng (Golden Hour)</span>
          </div>
          <div style="color:#f59e0b; font-weight:700;">💡 Rê chuột / chạm ô để xem chi tiết số lượt &amp; tỷ lệ</div>
        </div>

        <!-- Heatmap Grid / Table Container -->
        <div class="heatmap-scroll-wrapper">
          <div id="heatmap-matrix-container">
            <div style="text-align:center; padding:20px; color:#64748b;">Đang tải ma trận heatmap 2D...</div>
          </div>
          <div id="heatmap-tooltip" class="chart-tooltip" style="display:none;"></div>
        </div>
      </div>

      <!-- Region & Chain Distribution Grid -->
      <div class="chart-grid">
        <div class="panel-card">
          <div class="panel-card-header">
            <div class="panel-title">📍 Phân Bổ Theo Tỉnh Thành</div>
          </div>
          <div id="pref-distribution-container">
            <!-- Progress bars -->
          </div>
        </div>

        <div class="panel-card">
          <div class="panel-card-header">
            <div class="panel-title">🏢 Phân Bổ Theo Chuỗi Cửa Hàng</div>
          </div>
          <div id="chain-distribution-container">
            <!-- Progress bars -->
          </div>
        </div>
      </div>

      <!-- Top Packs Trending -->
      <div class="panel-card">
        <div class="panel-card-header">
          <div class="panel-title">📦 Các Bộ Pack Thẻ Xuất Hiện Nhiều Nhất</div>
          <div class="panel-sub">Tên các gói thẻ Pokémon được người dùng ghi nhận trong các đợt mở bán</div>
        </div>
        <div id="top-packs-container" style="display:flex; flex-wrap:wrap; gap:10px;">
          <!-- Pack tags -->
        </div>
      </div>
    </section>

    <!-- PANE 4: DB & SYSTEM OPERATIONS -->
    <section id="pane-db" class="stats-pane">
      <div class="panel-card">
        <div class="panel-card-header">
          <div class="panel-title">⚡ Trạng Thái Hệ Thống &amp; CSDL SQLite</div>
          <div class="panel-sub">Theo dõi luồng chạy ngầm 24/7 và kiểm soát tính toàn vẹn dữ liệu</div>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px;">
          <div style="background:#0f172a; padding:14px; border-radius:10px; border:1px solid #334155;">
            <div style="font-weight:800; font-size:0.85rem; color:#38bdf8; margin-bottom:8px;">🤖 Tiến trình ngầm DataSyncDaemon</div>
            <div style="font-size:0.75rem; color:#94a3b8; line-height:1.6;">
              • Trạng thái: <span style="color:#4ade80; font-weight:800;">🟢 Đang chạy ngầm liên tục</span><br>
              • Chu kỳ quét: <strong>15 giây / lần</strong><br>
              • Vùng quét: <strong>Osaka, Tokyo, Kanagawa, Chiba, Aichi, Gifu, Mie</strong><br>
              • Cơ chế: Bất kỳ tin mới phát sinh trên PokéTan JP sẽ được tự động ghi vĩnh viễn vào SQLite CSDL.
            </div>
          </div>

          <div style="background:#0f172a; padding:14px; border-radius:10px; border:1px solid #334155;">
            <div style="font-weight:800; font-size:0.85rem; color:#38bdf8; margin-bottom:8px;">💾 CSDL SQLite pokemap.db</div>
            <div style="font-size:0.75rem; color:#94a3b8; line-height:1.6;">
              • File vị trí: <code>app/data/pokemap.db</code><br>
              • Chế độ ghi: <strong>WAL (Write-Ahead Logging)</strong> an toàn đa luồng<br>
              • Ràng buộc duy nhất: <code>(store_id, timestamp, status_code)</code> chống trùng 100%<br>
              • Múi giờ chuẩn: <strong>JST (UTC+9, Giờ Nhật Bản)</strong>
            </div>
          </div>
        </div>

        <!-- Sync single store manual tool -->
        <div style="margin-top:20px; background:#0f172a; padding:16px; border-radius:10px; border:1px solid #334155;">
          <div style="font-weight:800; font-size:0.85rem; color:#f8fafc; margin-bottom:6px;">🔄 Nạp lại lịch sử tức thời cho 1 cửa hàng</div>
          <div style="font-size:0.72rem; color:#94a3b8; margin-bottom:10px;">Nhập mã ID quán (ví dụ <code>p_R8tFFNuYJkys</code>) để ép hệ thống gọi PokéTan Firestore và nạp trọn bộ vào SQLite:</div>
          <div style="display:flex; gap:8px; max-width:480px;">
            <input type="text" class="filter-input" id="manual-sync-sid" placeholder="Nhập Store ID (ví dụ: p_R8tFFNuYJkys)" style="flex:1;">
            <button class="stats-btn stats-btn-primary" onclick="manualSyncStore()">⚡ Nạp ngay</button>
          </div>
          <div id="manual-sync-result" style="margin-top:8px; font-size:0.75rem; font-weight:700;"></div>
        </div>
      </div>
    </section>

  </main>

  <!-- STORE DETAIL MODAL -->
  <div id="store-modal" class="stats-modal" onclick="if(event.target===this) closeStoreModal()">
    <div class="stats-modal-card">
      <div class="stats-modal-header">
        <div>
          <h3 id="modal-store-name" style="font-size:0.95rem; font-weight:800; color:#ffffff; margin:0;">Chi tiết Cửa Hàng</h3>
          <div id="modal-store-sub" style="font-size:0.7rem; color:#94a3b8; margin-top:2px;"></div>
        </div>
        <button class="modal-close-btn" style="color:#ffffff;" onclick="closeStoreModal()">✕</button>
      </div>
      <div class="stats-modal-body">
        <div style="display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
          <a id="modal-map-link" href="#" class="stats-btn stats-btn-primary" style="font-size:0.75rem;">🗺️ Xem Trên Bản Đồ</a>
          <button id="modal-resync-btn" class="stats-btn stats-btn-outline" style="font-size:0.75rem;" onclick="resyncCurrentModalStore()">🔄 Nạp lại từ PokéTan</button>
        </div>
        <h4 style="font-size:0.8rem; font-weight:800; color:#e2e8f0; margin-bottom:8px;">Lịch sử các lần báo cáo:</h4>
        <div id="modal-history-list" style="display:flex; flex-direction:column; gap:8px;">
          <!-- Items -->
        </div>
      </div>
    </div>
  </div>

  __SHARED_MODALS_HTML__
  __SHARED_FOOTER__

  <!-- JAVASCRIPT LOGIC -->
  <script>
    let currentHistPage = 1;
    let totalHistPages = 1;
    let rawLeaderboardData = [];
    let currentModalStoreId = null;

    const CHAIN_NAMES = {
      'seven': '7-Eleven',
      'lawson': 'Lawson',
      'familymart': 'FamilyMart',
      'ministop': 'Ministop',
      'specialty': 'Shop Thẻ Bài',
      'joshin': 'Joshin',
      'edion': 'EDION',
      'aeon': 'AEON',
      'geo': 'GEO',
      'yamada': 'Yamada Denki',
      'ks': "K's Denki",
      'toysrus': 'Toys "R" Us',
      'biccamera': 'Bic Camera',
      'yodobashi': 'Yodobashi Camera',
      'other': 'Cửa hàng khác'
    };

    const PREF_NAMES = {
      'osaka': '大阪 Osaka',
      'tokyo': '東京 Tokyo',
      'kanagawa': '神奈川 Kanagawa',
      'aichi': '愛知 Aichi',
      'chiba': '千葉 Chiba',
      'gifu': '岐阜 Gifu',
      'mie': '三重 Mie'
    };

    // Known Station Coordinates for Distance & Proximity Filtering
    const ANCHOR_COORDS = {
      namba: { lat: 34.6667, lng: 135.5000, name: 'Ga Namba (Osaka)' },
      umeda: { lat: 34.7024, lng: 135.4959, name: 'Ga Umeda (Osaka)' },
      imamiya: { lat: 34.6540, lng: 135.4925, name: 'Ga JR Imamiya (Osaka)' },
      ota: { lat: 34.6628, lng: 135.5058, name: 'Nipponbashi Ota Road' },
      tennoji: { lat: 34.6472, lng: 135.5140, name: 'Ga Tennoji (Osaka)' },
      shinjuku: { lat: 35.6896, lng: 139.7006, name: 'Ga Shinjuku (Tokyo)' },
      akiba: { lat: 35.6983, lng: 139.7731, name: 'Ga Akihabara (Tokyo)' },
      shibuya: { lat: 35.6580, lng: 139.7016, name: 'Ga Shibuya (Tokyo)' },
      nagoya: { lat: 35.1709, lng: 136.8815, name: 'Ga Nagoya (Aichi)' },
      yokohama: { lat: 35.4658, lng: 139.6227, name: 'Ga Yokohama (Kanagawa)' }
    };

    let userGpsLat = null;
    let userGpsLng = null;
    let currentLbAnchor = 'all';
    let currentLbRadius = '';
    let currentHistAnchor = 'all';
    let currentHistRadius = '';
    let currentChartChain = '';
    let currentHeatmapMode = 'chain';
    let rawHourlyData = [];
    const chainAnalyticsCache = {};
    const heatmapDataCache = {};

    function calcDistanceKm(lat1, lon1, lat2, lon2) {
      if (lat1 === null || lon1 === null || lat2 === null || lon2 === null) return null;
      if (lat1 === undefined || lon1 === undefined || lat2 === undefined || lon2 === undefined) return null;
      const R = 6371.0;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      return R * c;
    }

    function formatDistanceBadge(dKm, anchorName) {
      if (dKm === null || dKm === undefined) return '';
      const roadKm = dKm * 1.22;
      let text = '';
      if (dKm < 1.0) {
        const dM = Math.round(dKm * 1000);
        if (roadKm < 1.0) {
          const roadM = Math.round(roadKm * 1000);
          text = `~${roadM}m đường đi (${dM}m thẳng)`;
        } else {
          text = `~${roadKm.toFixed(1)}km đường đi (${dM}m thẳng)`;
        }
      } else {
        text = `~${roadKm.toFixed(1)}km đường đi (${dKm.toFixed(1)}km thẳng)`;
      }
      return `<span class="dist-badge" title="Khoảng cách từ ${anchorName}: ${text}">📍 ${text}</span>`;
    }

    function getAnchorCoords(anchorKey) {
      if (anchorKey === 'gps' && userGpsLat !== null && userGpsLng !== null) {
        return { lat: userGpsLat, lng: userGpsLng, name: 'Vị trí của bạn' };
      }
      if (ANCHOR_COORDS[anchorKey]) {
        return ANCHOR_COORDS[anchorKey];
      }
      return null;
    }

    function onLbAnchorChange() {
      const val = document.getElementById('lb-anchor-select').value;
      currentLbAnchor = val;
      if (val === 'gps') {
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            pos => {
              userGpsLat = pos.coords.latitude;
              userGpsLng = pos.coords.longitude;
              filterLeaderboardClient();
            },
            err => {
              alert('Không thể lấy vị trí GPS từ trình duyệt: ' + err.message);
              document.getElementById('lb-anchor-select').value = 'all';
              currentLbAnchor = 'all';
              filterLeaderboardClient();
            }
          );
        } else {
          alert('Trình duyệt không hỗ trợ Geolocation GPS.');
          document.getElementById('lb-anchor-select').value = 'all';
          currentLbAnchor = 'all';
          filterLeaderboardClient();
        }
      } else {
        filterLeaderboardClient();
      }
    }

    function selectLbRadius(rad) {
      currentLbRadius = rad !== '' ? parseFloat(rad) : '';
      document.querySelectorAll('#lb-radius-chips-bar .radius-chip').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-radius') === String(rad));
      });
      if (currentLbRadius !== '' && currentLbAnchor === 'all') {
        document.getElementById('lb-anchor-select').value = 'namba';
        currentLbAnchor = 'namba';
      }
      filterLeaderboardClient();
    }

    function onHistAnchorChange() {
      currentHistAnchor = document.getElementById('hist-anchor-select').value;
      if (currentHistAnchor === 'gps') {
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            pos => {
              userGpsLat = pos.coords.latitude;
              userGpsLng = pos.coords.longitude;
              fetchHistoryPage(1);
            },
            err => {
              document.getElementById('hist-anchor-select').value = 'all';
              currentHistAnchor = 'all';
              fetchHistoryPage(1);
            }
          );
        } else {
          currentHistAnchor = 'all';
          fetchHistoryPage(1);
        }
      } else {
        fetchHistoryPage(1);
      }
    }

    function selectHistRadius(rad) {
      currentHistRadius = rad !== '' ? parseFloat(rad) : '';
      document.querySelectorAll('#hist-radius-chips-bar .radius-chip').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-radius') === String(rad));
      });
      if (currentHistRadius !== '' && currentHistAnchor === 'all') {
        document.getElementById('hist-anchor-select').value = 'namba';
        currentHistAnchor = 'namba';
      }
      fetchHistoryPage(1);
    }

    // Switch Top Tabs
    function switchStatsTab(tabId) {
      document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.stats-pane').forEach(p => p.classList.remove('active'));

      const btn = document.getElementById('tab-' + tabId + '-btn');
      if (btn) btn.classList.add('active');
      const pane = document.getElementById('pane-' + tabId);
      if (pane) pane.classList.add('active');

      if (tabId === 'history' && currentHistPage === 1) {
        fetchHistoryPage(1);
      }
    }

    // Load Overview & Initial Data
    async function loadAllStats() {
      try {
        const res = await fetch('/api/stats/overview');
        const data = await res.json();

        // Update KPIs
        document.getElementById('kpi-total-stores').textContent = (data.total_stores || 0).toLocaleString();
        document.getElementById('kpi-in-stock').textContent = (data.in_stock_now || 0).toLocaleString();
        
        const inRate = data.total_stores > 0 ? ((data.in_stock_now / data.total_stores) * 100).toFixed(2) : '0';
        document.getElementById('kpi-in-rate').textContent = `Tỷ lệ có hàng: ${inRate}%`;

        document.getElementById('kpi-total-reports').textContent = (data.total_reports || 0).toLocaleString();
        document.getElementById('kpi-active-stores').textContent = `Ghi nhận: ${(data.active_stores || 0).toLocaleString()} quán`;

        document.getElementById('kpi-latest-time').textContent = data.latest_formatted_time || 'Chưa có';
        document.getElementById('kpi-latest-ago').textContent = data.latest_timestamp ? formatTimeAgoJST(data.latest_timestamp) : 'Tự động 15s';

        // Render Charts & 2D Heatmap
        rawHourlyData = data.by_hour || [];
        renderHourlyChart(rawHourlyData);
        renderDistribution(data.by_pref || [], 'pref-distribution-container', PREF_NAMES);
        renderDistribution(data.by_chain || [], 'chain-distribution-container', CHAIN_NAMES);
        renderTopPacks(data.top_packs || []);

        // Load Heatmap Matrix
        loadHeatmapData('chain');

      } catch (e) {
        console.error('Error loading overview stats:', e);
      }

      // Fetch Leaderboard
      fetchLeaderboard();
    }

    // Interactive SVG Chart Renderer
    async function selectChartChain(chainCode) {
      currentChartChain = chainCode;
      document.querySelectorAll('.chain-chip').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-chain') === chainCode);
      });

      if (!chainCode) {
        renderInteractiveSvgChart(rawHourlyData, null, '');
        return;
      }

      if (chainAnalyticsCache[chainCode]) {
        renderInteractiveSvgChart(chainAnalyticsCache[chainCode].by_hour_objs, chainAnalyticsCache[chainCode], chainCode);
        return;
      }

      try {
        const res = await fetch(`/api/stats/combini_analytics?chain=${encodeURIComponent(chainCode)}`);
        const data = await res.json();
        const byHourObjs = (data.hourly_distribution || []).map(h => ({
          hour: h.hour,
          total: h.count,
          in_stock: h.count
        }));
        data.by_hour_objs = byHourObjs;
        chainAnalyticsCache[chainCode] = data;
        renderInteractiveSvgChart(byHourObjs, data, chainCode);
      } catch (e) {
        console.error('Error fetching chain analytics:', e);
      }
    }

    function renderHourlyChart(hourlyData) {
      rawHourlyData = hourlyData || [];
      renderInteractiveSvgChart(rawHourlyData, null, currentChartChain);
    }

    function renderInteractiveSvgChart(hourlyData, chainData, selectedChain) {
      const container = document.getElementById('hourly-chart-bars');
      if (!container) return;

      const hourMap = {};
      (hourlyData || []).forEach(h => { hourMap[h.hour] = h; });

      const hours = [];
      let maxVal = 1;
      for (let h = 0; h < 24; h++) {
        const item = hourMap[h] || { hour: h, total: 0, in_stock: 0 };
        hours.push(item);
        if (item.total > maxVal) maxVal = item.total;
        if (item.in_stock > maxVal) maxVal = item.in_stock;
      }

      const svgWidth = 840;
      const svgHeight = 200;
      const chartTop = 20;
      const chartBottom = 165;
      const chartLeft = 40;
      const chartRight = 820;
      const plotWidth = chartRight - chartLeft;
      const plotHeight = chartBottom - chartTop;

      const colWidth = (plotWidth / 24);
      const barWidth = Math.max(8, colWidth - 8);

      let gridLinesHtml = '';
      for (let g = 0; g <= 4; g++) {
        const y = chartBottom - (plotHeight * (g / 4));
        const val = Math.round(maxVal * (g / 4));
        gridLinesHtml += `
          <line x1="${chartLeft}" y1="${y}" x2="${chartRight}" y2="${y}" class="svg-grid-line" />
          <text x="${chartLeft - 6}" y="${y + 3.5}" text-anchor="end" fill="#64748b" font-size="9.5" font-weight="700">${val}</text>
        `;
      }

      let barsHtml = '';
      let hoverRectsHtml = '';
      const chainName = selectedChain ? (CHAIN_NAMES[selectedChain] || selectedChain) : 'Tất cả chuỗi';

      hours.forEach((item, hr) => {
        const x = chartLeft + (hr * colWidth) + (colWidth - barWidth) / 2;
        const totalHeight = Math.max(2, (item.total / maxVal) * plotHeight);
        const instockHeight = Math.max(2, (item.in_stock / maxVal) * plotHeight);
        const yTotal = chartBottom - totalHeight;
        const yInstock = chartBottom - instockHeight;
        const isPeak = hr >= 9 && hr <= 15;
        const inRate = item.total > 0 ? ((item.in_stock / item.total) * 100).toFixed(1) : '0';

        barsHtml += `
          <rect x="${x}" y="${yTotal}" width="${barWidth}" height="${totalHeight}" class="svg-bar-total" />
          <rect x="${x}" y="${yInstock}" width="${barWidth}" height="${instockHeight}" class="svg-bar-instock${isPeak ? ' peak' : ''}" />
        `;

        if (isPeak) {
          barsHtml += `
            <text x="${x + barWidth / 2}" y="${Math.min(yInstock, yTotal) - 4}" text-anchor="middle" font-size="9" fill="#f59e0b" font-weight="900">⭐</text>
          `;
        }

        const xLabel = x + barWidth / 2;
        barsHtml += `
          <text x="${xLabel}" y="${chartBottom + 16}" class="svg-axis-text">${hr % 2 === 0 ? String(hr).padStart(2,'0') + 'h' : ''}</text>
        `;

        const colLeft = chartLeft + (hr * colWidth);
        hoverRectsHtml += `
          <rect class="svg-col-hover-rect" x="${colLeft}" y="${chartTop}" width="${colWidth}" height="${plotHeight}"
                onmouseenter="showChartTooltip(event, ${hr}, ${item.total}, ${item.in_stock}, '${inRate}', '${chainName}', ${isPeak})"
                onmousemove="moveChartTooltip(event)"
                onmouseleave="hideChartTooltip()" />
        `;
      });

      container.innerHTML = `
        <svg class="svg-chart" viewBox="0 0 ${svgWidth} ${svgHeight}" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="instock-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#38bdf8" />
              <stop offset="100%" stop-color="#2563eb" />
            </linearGradient>
            <linearGradient id="peak-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#fbbf24" />
              <stop offset="100%" stop-color="#d97706" />
            </linearGradient>
          </defs>
          ${gridLinesHtml}
          ${barsHtml}
          ${hoverRectsHtml}
        </svg>
      `;
    }

    function showChartTooltip(event, hour, total, instock, inRate, chainLabel, isPeak) {
      const tip = document.getElementById('chart-tooltip');
      if (!tip) return;
      const hStr = String(hour).padStart(2, '0');
      const peakHtml = isPeak 
        ? `<div style="color:#f59e0b; font-weight:800; margin-top:4px;">🔥 Khung giờ vàng Restock cao điểm!</div>`
        : '';

      tip.innerHTML = `
        <div style="font-weight:800; color:#38bdf8; font-size:0.8rem; margin-bottom:4px;">⏰ ${hStr}:00 - ${hStr}:59 JST</div>
        <div style="color:#cbd5e1; font-size:0.7rem;">🏢 Phạm vi: <strong>${chainLabel}</strong></div>
        <div style="margin-top:4px; display:flex; justify-content:space-between; gap:10px;">
          <span>📦 Tổng lượt báo cáo:</span>
          <strong>${total.toLocaleString()}</strong>
        </div>
        <div style="display:flex; justify-content:space-between; gap:10px; color:#34d399;">
          <span>🟢 Lượt có hàng:</span>
          <strong>${instock.toLocaleString()} (${inRate}%)</strong>
        </div>
        ${peakHtml}
      `;
      tip.style.display = 'block';
      moveChartTooltip(event);
    }

    function moveChartTooltip(event) {
      const tip = document.getElementById('chart-tooltip');
      const container = document.getElementById('interactive-chart-container');
      if (!tip || !container) return;
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left + 12;
      const y = event.clientY - rect.top - 10;
      tip.style.left = Math.min(x, rect.width - 240) + 'px';
      tip.style.top = Math.max(10, Math.min(y, rect.height - 100)) + 'px';
    }

    function hideChartTooltip() {
      const tip = document.getElementById('chart-tooltip');
      if (tip) tip.style.display = 'none';
    }

    // 2D Heatmap Matrix Implementation
    function switchHeatmapMode(mode) {
      currentHeatmapMode = mode;
      document.getElementById('btn-hm-chain').className = mode === 'chain' ? 'stats-btn stats-btn-primary' : 'stats-btn stats-btn-outline';
      document.getElementById('btn-hm-dow').className = mode === 'dow' ? 'stats-btn stats-btn-primary' : 'stats-btn stats-btn-outline';
      loadHeatmapData(mode);
    }

    async function loadHeatmapData(mode) {
      const container = document.getElementById('heatmap-matrix-container');
      if (!container) return;

      if (heatmapDataCache[mode]) {
        renderHeatmapMatrix(heatmapDataCache[mode]);
        return;
      }

      container.innerHTML = '<div style="text-align:center; padding:24px; color:#64748b;">Đang phân tích mật độ 2D Heatmap...</div>';

      try {
        const res = await fetch(`/api/stats/heatmap?mode=${encodeURIComponent(mode)}`);
        const data = await res.json();
        heatmapDataCache[mode] = data;
        renderHeatmapMatrix(data);
      } catch (e) {
        container.innerHTML = `<div style="text-align:center; padding:20px; color:#ef4444;">Lỗi tải dữ liệu Heatmap: ${e.message}</div>`;
      }
    }

    function renderHeatmapMatrix(data) {
      const container = document.getElementById('heatmap-matrix-container');
      if (!container) return;

      const rows = data.rows || [];
      const maxDensity = data.max_density || 1;
      const mode = data.mode || 'chain';

      let html = `<table class="heatmap-table"><thead><tr>`;
      html += `<th style="width:130px; text-align:left; padding-left:10px;">${mode === 'chain' ? 'Chuỗi Combini' : 'Thứ Trong Tuần'}</th>`;
      for (let h = 0; h < 24; h++) {
        const isPeakH = h >= 9 && h <= 15;
        const hStyle = isPeakH ? 'color:#f59e0b; font-weight:900;' : '';
        html += `<th style="${hStyle}">${String(h).padStart(2, '0')}h</th>`;
      }
      html += `<th style="width:70px;">Tổng Restock</th>`;
      html += `</tr></thead><tbody>`;

      rows.forEach(r => {
        html += `<tr>`;
        html += `<td class="heatmap-row-label">${r.label}</td>`;

        (r.hours || []).forEach(cell => {
          const count = cell.in_stock || 0;
          const ratio = maxDensity > 0 ? (count / maxDensity) : 0;
          const isGolden = cell.is_golden || (ratio >= 0.65 && cell.hour >= 9 && cell.hour <= 16);

          let bg = '#090e17';
          let textColor = '#475569';
          if (count > 0) {
            if (ratio < 0.2) {
              bg = 'rgba(2, 132, 199, 0.35)';
              textColor = '#93c5fd';
            } else if (ratio < 0.5) {
              bg = 'rgba(16, 185, 129, 0.45)';
              textColor = '#a7f3d0';
            } else if (ratio < 0.75) {
              bg = 'linear-gradient(135deg, rgba(245, 158, 11, 0.6), rgba(217, 119, 6, 0.65))';
              textColor = '#ffffff';
            } else {
              bg = 'linear-gradient(135deg, #f59e0b, #ef4444)';
              textColor = '#ffffff';
            }
          }

          const cellClass = 'heatmap-cell' + (isGolden ? ' golden-cell' : '');
          const goldenIcon = isGolden ? '⭐' : '';
          const displayVal = count > 0 ? (count >= 100 ? `${Math.round(count/1000 * 10)/10}k` : count) : '·';

          html += `
            <td class="${cellClass}" style="background:${bg}; color:${textColor};"
                onmouseenter="showHeatmapTooltip(event, '${r.label}', ${cell.hour}, ${cell.total}, ${cell.in_stock}, '${cell.in_rate}', ${isGolden})"
                onmousemove="moveHeatmapTooltip(event)"
                onmouseleave="hideHeatmapTooltip()">
              ${goldenIcon ? `<div style="font-size:0.6rem; line-height:1;">${goldenIcon}</div>` : ''}
              <div>${displayVal}</div>
            </td>
          `;
        });

        const peakHStr = String(r.peak_hour).padStart(2, '0') + ':00';
        html += `
          <td style="text-align:center; padding:6px; font-weight:800; color:#38bdf8; background:#0f172a; border-radius:4px;">
            <div>${(r.total_in_stock || 0).toLocaleString()}</div>
            <div style="font-size:0.62rem; color:#f59e0b; margin-top:2px;" title="Giờ đỉnh điểm">🔥 ${peakHStr}</div>
          </td>
        `;
        html += `</tr>`;
      });

      html += `</tbody></table>`;
      container.innerHTML = html;
    }

    function showHeatmapTooltip(event, label, hour, total, instock, inRate, isGolden) {
      const tip = document.getElementById('heatmap-tooltip');
      if (!tip) return;
      const hStr = String(hour).padStart(2, '0');
      const goldenNotice = isGolden 
        ? `<div style="color:#f59e0b; font-weight:800; margin-top:4px;">⭐ KHUNG GIỜ VÀNG RESTOCK CỰC CAO!</div>`
        : '';

      tip.innerHTML = `
        <div style="font-weight:800; color:#f8fafc; font-size:0.8rem; margin-bottom:4px;">🏢 ${label} • ${hStr}:00 - ${hStr}:59 JST</div>
        <div style="display:flex; justify-content:space-between; gap:10px; color:#94a3b8;">
          <span>Tổng số báo cáo:</span>
          <strong style="color:#ffffff;">${total.toLocaleString()}</strong>
        </div>
        <div style="display:flex; justify-content:space-between; gap:10px; color:#34d399;">
          <span>🟢 Lượt có hàng:</span>
          <strong>${instock.toLocaleString()} (${inRate}%)</strong>
        </div>
        ${goldenNotice}
      `;
      tip.style.display = 'block';
      moveHeatmapTooltip(event);
    }

    function moveHeatmapTooltip(event) {
      const tip = document.getElementById('heatmap-tooltip');
      const container = document.getElementById('heatmap-card');
      if (!tip || !container) return;
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left + 12;
      const y = event.clientY - rect.top - 10;
      tip.style.left = Math.min(x, rect.width - 250) + 'px';
      tip.style.top = Math.max(10, Math.min(y, rect.height - 90)) + 'px';
    }

    function hideHeatmapTooltip() {
      const tip = document.getElementById('heatmap-tooltip');
      if (tip) tip.style.display = 'none';
    }

    // Render Progress distribution
    function renderDistribution(items, containerId, labelMap) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = '';

      if (!items || items.length === 0) {
        container.innerHTML = '<div style="color:#64748b; font-size:0.75rem;">Không có dữ liệu</div>';
        return;
      }

      const maxVal = Math.max(...items.map(x => x.count || 0), 1);
      items.slice(0, 7).forEach(item => {
        const key = item.pref || item.chain || 'other';
        const label = labelMap[key] || key;
        const cnt = item.count || 0;
        const pct = Math.max(4, (cnt / maxVal) * 100);

        const row = document.createElement('div');
        row.className = 'progress-row';
        row.innerHTML = `
          <div class="progress-label" title="${label}">${label}</div>
          <div class="progress-track">
            <div class="progress-fill" style="width:${pct}%;"></div>
          </div>
          <div class="progress-val">${cnt.toLocaleString()}</div>
        `;
        container.appendChild(row);
      });
    }

    // Render Top Packs
    function renderTopPacks(packs) {
      const container = document.getElementById('top-packs-container');
      if (!container) return;
      container.innerHTML = '';
      if (!packs || packs.length === 0) {
        container.innerHTML = '<div style="color:#64748b; font-size:0.75rem;">Chưa có dữ liệu pack thẻ</div>';
        return;
      }
      packs.forEach(p => {
        const div = document.createElement('div');
        div.style.cssText = 'background:#0f172a; border:1px solid #38bdf8; border-radius:8px; padding:6px 12px; display:flex; align-items:center; gap:8px; font-size:0.78rem; font-weight:700; color:#38bdf8;';
        div.innerHTML = `<span>📦 ${p.pack}</span> <span style="background:rgba(56,189,248,0.2); padding:2px 6px; border-radius:4px; font-weight:800;">${p.count}</span>`;
        container.appendChild(div);
      });
    }

    // Fetch Leaderboard
    async function fetchLeaderboard() {
      const pref = document.getElementById('lb-pref-select').value;
      const chain = document.getElementById('lb-chain-select').value;
      const tbody = document.getElementById('leaderboard-tbody');
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:30px; color:#64748b;">Đang tải dữ liệu xếp hạng...</td></tr>';

      try {
        let url = `/api/stats/leaderboard?limit=100`;
        if (pref) url += `&pref=${encodeURIComponent(pref)}`;
        if (chain) url += `&chain=${encodeURIComponent(chain)}`;

        const res = await fetch(url);
        rawLeaderboardData = await res.json();
        filterLeaderboardClient();
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:30px; color:#ef4444;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
      }
    }

    // Filter Leaderboard client-side by keyword, distance and sort
    function filterLeaderboardClient() {
      const q = (document.getElementById('lb-search').value || '').trim().toLowerCase();
      const sortMode = (document.getElementById('lb-sort-select') ? document.getElementById('lb-sort-select').value : 'reports') || 'reports';
      const tbody = document.getElementById('leaderboard-tbody');
      tbody.innerHTML = '';

      let list = [...rawLeaderboardData];
      const anchor = getAnchorCoords(currentLbAnchor);

      // Attach distance to stores if anchor is active
      if (anchor) {
        list.forEach(st => {
          if (st.lat && st.lng) {
            st._distKm = calcDistanceKm(anchor.lat, anchor.lng, parseFloat(st.lat), parseFloat(st.lng));
          } else {
            st._distKm = null;
          }
        });

        // Filter by radius if selected
        if (currentLbRadius !== '') {
          list = list.filter(st => st._distKm !== null && st._distKm <= currentLbRadius);
        }
      }

      if (q) {
        list = list.filter(item => 
          (item.name && item.name.toLowerCase().includes(q)) || 
          (item.address && item.address.toLowerCase().includes(q)) ||
          (item.id && item.id.toLowerCase().includes(q))
        );
      }

      // Sort
      if (sortMode === 'distance' && anchor) {
        list.sort((a, b) => {
          if (a._distKm === null) return 1;
          if (b._distKm === null) return -1;
          return a._distKm - b._distKm;
        });
      } else if (sortMode === 'rate') {
        list.sort((a, b) => (b.in_rate || 0) - (a.in_rate || 0));
      } else {
        list.sort((a, b) => (b.total_reports || 0) - (a.total_reports || 0));
      }

      document.getElementById('lb-count-display').textContent = list.length;

      if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:30px; color:#64748b;">Không tìm thấy cửa hàng nào thỏa mãn điều kiện hoặc nằm trong bán kính đã chọn.</td></tr>';
        return;
      }

      list.slice(0, 100).forEach((st, idx) => {
        const tr = document.createElement('tr');
        const chainLabel = CHAIN_NAMES[st.chain] || st.chain || 'Other';
        const prefLabel = PREF_NAMES[st.pref] || st.pref || '';
        
        let rankBadge = `<span style="font-weight:800; color:#94a3b8;">#${idx + 1}</span>`;
        if (idx === 0) rankBadge = `<span style="font-size:1.1rem;">🥇</span>`;
        else if (idx === 1) rankBadge = `<span style="font-size:1.1rem;">🥈</span>`;
        else if (idx === 2) rankBadge = `<span style="font-size:1.1rem;">🥉</span>`;

        const inBadge = `<span class="badge badge-in">🟢 ${st.in_count}</span>`;
        const outBadge = `<span class="badge badge-out">🔴 ${st.out_count}</span>`;

        let distBadgeHtml = '';
        if (anchor && st._distKm !== null && st._distKm !== undefined) {
          distBadgeHtml = formatDistanceBadge(st._distKm, anchor.name);
        }

        tr.innerHTML = `
          <td data-label="Thứ hạng" style="text-align:center;">${rankBadge}</td>
          <td data-label="Cửa hàng">
            <div style="font-weight:800; color:#f8fafc; cursor:pointer;" onclick="openStoreModal('${st.id}')">${st.name}</div>
            <div style="font-size:0.68rem; color:#64748b; max-width:260px; overflow:hidden; text-overflow:ellipsis;" title="${st.address}">${st.address || 'Chưa cập nhật địa chỉ'}</div>
          </td>
          <td data-label="Khu vực & Khoảng cách">
            <div style="display:flex; flex-direction:column; gap:2px;">
              <span style="font-size:0.75rem; font-weight:700; color:#38bdf8;">${prefLabel}</span>
              ${distBadgeHtml}
            </div>
          </td>
          <td data-label="Chuỗi"><span style="font-size:0.75rem; color:#cbd5e1;">${chainLabel}</span></td>
          <td data-label="Tổng báo cáo" style="text-align:center; font-weight:900; font-size:0.92rem; color:#f8fafc;">${st.total_reports}</td>
          <td data-label="Tỷ lệ có hàng">
            <div style="display:flex; align-items:center; gap:6px;">
              ${inBadge} ${outBadge}
              <span style="font-size:0.7rem; font-weight:800; color:#94a3b8;">${st.in_rate}%</span>
            </div>
          </td>
          <td data-label="Lần cuối báo cáo" style="font-size:0.72rem; color:#94a3b8;">${st.last_reported_at || 'Chưa có'}</td>
          <td data-label="Thao tác" style="text-align:center;">
            <div style="display:inline-flex; gap:4px;">
              <a href="/map?focus=${st.id}" class="stats-btn stats-btn-outline" style="padding:4px 8px; font-size:0.7rem;" title="Xem trên Bản đồ">🗺️</a>
              <button class="stats-btn stats-btn-outline" style="padding:4px 8px; font-size:0.7rem;" onclick="openStoreModal('${st.id}')" title="Xem chi tiết">📋</button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Fetch Paginated History with distance filtering
    async function fetchHistoryPage(page) {
      currentHistPage = Math.max(1, page);
      const q = (document.getElementById('hist-q').value || '').trim();
      const status = document.getElementById('hist-status').value;
      const pref = document.getElementById('hist-pref').value;
      const chain = document.getElementById('hist-chain').value;

      const tbody = document.getElementById('history-tbody');
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">Đang truy vấn CSDL...</td></tr>';

      try {
        let url = `/api/stats/history_logs?page=${currentHistPage}&limit=30`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (pref) url += `&pref=${encodeURIComponent(pref)}`;
        if (chain) url += `&chain=${encodeURIComponent(chain)}`;

        const res = await fetch(url);
        const data = await res.json();

        totalHistPages = data.total_pages || 1;
        document.getElementById('hist-total-display').textContent = `Tổng cộng: ${(data.total || 0).toLocaleString()} báo cáo`;
        document.getElementById('hist-page-info').textContent = `Trang ${currentHistPage} / ${totalHistPages} (${(data.total || 0).toLocaleString()} tin)`;

        document.getElementById('btn-prev-page').disabled = currentHistPage <= 1;
        document.getElementById('btn-next-page').disabled = currentHistPage >= totalHistPages;

        tbody.innerHTML = '';
        const items = data.items || [];
        if (items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">Không tìm thấy báo cáo nào thỏa điều kiện tìm kiếm.</td></tr>';
          return;
        }

        const anchor = getAnchorCoords(currentHistAnchor);
        let renderedCount = 0;

        items.forEach(item => {
          let distBadgeHtml = '';
          if (anchor && item.lat && item.lng) {
            const dKm = calcDistanceKm(anchor.lat, anchor.lng, parseFloat(item.lat), parseFloat(item.lng));
            if (dKm !== null) {
              if (currentHistRadius !== '' && dKm > currentHistRadius) {
                return;
              }
              distBadgeHtml = `<div style="margin-top:2px;">${formatDistanceBadge(dKm, anchor.name)}</div>`;
            }
          }

          renderedCount++;
          const tr = document.createElement('tr');
          let statusBadge = `<span class="badge badge-none">⚪ Chưa rõ</span>`;
          if (item.status_code === 'i') statusBadge = `<span class="badge badge-in">🟢 Có hàng</span>`;
          else if (item.status_code === 'o') statusBadge = `<span class="badge badge-out">🔴 Hết hàng</span>`;
          else if (item.status_code === 'n') statusBadge = `<span class="badge badge-none">⚪ Không bán thẻ</span>`;

          let packsHtml = '<span style="color:#64748b; font-size:0.7rem;">--</span>';
          if (item.packs && item.packs.length > 0) {
            packsHtml = item.packs.map(p => `<span class="badge-pack">${p}</span>`).join('');
          }

          const noteHtml = item.note ? `<span style="color:#f1f5f9; font-weight:600;">${item.note}</span>` : '<span style="color:#64748b;">(Không có)</span>';
          const authorHtml = `<div style="font-weight:700; color:#94a3b8;">${item.user || '匿名トレーナー'}</div>${item.onsite ? '<span style="color:#38bdf8; font-size:0.65rem; font-weight:800;">📍 Tại quán</span>' : ''}`;

          tr.innerHTML = `
            <td data-label="Thời gian" style="font-weight:700; color:#38bdf8; font-size:0.75rem;">${item.formatted_time || '--'}</td>
            <td data-label="Cửa hàng">
              <div style="font-weight:800; color:#f8fafc; cursor:pointer;" onclick="openStoreModal('${item.store_id}')">${item.name}</div>
              <div style="font-size:0.68rem; color:#64748b; max-width:240px; overflow:hidden; text-overflow:ellipsis;">${item.address || ''}</div>
              ${distBadgeHtml}
            </td>
            <td data-label="Trạng thái">${statusBadge}</td>
            <td data-label="Packs">${packsHtml}</td>
            <td data-label="Ghi chú" style="max-width:200px; overflow:hidden; text-overflow:ellipsis;">${noteHtml}</td>
            <td data-label="Người gửi" style="font-size:0.72rem;">${authorHtml}</td>
            <td data-label="Thao tác" style="text-align:center;">
              <a href="/map?focus=${item.store_id}" class="stats-btn stats-btn-outline" style="padding:4px 8px; font-size:0.7rem;" title="Xem trên Bản đồ">🗺️</a>
            </td>
          `;
          tbody.appendChild(tr);
        });

        if (renderedCount === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">Không có báo cáo nào nằm trong bán kính đã chọn.</td></tr>';
        }

      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:30px; color:#ef4444;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
      }
    }

    function prevHistoryPage() {
      if (currentHistPage > 1) fetchHistoryPage(currentHistPage - 1);
    }
    function nextHistoryPage() {
      if (currentHistPage < totalHistPages) fetchHistoryPage(currentHistPage + 1);
    }

    // Open Store Modal with Fresh History
    async function openStoreModal(storeId) {
      currentModalStoreId = storeId;
      const modal = document.getElementById('store-modal');
      const listContainer = document.getElementById('modal-history-list');
      document.getElementById('modal-store-name').textContent = 'Đang tải thông tin quán...';
      document.getElementById('modal-store-sub').textContent = storeId;
      document.getElementById('modal-map-link').href = `/map?focus=${storeId}`;
      listContainer.innerHTML = '<div style="color:#94a3b8; font-size:0.75rem;">Đang kéo dữ liệu lịch sử từ PokéTan & CSDL...</div>';
      modal.classList.add('open');

      try {
        const res = await fetch(`/api/store_history/${storeId}`);
        const reports = await res.json();

        if (reports && reports.length > 0) {
          listContainer.innerHTML = '';
          reports.forEach(r => {
            const div = document.createElement('div');
            div.style.cssText = 'background:#0f172a; border:1px solid #334155; border-radius:8px; padding:10px 12px;';
            
            let statusBadge = `<span class="badge badge-none">⚪ Chưa rõ</span>`;
            if (r.status_code === 'i') statusBadge = `<span class="badge badge-in">🟢 Có hàng</span>`;
            else if (r.status_code === 'o') statusBadge = `<span class="badge badge-out">🔴 Hết hàng</span>`;
            else if (r.status_code === 'n') statusBadge = `<span class="badge badge-none">⚪ Không bán</span>`;

            let packsStr = '';
            if (r.packs && r.packs.length > 0) {
              packsStr = r.packs.map(p => `<span class="badge-pack">${p}</span>`).join('');
            }

            div.innerHTML = `
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                ${statusBadge}
                <span style="font-size:0.72rem; color:#38bdf8; font-weight:700;">${r.formatted_time || ''}</span>
              </div>
              ${packsStr ? '<div style="margin:4px 0;">' + packsStr + '</div>' : ''}
              ${r.note ? '<div style="font-size:0.75rem; color:#f1f5f9; font-weight:600; margin-top:4px;">' + r.note + '</div>' : ''}
              <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">👤 ${r.user || '匿名トレーナー'} ${r.onsite ? '• 📍 Tại quán' : ''}</div>
            `;
            listContainer.appendChild(div);
          });
        } else {
          listContainer.innerHTML = '<div style="color:#64748b; font-size:0.75rem;">Cửa hàng này chưa có báo cáo nào từ cộng đồng.</div>';
        }
      } catch (e) {
        listContainer.innerHTML = `<div style="color:#ef4444; font-size:0.75rem;">Lỗi: ${e.message}</div>`;
      }
    }

    function closeStoreModal() {
      document.getElementById('store-modal').classList.remove('open');
    }

    async function resyncCurrentModalStore() {
      if (!currentModalStoreId) return;
      const btn = document.getElementById('modal-resync-btn');
      btn.textContent = '⏳ Đang nạp...';
      btn.disabled = true;
      await openStoreModal(currentModalStoreId);
      btn.textContent = '🔄 Nạp lại từ PokéTan';
      btn.disabled = false;
    }

    // Manual Sync Tool in DB pane
    async function manualSyncStore() {
      const input = document.getElementById('manual-sync-sid');
      const resDiv = document.getElementById('manual-sync-result');
      const sid = (input.value || '').trim();
      if (!sid) {
        resDiv.style.color = '#ef4444';
        resDiv.textContent = 'Vui lòng nhập Store ID!';
        return;
      }
      resDiv.style.color = '#38bdf8';
      resDiv.textContent = '⏳ Đang kết nối PokéTan Firestore & nạp vào SQLite CSDL...';
      try {
        const res = await fetch(`/api/store_history/${encodeURIComponent(sid)}`);
        const reports = await res.json();
        resDiv.style.color = '#4ade80';
        resDiv.textContent = `✅ Thành công! Đã nạp và lưu ${reports.length} bản ghi lịch sử vào SQLite CSDL cho quán ${sid}!`;
        loadAllStats();
      } catch (e) {
        resDiv.style.color = '#ef4444';
        resDiv.textContent = `❌ Lỗi: ${e.message}`;
      }
    }

    // Relative Time Helper
    function formatTimeAgoJST(unixTs) {
      if (!unixTs) return '';
      const now = Math.floor(Date.now() / 1000);
      const diff = now - unixTs;
      if (diff < 60) return 'たった今';
      if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
      if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
      return `${Math.floor(diff / 86400)} ngày trước`;
    }

    // Boot
    document.addEventListener('DOMContentLoaded', () => {
      loadAllStats();
    });
  </script>
</body>
</html>"""

    return html.replace("__SHARED_HEAD__", shared_head)\
               .replace("__SHARED_BASE_CSS__", SHARED_BASE_CSS)\
               .replace("__SHARED_MODALS_HTML__", SHARED_MODALS_HTML)\
               .replace("__SHARED_FOOTER__", shared_footer)
