"""Shared GIS utilities for ISO-A2 TopoJSON build."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union

if TYPE_CHECKING:
    from pathlib import Path

    import geopandas as gpd

    from .types import Bbox, GeoJsonProperties, IsoDestination, IsoFeature


def dissolve_geometries(geometries: list[Any]) -> Any:
    """Dissolve a list of geometries into a single geometry.

    Args:
        geometries: Shapely geometry objects to union together.

    Returns:
        A single merged shapely geometry.
    """
    return unary_union(geometries)


def extract_polygons_by_bbox(geom: Any, bbox: Bbox) -> Polygon | MultiPolygon | None:
    """Extract individual polygons from a Multi/Polygon whose centroid falls within bbox.

    Args:
        geom: A shapely geometry (Polygon or MultiPolygon).
        bbox: (west, south, east, north) bounding box.

    Returns:
        A MultiPolygon or Polygon of matching sub-polygons, or None if no match.
    """
    w, s, e, n = bbox
    bbox_poly = Polygon([(w, s), (e, s), (e, n), (w, n)])

    if isinstance(geom, Polygon):
        polys: list[Polygon] = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    else:
        return None

    matches = [p for p in polys if bbox_poly.contains(p.centroid)]

    if not matches:
        # Fallback: check intersection instead of centroid containment
        matches = [p for p in polys if bbox_poly.intersects(p)]

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return MultiPolygon(matches)


def load_shapefile(path: Path) -> gpd.GeoDataFrame:
    """Load a shapefile as a GeoDataFrame.

    Args:
        path: Filesystem path to the .shp file.

    Returns:
        A GeoDataFrame with all features from the shapefile.
    """
    import geopandas as gpd

    return gpd.read_file(path)


def to_feature(geometry: Any, properties: GeoJsonProperties) -> IsoFeature:
    """Create a GeoJSON-style feature dict.

    Args:
        geometry: A shapely geometry object.
        properties: Dict of feature properties.

    Returns:
        A GeoJSON Feature dict with ``type``, ``geometry``, and ``properties`` keys.
    """
    return {
        "type": "Feature",
        "geometry": mapping(geometry),
        "properties": properties,
    }


def make_properties(dest: IsoDestination) -> GeoJsonProperties:
    """Create the standard ISO properties dict from a destination config.

    Args:
        dest: Merged destination config dict from ``get_destinations()``.

    Returns:
        Dict with all standard ISO feature properties.
    """
    return {
        "iso_a2": dest["iso_a2"],
        "iso_a3": dest.get("iso_a3"),
        "iso_n3": dest.get("iso_n3"),
        "name": dest["name"],
        "sovereign": dest.get("sovereign"),
        "type": dest.get("type"),
    }


def get_country_geom(
    adm0_a3: str, subunits_gdf: gpd.GeoDataFrame, units_gdf: gpd.GeoDataFrame
) -> Any | None:
    """Get the full country geometry from admin_0 layers by A3 code.

    Searches both map_subunits and map_units GeoDataFrames across the four
    standard A3 code fields and dissolves any multi-row matches into a single
    geometry.

    Args:
        adm0_a3: Three-letter A3 country code to look up.
        subunits_gdf: Natural Earth admin_0_map_subunits GeoDataFrame.
        units_gdf: Natural Earth admin_0_map_units GeoDataFrame.

    Returns:
        A dissolved shapely geometry, or None if not found in either layer.
    """
    for gdf in [subunits_gdf, units_gdf]:
        for field in ["ADM0_A3", "SU_A3", "GU_A3", "ISO_A3"]:
            if field not in gdf.columns:
                continue
            matches = gdf[gdf[field] == adm0_a3]
            if len(matches) > 0:
                return matches.dissolve().geometry.iloc[0]
    return None
