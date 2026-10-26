"""Summer-specific original-arc and panel conservation regressions."""
from pathlib import Path
from copy import deepcopy
import importlib.util,sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studies/summer_scene_v01'))
from generate import panel_rows,progress
from verify import validate_rows,check_panels,read
OUT=ROOT/'docs/experiments/summer_scene_v01'


def test_seam_clipping_preserves_reentry_and_profiles():
    source=dict(id='crossing',xy_mm=[[290,10],[310,20],[290,30],[310,40]],width_mm=.4,
        width_profile_mm=[.2,.3,.5,.7],opacity_profile=[.3,.4,.5,.6],expression=dict(intensity_samples=[.2,.4,.6,.8]))
    p={n:panel_rows([source],n) for n in (3,4)}
    assert sum(len(rows) for rows in p.values())==4
    checked=check_panels([source],p)
    assert checked['max_source_length_error_mm']<1e-9
    for r in [r for rows in p.values() for r in rows]:assert len(r['width_profile_mm'])==len(r['xy_mm'])==len(r['expression']['intensity_samples'])


def test_original_arc_mutation_is_rejected():
    original=dict(id='s',xy_mm=[[10,10],[20,15],[30,10]],width_mm=.4)
    final=dict(id='f',xy_mm=original['xy_mm'],source_stroke_id='s',source_arc_mm=[0,2*np.hypot(10,5)])
    validate_rows([final],{'s':original})
    changed=deepcopy(final);changed['xy_mm'][1][1]+=1
    with pytest.raises(ValueError,match='geometry'):validate_rows([changed],{'s':original})


def test_panel_missing_fragment_is_rejected():
    source=dict(id='s',xy_mm=[[250,300],[350,350]],width_mm=.3)
    with pytest.raises(ValueError,match='length loss'):check_panels([source],{3:panel_rows([source],3),4:[]})


def test_actual_output_sources_and_panels():
    sources={r['id']:r for r in read(OUT/'authoring_sources.json.gz')['strokes']}
    full=[]
    for name in ['summer_ink','summer_color_intent']:
        rows=read(OUT/f'{name}.json.gz')['strokes'];validate_rows(rows,sources);full+=rows
    check_panels(full,{n:read(OUT/f'P{n}.vectors.json.gz')['strokes'] for n in (3,4)})


def test_no_step_in_growth_or_machine_scope():
    eps=1e-6
    assert abs(progress(300-eps)-progress(300+eps))<1e-6
    assert progress(0)==0 and progress(600)==1
    config=read(ROOT/'studies/summer_scene_v01/config.json')
    assert config['far_surface_micro_B_enabled'] is False
    gen=read(OUT/'generation.json')
    assert not gen['production_Gcode_generated'] and not gen['Spring_modified']


def test_closed_path_and_exact_seam_have_unique_arc_ownership():
    closed=dict(id='loop',xy_mm=[[280,50],[320,50],[320,80],[280,80],[280,50]],width_mm=.3)
    seam=dict(id='seam',xy_mm=[[300,100],[300,130]],width_mm=.3)
    rows=[closed,seam];panels={n:panel_rows(rows,n) for n in (3,4)}
    check_panels(rows,panels)
    assert sum(r['canonical_source_id']=='seam' for r in panels[3])==0
    assert sum(r['canonical_source_id']=='seam' for r in panels[4])==1


def test_fully_visible_short_source_cannot_bypass_minimum():
    from generate import clip_review
    r=dict(id='tiny',xy_mm=[[20,30],[20.5,30]],width_mm=.3)
    rows,audit=clip_review(r,lambda xy,arc,r:(np.ones(len(xy)),[]))
    assert rows==[] and audit['removed_mm']==.5
    assert audit['kept_intervals_mm']==[]
