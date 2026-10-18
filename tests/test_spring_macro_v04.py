"""Behavioral checks for v04 source-space selection and explicit wash vectors."""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
import json
import numpy as np
from shapely.geometry import box,LineString
from datascape.integration.macro_wash import source_basis,geometric_feather,expressive_profile,paired_supports,gate_v04,retain
from datascape.rendering.spring_macro_study import width_envelope
C=json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_macro_v04.json').read_text())


def record(key='test'):
    return dict(id=key,source_stroke_id=key,source_arc_mm=[0,60],xy_mm=[[20,20],[20,50],[20,80]],width_mm=.8,width_profile_mm=[.4,.8,.4],opacity_profile=[.2,.2,.2],source_forward_profile_m=[500,600,700],carrier_basis='same-local-flow')


def test_D_source_basis_uses_forward_distance_and_elevation_with_integer_camera():
    fixed=dict(scene=dict(primary_eye_xy_m=[100,200],look_target_xy_m=[100,300]))
    p=source_basis(fixed,[[100,230,20],[100,250,20],[100,230,70]])
    assert np.allclose(p[1]-p[0],[0,20,0]) and np.allclose(p[2]-p[0],[0,0,50])


def test_feather_changes_actual_lengths_and_selection_without_alpha_changes():
    weak=dict(retention=np.full((900,600),.12));strong=dict(retention=np.ones((900,600)));sums=[0,0]
    for i in range(40):
        r=record(str(i));original=deepcopy(r)
        for j,f in enumerate([weak,strong]):
            out,decision=geometric_feather(r,f,C)
            assert np.isclose(sum(b-a for a,b in decision['kept_intervals_mm'])+decision['removed_mm'],60)
            if out:sums[j]+=LineString(out['xy_mm']).length;assert np.allclose(out['opacity_profile'],.2)
        assert r==original
    assert sums[0]<sums[1]*.65
    assert geometric_feather(record('stable'),weak,C)==geometric_feather(record('stable'),weak,C)


def test_width_intent_widens_and_releases_without_claiming_pressure():
    r=expressive_profile(record(),2.4,.4);w=r['width_profile_mm']
    assert w[1]>w[0]*2 and w[1]>w[-1]*2
    assert not r['brush_pressure_calibrated']
    assert len(r['pressure_intent_samples'])==len(r['xy_mm'])
    envelope=width_envelope(r);assert envelope.area>30 and envelope.is_valid


def test_trunk_support_comes_from_actual_posed_paired_ink_sides():
    obj=dict(tree=SimpleNamespace(structure=dict(members={'axis/0':[[20,10],[20,50]]})),records=[dict(grammar_part='trunk-contour',component_key='axis/side-1/0',xy_mm=[[19,10],[19.5,50]]),dict(grammar_part='trunk-contour',component_key='axis/side1/0',xy_mm=[[22,10],[21,50]])])
    supports=paired_supports(obj);poly,_=supports['axis']
    assert np.isclose(poly.area,90) and poly.bounds==(19.,10.,22.,50.)


def test_longitudinal_path_footprint_is_clipped_inside_actual_boundaries(monkeypatch):
    import datascape.integration.macro_wash as module
    monkeypatch.setattr(module,'object_gate_v03',lambda *args:lambda xy,arc,r:(np.ones(len(xy)),[]))
    r=record();r.update(xy_mm=[[20,10],[20,25],[23,35]],width_profile_mm=[1,1,1],assumed_footprint_mm=1.)
    ctx={k:np.full((900,600),1e6) for k in ['global_clearance','corridor_clearance']}
    gate=gate_v04({},ctx,[],C,obj={"id":"trunk"},region=box(19,0,21,50),exact_region=True)
    parts=[];retain(r,gate,[],[],parts)
    assert parts and max(np.asarray(parts[0]['xy_mm'])[:,0])<=20.40001
    assert box(19,0,21,50).covers(LineString(parts[0]['xy_mm']).buffer(.5))


def test_macro_revision_keeps_count_and_validated_scale_boundaries_separate():
    assert sum(len(g['trees']) for g in C['groups'])==79
    assert len(C['macro_fields'])==3 and all(g['open_edges'] for g in C['macro_fields'])
    assert max(t['height_mm'] for g in C['groups'] for t in g['trees'])==130
    assert C['scale_policy']['dominant_rock_current_mm']==[240,82]
    assert not C['scale_policy']['finished_vectors_scaled']
