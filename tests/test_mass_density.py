"""Local rhythm, phase topology and diagnostic isolation contracts."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from datascape.strokes.mass_density import mass_coordinates,phase_redistribution,rhythm_weights
from datascape.rendering.mass_density_study import readable


def config():
    return json.loads((Path(__file__).resolve().parents[1]/'configs/scenes/seoul_spring_a_density_v02.json').read_text())


def synthetic():
    y,x=np.mgrid[:100,:120];occ=((x>=8)&(x<52)|(x>=68)&(x<112))&(y>=8)&(y<92)
    q=2000+y*20.;z=900-y*7.+15*np.sin(x/12);xyz=np.stack([x*10.,y*10.,z],2);q=np.where(occ,q,0)
    fixed={'base':{'occupied':occ,'depth_m':q,'xyz':xyz},'_grammar_xyz':xyz,'retention':np.where(occ,.6,0),
        'features':{'valley_medium':np.zeros_like(q)}}
    labels=np.where(occ,np.where(x<60,1,2),0);t=np.clip((y-8)/83,0,1)
    masses=[{'label':1},{'label':2}]
    mass={'labels':labels,'t':t,'D_support':np.zeros_like(q),'masses':masses}
    return fixed,mass,{'phase_field':q/20}


def test_rhythm_contains_dense_open_dense_before_mist():
    rho=rhythm_weights(np.array([.08,.35,.65]),config())
    assert rho[0]/rho[1]>4 and rho[2]/rho[1]>4


def test_independent_altitude_offsets_do_not_change_form_coordinates():
    f,_,_=synthetic();c=config();a=mass_coordinates(f,[],c)
    shifted=deepcopy(f);shifted['_grammar_xyz'][:,:60,2]+=800;shifted['base']['xyz']=shifted['_grammar_xyz']
    b=mass_coordinates(shifted,[],c)
    assert np.array_equal(a['labels'],b['labels'])
    assert np.allclose(a['t'],b['t'],atol=1e-10)
    assert not a['D_support'].any()


def test_same_local_slope_rhythm_at_different_source_depths():
    f,m,p=synthetic();c=config();a=phase_redistribution(f,m,p,c)
    g=deepcopy(f);g['base']['depth_m']=np.where(g['base']['occupied'],g['base']['depth_m']+2500,0)
    b=phase_redistribution(g,m,{'phase_field':g['base']['depth_m']/20},c)
    assert np.allclose(a['correction'],b['correction'],atol=1e-9)


def test_positive_phase_and_zero_boundary_displacement():
    f,m,p=synthetic();r=phase_redistribution(f,m,p,config())
    assert r['phase_derivative_nonpositive_pixels']==0
    assert np.min(r['directional_phase_ratio'])>=.2499
    assert np.all(r['correction'][m['labels']==0]==0)
    assert np.allclose(r['correction'][8],0) and np.allclose(r['correction'][91],0)


def test_uniform_policy_cannot_densify_the_scene():
    f,m,p=synthetic();c=config();c['rhythm']['relative_density']=[1]*8;c['rhythm']['D_support_gain']=0
    r=phase_redistribution(f,m,p,c)
    assert np.allclose(r['phase'],p['phase_field'],atol=1e-9)


def test_fields_and_retention_are_read_only():
    f,m,p=synthetic();before=deepcopy(f);phase_redistribution(f,m,p,config())
    assert np.array_equal(f['retention'],before['retention'])
    assert np.array_equal(f['_grammar_xyz'],before['_grammar_xyz'])
    assert np.array_equal(f['base']['depth_m'],before['base']['depth_m'])


def test_dense_open_dense_measured_in_a_uniform_slope():
    f,m,p=synthetic();r=phase_redistribution(f,m,p,config());t=m['t'];core=(m['labels']==1)&(np.indices(t.shape)[1]>24)&(np.indices(t.shape)[1]<36)
    med=[np.median(r['directional_phase_ratio'][core&(t>=lo)&(t<hi)]) for lo,hi in [(0,.18),(.25,.45),(.55,.75)]]
    assert med[0]>med[1]*1.4 and med[2]>med[1]*1.4


def test_diagnostic_styling_cannot_mutate_C_geometry(tmp_path):
    s=[{'layer':'C','xy_mm':[[20,20],[100,100]],'width_mm':.16,'opacity_profile':[.1,.2]}];before=deepcopy(s)
    readable(s,tmp_path/'C.png','C',pixels=(120,180))
    assert s==before


def test_v3_topology_floor_relaxes_only_the_phase_guard_and_stays_positive():
    from datascape.strokes.spacing_schedule import phase_ablation
    fixed, mass, profile = synthetic()
    original = deepcopy(fixed)
    base = phase_ablation(fixed, mass, profile, config(), minimum_derivative_ratio=.25)
    relaxed = phase_ablation(fixed, mass, profile, config(), minimum_derivative_ratio=.05)
    assert base['phase_derivative_nonpositive_pixels'] == 0
    assert relaxed['phase_derivative_nonpositive_pixels'] == 0
    assert np.min(relaxed['directional_phase_ratio'][relaxed['safe']]) >= .05
    assert np.array_equal(fixed['retention'], original['retention'])
    assert np.array_equal(fixed['base']['depth_m'], original['base']['depth_m'])


def test_explicit_source_schedule_keeps_positive_phase_and_reports_raw_folds():
    from datascape.strokes.spacing_schedule import explicit_source_spacing_phase
    fixed, mass, profile = synthetic()
    result = explicit_source_spacing_phase(fixed, mass, profile, config(),
                                           minimum_derivative_ratio=.05)
    assert result['phase_derivative_nonpositive_pixels'] == 0
    assert result['unlimited_phase_derivative_nonpositive_pixels'] >= 0
    assert np.all(np.isfinite(result['phase']))
