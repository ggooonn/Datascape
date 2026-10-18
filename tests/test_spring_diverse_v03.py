"""Integration invariants for independent color carriers and reciprocal overlap."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from shapely.geometry import LineString
from datascape.integration.diverse_color import displaced_a,retain_carrier,coverage_metrics,DirectionField
from datascape.integration.diverse_scene import behind_v03,representation_records

CONFIG=json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_diverse_v03.json').read_text())


def test_A_carrier_is_separate_deterministic_and_original_is_unchanged():
    x=np.linspace(30,190,100);p=np.c_[x,400+7*np.sin(x/60)];before=p.copy()
    a,controls=displaced_a(p,'same-source',CONFIG)
    b,_=displaced_a(p,'same-source',CONFIG)
    assert np.array_equal(p,before) and np.array_equal(a,b)
    assert LineString(a).hausdorff_distance(LineString(p))>.1
    assert controls['max_displacement_mm']<3
    control,_=displaced_a(p,'same-source',CONFIG,coincident=True)
    assert LineString(control).hausdorff_distance(LineString(p))<1e-6


def test_local_contact_can_put_either_tree_or_rock_in_front():
    tree=dict(id='tree',kind='tree',group='shared',overlap_rank=7,local_rank=0)
    rock=dict(id='rock',kind='rock',group='shared',overlap_rank=1,local_rank=0)
    q=np.array([600.,600.,600.])
    assert behind_v03(tree,rock,q,q).all()
    assert not behind_v03(rock,tree,q,q).any()
    tree['overlap_rank']=0
    assert not behind_v03(tree,rock,q,q).any()
    assert behind_v03(rock,tree,q,q).all()
    # Authored rank never reverses a metrically clear depth relationship.
    assert behind_v03(tree,rock,q+70,q).all()


def test_color_clipping_interpolates_depth_and_preserves_arc_lineage():
    r=dict(id='source',source_stroke_id='source',source_arc_mm=[0.,20.],xy_mm=[[10,30],[20,30],[30,30]],width_mm=.8,
           width_profile_mm=[.5,1,.5],opacity_profile=[.2,.3,.2],source_forward_profile_m=[500,1500,2500])
    sources=[];ledger=[];parts=[]
    retain_carrier(r,lambda xy,arc,r:(np.minimum(arc-3,17-arc),['test-bounds']),sources,ledger,parts)
    assert len(parts)==1
    p=parts[0];assert np.allclose(p['source_arc_mm'],[3,17])
    assert np.allclose(p['source_forward_profile_m'],[800,1500,2200])
    assert np.isclose(p['source_forward_mean_m'],1500)
    assert r['source_forward_profile_m']==[500,1500,2500]


def test_coverage_splits_a_single_path_across_actual_q_bands():
    r=dict(xy_mm=[[2,2],[32,2]],source_forward_profile_m=[500,3500],palette_slot='C1',color_channel='A-derived')
    fixed=dict(base=dict(depth_m=np.array([[500,1500,3000.]])))
    context=dict(eligible=np.ones((1,3),bool),common_eligible=np.ones((1,3),bool))
    m=coverage_metrics([r],fixed,context)
    assert np.isclose(m['depth']['near']['length_mm'],4.8,atol=.6)
    assert np.isclose(m['depth']['middle']['length_mm'],12,atol=.6)
    assert np.isclose(sum(b['length_mm'] for b in m['depth'].values()),30)


def test_direction_field_keeps_real_sources_and_changes_with_tangents():
    a=[dict(id='C-reference',source_family='C',xy_mm=[[0,0],[60,30]]),
       dict(id='B-reference',source_family='B',xy_mm=[[0,10],[60,50]])]
    t,c,b=DirectionField(a).at([[25,20]])
    assert t[0,0]>0 and t[0,1]>.4
    assert np.isclose(np.linalg.norm(t),1)
    assert c[0]=='C-reference' and b[0]=='B-reference'


def test_far_representation_is_an_exact_subset_without_scaled_glyphs():
    records=[dict(id='trunk',grammar_part='trunk-contour',component_key='axis/0',xy_mm=[[1,2],[3,4]]),
             dict(id='leaf',grammar_part='foliage-field',component_key='crown-0/fan/0',xy_mm=[[4,5],[6,7]])]
    before=deepcopy(records);out=representation_records(None,records,'aggregate')
    assert out==[records[1]] and records==before


def test_authored_roles_may_omit_complete_object_categories():
    groups=CONFIG['groups']
    assert any(g['trees'] and not g['rocks'] for g in groups)
    assert any(g['rocks'] and not g['trees'] for g in groups)
    assert any(g['trees'] and not g['rocks'] and not g['soils'] for g in groups)
    assert len({len(g['trees']) for g in groups})>=6
    assert sum(CONFIG['spring_active_target_percent'].values())==100


def test_display_modes_do_not_change_vector_quantity_geometry_or_slots():
    from datascape.rendering.spring_diverse_study import display_records
    records=[dict(id='one',xy_mm=[[1,2],[4,6]],palette_slot='C2',width_profile_mm=[1,1],opacity_profile=[.2,.3])]
    before=deepcopy(records);diagnostic=display_records(records,CONFIG,'diagnostic')
    assert records==before and len(diagnostic)==len(records)
    for name in ['xy_mm','palette_slot','width_profile_mm']:assert diagnostic[0][name]==records[0][name]
    assert diagnostic[0]['opacity_profile'][0]>records[0]['opacity_profile'][0]
