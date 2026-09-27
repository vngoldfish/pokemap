"""
Data fetcher module for PokéTan Osaka Stock Tracker
Fetches static store metadata and real-time Firestore status documents.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from .config import (
    FIRESTORE_BASE_URL,
    FIREBASE_API_KEY,
    STORES_URL_TEMPLATE
)

DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Any:
    """Fetch and decode JSON from a given URL."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP Error {e.code} when requesting {url}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error when requesting {url}: {e.reason}")


def fetch_stores(pref: str = "osaka", cache_dir: Optional[str] = DEFAULT_CACHE_DIR, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Fetch stores metadata for a specific prefecture.
    Caches locally to avoid redundant downloads (e.g. ~880KB for Osaka).
    Returns a dict mapping store ID -> store object.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"stores_{pref}.json")

    stores_list = None
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                stores_list = json.load(f)
        except Exception:
            stores_list = None

    if stores_list is None:
        url = STORES_URL_TEMPLATE.format(pref=pref)
        stores_list = fetch_json(url)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(stores_list, f, ensure_ascii=False, indent=2)

    return {store["id"]: store for store in stores_list}


def parse_firestore_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Firestore REST API fields format:
    {'key': {'stringValue': 'val'}} -> {'key': 'val'}
    """
    result = {}
    for key, val_obj in fields.items():
        if not isinstance(val_obj, dict):
            continue
        if "stringValue" in val_obj:
            result[key] = val_obj["stringValue"]
        elif "integerValue" in val_obj:
            result[key] = int(val_obj["integerValue"])
        elif "booleanValue" in val_obj:
            result[key] = val_obj["booleanValue"]
        elif "timestampValue" in val_obj:
            result[key] = val_obj["timestampValue"]
        elif "nullValue" in val_obj:
            result[key] = None
        else:
            result[key] = val_obj
    return result


def fetch_firestore_document(doc_path: str) -> Dict[str, Any]:
    """Fetch a single Firestore document by its relative path."""
    url = f"{FIRESTORE_BASE_URL}/{doc_path}?key={FIREBASE_API_KEY}"
    doc_json = fetch_json(url)
    fields = doc_json.get("fields", {})
    return parse_firestore_fields(fields)


def fetch_realtime_status(pref: str = "osaka", include_cold: bool = True) -> Dict[str, Any]:
    """
    Fetch real-time stock status from Firestore:
    1. Hot document (status/{pref}): reports updated within the last 24h.
    2. Cold document (status/{pref}_cold): historical reports older than 24h.
    Hot data takes precedence over cold data.
    """
    hot_data = fetch_firestore_document(f"status/{pref}")
    if not include_cold:
        return hot_data

    try:
        cold_data = fetch_firestore_document(f"status/{pref}_cold")
    except Exception:
        cold_data = {}

    # Merge cold first, then override with hot
    merged = {**cold_data, **hot_data}
    return merged


_history_cache: Dict[str, Dict[str, Any]] = {}

def fetch_store_history(store_id: str) -> list:
    """Fetch history reports for a specific store from Firestore subcollection stores/{storeId}/history."""
    import time
    now = time.time()
    clean_id = store_id[:-2] if store_id.endswith("_c") else store_id
    if clean_id in _history_cache:
        cached = _history_cache[clean_id]
        if now - cached["time"] < 30:  # 30 second cache
            return cached["data"]

    import urllib.parse
    clean_id_quoted = urllib.parse.quote(clean_id)
    url = f"{FIRESTORE_BASE_URL}/stores/{clean_id_quoted}/history?key={FIREBASE_API_KEY}&pageSize=100"
    history = []
    try:
        doc_json = fetch_json(url)
        documents = doc_json.get("documents", [])
        for doc in documents:
            fields = parse_firestore_fields(doc.get("fields", {}))
            doc_id = doc.get("name", "").split("/")[-1]
            ts_str = fields.get("timestamp")
            unix_ts = 0
            formatted_time = ""
            if ts_str:
                try:
                    from datetime import datetime as dt_cls, timezone, timedelta
                    JST = timezone(timedelta(hours=9))
                    dt = dt_cls.fromisoformat(ts_str.replace("Z", "+00:00"))
                    unix_ts = int(dt.timestamp())
                    jst_dt = dt.astimezone(JST)
                    formatted_time = jst_dt.strftime("%H:%M %d/%m/%Y")
                except Exception:
                    pass

            raw_status = fields.get("status", "")
            status_code = "u"
            status_label = "Chưa rõ"
            if raw_status in ["in-stock", "i"]:
                status_code = "i"
                status_label = "🟢 Có hàng"
            elif raw_status in ["out-of-stock", "o"]:
                status_code = "o"
                status_label = "🔴 Hết hàng"
            elif raw_status in ["not-handled", "none", "n"]:
                status_code = "n"
                status_label = "⚪ Không bán thẻ"

            note_str = fields.get("note", "")
            packs_list = []
            if isinstance(fields.get("packs"), list):
                packs_list = fields.get("packs")
            elif isinstance(fields.get("p"), list):
                packs_list = fields.get("p")

            # Detect pack tags from note if packs_list is empty
            if not packs_list and note_str:
                from .config import PACK_CODES
                note_lower = note_str.lower()
                for p_code, p_name in PACK_CODES.items():
                    p_name_lower = p_name.lower()
                    aliases = [p_name_lower]
                    if "(" in p_name:
                        aliases.append(p_name[p_name.find("(")+1:p_name.find(")")].lower())
                    if any(a in note_lower for a in aliases):
                        if p_name not in packs_list:
                            packs_list.append(p_name)

            confirms_count = 1
            if fields.get("confirms"):
                try:
                    confirms_count = max(1, int(fields.get("confirms")))
                except Exception:
                    confirms_count = 1
            elif fields.get("count"):
                try:
                    confirms_count = max(1, int(fields.get("count")))
                except Exception:
                    confirms_count = 1

            history.append({
                "id": doc_id,
                "status": raw_status,
                "status_code": status_code,
                "status_label": status_label,
                "note": note_str,
                "packs": packs_list,
                "user": fields.get("user", "匿名トレーナー"),
                "who": str(fields.get("who", ""))[:6] if fields.get("who") else "",
                "onsite": fields.get("os") == 1,
                "confirms": confirms_count,
                "timestamp": unix_ts,
                "formatted_time": formatted_time
            })
        history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    except Exception as e:
        print(f"Error fetching history for store {store_id}:", e)

    _history_cache[store_id] = {"time": now, "data": history}
    return history
