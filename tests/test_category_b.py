"""Tests for src/category_b.py — admin1 extraction."""

from __future__ import annotations

import pytest

from src.category_b import extract_admin1


def test_extract_admin1_success(admin1_dest, admin1_gdf) -> None:
    """extract_admin1 dissolves matching provinces into a single feature."""
    feat = extract_admin1(admin1_dest, admin1_gdf)
    assert feat is not None
    assert feat["properties"]["iso_a2"] == "TP"
    assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_extract_admin1_no_adm0_a3(admin1_dest, admin1_gdf) -> None:
    """extract_admin1 returns None when adm0_a3 is missing."""
    del admin1_dest["adm0_a3"]
    feat = extract_admin1(admin1_dest, admin1_gdf)
    assert feat is None


def test_extract_admin1_no_admin1_list(admin1_dest, admin1_gdf) -> None:
    """extract_admin1 returns None when admin1 list is empty."""
    admin1_dest["admin1"] = []
    feat = extract_admin1(admin1_dest, admin1_gdf)
    assert feat is None


def test_extract_admin1_wrong_country(admin1_dest, admin1_gdf) -> None:
    """extract_admin1 returns None when adm0_a3 doesn't match any admin1 rows."""
    admin1_dest["adm0_a3"] = "ZZZ"
    feat = extract_admin1(admin1_dest, admin1_gdf)
    assert feat is None


def test_extract_admin1_multiple_provinces(admin1_gdf) -> None:
    """extract_admin1 dissolves multiple provinces when all match."""
    dest = {
        "iso_a2": "TP",
        "name": "Both Provinces",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Testland",
        "type": "territory",
        "strategy": "admin1",
        "adm0_a3": "TST",
        "admin1": ["North Province", "South Province"],
    }
    feat = extract_admin1(dest, admin1_gdf)
    assert feat is not None
    from shapely.geometry import shape

    geom = shape(feat["geometry"])
    # Combined area = 10x5 + 10x5 = 100
    assert geom.area == pytest.approx(100.0)
