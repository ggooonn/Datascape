"""Small combination and fixed-coverage comparison contracts."""
import numpy as np
import pytest
from datascape.rendering.foreground_continuity import blend_existing_and_selective,root_ground_support,combine


def test_weight_endpoints_bounds_and_inputs_unchanged():
    existing=np.array([[.8,.6],[0,1.]]);selective=np.array([[.2,.4],[0,1.]])
    old_e=existing.copy();old_s=selective.copy()
    np.testing.assert_array_equal(blend_existing_and_selective(existing,selective,1),existing)
    np.testing.assert_array_equal(blend_existing_and_selective(existing,selective,0),selective)
    mixed=blend_existing_and_selective(existing,selective,.7)
    assert np.all(mixed>=selective) and np.all(mixed<=existing)
    np.testing.assert_array_equal(old_e,existing);np.testing.assert_array_equal(old_s,selective)
    with pytest.raises(ValueError):blend_existing_and_selective(existing,selective,1.1)


def test_common_far_global_boundary_and_vegetation_survive_combination():
    a=np.array([[.8,.3],[.1,.2]]);b=np.array([[.8,.9],[.8,.9]])
    global_gate=np.array([[1,.7],[0,0]]);vegetation=np.array([[.2,.4],[0,0]])
    c=blend_existing_and_selective(b,a,.7)
    variants=[combine(v*global_gate,vegetation) for v in [a,b,c]]
    assert all(np.all(v[-1]==0) for v in variants)
    assert all(v[0,0]==variants[0][0,0] for v in variants)
    np.testing.assert_allclose(variants[2],.7*variants[1]+.3*variants[0],atol=1e-15)
    np.testing.assert_array_equal(c[a==b],a[a==b])


def test_root_measurement_deduplicates_representatives_at_parent_sites():
    ink=np.full((20,20),.3)
    marks=[{'kind':'near','root_pixel_xy':[5.5,10.5]},
           {'kind':'near','root_pixel_xy':[5.5,10.5]},
           {'kind':'near','root_pixel_xy':[15.5,10.5]},
           {'kind':'far','root_pixel_xy':[9.5,5.5]}]
    result=root_ground_support(ink,marks,7)
    assert result['sites']==2
    assert result['mean_terrain_ink_below_root']==pytest.approx(.3)
