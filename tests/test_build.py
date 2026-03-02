"""Tests for src/build.py — orchestrator and write_geojson."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.build import build_features, write_geojson


def test_build_features_direct(base_dest, subunits_gdf, units_gdf, admin1_gdf, disputed_gdf) -> None:
    """build_features builds a direct-strategy destination."""
    with patch("src.build.get_destinations", return_value=[base_dest]):
        built = build_features(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf)

    assert "TS" in built
    feat = built["TS"]
    assert feat["properties"]["iso_a2"] == "TS"


def test_build_features_group_remainder_ordering(
    subunits_gdf, units_gdf, admin1_gdf, disputed_gdf
) -> None:
    """build_features processes group_remainder after direct features."""
    from shapely.geometry import box, mapping

    sub_dest = {
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
    rem_dest = {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "group_remainder",
        "adm0_a3": "TST",
        "subtract_codes": ["TP"],
    }

    with patch("src.build.get_destinations", return_value=[sub_dest, rem_dest]):
        built = build_features(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf)

    assert "TS" in built
    assert "TP" in built


def test_build_features_unknown_strategy(
    subunits_gdf, units_gdf, admin1_gdf, disputed_gdf
) -> None:
    """build_features skips features with unknown strategy."""
    dest = {
        "iso_a2": "ZZ",
        "name": "Unknown",
        "iso_a3": None,
        "iso_n3": None,
        "sovereign": "Test",
        "type": "country",
        "strategy": "totally_unknown",
    }
    with patch("src.build.get_destinations", return_value=[dest]):
        built = build_features(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf)

    assert "ZZ" not in built


def test_write_geojson(tmp_path: Path) -> None:
    """write_geojson writes a valid GeoJSON FeatureCollection sorted by iso_a2."""
    from shapely.geometry import box, mapping

    features = {
        "ZZ": {
            "type": "Feature",
            "geometry": mapping(box(1, 0, 2, 1)),
            "properties": {"iso_a2": "ZZ", "name": "Zz"},
        },
        "AA": {
            "type": "Feature",
            "geometry": mapping(box(0, 0, 1, 1)),
            "properties": {"iso_a2": "AA", "name": "Aa"},
        },
    }

    out = tmp_path / "test.geojson"
    write_geojson(features, out)

    assert out.exists()
    with out.open() as f:
        data = json.load(f)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    # Features should be sorted alphabetically by iso_a2
    assert data["features"][0]["properties"]["iso_a2"] == "AA"
    assert data["features"][1]["properties"]["iso_a2"] == "ZZ"


def test_build_features_point_strategy(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf) -> None:
    """build_features builds a point-strategy destination."""
    dest = {
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
    with patch("src.build.get_destinations", return_value=[dest]):
        built = build_features(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf)

    assert "TK" in built
    assert built["TK"]["geometry"]["type"] == "Point"


def test_main_runs(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf, tmp_path: Path) -> None:
    """main() writes merged.geojson via mocked data."""
    dest = {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "direct",
        "adm0_a3": "TST",
    }
    with (
        patch("src.build.get_destinations", return_value=[dest]),
        patch("src.build.load_data", return_value=(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf)),
        patch("src.build.OUTPUT_DIR", tmp_path),
    ):
        from src.build import main
        main()

    assert (tmp_path / "merged.geojson").exists()


def test_main_markers_only_separated(
    subunits_gdf, units_gdf, admin1_gdf, disputed_gdf, tmp_path: Path
) -> None:
    """main() writes markers_only features to points-only.geojson, not merged.geojson."""
    import json

    regular_dest = {
        "iso_a2": "TS",
        "name": "Testland",
        "iso_a3": "TST",
        "iso_n3": 999,
        "sovereign": "Testland",
        "type": "country",
        "strategy": "direct",
        "adm0_a3": "TST",
    }
    markers_only_dest = {
        "iso_a2": "BV",
        "name": "Bouvet Island",
        "iso_a3": "BVT",
        "iso_n3": 74,
        "sovereign": "Norway",
        "type": "territory",
        "strategy": "point",
        "lat": -54.43,
        "lon": 3.38,
        "markers_only": True,
    }
    with (
        patch("src.build.get_destinations", return_value=[regular_dest, markers_only_dest]),
        patch(
            "src.build.load_data",
            return_value=(subunits_gdf, units_gdf, admin1_gdf, disputed_gdf),
        ),
        patch("src.build.OUTPUT_DIR", tmp_path),
    ):
        from src.build import main

        main()

    with (tmp_path / "merged.geojson").open() as f:
        merged = json.load(f)
    codes = {feat["properties"]["iso_a2"] for feat in merged["features"]}
    assert "TS" in codes
    assert "BV" not in codes

    assert (tmp_path / "points-only.geojson").exists()
    with (tmp_path / "points-only.geojson").open() as f:
        pts = json.load(f)
    pt_codes = {feat["properties"]["iso_a2"] for feat in pts["features"]}
    assert "BV" in pt_codes


def test_write_geojson_creates_parent_dirs(tmp_path: Path) -> None:
    """write_geojson creates parent directories if they don't exist."""
    from shapely.geometry import box, mapping

    features = {
        "TS": {
            "type": "Feature",
            "geometry": mapping(box(0, 0, 1, 1)),
            "properties": {"iso_a2": "TS"},
        }
    }
    nested = tmp_path / "deep" / "nested" / "out.geojson"
    write_geojson(features, nested)
    assert nested.exists()
