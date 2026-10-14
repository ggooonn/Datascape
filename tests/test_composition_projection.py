"""Checks for continuous depth mapping, overlap order and physical panel layout."""
import numpy as np
import pytest

from datascape.projection.camera import Camera
from datascape.projection.composition import Composition, depth_weights, insert_panel_gap
from datascape.rendering.composition_study import rasterize
from datascape.rendering.terrain_preview import rasterize_triangles


def composition():
    return Composition(Camera(0, 10, 6000, 1.8, 38), (0, 0, 200), (-4000, 4000))


def test_p0_matches_existing_camera_and_all_methods_preserve_raw_vertices():
    mapping = composition()
    xyz = np.array([[-200, -2500, 40], [100, 0, 800], [0, 2200, 250]], dtype=float)
    before = xyz.copy()
    expected, depth = mapping.camera.project(xyz, mapping.target_raw_xyz_m, 600, 900)
    for method in ("P0", "P1", "P2", "P3"):
        pixel, source_depth, fractions = mapping.project(xyz, method, 600, 900)
        assert np.array_equal(xyz, before)
        assert np.array_equal(source_depth, depth)
        assert np.isfinite(pixel).all()
        assert ((fractions >= 0) & (fractions <= 1)).all()
        if method == "P0":
            np.testing.assert_array_equal(pixel, expected)


def test_multiview_transition_has_no_position_or_slope_jump():
    mapping = composition()
    # Flat surface crossing each blend boundary at fixed east coordinate.
    for center in (1 / 3, 2 / 3):
        for d in (center - .06, center, center + .06):
            h = 1e-6
            fraction = np.array([d - h, d, d + h])
            xyz = np.column_stack([np.full(3, 200), -4000 + 8000 * fraction, np.full(3, 200)])
            pixel, _, _ = mapping.project(xyz, "P2", 600, 900)
            left = (pixel[1] - pixel[0]) / h
            right = (pixel[2] - pixel[1]) / h
            assert np.linalg.norm(left - right) < .1
            weights = depth_weights(fraction)
            np.testing.assert_allclose(weights.sum(axis=1), 1)
            assert (weights >= 0).all()


def test_scroll_unfolds_flat_ground_upward_without_horizontal_depth_shrinkage():
    mapping = composition()
    xyz = np.array([[250, -3500, 200], [250, 0, 200], [250, 3500, 200]])
    pixel, _, _ = mapping.project(xyz, "P3", 600, 900)
    assert np.all(np.diff(pixel[:, 1]) < 0)
    np.testing.assert_allclose(pixel[:, 0], pixel[0, 0])


def test_inserted_gap_preserves_every_pixel_in_both_panels():
    image = np.arange(48).reshape(6, 8)
    physical = insert_panel_gap(image, 3)
    restored = np.concatenate([physical[:, :4], physical[:, 7:]], axis=1)
    np.testing.assert_array_equal(restored, image)
    assert physical.shape == (6, 11)
    np.testing.assert_array_equal(physical[:, 4:7], 1)
    with pytest.raises(ValueError):
        insert_panel_gap(image[:, :7], 3)


def test_compositor_matches_existing_perspective_visibility_and_near_wins():
    triangle = np.array([[0, 0], [6, 0], [0, 6]], dtype=float)
    pixel = np.concatenate([triangle, triangle])
    depth = np.array([10, 11, 12, 2, 2, 2], dtype=float)
    fraction = np.array([.9, .9, .9, .1, .1, .1])
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    tones = np.array([.8, .2])
    expected, _ = rasterize_triangles(pixel, depth, faces, tones, 6, 6)
    actual, visible, owners = rasterize(pixel, depth, fraction, faces, tones, 6, 6)
    np.testing.assert_array_equal(actual, expected)
    assert actual[1, 1] == pytest.approx(.2)
    assert visible[1, 1] == pytest.approx(.1)
    assert owners[1, 1] == 1
    reverse = rasterize(pixel, depth, fraction, faces[::-1], tones[::-1], 6, 6)
    np.testing.assert_array_equal(reverse[0], actual)


def test_invalid_method_and_depth_extent_are_rejected():
    with pytest.raises(ValueError):
        composition().project(np.array([[0, 0, 200]]), "missing", 600, 900)
    mapping = Composition(Camera(0, 10, 6000), (0, 0, 200), (1, 1))
    with pytest.raises(ValueError):
        mapping.depth_fraction(np.array([[0, 0, 200]]))
