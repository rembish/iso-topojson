"""Tests for src/build_biomes.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest
from shapely.geometry import box, mapping

import src.build_biomes as bb
from src.build_biomes import (
    _assign_provinces,
    _sanitize,
    apply_markers,
    build_biome_features,
    load_biomes,
    load_country_features,
    load_province_rules,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_province_admin1() -> gpd.GeoDataFrame:
    """Admin-1 GeoDataFrame: North Province (centroid ~lat 17.5) and South Province."""
    return gpd.GeoDataFrame(
        {
            "adm0_a3": ["TST", "TST"],
            "iso_a2": ["TS", "TS"],
            "name": ["North Province", "South Province"],
            "name_en": ["North Province", "South Province"],
            "NAME": ["North Province", "South Province"],
            "NAME_EN": ["North Province", "South Province"],
        },
        geometry=[box(0, 15, 10, 20), box(0, 0, 10, 15)],
        crs="EPSG:4326",
    )


@pytest.fixture()
def test_biomes() -> dict[str, dict[str, Any]]:
    return {
        "TS-NORTH": {"country": "TS", "name": "Northern Testland", "aurora_zone": True},
        "TS-SOUTH": {"country": "TS", "name": "Southern Testland", "aurora_zone": False},
    }


@pytest.fixture()
def test_province_config() -> dict[str, dict[str, Any]]:
    return {
        "TS": {
            "adm0_a3": "TST",
            "default": "TS-SOUTH",
            "overrides": {
                "TS-NORTH": {"names": ["North Province"]},
            },
        }
    }


@pytest.fixture()
def test_country_features() -> dict[str, dict[str, Any]]:
    return {
        "TS": {
            "type": "Feature",
            "properties": {
                "iso_a2": "TS",
                "iso_a3": "TST",
                "iso_n3": 999,
                "sovereign": "Testland",
                "type": "country",
            },
            "geometry": mapping(box(0, 0, 10, 20)),
        }
    }


# ---------------------------------------------------------------------------
# load_biomes / load_province_rules
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent / "data" / "biomes.json").exists(),
    reason="data/biomes.json not present",
)
def test_load_biomes_returns_dict() -> None:
    biomes = load_biomes()
    assert isinstance(biomes, dict)
    assert len(biomes) > 0
    # Each entry has required keys
    for _biome_id, info in biomes.items():
        assert "country" in info
        assert "name" in info
        assert "aurora_zone" in info


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent / "data" / "biome-provinces.json").exists(),
    reason="data/biome-provinces.json not present",
)
def test_load_province_rules_returns_dict() -> None:
    rules = load_province_rules()
    assert isinstance(rules, dict)
    assert len(rules) > 0
    for _cc, cfg in rules.items():
        assert "adm0_a3" in cfg
        assert "default" in cfg


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent / "data" / "biomes.json").exists()
    or not (Path(__file__).resolve().parent.parent / "data" / "biome-provinces.json").exists(),
    reason="data/biomes.json or data/biome-provinces.json not present",
)
def test_load_biomes_covers_all_province_rule_countries() -> None:
    biomes = load_biomes()
    rules = load_province_rules()
    biomed_countries = {info["country"] for info in biomes.values()}
    assert biomed_countries == set(rules.keys())


# ---------------------------------------------------------------------------
# load_country_features
# ---------------------------------------------------------------------------


def test_load_country_features_reads_geojson(tmp_path: Path, monkeypatch) -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"iso_a2": "FR", "name": "France"},
                "geometry": mapping(box(0, 0, 1, 1)),
            },
            {
                "type": "Feature",
                "properties": {"iso_a2": "DE", "name": "Germany"},
                "geometry": mapping(box(1, 0, 2, 1)),
            },
        ],
    }
    path = tmp_path / "merged.geojson"
    path.write_text(json.dumps(geojson))
    monkeypatch.setattr(bb, "MERGED_GEOJSON", path)

    result = load_country_features()
    assert set(result.keys()) == {"FR", "DE"}
    assert result["FR"]["properties"]["name"] == "France"


def test_load_country_features_skips_missing_iso_a2(tmp_path: Path, monkeypatch) -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "NoCode"},
                "geometry": mapping(box(0, 0, 1, 1)),
            }
        ],
    }
    path = tmp_path / "merged.geojson"
    path.write_text(json.dumps(geojson))
    monkeypatch.setattr(bb, "MERGED_GEOJSON", path)

    result = load_country_features()
    assert result == {}


# ---------------------------------------------------------------------------
# _assign_provinces
# ---------------------------------------------------------------------------


def test_assign_provinces_by_name(two_province_admin1: gpd.GeoDataFrame) -> None:
    overrides = {
        "TS-NORTH": {"names": ["North Province"]},
    }
    result = _assign_provinces(two_province_admin1, "TS-SOUTH", overrides)

    north_indices = result["TS-NORTH"]
    south_indices = result["TS-SOUTH"]
    assert len(north_indices) == 1
    assert len(south_indices) == 1
    # North Province has centroid.y > 15
    assert two_province_admin1.loc[north_indices[0]].geometry.centroid.y > 15


def test_assign_provinces_by_lat_min(two_province_admin1: gpd.GeoDataFrame) -> None:
    """lat_min=15 captures North Province (centroid y=17.5), South goes to default."""
    overrides = {
        "TS-NORTH": {"lat_min": 15.0},
    }
    result = _assign_provinces(two_province_admin1, "TS-SOUTH", overrides)
    assert len(result["TS-NORTH"]) == 1
    assert len(result["TS-SOUTH"]) == 1


def test_assign_provinces_by_lat_max(two_province_admin1: gpd.GeoDataFrame) -> None:
    """lat_max=15 captures South Province (centroid y=7.5)."""
    overrides = {
        "TS-SOUTH_ONLY": {"lat_max": 15.0},
    }
    result = _assign_provinces(two_province_admin1, "TS-NORTH", overrides)
    assert len(result["TS-SOUTH_ONLY"]) == 1
    assert len(result["TS-NORTH"]) == 1


def test_assign_provinces_names_priority_over_lat(two_province_admin1: gpd.GeoDataFrame) -> None:
    """Name match takes precedence: North Province is assigned by name, not swept by lat."""
    overrides = {
        "TS-NORTH": {"names": ["North Province"]},
        "TS-ALL": {"lat_min": -90.0},  # would match everything remaining
    }
    result = _assign_provinces(two_province_admin1, "TS-SOUTH", overrides)
    # TS-NORTH gets North Province by name
    assert len(result["TS-NORTH"]) == 1
    # TS-ALL gets South Province (the only unassigned one)
    assert len(result["TS-ALL"]) == 1
    # Default gets nothing
    assert len(result["TS-SOUTH"]) == 0


def test_assign_provinces_all_to_default(two_province_admin1: gpd.GeoDataFrame) -> None:
    """When no overrides match, all provinces go to the default biome."""
    overrides: dict[str, dict[str, Any]] = {}
    result = _assign_provinces(two_province_admin1, "TS-SOUTH", overrides)
    assert len(result["TS-SOUTH"]) == 2


def test_assign_provinces_no_duplicates(two_province_admin1: gpd.GeoDataFrame) -> None:
    """A province matched by name is not also matched by lat range."""
    overrides = {
        "TS-NORTH": {"names": ["North Province"]},
        "TS-ANYTHING": {"lat_min": 0.0},  # catches everything not yet assigned
    }
    result = _assign_provinces(two_province_admin1, "TS-SOUTH", overrides)
    all_assigned = result["TS-NORTH"] + result["TS-ANYTHING"] + result["TS-SOUTH"]
    assert len(all_assigned) == len(set(all_assigned))  # no duplicates


def test_assign_provinces_lon_range(two_province_admin1: gpd.GeoDataFrame) -> None:
    """lon_min / lon_max threshold captures provinces by longitude centroid."""
    overrides = {
        "TS-EAST": {"lon_min": 0.0, "lon_max": 5.0},  # centroid x=5 is on the boundary
    }
    # Both provinces have centroid.x = 5.0, which is the midpoint of [0,10]
    result = _assign_provinces(two_province_admin1, "TS-DEFAULT", overrides)
    assert len(result["TS-EAST"]) == 2
    assert len(result["TS-DEFAULT"]) == 0


# ---------------------------------------------------------------------------
# build_biome_features
# ---------------------------------------------------------------------------


def test_build_biome_features_basic(
    two_province_admin1: gpd.GeoDataFrame,
    test_biomes: dict[str, dict[str, Any]],
    test_province_config: dict[str, dict[str, Any]],
    test_country_features: dict[str, dict[str, Any]],
) -> None:
    result, transfers = build_biome_features(
        two_province_admin1, test_biomes, test_province_config, test_country_features
    )
    assert set(result.keys()) == {"TS-NORTH", "TS-SOUTH"}
    assert transfers == {}
    for biome_id, feat in result.items():
        assert feat["type"] == "Feature"
        assert feat["properties"]["biome_id"] == biome_id
        assert feat["properties"]["iso_a2"] == "TS"
        assert feat["properties"]["iso_a3"] == "TST"
        assert feat["properties"]["sovereign"] == "Testland"
        assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_build_biome_features_inherits_parent_props(
    two_province_admin1: gpd.GeoDataFrame,
    test_biomes: dict[str, dict[str, Any]],
    test_province_config: dict[str, dict[str, Any]],
    test_country_features: dict[str, dict[str, Any]],
) -> None:
    result, _ = build_biome_features(
        two_province_admin1, test_biomes, test_province_config, test_country_features
    )
    north = result["TS-NORTH"]
    assert north["properties"]["name"] == "Northern Testland"
    assert north["properties"]["aurora_zone"] is True
    south = result["TS-SOUTH"]
    assert south["properties"]["aurora_zone"] is False


def test_build_biome_features_missing_config(
    two_province_admin1: gpd.GeoDataFrame,
    test_biomes: dict[str, dict[str, Any]],
    test_country_features: dict[str, dict[str, Any]],
    capsys,
) -> None:
    """Countries without province config are skipped with a warning."""
    result, _ = build_biome_features(two_province_admin1, test_biomes, {}, test_country_features)
    assert result == {}
    captured = capsys.readouterr()
    assert "WARN" in captured.out


def test_build_biome_features_unknown_adm0_a3(
    two_province_admin1: gpd.GeoDataFrame,
    test_biomes: dict[str, dict[str, Any]],
    test_country_features: dict[str, dict[str, Any]],
    capsys,
) -> None:
    """When adm0_a3 matches nothing, falls back to iso_a2 then warns."""
    config = {
        "TS": {
            "adm0_a3": "ZZZ",  # doesn't match any province
            "default": "TS-SOUTH",
            "overrides": {"TS-NORTH": {"names": ["North Province"]}},
        }
    }
    # The admin1 fixture has iso_a2="TS" so the iso_a2 fallback should work
    result, _ = build_biome_features(
        two_province_admin1, test_biomes, config, test_country_features
    )
    # Fallback to iso_a2 succeeds
    assert "TS-NORTH" in result or "TS-SOUTH" in result


def test_build_biome_features_exclude_transfer(
    two_province_admin1: gpd.GeoDataFrame,
    test_biomes: dict[str, dict[str, Any]],
    test_country_features: dict[str, dict[str, Any]],
) -> None:
    """Excluded provinces are transferred to the target country."""
    config = {
        "TS": {
            "adm0_a3": "TST",
            "default": "TS-SOUTH",
            "exclude": {"names": ["North Province"], "transfer_to": "XX"},
            "overrides": {"TS-NORTH": {"names": ["North Province"]}},
        }
    }
    result, transfers = build_biome_features(
        two_province_admin1, test_biomes, config, test_country_features
    )
    # North Province excluded, so TS-NORTH has no provinces
    assert "TS-NORTH" not in result
    assert "TS-SOUTH" in result
    assert "XX" in transfers
    assert len(transfers["XX"]) == 1


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------


def test_sanitize_regular_values() -> None:
    assert _sanitize(42) == 42
    assert _sanitize("hello") == "hello"
    assert _sanitize(3.14) == pytest.approx(3.14)
    assert _sanitize(None) is None


def test_sanitize_nan_to_none() -> None:
    assert _sanitize(float("nan")) is None


def test_sanitize_inf_to_none() -> None:
    assert _sanitize(float("inf")) is None
    assert _sanitize(float("-inf")) is None


def test_sanitize_numpy_scalar() -> None:
    import numpy as np

    val = np.float64(1.5)
    result = _sanitize(val)
    assert result == pytest.approx(1.5)
    assert isinstance(result, float)


def test_sanitize_numpy_nan() -> None:
    import numpy as np

    assert _sanitize(np.float64("nan")) is None


# ---------------------------------------------------------------------------
# apply_markers
# ---------------------------------------------------------------------------


def _make_feature(geom, **props) -> dict[str, Any]:
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def test_apply_markers_large_polygon_stays() -> None:
    """A 10x10 degree box (~1.2M km2) stays as a polygon."""
    features = [_make_feature(box(0, 0, 10, 10), iso_a2="BIG", name="Big Country", type="country")]
    polygons, points = apply_markers(features)
    assert len(polygons) == 1
    assert len(points) == 0
    assert polygons[0]["properties"]["marker"] is False
    assert polygons[0]["properties"]["area_km2"] > 500


def test_apply_markers_tiny_polygon_becomes_point() -> None:
    """A 0.001x0.001 degree box (~0.01 km2) is converted to a centroid point."""
    features = [_make_feature(box(0, 0, 0.001, 0.001), iso_a2="TK", name="Tiny", type="territory")]
    polygons, points = apply_markers(features)
    assert len(polygons) == 0
    assert len(points) == 1
    assert points[0]["properties"]["marker"] is True
    assert points[0]["geometry"]["type"] == "Point"


def test_apply_markers_point_passthrough() -> None:
    """A pre-existing Point feature passes through unchanged as a marker."""
    from shapely.geometry import Point

    features = [_make_feature(Point(5, 5), iso_a2="PT", name="Point Country", type="territory")]
    polygons, points = apply_markers(features)
    assert len(polygons) == 0
    assert len(points) == 1
    assert points[0]["properties"]["marker"] is True


def test_apply_markers_mixed() -> None:
    """Mixed features: large polygon stays, tiny becomes point."""
    features = [
        _make_feature(box(0, 0, 10, 10), iso_a2="BIG", name="Big", type="country"),
        _make_feature(box(0, 0, 0.001, 0.001), iso_a2="TK", name="Tiny", type="territory"),
    ]
    polygons, points = apply_markers(features)
    assert len(polygons) == 1
    assert len(points) == 1


def test_apply_markers_nan_props_sanitized() -> None:
    """NaN property values are sanitized to None in the output."""
    features = [
        {
            "type": "Feature",
            "properties": {
                "iso_a2": "TS",
                "name": "Test",
                "type": "country",
                "badval": float("nan"),
            },
            "geometry": mapping(box(0, 0, 10, 10)),
        }
    ]
    polygons, _points = apply_markers(features)
    assert len(polygons) == 1
    assert polygons[0]["properties"]["badval"] is None


# ---------------------------------------------------------------------------
# main — file-not-found guard
# ---------------------------------------------------------------------------


def test_main_raises_if_merged_geojson_missing(tmp_path: Path, monkeypatch) -> None:
    """main() raises FileNotFoundError when merged.geojson does not exist."""
    monkeypatch.setattr(bb, "MERGED_GEOJSON", tmp_path / "nonexistent.geojson")
    with pytest.raises(FileNotFoundError, match=r"nonexistent\.geojson"):
        bb.main()


def test_main_raises_if_admin1_missing(tmp_path: Path, monkeypatch) -> None:
    """main() raises FileNotFoundError when admin-1 shapefile does not exist."""
    # merged.geojson exists, but admin1 shp does not
    merged = tmp_path / "merged.geojson"
    merged.write_text('{"type":"FeatureCollection","features":[]}')
    monkeypatch.setattr(bb, "MERGED_GEOJSON", merged)
    monkeypatch.setattr(bb, "ADMIN1_SHP", tmp_path / "no_admin1.shp")
    with pytest.raises(FileNotFoundError):
        bb.main()
