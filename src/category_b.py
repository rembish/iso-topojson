"""Category B: admin_1 extraction and merge.

Selects admin_1 provinces and dissolves them into a single feature.
Used for Åland Islands (Finland admin1) when subunit lookup fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .utils import make_properties, to_feature

if TYPE_CHECKING:
    import geopandas as gpd

    from .types import IsoDestination, IsoFeature


def _match_provinces(
    country_admin1: gpd.GeoDataFrame,
    names: list[str],
) -> gpd.GeoDataFrame:
    """Match province rows by name against a target list.

    Tries exact match on ``name`` and ``name_en``, then case-insensitive
    substring match as a fallback.

    Args:
        country_admin1: Admin1 rows already filtered to the target country.
        names: Province names to match.

    Returns:
        GeoDataFrame subset of matching rows.
    """
    name_fields = [f for f in ["name", "name_en", "NAME", "NAME_EN"] if f in country_admin1.columns]
    matched_rows = []

    for target in names:
        target_lower = target.lower()
        found = False

        # Exact match first
        for field in name_fields:
            rows = country_admin1[country_admin1[field].str.lower() == target_lower]
            if len(rows) > 0:
                matched_rows.append(rows)
                found = True
                break

        # Substring match fallback
        if not found:
            for field in name_fields:
                rows = country_admin1[
                    country_admin1[field].str.lower().str.contains(target_lower, na=False)
                ]
                if len(rows) > 0:
                    matched_rows.append(rows)
                    break

    if not matched_rows:
        import geopandas as gpd

        return gpd.GeoDataFrame()

    import pandas as pd

    combined = pd.concat(matched_rows).drop_duplicates()
    import geopandas as gpd

    return gpd.GeoDataFrame(combined, crs=country_admin1.crs)


def extract_admin1(
    dest: IsoDestination,
    admin1_gdf: gpd.GeoDataFrame,
    subunits_gdf: gpd.GeoDataFrame | None = None,
    units_gdf: gpd.GeoDataFrame | None = None,
) -> IsoFeature | None:
    """Select and dissolve admin_1 provinces into a single feature.

    Uses ``adm0_a3`` to filter the country, then matches province names
    from the ``admin1`` list.

    Args:
        dest: Destination config dict from ``get_destinations()``.
        admin1_gdf: Natural Earth admin_1_states_provinces GeoDataFrame.
        subunits_gdf: Unused; kept for API symmetry.
        units_gdf: Unused; kept for API symmetry.

    Returns:
        A GeoJSON Feature dict, or None if no matching provinces were found.
    """
    adm0 = dest.get("adm0_a3")
    admin1_names: list[str] = dest.get("admin1", [])

    if not adm0 or not admin1_names:
        return None

    # Filter admin1 to the target country
    country_admin1 = admin1_gdf[admin1_gdf["adm0_a3"] == adm0]
    if len(country_admin1) == 0:
        # Try iso_a2 fallback
        iso_a2 = dest.get("iso_a2", "")
        if iso_a2:
            country_admin1 = admin1_gdf[admin1_gdf["iso_a2"] == iso_a2]

    # Match province names
    matched = _match_provinces(country_admin1, admin1_names)

    if len(matched) == 0:
        print(
            f"  WARNING: No admin1 matches for {dest['name']} "
            f"(adm0={adm0}, names={admin1_names})"
        )
        return None

    geom = matched.dissolve().geometry.iloc[0]
    return to_feature(geom, make_properties(dest))
