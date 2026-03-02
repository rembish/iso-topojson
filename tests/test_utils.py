"""Tests for src/utils.py — GIS utility functions."""

from __future__ import annotations

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

from src.utils import (
    dissolve_geometries,
    extract_polygons_by_bbox,
    make_properties,
    to_feature,
)


def test_dissolve_two_polygons() -> None:
    """dissolve_geometries merges two non-overlapping boxes into a MultiPolygon."""
    a = box(0, 0, 1, 1)
    b = box(2, 0, 3, 1)
    result = dissolve_geometries([a, b])
    assert not result.is_empty
    assert result.area == pytest.approx(2.0)


def test_dissolve_overlapping_polygons() -> None:
    """dissolve_geometries unions overlapping polygons."""
    a = box(0, 0, 2, 2)
    b = box(1, 1, 3, 3)
    result = dissolve_geometries([a, b])
    assert result.area == pytest.approx(7.0)


def test_extract_polygons_by_bbox_centroid_inside() -> None:
    """extract_polygons_by_bbox returns sub-polygon whose centroid is inside bbox."""
    p1 = box(0, 0, 2, 2)   # centroid (1, 1) inside bbox
    p2 = box(10, 10, 12, 12)  # centroid outside bbox
    geom = MultiPolygon([p1, p2])
    result = extract_polygons_by_bbox(geom, (0.0, 0.0, 5.0, 5.0))
    assert result is not None
    assert result.area == pytest.approx(4.0)


def test_extract_polygons_by_bbox_no_match() -> None:
    """extract_polygons_by_bbox returns None when no polygons fall inside."""
    geom = box(20, 20, 25, 25)
    result = extract_polygons_by_bbox(geom, (0.0, 0.0, 5.0, 5.0))
    assert result is None


def test_extract_polygons_by_bbox_single_polygon() -> None:
    """extract_polygons_by_bbox handles a plain Polygon input."""
    geom = box(1, 1, 3, 3)
    result = extract_polygons_by_bbox(geom, (0.0, 0.0, 5.0, 5.0))
    assert result is not None
    assert result.area == pytest.approx(4.0)


def test_to_feature_structure() -> None:
    """to_feature returns a properly structured GeoJSON feature dict."""
    geom = Point(10, 20)
    props = {"iso_a2": "TS", "name": "Test"}
    feat = to_feature(geom, props)
    assert feat["type"] == "Feature"
    assert feat["properties"] == props
    assert feat["geometry"]["type"] == "Point"
    # shapely mapping() may return tuples or lists; compare as list
    assert list(feat["geometry"]["coordinates"]) == [10.0, 20.0]


def test_make_properties_full() -> None:
    """make_properties maps all standard fields from a dest config."""
    dest = {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
    }
    props = make_properties(dest)
    assert props["iso_a2"] == "TS"
    assert props["iso_a3"] == "TST"
    assert props["iso_n3"] == 999
    assert props["name"] == "Testland"
    assert props["sovereign"] == "Testland"
    assert props["type"] == "country"


def test_make_properties_nullable_fields() -> None:
    """make_properties handles None for optional fields."""
    dest = {
        "iso_a2": "XK",
        "name": "Kosovo",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Kosovo",
        "type": "disputed",
    }
    props = make_properties(dest)
    assert props["iso_a3"] is None
    assert props["iso_n3"] is None
