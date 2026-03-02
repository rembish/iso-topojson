"""Tests for src/category_a.py — direct and subunit extraction."""

from __future__ import annotations

import pytest
from shapely.geometry import box

import geopandas as gpd

from src.category_a import extract_direct, extract_subunit


def test_extract_direct_by_adm0_a3(base_dest, subunits_gdf, units_gdf) -> None:
    """extract_direct finds a feature by adm0_a3."""
    feat = extract_direct(base_dest, subunits_gdf, units_gdf)
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TS"
    assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_extract_direct_not_found(base_dest, subunits_gdf, units_gdf) -> None:
    """extract_direct returns None when adm0_a3 and name are not in either layer."""
    base_dest["adm0_a3"] = "ZZZ"
    base_dest["iso_a3"] = "ZZZ"
    base_dest["name"] = "Nonexistent Country"
    feat = extract_direct(base_dest, subunits_gdf, units_gdf)
    assert feat is None


def test_extract_direct_name_fallback(subunits_gdf, units_gdf) -> None:
    """extract_direct falls back to NAME match when A3 code is absent."""
    dest = {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "direct",
    }
    feat = extract_direct(dest, subunits_gdf, units_gdf)
    assert feat is not None


def test_extract_direct_merge_a3(base_dest, subunits_gdf, units_gdf) -> None:
    """extract_direct merges extra geometries from merge_a3 list."""
    extra_gdf = gpd.GeoDataFrame(
        {"ADM0_A3": ["EXT"], "SU_A3": ["EXT"], "GU_A3": ["EXT"], "ISO_A3": ["EXT"],
         "NAME": ["Extra"]},
        geometry=[box(20, 10, 30, 20)],
        crs="EPSG:4326",
    )
    # Combine extra into subunits
    combined = gpd.GeoDataFrame(
        gpd.pd.concat([subunits_gdf, extra_gdf], ignore_index=True),
        crs="EPSG:4326",
    )
    base_dest["merge_a3"] = ["EXT"]
    feat = extract_direct(base_dest, combined, units_gdf)
    assert feat is not None
    # Merged area should be larger than the original 10x10 box
    from shapely.geometry import shape
    geom = shape(feat["geometry"])
    assert geom.area > 100


def test_extract_subunit_by_su_a3(subunit_dest, subunits_gdf) -> None:
    """extract_subunit finds a feature by su_a3."""
    feat = extract_subunit(subunit_dest, subunits_gdf)
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TG"


def test_extract_subunit_no_su_a3(subunit_dest, subunits_gdf) -> None:
    """extract_subunit returns None when su_a3 key is missing."""
    del subunit_dest["su_a3"]
    feat = extract_subunit(subunit_dest, subunits_gdf)
    assert feat is None


def test_extract_subunit_not_found(subunit_dest, subunits_gdf) -> None:
    """extract_subunit returns None when su_a3 is not in the layer."""
    subunit_dest["su_a3"] = "ZZZ"
    subunit_dest["name"] = "Nonexistent"
    feat = extract_subunit(subunit_dest, subunits_gdf)
    assert feat is None
