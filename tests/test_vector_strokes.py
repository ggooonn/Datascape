"""Physical boundary, omission, exact seam and shared-data contracts."""
import numpy as np
from scipy.ndimage import distance_transform_edt
from datascape.strokes.vector import clip_polyline, split_at_gate, omit_path, finalize, save_vectors, read_vectors, resample, sample, simplify, thin_parallel_paths
from datascape.rendering.vector_study import write_svg, validate_vectors


def test_exact_outside_crossing_and_seam():
    p=np.array([[-20.,400.],[620.,400.]])
    runs=clip_polyline(p,(0,0,600,900))
    assert len(runs)==1
    np.testing.assert_allclose(runs[0],[[0,400],[600,400]])
    strokes=finalize(runs,'test',.32,{'layer':'terrain'})
    assert [s['panel'] for s in strokes]==[1,2]
    assert strokes[0]['xy_mm'][-1]==strokes[1]['xy_mm'][0]==[300.,400.]
    assert sum(np.linalg.norm(np.diff(s['xy_mm'],axis=0),axis=1).sum() for s in strokes)==600


def test_gate_intersections_do_not_bridge_omission():
    p=np.column_stack([np.arange(5.),np.ones(5)*20])
    runs=split_at_gate(p,[1,1,-1,1,1])
    assert len(runs)==2
    np.testing.assert_allclose(runs[0][-1],[1.5,20])
    np.testing.assert_allclose(runs[1][0],[2.5,20])


def test_true_empty_core_and_bottom_footprint():
    probability=np.ones((900,600));probability[300:400]=0
    safe=distance_transform_edt(probability>0)
    paths=omit_path([[200.,200.],[200.,900.]],probability,safe,'core',71,.32,1)
    assert len(paths)>=2
    for path in paths:
        dense=resample(path,.1)
        assert not np.any((dense[:,1]>300)&(dense[:,1]<400))
        assert dense[:,1].max()+.16<898
    assert validate_vectors(finalize(paths,'test',.32,{'layer':'terrain'}),safe,.32)['last_2mm_footprint_empty']


def test_density_changes_paths_not_opacity():
    safe=np.full((900,600),100.)
    high=np.ones_like(safe);low=high*.2
    p=np.array([[50.,600.],[550.,600.]])
    a=omit_path(p,high,safe,'same',123,.32,2)
    b=omit_path(p,low,safe,'same',123,.32,2)
    length=lambda runs:sum(np.linalg.norm(np.diff(x,axis=0),axis=1).sum() for x in runs)
    assert 0<length(b)<length(a)*.4
    assert len(b)>len(a)
    assert all(s['opacity']==1 for s in finalize(b,'x',.32))
    assert len(b)==len(omit_path(p,low,safe,'same',123,.32,2))


def test_roundtrip_is_the_svg_geometry(tmp_path):
    strokes=finalize([np.array([[11.123456,40.],[299.99,50.],[320.,60.]])],'A',.32,{'layer':'terrain'})
    target=tmp_path/'strokes.json.gz';save_vectors(target,strokes,{'seed':3})
    decoded=read_vectors(target)['strokes'];assert decoded==strokes
    first=target.read_bytes();save_vectors(target,strokes,{'seed':3});assert target.read_bytes()==first
    svg=tmp_path/'panel.svg';write_svg(decoded,svg,2);text=svg.read_text()
    assert 'opacity' not in text and 'stroke="black"' in text
    assert '20,60' in text and 'width="300mm"' in text


def test_field_sampling_uses_pixel_centers():
    grid=np.arange(12).reshape(3,4)
    np.testing.assert_allclose(sample(grid,[[.5,.5],[3.5,2.5]]),[0,11])
    assert sample(grid,[[-1,1]])[0]==0
    assert sample(grid,[[.1,2.5]],order=0)[0]==8


def test_simplification_preserves_a_corner_and_submillimeter_shape():
    p=np.array([[0,0],[1,.001],[2,0],[2,1],[2,2]])
    np.testing.assert_allclose(simplify(p),[[0,0],[2,0],[2,2]])


def test_parallel_retracing_is_removed_but_crossings_survive():
    paths=[np.array([[10.,40.],[90.,40.]]),np.array([[12.,40.2],[88.,40.2]]),np.array([[50.,10.],[50.,80.]])]
    result=thin_parallel_paths(paths)
    assert len(result)==2
    length=sum(np.linalg.norm(np.diff(p,axis=0),axis=1).sum() for p in result)
    assert abs(length-150)<.01
