"""Tests for src/category_c.py — disputed, island_bbox, point, group_remainder."""

from __future__ import annotations

import pytest
from shapely.geometry import shape

from src.category_c import (
    extract_disputed,
    extract_group_remainder,
    extract_island_bbox,
    generate_point,
)


def test_extract_disputed_found(disputed_dest, disputed_gdf) -> None:
    """extract_disputed finds a feature by ne_name."""
    feat = extract_disputed(disputed_dest, disputed_gdf)
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TD"


def test_extract_disputed_not_found(disputed_dest, disputed_gdf) -> None:
    """extract_disputed returns None when name is not found."""
    disputed_dest["ne_name"] = "Nonexistent Territory"
    feat = extract_disputed(disputed_dest, disputed_gdf)
    assert feat is None


def test_extract_island_bbox_found(island_dest, subunits_gdf, units_gdf) -> None:
    """extract_island_bbox extracts sub-polygons inside the bbox."""
    feat = extract_island_bbox(island_dest, subunits_gdf, units_gdf)
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TI"


def test_extract_island_bbox_no_bbox(island_dest, subunits_gdf, units_gdf) -> None:
    """extract_island_bbox returns None when bbox is missing."""
    del island_dest["bbox"]
    feat = extract_island_bbox(island_dest, subunits_gdf, units_gdf)
    assert feat is None


def test_extract_island_bbox_no_parent(island_dest, subunits_gdf, units_gdf) -> None:
    """extract_island_bbox returns None when parent_adm0_a3 is missing."""
    del island_dest["parent_adm0_a3"]
    feat = extract_island_bbox(island_dest, subunits_gdf, units_gdf)
    assert feat is None


def test_extract_island_bbox_parent_not_found(island_dest, subunits_gdf, units_gdf) -> None:
    """extract_island_bbox returns None when parent feature is not found."""
    island_dest["parent_adm0_a3"] = "ZZZ"
    feat = extract_island_bbox(island_dest, subunits_gdf, units_gdf)
    assert feat is None


def test_generate_point_success(point_dest) -> None:
    """generate_point creates a Point feature at the given coordinates."""
    feat = generate_point(point_dest)
    assert feat is not None
    assert feat["geometry"]["type"] == "Point"
    assert list(feat["geometry"]["coordinates"]) == [-171.8, -9.2]
    assert feat["properties"]["iso_a2"] == "TK"


def test_generate_point_missing_lat(point_dest) -> None:
    """generate_point returns None when lat is missing."""
    del point_dest["lat"]
    feat = generate_point(point_dest)
    assert feat is None


def test_generate_point_missing_lon(point_dest) -> None:
    """generate_point returns None when lon is missing."""
    del point_dest["lon"]
    feat = generate_point(point_dest)
    assert feat is None


def test_extract_group_remainder(base_dest, subunits_gdf, units_gdf) -> None:
    """extract_group_remainder returns the full country when subtract_codes is empty."""
    rem_dest = {
        "iso_a2": "TR",
        "name": "Testland remainder",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "group_remainder",
        "adm0_a3": "TST",
        "subtract_codes": [],
    }
    feat = extract_group_remainder(rem_dest, subunits_gdf, units_gdf, {})
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TR"


def test_extract_group_remainder_with_subtraction(
    base_dest, subunits_gdf, units_gdf, admin1_gdf
) -> None:
    """extract_group_remainder subtracts already-built feature geometry."""
    from shapely.geometry import box, mapping

    # Pre-built feature covering the bottom-left corner of TST (10,10)-(15,15)
    sub_geom = box(10, 10, 15, 15)
    sub_feat = {
        "type": "Feature",
        "geometry": mapping(sub_geom),
        "properties": {"iso_a2": "TP"},
    }
    built = {"TP": sub_feat}

    rem_dest = {
        "iso_a2": "TR",
        "name": "Testland remainder",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "group_remainder",
        "adm0_a3": "TST",
        "subtract_codes": ["TP"],
    }
    feat = extract_group_remainder(rem_dest, subunits_gdf, units_gdf, built)
    assert feat is not None
    remainder = shape(feat["geometry"])
    # Original TST = 100, subtract 25 → ≈75
    assert remainder.area == pytest.approx(75.0, abs=1.0)
