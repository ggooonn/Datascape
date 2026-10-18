"""Behavioral invariants for catalog-only placement and vector color supports."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import GeometryCollection,box
from datascape.integration.vector_wash import depth_parameters,palette_weights,choose_slot
from datascape.integration.cluster_scene import catalog_seed,pose_tree,initialize,SHAPE,resolve_clusters
from datascape.rendering.spring_cluster_study import export_svg

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'configs/scenes/seoul_spring_clusters_v02.json').read_text())


def test_continuous_depth_modulation_has_expected_direction_and_no_steps():
    q=np.linspace(250,2550,101);d=depth_parameters(q,CONFIG)
    for name in ['density','width','alpha']:
        assert np.all(np.diff(d[name])<0)
    assert d['density'][0]==1 and np.isclose(d['density'][-1],.36)
    assert d['width'][0]==1.7 and d['width'][-1]==.85


def test_object_palette_and_depth_modulation_are_combined():
    near=palette_weights('rock',300,CONFIG);far=palette_weights('rock',2500,CONFIG)
    assert far['A3']>near['A3']
    assert far['A4']<near['A4']
    green=palette_weights('vegetation',300,CONFIG)
    assert green['C1']+green['C2']>.6
    for kind in ['rock','Soil','terrain','vegetation']:
        p=palette_weights(kind,1700,CONFIG)
        assert np.isclose(sum(p.values()),1)
        assert set(p)<=set(CONFIG['spring_active_target_percent'])
    assert sum(CONFIG['spring_active_target_percent'].values())==100
    assert len(CONFIG['spring_active_target_percent'])==12


def test_correlated_color_assignment_does_not_depend_on_iteration_order():
    keys=['cluster-a/band-1','cluster-a/band-2','cluster-b/band-1']
    forward={k:choose_slot('vegetation',900,k,CONFIG) for k in keys}
    reverse={k:choose_slot('vegetation',900,k,CONFIG) for k in reversed(keys)}
    assert forward==reverse


def test_rigid_scene_pose_preserves_native_lengths_and_root_contact():
    from datascape.vegetation.tree_final_scale import make_tree
    from shapely.geometry import LineString
    seed=catalog_seed(20261018,'pose-proof')
    tree=make_tree('P',root=(100,700),height=95,seed=seed,identity='pose-proof')
    lengths=[LineString(m.xy).length for m in tree.marks]
    left,_,lean=pose_tree(tree,-1);right,_,other=pose_tree(tree,1)
    assert lean<0 and other>0
    assert np.array_equal(left.root,tree.root)
    assert np.allclose(lengths,[LineString(m.xy).length for m in left.marks])
    assert np.allclose(lengths,[LineString(m.xy).length for m in right.marks])
    assert catalog_seed(20261018,'pose-proof')==seed


def test_soil_uses_actual_surface_depth_instead_of_an_upright_root_sheet():
    yy,xx=np.mgrid[:900,:600];q=3000-yy*3.2+xx*.01
    fixed=dict(base=dict(depth_m=q,occupied=np.ones(SHAPE,bool)),retention=np.full(SHAPE,.7),
               refined=dict(global_retention=np.ones(SHAPE)))
    r=dict(id='soil-a',xy_mm=[[20,700],[50,704]],width_mm=.6)
    obj=dict(id='Soil',kind='soil',site={},support=box(20,700,50,710),records=[r])
    initialize(obj,fixed,GeometryCollection(),ground=True)
    assert obj['q'] is q
    assert obj['depth_provider']=='actual-visible-F2-ground-surface'
    assert obj['q'][710,30]!=obj['q'][700,30]


def test_every_legacy_V_path_is_removed_while_A_source_is_preserved(monkeypatch):
    import datascape.integration.cluster_scene as module
    monkeypatch.setattr(module,'create_objects',lambda *args:([],[],[]))
    fixed=dict(base=dict(depth_m=np.ones(SHAPE)*900))
    sources=[dict(id='old-V',layer='V',xy_mm=[[10,10],[20,10]],width_mm=.6),
             dict(id='fixed-A',layer='A',xy_mm=[[10,15],[20,15]],width_mm=.32)]
    out=resolve_clusters(fixed,sources,CONFIG,'clean',GeometryCollection())
    assert out['legacy_V_paths_removed']==1
    assert len(out['ink'])==1 and out['ink'][0]['source_family']=='A'
    assert out['ink'][0]['xy_mm']==sources[1]['xy_mm']
    assert sources[0]['id']=='old-V'
    removed=next(r for r in out['terrain_ledger'] if r['source_id']=='old-V')
    assert removed['kept_intervals_mm']==[] and removed['removed_mm']==10


def test_vector_export_has_only_open_strokes_and_no_filled_paint(tmp_path):
    r=dict(xy_mm=[[10,10],[14,13],[18,14]],width_mm=1.2,opacity_profile=[.2,.2,.2],palette_slot='C1')
    p=tmp_path/'proof.svg';export_svg(p,[],[r],{'slots':{'C1':{'preview_hex':'#E1ECB8'}}})
    tree=ET.parse(p)
    tags=[e.tag.rsplit('}',1)[-1] for e in tree.iter()]
    assert not any(t in tags for t in ['polygon','rect','ellipse','image'])
    assert tags.count('path')==1
    assert all(e.attrib.get('fill','none')=='none' for e in tree.iter())
