"""Main build orchestrator for ISO-A2 TopoJSON.

Loads source data, runs all extractors, and outputs merged.geojson.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd

from .category_a import extract_direct, extract_subunit
from .category_b import extract_admin1
from .category_c import (
    extract_disputed,
    extract_group_remainder,
    extract_island_bbox,
    extract_land_bbox,
    generate_point,
)
from .destinations import get_destinations

if TYPE_CHECKING:
    from .types import IsoDestination, IsoFeature

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def load_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load all source GeoDataFrames.

    Returns:
        A 4-tuple of ``(subunits, units, admin1, disputed)`` GeoDataFrames loaded
        from the Natural Earth shapefiles in ``DATA_DIR``.
    """
    print("Loading source data...")
    subunits = gpd.read_file(DATA_DIR / "ne_10m_admin_0_map_subunits.shp")
    units = gpd.read_file(DATA_DIR / "ne_10m_admin_0_map_units.shp")
    admin1 = gpd.read_file(DATA_DIR / "ne_10m_admin_1_states_provinces.shp")
    disputed = gpd.read_file(DATA_DIR / "ne_10m_admin_0_disputed_areas.shp")

    print(f"  Subunits: {len(subunits)} features")
    print(f"  Units: {len(units)} features")
    print(f"  Admin1: {len(admin1)} features")
    print(f"  Disputed: {len(disputed)} features")

    return subunits, units, admin1, disputed


def build_features(
    subunits: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    admin1: gpd.GeoDataFrame,
    disputed: gpd.GeoDataFrame,
) -> dict[str, IsoFeature]:
    """Build all ISO alpha-2 features.

    Uses a two-pass approach: first builds all features whose extraction
    does not depend on previously built features; then builds
    ``group_remainder`` features that subtract already-built geometries.

    Args:
        subunits: Natural Earth admin_0_map_subunits GeoDataFrame.
        units: Natural Earth admin_0_map_units GeoDataFrame.
        admin1: Natural Earth admin_1_states_provinces GeoDataFrame.
        disputed: Natural Earth breakaway_disputed_areas GeoDataFrame.

    Returns:
        Dict mapping iso_a2 to GeoJSON Feature dict for all successfully
        built features.
    """
    destinations = get_destinations()
    print(f"\nBuilding {len(destinations)} ISO alpha-2 destinations...")

    built: dict[str, IsoFeature] = {}
    deferred: list[IsoDestination] = []

    # First pass: build all non-dependent features
    for dest in destinations:
        strategy: str = dest.get("strategy", "direct")

        if strategy == "group_remainder":
            deferred.append(dest)
            continue

        feature = _extract_feature(dest, strategy, subunits, units, admin1, disputed, built)

        if feature:
            built[dest["iso_a2"]] = feature
        else:
            print(f"  FAILED: [{dest['iso_a2']}] {dest['name']} (strategy={strategy})")

    # Second pass: build group_remainder features (depend on first pass results)
    for dest in deferred:
        feature = extract_group_remainder(dest, subunits, units, built, disputed)
        if feature:
            built[dest["iso_a2"]] = feature
        else:
            print(f"  FAILED: [{dest['iso_a2']}] {dest['name']} (group_remainder)")

    return built


def _extract_feature(
    dest: IsoDestination,
    strategy: str,
    subunits: gpd.GeoDataFrame,
    units: gpd.GeoDataFrame,
    admin1: gpd.GeoDataFrame,
    disputed: gpd.GeoDataFrame,
    built: dict[str, IsoFeature],
) -> IsoFeature | None:
    """Dispatch to the appropriate extraction function based on strategy.

    Args:
        dest: Destination config dict from ``get_destinations()``.
        strategy: Extraction strategy string from the config.
        subunits: Natural Earth admin_0_map_subunits GeoDataFrame.
        units: Natural Earth admin_0_map_units GeoDataFrame.
        admin1: Natural Earth admin_1_states_provinces GeoDataFrame.
        disputed: Natural Earth breakaway_disputed_areas GeoDataFrame.
        built: Dict of already-built features keyed by iso_a2.

    Returns:
        A GeoJSON Feature dict, or None if extraction fails.
    """
    iso_a2 = dest["iso_a2"]
    name = dest["name"]

    if strategy == "direct":
        return extract_direct(dest, subunits, units, disputed)

    elif strategy == "subunit":
        return extract_subunit(dest, subunits)

    elif strategy == "admin1":
        return extract_admin1(dest, admin1, subunits, units)

    elif strategy == "disputed":
        return extract_disputed(dest, disputed)

    elif strategy == "island_bbox":
        return extract_island_bbox(dest, subunits, units, admin1)

    elif strategy == "land_bbox":
        return extract_land_bbox(dest)

    elif strategy == "point":
        return generate_point(dest)

    else:
        print(f"  Unknown strategy '{strategy}' for [{iso_a2}] {name}")
        return None


def write_geojson(features: dict[str, IsoFeature], output_path: Path) -> None:
    """Write features dict to a GeoJSON FeatureCollection.

    Args:
        features: Dict mapping iso_a2 to GeoJSON Feature dict.
        output_path: Destination file path (parent directories created if needed).
    """
    sorted_features = [features[k] for k in sorted(features.keys())]

    collection = {
        "type": "FeatureCollection",
        "features": sorted_features,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(collection, f)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nWrote {len(sorted_features)} features to {output_path} ({size_mb:.1f} MB)")


def main() -> None:
    """Orchestrate the full build pipeline."""
    subunits, units, admin1, disputed = load_data()
    features = build_features(subunits, units, admin1, disputed)

    total = len(features)
    destinations = get_destinations()
    expected = len(destinations)
    missing = expected - total
    print(f"\nBuilt {total}/{expected} features ({missing} missing)")

    if missing > 0:
        all_codes = {d["iso_a2"] for d in destinations}
        built_codes = set(features.keys())
        missing_codes = sorted(all_codes - built_codes)
        dest_map = {d["iso_a2"]: d for d in destinations}
        print("Missing destinations:")
        for code in missing_codes:
            d = dest_map.get(code, {})
            print(f"  [{code}] {d.get('name', '???')} (strategy={d.get('strategy', '???')})")

    # Separate markers-only features (e.g. UM, BV, HM): these appear only in
    # the markers variant (iso-a2-markers.json), not in the full iso-a2.json.
    markers_only_codes = {d["iso_a2"] for d in destinations if d.get("markers_only")}
    polygon_features = {k: v for k, v in features.items() if k not in markers_only_codes}
    points_only_features = {k: v for k, v in features.items() if k in markers_only_codes}

    write_geojson(polygon_features, OUTPUT_DIR / "merged.geojson")

    if points_only_features:
        write_geojson(points_only_features, OUTPUT_DIR / "points-only.geojson")


if __name__ == "__main__":
    main()
