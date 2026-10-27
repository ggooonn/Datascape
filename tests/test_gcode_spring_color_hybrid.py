"""Hybrid reload invariants, actual contacts and source-atomic failure cases."""
from copy import deepcopy
from math import hypot
from pathlib import Path
import os
import pytest
from benchmarks.integrated_330_v01 import spring_color_execution as c
from benchmarks.integrated_330_v01 import spring_color_hybrid as h


def unit(name,slot='C1',xy=((320,100),(322,100))):
    s=c.Stroke(name,tuple(c.Point(x,y,.4) for x,y in xy),'TEST',slot,'color')
    fs=[c.Fragment(f,'P2','SHARED',tuple((p.x,900-p.y) for p in f.points)) for f in c.clip_stroke(s,c.PANELS[1])]
    return dict(id=name,original=s,fragments=fs,physical_slot=slot,legacy_slot=slot,dose_factor=1.,
        length_mm=sum(sum(hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(f.work_xy,f.work_xy[1:])) for f in fs))


def build(us,limit=15):
    policy=c.read(h.POLICY);policy['contact_limit']=limit;profile=c.make_profile(policy)
    order=list(range(len(us)));commands,material=c.build(us,order,profile,policy)
    h.audit_material(commands,material,us,order,policy)
    return commands,material,profile,policy


@pytest.mark.parametrize('limit,loads',[(15,3),(20,2),(30,2)])
def test_preferred_and_sensitivity_thresholds(limit,loads):
    us=[unit('short-'+str(i),xy=((320,100+i*2),(322,100+i*2))) for i in range(31)]
    commands,m,p,cfg=build(us,limit)
    assert m['total_loads']==loads and m['contact_count']==31
    assert m['maximum_contacts_since_load']==limit
    assert m['pigment_changes']==0 and m['wash_count']==0
    assert all(r['reason']=='contact_limit' and not r['wash_performed'] for r in m['loads'][1:])
    assert all(r['after_load_budget']==dict(distance_mm=0.,actual_paper_contacts=0) for r in m['loads'])


def test_many_vertices_are_one_actual_contact():
    us=[unit('many-vertices',xy=tuple((320+i,100) for i in range(41)))]
    commands,m,p,cfg=build(us)
    assert sum(x.artistic_pressure is not None for x in commands)==41
    assert m['contact_count']==1 and m['maximum_contacts_since_load']==1 and m['total_loads']==1


def test_split_source_finishes_before_contact_reload():
    us=[unit('split',xy=((320,100),(290,100),(320,120))),unit('next')]
    assert len(us[0]['fragments'])==2
    commands,m,p,cfg=build(us,1)
    assert m['contact_count']==3 and m['total_loads']==2
    assert m['events'][0]['actual_paper_contacts']==2
    assert m['events'][0]['atomic_contact_overrun']==1
    assert m['loads'][1]['previous_contacts']==2 and m['loads'][1]['before_source']=='next'
    assert m['loads'][1]['first_command']>m['events'][0]['last_command']
    assert m['events'][1]['before']==dict(distance_mm=0.,actual_paper_contacts=0)


def test_distance_trigger_can_occur_first():
    us=[unit('long-'+str(i),xy=((320,100+i*3),(550,100+i*3),(320,100+i*3))) for i in range(3)]
    commands,m,p,cfg=build(us,15)
    assert m['total_loads']==2 and m['loads'][1]['reasons']==['distance_limit']
    assert m['loads'][1]['previous_contacts']==2
    assert m['maximum_atomic_distance_overrun_mm']==pytest.approx(320)
    assert m['maximum_atomic_contact_overrun']==0


def test_simultaneous_limits_reload_once_and_reset_both():
    us=[unit('both-'+str(i),xy=((320,100+i*3),(550,100+i*3),(320,100+i*3))) for i in range(3)]
    commands,m,p,cfg=build(us,2)
    assert m['total_loads']==2
    assert m['loads'][1]['reasons']==['distance_limit','contact_limit']
    assert m['same_pigment_trigger_counts']=={'both':1}
    assert m['events'][2]['before']==dict(distance_mm=0.,actual_paper_contacts=0)


def test_pigment_change_at_contact_limit_is_not_double_loaded():
    us=[unit('old-'+str(i),xy=((320,100+i*2),(322,100+i*2))) for i in range(15)]+[unit('new','A5')]
    commands,m,p,cfg=build(us,15)
    assert m['total_loads']==2 and m['pigment_changes']==1 and m['same_pigment_reloads']==0
    assert m['loads'][1]['reasons']==['pigment_change']
    assert m['loads'][1]['threshold_reasons_before_service']==['contact_limit']
    assert m['wash_count']==1 and m['terminal_water_visits']==3


@pytest.mark.parametrize('bad',[0,-1,True,1.5,'15'])
def test_contact_limit_must_be_positive_integer_or_none(bad):
    policy=c.read(h.POLICY);policy['contact_limit']=bad
    with pytest.raises(ValueError):c.make_profile(policy)


def test_omitted_replenishment_fails_independent_contact_audit():
    us=[unit('short-'+str(i),xy=((320,100+i*2),(322,100+i*2))) for i in range(16)]
    commands,m,p,cfg=build(us,None)
    strict=deepcopy(cfg);strict['contact_limit']=15
    with pytest.raises(ValueError):h.audit_material(commands,m,us,list(range(16)),strict)


def test_contact_or_washing_audit_mutation_rejected():
    us=[unit('split',xy=((320,100),(290,100),(320,120))),unit('next')]
    commands,m,p,cfg=build(us,1);broken=deepcopy(m);broken['events'][0]['actual_paper_contacts']=1
    with pytest.raises(ValueError):h.audit_material(commands,broken,us,[0,1],cfg)
    broken=deepcopy(m);broken['loads'][1]['wash_performed']=True
    with pytest.raises(ValueError):h.audit_material(commands,broken,us,[0,1],cfg)
    broken=deepcopy(m);broken['loads'][1]['after_load_budget']['actual_paper_contacts']=2
    with pytest.raises(ValueError):h.audit_material(commands,broken,us,[0,1],cfg)


def test_matching_AIR_retains_load_XY_and_no_contact():
    us=[unit('a'+str(i),xy=((320,100+i*2),(322,100+i*2))) for i in range(16)]
    commands,m,p,cfg=build(us)
    air=c.air_projection(commands,p)
    assert [x.xyz[:2] for x in air if x.kind=='move']==[x.xyz[:2] for x in commands if x.kind=='move']
    assert all(x.xyz[2]==35 for x in air if x.kind=='move')
    text=c.BANNER+c._serialize(air,p,'test','AIR','air')
    c.verify_numeric(text,air,p,us,list(range(16)),cfg,air=True)


def test_full_hybrid_delivery_when_requested():
    output=os.environ.get('DATASCAPE_COLOR_HYBRID_REVIEW');context=os.environ.get('DATASCAPE_COLOR_CONTEXT')
    if not output or not context:pytest.skip('Set hybrid delivery paths for complete numerical integration readback')
    proof=h.verify(Path(output),Path(context))
    assert proof['program_pairs_verified']==7 and proof['selected_sources']==3947
    assert proof['contact_limit']==15 and proof['no_same_pigment_washing']
