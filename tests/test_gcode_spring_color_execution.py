"""Registration, pigment state, clipping and delivered-motion failure cases."""
from copy import deepcopy
from pathlib import Path
import gzip, json, os, subprocess
import pytest
from benchmarks.integrated_330_v01 import spring_color_execution as c


def unit(name,slot='C1',xy=((320,100),(360,100)),pressures=(.2,.8),rank=0):
    points=tuple(c.Point(x,y,p) for (x,y),p in zip(xy,pressures))
    original=c.Stroke(name,points,'TEST',slot,'color')
    fragments=[c.Fragment(s,'P2','SHARED',tuple((p.x,900-p.y) for p in s.points)) for s in c.clip_stroke(original,c.PANELS[1])]
    return dict(id=name,original=original,fragments=fragments,physical_slot=slot,legacy_slot=slot,
        length_mm=sum(sum(c.hypot(q[0]-p[0],q[1]-p[1]) for p,q in zip(f.work_xy,f.work_xy[1:])) for f in fragments),
        dose_factor=1.,rank=rank,slot_rank=['A2','A4','C1','A5','C3','C2','D1'].index(slot),
        group='authored-body',body='body',center=[340,800],
        style=dict(role='structural',depth_role='near'),rich=dict(width_mm=1.,color_kind='vegetation',source_family='RSU'))


@pytest.fixture
def setup():
    policy=c.read(c.POLICY)
    return policy,c.make_profile(policy)


def program(us,setup):
    policy,profile=setup;order=list(range(len(us)));commands,material=c.build(us,order,profile,policy)
    text=c.BANNER+c._serialize(commands,profile,'test','TEST','painting')
    return text,commands,material


def test_color_curve_is_separate_and_unmeasured(setup):
    policy,p=setup
    assert p.data['brush_profiles']['color']['knots']!=p.data['brush_profiles']['ink']['knots']
    assert p.brush_for('color','C1').work_z_for(.8)==pytest.approx(8.2)
    assert p.brush_for('color','C1').work_z_for(1)==pytest.approx(7.6)
    assert p.data['evidence']==[] and p.data['brush_profiles']['color']['status']=='unverified'
    assert p.data['machine']['validated_free_boxes']==[]


def test_seam_pressure_interpolation_remains_global(setup):
    u=unit('crossing',xy=((299,100),(301,100)),pressures=(.2,.8))
    assert u['fragments'][0].work_xy[0]==(300,800)
    assert u['fragments'][0].stroke.points[0].pressure==pytest.approx(.5)
    text,commands,m=program([u],setup)
    samples=[x for x in commands if x.artistic_pressure is not None]
    assert samples[0].xyz==pytest.approx((300,800,9.05))
    c.verify_numeric(text,commands,setup[1],[u],[0],setup[0])


def test_original_seam_only_path_not_duplicated():
    assert unit('seam',xy=((300,100),(300,140)))['fragments']==[]


def test_numeric_XYZ_tamper_rejected(setup):
    u=unit('registered');text,commands,m=program([u],setup)
    bad=text.replace('X320.000000000 Y800.000000000','X20.000000000 Y800.000000000',1)
    with pytest.raises(ValueError):c.verify_numeric(bad,commands,setup[1],[u],[0],setup[0])


def test_numeric_extra_pause_rejected(setup):
    u=unit('registered');text,commands,m=program([u],setup)
    with pytest.raises(ValueError):c.verify_numeric(text.replace('M2','M0\nM2'),commands,setup[1],[u],[0],setup[0])


def test_AIR_preserves_XY_and_all_stations_at35(setup):
    u=unit('air');text,commands,m=program([u],setup);p=setup[1]
    air=c.air_projection(commands,p)
    assert [x.xyz[:2] for x in air if x.kind=='move']==[x.xyz[:2] for x in commands if x.kind=='move']
    assert all(x.xyz[2]==35 for x in air if x.kind=='move')
    text=c.BANNER+c._serialize(air,p,'test','AIR','air')
    c.verify_numeric(text,air,p,[u],[0],setup[0],air=True)
    with pytest.raises(ValueError):c.verify_numeric(text.replace('Z35.000000000','Z34.000000000',1),air,p,[u],[0],setup[0],air=True)


