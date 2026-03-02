"""Category C: Custom GIS work — disputed territories, island extractions,
group remainders, and point markers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shapely.geometry import Point
from shapely.geometry import box as shapely_box
from shapely.ops import unary_union

from .utils import (
    extract_polygons_by_bbox,
    get_country_geom,
    make_properties,
    to_feature,
)

if TYPE_CHECKING:
    import geopandas as gpd

    from .types import Bbox, IsoDestination, IsoFeature

_LAND_SHP = Path(__file__).resolve().parent.parent / "data" / "ne_10m_land.shp"


def extract_disputed(
    dest: IsoDestination,
    disputed_gdf: gpd.GeoDataFrame,
) -> IsoFeature | None:
    """Extract a feature from NE breakaway_disputed_areas layer.

    Uses ``ne_name`` from the destination config (falls back to ``name``) to
    search across NAME, BRK_NAME, NAME_LONG, and ADMIN fields.

    Args:
        dest: Destination config dict from ``get_destinations()``.
        disputed_gdf: Natural Earth breakaway_disputed_areas GeoDataFrame.

    Returns:
        A GeoJSON Feature dict, or None if the disputed feature is not found.
    """
    ne_name: str = str(dest.get("ne_name", dest["name"]))

    geom = _find_disputed_geom(ne_name, disputed_gdf)
    if geom is None:
        print(f"  WARNING: Disputed feature not found: {ne_name}")
        return None

    return to_feature(geom, make_properties(dest))


def _find_disputed_geom(name: str, disputed_gdf: gpd.GeoDataFrame) -> Any | None:
    """Find a geometry from the disputed layer by name or ADM0_A3 code.

    First searches across NAME, BRK_NAME, NAME_LONG, and ADMIN fields using a
    case-insensitive substring match.  Falls back to an exact ``ADM0_A3``
    match.

    Args:
        name: Name/partial name to search, or an exact ADM0_A3 code.
        disputed_gdf: Natural Earth disputed_areas GeoDataFrame.

    Returns:
        A dissolved shapely geometry, or None if not found.
    """
    for field in ["NAME", "BRK_NAME", "NAME_LONG", "ADMIN"]:
        if field not in disputed_gdf.columns:
            continue
        matches = disputed_gdf[disputed_gdf[field].str.lower().str.contains(name.lower(), na=False)]
        if len(matches) > 0:
            return matches.dissolve().geometry.iloc[0]
    # Fall back to exact ADM0_A3 match
    if "ADM0_A3" in disputed_gdf.columns:
        matches = disputed_gdf[disputed_gdf["ADM0_A3"].str.upper() == name.upper()]
        if len(matches) > 0:
            return matches.dissolve().geometry.iloc[0]
    return None


def extract_island_bbox(
    dest: IsoDestination,
    subunits_gdf: gpd.GeoDataFrame,
    units_gdf: gpd.GeoDataFrame,
    admin1_gdf: gpd.GeoDataFrame | None = None,
) -> IsoFeature | None:
    """Extract island polygons from a parent feature by bounding box.

    Finds the parent feature by ``parent_adm0_a3``, then extracts individual
    polygon rings whose centroids fall within the specified bbox.

    Args:
        dest: Destination config dict from ``get_destinations()``.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.
        units_gdf: Natural Earth admin_0_map_units GeoDataFrame.
        admin1_gdf: Unused; kept for API symmetry.

    Returns:
        A GeoJSON Feature dict, or None if the parent or bbox polygons are not found.
    """
    bbox: Bbox | None = dest.get("bbox")
    parent_adm0: str | None = dest.get("parent_adm0_a3")

    if not bbox or not parent_adm0:
        return None

    parent_geom = get_country_geom(parent_adm0, subunits_gdf, units_gdf)
    if parent_geom is None:
        print(f"  WARNING: Parent feature not found for {dest['name']} (parent={parent_adm0})")
        return None

    result = extract_polygons_by_bbox(parent_geom, bbox)
    if result is None:
        print(f"  WARNING: No polygons in bbox for {dest['name']}")
        return None

    return to_feature(result, make_properties(dest))


def extract_group_remainder(
    dest: IsoDestination,
    subunits_gdf: gpd.GeoDataFrame,
    units_gdf: gpd.GeoDataFrame,
    built_features: dict[str, IsoFeature],
    disputed_gdf: gpd.GeoDataFrame | None = None,
) -> IsoFeature | None:
    """Extract a feature that is the remainder after subtracting other ISO features.

    Takes the parent admin_0 feature and subtracts geometries of already-built
    ISO features specified by subtract_codes (iso_a2 values).

    Args:
        dest: Destination config dict from ``get_destinations()``.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.
        units_gdf: Natural Earth admin_0_map_units GeoDataFrame.
        built_features: Dict of already-built features keyed by iso_a2.
        disputed_gdf: Optional disputed_areas GeoDataFrame for ``subtract_disputed``.

    Returns:
        A GeoJSON Feature dict, or None if the country geometry is not found
        or the remainder is empty.
    """
    from shapely.geometry import shape

    adm0 = dest.get("adm0_a3")
    subtract_codes: list[str] = dest.get("subtract_codes", [])

    if not adm0:
        return None

    country_geom = get_country_geom(adm0, subunits_gdf, units_gdf)
    if country_geom is None:
        return None

    subtract_geoms = []

    for code in subtract_codes:
        feat = built_features.get(code)
        if feat:
            subtract_geoms.append(shape(feat["geometry"]))

    if disputed_gdf is not None:
        for lookup in dest.get("subtract_disputed", []):
            extra = _find_disputed_geom(lookup, disputed_gdf)
            if extra is not None:
                subtract_geoms.append(extra)

    if not subtract_geoms:
        return to_feature(country_geom, make_properties(dest))

    subtract_union = unary_union(subtract_geoms)
    result = country_geom.difference(subtract_union.buffer(0))

    if result.is_empty:
        print(f"  WARNING: group_remainder result empty for {dest['name']}")
        return None

    if not result.is_valid:
        result = result.buffer(0)

    return to_feature(result, make_properties(dest))


def extract_land_bbox(dest: IsoDestination) -> IsoFeature | None:
    """Extract a polygon from the NE physical land layer by bounding box.

    Used for territories absent from admin layers (e.g. Bouvet Island) that
    nonetheless appear in the general ``ne_10m_land`` dataset.

    Args:
        dest: Destination config dict; must have a ``bbox`` key.

    Returns:
        A GeoJSON Feature dict, or None if the land layer is missing or
        no geometry falls within the bbox.
    """
    import geopandas as gpd

    bbox: Bbox | None = dest.get("bbox")
    if not bbox:
        return None

    if not _LAND_SHP.exists():
        print(f"  WARNING: ne_10m_land.shp not found — cannot extract {dest['name']}")
        return None

    west, south, east, north = bbox
    bbox_geom = shapely_box(west, south, east, north)

    land_gdf = gpd.read_file(_LAND_SHP)
    matches = land_gdf[land_gdf.intersects(bbox_geom)]
    if matches.empty:
        print(f"  WARNING: No land polygons in bbox for {dest['name']}")
        return None

    merged = unary_union(matches.geometry.tolist())
    clipped = merged.intersection(bbox_geom)
    if clipped.is_empty:
        return None

    return to_feature(clipped, make_properties(dest))


def generate_point(dest: IsoDestination) -> IsoFeature | None:
    """Generate a Point feature at specified coordinates.

    Used for tiny territories like Pitcairn, Tokelau, Bouvet Island, etc.
    that are too small for meaningful polygon representation at world scale.

    Args:
        dest: Destination config dict; must have ``lat`` and ``lon`` keys.

    Returns:
        A GeoJSON Feature dict with a Point geometry, or None if coords are missing.
    """
    lat = dest.get("lat")
    lon = dest.get("lon")

    if lat is None or lon is None:
        return None

    point = Point(lon, lat)
    return to_feature(point, make_properties(dest))
