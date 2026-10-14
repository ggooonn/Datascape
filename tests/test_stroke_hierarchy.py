"""Sparse accents, nested density, fixed geometry and shared-width contracts."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from datascape.strokes.hierarchy import select_a,select_c,select_d,style,total_length,trace_lattice_edges,split_saddles
from datascape.rendering.hierarchy_study import compose,segments,write_svg


def config():
    return json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_stroke_hierarchy_v02.json').read_text())


def stroke(identity,xy,layer='C'):
    return {'id':identity,'xy_mm':xy,'layer':layer,'panel':1,'parent_path':0,'width_mm':.32,'opacity':1,'preview_opacity':.32,'draw_order':0,'expression':{'intensity':.25,'pressure_calibrated':False}}


def test_density_sets_are_nested_without_width_or_tone_changes():
    c=config();base={'depth_m':np.full((900,600),300.),'slope_deg':np.full((900,600),5.)}
    source=[stroke(str(i),[[20.,500+i],[60.,500+i]]) for i in range(100)]
    original=deepcopy(source);low=select_c(source,base,c,.32);high=select_c(source,base,c,.88)
    assert 0<len(low)<len(high)
    by_id={s['id']:s for s in high}
    assert all(by_id[s['id']]==s for s in low)
    assert source==original
    assert {s['width_mm'] for s in high}=={.16}
    assert {s['preview_opacity'] for s in high}=={.32}


def test_a_density_control_changes_paths_without_changing_style():
    c=config();ones=np.ones((900,600));zeros=np.zeros((900,600))
    fixed={'old':{'depth_roles':{'near':ones,'middle':zeros,'far':zeros}}}
    source=[stroke(str(i),[[20.,500+i],[60.,500+i]],'A') for i in range(20)]
    full=select_a(source,fixed,c);assert len(full)==len(source)
    c['A']['depth_density_multipliers']['near']=0
    assert select_a(source,fixed,c)==[]


def test_adding_skeleton_does_not_change_underlying_geometry():
    pool=[stroke('A',[[1,1],[10,10]],'A'),stroke('C',[[1,2],[10,12]],'C'),stroke('D',[[3,3],[7,7]],'D')]
    before=compose(pool,['C','A']);after=compose(pool,['C','A','D'])
    assert after[:-1]==before
    assert after[-1]['layer']=='D'


def test_black_and_density_profiles_use_identical_geometry():
    c=config();s=style([stroke('a',[[10,20],[30,40]])],'C',c)
    black=segments(s,'black',(0,0,600,900),(1200,1800));density=segments(s,'density',(0,0,600,900),(1200,1800))
    np.testing.assert_array_equal(black[0],density[0]);np.testing.assert_array_equal(black[1],density[1])
    assert black[2][0][-1]==1 and density[2][0][-1]==.32


def test_profile_svg_uses_stored_widths_and_panel_transform(tmp_path):
    s=stroke('D',[[300,20],[310,30],[320,40]],'D');s['panel']=2;s['width_profile_mm']=[.8,.4,0]
    p=tmp_path/'D.svg';write_svg([s],p,2);text=p.read_text()
    assert '0,20 10,30' in text and '10,30 20,40' in text
    assert 'stroke-width="0.6"' in text and 'stroke-width="0.2"' in text
    assert 'opacity' not in text


def test_edge_trace_splits_junctions_without_double_tracing():
    edges=[((i,3),(i+1,3)) for i in range(9)]+[((4,i),(4,i+1)) for i in range(3,8)]
    paths=trace_lattice_edges(edges)
    segments_seen=[]
    for p in paths:
        segments_seen.extend(tuple(sorted([tuple(a),tuple(b)])) for a,b in zip(p[:-1],p[1:]))
    assert len(segments_seen)==len(set(segments_seen))
    assert len(paths)==3


def test_d_nms_budget_and_release_are_actual_geometry(monkeypatch):
    import datascape.strokes.hierarchy as h
    c=config();c['D']['target_all_length_fraction']=.04;c['D']['type_maximum_fraction']={k:1 for k in c['D']['type_maximum_fraction']}
    yy,xx=np.mgrid[:900,:600];base={'xyz':np.stack([xx,yy,900-yy],axis=2).astype(float),'occupied':np.ones((900,600),bool),'depth_m':yy.astype(float)}
    fixed={'base':base,'retention':np.ones((900,600)),'features':{'ridge':np.ones((900,600)),'silhouette':np.zeros((900,600)),'relative_foot':np.zeros((900,600))}}
    candidates=[('crest',np.array([[x,300.],[x,319.]])) for x in [50.,51.,90.]]
    monkeypatch.setattr(h,'skeleton_candidates',lambda *args:candidates)
    d,record=select_d(fixed,{},0,c,[stroke('long',[[0.,0.],[1000.,0.]],'A')],[])
    assert len({s['parent_path'] for s in d})==2
    assert total_length(d)/(1000+total_length(d))<=.04
    assert all(s['width_profile_mm'][0]>s['width_profile_mm'][-1] for s in d)
    assert all(s['xy_mm'][0][1]<s['xy_mm'][-1][1] for s in d)
    assert record['selected_length_mm']<=record['length_budget_mm']
