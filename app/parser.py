"""
Data parser module for PokéTan Osaka Stock Tracker
Decodes compressed status strings, confirmations, pack tags, and joins with store metadata.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from .config import (
    STATUS_CODE_MAP,
    CHAIN_NAMES,
    PACK_CODES
)

CONFIRMATION_REGEX = re.compile(r"^(\d+)(g?)(?::([0-9a-z]*))?$")


def parse_confirmation_tag(c_val: str) -> Dict[str, Any]:
    """
    Parse {store_id}_c confirmation tag.
    Examples:
      - '1' -> 1 confirmation, not onsite, no pack tag
      - '2g' -> 2 confirmations, onsite (tại chỗ)
      - '3g:es' -> 3 confirmations, onsite, packs 'e' and 's'
    """
    if not c_val or not isinstance(c_val, str):
        return {
            "confirms": 1,
            "onsite": False,
            "packs_raw": "",
            "packs_decoded": []
        }

    match = CONFIRMATION_REGEX.match(c_val)
    if not match:
        return {
            "confirms": 1,
            "onsite": False,
            "packs_raw": c_val,
            "packs_decoded": []
        }

    count_str, onsite_flag, packs_str = match.groups()
    confirms = max(1, int(count_str)) if count_str else 1
    onsite = bool(onsite_flag)
    packs_raw = packs_str or ""

    packs_decoded = [
        PACK_CODES.get(char, f"Pack ({char})")
        for char in packs_raw
        if char in PACK_CODES
    ]

    return {
        "confirms": confirms,
        "onsite": onsite,
        "packs_raw": packs_raw,
        "packs_decoded": packs_decoded
    }


def parse_store_status(val: str, conf_val: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Parse status value string:
    e.g. 'i1790115216' -> code: 'i', timestamp: 1790115216
    """
    if not isinstance(val, str) or len(val) < 2:
        return None

    raw_char = val[0]
    code = raw_char.lower()
    ts_str = val[1:]

    if code not in STATUS_CODE_MAP or not ts_str.isdigit():
        return None

    status_meta = STATUS_CODE_MAP[code]
    timestamp = int(ts_str)
    try:
        report_dt = datetime.fromtimestamp(timestamp)
        report_time_str = report_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        report_time_str = str(timestamp)

    conf_info = parse_confirmation_tag(conf_val or "")

    return {
        "status_code": code,
        "status_key": status_meta["key"],
        "status_label": status_meta["label"],
        "status_symbol": status_meta["symbol"],
        "disputed": (raw_char != code),
        "timestamp": timestamp,
        "reported_at": report_time_str,
        "confirms": conf_info["confirms"],
        "onsite": conf_info["onsite"],
        "packs_raw": conf_info["packs_raw"],
        "packs": conf_info["packs_decoded"]
    }


def merge_stores_with_status(
    stores: Dict[str, Dict[str, Any]],
    raw_status: Dict[str, Any],
    hot_keys: Optional[set] = None
) -> List[Dict[str, Any]]:
    """
    Combine store list with decoded status data.
    """
    results = []

    for key, val in raw_status.items():
        if key.endswith("_c") or key.endswith("_at") or key == "updatedAt":
            continue

        store_id = key
        conf_val = raw_status.get(f"{store_id}_c")
        status_info = parse_store_status(str(val), conf_val)
        if not status_info:
            continue

        store_meta = stores.get(store_id, {})
        chain_key = store_meta.get("chain", "other")
        chain_label = CHAIN_NAMES.get(chain_key, chain_key)

        record = {
            "id": store_id,
            "name": store_meta.get("name", "Cửa hàng không rõ tên"),
            "chain": chain_key,
            "chain_label": chain_label,
            "address": store_meta.get("address", "Chưa có địa chỉ"),
            "lat": store_meta.get("lat"),
            "lng": store_meta.get("lng"),
            "is_hot": bool(hot_keys and store_id in hot_keys),
            **status_info
        }
        results.append(record)

    return results
