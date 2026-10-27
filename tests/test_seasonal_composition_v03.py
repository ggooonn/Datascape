"""Terrain response, conserved panels and actual seasonal artifact checks."""
from pathlib import Path
import importlib.util,sys
from copy import deepcopy
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studies/seasonal_composition_v03'))
from shared import read,prior,accepted,ROOT as SCENE_ROOT
from recipes import config
from flow import release,valley_path
spec=importlib.util.spec_from_file_location('season_v03_verify',ROOT/'studies/seasonal_composition_v03/verify.py')
verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)

def synthetic(valley_x=230):
    y,x=np.mgrid[:900,:600];occ=np.ones((900,600),bool)
    q=900+(900-y)*6.;z=np.stack([x*8.,y*8.,500-y*.3],axis=2)
    global_r=np.ones((900,600));global_r[-2:]=0
    return dict(base=dict(occupied=occ,depth_m=q,xyz=z),retention=.35*global_r,
        features=dict(valley_small=np.exp(-((x-valley_x)/24)**2),valley_medium=np.zeros((900,600)),ridge=np.zeros((900,600))),
        refined=dict(global_retention=global_r))

def test_route_responds_to_measured_valley_under_the_same_gaze_prior():
    anchors=[[300,280],[300,795]]
    a=valley_path(synthetic(230),anchors)[0];b=valley_path(synthetic(370),anchors)[0]
    assert np.median(b[:,0]-a[:,0])>70

def test_release_is_local_and_never_overrides_global_reserves_or_source():
    f=synthetic();original=deepcopy(f);recipe=config('summer')['flow_candidates'][0]
    new,field,record=release(f,recipe)
    assert np.array_equal(f['base']['xyz'],original['base']['xyz'])
    assert np.array_equal(f['retention'],original['retention'])
    assert np.all(new['retention'][-2:]==0)
    assert np.array_equal(new['retention'][f['base']['depth_m']>3600],f['retention'][f['base']['depth_m']>3600])
    assert abs(np.median(field['points'][:,0])-230)<25

def test_depth_local_release_has_open_and_retained_territories_in_one_row():
    f=synthetic();new,fields,_=release(f,config('summer')['flow_candidates'][0])
    scope=fields['scope'][600]>.8
    values=new['retention'][600,scope]
    assert values.min()<.25 and values.max()>.65

@pytest.mark.parametrize('season',['summer','autumn','winter'])
def test_actual_scene_sources_panels_and_ledgers(season):
    name='summer_composition_v03' if season=='summer' else season+'_composition_v01'
    result=verify.check(ROOT/'docs/experiments'/name,check_parent=False)
    assert result['checks']['ink']['paths']>1000
    assert result['checks']['panels']['max_source_length_error_mm']<1e-6

def test_seasons_use_distinct_recorded_views_and_unequal_growth_controls():
    cc=[config(s) for s in ['summer','autumn','winter']]
    assert [c['selected_view'] for c in cc]==['C_east','A_south','B_northwest']
    assert cc[2]['summer_progression']['foliage_vigor'][1]<cc[1]['summer_progression']['foliage_vigor'][1]<cc[0]['summer_progression']['foliage_vigor'][1]
    assert len({m[2] for g in cc[0]['near_groups'] for m in g['members']})>8
    assert all(1<=v<=1.5 for c in cc for v in c['summer_progression']['foliage_unit_count_scale'])

def test_winter_actual_catalog_preserves_pine_foliage_and_broadleaf_structure():
    out=ROOT/'docs/experiments/winter_composition_v01'
    rows=read(out/'authoring_sources.json.gz')['strokes']
    trees=[r for r in rows if r.get('catalog_version')=='0.10']
    assert trees and {r.get('catalog_form') for r in trees}>={'P','B','U'}
    assert any(r.get('catalog_form')=='P' and r.get('grammar_part')=='foliage-field' for r in trees)
    assert any(r.get('catalog_form')=='B' and r.get('grammar_part')=='trunk-contour' for r in trees)

def test_corrupt_profile_is_rejected_even_if_geometry_is_valid():
    r=dict(id='source',xy_mm=[[20,30],[30,40]],width_mm=.3)
    out=dict(id='piece',xy_mm=r['xy_mm'],width_profile_mm=[.3],source_stroke_id='source',source_arc_mm=[0,2**.5*10])
    with pytest.raises(ValueError,match='profile'):verify.pinned.validate_rows([out],{'source':r})

def test_repeated_panel_crossings_conserve_profiles_without_seam_relocation():
    r=dict(id='cross',xy_mm=[[290,100],[310,110],[290,120],[310,130]],width_mm=.3,width_profile_mm=[.2,.4,.5,.3],expression=dict(intensity_samples=[.2,.4,.5,.3]))
    panels={n:prior.panel_rows([r],n) for n in [3,4]}
    assert sum(map(len,panels.values()))==4
    assert verify.pinned.check_panels([r],panels)['max_source_length_error_mm']<1e-6

def test_no_inherited_file_is_changed():
    assert verify.parent_invariants()['inherited_changes']==[]

def test_summer_far_parent_source_geometry_is_exactly_the_pinned_reference():
    old=read(ROOT/'docs/experiments/summer_foreground_v02/ink.json.gz')['strokes']
    terrain=[r for r in old if r['layer'] in ['A','B','C','D']]
    sources=read(ROOT/'docs/experiments/summer_composition_v03/authoring_sources.json.gz')['strokes']
    lookup={r['id']:r for r in sources}
    for i,parent in enumerate(terrain):
        key='summer-v03/far-reference/'+str(i)+'/'+parent['id'].replace('summer/','summer-v03/')
        r=lookup[key]
        assert r['xy_mm']==parent['xy_mm']
        assert r.get('width_profile_mm')==parent.get('width_profile_mm')

def test_eight_panel_review_keeps_native_panel_scale_and_unfitted_skyline():
    from PIL import Image
    out=ROOT/'docs/experiments/seasonal_composition_v03'
    with Image.open(out/'P1_P8_full.png') as im:assert im.size==(5360,1880)
    sky=read(out/'skyline.json');reference=read(ROOT/'docs/experiments/summer_scene_v01/viewpoint_review.json')
    expected=next(r['skyline_mm'] for r in reference['candidates'] if r['id']=='C_east')
    assert sky['terrain_silhouettes_mm']['summer']==expected
    assert all(len(r)==600 for r in sky['terrain_silhouettes_mm'].values())
    assert len(read(out/'density_whitespace.json')['panels'])==8

def test_short_seam_audit_does_not_relabel_inherited_spring_short_paths():
    work=read(ROOT/'docs/experiments/seasonal_composition_v03/workload.json')
    spring=work['spring']['panels']
    assert sum(r['inherited_short_sources'] for r in spring.values())>0
    assert sum(r['new_short_seam_fragments'] for r in spring.values())==0
    assert all(r['inherited_short_sources']==0 for s in ['summer','autumn','winter'] for r in work[s]['panels'].values())
