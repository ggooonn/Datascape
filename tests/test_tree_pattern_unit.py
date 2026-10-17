"""Exact V02 ancestry, limited variation and independent constructed bodies."""
import unittest
import numpy as np
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_pattern as pattern


def body_signature(tree):
    return [(m.key,m.xy.tolist(),m.width,m.parent) for m in tree.marks if m.part!='foliage-field']


class PatternTests(unittest.TestCase):
    def test_control_reproduces_exact_v02_fan_canopy_and_footprint(self):
        for family in old.FAMILIES:
            a=old.make_tree(family,'fans',height=95)
            b=pattern.make_tree(family,canopy='v02-control')
            aa=[(m.key,m.xy.tolist(),m.width) for m in a.marks if m.part=='foliage-field']
            bb=[(m.key,m.xy.tolist(),m.width) for m in b.marks if m.part=='foliage-field']
            self.assertEqual(aa,bb)
            for x,y in zip(a.lobes,b.lobes):
                np.testing.assert_array_equal(x['center'],y['center'])
                np.testing.assert_array_equal(x['radii'],y['radii'])
                self.assertEqual(x['angle'],y['angle'])

    def test_count_only_is_a_literal_subset_with_two_to_five_visible_touches(self):
        for family in old.FAMILIES:
            a=pattern.make_tree(family,canopy='v02-control');b=pattern.make_tree(family,canopy='count-2-5')
            source={m.key:m for m in a.marks}
            for m in b.marks:np.testing.assert_array_equal(m.xy,source[m.key].xy)
            counts=[p['retained_touches'] for p in b.canopy_diagnostics['packets'] if p['retained_touches']]
            self.assertTrue(set(counts)<={2,3,4,5});self.assertTrue({2,3,4,5}<=set(counts))
            self.assertGreater(b.canopy_diagnostics['retained_fraction'],.80)
            self.assertLess(b.canopy_diagnostics['retained_fraction'],.97)

    def test_jitter_only_rotates_same_paths_at_fixed_starts_with_five_to_ten_degrees(self):
        a=pattern.make_tree(canopy='count-2-5');b=pattern.make_tree(canopy='count-angle')
        self.assertEqual([m.key for m in a.marks],[m.key for m in b.marks])
        self.assertEqual(body_signature(a),body_signature(b))
        for m,n in zip(a.marks,b.marks):
            if m.part!='foliage-field':continue
            np.testing.assert_allclose(m.xy[0],n.xy[0],atol=1e-10)
            self.assertAlmostEqual(old.length(m.xy),old.length(n.xy),places=10)
            d=m.xy[-1]-m.xy[0];e=n.xy[-1]-n.xy[0]
            angle=np.degrees(np.arctan2(d[0]*e[1]-d[1]*e[0],d@e))
            self.assertGreaterEqual(abs(angle),5-1e-8);self.assertLessEqual(abs(angle),10+1e-8)

    def test_body_crown_and_visibility_are_identical_across_canopy_controls(self):
        ts=[pattern.make_tree(canopy=c) for c in pattern.CANOPIES]
        sample=np.array([[80,80],[90,100],[110,70],[90,149]],float)
        for t in ts[1:]:
            self.assertEqual(ts[0].structure,t.structure)
            self.assertEqual(body_signature(ts[0]),body_signature(t))
            np.testing.assert_array_equal(old.foreground_gate(sample,ts[0]),old.foreground_gate(sample,t))

    def test_posture_family_changes_growth_but_keeps_original_crown_supports(self):
        ts=[pattern.make_tree('hero-pine',posture=p) for p in pattern.POSTURES]
        self.assertEqual(len({str(t.structure['axis_nodes_mm']) for t in ts}),3)
        for t in ts:
            self.assertIn(t.structure['member_count'],[2,3,4])
            self.assertTrue(any(x=='straight' for x in t.structure['segment_types']))
            members=t.structure['members'];axis=np.concatenate([p for k,p in members.items() if k.startswith('axis/')])
            for i,tip in enumerate(t.structure['branch_terminals_mm']):
                arm=np.array(members[f'arm-{i}'])
                np.testing.assert_allclose(arm[-1],tip,atol=1e-10)
                self.assertLess(np.linalg.norm(axis-arm[0],axis=1).min(),1e-8)
            contours=[m for m in t.marks if m.part=='trunk-contour']
            self.assertGreaterEqual(len(contours),6);self.assertLessEqual(len(contours),8)
            self.assertTrue(any(m.part=='bark-grain' for m in t.marks))

    def test_seeds_give_multiple_growth_characters_and_are_order_independent(self):
        a=pattern.make_tree(seed=40);pattern.make_tree(seed=41);b=pattern.make_tree(seed=40)
        self.assertEqual(body_signature(a),body_signature(b))
        self.assertEqual(a.canopy_diagnostics,b.canopy_diagnostics)
        poses={pattern.make_tree(seed=i).structure['posture'] for i in range(10,20)}
        self.assertEqual(poses,set(pattern.POSTURES))

    def test_seasonal_parameters_keep_exact_body(self):
        ts={s:pattern.make_tree(season=s) for s in old.SEASONS}
        for t in ts.values():
            self.assertEqual(body_signature(ts['spring']),body_signature(t))
            self.assertEqual(ts['spring'].structure,t.structure)
        count=lambda s:sum(m.part=='foliage-field' for m in ts[s].marks)
        self.assertGreater(count('summer'),count('spring'));self.assertGreater(count('spring'),count('autumn'))
        self.assertEqual(count('winter'),0)

    def test_overlap_export_retains_ownership_and_unresolved_ground(self):
        trees=[pattern.make_tree(root=(70+i*12,140+i*4),height=70,seed=10+i,identity=f't{i}') for i in range(3)]
        marks,stats=old.overlap(trees);self.assertGreater(stats['removed_mm'],0)
        self.assertEqual({m.owner for m in marks},{'t0','t1','t2'})
        records=pattern.vector_records(marks,trees)
        self.assertTrue(all(x['catalog_version']=='0.5' for x in records))
        self.assertTrue(all(x['ground_visibility_status']=='unresolved' for x in records))
        self.assertTrue(all(np.isfinite(m.xy).all() and np.linalg.norm(m.xy[-1]-m.xy[0])>0 for m in marks))

    def test_middle_detail_is_reduced_without_changing_source_foliage(self):
        a=pattern.make_tree(depth='near');b=pattern.make_tree(depth='middle')
        self.assertFalse(any(m.part in ('twig','bark-grain') for m in b.marks))
        leaves=lambda t:[(m.key,m.xy.tolist()) for m in t.marks if m.part=='foliage-field']
        self.assertEqual(leaves(a),leaves(b))

    def test_invalid_inputs(self):
        for kwargs in [dict(angle_limit_deg=20),dict(angle_limit_deg=0),dict(canopy='hybrid'),dict(height=float('nan')),dict(posture='random')]:
            with self.assertRaises(ValueError):pattern.make_tree(**kwargs)


if __name__=='__main__':unittest.main()
