"""Regression checks for optional building-registry evidence and fixed projection."""

import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
pytest.importorskip("pyproj")

from datascape.buildings.enrichment_study import crop_view
from datascape.buildings.regional import choose_height, korean_family, match_polygons, source_id


CONFIG = json.loads((Path(__file__).resolve().parents[1] /
                     "docs/experiments/buildings_work01b/seoul.json").read_text())


def test_exact_large_identifiers_are_preserved():
    assert source_id("0012345678901234567890") == "0012345678901234567890"
    assert source_id(12345678901234567890) == "12345678901234567890"
    with pytest.raises(ValueError):
        source_id(1.2345678901234568e19)


def test_only_strong_reciprocal_overlap_is_accepted():
    native = [box(0, 0, 10, 10), box(40, 0, 50, 10), box(60, 0, 70, 10)]
    source = [box(.2, 0, 10.2, 10), box(50, 0, 58, 10), box(67, 0, 77, 10)]
    rows = match_polygons(native, source, CONFIG["overlap"])
    assert [row["status"] for row in rows] == ["high_confidence", "unmatched", "ambiguous"]
    assert [row["region_index"] for row in rows] == [0, None, None]


def test_apartment_wings_and_merged_source_envelopes_are_excluded():
    split = [box(0, 0, 7.5, 10), box(7.5, 0, 10, 10)]
    merged = [box(0, 0, 10, 10)]
    assert match_polygons(merged, split, CONFIG["overlap"])[0]["status"] == "one_to_many"
    assert all(r["status"] == "many_to_one" for r in match_polygons(split, merged, CONFIG["overlap"]))


def test_official_reference_and_provisional_heights_stay_distinct():
    rates = CONFIG["floor_rate_m"]
    assert choose_height({}, {"height_m": 8}, False, rates)["h1_m"] is None
    result = choose_height({"height": 17, "num_floors": 5},
                           {"height_m": 8, "floors": 3, "use_name": "제2종근린생활시설"}, True, rates)
    assert result["height_conflict"] and result["floor_conflict"]
    assert result["official_height_m"] == 8 and result["h1_m"] == 17
    assert result["h1_source"] == "overture"
    result = choose_height({"num_floors": 3, "class": "house"}, {}, False, rates)
    assert result["h2_m"] == 9 and result["h2_floor_source"] == "overture_floors"
    result = choose_height({}, {"floors": 2, "use_name": "제1종근린생활시설"}, True, rates)
    assert result["h2_m"] == 6.8 and result["h2_floor_source"] == "regional_official_floors"
    assert korean_family("02000", "아파트") == "apartment"
    assert choose_height({"is_underground": True, "height": 10}, {}, False, rates)["h0_m"] is None


def test_width_study_is_a_uniform_projected_crop():
    reference = {
        "id": "A", "bearing_deg": 123, "depth_anchors_m": [-1750, 4800],
        "p3_depth_rise_fraction": 1.1,
        "mapping": {"p3_width_scale_m": 3300, "p3_relief_fraction_per_km": .8,
                    "p3_bottom_fraction": 1.12}
    }
    result = crop_view(reference, 1650, .61)
    assert result["depth_anchors_m"] == reference["depth_anchors_m"]
    assert result["mapping"]["p3_relief_fraction_per_km"] == 1.6
    assert result["mapping"]["p3_depth_rise_fraction"] == 2.2
    assert np.isclose(result["mapping"]["p3_bottom_fraction"], .5 + 2 * (1.12 - .61))
