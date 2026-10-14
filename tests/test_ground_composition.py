"""Physical camera, measured-surface clipping and invertible composite checks."""
import numpy as np
import pytest

from datascape.projection.camera import Camera
from datascape.projection.ground import GroundCamera,GroundComposite
from datascape.rendering.ground_composition import clip_near_plane


@pytest.mark.parametrize('bearing,forward',[(0,[0,1,0]),(90,[1,0,0])])
def test_ground_camera_uses_clockwise_bearing_and_raw_metric_coordinates(bearing,forward):
    camera=GroundCamera((100,200,42),bearing,0,36)
    eye,basis=camera.frame()
    np.testing.assert_allclose(basis@basis.T,np.eye(3),atol=1e-12)
    pixel,depth=camera.project(eye[None,:]+np.array(forward)[None,:]*100,600,900)
    np.testing.assert_allclose(pixel,[[300,450]],atol=1e-9)
    assert depth[0]==pytest.approx(100)


def test_ground_pinhole_matches_existing_camera_for_raw_height_downward_view():
    previous=Camera(240,10,6480,1.0,38)
    target=[321720,4171370,252.8]
    eye,_=previous.frame(target)
    grounded=GroundCamera(tuple(eye),240,-10,38)
    xyz=np.array([[321000,4170000,800],[323000,4171500,40]],dtype=float)
    a,da=previous.project(xyz,target,600,900)
    b,db=grounded.project(xyz,600,900)
    np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-9)
    np.testing.assert_allclose(da,db,rtol=1e-10,atol=1e-9)


def test_near_clipping_preserves_original_vertices_and_intersects_existing_edges():
    xyz=np.array([[0,0,-1],[2,0,2],[0,2,2]],dtype=float);before=xyz.copy()
    vertices,faces,ids,record=clip_near_plane(xyz,np.array([[0,1,2]]),xyz[:,2],1)
    np.testing.assert_array_equal(xyz,before)
    assert faces.shape==(2,3)
    assert (vertices[faces,2]>=1).all()
    assert (ids==0).all()
    intersections=vertices[3:]
    np.testing.assert_allclose(intersections[:,2],1)
    assert record['crossing_source_triangles']==1
    assert record['edge_intersection_vertices']==2


def test_composite_inverts_known_depth_without_relocating_source_coordinates():
    c=GroundCamera((325305,4168385,40.128),292.12194,0,36)
    mapping=GroundComposite(c,38.128)
    az=np.deg2rad(c.azimuth_deg);r=np.array([-200,0,300,400]);q=np.array([100,700,2500,5000])
    xy=np.array(c.eye_xyz_m[:2])+r[:,None]*[np.cos(az),-np.sin(az)]+q[:,None]*[np.sin(az),np.cos(az)]
    xyz=np.column_stack([xy,[40,70,200,800]]);before=xyz.copy()
    pixel,depth=mapping.project(xyz,600,900)
    recovered=mapping.unproject(pixel,depth,600,900)
    np.testing.assert_allclose(recovered,xyz,atol=1e-9)
    np.testing.assert_array_equal(xyz,before)


def test_analytic_volume_determinant_matches_numeric_derivatives_across_depth_bands():
    c=GroundCamera((0,0,42),0,0,36);m=GroundComposite(c,40)
    xyz=np.array([[20,100,40],[100,700,60],[200,2000,400],[300,4000,800]],dtype=float)
    h=.001;derivatives=[]
    for axis in range(3):
        delta=np.zeros(3);delta[axis]=h
        p,z=m.project(xyz+delta,600,900);n,d=m.project(xyz-delta,600,900)
        derivatives.append((np.column_stack([p,z])-np.column_stack([n,d]))/(2*h))
    numeric=np.linalg.det(np.stack(derivatives,axis=2));analytic=m.volume_determinant(xyz,600,900)
    assert (analytic>0).all()
    np.testing.assert_allclose(numeric,analytic,rtol=1e-6)


def test_ground_composite_unfolds_flat_ground_upward_and_keeps_near_width_broad():
    c=GroundCamera((0,0,42),0,0,36);m=GroundComposite(c,40)
    xyz=np.array([[200,100,40],[200,800,40],[200,2400,40],[200,5000,40]],dtype=float)
    pixel,_=m.project(xyz,600,900)
    assert (np.diff(pixel[:,1])<0).all()
    assert (np.diff(pixel[:,0])<0).all()
    assert pixel[0,1]>800 and pixel[-1,1]<500


def test_invalid_view_or_collapsed_composite_is_rejected():
    with pytest.raises(ValueError):GroundCamera((0,0,40),0,90,36)
    c=GroundCamera((0,0,40),0)
    with pytest.raises(ValueError):GroundComposite(c,40,height_coefficients_per_km=(0,.2,.3))
    with pytest.raises(ValueError):GroundComposite(c,40,width_growth=-1)


def test_behind_triangles_are_removed_without_changing_source_data():
    xyz=np.array([[0,0,-3],[2,0,-2],[0,2,-1]],dtype=float)
    new,faces,ids,record=clip_near_plane(xyz,np.array([[0,1,2]]),xyz[:,2],1)
    np.testing.assert_array_equal(new,xyz)
    assert faces.shape==(0,3) and len(ids)==0
    assert record['behind_plane_source_triangles']==1
