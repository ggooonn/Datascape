"""Foreground continuation, mapped visibility and local inversion checks."""
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from datascape.projection.camera import Camera
from datascape.projection.composition import Composition
from datascape.projection.production import ProductionMapping, continued_power, mapping_jacobians
from datascape.rendering.spring_production import extended_grid, rasterize_mapped


def mapping():
    return ProductionMapping(Composition(Camera(240, 10, 6480, 1.8, 38),
                              (0, 0, 252.8), (-4897.2, 4897.2)))


def test_power_continuation_preserves_anchors_and_has_no_near_depth_shelf():
    d = np.linspace(-.25, 1, 1001)
    f = continued_power(d, .85, .05)
    assert np.all(np.diff(f) > 0)
    assert continued_power(0, .85, .05) == pytest.approx(0)
    assert continued_power(1, .85, .05) == pytest.approx(1)
    h = 1e-7
    left = -continued_power(-h, .85, .05) / h
    right = continued_power(h, .85, .05) / h
    assert left == pytest.approx(right, rel=1e-5)


def test_p2_preserves_existing_screen_mapping_and_raw_vertices():
    m = mapping()
    xyz = np.array([[200, -1000, 800], [1500, 1800, 100], [-1800, -2000, 200]], dtype=float)
    before = xyz.copy()
    pixel, display_depth, _, source_depth = m.project(xyz, "P2", 600, 900)
    previous, previous_depth, _ = m.base.project(xyz, "P2", 600, 900)
    np.testing.assert_array_equal(pixel, previous)
    np.testing.assert_array_equal(source_depth, previous_depth)
    assert np.isfinite(display_depth).all()
    m.project(xyz, "P3", 600, 900)
    np.testing.assert_array_equal(xyz, before)


def test_p3_foreground_continues_upward_instead_of_clamping():
    m = mapping()
    bearing = np.deg2rad(240)
    look = np.array([np.sin(bearing), np.cos(bearing)])
    xyz = np.column_stack([np.array([-5100, -5000, -4900])[:, None] * look, np.full(3, 252.8)])
    pixel, depth, d, _ = m.project(xyz, "P3", 600, 900)
    assert (d < 0).all()
    assert (np.diff(pixel[:, 1]) < 0).all()
    assert (np.diff(depth) > 0).all()


def test_mapped_triangle_visibility_is_order_independent_and_affine():
    pixel = np.array([[0, 0], [4, 0], [0, 4], [0, 0], [4, 0], [0, 4]], dtype=float)
    depth = np.array([2, 10, 10, 6.2, 6.2, 6.2], dtype=float)
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    fractions = np.array([0, 1, 1, .5, .5, .5])
    shade, _, owner, buffer = rasterize_mapped(pixel, depth, fractions, faces, np.array([.2, .8]), 4, 4)
    # At pixel (0.5,0.5), barycentric weights are .75/.125/.125.
    assert buffer[0, 0] == pytest.approx(4)
    assert owner[0, 0] == 0
    assert owner[0, 2] == 1
    reverse = rasterize_mapped(pixel, depth, fractions, faces[::-1], np.array([.8, .2]), 4, 4)
    np.testing.assert_array_equal(shade, reverse[0])
    np.testing.assert_array_equal(buffer, reverse[3])


def test_extension_keeps_nodata_and_eye_clip_separate_from_raw_source():
    z = np.arange(36, dtype='float32').reshape(6, 6)
    z[-1, -1] = np.nan
    with MemoryFile() as memory:
        with memory.open(driver='GTiff', height=6, width=6, count=1, dtype='float32',
                         crs='EPSG:32652', transform=from_origin(0, 900, 30, 30), nodata=-9999) as ds:
            ds.write(z, 1)
            m = ProductionMapping(Composition(Camera(180, 10, 120, 1.8, 38), (90, 780, 100), (-120, 120)))
            source, view, record = extended_grid(ds, [0, 720, 90, 810], m, 60)
    np.testing.assert_array_equal(source.elevation_m, z)
    assert not source.valid[-1, -1] and not view.valid[-1, -1]
    assert source.valid[:2].all() and not view.valid[:2].any()
    assert record['eye_distance_clip_pixels'] == 12


@pytest.mark.parametrize('method', ['P2', 'P3'])
def test_volume_jacobian_does_not_confuse_above_eye_flat_plane_with_warp_inversion(method):
    m = mapping()
    bearing = np.deg2rad(240)
    look = np.array([np.sin(bearing), np.cos(bearing)])
    xyz = np.column_stack([np.array([-5000, -3000, 0, 3000])[:, None] * look, np.full(4, 850)])
    volume, plane = mapping_jacobians(m, xyz, method, 600, 900)
    assert (volume > 0).all()
    if method == 'P2':
        # A synthetic flat plane above the low foreground eye can reverse in
        # 2D while the 3D mapping has no local inversion.
        assert (plane > 0).any()


def test_invalid_continuation_parameters_and_method_fail_explicitly():
    with pytest.raises(ValueError):
        continued_power([0, 1], .85, 0)
    with pytest.raises(ValueError):
        mapping().project(np.array([[0, 0, 200]]), 'P4', 600, 900)
