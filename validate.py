"""Validation script for ISO-A2 TopoJSON output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

REQUIRED_PROPS = ["iso_a2", "name", "sovereign", "type"]
SIZE_LIMIT_KB = 400


def _valid_codes() -> set[str]:
    """Return the set of iso_a2 values expected in the polygon output files.

    Excludes ``markers_only`` entries (BV, HM, UM) which appear only in
    ``iso-a2-markers.json``, not in the full ``iso-a2.json``.
    """
    import csv

    regions_csv = Path(__file__).resolve().parent / "regions.csv"
    with regions_csv.open(newline="", encoding="utf-8") as f:
        return {row["iso_a2"] for row in csv.DictReader(f) if not row.get("markers_only")}


def validate_geojson(path: Path) -> bool:
    """Validate the merged GeoJSON file.

    Checks:
    - Feature count matches regions.csv.
    - All iso_a2 values are unique and match regions.csv.
    - All required properties are non-null on every feature.
    - Every feature has a geometry.

    Args:
        path: Path to the ``merged.geojson`` file to validate.

    Returns:
        ``True`` if all checks pass, ``False`` otherwise.
    """
    print(f"Validating {path}...")

    with path.open() as f:
        data = json.load(f)

    features = data.get("features", [])
    expected_codes = _valid_codes()
    print(f"  Features: {len(features)} (expected {len(expected_codes)})")

    codes: set[str] = set()
    errors: list[str] = []
    for feat in features:
        props = feat.get("properties", {})
        code = props.get("iso_a2")

        if code is None:
            errors.append(f"Feature missing iso_a2: {props.get('name', '???')}")
            continue

        if code in codes:
            errors.append(f"Duplicate iso_a2: {code}")
        codes.add(code)

        for prop in REQUIRED_PROPS:
            if props.get(prop) is None:
                errors.append(f"[{code}] {props.get('name', '???')}: missing '{prop}'")

        geom = feat.get("geometry")
        if geom is None:
            errors.append(f"[{code}] {props.get('name', '???')}: missing geometry")

    missing = sorted(expected_codes - codes)
    extra = sorted(codes - expected_codes)

    if missing:
        print(
            f"  Missing codes ({len(missing)}): {missing[:20]}"
            f"{'...' if len(missing) > 20 else ''}"
        )
    if extra:
        print(f"  Extra codes: {extra}")

    for err in errors[:20]:
        print(f"  ERROR: {err}")
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more errors")

    size_kb = path.stat().st_size / 1024
    print(f"  File size: {size_kb:.0f} KB")

    print(f"\n  Summary: {len(features)} features, {len(missing)} missing, {len(errors)} errors")
    return len(errors) == 0 and len(missing) == 0


def validate_topojson(path: Path) -> bool:
    """Validate the final TopoJSON file.

    Checks:
    - Total geometry count across all objects matches regions.csv.
    - File size is within the 400 KB target (warns if exceeded).

    Args:
        path: Path to the ``iso-a2.json`` TopoJSON file to validate.

    Returns:
        ``True`` if the geometry count matches expected, ``False`` otherwise.
    """
    print(f"\nValidating {path}...")

    with path.open() as f:
        data = json.load(f)

    expected_count = len(_valid_codes())
    objects = data.get("objects", {})
    total_features = 0
    for name, obj in objects.items():
        geoms = obj.get("geometries", [])
        total_features += len(geoms)
        print(f"  Object '{name}': {len(geoms)} geometries")

    print(f"  Total features: {total_features}")

    size_kb = path.stat().st_size / 1024
    print(f"  File size: {size_kb:.0f} KB")

    if size_kb > SIZE_LIMIT_KB:
        print(f"  WARNING: File exceeds {SIZE_LIMIT_KB} KB target")

    return total_features == expected_count


def main() -> None:
    """Validate both merged.geojson and iso-a2.json if present.

    Exits with code 1 if any check fails, code 0 if all pass.
    """
    ok = True

    geojson_path = OUTPUT_DIR / "merged.geojson"
    if geojson_path.exists():
        if not validate_geojson(geojson_path):
            ok = False
    else:
        print(f"GeoJSON not found: {geojson_path}")
        ok = False

    topojson_path = OUTPUT_DIR / "iso-a2.json"
    if topojson_path.exists():
        if not validate_topojson(topojson_path):
            ok = False
    else:
        print(f"TopoJSON not found: {topojson_path}")

    if not ok:
        print("\nValidation FAILED")
        sys.exit(1)
    else:
        print("\nValidation PASSED")


if __name__ == "__main__":
    main()
