"""
Calendar and Lottery Tracker Module for PokéTan
Fetches lottery schedules, invitation registrations, and product release events.
"""

import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from .fetcher import fetch_json

EVENTS_URL = "https://poketan.jp/data/events.json"

PRODUCT_LABELS = {
    "pack": "Gói kỷ niệm 30th (30th CELEBRATION)",
    "eievui": "Premium Deck Set Eevee (エーフィ・ブラッキー)",
    "cardset": "Bộ 9 Thẻ 30th Anniversary (カードセット)",
    "stem": "Stellar Emerald (ストエメ)",
    "futuristic": "30th Futuristic Box"
}

TYPE_LABELS = {
    "invite": "Thư mời mua (Invite)",
    "lottery": "Bốc thăm quyền mua (Lottery)",
    "release": "Lịch phát hành chính thức (Release)"
}


def parse_event_status(event: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """
    Categorize event into:
      - 'OPEN': Đang nhận đăng ký
      - 'UPCOMING': Sắp mở đăng ký
      - 'AWAITING_ANNOUNCE': Hết hạn đăng ký, đang chờ công bố kết quả
      - 'CLOSED': Đã kết thúc
    """
    if today is None:
        today = date.today()

    start_str = event.get("start")
    end_str = event.get("end")
    ev_type = event.get("type", "lottery")

    start_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else None
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else None

    # Handle invitations with no end date
    is_expired = False
    if ev_type == "invite":
        if start_date and today < start_date:
            cat = "UPCOMING"
            cat_label = "Sắp mở"
        else:
            cat = "OPEN"
            cat_label = "Đang nhận mời (Liên tục)"
        days_left = None
    elif end_date:
        if start_date and today < start_date:
            cat = "UPCOMING"
            cat_label = f"Sắp mở ({start_str})"
            days_left = (start_date - today).days
        elif today <= end_date:
            cat = "OPEN"
            days_left = (end_date - today).days
            cat_label = f"Đang mở (Còn {days_left} ngày - Hạn: {end_str})"
        else:
            cat = "EXPIRED"
            cat_label = f"Hết hạn đăng ký ({end_str})"
            days_left = 0
            is_expired = True
    else:
        cat = "OPEN"
        cat_label = "Đang mở"
        days_left = None

    # Decode product labels
    products_raw = event.get("products", [])
    products_decoded = [PRODUCT_LABELS.get(p, p) for p in products_raw]

    return {
        "id": event.get("id"),
        "title": event.get("title"),
        "type": ev_type,
        "type_label": TYPE_LABELS.get(ev_type, ev_type),
        "start": start_str,
        "end": end_str,
        "category": cat,
        "category_label": cat_label,
        "days_left": days_left,
        "is_expired": is_expired,
        "url": event.get("url"),
        "note": event.get("note", ""),
        "products": products_decoded
    }


import time


def fetch_calendar_events(today: Optional[date] = None, include_expired: bool = True) -> List[Dict[str, Any]]:
    """Fetch and parse calendar events from poketan.jp. Returns events with is_expired flag."""
    fresh_url = f"{EVENTS_URL}?_t={int(time.time())}"
    try:
        raw = fetch_json(fresh_url, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})
    except Exception:
        raw = fetch_json(EVENTS_URL)
    events = raw.get("events", [])
    parsed = [parse_event_status(e, today=today) for e in events]
    if not include_expired:
        parsed = [e for e in parsed if not e["is_expired"]]
    return parsed

