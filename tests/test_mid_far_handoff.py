"""Guard the closure direction against accidental candidate promotion."""
from pathlib import Path
import json
import pytest
from datascape.vegetation.mid_far_handoff import recommended_selection

ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'configs/vegetation/mid_far_integration_handoff_v05.json').read_text())


@pytest.mark.parametrize('distance',['middle','far'])
def test_primary_only_is_the_default(distance):
    plan=recommended_selection(POLICY,distance)
    assert plan['primary_families']==['R','S','U']
    assert not plan['far_micro_B_enabled'] and not plan['v05_A_C_enabled']
    assert not plan['scene_integration'] and plan['terrain_mask']=='overlay'


def test_b_cannot_be_selected_for_middle():
    with pytest.raises(ValueError,match='far-only'):
        recommended_selection(POLICY,'middle',include_far_b=True)


def test_far_b_does_not_silently_reuse_unlinked_historical_marks():
    with pytest.raises(NotImplementedError,match='linked ink'):
        recommended_selection(POLICY,'far',include_far_b=True)


def test_plan_does_not_mutate_the_policy_or_share_its_family_list():
    before=json.dumps(POLICY,sort_keys=True)
    plan=recommended_selection(POLICY,'far');plan['primary_families'].clear()
    assert json.dumps(POLICY,sort_keys=True)==before
