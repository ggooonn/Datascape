"""Final boundary and immutable composition contracts."""
import json
from pathlib import Path
import numpy as np
from datascape.composition.refinement import boundary_retention,apply_boundary,positive_forms,representative_trees

CONFIG=json.loads((Path(__file__).parents[1]/'configs/scenes/seoul_f2_painterly_composition_v03.json').read_text())


def test_bottom_boundary_is_zero_for_every_object_and_channel():
    y=np.array([860.,885.,898.,900.,910.]);contribution=np.ones((5,4))
    result=apply_boundary(contribution,y,**CONFIG['boundary'])
    assert np.all(result[2:]==0)
    assert 0<result[1,0]<1;assert result[0,0]==1
    assert float(boundary_retention(900,hard_bottom_guard_mm=0))==0
    edges=(np.arange(900)+1)*900/900
    assert boundary_retention(edges,hard_bottom_guard_mm=0)[-1]==0


def test_boundary_transition_is_continuous_and_guard_is_independent():
    y=np.linspace(870,905,1001);r=boundary_retention(y,**CONFIG['boundary'])
    assert np.all(np.diff(r)<=0)
    assert np.max(np.abs(np.diff(r)))<.004
    assert boundary_retention(850,collar_mm=18)==1
    assert boundary_retention(850,collar_mm=60)<1


def test_positive_forms_follow_translated_dem_evidence_not_fixed_x_bins():
    from copy import deepcopy
    h,w=90,100;yy,xx=np.mgrid[:h,:w];ones=np.ones((h,w))
    base={'occupied':ones.astype(bool),'depth_m':ones*600,'slope_deg':ones*4,
        'xyz':np.stack([xx*10+300000,yy*10+4000000,ones*60],axis=2)}
    cfg={**CONFIG['positive_forms'],'maximum_count':1}
    original=base['xyz'].copy()
    def evidence(col):
        mound=np.exp(-.5*((xx-col)**2+(yy-73)**2)/4)
        return {'mound':mound,'macros':[ones*58]}
    _,_,_,left=positive_forms(base,evidence(15),[],cfg)
    _,_,_,right=positive_forms(base,evidence(71),[],cfg)
    assert len(left)==len(right)==1
    assert abs(right[0]['pixel_xy'][0]-left[0]['pixel_xy'][0]-56)<1
    np.testing.assert_array_equal(base['xyz'],original)


def test_representatives_preserve_small_marks_and_real_root_metadata():
    from copy import deepcopy
    h,w=90,120;ones=np.ones((h,w));q=ones*1600;q[60:]=400
    base={'occupied':ones.astype(bool),'depth_m':q}
    r={'terrain_retention':ones*.5,'positive':ones*.6,'local_core_retention':ones*.4}
    marks=[]
    for i,x in enumerate([15,22,30,70,78,86]):
        marks.append({'id':str(i),'kind':'near','root_pixel_xy':[x+.5,75.5],'ndvi':.4,
            'source_xyz_m':[300000+x*30,4000000,40],'forward_depth_m':400,'polylines_pixel_xy':[[[x,75],[x,70]]],'height_mm':50})
    snapshot=deepcopy(marks);cfg={**CONFIG['representative_trees'],'count':2,'minimum_spacing_mm':135}
    a=representative_trees(marks,base,r,cfg,12);b=representative_trees(marks,base,r,cfg,12)
    json.dumps(a,allow_nan=False)
    assert a==b;assert len(a)==2;assert marks==snapshot
    for tree in a:
        parent=next(m for m in marks if m['id']==tree['parent_small_mark_id'])
        assert tree['source_xyz_m']==parent['source_xyz_m'] and tree['root_pixel_xy']==parent['root_pixel_xy']
        assert tree['height_mm']>parent['height_mm']
        assert abs(tree['root_pixel_xy'][0]*600/w-300)>=cfg['minimum_trunk_seam_distance_mm']
