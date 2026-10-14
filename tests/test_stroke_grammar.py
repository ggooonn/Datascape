"""Stroke continuity, hard omission, attenuation and fixed-root contracts."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import distance_transform_edt
from datascape.strokes.grammar import strength_envelope,compatible_bridge,connect_candidates,transfer_mist
from datascape.strokes.hierarchy import total_length
from datascape.vegetation.grammar import tree_paths,cluster_paths,far_paths
from datascape.rendering.grammar_study import svg


def config():
    return json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_stroke_grammar_v03.json').read_text())


def fixed(r=1.):
    y,x=np.mgrid[:900,:600];ones=np.ones((900,600));retention=ones*r
    return {'retention':retention,'_grammar_safe':distance_transform_edt(retention>0),
            '_grammar_xyz':np.stack([x,y,900-y],axis=2),'base':{'depth_m':y.astype(float)},
            'old':{'depth_roles':{'near':ones,'middle':ones*0,'far':ones*0}}}


def candidates():
    return [{'id':str(i),'xy_mm':[[20.,300.+i],[250.,300.+i]],'width_mm':.32,'layer':'A',
             'preview_opacity':.82,'expression':{'intensity':.6}} for i in range(100)]


def test_envelope_has_soft_entry_sustained_center_soft_exit():
    e=strength_envelope(np.linspace(0,1,101))
    assert e[0]<.1 and e[-1]<.05 and min(e[30:60])>.99
    assert np.all(np.diff(e[:27])>=0) and np.all(np.diff(e[63:])<=0)


def test_connection_rejects_omission_core_and_incompatible_tangent():
    c={**config()['D'],'width_mm':.82};f=fixed();a=np.array([[20.,300.],[40.,300.]])
    b=np.array([[45.,300.],[65.,300.]])
    assert compatible_bridge(a,b,f,c)
    f['retention'][:,41:45]=0
    assert not compatible_bridge(a,b,f,c)
    assert not compatible_bridge(a,np.array([[45.,300.],[45.,330.]]),fixed(),c)


def test_endpoint_graph_preserves_kind_and_connects_one_axis():
    c={**config()['D'],'width_mm':.82}
    raw=[('crest',np.array([[20.,300.],[40.,300.]])),('crest',np.array([[45.,300.],[65.,300.]])),('cliff',np.array([[70.,300.],[90.,300.]]))]
    chains,joins=connect_candidates(raw,fixed(),c)
    assert joins==1 and len(chains)==2
    assert sorted(len(x['events']) for x in chains)==[1,2]


def test_mist_changes_actual_lengths_and_profiles_without_double_fade():
    c=config();source=candidates();f=fixed(.25)
    a=transfer_mist(source,f,'binary',c);b=transfer_mist(source,f,'density',c);d=transfer_mist(source,f,'combined',c)
    assert 0<total_length(d)<total_length(b)<total_length(a)
    assert all('opacity_profile' not in s for s in b)
    assert all(max(s['opacity_profile'])<.82 and max(s['width_profile_mm'])<.32 for s in d)
    assert all(s['expression']['pressure_calibrated'] is False for s in d)
    assert transfer_mist(source,fixed(0),'combined',c)==[]


def test_full_retention_preserves_all_modes_geometry():
    c=config();source=candidates()[:1];f=fixed()
    outputs=[transfer_mist(source,f,m,c) for m in ['binary','density','combined']]
    assert [s['xy_mm'] for s in outputs[0]]==[s['xy_mm'] for s in outputs[1]]==[s['xy_mm'] for s in outputs[2]]


def test_depth_grammars_are_distinct_and_trunk_starts_at_archived_root():
    c=config()['vegetation'];mark={'root_pixel_xy':[200.,750.],'height_mm':40.,'ndvi':.6}
    near=tree_paths(mark,np.random.default_rng(3),c);middle=cluster_paths(mark,np.random.default_rng(3),c)
    far=far_paths(mark,np.random.default_rng(3),c,.7)
    np.testing.assert_array_equal(near[0][0][0],mark['root_pixel_xy'])
    assert set(p[2] for p in near)=={'trunk','branch','twig','foliage'}
    assert {p[2] for p in middle}=={'cluster-grain'} and {p[2] for p in far}=={'ridge-touch'}
    assert far_paths(mark,np.random.default_rng(3),c,0)==[]
    assert all(not np.array_equal(p[0][0],p[0][-1]) for p in near)


def test_svg_profiles_and_physical_panel_transform_share_vertices(tmp_path):
    s={'id':'d','layer':'D','panel':2,'xy_mm':[[300.,20.],[310.,30.],[320.,40.]],'width_mm':.8,
       'width_profile_mm':[.1,.8,.05],'opacity_profile':[.2,1.,.1]}
    path=tmp_path/'test.svg';svg([s],path,panel=2);text=path.read_text()
    assert '0,20 10,30' in text and '10,30 20,40' in text
    assert 'stroke-width="0.45"' in text and 'stroke-opacity="0.6"' in text
