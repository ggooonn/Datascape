"""Meaningful visibility/identity invariants; no physical brush claims."""
from copy import deepcopy
import numpy as np
import pytest
from shapely.geometry import LineString
from datascape.integration.visibility import (SHAPE,adapt,clip_source,depth_field,
    signed_clearance,terrain_gate,digest,contact)


def record():
    return dict(id='A/original',xy_mm=[[0.,10.],[5.,10.],[10.,10.]],layer='A',width_mm=.6,
        source_stroke_id='older-generator',source_arc_mm=[7.,17.],
        width_profile_mm=[.2,.4,.8],opacity_profile=[.2,.6,1.],
        expression=dict(intensity_samples=[0.,.5,1.],pressure_calibrated=False))


def test_adaptation_preserves_original_and_upstream_identity():
    original=record();before=deepcopy(original);r=adapt(original,'baseline','baseline/A','A')
    assert original==before
    assert r['source_stroke_id']=='A/original'
    assert r['upstream_source_stroke_id']=='older-generator'
    assert r['upstream_source_arc_mm']==[7.,17.]
    assert r['source_arc_mm']==[0.,10.]


def test_exact_arc_endpoints_profiles_and_length_conservation():
    r=adapt(record(),'baseline','baseline/A','A')
    def gate(xy,arc,r):return np.abs(arc-5)-1.13,['bounded-crossing']
    out,a=clip_source(r,gate,step_mm=.35,minimum_mm=.5)
    assert len(out)==2
    assert out[0]['source_arc_mm']==pytest.approx([0.,3.87])
    assert out[1]['source_arc_mm']==pytest.approx([6.13,10.])
    assert out[0]['xy_mm'][-1]==pytest.approx([3.87,10.])
    assert out[0]['width_profile_mm'][-1]==pytest.approx(.3548)
    assert out[1]['opacity_profile'][0]==pytest.approx(.6904)
    for p in out:
        assert len(p['expression']['intensity_samples'])==len(p['xy_mm'])
    kept=sum(LineString(p['xy_mm']).length for p in out)
    assert kept+a['removed_mm']==pytest.approx(10.)


def test_small_fragments_drop_without_reconnection():
    r=adapt(record(),'baseline','baseline/A','A')
    out,a=clip_source(r,lambda xy,arc,r:(np.abs(arc-5)-4.,['cut']),minimum_mm=2.8)
    assert out==[]
    assert a['removed_mm']==pytest.approx(10.)
    assert a['short_dropped_mm']==pytest.approx(2.)


def test_zero_gate_retains_original_geometry_profiles_and_id():
    r=adapt(record(),'baseline','baseline/A','A')
    out,a=clip_source(r)
    assert out==[r] and a['removed_mm']==0


def test_depth_field_is_bounded_and_does_not_convert_height_to_world_meters():
    site=dict(source_forward_m=500.,xy_mm=[300.,700.],lateral_q_per_mm=5.)
    q=depth_field(site,lateral_bound_m=35.)
    assert q.min()==465 and q.max()==535
    assert np.array_equal(q[0],q[-1])


def test_terrain_nearer_than_visible_object_stays_and_order_is_deterministic():
    fixed=dict(base=dict(depth_m=np.full(SHAPE,1200.)))
    body=np.zeros(SHAPE,bool);body[8:13,3:7]=True
    objs=[]
    for key,q in [('near',1000.),('rear',1500.)]:
        objs.append(dict(id=key,q=np.full(SHAPE,q),body_distance=signed_clearance(body),
                         regions=dict(soft=np.zeros(SHAPE))))
    r=adapt(record(),'baseline','baseline/A','A')
    gate1=terrain_gate(fixed,objs);gate2=terrain_gate(fixed,list(reversed(objs)))
    a,_=clip_source(r,gate1,minimum_mm=.1);b,_=clip_source(r,gate2,minimum_mm=.1)
    assert digest(a)==digest(b)
    fixed['base']['depth_m'][:]=800
    c,audit=clip_source(r,terrain_gate(fixed,objs))
    assert c==[r] and audit['removed_mm']==0


def test_exact_contact_preserves_source_xyz_and_forward_coordinate():
    # A nonaxis-aligned triangle checks the actual barycentric mapping.
    t=dict(owners=np.zeros(SHAPE,int),faces=np.array([[0,1,2]]),
        pixel=np.array([[0.,0.],[600.,0.],[0.,900.]]),
        xyz=np.array([[100.,200.,0.],[700.,200.,60.],[100.,1100.,90.]]),source_ids=np.array([27]))
    b={k:np.ones(SHAPE) for k in ['slope_deg','current_ndvi','current_observations']}
    fixed=dict(terrain=t,base=b,retention=np.ones(SHAPE),scene=dict(primary_eye_xy_m=[0,0],look_target_xy_m=[1,0]))
    site=contact(fixed,[150.,225.])
    assert site['barycentric']==pytest.approx([.5,.25,.25])
    assert site['source_xyz_utm_m']==pytest.approx([250.,425.,37.5])
    assert site['source_forward_m']==pytest.approx(250.)
    assert site['original_mesh_face_id']==27


def test_forced_V_replacement_is_explicit_and_does_not_reroll_source():
    r=adapt(record(),'baseline','baseline/V','V');before=digest(r)
    out,a=clip_source(r,force_reason='selected-V-root-replacement:root-7')
    assert not out and a['reasons']==['selected-V-root-replacement:root-7']
    assert digest(r)==before


def test_contact_priority_is_local_and_keeps_catalog_rank_distinct_from_meters():
    from datascape.integration.visibility import behind_object
    a=dict(kind='tree',group='contact-a')
    b=dict(kind='rock',group='contact-a',parent_mass_id='mass-a',catalog_local_rank=4.)
    assert behind_object(b,a,np.array([500.]),np.array([500.])).all()
    assert not behind_object(a,b,np.array([500.]),np.array([500.])).any()
    other=dict(kind='tree',group='contact-b')
    assert not behind_object(b,other,np.array([500.]),np.array([500.])).any()
    front=dict(b,catalog_local_rank=2.8)
    assert behind_object(b,front,np.array([500.]),np.array([500.])).all()
    assert not behind_object(front,b,np.array([500.]),np.array([500.])).any()


def test_catalog_rounding_cannot_sneak_short_new_paths_past_final_minimum():
    r=dict(id='new',xy_mm=[[1.,1.],[3.797,1.]],origin_kind='new-catalog',width_mm=.6)
    out,audit=clip_source(r)
    assert not out
    assert audit['short_dropped_mm']==pytest.approx(2.797)
