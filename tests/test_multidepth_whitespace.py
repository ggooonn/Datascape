"""Depth-scoped omission and global reserve contracts, independent of imagery."""
import numpy as np
from datascape.composition.multidepth import depth_roles,omission_retention
from datascape.vegetation.multidepth import object_retention,glyph


def test_distance_roles_partition_without_screen_row_bands():
    q=np.array([[300,1000,2200,3400,5000],[5000,3400,2200,1000,300]],dtype=float)
    roles=depth_roles(q,{'near_middle_m':[600,1600],'middle_far_m':[2600,4200]})
    np.testing.assert_allclose(sum(roles.values()),1)
    assert roles['near'][0,0]==roles['near'][1,4]==1
    assert roles['far'][0,4]==roles['far'][1,0]==1


def test_cores_and_soft_transitions_have_distinct_semantics():
    f=np.linspace(0,1,1001)
    soft=omission_retention(f,.92,.9,False);core=omission_retention(f,.92,.9,True)
    assert soft[-1]>0;assert core[-1]==0
    assert np.all(np.diff(soft)<=1e-12);assert np.all(np.diff(core)<=1e-12)
    assert np.all(core<=soft);assert np.all(core>=0)


def test_foreground_branch_survives_a_deeper_local_reserve():
    q=np.array([[3000.,100.]]);occupied=np.ones((1,2),bool)
    cfg={'omission_match_sigma_m':220,'foreground_depth_tolerance_m':80}
    r=object_retention(q,occupied,100,np.zeros_like(q),np.ones_like(q),cfg)
    assert r[0,0]>.999;assert r[0,1]==0


def test_global_reserve_applies_to_every_depth():
    q=np.array([[3000.,100.]]);occupied=np.ones((1,2),bool)
    cfg={'omission_match_sigma_m':220,'foreground_depth_tolerance_m':80}
    r=object_retention(q,occupied,100,np.ones_like(q),np.zeros_like(q),cfg)
    assert np.all(r==0)


def test_nearer_terrain_occludes_a_background_glyph():
    q=np.array([[1000.,3100.]]);occupied=np.ones((1,2),bool)
    cfg={'omission_match_sigma_m':220,'foreground_depth_tolerance_m':80}
    r=object_retention(q,occupied,3000,np.ones_like(q),np.ones_like(q),cfg)
    assert r[0,0]==0;assert r[0,1]==1


def test_grammars_are_structurally_different_and_seeded():
    root=np.array([50,70]);near=glyph(root,'near',40,np.random.default_rng(4))
    middle=glyph(root,'middle',8,np.random.default_rng(4));far=glyph(root,'far',2,np.random.default_rng(4))
    assert near==glyph(root,'near',40,np.random.default_rng(4))
    assert max(len(line) for line in near)==17
    assert max(len(line) for line in middle)==9
    assert max(len(line) for line in far)==2


def test_global_bottom_is_partial_and_local_silhouette_is_protected():
    import json
    from pathlib import Path
    from datascape.composition.multidepth import build_reserves
    cfg=json.loads((Path(__file__).parents[1]/'configs/scenes/seoul_f2_multidepth_whitespace_v02.json').read_text())
    h,w=90,60;yy,xx=np.mgrid[:h,:w];ones=np.ones((h,w));xyz=np.stack([xx+300000,yy+4000000,ones*40],axis=2)
    base={'occupied':ones.astype(bool),'depth_m':ones*200,'xyz':xyz,'slope_deg':ones*3}
    features={key:ones*.5 for key in ['valley_small','valley_medium','valley_large','noise','mound','ridge','behind_edge','relative_foot']}
    features['silhouette']=np.zeros((h,w));features['silhouette'][:2]=1
    original=xyz.copy();r=build_reserves(base,features,cfg)
    assert np.all(r['local'][:2]==0)
    assert np.ptp(r['global_bottom'][-1])>.3
    assert len(r['anchor_records'])==4
    assert np.all(r['terrain_retention']>=0) and np.all(r['terrain_retention']<=1)
    np.testing.assert_array_equal(xyz,original)


def test_missing_evidence_suppresses_all_vegetation_grammars():
    from datascape.vegetation.multidepth import vegetation_fields
    q=np.array([[200,1800,5000]],dtype=float);ones=np.ones_like(q)
    base={'occupied':ones.astype(bool),'xyz':np.stack([ones*300000,ones*4000000,ones*40],axis=2),
        'slope_deg':ones*3,'aspect_deg':ones*135}
    role=depth_roles(q,{'near_middle_m':[600,1600],'middle_far_m':[2200,3400]})
    r={'depth_roles':role,'features':{'ridge':ones,'silhouette':ones},'terrain_retention':ones}
    ndvi={s:ones*.4 for s in ['SPRING','SUMMER','AUTUMN','WINTER']};counts={s:ones*20 for s in ndvi}
    cfg={'season':'SPRING','observations_min_full':[6,12],'ndvi_range':[.1,.65],'aspect_preference_deg':135,'center_density_floor':.4}
    valid=vegetation_fields(base,ndvi,counts,r,cfg)
    assert all(valid['before'][kind].sum()>0 for kind in ['near','middle','far'])
    counts['SPRING'][:]=0
    missing=vegetation_fields(base,ndvi,counts,r,cfg)
    assert all(missing['before'][kind].sum()==0 for kind in ['near','middle','far'])


def test_archives_publish_complete_arrays_and_structured_values(tmp_path):
    import json
    from datascape.rendering.multidepth_whitespace import save_fields,save_json
    values={'mask':np.array([[True,False]]),'retention':np.array([[0,.5]],dtype=np.float16)}
    save_fields(values,tmp_path/'fields.npz')
    with np.load(tmp_path/'fields.npz') as loaded:
        for key,value in values.items():np.testing.assert_array_equal(loaded[key],value)
    save_json({'tuple_serializes_as_array':(1,2)},tmp_path/'record.json')
    assert json.loads((tmp_path/'record.json').read_text())=={'tuple_serializes_as_array':[1,2]}
    assert not list(tmp_path.glob('*.writing.*'))
