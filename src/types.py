"""Shared type aliases and TypedDicts for ISO-A2 TopoJSON build."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

# ---------------------------------------------------------------------------
# Primitive aliases
# ---------------------------------------------------------------------------

type Bbox = tuple[float, float, float, float]  # (west, south, east, north)
type Coordinate = tuple[float, float]
type CoordList = list[Coordinate]
type GeoJsonProperties = dict[str, str | int | float | None]

# A complete GeoJSON Feature dict as produced by to_feature()
type IsoFeature = dict[str, Any]

# A merged destination config dict as returned by get_destinations()
type IsoDestination = dict[str, Any]

# ---------------------------------------------------------------------------
# Extraction strategy literals
# ---------------------------------------------------------------------------

type ExtractionStrategy = Literal[
    "direct",
    "subunit",
    "admin1",
    "group_remainder",
    "disputed",
    "island_bbox",
    "land_bbox",
    "point",
]

# ---------------------------------------------------------------------------
# Feature properties TypedDict
# ---------------------------------------------------------------------------


class IsoBaseProps(TypedDict):
    """Standard properties carried by every ISO output feature."""

    iso_a2: str
    iso_a3: str | None
    iso_n3: int | None
    name: str
    sovereign: str
    type: Literal["country", "territory", "disputed", "dependency"]


# ---------------------------------------------------------------------------
# Conditional imports (type-checking only)
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    import geopandas as gpd

    GeoDataFrame = gpd.GeoDataFrame
