"""Tests for src/markers.py — markers pipeline."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, box, mapping

from src.markers import AREA_THRESHOLD_KM2, _quantize, build_markers_collection, inject_points


def _make_gdf(geoms: list, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    rows = []
    for i, _geom in enumerate(geoms):
        rows.append(
            {
                "iso_a2": f"T{i}",
                "name": f"Test{i}",
                "sovereign": "Testland",
                "type": "country",
            }
        )
    return gpd.GeoDataFrame(rows, geometry=geoms, crs=crs)


def test_area_threshold_is_500() -> None:
    """AREA_THRESHOLD_KM2 is 500 for iso-topojson."""
    assert AREA_THRESHOLD_KM2 == 500.0


def test_build_markers_large_polygon_kept() -> None:
    """Polygons above threshold are kept as polygons."""
    # A large polygon (continental size)
    large = box(-10, -10, 10, 10)
    gdf = _make_gdf([large])
    polygons, points = build_markers_collection(gdf)
    assert len(polygons["features"]) == 1
    assert len(points) == 0


def test_build_markers_small_polygon_converted() -> None:
    """Polygons below threshold become point markers."""
    # A tiny box (fractions of a degree — well under 500 km²)
    tiny = box(0, 0, 0.01, 0.01)
    gdf = _make_gdf([tiny])
    polygons, points = build_markers_collection(gdf)
    assert len(polygons["features"]) == 0
    assert len(points) == 1
    assert points[0]["properties"]["marker"] is True


def test_build_markers_point_kept_as_marker() -> None:
    """Pre-existing Point features are kept as markers unchanged."""
    pt = Point(10, 20)
    gdf = _make_gdf([pt])
    polygons, points = build_markers_collection(gdf)
    assert len(polygons["features"]) == 0
    assert len(points) == 1
    assert points[0]["geometry"]["type"] == "Point"
    assert points[0]["properties"]["marker"] is True


def test_inject_points_adds_object(tmp_path: Path) -> None:
    """inject_points adds a 'points' object to an existing TopoJSON."""
    topo = {
        "type": "Topology",
        "transform": {"scale": [0.001, 0.001], "translate": [-180, -90]},
        "objects": {
            "world": {
                "type": "GeometryCollection",
                "geometries": [],
            }
        },
        "arcs": [],
    }
    topo_path = tmp_path / "test.json"
    topo_path.write_text(json.dumps(topo))

    point_features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "properties": {"iso_a2": "TS", "name": "Test"},
        }
    ]
    inject_points(topo_path, point_features)

    with topo_path.open() as f:
        result = json.load(f)

    assert "points" in result["objects"]
    geoms = result["objects"]["points"]["geometries"]
    assert len(geoms) == 1
    assert geoms[0]["type"] == "Point"
    assert geoms[0]["properties"]["iso_a2"] == "TS"


def test_quantize_origin() -> None:
    """_quantize converts (0, 0) to (0, 0) under identity-like transform."""
    transform = {"scale": [1.0, 1.0], "translate": [0.0, 0.0]}
    assert _quantize(0.0, 0.0, transform) == [0, 0]


def test_main_runs(tmp_path: Path) -> None:
    """markers main() runs end-to-end with mocked mapshaper."""
    import json

    from shapely.geometry import box

    # Write a minimal merged.geojson
    large = box(-10, -10, 10, 10)
    tiny = box(0, 0, 0.01, 0.01)
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(large),
                "properties": {"iso_a2": "TS", "name": "Test", "sovereign": "T", "type": "country"},
            },
            {
                "type": "Feature",
                "geometry": mapping(tiny),
                "properties": {
                    "iso_a2": "TT",
                    "name": "Tiny",
                    "sovereign": "T",
                    "type": "territory",
                },
            },
        ],
    }
    merged = tmp_path / "merged.geojson"
    merged.write_text(json.dumps(collection))

    # Stub mapshaper: write a minimal TopoJSON
    def fake_run_mapshaper(input_path: Path, output_path: Path, simplify: str = "3%") -> None:
        topo = {
            "type": "Topology",
            "transform": {"scale": [0.001, 0.001], "translate": [-180, -90]},
            "objects": {"world": {"type": "GeometryCollection", "geometries": []}},
            "arcs": [],
        }
        output_path.write_text(json.dumps(topo))

    with (
        patch("src.markers.OUTPUT_DIR", tmp_path),
        patch("src.markers.MERGED_GEOJSON", merged),
        patch("src.markers.MARKERS_TOPOJSON", tmp_path / "iso-a2-markers.json"),
        patch("src.markers.MARKERS_GEOJSON", tmp_path / "merged-markers.geojson"),
        patch("src.markers.run_mapshaper", fake_run_mapshaper),
    ):
        from src.markers import main

        main()

    assert (tmp_path / "iso-a2-markers.json").exists()


def test_main_includes_points_only(tmp_path: Path) -> None:
    """main() includes features from points-only.geojson in the markers topology."""
    import json

    from shapely.geometry import box

    large = box(-10, -10, 10, 10)
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(large),
                "properties": {
                    "iso_a2": "TS",
                    "name": "Test",
                    "sovereign": "T",
                    "type": "country",
                },
            }
        ],
    }
    merged = tmp_path / "merged.geojson"
    merged.write_text(json.dumps(collection))

    points_only_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [3.38, -54.43]},
                "properties": {
                    "iso_a2": "BV",
                    "name": "Bouvet Island",
                    "sovereign": "Norway",
                    "type": "territory",
                },
            }
        ],
    }
    points_only = tmp_path / "points-only.geojson"
    points_only.write_text(json.dumps(points_only_fc))

    def fake_run_mapshaper(input_path: Path, output_path: Path, simplify: str = "3%") -> None:
        topo = {
            "type": "Topology",
            "transform": {"scale": [0.001, 0.001], "translate": [-180, -90]},
            "objects": {"world": {"type": "GeometryCollection", "geometries": []}},
            "arcs": [],
        }
        output_path.write_text(json.dumps(topo))

    with (
        patch("src.markers.OUTPUT_DIR", tmp_path),
        patch("src.markers.MERGED_GEOJSON", merged),
        patch("src.markers.POINTS_ONLY_GEOJSON", points_only),
        patch("src.markers.MARKERS_TOPOJSON", tmp_path / "iso-a2-markers.json"),
        patch("src.markers.MARKERS_GEOJSON", tmp_path / "merged-markers.geojson"),
        patch("src.markers.run_mapshaper", fake_run_mapshaper),
    ):
        from src.markers import main

        main()

    with (tmp_path / "iso-a2-markers.json").open() as f:
        topo = json.load(f)
    point_geoms = topo["objects"]["points"]["geometries"]
    assert any(g["properties"]["iso_a2"] == "BV" for g in point_geoms)


def test_quantize_nonzero() -> None:
    """_quantize correctly encodes a known coordinate."""
    transform = {"scale": [0.001, 0.001], "translate": [-180.0, -90.0]}
    result = _quantize(0.0, 0.0, transform)
    assert result == [180000, 90000]
