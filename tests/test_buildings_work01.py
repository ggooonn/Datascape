"""Fixtures for geometry and occlusion semantics introduced by Buildings Work 01."""

from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import Polygon

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
pytest.importorskip("pyproj")

from datascape.buildings.acquire import intersecting_shards
from datascape.buildings.massing import Mass, height_policy, prism
from datascape.buildings.projection import Projected, composite
from datascape.buildings.source import overlap_audit


def test_height_provenance_and_unknown_floating_floor():
    assert height_policy({"height": 24, "num_floors": 7}) == (24, "overture_height_field")
    assert height_policy({"num_floors": 7}) is None
    assert height_policy({"num_floors": 7}, True) == (21, "floor_count_x_3m_diagnostic_estimate")
    assert height_policy({"height": 24, "min_floor": 2}) is None
    assert height_policy({"height": 24, "is_underground": True}) is None


def test_massing_keeps_courtyard_hole_and_elevated_bottom():
    footprint = Polygon([(0, 0), (12, 0), (12, 9), (0, 9)],
                        [[(3, 3), (7, 3), (7, 6), (3, 6)]])
    mass = Mass("part-id", footprint, 150, 4, 20, "overture_height_field", parent_id="parent-id")
    xyz, tones = prism(mass)
    triangles = xyz.reshape(-1, 3, 3)
    roof = triangles[(triangles[:, :, 2] == 174).all(axis=1), :, :2]
    x, y = (roof[:, 1] - roof[:, 0]).T
    u, v = (roof[:, 2] - roof[:, 0]).T
    assert np.abs(x * v - y * u).sum() / 2 == pytest.approx(footprint.area)
    assert xyz[:, 2].min() == 154
    assert xyz[:, 2].max() == 174
    assert len(tones) == len(triangles)
    assert mass.footprint.equals_exact(footprint, 0)


def test_composite_counts_terrain_and_object_occlusion_for_synthetic_parts():
    width, height = 13, 13
    land_depth = np.full((height, width), np.inf)
    land_depth[:, :5] = 2
    land = (None, None, None, land_depth)
    triangle = np.array([[1, 1], [11, 1], [1, 11]], dtype=float)
    front = Projected(SimpleNamespace(id="west", parent_id="parent", height_kind="source",
                                      native_class=None, ground_kind="synthetic"),
                      triangle, np.full(3, 4.), np.full(3, .2), np.array([.7]), "near")
    back = Projected(SimpleNamespace(id="east", parent_id="parent", height_kind="source",
                                     native_class=None, ground_kind="synthetic"),
                     triangle, np.full(3, 7.), np.full(3, .5), np.array([.7]), "middle")
    owner, _, rows = composite([front, back], land, width, height)
    assert rows[0]["visible_px"] > 0
    assert rows[0]["terrain_blocked_px"] > 0
    assert rows[1]["building_blocked_px"] == rows[0]["visible_px"]
    assert rows[1]["visible_px"] == 0
    assert np.all(owner[:, :5] == -1)
    for row in rows:
        assert row["isolated_px"] == sum(row[key] for key in
                                         ("visible_px", "terrain_blocked_px", "building_blocked_px"))


def test_overlap_counts_exact_duplicates_but_excludes_touching_edges():
    a = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    b = Polygon([(2, 0), (4, 0), (4, 2), (2, 2)])
    assert overlap_audit([a, b, a]) == {
        "positive_area_pairs_gt_0_01_m2": 1,
        "near_duplicate_candidate_pairs_iou_ge_0_90": 1,
        "topologically_equal_pairs": 1,
    }


def test_release_index_includes_boundary_touch_and_selects_type():
    bound = {"xmin": 1, "xmax": 2, "ymin": 2, "ymax": 3}
    index = [
        {"collection": "building", "bbox": bound, "assets": {"aws": {"href": "chosen"}}},
        {"collection": "building_part", "bbox": bound, "assets": {"aws": {"href": "other"}}},
    ]
    assert intersecting_shards(index, "building", [2, 3, 3, 4]) == ["chosen"]
    assert intersecting_shards(index, "building", [2.01, 3, 3, 4]) == []
