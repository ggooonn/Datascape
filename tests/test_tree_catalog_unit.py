"""Standalone catalog tests; no raster/scene/hardware dependency is needed."""
import unittest
import tempfile
from pathlib import Path
import numpy as np
from datascape.vegetation import tree_catalog as tc
from datascape.strokes.vector import save_vectors, read_vectors


def signature(marks):
    return [(m.key,m.width,m.part,m.parent,m.xy.tolist()) for m in marks]


class CatalogTests(unittest.TestCase):
    def test_family_canopy_matrix_is_finite_open_and_has_built_trunks(self):
        for family in tc.FAMILIES:
            for canopy in tc.CANOPIES:
                t=tc.make_tree(family,canopy)
                self.assertTrue(any(m.part=='bark-grain' for m in t.marks))
                self.assertTrue(any(m.part=='trunk-contour' for m in t.marks))
                self.assertFalse(any(m.part=='trunk-control' for m in t.marks))
                for m in t.marks:
                    self.assertTrue(np.isfinite(m.xy).all())
                    self.assertGreaterEqual(len(m.xy),2)
                    self.assertGreater(np.linalg.norm(m.xy[0]-m.xy[-1]),1e-6)
                    self.assertGreaterEqual(tc.length(m.xy),1.19)

    def test_fixed_seed_and_call_order_determinism(self):
        a=tc.make_tree('broadleaf','hybrid',seed=13)
        tc.make_tree('hero-pine','fans',seed=35)
        b=tc.make_tree('broadleaf','hybrid',seed=13)
        self.assertEqual(signature(a.marks),signature(b.marks))
        self.assertNotEqual(signature(a.marks),signature(tc.make_tree('broadleaf','hybrid',seed=14).marks))

    def test_canopy_changes_do_not_redraw_structure(self):
        trees=[tc.make_tree('broadleaf',canopy) for canopy in tc.CANOPIES]
        base=signature([m for m in trees[0].marks if m.part!='foliage-field'])
        for t in trees[1:]:self.assertEqual(base,signature([m for m in t.marks if m.part!='foliage-field']))

    def test_seasons_keep_structure_and_change_canopy(self):
        trees={s:tc.make_tree('broadleaf',season=s) for s in tc.SEASONS}
        base=signature([m for m in trees['spring'].marks if m.part!='foliage-field'])
        for t in trees.values():self.assertEqual(base,signature([m for m in t.marks if m.part!='foliage-field']))
        count=lambda s:sum(m.part=='foliage-field' for m in trees[s].marks)
        self.assertGreater(count('summer'),count('spring'))
        self.assertLess(count('autumn'),count('spring'))
        self.assertEqual(count('winter'),0)
        pine=tc.make_tree('hero-pine',season='winter')
        self.assertGreater(sum(m.part=='foliage-field' for m in pine.marks),0)

    def test_translation_preserves_object_geometry(self):
        a=tc.make_tree(root=(90,155));b=tc.make_tree(root=(110,165))
        for x,y in zip(a.marks,b.marks):np.testing.assert_allclose(y.xy-x.xy,np.tile([20,10],(len(x.xy),1)),atol=1e-10)

    def test_paired_and_segmented_trunks_have_different_lift_counts(self):
        a=tc.make_tree('hero-pine',trunk_mode='paired');b=tc.make_tree('hero-pine',trunk_mode='segmented')
        self.assertEqual(sum(m.part=='trunk-contour' for m in a.marks),2)
        self.assertEqual(sum(m.part=='trunk-contour' for m in b.marks),7)

    def test_overlap_cuts_geometry_and_keeps_object_provenance(self):
        a=tc.make_tree('broadleaf','ribbons',root=(85,145),identity='rear')
        b=tc.make_tree('broadleaf','hybrid',root=(100,160),height=90,identity='front')
        original=signature(a.marks)
        visible,record=tc.overlap([a,b])
        self.assertGreater(record['removed_mm'],0)
        self.assertGreater(record['affected_source_paths'],0)
        self.assertEqual(signature(a.marks),original)
        self.assertEqual({m.owner for m in visible},{'rear','front'})
        for m in visible:
            if m.owner=='rear':self.assertGreaterEqual(tc.foreground_gate(tc.resample(m.xy,.3),b).min(),-.08)

    def test_unique_cluster_id_is_required(self):
        a=tc.make_tree(identity='duplicate');b=tc.make_tree(identity='duplicate')
        with self.assertRaises(ValueError):tc.overlap([a,b])

    def test_wash_is_separate_intent_without_executable_paths(self):
        t=tc.make_tree();before=signature(t.marks);wash=tc.wash_metadata([t])
        self.assertTrue(wash['not_plotter_paths'])
        self.assertFalse(wash['calibrated_pigment'])
        self.assertEqual(signature(t.marks),before)
        self.assertTrue(all('outline_xy_mm' in r for r in wash['regions']))
        ss=tc.vector_records(t.marks,[t])
        self.assertTrue(all('outline_xy_mm' not in s for s in ss))

    def test_records_roundtrip_profiles_and_root_identity(self):
        t=tc.make_tree(identity='fixture');ss=tc.vector_records(t.marks,[t])
        self.assertEqual(len({s['id'] for s in ss}),len(ss))
        for s in ss:
            self.assertEqual(s['source_root_id'],'fixture')
            self.assertEqual(s['source_root_xy_mm'],t.root.tolist())
            self.assertFalse(s['expression']['pressure_calibrated'])
            self.assertEqual(s['ground_visibility_status'],'unresolved')
            self.assertEqual(len(s['width_profile_mm']),len(s['xy_mm']))
            self.assertEqual(len(s['expression']['intensity_samples']),len(s['xy_mm']))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'v.gz';save_vectors(p,ss,{'synthetic':True});self.assertEqual(read_vectors(p)['strokes'],ss)

    def test_accent_layer_changes_structure_but_keeps_root(self):
        for accent in tc.ACCENTS:
            t=tc.make_tree('broadleaf',accent=accent)
            np.testing.assert_array_equal(t.root,[90,155])
            self.assertTrue(all(np.isfinite(m.xy).all() for m in t.marks))
        broken=tc.make_tree('hero-pine',accent='broken-top')
        self.assertTrue(any(m.part=='fracture' for m in broken.marks))
        dead=tc.make_tree('broadleaf',accent='dead-limb')
        self.assertTrue(any(m.part=='dead-limb' for m in dead.marks))

    def test_invalid_inputs_are_rejected(self):
        for kwargs in [{'height':0},{'height':float('nan')},{'root':(0,float('nan'))},{'family':'unknown'},{'canopy':'unknown'},{'accent':'unknown'},{'trunk_mode':'unknown'}]:
            with self.assertRaises(ValueError):tc.make_tree(**kwargs)


if __name__=='__main__':unittest.main()
