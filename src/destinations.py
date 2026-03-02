"""ISO destination definitions — loaded from regions.csv."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import IsoDestination

REGIONS_CSV = Path(__file__).resolve().parent.parent / "regions.csv"


def get_destinations() -> list[IsoDestination]:
    """Return all ISO alpha-2 destinations as dicts with extraction config.

    Reads ``regions.csv`` from the project root and parses each row into a
    destination config dict.  Strategy-specific columns (adm0_a3, su_a3,
    admin1_names, bbox, etc.) are only included in the dict when non-empty.

    Returns:
        List of destination config dicts, one per ISO alpha-2 entry, sorted by
        ``iso_a2``.
    """
    results: list[IsoDestination] = []

    with REGIONS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d: dict[str, Any] = {
                "iso_a2": row["iso_a2"],
                "name": row["name"],
                "iso_a3": row["iso_a3"] or None,
                "iso_n3": int(row["iso_n3"]) if row["iso_n3"] else None,
                "sovereign": row["sovereign"],
                "type": row["type"],
                "strategy": row["strategy"] or "direct",
            }

            # Strategy-specific fields — only added when present in CSV
            if row.get("adm0_a3"):
                d["adm0_a3"] = row["adm0_a3"]
            if row.get("su_a3"):
                d["su_a3"] = row["su_a3"]
            if row.get("admin1_names"):
                d["admin1"] = [n.strip() for n in row["admin1_names"].split(";") if n.strip()]
            if row.get("parent_adm0_a3"):
                d["parent_adm0_a3"] = row["parent_adm0_a3"]
            if row.get("bbox"):
                parts = [float(x) for x in row["bbox"].split(",")]
                d["bbox"] = tuple(parts)  # (west, south, east, north)
            if row.get("point_lat"):
                d["lat"] = float(row["point_lat"])
            if row.get("point_lon"):
                d["lon"] = float(row["point_lon"])
            if row.get("subtract_codes"):
                d["subtract_codes"] = [
                    c.strip() for c in row["subtract_codes"].split(";") if c.strip()
                ]
            if row.get("disputed_name"):
                d["ne_name"] = row["disputed_name"]
            if row.get("merge_a3"):
                d["merge_a3"] = [c.strip() for c in row["merge_a3"].split(";") if c.strip()]
            if row.get("merge_disputed"):
                d["merge_disputed"] = [
                    n.strip() for n in row["merge_disputed"].split(";") if n.strip()
                ]
            if row.get("markers_only"):
                d["markers_only"] = True

            results.append(d)

    return results
