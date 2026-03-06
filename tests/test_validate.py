"""Tests for validate.py — output validation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

import validate

_VALID_CODES: set[str] = {"AF", "AL", "DZ", "AD", "AO", "GB", "US", "FR", "DE"}


def _write_geojson(path: Path, features: list) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_topojson(path: Path, geometries: list) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "Topology",
                "objects": {"regions": {"type": "GeometryCollection", "geometries": geometries}},
                "arcs": [],
            }
        )
    )


def _make_feature(code: str, name: str = "Test", geom: dict | None = None) -> dict:
    if geom is None:
        geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "iso_a2": code,
            "name": name,
            "sovereign": "Testland",
            "type": "country",
        },
    }


# ---------------------------------------------------------------------------
# validate_geojson
# ---------------------------------------------------------------------------


def test_validate_geojson_all_valid(tmp_path: Path) -> None:
    """validate_geojson returns True when all features are valid."""
    features = [_make_feature(c) for c in sorted(_VALID_CODES)]
    path = tmp_path / "merged.geojson"
    _write_geojson(path, features)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_geojson(path) is True


def test_validate_geojson_missing_code(tmp_path: Path) -> None:
    """validate_geojson returns False when a code from regions.csv is absent."""
    codes = _VALID_CODES - {"GB"}
    features = [_make_feature(c) for c in sorted(codes)]
    path = tmp_path / "merged.geojson"
    _write_geojson(path, features)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_geojson(path) is False


def test_validate_geojson_duplicate_code(tmp_path: Path) -> None:
    """validate_geojson returns False on duplicate iso_a2."""
    features = [_make_feature(c) for c in sorted(_VALID_CODES)]
    features.append(_make_feature("GB"))  # duplicate
    path = tmp_path / "merged.geojson"
    _write_geojson(path, features)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_geojson(path) is False


def test_validate_geojson_missing_prop(tmp_path: Path) -> None:
    """validate_geojson returns False when a required property is missing."""
    features = [_make_feature(c) for c in sorted(_VALID_CODES)]
    del features[0]["properties"]["sovereign"]
    path = tmp_path / "merged.geojson"
    _write_geojson(path, features)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_geojson(path) is False


def test_validate_geojson_missing_geometry(tmp_path: Path) -> None:
    """validate_geojson returns False when a feature has no geometry."""
    features = [_make_feature(c) for c in sorted(_VALID_CODES)]
    features[0]["geometry"] = None
    path = tmp_path / "merged.geojson"
    _write_geojson(path, features)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_geojson(path) is False


# ---------------------------------------------------------------------------
# validate_topojson
# ---------------------------------------------------------------------------


def test_validate_topojson_correct_count(tmp_path: Path) -> None:
    """validate_topojson returns True when geometry count matches expected."""
    geoms = [{"type": "Polygon", "arcs": [[i]]} for i in range(len(_VALID_CODES))]
    path = tmp_path / "iso-a2.json"
    _write_topojson(path, geoms)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_topojson(path) is True


def test_validate_topojson_wrong_count(tmp_path: Path) -> None:
    """validate_topojson returns False for wrong geometry count."""
    geoms = [{"type": "Polygon", "arcs": [[i]]} for i in range(5)]
    path = tmp_path / "iso-a2.json"
    _write_topojson(path, geoms)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        assert validate.validate_topojson(path) is False


def test_validate_topojson_large_file_warning(tmp_path: Path, capsys) -> None:
    """validate_topojson warns when file exceeds 400 KB."""
    # 9 codes x 50000 chars padding ~ 440 KB -> exceeds 400 KB limit
    geoms = [
        {"type": "Polygon", "arcs": [[i]], "padding": "x" * 50000} for i in range(len(_VALID_CODES))
    ]
    path = tmp_path / "iso-a2.json"
    _write_topojson(path, geoms)
    with patch("validate._valid_codes", return_value=_VALID_CODES):
        validate.validate_topojson(path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_passes(tmp_path: Path) -> None:
    """main() exits 0 when both files are valid."""
    features = [_make_feature(c) for c in sorted(_VALID_CODES)]
    geojson_path = tmp_path / "merged.geojson"
    _write_geojson(geojson_path, features)

    geoms = [{"type": "Polygon", "arcs": [[i]]} for i in range(len(_VALID_CODES))]
    topojson_path = tmp_path / "iso-a2.json"
    _write_topojson(topojson_path, geoms)

    with (
        patch("validate.OUTPUT_DIR", tmp_path),
        patch("validate._valid_codes", return_value=_VALID_CODES),
        patch("sys.exit") as mock_exit,
    ):
        validate.main()
        mock_exit.assert_not_called()


def test_main_fails_missing_geojson(tmp_path: Path) -> None:
    """main() exits 1 when merged.geojson is missing."""
    with (
        patch("validate.OUTPUT_DIR", tmp_path),
        pytest.raises(SystemExit) as exc,
    ):
        validate.main()
    assert exc.value.code == 1


def test_main_fails_invalid_geojson(tmp_path: Path) -> None:
    """main() exits 1 when merged.geojson has errors."""
    features = [_make_feature(c) for c in list(_VALID_CODES)[:3]]  # only partial
    geojson_path = tmp_path / "merged.geojson"
    _write_geojson(geojson_path, features)

    with (
        patch("validate.OUTPUT_DIR", tmp_path),
        patch("validate._valid_codes", return_value=_VALID_CODES),
        pytest.raises(SystemExit) as exc,
    ):
        validate.main()
    assert exc.value.code == 1
