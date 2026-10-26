"""Near-domain protection, source-arc integrity and scene regression checks."""
from pathlib import Path
from copy import deepcopy
import sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studies/seasonal_screen_v01'))
from common import prior,read,split_domain,ROOT,BASE
import importlib.util
_spec=importlib.util.spec_from_file_location('seasonal_verify',ROOT/'studies/seasonal_screen_v01/verify.py');_v=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_v)
check=_v.check


def test_source_depth_split_preserves_geometry_and_profiles():
    yy,xx=np.mgrid[:900,:600];f=dict(base=dict(depth_m=xx*10.))
    r=dict(id='cross',xy_mm=[[100,300],[200,400]],width_mm=.3,width_profile_mm=[.2,.6],layer='A')
    near,_=split_domain([r],f,True);far,_=split_domain([r],f,False)
    assert abs(sum(prior.total_length(rows) for rows in [near,far])-prior.total_length([r]))<1e-6
    assert np.max(np.array(near[0]['xy_mm'])[:,0])==pytest.approx(160.5)
    assert len(near[0]['width_profile_mm'])==len(near[0]['xy_mm'])


def test_short_source_is_not_lengthened():
    r=dict(id='tiny',xy_mm=[[20,30],[20.3,30]],width_mm=.3)
    before=deepcopy(r);parts,a=prior.clip_review(r,lambda p,arc,r:(np.ones(len(p)),[]))
    assert not parts and a['removed_mm']==pytest.approx(.3)
    assert r==before


def test_summer_protected_records_and_actual_vectors():
    result=check(ROOT/'docs/experiments/summer_foreground_v02')
    assert result['checks']['unchanged_full_middle_far_records']>1000
    assert result['inherited_changes']==[]


def test_double_crossing_panel_conservation():
    r=dict(id='zigzag',xy_mm=[[290,100],[310,110],[290,120],[310,130]],width_mm=.3)
    parts=[prior.panel_rows([r],n) for n in (3,4)]
    assert sum(prior.total_length(rows) for rows in parts)==pytest.approx(prior.total_length([r]))
    assert sum(map(len,parts))==4


def test_malformed_profile_is_rejected():
    pinned=_v.pinned
    r=dict(id='s',xy_mm=[[20,30],[30,40]],width_mm=.3)
    q=dict(id='out',xy_mm=r['xy_mm'],width_profile_mm=[.3],source_stroke_id='s',source_arc_mm=[0,2**.5*10])
    with pytest.raises(ValueError,match='profile'):pinned.validate_rows([q],{'s':r})
