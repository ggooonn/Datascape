"""Accepted patch relationships preserve ownership, whitespace and one ink field."""
from dataclasses import replace
import pytest
from shapely.geometry import LineString,box
from datascape.ground.surface_ground_v02 import ground_source
from datascape.ground.patch_system_v04 import PatchSpec,PatchControls,patch_system,distribution_cases
from datascape.ground.interaction import Corridor


def test_geometry_and_pigment_are_independent_of_internal_density():
    host=ground_source()[2];specs=[PatchSpec('ground',83,3,850,3.2,.28)]
    a=patch_system('same',host,specs,PatchControls(spacing_mm=2.4))
    b=patch_system('same',host,specs,PatchControls(spacing_mm=5.5))
    c=patch_system('same',host,specs,PatchControls(spacing_mm=2.4,pigment_enabled=False))
    assert a.surface.support.equals_exact(b.surface.support,0)
    assert a.surface.support.equals_exact(c.surface.support,0)
    assert len(a.surface.paths)>len(b.surface.paths)
    assert a.surface.paths==c.surface.paths and c.pigment_support.is_empty
    assert a.pigment_support.area>0


@pytest.mark.parametrize('key,components',[('none',0),('satellites',3),('connected',2),('shared',1)])
def test_patch_relationships_do_not_duplicate_ink(key,components):
    _,_,specs,controls,white=next(x for x in distribution_cases() if x[0]==key)
    host=ground_source()[2];corridor=Corridor('open',box(153,61,165,108))
    ground=patch_system('family',host,specs,controls,corridor,white)
    assert ground.surface.info['effective_components']==components
    paths=ground.surface.paths
    for i,a in enumerate(paths):
        for b in paths[i+1:]:assert LineString(a['xy_mm']).intersection(LineString(b['xy_mm'])).length<1e-7
    assert ground.surface.support.intersection(corridor.geometry).area==0
    assert ground.pigment_support.intersection(corridor.geometry).area==0
    assert not ground.surface.opaque
    if key=='none':assert not paths and ground.pigment_support.is_empty


def test_context_geometry_is_not_derived_from_host_object_size():
    host=ground_source()[2];spec=PatchSpec('contact',80,3,850,3.2,.25)
    a=patch_system('same',host,[spec]);b=patch_system('same',host,[replace(spec,aspect_ratio=5.5)])
    assert abs(a.surface.support.area-850)<.002*850
    assert abs(b.surface.support.area-850)<.002*850
    assert not a.surface.support.equals(b.surface.support)
    with pytest.raises(ValueError):
        patch_system('bad',host,[spec,replace(spec,identity='b',x_mm=82)],PatchControls(minimum_separation_mm=3))
