"""
Main CLI entry point for BAWUI POKE APP - Osaka Real-Time Stock & Lottery Tracker.
Usage:
    python -m app.main
    python -m app.main --status in-stock --chain seven
    python -m app.main --query "梅田" --export-csv osaka_in_stock.csv
    python -m app.main --watch --interval 30
    python -m app.main --calendar
"""

import argparse
import sys
import time
from typing import List, Dict, Any

from .fetcher import fetch_stores, fetch_realtime_status, fetch_firestore_document
from .parser import merge_stores_with_status
from .exporter import export_to_json, export_to_csv
from .config import STATUS_CODE_MAP, CHAIN_NAMES

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def print_summary(records: List[Dict[str, Any]], hot_count: int, total_stores: int) -> None:
    counts = {
        'i': sum(1 for r in records if r['status_code'] == 'i'),
        'o': sum(1 for r in records if r['status_code'] == 'o'),
        'n': sum(1 for r in records if r['status_code'] == 'n'),
        'u': sum(1 for r in records if r['status_code'] == 'u'),
    }

    if RICH_AVAILABLE:
        console = Console()
        content = (
            f"[bold green]🟢 Có hàng (In Stock):[/bold green] {counts['i']}\n"
            f"[bold red]🔴 Hết hàng (Out of Stock):[/bold red] {counts['o']}\n"
            f"[bold white]⚪ Không bán thẻ (Not Handled):[/bold white] {counts['n']}\n"
            f"[dim]--------------------------------------[/dim]\n"
            f"[bold cyan]⚡ Báo cáo 24h gần nhất (Hot):[/bold cyan] {hot_count}\n"
            f"[bold blue]🏢 Tổng số cửa hàng tại Osaka:[/bold blue] {total_stores}"
        )
        console.print(Panel(content, title="[bold yellow]THỐNG KÊ KHO THẺ POKÉMON - OSAKA[/bold yellow]", border_style="cyan"))
    else:
        print("\n" + "=" * 50)
        print(" THỐNG KÊ KHO THẺ POKÉMON - OSAKA")
        print("=" * 50)
        print(f"🟢 Có hàng (In Stock):        {counts['i']}")
        print(f"🔴 Hết hàng (Out of Stock):   {counts['o']}")
        print(f"⚪ Không bán thẻ:             {counts['n']}")
        print("-" * 50)
        print(f"⚡ Báo cáo 24h qua (Hot):     {hot_count}")
        print(f"🏢 Tổng cửa hàng tại Osaka:   {total_stores}")
        print("=" * 50 + "\n")


def print_records_table(records: List[Dict[str, Any]], limit: int = 50) -> None:
    if not records:
        print("Không tìm thấy cửa hàng nào phù hợp với bộ lọc.")
        return

    display_records = records[:limit]

    if RICH_AVAILABLE:
        console = Console()
        table = Table(
            title=f"Danh Sách Cửa Hàng (Hiển thị {len(display_records)}/{len(records)})",
            box=box.ROUNDED,
            header_style="bold magenta",
            show_lines=True
        )

        table.add_column("Trạng Thái", justify="center", width=12)
        table.add_column("Tên Cửa Hàng", style="bold white", min_width=22)
        table.add_column("Chuỗi", style="cyan", width=14)
        table.add_column("Pack Có Sẵn", style="yellow", min_width=16)
        table.add_column("Xác Nhận", justify="center", width=10)
        table.add_column("Thời Gian", style="green", width=19)
        table.add_column("Địa Chỉ", style="dim", min_width=30)

        for r in display_records:
            status_text = f"{r['status_symbol']} {r['status_label'].split('(')[0].strip()}"
            packs_str = ", ".join(r['packs']) if r['packs'] else (r['packs_raw'] or "-")
            conf_str = f"{r['confirms']} ng" + (" (tại chỗ)" if r['onsite'] else "")

            table.add_row(
                status_text,
                r['name'],
                r['chain_label'].split('(')[0].strip(),
                packs_str,
                conf_str,
                r['reported_at'],
                r['address']
            )

        console.print(table)
    else:
        print(f"\n--- DANH SÁCH CỬA HÀNG ({len(display_records)}/{len(records)}) ---")
        for i, r in enumerate(display_records, 1):
            packs = f" | Packs: {', '.join(r['packs'])}" if r['packs'] else ""
            onsite = " (Xác nhận tại chỗ)" if r['onsite'] else ""
            print(f"[{i}] {r['status_symbol']} {r['name']} ({r['chain_label'].split('(')[0].strip()})")
            print(f"    Trạng thái: {r['status_label']}{packs}")
            print(f"    Báo cáo lúc: {r['reported_at']} ({r['confirms']} người xác nhận{onsite})")
            print(f"    Địa chỉ: {r['address']}")
            print()


