"""
Exporter module to export stock data to JSON or CSV format.
"""

import json
import csv
from typing import List, Dict, Any


def export_to_json(records: List[Dict[str, Any]], filepath: str) -> None:
    """Save records as JSON."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def export_to_csv(records: List[Dict[str, Any]], filepath: str) -> None:
    """Save records as CSV."""
    if not records:
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            f.write("")
        return

    fieldnames = [
        "id",
        "name",
        "chain_label",
        "status_label",
        "reported_at",
        "confirms",
        "onsite",
        "packs",
        "address",
        "lat",
        "lng",
        "is_hot"
    ]

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = dict(r)
            row["packs"] = ", ".join(r.get("packs", []))
            writer.writerow(row)