def test_same_pigment_distance_reload_does_not_wash(setup):
    us=[unit('long-'+str(i),xy=((320,100+i*5),(550,100+i*5),(320,100+i*5)),pressures=(.4,.4,.4)) for i in range(3)]
    text,commands,m=program(us,setup)
    assert m['pigment_changes']==0 and m['same_pigment_reloads']==1
    assert [r['reason'] for r in m['loads']]==['initial_load','distance_limit']
    assert m['loads'][1]['wash_performed'] is False
    assert not any(r['action']=='wash' for r in m['station_operations'])
    assert m['maximum_atomic_distance_overrun_mm']==pytest.approx(320)
    assert m['terminal_water_visits']==3


def test_actual_pigment_change_washes_once_and_cleans_terminal(setup):
    us=[unit('base','C1'),unit('core','A5')];text,commands,m=program(us,setup)
    assert m['pigment_changes']==1 and m['same_pigment_reloads']==0
    assert sum(r['action']=='wash' for r in m['station_operations'])==1
    assert sum(r['action']=='controlled_rewet' for r in m['station_operations'])==1
    assert sum(r['action']=='terminal_wash' for r in m['station_operations'])==3
    assert any(x.action=='park' and x.xyz==(800,800,35) for x in commands)
    assert 'M0' not in text and text.endswith('M2\n')


def test_weakening_changes_execution_compression_not_artistic_pressure(setup):
    a=unit('weak');b=deepcopy(a);b['dose_factor']=.65
    _,ca,_=program([a],setup);_,cb,_=program([b],setup)
    aa=[x for x in ca if x.artistic_pressure is not None];bb=[x for x in cb if x.artistic_pressure is not None]
    assert [x.artistic_pressure for x in aa]==[x.artistic_pressure for x in bb]
    assert all(y.xyz[:2]==x.xyz[:2] and y.xyz[2]==pytest.approx(10-(10-x.xyz[2])*.65) for x,y in zip(aa,bb))


def test_local_under_over_order_can_differ_from_original_rank(setup):
    us=[unit('upper','C2',rank=0),unit('under','C1',rank=1)]
    edges,_=c.layering(us);assert (1,0) in edges
    order,batches,wet=c.schedule(us,edges,setup[0]);assert order==[1,0]


def test_missing_palette_or_unsupported_curve_fails(setup):
    policy,p=setup;bad=deepcopy(p.data);bad['brush_profiles']['color']['knots']=[[0,0],[1,1]]
    with pytest.raises(ValueError):c.Profile.from_dict(bad).brush_for('color','A2')
    changed=deepcopy(policy);changed['paper_first_touch_z']=12
    with pytest.raises(ValueError):c.make_profile(changed)
    bad=deepcopy(p.data);bad['stations']['C1']['liquid_reference_z']=1
    with pytest.raises(ValueError):program([unit('bad')],(policy,c.Profile.from_dict(bad)))


def test_published_PR42_uses_current_review_role():
    policy=c.read(c.POLICY)
    try:raw=subprocess.check_output(['git','show',policy['ink_compatibility_commit']+':docs/spring_a_hierarchy_v01/review/source_roles.json.gz'],cwd=c.ROOT,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:pytest.skip('Pinned PR42 commit absent in this shallow checkout')
    rows=json.loads(gzip.decompress(raw))
    actual=c.Counter('fine' if r['review_role'].startswith('fine_') else 'color' if r['review_role']=='color' else 'main' for r in rows)
    legacy=c.Counter(r['variant_B'] for r in rows)
    assert actual==dict(main=985,fine=224,color=642)
    assert legacy!=actual


def test_delivered_full_panel_when_requested():
    output=os.environ.get('DATASCAPE_COLOR_REVIEW');context=os.environ.get('DATASCAPE_COLOR_CONTEXT')
    if not output or not context:pytest.skip('Set delivery paths for full delivered-byte integration readback')
    from benchmarks.integrated_330_v01.spring_color_verify import verify
    report=verify(Path(output),Path(context))
    assert report['all_checks_passed'] and report['program_pairs_verified']==7
    assert report['complete_and_stage_source_orders_identical']
