"""Shared geometry, visible edges, profile continuity and intrinsic B contracts."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import distance_transform_edt
from datascape.strokes.color_ready import profile_vertices,make_profiled,visible_supports,internal_b
from datascape.rendering.color_ready_study import styled_segments,write_svg
from datascape.vegetation.object_prototypes import tree_centerlines,rock_centerlines


def config():
    return json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_color_ready_v02.json').read_text())


def stroke(layer):
    return {'id':layer,'xy_mm':[[20.,300.],[40.,310.],[70.,320.]],'layer':layer,'panel':1,'parent_path':0,'width_mm':.32,'preview_opacity':1,'expression':{'intensity':.6,'pressure_calibrated':False}}


def fixture():
    y,x=np.mgrid[:900,:600];occ=(y>=200)&(y<650);one=np.ones((900,600));zero=one*0
    xyz=np.stack([x*5,y*5,one*10],axis=2).astype(float)
    f={'retention':one.copy(),'_grammar_safe':distance_transform_edt(occ),'_grammar_xyz':xyz,
       'base':{'occupied':occ,'xyz':xyz,'depth_m':np.where(x<300,1000.,2000.),'slope_deg':one*10},
       'features':{'ridge':zero,'silhouette':zero,'relative_foot':zero,'valley_small':zero,'valley_medium':zero}}
    d={k:zero.copy() for k in ['gx','gy','hxx','hxy','hyy']};return f,d


class LinearProjection:
    class Camera:azimuth_deg=0
    camera=Camera()
    def project(self,xyz,w,h):return np.asarray(xyz)[:,:2],np.asarray(xyz)[:,1]
    def volume_determinant(self,xyz,w,h):return np.ones(len(xyz))


def test_alpha_hierarchy_does_not_change_paths_or_width_profiles():
    c=config();ss=[stroke(k) for k in ['D','B','A','C']];original=deepcopy(ss)
    black=styled_segments(ss,'black',c);tone=styled_segments(ss,'composite',c)
    for a,b in zip(black[0],tone[0]):np.testing.assert_array_equal(a,b)
    np.testing.assert_array_equal(black[1],tone[1]);assert [x[-1] for x in tone[2]]==[.98,.82,.63,.22]
    assert ss==original and all(x[-1]==1 for x in black[2])


def test_straight_d_keeps_middle_envelope_after_geometry_simplification():
    f,_=fixture();paths=[np.array([[100.,300.],[200.,300.]])];items=[{'kind':'skyline','events':[0]}]
    s=make_profiled(paths,items,'test',.82,f,True)[0]
    assert len(s['xy_mm'])>50
    w=s['width_profile_mm'];assert max(w)>.81 and w[0]<.1 and w[-1]<.03
    np.testing.assert_allclose(s['xy_mm'][0],paths[0][0]);np.testing.assert_allclose(s['xy_mm'][-1],paths[0][-1])


def test_d_parent_envelope_does_not_restart_at_panel_seam():
    f,_=fixture();p=np.array([[250.,300.],[350.,300.]])
    ss=make_profiled([p],[{'kind':'occlusion','events':[0]}],'seam',.82,f,True)
    assert len(ss)==2 and ss[0]['panel']==1 and ss[1]['panel']==2
    assert ss[0]['width_profile_mm'][-1]>.8 and ss[1]['width_profile_mm'][0]>.8
    assert abs(ss[0]['width_profile_mm'][-1]-ss[1]['width_profile_mm'][0])<.01


def test_depth_step_without_source_surface_separation_is_not_d_edge():
    f,d=fixture();c=config();raw,fields,record=visible_supports(f,d,LinearProjection(),c)
    assert record['adjacent_depth_source_edges']==0
    assert not any(kind=='occlusion' for kind,p in raw)


def test_visible_occlusion_is_inset_on_nearer_surface_only():
    f,d=fixture();f['_grammar_xyz'][:,300:,0]+=1000
    raw,fields,record=visible_supports(f,d,LinearProjection(),config());oc=[p for k,p in raw if k=='occlusion']
    assert record['adjacent_depth_source_edges']>0 and oc
    assert all(np.median(p[:,0])<300 for p in oc)


def test_mist_boundary_alone_cannot_generate_b():
    f,d=fixture();y,x=np.mgrid[:900,:600];f['retention']=1/(1+np.exp((y-500)/8))
    ctx={'gx':x*0.,'gy':x*0.+1,'transition_distance':abs(y-500),'A_support':x*0.+1}
    b,record=internal_b([],f,d,[stroke('A')],config(),ctx)
    assert b==[] and record['intrinsic_candidates']==0 and record['mask_derived_candidates']==0


def test_b_retreat_is_adjustable_and_filters_parallel_transition():
    f,d=fixture();y,x=np.mgrid[:900,:600];d['hxx'][:]=.002
    ctx={'gx':x*0.,'gy':x*0.+1,'transition_distance':abs(y-500),'A_support':x*0.+1}
    raw=[np.array([[40.,500.],[100.,500.]])];c=config();c['B']['maximum_A_length_fraction']=1
    body=[{**stroke('A'),'xy_mm':[[1.,300.],[590.,300.]]}]
    b,_=internal_b(raw,f,d,body,c,ctx);assert b==[]
    c['B']['inward_retreat_mm']=0;b,_=internal_b(raw,f,d,body,c,ctx);assert b


def test_tree_prototype_is_seeded_rooted_and_height_bounded():
    mark={'id':'hero','root_pixel_xy':[400.,800.],'height_mm':180.,'ndvi':.6};c=config()['objects']
    a=tree_centerlines(mark,21,c);b=tree_centerlines(mark,21,c)
    assert len(a)==len(b)
    for x,y in zip(a,b):np.testing.assert_array_equal(x[0],y[0])
    np.testing.assert_array_equal(a[0][0][0],mark['root_pixel_xy'])
    assert abs(min(p[:,1].min() for p,_,_ in a)-(800-180))<1e-8
    assert all(not np.array_equal(p[0],p[-1]) for p,_,_ in a)


def test_rock_prototype_uses_open_upper_facets_not_filled_outline():
    anchor={'xy_mm':[200.,780.],'width_mm':24.,'height_mm':12.,'orientation_xy':[.8,.2]}
    result=rock_centerlines(anchor,3,config()['objects'])
    assert result[0][2]=='upper-facet' and {r[2] for r in result}=={'upper-facet','facet-break','texture'}
    assert all(not np.array_equal(p[0],p[-1]) for p,_,_ in result)


def test_svg_reuses_same_coordinates_for_black_and_composite(tmp_path):
    c=config();s=stroke('D');s['width_profile_mm']=[.1,.8,.1];s['opacity_profile']=[.1,1,.1]
    a=tmp_path/'a.svg';b=tmp_path/'b.svg';write_svg([s],a,c,'black');write_svg([s],b,c,'composite')
    import xml.etree.ElementTree as ET
    ns={'s':'http://www.w3.org/2000/svg'};aa=ET.parse(a).findall('.//s:polyline',ns);bb=ET.parse(b).findall('.//s:polyline',ns)
    assert [(x.attrib['points'],x.attrib['stroke-width']) for x in aa]==[(x.attrib['points'],x.attrib['stroke-width']) for x in bb]
    assert all(x.attrib['stroke-opacity']=='1' for x in aa) and any(x.attrib['stroke-opacity']!='1' for x in bb)


def test_each_b_path_owns_its_own_intensity_profile():
    f,d=fixture();y,x=np.mgrid[:900,:600];d['hxx'][:]=.002
    ctx={'gx':x*0.,'gy':x*0.+1,'transition_distance':abs(y-500),'A_support':x*0.+1};c=config();c['B']['maximum_A_length_fraction']=1
    raw=[np.array([[40.,350.],[135.,350.]]),np.array([[50.,400.],[110.,420.]])]
    body=[{**stroke('A'),'xy_mm':[[1.,300.],[590.,300.]]}];ss,_=internal_b(raw,f,d,body,c,ctx)
    assert len(ss)>1
    for s in ss:assert len(s['expression']['intensity_samples'])==len(s['xy_mm'])
    assert len({id(s['expression']) for s in ss})==len(ss)


def test_new_a_parent_is_attenuated_before_panel_split(monkeypatch,tmp_path):
    import datascape.strokes.color_ready as module
    import datascape.strokes.vector as vector
    f,_=fixture();one=np.ones((900,600));f['old']={'depth_roles':{'near':one,'middle':one*0,'far':one*0}}
    raw=np.array([[250.,300.],[350.,300.]])
    monkeypatch.setattr(module,'taebaek_rows',lambda *args:[raw])
    monkeypatch.setattr(vector,'read_vectors',lambda *args:{'strokes':[]})
    monkeypatch.setattr(module,'select_c',lambda *args:[])
    original=module.transfer_mist;seen=[]
    def inspect(candidates,*args):
        seen.extend(candidates);return original(candidates,*args)
    monkeypatch.setattr(module,'transfer_mist',inspect)
    c=config()
    for p in c['density']['presets'].values():p['A_interleaved_keep']={'near':1.,'middle':1.,'far':1.}
    parent=json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_stroke_grammar_v03.json').read_text())
    (tmp_path/'vector.json').write_text(json.dumps({'taebaek':{'first_depth_m':40,'depth_pitch_m':20}}));parent['vector_config']='vector.json'
    presets,_=module.density_presets([],f,tmp_path,c,parent,{'source_vectors':{'C':'unused'}})
    assert len(seen)==1 and seen[0]['xy_mm']==raw.tolist()
    a=presets['color_ready']['A'];assert len(a)==2 and {s['panel'] for s in a}=={1,2}
    assert len({s['source_stroke_id'] for s in a})==1
    assert a[0]['xy_mm'][-1]==a[1]['xy_mm'][0]==[300.,300.]
