"""v08 catalog contracts: frozen pine, scale budgets and explicit B/U knobs."""
from collections import defaultdict
from dataclasses import replace
import json
import unittest
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_group_review as gram
from datascape.vegetation import tree_plot_scale as pine
from datascape.vegetation import tree_catalog as old
from datascape.strokes.vector import resample


def sig(marks):return [(m.key,m.xy.tolist(),m.width,m.part,m.parent) for m in marks]
def leaves(t):return [m for m in t.marks if m.part=='foliage-field']
def body(t):return [m for m in t.marks if m.part!='foliage-field']
def units(t):
    out=defaultdict(list)
    for m in leaves(t):out[m.key.rsplit('-',1)[0]].append(m)
    return out


class GroupReviewTests(unittest.TestCase):
    def test_pine_remains_exact_at_all_review_sizes(self):
        for h,p in [(95,'redirected'),(45,'stooped'),(22,'upright')]:
            a=pine.make_tree(height=h,posture=p);b=gram.make_tree('hero-pine',height=h,posture=p)
            self.assertEqual(sig(a.marks),sig(b.marks));self.assertEqual(a.structure,b.structure)
            self.assertEqual(a.canopy_diagnostics,b.canopy_diagnostics)
            self.assertEqual(pine.vector_records(a.marks,[a]),gram.vector_records(b.marks,[b]))
        with self.assertRaises(ValueError):gram.make_tree('hero-pine',controls=gram.FoliageControls())

    def test_bu_budgets_are_scale_sensitive_and_light(self):
        for f in gram.FAMILY_CAPS:
            counts=[]
            for h in [95,45,22]:
                t=gram.make_tree(f,height=h);d=t.canopy_diagnostics;counts.append(d['retained_units'])
                self.assertLess(len(leaves(t)),d['source_foliage_paths']*.25)
                n=[len(u) for u in units(t).values()]
                self.assertTrue(all(1<=x<=3 for x in n));self.assertGreater(sum(x<=2 for x in n),len(n)*.85)
                self.assertTrue(all(old.length(m.xy)>=2.8-1e-9 for m in leaves(t)))
                self.assertLessEqual(max(abs(u['rotation_deg']) for u in d['units']),8)
                self.assertTrue(all(p['retained_units']<=p['unit_cap'] for p in d['pads']))
            self.assertGreater(counts[0],counts[1]);self.assertGreater(counts[1],counts[2])

    def test_geometric_clearance_is_independently_verified_for_bu(self):
        for f,h in [('broadleaf',95),('understory',45),('broadleaf',22),('understory',22)]:
            t=gram.make_tree(f,height=h);dense=[];best=float('inf')
            for marks in units(t).values():
                p=np.concatenate([resample(m.xy,.06) for m in marks])
                if dense:best=min(best,float(cKDTree(np.concatenate(dense)).query(p)[0].min()))
                dense.append(p)
            self.assertGreaterEqual(best,1.3-.03)

    def test_budget_and_occupancy_inputs_do_not_deform_the_body(self):
        a=gram.make_tree();z=gram.make_tree(controls=gram.FoliageControls(unit_budget_scale=0))
        self.assertEqual(sig(body(a)),sig(body(z)));self.assertEqual(len(leaves(z)),0)
        q=gram.make_tree(controls=gram.FoliageControls(pad_occupancy=(1,1,0,0)))
        self.assertEqual(sig(body(a)),sig(body(q)))
        self.assertTrue(all(p['retained_units']==0 for p in q.canopy_diagnostics['pads'] if p['state']=='open'))
        twice=gram.make_tree(controls=gram.FoliageControls(unit_budget_scale=2))
        a_caps={p['key']:p['unit_cap'] for p in a.canopy_diagnostics['pads']}
        self.assertTrue(all(p['unit_cap']==2*a_caps[p['key']] for p in twice.canopy_diagnostics['pads']))
        self.assertLess(twice.canopy_diagnostics['retained_units'],2*a.canopy_diagnostics['retained_units'])

    def test_touch_length_and_rotation_are_exposed_but_physically_constrained(self):
        settings=gram.FoliageControls(touch_probabilities=(1,0,0),rotation_limit_deg=0,leaf_length_scale=.5)
        a=gram.make_tree(controls=settings);b=gram.make_tree(controls=replace(settings,leaf_length_scale=1.5))
        self.assertTrue(all(len(u)==1 for u in units(a).values()))
        self.assertTrue(all(u['rotation_deg']==0 for u in a.canopy_diagnostics['units']))
        self.assertEqual(sig(body(a)),sig(body(b)))
        common=set(m.key for m in leaves(a))&set(m.key for m in leaves(b));self.assertTrue(common)
        aa={m.key:old.length(m.xy) for m in leaves(a)};bb={m.key:old.length(m.xy) for m in leaves(b)}
        self.assertTrue(any(bb[k]>aa[k]+.1 for k in common));self.assertTrue(all(x>=2.8-1e-9 for x in aa.values()))

    def test_understory_basal_stems_share_the_physical_lod(self):
        t=gram.make_tree('understory',height=22)
        basal=[m for m in t.marks if m.key.startswith('basal-')]
        self.assertEqual(len(basal),2);self.assertTrue(all('/single' in m.key for m in basal))
        self.assertTrue(all(m.owner==t.identity for m in basal))
        self.assertEqual(set(k for k in t.structure['members'] if k.startswith('basal-')),{'basal-0','basal-1'})

    def test_upright_stooped_and_redirected_keep_structural_history(self):
        found=set()
        for f in gram.FAMILY_CAPS:
            for p in ['upright','stooped','redirected']:
                t=gram.make_tree(f,posture=p,height=45)
                self.assertEqual(t.structure['posture'],p)
                self.assertTrue(2<=t.structure['member_count']<=4)
                self.assertTrue(all(a['opposite_side_crossings']==0 for a in t.structure['contour_audit'].values()))
                found.update(a['state'] for a in t.structure['terminal_behavior'])
        self.assertEqual(found,{'rise','level','droop'})

    def test_mixed_overlap_keeps_owner_versions_and_reports_real_cuts(self):
        trees=[gram.make_tree(f,root=(80+12*i,145+8*i),height=60-10*i,identity=f,seed=20+i)
               for i,f in enumerate(old.FAMILIES)]
        marks,stats=old.overlap(trees);self.assertGreater(stats['removed_mm'],0)
        rr=gram.vector_records(marks,trees)
        self.assertEqual(json.loads(json.dumps(rr)),rr)
        self.assertEqual([r['draw_order'] for r in rr],list(range(len(rr))))
        for r in rr:
            self.assertEqual(r['catalog_version'],'0.7' if r['catalog_family']=='hero-pine' else '0.8')
            self.assertEqual(r['ground_visibility_status'],'unresolved');self.assertFalse(r['physical_plotting_validated'])
        with self.assertRaises(ValueError):old.overlap([trees[0],trees[0]])

    def test_controls_preserve_legacy_provenance_exactly(self):
        t=pine.make_tree('broadleaf',profile='v06')
        self.assertEqual(pine.vector_records(t.marks,[t]),gram.vector_records(t.marks,[t]))

    def test_invalid_controls_are_rejected(self):
        for kw in [dict(unit_budget_scale=-1),dict(pad_occupancy=(1,)),dict(leaf_length_scale=0),
                   dict(touch_probabilities=(.5,.5,.5)),dict(design_width_mm=0),dict(clear_gap_mm=0),dict(rotation_limit_deg=11)]:
            with self.assertRaises(ValueError):gram.make_tree(controls=gram.FoliageControls(**kw))


if __name__=='__main__':unittest.main()
