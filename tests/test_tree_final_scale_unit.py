"""Independent final-scale knobs and preservation of the v09 anatomy."""
import unittest
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_final_scale as gram
from datascape.vegetation import tree_form_calibration as prior
from datascape.vegetation import tree_catalog as old
from datascape.strokes.vector import resample


def signature(marks): return [(m.key, m.xy.tolist(), m.part, m.parent) for m in marks]
def body(tree): return [m for m in tree.marks if m.part != 'foliage-field']


class FinalScaleTests(unittest.TestCase):
    def test_exact_control_and_unchanged_body_supports(self):
        for form in 'PBUW':
            a=prior.make_tree(form,height=95);b=gram.make_tree(form,height=95,profile='v09');c=gram.make_tree(form,height=95)
            self.assertEqual(signature(a.marks),signature(b.marks))
            self.assertEqual(prior.vector_records(a.marks,[a]),gram.vector_records(b.marks,[b]))
            self.assertEqual(signature(body(a)),signature(body(c)))
            self.assertEqual(a.structure['members'],c.structure['members'])
            for x,y in zip(a.lobes,c.lobes):
                np.testing.assert_array_equal(x['center'],y['center']);np.testing.assert_array_equal(x['radii'],y['radii'])

    def test_touch_and_length_changes_keep_all_unit_positions_and_omissions(self):
        for form in 'PB':
            a=gram.make_tree(form,height=130,profile='v09');aa=gram.bundles(a.marks)
            for profile in ['touch','length','refined']:
                b=gram.make_tree(form,height=130,profile=profile);bb=gram.bundles(b.marks)
                self.assertEqual(set(aa),set(bb))
                for key in aa:
                    source={m.key:m for m in aa[key]}
                    for m in bb[key]:
                        if m.key in source:np.testing.assert_array_equal(m.xy[0],source[m.key].xy[0])
                self.assertEqual([(p['key'],p['state'],p['retained_units']) for p in a.canopy_diagnostics['pads']],
                                 [(p['key'],p['state'],p['retained_units']) for p in b.canopy_diagnostics['pads']])

    def test_actual_counts_not_requested_budgets_and_independent_count_profile(self):
        for form in 'PB':
            a=gram.make_tree(form,height=130,profile='v09');touch=gram.make_tree(form,height=130,profile='touch');units=gram.make_tree(form,height=130,profile='units')
            self.assertGreater(len(gram.bundles(units.marks)),len(gram.bundles(a.marks)))
            self.assertGreater(touch.canopy_diagnostics['retained_foliage_paths'],units.canopy_diagnostics['retained_foliage_paths'])
            aa={m.key:m for m in a.marks if m.part=='foliage-field'}
            uu={m.key:m for m in units.marks if m.part=='foliage-field'}
            self.assertTrue(set(aa)<=set(uu))
            for key in aa:np.testing.assert_array_equal(aa[key].xy,uu[key].xy)

    def test_small_sizes_and_source_availability_limits_are_explicit(self):
        for form in 'PBUW':
            a=gram.make_tree(form,height=22,profile='v09');b=gram.make_tree(form,height=22)
            self.assertEqual(signature(a.marks),signature(b.marks))
        w=gram.make_tree('W',height=130)
        self.assertTrue(all(u['touches']<=3 for u in w.canopy_diagnostics['units']))
        self.assertTrue(any(u['requested_touches']>u['available_touches'] for u in w.canopy_diagnostics['units']))

    def test_correlated_lengths_respect_floor_and_inter_unit_clearance(self):
        for form,h in [('P',130),('B',95),('U',45),('W',130)]:
            t=gram.make_tree(form,height=h);seen=[]
            for mm in gram.bundles(t.marks).values():
                for m in mm:self.assertGreaterEqual(old.length(m.xy),2.8-1e-9)
                dense=np.concatenate([resample(m.xy,.05) for m in mm])
                if seen:self.assertGreaterEqual(float(cKDTree(np.concatenate(seen)).query(dense)[0].min()),1.27)
                seen.append(dense)
            for u in t.canopy_diagnostics['units']:self.assertLessEqual(abs(u['rotation_deg']),8)

    def test_export_preserves_unresolved_material_and_ground_status(self):
        t=gram.make_tree('P',height=95);rr=gram.vector_records(t.marks,[t])
        self.assertTrue(all(r['catalog_version']=='0.10' and r['ground_visibility_status']=='unresolved' and not r['physical_plotting_validated'] for r in rr))
        with self.assertRaises(ValueError):gram.make_tree(controls=gram.FoliageControls(length_variation=.3))
        with self.assertRaises(ValueError):gram.make_tree(profile='v09',controls=gram.FoliageControls())


if __name__=='__main__':unittest.main()
