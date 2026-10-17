"""Physical-size information budgets, spacing and safe contour contracts."""
from collections import defaultdict
import unittest
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_plot_scale as gram
from datascape.vegetation import tree_rhythm as prior
from datascape.strokes.vector import resample

def leaves(t):return [m for m in t.marks if m.part=='foliage-field']
def signature(t):return [(m.key,m.xy.tolist(),m.width,m.part,m.parent) for m in t.marks]
def units(t):
    out=defaultdict(list)
    for m in leaves(t):out[m.key.rsplit('-',1)[0]].append(m)
    return out


class PlotScaleTests(unittest.TestCase):
    def test_v06_control_is_unchanged(self):
        a=gram.make_tree(profile='v06');b=prior.make_tree('hero-pine')
        self.assertEqual(signature(a),signature(b));self.assertEqual(a.structure,b.structure)
        self.assertEqual(gram.vector_records(a.marks,[a]),prior.vector_records(b.marks,[b]))

    def test_both_touch_and_unit_counts_are_strongly_reduced(self):
        a=gram.make_tree(profile='v06');b=gram.make_tree();c=gram.make_tree(profile='spare')
        self.assertLess(len(units(b)),len(units(a))*.30)
        self.assertLess(len(leaves(b)),len(leaves(a))*.20)
        self.assertLess(len(units(c)),len(units(b)));self.assertLess(len(leaves(c)),len(leaves(b)))

    def test_units_use_one_to_three_touches_and_most_are_light(self):
        t=gram.make_tree();d=t.canopy_diagnostics
        counts=[len(v) for v in units(t).values()]
        self.assertTrue(set(counts)<={1,2,3});self.assertGreater(sum(n<=2 for n in counts),len(counts)*.85)
        self.assertGreaterEqual(len(set(counts)),2)
        self.assertTrue(all(abs(u['rotation_deg'])<=8 for u in d['units']))
        for p in d['pads']:self.assertLessEqual(p['retained_units'],p['unit_cap'])

    def test_independent_fine_sampling_confirms_between_unit_clearance(self):
        t=gram.make_tree();groups=list(units(t).values());best=float('inf')
        dense=[np.concatenate([resample(m.xy,.06) for m in marks]) for marks in groups]
        for i,a in enumerate(dense):
            if i:best=min(best,float(cKDTree(np.concatenate(dense[:i])).query(a)[0].min()))
        self.assertGreaterEqual(best,t.canopy_diagnostics['minimum_between_unit_centerline_gap_mm']-.03)

    def test_leaf_length_does_not_shrink_below_physical_floor(self):
        for h in [95,45,22]:
            t=gram.make_tree(height=h)
            self.assertTrue(all(prior.old.length(m.xy)>=2.8-1e-9 for m in leaves(t)))
            self.assertTrue(all(prior.old.length(m.xy)<=6.2+1e-9 for m in leaves(t)))

    def test_smaller_size_classes_reduce_information_and_use_single_structures(self):
        ts=[gram.make_tree(height=h) for h in [95,45,22]]
        counts=[len(leaves(t)) for t in ts]
        self.assertGreater(counts[0],counts[1]);self.assertGreater(counts[1],counts[2])
        self.assertEqual([t.canopy_diagnostics['size_class'] for t in ts],['large','medium','small'])
        self.assertFalse(any(m.part in ('twig','bark-grain') for m in ts[-1].marks))
        self.assertTrue(any('/single' in m.key for m in ts[-1].marks))

    def test_original_growth_members_posture_and_terminals_are_preserved(self):
        a=gram.make_tree(profile='v06');b=gram.make_tree()
        for k in ['members','axis_nodes_mm','posture','terminal_behavior']:
            self.assertEqual(a.structure[k],b.structure[k])
        self.assertNotIn('neck_fraction',b.structure['contour_spacing'])

    def test_ordered_sections_do_not_cross_and_nonmonotone_members_fall_back(self):
        for posture in ['upright','stooped','redirected']:
            t=gram.make_tree(posture=posture,seed=30)
            for a in t.structure['contour_audit'].values():self.assertEqual(a['opposite_side_crossings'],0)
            left=[m for m in t.marks if m.key.startswith('axis/side-1')]
            right=[m for m in t.marks if m.key.startswith('axis/side1')]
            self.assertEqual(sum(gram.segment_crossings(a.xy,b.xy) for a in left for b in right),0)
        loop=np.array([[0,0],[2,3],[-2,5],[0,0]])
        marks,audit,_=gram.safe_contours(loop,1,'axis',2)
        self.assertEqual(audit['mode'],'single nonmonotone fallback');self.assertEqual(len(marks),1)

    def test_arm_contours_do_not_continue_through_stem_interior(self):
        t=gram.make_tree();members=t.structure['members']
        axis=np.vstack([p if i==0 else p[1:] for i,(k,p) in enumerate((x for x in members.items() if x[0].startswith('axis/')))])
        origins=[np.array(p)[0] for k,p in members.items() if k.startswith('arm-')]
        _,_,envelope=gram.safe_contours(axis,t.height*.022,'axis',t.seed,.8,origins)
        for m in t.marks:
            if m.part=='branch-contour':self.assertGreater(np.min(gram.outside_stem(m.xy,envelope)),-.05)

    def test_policy_transfers_without_claiming_whole_catalog_approval(self):
        for f,h in [('broadleaf',75),('understory',55)]:
            t=gram.make_tree(f,height=h)
            self.assertTrue(all(1<=len(u)<=3 for u in units(t).values()))
            rr=gram.vector_records(t.marks,[t])
            self.assertTrue(all(r['catalog_version']=='0.7' and not r['physical_plotting_validated'] for r in rr))
            self.assertTrue(all(r['ground_visibility_status']=='unresolved' for r in rr))

    def test_all_geometry_is_finite_open_and_reproducible(self):
        a=gram.make_tree(seed=8);gram.make_tree(seed=13);b=gram.make_tree(seed=8)
        self.assertEqual(signature(a),signature(b));self.assertEqual(a.canopy_diagnostics,b.canopy_diagnostics)
        for m in a.marks:
            self.assertTrue(np.isfinite(m.xy).all());self.assertGreater(np.linalg.norm(m.xy[-1]-m.xy[0]),0)

    def test_invalid_design_parameters(self):
        for kwargs in [dict(profile='dense'),dict(design_width_mm=0),dict(clear_gap_mm=0),dict(height=10)]:
            with self.assertRaises(ValueError):gram.make_tree(**kwargs)


if __name__=='__main__':unittest.main()
