"""Camera geometry, occlusion, data preservation, and screen ratio checks."""
import numpy as np
import pytest
from datascape.projection.camera import Camera
from datascape.rendering.terrain_preview import rasterize_triangles,panel_pair,mesh
from datascape.terrain.candidates import TerrainGrid


def test_target_projects_to_center_and_east_is_right_when_looking_north():
    camera=Camera(0,12,4000,1.8)
    vertices=np.array([[1000,2000,300],[1100,2000,300]],dtype=float)
    original=vertices.copy()
    pixel,depth=camera.project(vertices,[1000,2000,300],1200,675)
    np.testing.assert_allclose(pixel[0],[600,337.5])
    assert pixel[1,0]>pixel[0,0]
    assert (depth>0).all()
    np.testing.assert_array_equal(vertices,original)


def test_horizontal_camera_distance_and_vertical_exaggeration_are_separate():
    camera=Camera(90,20,3000,2)
    eye,_=camera.frame([100,200,50])
    np.testing.assert_allclose(np.linalg.norm(eye[:2]-[100,200]),3000)
    assert eye[2]==pytest.approx(100+3000*np.tan(np.deg2rad(20)))


@pytest.mark.parametrize("near_first",[True,False])
def test_z_buffer_keeps_front_face_independent_of_draw_order(near_first):
    pixel=np.array([[0,0],[4,0],[0,4],[0,0],[4,0],[0,4]])
    depth=np.array([100,100,100,200,200,200])
    faces=np.array([[0,1,2],[3,4,5]])
    tones=np.array([.2,.8])
    if not near_first:faces,tones=faces[::-1],tones[::-1]
    image,inv=rasterize_triangles(pixel,depth,faces,tones,4,4)
    assert image[0,0]==pytest.approx(.2)
    assert inv[0,0]==pytest.approx(.01)


def test_depth_interpolation_is_perspective_correct():
    pixel=np.array([[0,0],[4,0],[0,4]])
    depth=np.array([100,200,400])
    _,inv=rasterize_triangles(pixel,depth,np.array([[0,1,2]]),[.5],4,4)
    assert inv[0,0]==pytest.approx(.75/100+.125/200+.125/400)


def test_pair_crop_keeps_300_40_300_proportions_and_does_not_modify_source():
    panorama=np.full((675,1200),.2)
    pair=panel_pair(panorama)
    assert pair.shape==(675,480)
    assert (pair[:,225:255]==1).all()
    assert (pair[:,:225]==.2).all() and (pair[:,255:]==.2).all()
    assert (panorama==.2).all()


def test_mesh_samples_actual_negative_and_positive_heights_without_normalizing():
    z=np.array([[-5,100,200],[20,30,40],[400,500,600]],dtype=float)
    y,x=np.mgrid[:3,:3]
    grid=TerrainGrid(z.copy(),np.ones(z.shape,dtype=bool),x*30,y*30,(0,0,90,90),(30,30))
    vertices,_,_=mesh(grid,2)
    np.testing.assert_array_equal(vertices[:,2],[-5,200,400,600])
    np.testing.assert_array_equal(grid.elevation_m,z)


def test_bad_camera_configuration_is_explicit():
    with pytest.raises(ValueError):Camera(0,0,1000)
    with pytest.raises(ValueError):Camera(0,20,-100)
