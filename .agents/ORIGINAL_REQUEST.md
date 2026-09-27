# Original User Request

## 2026-09-27T03:38:39Z

This is a focused team task; keep it small and focused.

Thực hiện rà soát và kiểm tra toàn diện hệ thống PokéTan Stock Tracker, tập trung cao độ vào tính toàn vẹn của CSDL SQLite và luồng dữ liệu thời gian thực (JST).

Working directory: c:\Users\Admin\Desktop\project\POKETAN
Integrity mode: development

## Requirements

### R1. Kiểm tra tính toàn vẹn CSDL SQLite & Dữ liệu
Kiểm tra cấu trúc và dữ liệu trong `app/data/pokemap.db`:
- Kiểm tra các bảng `stores` và `store_history`.
- Đảm bảo index duy nhất `idx_hist_unique ON store_history(store_id, timestamp, status_code)` hoạt động chuẩn xác, không còn bản ghi trùng lặp nào.
- Đảm bảo 100% trường `formatted_time` trong database và dữ liệu mới sinh ra đều chuẩn theo Giờ Nhật Bản (JST, UTC+9).
- Kiểm tra tính logic của `created_at` (chỉ những báo cáo thực sự mới phát sinh trong 120s mới có `created_at = now`, các báo cáo lịch sử phải giữ nguyên `timestamp`).

### R2. Kiểm tra Luồng ngầm quét dữ liệu (Background Daemon)
Kiểm tra luồng `telegram_background_watcher()` trong `app/web.py` và các hàm `record_new_report`, `save_bulk_history`:
- Xác nhận daemon quét 5 tỉnh thành (Osaka, Tokyo, Aichi, Kanagawa, Gifu, Mie) đa luồng an toàn, không bị deadlock hoặc khóa database SQLite (`database is locked`).
- Kiểm tra cơ chế backfill lịch sử không gây tràn bản ghi giả vào luồng báo cáo thời gian thực.

### R3. Kiểm tra API Endpoints & Đồng bộ thời gian Client-Server
Kiểm tra các endpoints FastAPI:
- `/api/latest_reports?since=...`: chỉ trả về báo cáo thực sự mới trong thời gian thực.
- `/api/store_history/{store_id}`: trả về đúng lịch sử đầy đủ (lên đến 100 bản ghi) với giờ JST.
- `/api/config`: trả về `serverTime` chính xác để client đồng bộ độ lệch đồng hồ (`serverTimeOffset`).

### R4. Kiểm tra Frontend Map & Danh sách
Kiểm tra mã nguồn `app/templates.py`:
- Không còn bất kỳ lỗi cú pháp JavaScript nào (Console clean 100%).
- Header mới (`#poketan-header.map-top-bar`) hiển thị đúng số liệu `4.050 quán • 🟢 41 có...` và nút `Bộ lọc Bản đồ (地図フィルター)` hoạt động trơn tru.
- Toast thông báo chỉ bật khi có báo cáo mới trong 120 giây và hiển thị `たった今`.

## Acceptance Criteria

### Data & Time Integrity
- [ ] Truy vấn SQLite xác nhận 0 bản ghi duplicate theo `(store_id, timestamp, status_code)`.
- [ ] 100% thời gian hiển thị trong CSDL và API tuân thủ định dạng JST (`%H:%M %d/%m/%Y`), không còn bản ghi UTC lệch 9 tiếng.
- [ ] Trường `created_at` của các bản ghi lịch sử khớp với `timestamp` thực tế, không bị đội lên thời gian hiện tại.

### Concurrency & Daemon Stability
- [ ] Daemon chạy ngầm liên tục mà không gây lỗi `sqlite3.OperationalError: database is locked`.
- [ ] Tất cả các file Python (`web.py`, `db.py`, `fetcher.py`, `parser.py`, `templates.py`) biên dịch sạch sẽ không có cảnh báo nghiêm trọng.

### UI & Real-time Verification
- [ ] Gọi thử các API (`/`, `/thongbao`, `/api/latest_reports`, `/api/store_history/{id}`) đều trả về mã HTTP 200 hợp lệ.
- [ ] Không có lỗi JavaScript trùng lặp biến hay undefined trên cả 2 trang.
