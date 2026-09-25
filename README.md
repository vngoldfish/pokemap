# PokéTan Osaka Real-Time Stock & Lottery Tracker

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Hệ thống theo dõi và trực quan hóa dữ liệu tồn kho thẻ bài Pokémon (**Pokémon Card / ポケカ**) thời gian thực tại toàn bộ khu vực **Osaka (~4.050 cửa hàng)** kết hợp lịch mở bán / bốc thăm đặt trước (Lottery Calendar) từ [PokéTan](https://poketan.jp/) và Google Cloud Firestore.

---

## ✨ Tính năng chính

- **Web Dashboard tương tác**:
  - Bản đồ thời gian thực tích hợp GPS người dùng, hiển thị khoảng cách và chỉ đường đến từng cửa hàng.
  - Bộ lọc linh hoạt: Chuỗi cửa hàng (7-Eleven, Lawson, FamilyMart, Joshin, v.v.), trạng thái tồn kho (Có hàng, Hết hàng, Không bán), độ trễ báo cáo (Hot / Cold).
  - Tích hợp **Lịch bốc thăm & Đặt trước (Lottery Calendar)** với đồng hồ đếm ngược tự động cập nhật.
  - Âm thanh và thông báo Popup khi phát hiện điểm bán có hàng mới.
- **Công cụ dòng lệnh CLI**:
  - Tra cứu nhanh tồn kho theo chuỗi hoặc khu vực (Umeda, Namba, Ikuno, Suita,...).
  - Chế độ giám sát liên tục (**Watch Mode**) tự động làm mới theo chu kỳ.
  - Xuất dữ liệu tồn kho ra định dạng **JSON** và **CSV**.
- **Module Python tái sử dụng**:
  - Cung cấp API trực tiếp để tích hợp vào bot Discord, Telegram hoặc hệ thống crawler khác.

---

## 📁 Cấu trúc dự án

```
POKETAN/
├── .gitignore              # Cấu hình bỏ qua cache, file dump HAR và file tạm
├── .gitattributes         # Chuẩn hóa định dạng file và ký tự xuống dòng
├── requirements.txt        # Danh sách thư viện phụ thuộc
├── README.md               # Tài liệu hướng dẫn sử dụng dự án
├── har_analysis_summary.md # Báo cáo phân tích giao thức mạng và API
└── app/
    ├── __init__.py         # Package init
    ├── config.py           # Cấu hình Firebase, API endpoint, chuỗi cửa hàng, mã pack
    ├── fetcher.py          # Tải metadata cửa hàng & stream Firestore realtime
    ├── parser.py           # Giải mã chuỗi trạng thái nén & ánh xạ dữ liệu
    ├── calendar_tracker.py # Theo dõi lịch bốc thăm & pre-order Box thẻ bài
    ├── exporter.py         # Xuất kết quả ra file JSON và CSV
    ├── main.py             # CLI Tool (lọc, tra cứu, xuất file, watch mode)
    ├── web.py              # Web Dashboard với bản đồ GPS và live notifications
    ├── README.md           # Hướng dẫn chi tiết riêng cho module app
    └── data/
        ├── .gitkeep        # Giữ thư mục data trên Git
        └── settings.json   # Lưu tùy chọn cấu hình giao diện mặc định
```

---

## 🚀 Cài đặt & Hướng dẫn sử dụng

### 1. Cài đặt môi trường

Yêu cầu **Python 3.10** trở lên.

```bash
# Clone repository về máy
git clone <URL_REPOSITORY_CUA_BAN>
cd POKETAN

# Khuyến nghị: Tạo môi trường ảo (virtualenv)
python -m venv venv

# Kích hoạt môi trường ảo:
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

---

### 2. Chạy Web Dashboard

Khởi chạy máy chủ web local:

```bash
python -m app.web
```

Truy cập trình duyệt tại: **[http://localhost:8080](http://localhost:8080)**

---

### 3. Chạy giao diện dòng lệnh (CLI)

#### Tra cứu các cửa hàng đang CÓ HÀNG tại Osaka:
```bash
python -m app.main
```

#### Lọc theo chuỗi cửa hàng:
```bash
# 7-Eleven
python -m app.main --chain seven

# Lawson
python -m app.main --chain lawson

# Cửa hàng chuyên bán thẻ bài (Card Shop)
python -m app.main --chain specialty
```
*(Hỗ trợ: `seven`, `lawson`, `familymart`, `ministop`, `specialty`, `joshin`, `edion`, `aeon`, `geo`, `yamada`, `ks`, `toysrus`, `biccamera`, `yodobashi`)*

#### Tìm kiếm theo khu vực hoặc từ khóa:
```bash
python -m app.main --query "梅田"
python -m app.main --query "難波"
```

#### Xem Lịch Bốc Thăm & Đặt trước (Lottery Calendar):
```bash
python -m app.main --calendar
```

#### Chế độ Watch Mode (Giám sát liên tục mỗi 30s):
```bash
python -m app.main --watch --interval 30
```

#### Xuất dữ liệu ra file JSON / CSV:
```bash
python -m app.main --export-json app/data/osaka_in_stock.json --export-csv app/data/osaka_in_stock.csv
```

---

## 🛠️ Sử dụng trong code Python

```python
from app.fetcher import fetch_stores, fetch_realtime_status
from app.parser import merge_stores_with_status

# Tải danh sách cửa hàng
stores = fetch_stores(pref="osaka")

# Lấy dữ liệu tồn kho Firestore thời gian thực
raw_status = fetch_realtime_status(pref="osaka", include_cold=True)

# Giải mã và hợp nhất dữ liệu
records = merge_stores_with_status(stores, raw_status)

# Lọc các cửa hàng đang có hàng
in_stock = [r for r in records if r["status_code"] == "i"]
for s in in_stock:
    print(f"[{s['chain_label']}] {s['name']} - Packs: {s['packs']} - Lúc: {s['reported_at']}")
```

---

## 📄 Bản quyền (License)

Dự án phát hành dưới giấy phép [MIT](LICENSE).