def run_tracker(args: argparse.Namespace) -> List[Dict[str, Any]]:
    # 1. Fetch store metadata
    stores = fetch_stores(pref="osaka", force_refresh=args.no_cache)

    # 2. Fetch real-time status
    hot_data = fetch_firestore_document("status/osaka")
    hot_keys = set(hot_data.keys())

    if args.status == "in-stock" and not args.include_cold:
        # Fast path: hot data usually contains in-stock updates
        raw_status = hot_data
    else:
        cold_data = {}
        try:
            cold_data = fetch_firestore_document("status/osaka_cold")
        except Exception:
            pass
        raw_status = {**cold_data, **hot_data}

    # 3. Merge and decode
    records = merge_stores_with_status(stores, raw_status, hot_keys=hot_keys)

    # 4. Filter
    filtered = []
    for r in records:
        # Filter status
        if args.status == "in-stock" and r["status_code"] != "i":
            continue
        elif args.status == "out-of-stock" and r["status_code"] != "o":
            continue
        elif args.status == "not-handled" and r["status_code"] != "n":
            continue

        # Filter chain
        if args.chain and r["chain"] != args.chain.lower():
            continue

        # Filter search query
        if args.query:
            q = args.query.lower()
            name = (r["name"] or "").lower()
            addr = (r["address"] or "").lower()
            if q not in name and q not in addr:
                continue

        filtered.append(r)

    # Sort: most recent reports first
    filtered.sort(key=lambda x: x["timestamp"], reverse=True)

    # 5. Output
    print_summary(records, hot_count=len(hot_keys), total_stores=len(stores))
    print_records_table(filtered, limit=args.limit)

    # 6. Export if requested
    if args.export_json:
        export_to_json(filtered, args.export_json)
        print(f"Đã xuất {len(filtered)} bản ghi ra file JSON: {args.export_json}")

    if args.export_csv:
        export_to_csv(filtered, args.export_csv)
        print(f"Đã xuất {len(filtered)} bản ghi ra file CSV: {args.export_csv}")

    return filtered


