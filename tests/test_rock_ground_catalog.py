"""Invariant tests for source lineage, local visibility and physical mm intent."""
from copy import deepcopy
import json
import unittest
import numpy as np
from shapely.geometry import LineString,box
from datascape.ground.grammar import rock,soil,synthetic_terrain,path_record
from datascape.ground.interaction import Region,Corridor,plan,visible_regions,replacement_intervals,duplicate_coverage


def line(identity='p',depth=5.,y=0.):
    return path_record(identity,[(0,y),(10,y),(20,y)],'terrain','A-like',.6,depth,'terrain-ink')


class GroundCatalogTests(unittest.TestCase):
    def test_reproducible_and_seed_variation_is_structural(self):
        a=rock();b=rock();c=rock(seed=99)
        self.assertEqual(a.paths,b.paths)
        self.assertNotEqual(a.paths,c.paths)
        self.assertEqual(len(a.planes),3)
        self.assertTrue(a.support.is_valid)
        self.assertTrue(all(not LineString(p['xy_mm']).is_ring for p in a.paths))

    def test_middle_is_budgeted_not_resized_foreground(self):
        a=rock(width=36,height=24,detail='foreground');b=rock(width=36,height=24,detail='middle')
        self.assertLess(len(b.paths),len(a.paths))
        self.assertFalse(any(p['grammar_part']=='fracture' for p in b.paths))

    def test_semantic_surface_and_soil_are_not_opaque(self):
        host=np.c_[np.linspace(0,120,30),np.linspace(80,95,30)]
        a=rock(form='bedrock',surface_profile=host,surface_source_id='A-test')
        self.assertFalse(a.opaque)
        self.assertEqual(a.info['surface_source_id'],'A-test')
        self.assertFalse(soil().opaque)
        self.assertNotEqual(soil().paths[0]['grammar_part'],a.paths[0]['grammar_part'])

    def test_same_plane_grains_respect_declared_digital_clearance(self):
        for form in ['compact','angular','bedrock']:
            r=rock(form=form)
            for f in range(3):
                pp=[LineString(p['xy_mm']) for p in r.paths if f'/plane-{f}/' in p['id']]
                for i,p in enumerate(pp):
                    for q in pp[i+1:]: self.assertGreaterEqual(p.distance(q),.8-1e-8)

    def test_opaque_clearance_includes_both_footprints(self):
        a=line();r=Region('body','rock',box(8,-2,12,2),2.,boundary_ink_width_mm=.8)
        out,audit=plan([a],[r],minimum_mm=0,edge_mm=.2)
        self.assertAlmostEqual(audit['excluded_mm'],4+2*(.3+.4+.2),places=7)
        self.assertAlmostEqual(out[0]['source_arc_mm'][1],7.1,places=7)

    def test_depth_unknown_nearer_equal_and_farther(self):
        r=Region('body','rock',box(8,-2,12,2),2.)
        for depth,should_cut in [(None,False),(1.,False),(2.,False),(5.,True)]:
            out,a=plan([line(depth=depth)],[r])
            self.assertEqual(a['excluded_mm']>0,should_cut)
            self.assertEqual(bool(a['unknown_depth_pairs']),depth is None)
            self.assertEqual(bool(a['equal_depth_conflicts']),depth==2.)

    def test_traversal_does_not_change_decisions_or_fragments(self):
        records=[line('a',y=0),line('b',y=1)]
        regs=[Region('r1','rock1',box(4,-3,7,3),2.),Region('r2','rock2',box(12,-3,15,3),3.)]
        self.assertEqual(plan(records,regs),plan(list(reversed(records)),list(reversed(regs))))

    def test_hidden_body_has_no_independent_visible_mask(self):
        a=Region('rear','rear',box(4,-3,16,3),4.)
        b=Region('front','front',box(0,-5,20,5),2.)
        visible=visible_regions([a,b]);rear=next(x for x in visible if x.identity=='rear')
        self.assertTrue(rear.geometry.is_empty)
        self.assertEqual(plan([line()],[a,b]),plan([line()],[b]))

    def test_source_identity_intervals_and_length_accounting(self):
        records=synthetic_terrain(); frozen=deepcopy(records)
        replace=replacement_intervals(records,box(35,40,70,80))
        out,a=plan(records,replacements=replace)
        self.assertEqual(records,frozen)
        self.assertTrue(replace)
        kept=sum(b-a for p in out for a,b in [p['source_arc_mm']])
        self.assertAlmostEqual(kept+a['removed_mm'],a['source_length_mm'],places=7)
        self.assertAlmostEqual(a['excluded_mm']+a['short_dropped_mm'],a['removed_mm'],places=6)
        self.assertTrue(all(p['source_stroke_id'] in {r['id'] for r in records} for p in out))

    def test_fragment_profiles_are_interpolated_on_source_arc(self):
        r=line();r['width_profile_mm']=[.2,.6,1.0];r['expression']={'intensity_samples':[0.,.5,1.]}
        out,a=plan([r],replacements={'p':[[8.,12.]]})
        self.assertEqual(out[0]['width_profile_mm'],[.2,.52])
        np.testing.assert_allclose(out[1]['width_profile_mm'],[.68,1.])
        for p in out:self.assertEqual(len(p['xy_mm']),len(p['expression']['intensity_samples']))

    def test_short_fragments_drop_without_bridging_hard_gap(self):
        r=line();out,a=plan([r],replacements={'p':[[1.,4.],[6.,10.],[17.,19.]]})
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['source_arc_mm'],[10.,17.])
        self.assertAlmostEqual(a['short_dropped_mm'],4.)
        self.assertGreaterEqual(a['minimum_final_path_mm'],2.8)

    def test_corridor_protects_the_actual_stroke_footprint(self):
        c=Corridor('opening',box(8,-2,12,2));out,a=plan([line()],corridor=c)
        for p in out:
            footprint=LineString(p['xy_mm']).buffer(p['width_mm']/2)
            self.assertLess(footprint.intersection(c.geometry).area,1e-7)
        self.assertIn('opening',a['sources'][0]['reasons'])

    def test_protection_cannot_waive_solid_body(self):
        out,a=plan([line()],[Region('body','rock',box(8,-2,12,2),2.)],protected={'p':[[0.,20.]]})
        self.assertEqual(len(a['contact_conflicts']),1)
        self.assertGreater(a['excluded_mm'],0)

    def test_missing_references_and_second_clipping_are_rejected(self):
        with self.assertRaises(ValueError):plan([line()],replacements={'absent':[[1,2]]})
        out,_=plan([line()],replacements={'p':[[8,12]]})
        with self.assertRaises(ValueError):plan(out)

    def test_shared_fixture_preserves_canonical_tree_width_and_profiles(self):
        from datascape.rendering.rock_ground_catalog_support import tree_fixture
        from datascape.vegetation.tree_final_scale import vector_records
        t,adapted,regions,info=tree_fixture()
        src=vector_records(t.marks,[t])
        for a,b in zip(src,adapted):
            self.assertEqual(a['xy_mm'],b['xy_mm'])
            self.assertEqual(a['width_mm'],b['width_mm'])
            self.assertEqual(a.get('width_profile_mm'),b.get('width_profile_mm'))
            self.assertEqual(b['assumed_footprint_mm'],.8)


    def test_replacement_reduces_duplicate_coverage(self):
        src=synthetic_terrain();s=soil(origin=(14,54),width=90,height=31)
        replaced,_=plan(src,replacements=replacement_intervals(src,box(20,42,104,85)))
        self.assertLess(duplicate_coverage(replaced,s.paths)['duplicate_mm2'],duplicate_coverage(src,s.paths)['duplicate_mm2']*.2)


if __name__=='__main__':unittest.main()
