"""Behavior contracts for the geometry-preserving seasonal display study."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'studies/seasonal_color_tone_v01'))
from model import read,CONFIG,rgb,to_lab,from_lab,palette_at,scalar_at,subpath,depth_role,material
from generate import panel_length

def test_oklab_known_primary_and_roundtrip():
    assert np.allclose(to_lab(rgb('#FF0000')),[.62795536,.22486306,.12584630],atol=1e-7)
    values=np.array([rgb(s) for s in ['#000000','#FFFFFF','#427F70','#CC7C3E']])
    assert np.allclose(from_lab(to_lab(values)),values,atol=2e-6)

@pytest.mark.parametrize('role',['base','structural','mineral','accent'])
def test_all_panel_anchors_and_seams(role):
    c=read(CONFIG)
    for i,p in enumerate(c['panels']):assert np.allclose(palette_at(c,i*300+150,role),rgb(p[role]),atol=2e-6)
    for j in range(1,8):assert np.max(abs(palette_at(c,j*300-1e-7,role)-palette_at(c,j*300+1e-7,role)))<1e-6
    assert np.allclose(palette_at(c,-20,role),rgb(c['panels'][0][role]),atol=2e-6)
    assert np.allclose(palette_at(c,2600,role),rgb(c['panels'][-1][role]),atol=2e-6)

def test_tone_targets_are_not_physical_dose():
    c=read(CONFIG)
    assert np.allclose(scalar_at(c,np.linspace(0,2400,99),'ink_mix_target').sum(axis=1),1)
    assert c['D4_policy']['primary_physical_assignment'] is None
    assert c['D4_policy']['strong_use_excluded_seasons']==['spring','summer']

def test_exact_subarc_bends_and_interpolates():
    p=subpath([[0,0],[10,0],[10,10]],5,17)
    assert np.allclose(p,[[5,0],[10,0],[10,7]])

def test_clip_lengths_handle_crossings_and_shared_boundary():
    r={'xy_mm':[[290,0],[310,0],[290,0]]}
    assert panel_length(r,0,300)==pytest.approx(20)
    assert panel_length(r,300,600)==pytest.approx(20)
    r={'xy_mm':[[300,0],[300,10]]}
    assert panel_length(r,0,300)==0
    assert panel_length(r,300,600)==10

def test_depth_fallback_is_explicit_not_ordinal_depth():
    row={'xy_mm':[[1,710],[3,720]],'forward_depth':1}
    assert depth_role(row,{'fields':None})==('near','screen-zone-fallback')
    row['source_forward_m']=4000
    assert depth_role(row,{'fields':None})==('far','source-depth-metadata')

def test_spring_rock_ink_and_material_paths_are_mineral():
    assert material({'layer':'rock-ink'})=='mineral'
    assert material({'color_channel':'material-C-like'})=='mineral'
    assert material({'color_channel':'RSU'})=='vegetation'
