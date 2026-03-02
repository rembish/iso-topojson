"""Tests for src/destinations.py — CSV-based region loader."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from src.destinations import get_destinations


def test_get_destinations_returns_entries() -> None:
    """get_destinations returns a non-empty list."""
    dests = get_destinations()
    assert len(dests) > 0


def test_all_codes_unique() -> None:
    """All iso_a2 values are unique with no duplicates."""
    dests = get_destinations()
    codes = [d["iso_a2"] for d in dests]
    assert len(codes) == len(set(codes)), "Duplicate iso_a2 codes found"


def test_known_codes_present() -> None:
    """Spot-check well-known iso_a2 codes are present."""
    dests = get_destinations()
    codes = {d["iso_a2"] for d in dests}
    for expected in ["US", "GB", "FR", "DE", "JP", "CN", "AU", "BR", "XK", "TW", "PS", "EH"]:
        assert expected in codes, f"{expected} not in destinations"


def test_required_fields_present() -> None:
    """Every destination has all required base fields."""
    required = {"iso_a2", "name", "sovereign", "type", "strategy"}
    for d in get_destinations():
        missing = required - set(d.keys())
        assert not missing, f"[{d.get('iso_a2')}] missing fields: {missing}"


def test_types_are_valid() -> None:
    """All type values are one of the allowed literals."""
    valid_types = {"country", "territory", "disputed", "dependency"}
    for d in get_destinations():
        assert d["type"] in valid_types, f"[{d['iso_a2']}] invalid type: {d['type']!r}"


def test_strategies_are_valid() -> None:
    """All strategy values are one of the known strategies."""
    valid = {"direct", "subunit", "admin1", "group_remainder", "disputed", "island_bbox", "land_bbox", "point"}
    for d in get_destinations():
        assert d["strategy"] in valid, (
            f"[{d['iso_a2']}] invalid strategy: {d['strategy']!r}"
        )


def test_iso_n3_is_int_or_none() -> None:
    """iso_n3 is always an int or None, never a string."""
    for d in get_destinations():
        v = d.get("iso_n3")
        assert v is None or isinstance(v, int), (
            f"[{d['iso_a2']}] iso_n3 is {type(v)}: {v!r}"
        )


def test_point_strategy_has_coords() -> None:
    """Every point-strategy destination has lat and lon."""
    for d in get_destinations():
        if d["strategy"] == "point":
            assert "lat" in d, f"[{d['iso_a2']}] point strategy has no lat"
            assert "lon" in d, f"[{d['iso_a2']}] point strategy has no lon"
            assert isinstance(d["lat"], float)
            assert isinstance(d["lon"], float)


def test_subunit_strategy_has_su_a3() -> None:
    """Every subunit-strategy destination has su_a3."""
    for d in get_destinations():
        if d["strategy"] == "subunit":
            assert "su_a3" in d, f"[{d['iso_a2']}] subunit strategy has no su_a3"


def test_direct_strategy_has_adm0_a3() -> None:
    """Most direct-strategy destinations have adm0_a3."""
    for d in get_destinations():
        if d["strategy"] == "direct":
            has_code = bool(d.get("adm0_a3") or d.get("iso_a3"))
            assert has_code, f"[{d['iso_a2']}] direct strategy has no lookup code"


def test_specific_entries() -> None:
    """Spot-check a few known destinations."""
    dests = {d["iso_a2"]: d for d in get_destinations()}

    # Afghanistan
    afg = dests["AF"]
    assert afg["name"] == "Afghanistan"
    assert afg["strategy"] == "direct"
    assert afg["iso_a3"] == "AFG"
    assert afg["iso_n3"] == 4

    # Pitcairn — subunit (NE has actual polygon)
    pn = dests["PN"]
    assert pn["strategy"] == "subunit"
    assert pn["su_a3"] == "PCN"

    # Tokelau — point
    tk = dests["TK"]
    assert tk["strategy"] == "point"
    assert isinstance(tk["lat"], float)
    assert isinstance(tk["lon"], float)

    # Gibraltar — subunit
    gi = dests["GI"]
    assert gi["strategy"] == "subunit"
    assert gi["su_a3"] == "GIB"

    # Kosovo — disputed quasi-ISO
    xk = dests["XK"]
    assert xk["strategy"] == "direct"
    assert xk["adm0_a3"] == "XKX"

    # BQ — Bonaire, Sint Eustatius and Saba merged as BES
    bq = dests["BQ"]
    assert bq["strategy"] == "direct"
    assert bq["adm0_a3"] == "BES"

    # SH — Saint Helena as single direct feature
    sh = dests["SH"]
    assert sh["strategy"] == "direct"
    assert sh["adm0_a3"] == "SHN"


def test_csv_file_exists() -> None:
    """regions.csv exists in the project root."""
    csv_path = Path(__file__).resolve().parent.parent / "regions.csv"
    assert csv_path.exists(), "regions.csv not found in project root"


def test_csv_has_correct_header() -> None:
    """regions.csv has the expected column headers."""
    csv_path = Path(__file__).resolve().parent.parent / "regions.csv"
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

    required_cols = {
        "iso_a2", "name", "type", "sovereign",
        "strategy", "adm0_a3", "su_a3",
        "parent_adm0_a3", "bbox", "point_lat", "point_lon",
        "disputed_name",
    }
    missing = required_cols - set(headers)
    assert not missing, f"CSV missing columns: {missing}"


def test_admin1_strategy_has_admin1_list() -> None:
    """Every admin1-strategy destination has a non-empty 'admin1' list."""
    for d in get_destinations():
        if d["strategy"] == "admin1":
            names = d.get("admin1", [])
            assert names, f"[{d['iso_a2']}] admin1 strategy but no admin1 list"
            assert all(isinstance(n, str) for n in names)


def test_island_bbox_strategy_has_bbox() -> None:
    """Every island_bbox-strategy destination has a 4-element bbox tuple."""
    for d in get_destinations():
        if d["strategy"] == "island_bbox":
            bbox = d.get("bbox")
            assert bbox is not None, f"[{d['iso_a2']}] island_bbox has no bbox"
            assert len(bbox) == 4, f"[{d['iso_a2']}] bbox has {len(bbox)} elements"


def test_optional_fields_parsed(tmp_path: Path) -> None:
    """get_destinations parses optional fields (merge_a3, subtract_codes, etc.)."""
    csv_path = tmp_path / "regions.csv"
    csv_path.write_text(
        "iso_a2,name,type,sovereign,iso_a3,iso_n3,"
        "strategy,adm0_a3,su_a3,admin1_names,parent_adm0_a3,bbox,"
        "point_lat,point_lon,subtract_codes,disputed_name,merge_a3,merge_disputed\n"
        "TS,Testland,country,Testland,TST,999,"
        'direct,TST,,,"North;South",,,,GR;FR,,\n'
    )
    with patch("src.destinations.REGIONS_CSV", csv_path):
        dests = get_destinations()

    assert len(dests) == 1
    d = dests[0]
    assert d["adm0_a3"] == "TST"


def test_markers_only_parsed(tmp_path: Path) -> None:
    """get_destinations sets markers_only=True for entries with markers_only=1."""
    csv_path = tmp_path / "regions.csv"
    csv_path.write_text(
        "iso_a2,name,type,sovereign,iso_a3,iso_n3,"
        "strategy,adm0_a3,su_a3,admin1_names,parent_adm0_a3,bbox,"
        "point_lat,point_lon,subtract_codes,disputed_name,merge_a3,merge_disputed,markers_only\n"
        "BV,Bouvet Island,territory,Norway,BVT,74,"
        "point,,,,,,-54.43,3.38,,,,,1\n"
        "TS,Testland,country,Testland,TST,999,"
        "direct,TST,,,,,,,,,,\n"
    )
    with patch("src.destinations.REGIONS_CSV", csv_path):
        dests = get_destinations()

    bv = next(d for d in dests if d["iso_a2"] == "BV")
    ts = next(d for d in dests if d["iso_a2"] == "TS")
    assert bv.get("markers_only") is True
    assert "markers_only" not in ts


def test_malformed_csv_non_numeric_iso_n3(tmp_path: Path) -> None:
    """get_destinations raises ValueError when iso_n3 is non-numeric."""
    bad_csv = tmp_path / "regions.csv"
    bad_csv.write_text(
        "iso_a2,name,type,sovereign,iso_a3,iso_n3,"
        "strategy,adm0_a3,su_a3,admin1_names,parent_adm0_a3,bbox,"
        "point_lat,point_lon,subtract_codes,disputed_name,merge_a3,merge_disputed\n"
        "TS,Test,country,Test,TST,not-a-number,direct,TST,,,,,,,,\n"
    )
    with patch("src.destinations.REGIONS_CSV", bad_csv):
        with pytest.raises(ValueError):
            get_destinations()