def main() -> None:
    # Ensure UTF-8 output on Windows console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="BAWUI POKE APP - Osaka Real-Time Stock & Lottery Tracker")
    parser.add_argument(
        "--status", "-s",
        choices=["in-stock", "out-of-stock", "not-handled", "all"],
        default="in-stock",
        help="Lọc theo trạng thái kho hàng (mặc định: in-stock - đang có hàng)"
    )
    parser.add_argument(
        "--chain", "-c",
        help=f"Lọc theo chuỗi cửa hàng ({', '.join(CHAIN_NAMES.keys())})"
    )
    parser.add_argument(
        "--query", "-q",
        help="Tìm kiếm theo tên cửa hàng hoặc khu vực/địa chỉ (VD: 梅田, 難波, 生野)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=30,
        help="Số lượng kết quả tối đa hiển thị (mặc định: 30)"
    )
    parser.add_argument(
        "--include-cold",
        action="store_true",
        default=True,
        help="Bao gồm cả dữ liệu lịch sử > 24h trước (mặc định: True)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Tải lại danh sách metadata cửa hàng thay vì dùng cache"
    )
    parser.add_argument(
        "--export-json",
        help="Đường dẫn file để xuất dữ liệu ra JSON"
    )
    parser.add_argument(
        "--export-csv",
        help="Đường dẫn file để xuất dữ liệu ra CSV"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Chế độ theo dõi liên tục thời gian thực"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Khoảng thời gian polling (giây) khi dùng --watch (mặc định: 30s)"
    )
    parser.add_argument(
        "--calendar",
        action="store_true",
        help="Xem lịch bốc thăm và đặt trước thẻ bài Pokémon (Lottery Calendar)"
    )
    parser.add_argument(
        "--include-expired",
        action="store_true",
        help="Bao gồm cả các sự kiện bốc thăm đã quá hạn (mặc định: False - ẩn đi)"
    )

    args = parser.parse_args()

    if args.calendar:
        from .calendar_tracker import fetch_calendar_events
        all_events = fetch_calendar_events(include_expired=True)
        if args.include_expired:
            events = all_events
            title_suffix = "Tất cả sự kiện (Bao gồm cả đã quá hạn)"
        else:
            events = [e for e in all_events if not e["is_expired"]]
            title_suffix = "Đang mở & Sắp diễn ra (Ẩn quá hạn)"

        expired_count = sum(1 for e in all_events if e["is_expired"])

        if RICH_AVAILABLE:
            console = Console()
            table = Table(
                title=f"Lịch Bốc Thăm & Đặt Trước Thẻ Pokémon - {title_suffix} ({len(events)} sự kiện)",
                box=box.ROUNDED,
                header_style="bold magenta",
                show_lines=True
            )
            table.add_column("Trạng Thái", justify="center", width=22)
            table.add_column("Nhà Bán Lẻ / Sự Kiện", style="bold white", min_width=24)
            table.add_column("Loại", style="cyan", width=16)
            table.add_column("Sản Phẩm", style="yellow", min_width=24)
            table.add_column("Link / Ghi Chú", style="dim", min_width=32)

            for e in events:
                prods = ", ".join(e["products"])
                note_str = e["url"] if e["url"] else e["note"][:60] + "..."
                table.add_row(
                    e["category_label"],
                    e["title"],
                    e["type_label"],
                    prods,
                    note_str
                )
            console.print(table)
            if not args.include_expired and expired_count > 0:
                console.print(f"[dim]💡 Đang ẩn [bold]{expired_count}[/bold] sự kiện đã quá hạn. Chạy với [bold cyan]--include-expired[/bold cyan] để xem lại.[/dim]\n")
        else:
            print(f"\n--- LỊCH BỐC THĂM & ĐẶT TRƯỚC THẺ POKÉMON - {title_suffix} ({len(events)} sự kiện) ---")
            for e in events:
                print(f"[{e['category_label']}] {e['title']} ({e['type_label']})")
                print(f"  Sản phẩm: {', '.join(e['products'])}")
                if e['url']:
                    print(f"  Link: {e['url']}")
                print(f"  Ghi chú: {e['note'][:80]}...\n")
            if not args.include_expired and expired_count > 0:
                print(f"💡 Đang ẩn {expired_count} sự kiện đã quá hạn. Chạy với '--include-expired' để xem lại.\n")
        return

    if args.watch:
        from .calendar_tracker import fetch_calendar_events
        print(f"👀 Bắt đầu chế độ theo dõi thời gian thực (chu kỳ {args.interval}s)...")
        print("   - Đang canh chừng: Báo cáo có hàng tại 4,050 cửa hàng Osaka")
        print("   - Đang canh chừng: Quản trị viên đăng Lịch Bốc Thăm / Sự Kiện mới")
        print("   - Nhấn Ctrl+C để dừng bất cứ lúc nào.\n")

        prev_stock_ids = set()
        prev_cal_ids = set()
        first_run = True

        try:
            while True:
                # 1. Check store stock
                results = run_tracker(args)
                current_in_stock = {r["id"]: r for r in results if r["status_code"] == "i"}

                if not first_run:
                    new_arrivals = [r for sid, r in current_in_stock.items() if sid not in prev_stock_ids]
                    if new_arrivals:
                        try:
                            import winsound
                            winsound.Beep(1200, 300)
                            winsound.Beep(1600, 400)
                        except Exception:
                            print("\a")
                        
                        print("\n" + "🔥" * 30)
                        print(f"🔥 CẢNH BÁO: PHÁT HIỆN {len(new_arrivals)} CỬA HÀNG VỪA BÁO CÓ HÀNG!")
                        print("🔥" * 30)
                        for a in new_arrivals:
                            packs_str = f" [Packs: {', '.join(a['packs'])}]" if a['packs'] else ""
                            print(f"  -> 🟢 {a['name']} ({a['chain_label']}){packs_str}")
                            print(f"     📍 {a['address']}")
                            print(f"     ⏱ Thời gian: {a['reported_at']}")
                        print("-" * 60 + "\n")

                prev_stock_ids = set(current_in_stock.keys())

                # 2. Check Calendar & Lottery Events from Admin
                try:
                    cal_events = fetch_calendar_events(include_expired=True)
                    current_cal_ids = {e["id"]: e for e in cal_events if e.get("id")}
                    if not first_run:
                        new_events = [e for eid, e in current_cal_ids.items() if eid not in prev_cal_ids]
                        if new_events:
                            try:
                                import winsound
                                winsound.Beep(900, 200)
                                winsound.Beep(1200, 200)
                                winsound.Beep(1500, 400)
                            except Exception:
                                print("\a")

                            print("\n" + "🎉" * 30)
                            print(f"🎉 CẢNH BÁO: QUẢN TRỊ VIÊN VỪA ĐĂNG {len(new_events)} LỊCH BỐC THĂM / SỰ KIỆN MỚI!")
                            print("🎉" * 30)
                            for ne in new_events:
                                print(f"  -> 🎁 {ne['title']} ({ne['type_label']})")
                                print(f"     📦 Sản phẩm: {', '.join(ne['products'])}")
                                print(f"     ⏰ Trạng thái: {ne['category_label']}")
                                if ne.get("url"):
                                    print(f"     🔗 Link: {ne['url']}")
                                if ne.get("note"):
                                    print(f"     📝 Ghi chú: {ne['note'][:100]}")
                            print("-" * 60 + "\n")

                    prev_cal_ids = set(current_cal_ids.keys())
                except Exception as ce:
                    pass

                first_run = False
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nĐã dừng chế độ theo dõi.")
    else:
        run_tracker(args)


if __name__ == "__main__":
    main()
