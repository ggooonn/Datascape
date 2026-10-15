"""Spacing responds to terrain while scene, omission and material stay separate."""
from copy import deepcopy
import numpy as np
import pytest
from scipy.ndimage import distance_transform_edt
from datascape.strokes.density_rhythm import integrated_phase,density_profile,a_proposals,assign_material,layer_digest,transfer
from datascape.rendering.density_rhythm_study import crossing_spacing,physical_pair
from datascape.strokes.vector import sample,resample


def synthetic():
    y,x=np.mgrid[:300,:120];q=40+y*20.
    peaks=np.exp(-((q-1500)/350)**2)+np.exp(-((q-4400)/400)**2)
    z=80+350*peaks+10*np.sin(x/25)
    occ=np.ones(q.shape,bool);zero=np.zeros_like(q)
    return {'base':{'occupied':occ,'depth_m':q,'xyz':np.stack([x*10,q,z],2),'slope_deg':5+20*peaks},
        '_grammar_xyz':np.stack([x*10,q,z],2),
        'features':{'macros':[np.full_like(z,80)],'ridge':peaks*.6,'mound':zero},
        'old':{'depth_roles':{'near':np.ones_like(q),'middle':zero,'far':zero}},'retention':np.ones_like(q)}


def config():
    return {'A':{'profile_bin_m':25,'profile_window_m':120,'smoothing_m':70,'macro_window_m':300,
        'widest_pitch_m':38,'tightest_pitch_m':9,'reference_pitch_m':20,'density_gain':1.45,
        'minimum_pitch_m':8,'maximum_pitch_m':48,'spline_knot_mm':3}}


def test_integral_produces_real_dense_open_dense_rows():
    q=np.arange(0,1001,1.);pitch=np.where((q<300)|(q>700),10.,30.)
    phase=integrated_phase(q,pitch);rows=np.interp(np.arange(1,phase[-1]),phase,q);gaps=np.diff(rows)
    assert np.all(np.diff(phase)>0)
    assert np.median(gaps[rows[:-1]<250])<11
    assert np.median(gaps[(rows[:-1]>350)&(rows[:-1]<650)])>29
    assert np.median(gaps[rows[:-1]>750])<11


@pytest.mark.parametrize('q,pitch', [([0,1],[1,0]),([1,0],[1,1])])
def test_invalid_phase_rejected(q,pitch):
    with pytest.raises(ValueError):integrated_phase(q,pitch)


def test_terrain_peaks_compress_spacing_without_editing_scene_or_mist():
    f=synthetic();before=deepcopy(f);p=density_profile(f,config());q=p['q_m'];pitch=p['pitch_m']
    high=(abs(q-1500)<100)|(abs(q-4400)<100);low=(q>2700)&(q<3200)
    assert np.mean(pitch[high])<np.mean(pitch[low])*.8
    assert np.all(np.diff(p['row_phase'])>0)
    assert np.array_equal(f['base']['xyz'],before['base']['xyz'])
    assert np.array_equal(f['retention'],before['retention'])
    assert np.array_equal(pitch,density_profile(f,config())['pitch_m'])


def test_a_curves_remain_source_transverse_after_spacing_change():
    f=synthetic();p=density_profile(f,config());paths=a_proposals(f,p,config())
    assert len(paths)>60
    for s in paths:
        q=sample(f['base']['depth_m'],s['xy_mm'])
        assert np.ptp(q)<.1
    depths=np.unique([round(np.mean(sample(f['base']['depth_m'],s['xy_mm'])),2) for s in paths])
    assert np.std(np.diff(depths))>1


def test_material_assignment_never_changes_centerlines_or_width():
    s=[{'layer':'C','xy_mm':[[1,2],[3,4]],'width_mm':.16,'opacity_profile':[.2,.3]}]
    a=assign_material(s,'light_ink');b=assign_material(s,'color_support');c=assign_material(s,'ink_and_color')
    for out in [a,b,c]:
        assert out[0]['xy_mm']==s[0]['xy_mm'] and out[0]['width_mm']==.16
        assert out[0]['opacity_profile']==s[0]['opacity_profile']
    assert 'material_intent' not in s[0]


def test_frozen_layer_digest_detects_profile_change_but_not_list_index():
    s=[{'layer':'D','draw_order':1,'xy_mm':[[1,2],[3,4]],'width_profile_mm':[.1,.8]}]
    t=deepcopy(s);t[0]['draw_order']=500;assert layer_digest(s,'D')==layer_digest(t,'D')
    t[0]['width_profile_mm'][1]=.7;assert layer_digest(s,'D')!=layer_digest(t,'D')


def test_dense_candidates_cannot_override_mist_cores_or_bottom_guard():
    r=np.ones((900,600));r[400:430,100:500]=0;r[898:]=0
    f={'retention':r,'_grammar_safe':distance_transform_edt(r>0),'old':{'depth_roles':{'near':r*0+1,'middle':r*0,'far':r*0}}}
    raw=[{'id':f'row-{i}','xy_mm':[[x,350],[x,899]],'width_mm':.32,'layer':'A','preview_opacity':.82,'expression':{'intensity':.6}} for i,x in enumerate(range(150,450,10))]
    mc={'seed':20261015,'mist':{'density_exponent':{'near':.95,'middle':1.15,'far':.85},'opacity_exponent':{'near':.7,'middle':.9,'far':.65},'length_cycle_mm':120,'minimum_window_mm':10,'minimum_path_mm':3.5,'minimum_width_fraction':.25,'width_exponent':.4}}
    out=transfer(raw,f,mc);assert out
    for s in out:
        p=resample(s['xy_mm'],.15)
        assert not np.any((p[:,1]>=400)&(p[:,1]<=430))
        assert p[:,1].max()+s['width_mm']/2<898


def test_spacing_reports_screen_mm_for_distinct_rows():
    y,x=np.mgrid[:900,:600];base={'depth_m':y*10.}
    ss=[{'layer':'A','xy_mm':[[1,v],[599,v]]} for v in range(100,900,4)]
    r=crossing_spacing(ss,base)
    for v in r.values():assert v['p10_p50_p90_mm']==pytest.approx([4,4,4])


def test_physical_gap_is_40mm_at_actual_scale(tmp_path):
    from PIL import Image
    p=tmp_path/'a.png';out=tmp_path/'b.png';Image.new('RGB',(600,900),'white').save(p);physical_pair(p,out)
    im=np.asarray(Image.open(out));assert im.shape==(900,640,3)
    assert np.all(im[:,300:340]==225)
