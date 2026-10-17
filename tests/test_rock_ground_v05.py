"""Scale, source lineage, material separation and fixed-fixture invariants."""
from copy import deepcopy
from dataclasses import replace
import pytest
from shapely.geometry import LineString
from shapely.ops import unary_union
from datascape.rendering.rock_ground_catalog import build
from datascape.ground.material_review_v05 import tag,family,appearance,angle_audit
from datascape.ground.structural_detail_v05 import feature_detail,formation,FormationControls,PhysicalDetailPolicy,base_mass
from datascape.rendering.rock_ground_review_controls import alternatives
from datascape.rendering.rock_ground_catalog_fixtures import shared_ground_fixture

@pytest.fixture(scope='module')
def study():return build()

def sig(paths,families):
    return [(p['id'],p['xy_mm'],p.get('width_profile_mm'),p.get('opacity_profile')) for p in paths if family(p) in families]

def test_material_is_view_only(study):
    paths=study[2]['ground-v05'];before=deepcopy(paths)
    assert any(family(p)=='C' for p in paths)
    assert all(appearance(p,'ink') is None for p in paths if family(p)=='C')
    assert all(appearance(p,'color-ready') is not None for p in paths)
    assert paths==before
    proposed=study[2]['ground-C-contact-proposal']
    assert sig(paths,['A','rock','soil','tree','support'])==sig(proposed,['A','rock','soil','tree','support'])
    assert sig(paths,['C'])!=sig(proposed,['C'])
    assert study[4]['ground-v05']['C_footprint_overlap_mm2']['support']>0
    assert study[4]['ground-C-contact-proposal']['C_footprint_overlap_mm2']['support']==0
    raw=study[3]['ground-v05'];tagged=tag(raw)
    assert [(p['id'],p['xy_mm']) for p in raw]==[(p['id'],p['xy_mm']) for p in tagged]

def test_source_steepness_is_identified(study):
    a=study[4]['ground-v05']['raw_angles']
    assert a['C']['steep_fraction']>.99 and a['A']['steep_fraction']==0
    assert a['soil']['steep_fraction']==0
    assert a['rock']['steep_length_mm']>0

def test_no_ac_geometry_edits(study):
    states,sources=study[2],study[3]
    assert sig(sources['ground-v04'],['A','C'])==sig(sources['ground-v05'],['A','C'])
    assert sig(states['ground-v04'],['A','C'])==sig(states['ground-v05'],['A','C'])
    # Reproduce the prior v04 output exactly, except for added review intent metadata.
    old=shared_ground_fixture()[4]
    assert sig(old,['A','C','rock','tree','support'])==sig(states['ground-v05'],['A','C','rock','tree','support'])

def test_ground_geometry_is_not_rebuilt(study):
    g=study[5];a=g['ground-v04']['ground'];b=g['ground-v05']['ground']
    assert a.surface.support.equals_exact(b.surface.support,0)
    assert a.pigment_support.equals_exact(b.pigment_support,0)
    assert a.white_reserve.equals_exact(b.white_reserve,0)
    assert a.patches==b.patches
    old=sum(LineString(p['xy_mm']).length for p in a.surface.paths)
    new=sum(LineString(p['xy_mm']).length for p in b.surface.paths)
    assert new<old

def test_structural_geometry_macro_and_features(study):
    states,geom=study[2],study[5]
    a,b=geom['structure-v04']['masses'],geom['structure-v05']['masses']
    assert all(x.surface.support.equals_exact(y.surface.support,0) for x,y in zip(a,b))
    base_ids={p['id'] for m in alternatives()['B'] for p in m.surface.paths}
    macro=lambda key:[(p['source_stroke_id'],p['xy_mm']) for p in states[key] if p['source_stroke_id'] in base_ids]
    assert macro('structure-v04')==macro('structure-v05')
    added=[p for p in study[3]['structure-v05'] if p.get('detail_level')]
    assert added
    assert all(p['feature_source_id'] in base_ids for p in added)
    assert all(p.get('junction_source_id',p['feature_source_id']) in base_ids for p in added)
    for a in study[4]['structure-v05']['feature_details']:
        assert a['detail_area_fraction']<.5
        assert all(e['overlap']<=.20 for e in a['events'] if e['accepted'])

def test_small_catalog_is_not_scaled_hatch(study):
    catalog=study[7]
    xs=[r for r in catalog if r['size_class']=='XS'];small=[r for r in catalog if r['size_class']=='S']
    assert len(catalog)==11
    assert all(r['added_paths']==0 and r['path_count']<=5 for r in xs)
    assert all(r['added_paths']==0 and r['path_count']<=10 for r in small)
    assert {r['size_class'] for r in catalog}=={'XS','S','M','L','XL'}
    for paths in study[2].values():
        for p in paths:
            if p.get('detail_level')=='micro':assert 2.8<=LineString(p['xy_mm']).length<=6.

def test_b_is_a_composition_policy(study):
    groups=[r for r in study[7] if r['morphology']=='B group']
    assert [r['major_mass_count'] for r in groups]==[2,3,4]
    for r in groups:
        masses=study[5][r['key']]['masses']
        assert unary_union([m.surface.support for m in masses]).geom_type=='Polygon'
        assert sum(s['excluded_mm'] for s in study[4][r['key']]['sources'])>5
    c=FormationControls(width_mm=170,height_mm=65)
    a=formation('same',c);b=formation('same',replace(c,dominance=.62,overlap=.36,burial=.25))
    assert not a[0].surface.support.equals(b[0].surface.support)


def test_contract_and_minimum(study):
    states,audits,geom=study[2],study[4],study[5]
    for key,paths in states.items():
        for p in paths:
            line=LineString(p['xy_mm']);assert line.is_simple and line.length>=2.8-1e-6
        if key in ['ground-v04','ground-v05','overview-A','overview-B']:
            corridor=geom[key]['corridor'].geometry
            for p in paths:
                width=p.get('assumed_footprint_mm',p['width_mm'])
                assert LineString(p['xy_mm']).buffer(width/2).intersection(corridor).area<1e-5
            assert not audits[key]['contact_conflicts'] and not audits[key]['unknown_depth_pairs'] and not audits[key]['equal_depth_conflicts']
            contacts=[s for s in audits[key]['sources'] if 'root-support' in s['source_id'] or s['source_id']=='v04/protected-ground']
            assert contacts and all(s['removed_mm']<1e-6 for s in contacts)

def test_v10_unchanged_and_deterministic(study):
    assert all(f['canonical_geometry_unchanged'] and f['canonical_width_profiles_retained'] for f in study[6])
    m=base_mass('determinism',165,70,'bedrock','jointed');old=deepcopy(m.surface.paths)
    a=feature_detail(m);b=feature_detail(m)
    assert a[0].surface.paths==b[0].surface.paths and a[1]==b[1] and m.surface.paths==old
    assert feature_detail(m,physical_policy=PhysicalDetailPolicy(secondary_min_width_mm=200))[1]['added_paths']==0
