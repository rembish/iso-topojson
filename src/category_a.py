"""Category A: Direct NE feature extraction (~230+ destinations).

Matches sovereign nations and territories directly from Natural Earth
admin_0_map_subunits or admin_0_map_units layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shapely.ops import unary_union

from .category_c import _find_disputed_geom
from .utils import make_properties, to_feature

if TYPE_CHECKING:
    import geopandas as gpd

    from .types import IsoDestination, IsoFeature


def _find_geom(
    code: str,
    subunits_gdf: gpd.GeoDataFrame,
    units_gdf: gpd.GeoDataFrame,
) -> Any | None:
    """Find a geometry by A3 code from admin_0 layers.

    Searches both GeoDataFrames across four standard A3 field names.
    Dissolves any multi-row match into a single geometry.

    Args:
        code: Three-letter A3 code to search for.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.
        units_gdf: Natural Earth admin_0_map_units GeoDataFrame.

    Returns:
        A dissolved shapely geometry, or None if not found.
    """
    for gdf in [subunits_gdf, units_gdf]:
        for field in ["SU_A3", "ADM0_A3", "ISO_A3", "GU_A3"]:
            if field not in gdf.columns:
                continue
            matches = gdf[gdf[field] == code]
            if len(matches) >= 1:
                return matches.dissolve().geometry.iloc[0]
    return None


def extract_direct(
    dest: IsoDestination,
    subunits_gdf: gpd.GeoDataFrame,
    units_gdf: gpd.GeoDataFrame,
    disputed_gdf: gpd.GeoDataFrame | None = None,
) -> IsoFeature | None:
    """Extract a feature directly from NE admin_0 layers.

    Tries map_subunits first, then falls back to map_units.
    Matches on ADM0_A3, SU_A3, GU_A3, or ISO_A3 against dest's adm0_a3.
    Also tries NAME match as a last resort.

    Optionally merges additional geometries via ``merge_a3`` (admin_0 A3
    codes) and ``merge_disputed`` (name or ADM0_A3 codes from the disputed
    layer).

    Args:
        dest: Destination config dict from ``get_destinations()``.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.
        units_gdf: Natural Earth admin_0_map_units GeoDataFrame.
        disputed_gdf: Optional disputed_areas GeoDataFrame for ``merge_disputed``.

    Returns:
        A GeoJSON Feature dict, or None if the feature could not be found.
    """
    ne_a3 = dest.get("adm0_a3") or dest.get("iso_a3")
    name = dest["name"]

    geom = None

    if ne_a3:
        geom = _find_geom(ne_a3, subunits_gdf, units_gdf)

    # Fallback: try name match
    if geom is None:
        for gdf in [subunits_gdf, units_gdf]:
            if "NAME" in gdf.columns:
                matches = gdf[gdf["NAME"].str.lower() == name.lower()]
                if len(matches) >= 1:
                    geom = matches.dissolve().geometry.iloc[0]
                    break

    if geom is None:
        return None

    parts: list[Any] = [geom]

    # Merge additional admin_0 features
    for code in dest.get("merge_a3", []):
        extra = _find_geom(code, subunits_gdf, units_gdf)
        if extra is not None:
            parts.append(extra)

    # Merge features from the disputed layer
    if disputed_gdf is not None:
        for lookup in dest.get("merge_disputed", []):
            extra = _find_disputed_geom(lookup, disputed_gdf)
            if extra is not None:
                parts.append(extra)

    if len(parts) > 1:
        geom = unary_union(parts)

    return to_feature(geom, make_properties(dest))


def extract_subunit(
    dest: IsoDestination,
    subunits_gdf: gpd.GeoDataFrame,
) -> IsoFeature | None:
    """Extract a specific subunit from NE map_subunits by su_a3 code.

    Used for Gibraltar and Åland Islands.
    Falls back to NAME_EN / NAME match if the SU_A3 lookup fails.

    Args:
        dest: Destination config dict from ``get_destinations()``.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.

    Returns:
        A GeoJSON Feature dict, or None if the subunit could not be found.
    """
    su_a3 = dest.get("su_a3")
    if not su_a3:
        return None

    matches = subunits_gdf[subunits_gdf["SU_A3"] == su_a3]

    if len(matches) == 0:
        # Try NAME_EN or NAME
        for field in ["NAME_EN", "NAME"]:
            if field in subunits_gdf.columns:
                matches = subunits_gdf[subunits_gdf[field].str.lower() == dest["name"].lower()]
                if len(matches) >= 1:
                    break

    if len(matches) == 0:
        return None

    geom = matches.dissolve().geometry.iloc[0]
    return to_feature(geom, make_properties(dest))
