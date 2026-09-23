# PokéTan Osaka Real-Time Stock Tracker (Python)

Ứng dụng Python theo dõi và trích xuất dữ liệu tồn kho thẻ bài Pokémon (**Pokémon Card / ポケカ**) thời gian thực tại toàn bộ khu vực **Osaka** (~4.050 cửa hàng) từ hệ thống [PokéTan (poketan.jp)](https://poketan.jp/) và Google Cloud Firestore.

---

## 📁 Cấu trúc thư mục `app/`

```
app/
├── __init__.py           # Package init
├── config.py             # Cấu hình API, URL Firestore, mã pack, tên chuỗi cửa hàng
├── fetcher.py            # Module tải metadata cửa hàng và dữ liệu Firestore realtime
├── parser.py             # Giải mã chuỗi trạng thái nén (status, xác nhận, loại pack)
├── calendar_tracker.py   # Module theo dõi lịch bốc thăm & đặt trước thẻ bài (Lottery Calendar)
├── exporter.py           # Xuất dữ liệu ra định dạng JSON và CSV
├── main.py               # Giao diện dòng lệnh CLI (lọc, tìm kiếm, xuất file, watch mode, calendar)
├── web.py                # Web Dashboard tương tác (Bản đồ GPS, Thông báo live, Lịch bốc thăm)
├── data/                 # Thư mục lưu cache và kết quả xuất
│   ├── stores_osaka.json # Cache danh sách 4.050 cửa hàng Osaka
│   ├── osaka_in_stock.json
│   └── osaka_in_stock.csv
└── README.md             # Hướng dẫn sử dụng chi tiết
```

---

## 🚀 Hướng dẫn sử dụng nhanh (CLI)

Chạy trực tiếp từ thư mục gốc của dự án:

### 1. Xem các cửa hàng đang CÓ HÀNG (In Stock) tại Osaka
```bash
python -m app.main
```

### 2. Lọc theo chuỗi cửa hàng (7-Eleven, Lawson, FamilyMart, v.v.)
```bash
# Chỉ xem các cửa hàng 7-Eleven đang có hàng
python -m app.main --chain seven

# Chỉ xem các cửa hàng Lawson
python -m app.main --chain lawson

# Chỉ xem các cửa hàng FamilyMart
python -m app.main --chain familymart

# Chỉ xem các shop chuyên bán thẻ bài (Card Shop)
python -m app.main --chain specialty
```
*Các chuỗi hỗ trợ*: `seven`, `lawson`, `familymart`, `ministop`, `specialty`, `joshin`, `edion`, `aeon`, `geo`, `yamada`, `ks`, `toysrus`, `biccamera`, `yodobashi`.

### 3. Tìm kiếm theo tên cửa hàng hoặc khu vực
```bash
# Tìm các cửa hàng quanh Umeda (梅田)
python -m app.main --query "梅田"

# Tìm các cửa hàng ở Namba (難波)
python -m app.main --query "難波"

# Tìm cửa hàng theo quận (VD: 生野, 吹田, 茨木)
python -m app.main --query "茨木"
```

### 4. Xuất dữ liệu ra file JSON hoặc CSV
```bash
# Xuất danh sách cửa hàng đang có hàng ra cả JSON và CSV
python -m app.main --export-json app/data/osaka_in_stock.json --export-csv app/data/osaka_in_stock.csv

# Xuất toàn bộ tất cả cửa hàng (cả hết hàng và có hàng)
python -m app.main --status all --export-csv app/data/all_osaka_stores.csv
```

### 5. Xem Lịch Bốc Thăm & Đặt Trước (Lottery Calendar)
Theo dõi các đợt mở đăng ký mua Box thẻ Pokémon 30th Anniversary từ Amazon, Nojima, TSUTAYA, GEO, v.v.:
```bash
python -m app.main --calendar
```

### 6. Chế độ giám sát thời gian thực (Watch Mode)
Tự động làm mới và thông báo ngay khi có cửa hàng mới được báo cáo có hàng:
```bash
# Polling kiểm tra mỗi 30 giây
python -m app.main --watch --interval 30
```

### 7. Khởi động Web Dashboard
Giao diện trực quan tích hợp đầy đủ Bản đồ GPS và Lịch bốc thăm:
```bash
python -m app.web
# Mở trình duyệt tại: http://localhost:8080
```

---

## 💻 Sử dụng trong code Python khác

Bạn có thể import các module của `app` vào bất kỳ script nào:

```python
from app.fetcher import fetch_stores, fetch_realtime_status
from app.parser import merge_stores_with_status

# 1. Tải danh sách cửa hàng Osaka (có cache cục bộ)
stores = fetch_stores(pref="osaka")

# 2. Lấy dữ liệu tồn kho Firestore thời gian thực
raw_status = fetch_realtime_status(pref="osaka", include_cold=True)

# 3. Giải mã và gộp dữ liệu
records = merge_stores_with_status(stores, raw_status)

# 4. Lọc các cửa hàng đang có hàng
in_stock_stores = [r for r in records if r["status_code"] == "i"]

for store in in_stock_stores:
    print(f"{store['name']} | Packs: {store['packs']} | Lúc: {store['reported_at']}")
```

---

## 🧩 Giải mã dữ liệu chi tiết

Mỗi cửa hàng trả về đối tượng có cấu trúc đầy đủ:
- `name`: Tên cửa hàng (VD: セブン-イレブン 茨木鮎川１丁目店).
- `chain_label`: Tên chuỗi bán lẻ tiếng Nhật & tiếng Anh.
- `status_label`: `Có hàng (In Stock)`, `Hết hàng (Out of Stock)`, `Không bán thẻ`.
- `packs`: Danh sách các loại pack Pokémon đang có sẵn (VD: `Stellar Emerald (ストエメ)`, `30th Anniversary`, `Sinfonia (シンフォニア)`, `Brave (ブレイブ)`).
- `confirms`: Số lượng người dùng đã xác nhận báo cáo.
- `onsite`: `True` nếu người báo cáo xác nhận trực tiếp tại chỗ (`現地確認あり`).
- `reported_at`: Thời gian báo cáo gần nhất (YYYY-MM-DD HH:MM:SS).
- `address`: Địa chỉ chính xác tại Osaka.
- `lat`, `lng`: Tọa độ vị trí địa lý trên bản đồ.
- `is_hot`: `True` nếu là báo cáo mới cập nhật trong vòng 24 giờ qua.
