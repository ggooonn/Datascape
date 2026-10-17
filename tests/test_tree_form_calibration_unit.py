"""Scale-calibration, structural W and local shallow-plane contracts."""
from collections import defaultdict
import json,unittest
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_form_calibration as gram
from datascape.vegetation import tree_group_review as previous
from datascape.vegetation import tree_spatial_groups as groups
from datascape.vegetation import tree_catalog as old
from datascape.strokes.vector import resample


def body(t):return [m for m in t.marks if m.part!='foliage-field']
def leaves(t):return [m for m in t.marks if m.part=='foliage-field']
def sig(marks):return [(m.key,m.xy.tolist(),m.width,m.part,m.parent) for m in marks]


class FormCalibrationTests(unittest.TestCase):
    def test_current_controls_delegate_exactly_without_upgrading_records(self):
        for form in 'PBU':
            a=gram.make_tree(form,profile='current',root=(100,170),height=45)
            b=previous.make_tree(gram.FORMS[form],root=(100,170),height=45)
            self.assertEqual(sig(a.marks),sig(b.marks));self.assertEqual(a.structure,b.structure)
            self.assertEqual(gram.vector_records(a.marks,[a]),previous.vector_records(b.marks,[b]))

    def test_small_density_and_existing_body_are_preserved(self):
        for form in 'PBU':
            a=gram.make_tree(form,height=22,profile='current');b=gram.make_tree(form,height=22)
            self.assertEqual([m.key for m in a.marks],[m.key for m in b.marks])
            for aa,bb in zip(a.marks,b.marks):np.testing.assert_allclose(aa.xy,bb.xy,atol=1e-10)
        a=gram.make_tree('P',profile='current');b=gram.make_tree('P')
        self.assertEqual(sig(body(a)),sig(body(b)))

    def test_budget_gain_is_family_and_scale_specific_with_actual_counts_recorded(self):
        self.assertEqual(gram.density_gain('P',95),2)
        self.assertNotEqual(gram.density_gain('P',95),gram.density_gain('B',95))
        for form in 'PBU':
            a=gram.make_tree(form,height=95,profile='current');b=gram.make_tree(form,height=95)
            self.assertGreater(len(leaves(b)),len(leaves(a)))
            aa={m.key:m for m in leaves(a)};bb={m.key:m for m in leaves(b)}
            self.assertTrue(set(aa)<=set(bb))
            for key in aa:np.testing.assert_allclose(aa[key].xy,bb[key].xy,atol=1e-10)
            opened=[p for p in b.canopy_diagnostics['pads'] if p['state']=='open']
            self.assertTrue(all(p['unit_cap']==p['base_cap'] for p in opened))
        self.assertGreater(len(leaves(gram.make_tree('P',height=130))),len(leaves(gram.make_tree('P',height=95))))

    def test_units_stay_light_with_physical_lengths_and_gap(self):
        for form,height in [('P',95),('B',45),('U',45),('W',95)]:
            t=gram.make_tree(form,height=height);uu=defaultdict(list)
            for m in leaves(t):
                uu[m.key.rsplit('-',1)[0]].append(m);self.assertGreaterEqual(old.length(m.xy),2.8-1e-9)
            self.assertTrue(all(1<=len(mm)<=3 for mm in uu.values()))
            self.assertTrue(all(abs(u['rotation_deg'])<=8 for u in t.canopy_diagnostics['units']))
            dense=[]
            for mm in uu.values():
                q=np.concatenate([resample(m.xy,.06) for m in mm])
                if dense:self.assertGreaterEqual(float(cKDTree(np.concatenate(dense)).query(q)[0].min()),1.27)
                dense.append(q)

    def test_stem_share_and_foliage_vigor_are_separate_inputs(self):
        a=gram.make_tree('B');long=gram.make_tree('B',growth_controls=gram.GrowthControls(stem_ratio=1.3))
        self.assertGreater(old.length(long.structure['members']['axis/0']),old.length(a.structure['members']['axis/0']))
        aa={m.key:m for m in leaves(a)};bb={m.key:m for m in leaves(long)}
        self.assertEqual(set(aa),set(bb))
        for key in aa:np.testing.assert_allclose(bb[key].xy-aa[key].xy,np.tile([0,-95*.30*.3],(len(aa[key].xy),1)),atol=1e-9)
        bare=gram.make_tree('B',growth_controls=gram.GrowthControls(vigor=0))
        self.assertEqual(sig(body(a)),sig(body(bare)));self.assertEqual(len(leaves(bare)),0)

    def test_terminal_droop_does_not_create_a_hanging_architecture(self):
        a=gram.make_tree('B');b=gram.make_tree('B',architecture='terminal-droop')
        self.assertEqual(a.structure['branch_terminals_mm'],b.structure['branch_terminals_mm'])
        self.assertEqual(sig(leaves(a)),sig(leaves(b)))
        self.assertTrue(all(t['downward_tangent'] for t in b.structure['terminal_behavior']))
        self.assertFalse(any(k.startswith('pendant-') for k in b.structure['members']))

    def test_w_has_actual_attached_descending_secondaries(self):
        t=gram.make_tree('W');s=t.structure;pendants={k:np.array(p) for k,p in s['members'].items() if k.startswith('pendant-')}
        self.assertGreaterEqual(len(pendants),6)
        for key,p in pendants.items():
            arm=np.array(s['members']['arm-'+key.split('-')[1]])
            self.assertLess(np.linalg.norm(arm-p[0],axis=1).min(),1e-8);self.assertGreater(p[-1,1]-p[0,1],0)
        self.assertTrue(all(m.parent in pendants for m in leaves(t)))
        self.assertEqual(t.family,'broadleaf');self.assertEqual(s['catalog_form'],'W');self.assertTrue(s['experimental_form'])

    def test_group_population_is_shared_but_roots_and_depth_scales_change(self):
        for kind,n in [('two',2),('three',3),('five',5),('eight',8)]:
            mm=groups.members(kind);self.assertEqual(len(mm),n)
            array=groups.project(mm,'array');space=groups.project(mm,'spatial')
            self.assertEqual({x['member']['identity'] for x in array},{x['member']['identity'] for x in space})
            self.assertEqual(len(set(x['root'][1] for x in array)),1)
            self.assertGreater(len(set(x['root'][1] for x in space)),1)
            self.assertEqual([x['member']['depth'] for x in space],sorted([x.depth for x in mm],reverse=True))
            self.assertTrue(all(x['depth_scale']==1-.3*x['member']['depth'] for x in space))
            self.assertAlmostEqual(min(x['root'][0] for x in array),min(x['root'][0] for x in space))
            self.assertAlmostEqual(max(x['root'][0] for x in array),max(x['root'][0] for x in space))

    def test_groups_have_a_core_perimeter_and_broken_serial_spacing(self):
        five=groups.members('five');self.assertTrue({'core','edge','anchor'}<=set(x.role for x in five))
        space=groups.project(groups.members('eight'),'spatial')
        dx=np.diff(sorted(x['root'][0] for x in space));self.assertGreater(np.ptp(dx),10)
        q=np.array([x['root'] for x in groups.project(groups.members('three'),'spatial')])
        self.assertGreater(abs(np.linalg.det(np.vstack([q[1]-q[0],q[2]-q[0]]))),1)

    def test_mixed_exports_keep_form_carrier_and_unresolved_ground(self):
        ts=[gram.make_tree(f,height=45,identity=f) for f in 'PBUW'];mm=[m for t in ts for m in t.marks]
        rr=gram.vector_records(mm,ts);self.assertEqual(rr,json.loads(json.dumps(rr)))
        self.assertEqual([r['draw_order'] for r in rr],list(range(len(rr))))
        self.assertEqual(set(r['catalog_form'] for r in rr),set('PBUW'))
        self.assertTrue(all(r['ground_visibility_status']=='unresolved' and not r['physical_plotting_validated'] for r in rr))

    def test_call_order_determinism_and_finite_open_geometry(self):
        a=gram.make_tree('W',seed=5);gram.make_tree('W',seed=7);b=gram.make_tree('W',seed=5)
        self.assertEqual(sig(a.marks),sig(b.marks))
        for m in a.marks:self.assertTrue(np.isfinite(m.xy).all());self.assertGreater(old.length(m.xy),0)

    def test_invalid_controls_and_unsupported_w_damage_are_explicit(self):
        for kw in [dict(form='X'),dict(height=12),dict(growth_controls=gram.GrowthControls(vigor=-1)),
                   dict(profile='current',growth_controls=gram.GrowthControls(stem_ratio=1.2)),
                   dict(form='W',accent='broken-top'),dict(form='W',profile='current'),
                   dict(design_width_mm=0),dict(clear_gap_mm=float('nan'))]:
            with self.assertRaises(ValueError):gram.make_tree(**kw)
        with self.assertRaises(ValueError):groups.project(groups.members(),depth_size=1)


if __name__=='__main__':unittest.main()
