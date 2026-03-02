"""Shared fixtures for ISO-A2 TopoJSON tests.

All fixtures use synthetic shapely geometries — no real shapefiles required.
"""

from __future__ import annotations

import pytest
from shapely.geometry import box

try:
    import geopandas as gpd

    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

pytestmark = pytest.mark.skipif(not HAS_GEOPANDAS, reason="geopandas not installed")


@pytest.fixture()
def subunits_gdf():
    """Minimal admin_0_map_subunits GeoDataFrame with one feature."""
    return gpd.GeoDataFrame(
        {
            "SU_A3": ["TST"],
            "ADM0_A3": ["TST"],
            "GU_A3": ["TST"],
            "ISO_A3": ["TST"],
            "NAME": ["Testland"],
            "NAME_EN": ["Testland"],
        },
        geometry=[box(10, 10, 20, 20)],
        crs="EPSG:4326",
    )


@pytest.fixture()
def units_gdf():
    """Minimal admin_0_map_units GeoDataFrame with one feature."""
    return gpd.GeoDataFrame(
        {
            "ADM0_A3": ["TST"],
            "SU_A3": ["TST"],
            "GU_A3": ["TST"],
            "ISO_A3": ["TST"],
            "NAME": ["Testland"],
            "NAME_EN": ["Testland"],
        },
        geometry=[box(10, 10, 20, 20)],
        crs="EPSG:4326",
    )


@pytest.fixture()
def admin1_gdf():
    """admin_1 GeoDataFrame with two provinces for the same country."""
    return gpd.GeoDataFrame(
        {
            "adm0_a3": ["TST", "TST"],
            "iso_a2": ["TS", "TS"],
            "name": ["North Province", "South Province"],
            "name_en": ["North Province", "South Province"],
            "NAME": ["North Province", "South Province"],
            "NAME_EN": ["North Province", "South Province"],
        },
        geometry=[box(10, 15, 20, 20), box(10, 10, 20, 15)],
        crs="EPSG:4326",
    )


@pytest.fixture()
def disputed_gdf():
    """Minimal breakaway_disputed_areas GeoDataFrame."""
    return gpd.GeoDataFrame(
        {
            "NAME": ["Disputed Zone"],
            "BRK_NAME": ["Disputed Zone"],
            "NAME_LONG": ["Disputed Zone"],
            "ADMIN": ["Disputed Zone"],
            "ADM0_A3": ["DZT"],
        },
        geometry=[box(12, 12, 14, 14)],
        crs="EPSG:4326",
    )


@pytest.fixture()
def base_dest():
    """Minimal destination config for a direct-strategy country."""
    return {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "direct",
        "adm0_a3": "TST",
    }


@pytest.fixture()
def admin1_dest():
    """Destination config for an admin1-strategy feature."""
    return {
        "iso_a2": "TP",
        "name": "North Province",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "territory",
        "strategy": "admin1",
        "adm0_a3": "TST",
        "admin1": ["North Province"],
    }


@pytest.fixture()
def island_dest():
    """Destination config for an island_bbox-strategy feature."""
    return {
        "iso_a2": "TI",
        "name": "Test Island",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "territory",
        "strategy": "island_bbox",
        "parent_adm0_a3": "TST",
        "bbox": (12.0, 12.0, 18.0, 18.0),
    }


@pytest.fixture()
def subunit_dest():
    """Destination config for a subunit-strategy feature."""
    return {
        "iso_a2": "TG",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "territory",
        "strategy": "subunit",
        "su_a3": "TST",
    }


@pytest.fixture()
def disputed_dest():
    """Destination config for a disputed-strategy feature."""
    return {
        "iso_a2": "TD",
        "name": "Disputed Zone",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "disputed",
        "strategy": "disputed",
        "ne_name": "Disputed Zone",
    }


@pytest.fixture()
def point_dest():
    """Destination config for a point-strategy feature."""
    return {
        "iso_a2": "TK",
        "name": "Tiny Island",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "territory",
        "strategy": "point",
        "lat": -9.2,
        "lon": -171.8,
    }
