"""Biomes variant of iso-a2-markers: subdivides traveler-zone countries into biome polygons.

Reads:
  - data/biomes.json            biome definitions (country, name, aurora_zone, ...)
  - data/biome-provinces.json   province-to-biome assignment rules per country
  - output/merged.geojson       country polygon features from the main build step
  - NE ne_10m_admin_1_states_provinces shapefile

Writes:
  - output/iso-a2-markers-biomes.json  combined TopoJSON:
      * biomed countries  → multiple biome polygon features keyed by biome_id
      * other countries   → single country feature (same as iso-a2-markers.json)
      * tiny polygons     → centroid Point markers (500 km² threshold)
      * point-only (UM, BV, HM, TK) → Point markers

Run with: python -m src.build_biomes
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

from .category_b import _match_provinces
from .markers import AREA_THRESHOLD_KM2, inject_points, run_mapshaper
from .utils import to_feature

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

MERGED_GEOJSON = OUTPUT_DIR / "merged.geojson"
POINTS_ONLY_GEOJSON = OUTPUT_DIR / "points-only.geojson"
ADMIN1_SHP = DATA_DIR / "ne_10m_admin_1_states_provinces.shp"

BIOMES_JSON = DATA_DIR / "biomes.json"
BIOME_PROVINCES_JSON = DATA_DIR / "biome-provinces.json"

MERGED_BIOMES_GEOJSON = OUTPUT_DIR / "merged-biomes.geojson"
BIOMES_TOPOJSON = OUTPUT_DIR / "iso-a2-markers-biomes.json"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_biomes() -> dict[str, dict[str, Any]]:
    """Return biomes.json as {biome_id: {country, name, aurora_zone, ...}}."""
    with BIOMES_JSON.open() as f:
        data: dict[str, dict[str, Any]] = json.load(f)
    return data


def load_province_rules() -> dict[str, dict[str, Any]]:
    """Return biome-provinces.json as {iso_a2: {adm0_a3, default, overrides}}."""
    with BIOME_PROVINCES_JSON.open() as f:
        data: dict[str, dict[str, Any]] = json.load(f)
    return data


def load_country_features() -> dict[str, dict[str, Any]]:
    """Load merged.geojson and return {iso_a2: feature_dict}."""
    with MERGED_GEOJSON.open() as f:
        collection = json.load(f)
    result: dict[str, dict[str, Any]] = {}
    for feat in collection["features"]:
        iso_a2 = feat["properties"].get("iso_a2")
        if iso_a2:
            result[iso_a2] = feat
    return result


# ---------------------------------------------------------------------------
# Province assignment
# ---------------------------------------------------------------------------


def _assign_provinces(
    country_admin1: gpd.GeoDataFrame,
    default_biome: str,
    overrides: dict[str, dict[str, Any]],
) -> dict[str, list[int]]:
    """Assign each admin-1 province row index to a biome.

    Processing order (within overrides dict, insertion order preserved):
    1. Name-based: province name matched against ``names`` list.
    2. Lat/lon range: province centroid within the rule's bounds.
    Unmatched provinces go to ``default_biome``.

    Args:
        country_admin1: Admin-1 rows for the target country.
        default_biome: Biome ID to assign unmatched provinces to.
        overrides: {biome_id: rule_dict} — rules for non-default biomes.

    Returns:
        {biome_id: [province_index, ...]} for every biome (including default).
    """
    assignments: dict[str, list[int]] = {default_biome: []}
    for biome_id in overrides:
        assignments[biome_id] = []

    assigned: set[int] = set()

    for biome_id, rule in overrides.items():
        # -- name-based matching ----------------------------------------
        if "names" in rule:
            matched = _match_provinces(country_admin1, rule["names"])
            for idx in matched.index:
                if idx not in assigned:
                    assignments[biome_id].append(int(idx))
                    assigned.add(idx)

        # -- centroid lat/lon threshold matching -------------------------
        has_threshold = any(k in rule for k in ("lat_min", "lat_max", "lon_min", "lon_max"))
        if has_threshold:
            lat_min = rule.get("lat_min", -90.0)
            lat_max = rule.get("lat_max", 90.0)
            lon_min = rule.get("lon_min", -180.0)
            lon_max = rule.get("lon_max", 180.0)
            for idx, row in country_admin1.iterrows():
                if idx in assigned:
                    continue
                centroid = row.geometry.centroid
                lat, lon = centroid.y, centroid.x
                if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                    assignments[biome_id].append(int(idx))
                    assigned.add(idx)

    # Remaining → default
    for idx in country_admin1.index:
        if idx not in assigned:
            assignments[default_biome].append(int(idx))

    return assignments


# ---------------------------------------------------------------------------
# Biome feature builder
# ---------------------------------------------------------------------------


def build_biome_features(
    admin1_gdf: gpd.GeoDataFrame,
    biomes: dict[str, dict[str, Any]],
    province_config: dict[str, dict[str, Any]],
    country_features: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[Any]]]:
    """Build one polygon feature per biome for each biomed country.

    Args:
        admin1_gdf: Natural Earth admin-1 GeoDataFrame.
        biomes: {biome_id: biome_info} from biomes.json.
        province_config: {iso_a2: config} from biome-provinces.json.
        country_features: {iso_a2: feature_dict} from merged.geojson.

    Returns:
        Tuple of:
        - {biome_id: GeoJSON Feature dict} for every successfully built biome.
        - {iso_a2: [geometry, ...]} geometries to union into target countries.
    """
    # Group biomes by country
    by_country: dict[str, list[str]] = {}
    for biome_id, info in biomes.items():
        cc = info["country"]
        by_country.setdefault(cc, []).append(biome_id)

    built: dict[str, dict[str, Any]] = {}
    transfers: dict[str, list[Any]] = {}

    for iso_a2, biome_ids in sorted(by_country.items()):
        config = province_config.get(iso_a2)
        if config is None:
            print(f"  WARN: no biome-provinces config for [{iso_a2}] — skipping")
            continue

        adm0_a3 = config["adm0_a3"]
        default_biome = config["default"]
        overrides = config.get("overrides", {})

        # Filter admin-1 to this country
        country_admin1 = admin1_gdf[admin1_gdf["adm0_a3"] == adm0_a3].copy()
        if len(country_admin1) == 0:
            # Fallback: try iso_a2 field
            country_admin1 = admin1_gdf[admin1_gdf["iso_a2"] == iso_a2].copy()
        if len(country_admin1) == 0:
            print(f"  WARN: no admin-1 provinces found for [{iso_a2}] adm0_a3={adm0_a3}")
            continue

        # Exclude provinces (they have their own ISO features or belong elsewhere)
        exclude_cfg = config.get("exclude")
        if exclude_cfg:
            excluded = _match_provinces(country_admin1, exclude_cfg["names"])
            if len(excluded) > 0:
                target = exclude_cfg.get("transfer_to")
                if target:
                    transfers.setdefault(target, []).extend(
                        g for g in excluded.geometry if g is not None and not g.is_empty
                    )
                    print(f"  [{iso_a2}] transferred {len(excluded)} provinces to [{target}]")
                else:
                    print(f"  [{iso_a2}] excluded {len(excluded)} provinces")
                country_admin1 = country_admin1.drop(excluded.index)

        print(f"  [{iso_a2}] {len(country_admin1)} provinces → {len(biome_ids)} biomes")

        # Assign provinces to biomes
        assignments = _assign_provinces(country_admin1, default_biome, overrides)

        # Get parent country properties for inheritance
        parent = country_features.get(iso_a2, {}).get("properties", {})

        # Dissolve each biome's provinces into a single geometry
        for biome_id in biome_ids:
            indices = assignments.get(biome_id, [])
            if not indices:
                print(f"    WARN: no provinces assigned to {biome_id}")
                continue

            rows = country_admin1.loc[indices]
            try:
                geom = rows.dissolve().geometry.iloc[0]
            except Exception as exc:
                print(f"    WARN: dissolve failed for {biome_id}: {exc}")
                continue

            if geom is None or geom.is_empty:
                print(f"    WARN: empty geometry for {biome_id}")
                continue

            biome_info = biomes[biome_id]
            props: dict[str, Any] = {
                "biome_id": biome_id,
                "iso_a2": iso_a2,
                "iso_a3": parent.get("iso_a3"),
                "iso_n3": parent.get("iso_n3"),
                "name": biome_info["name"],
                "sovereign": parent.get("sovereign"),
                "type": parent.get("type"),
                "aurora_zone": biome_info.get("aurora_zone", False),
            }
            built[biome_id] = to_feature(geom, props)
            print(f"    + {biome_id}: {biome_info['name']} ({len(indices)} provinces)")

        # Fill gaps: disputed areas in the original polygon but not in admin-1
        # Skip if this country has excludes (those gaps are intentional)
        orig_feat = country_features.get(iso_a2)
        if orig_feat and not exclude_cfg:
            orig_geom = shape(orig_feat["geometry"])
            country_biome_ids = [bid for bid in biome_ids if bid in built]
            if country_biome_ids:
                biome_geoms = [shape(built[bid]["geometry"]) for bid in country_biome_ids]
                biome_union = unary_union(biome_geoms)
                gap = orig_geom.difference(biome_union)
                if not gap.is_empty and gap.area > 0.001:
                    # Find nearest biome by centroid distance
                    gap_centroid = gap.centroid
                    nearest_bid = min(
                        country_biome_ids,
                        key=lambda bid: shape(built[bid]["geometry"]).centroid.distance(
                            gap_centroid
                        ),
                    )
                    patched = unary_union([shape(built[nearest_bid]["geometry"]), gap])
                    built[nearest_bid]["geometry"] = mapping(patched)
                    print(f"    ~ patched {gap.area:.3f} sq deg gap into {nearest_bid}")

    return built, transfers


# ---------------------------------------------------------------------------
# Markers logic (inline — matches markers.py threshold)
# ---------------------------------------------------------------------------


def _sanitize(value: Any) -> Any:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def apply_markers(
    features: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split features into polygon (large) and point (small/already-point) lists.

    Args:
        features: GeoJSON Feature dicts (polygon or point geometry).

    Returns:
        (polygon_features, point_features) — two lists of GeoJSON Feature dicts.
    """
    fc = {"type": "FeatureCollection", "features": features}
    gdf = gpd.GeoDataFrame.from_features(fc, crs="EPSG:4326")
    gdf_ea = gdf.to_crs("ESRI:54009")

    polygon_features: list[dict[str, Any]] = []
    point_features: list[dict[str, Any]] = []

    for idx, row in gdf.iterrows():
        geom_wgs = row.geometry
        geom_ea = gdf_ea.loc[idx, "geometry"]
        props = {k: _sanitize(v) for k, v in row.items() if k != "geometry"}

        if geom_wgs is None or geom_wgs.is_empty:
            continue

        if geom_wgs.geom_type == "Point":
            props["marker"] = True
            point_features.append(
                {"type": "Feature", "properties": props, "geometry": mapping(geom_wgs)}
            )
        else:
            area_km2 = geom_ea.area / 1_000_000.0
            if area_km2 < AREA_THRESHOLD_KM2:
                centroid: Point = geom_wgs.centroid
                props["marker"] = True
                props["area_km2"] = round(area_km2, 1)
                point_features.append(
                    {"type": "Feature", "properties": props, "geometry": mapping(centroid)}
                )
            else:
                props["marker"] = False
                props["area_km2"] = round(area_km2, 1)
                polygon_features.append(
                    {"type": "Feature", "properties": props, "geometry": mapping(geom_wgs)}
                )

    return polygon_features, point_features


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the biomes build pipeline."""
    for required in (MERGED_GEOJSON, ADMIN1_SHP, BIOMES_JSON, BIOME_PROVINCES_JSON):
        if not required.exists():
            raise FileNotFoundError(f"Required file missing: {required}\nRun 'make build' first.")

    simplify = os.environ.get("SIMPLIFY", "3%")
    print("=== Biomes build ===\n")

    # Load inputs
    print("Loading source data...")
    biomes = load_biomes()
    province_config = load_province_rules()
    country_features = load_country_features()
    admin1_gdf = gpd.read_file(ADMIN1_SHP)

    biomed_countries = {info["country"] for info in biomes.values()}
    print(f"  Biomes: {len(biomes)} across {len(biomed_countries)} countries")
    print(f"  Country features: {len(country_features)}")
    print(f"  Admin-1 provinces: {len(admin1_gdf)}")

    # Build biome features (biomed countries → N biome polygons each)
    print("\nBuilding biome features...")
    biome_features, transfers = build_biome_features(
        admin1_gdf, biomes, province_config, country_features
    )
    print(f"\n  Built {len(biome_features)} biome features")

    # Apply geometry transfers (e.g. Crimea → Ukraine)
    if transfers:
        from shapely.geometry import shape
        from shapely.ops import unary_union

        for target_iso, geoms in transfers.items():
            feat = country_features.get(target_iso)
            if feat is None:
                print(f"  WARN: transfer target [{target_iso}] not found")
                continue
            original = shape(feat["geometry"])
            merged = unary_union([original, *geoms])
            feat["geometry"] = mapping(merged)
            print(f"  Transferred geometry into [{target_iso}]")

    # Collect non-biomed country features (unchanged from merged.geojson)
    other_features = [
        feat for iso_a2, feat in country_features.items() if iso_a2 not in biomed_countries
    ]
    print(f"  Non-biomed country features: {len(other_features)}")

    # Merge all polygon-type features
    all_features: list[dict[str, Any]] = list(biome_features.values()) + other_features
    print(f"  Total features before markers: {len(all_features)}")

    # Apply markers logic (area threshold → centroid points)
    print(f"\nApplying markers (threshold: {AREA_THRESHOLD_KM2} km²)...")
    polygon_features, point_features = apply_markers(all_features)
    print(f"  Polygons kept:        {len(polygon_features)}")
    print(f"  Converted to points:  {len(point_features)}")

    # Append points-only features (UM, BV, HM, TK)
    if POINTS_ONLY_GEOJSON.exists():
        extra_gdf = gpd.read_file(POINTS_ONLY_GEOJSON)
        for _, row in extra_gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            props = {k: _sanitize(v) for k, v in row.items() if k != "geometry"}
            props["marker"] = True
            point_features.append(
                {"type": "Feature", "properties": props, "geometry": mapping(geom)}
            )
        print(f"  Points-only extras:   {len(extra_gdf)}")

    # Write merged-biomes.geojson (polygons only, for mapshaper)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    polygon_collection = {"type": "FeatureCollection", "features": polygon_features}
    with MERGED_BIOMES_GEOJSON.open("w") as f:
        json.dump(polygon_collection, f)
    size_mb = MERGED_BIOMES_GEOJSON.stat().st_size / (1024 * 1024)
    print(f"\nWrote {MERGED_BIOMES_GEOJSON} ({size_mb:.1f} MB)")

    # Run mapshaper (simplify + TopoJSON conversion)
    run_mapshaper(MERGED_BIOMES_GEOJSON, BIOMES_TOPOJSON, simplify=simplify)

    # Inject point markers into TopoJSON
    inject_points(BIOMES_TOPOJSON, point_features)
    print(f"  Injected {len(point_features)} point markers into topology")

    # Summary
    total = len(polygon_features) + len(point_features)
    size_kb = BIOMES_TOPOJSON.stat().st_size / 1024
    print(f"\nOutput: {BIOMES_TOPOJSON}")
    n_poly, n_pts = len(polygon_features), len(point_features)
    print(f"  {total} total features ({n_poly} polygons, {n_pts} points)")
    print(f"  {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
