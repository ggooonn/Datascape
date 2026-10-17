"""Pad hierarchy, rigid fan units, physical forks and terminal controls."""
from collections import defaultdict
import unittest
import numpy as np
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_pattern as pattern
from datascape.vegetation import tree_rhythm as rhythm


def signature(marks):return [(m.key,m.xy.tolist(),m.width,m.part,m.parent) for m in marks]
def body(t):return [m for m in t.marks if m.part!='foliage-field']
def leaves(t):return [m for m in t.marks if m.part=='foliage-field']
def units(t):
    out=defaultdict(list)
    for m in leaves(t):out[m.key.rsplit('-',1)[0]].append(m)
    return out


class RhythmTests(unittest.TestCase):
    def test_v05_control_is_exact(self):
        a=rhythm.make_tree(version='v05');b=pattern.make_tree()
        self.assertEqual(signature(a.marks),signature(b.marks))
        self.assertEqual(a.structure,b.structure)

    def test_density_changes_whole_units_without_changing_body(self):
        a=rhythm.make_tree(version='v05');b=rhythm.make_tree(version='density')
        self.assertEqual(signature(body(a)),signature(body(b)))
        aa=units(a);bb=units(b)
        self.assertLess(len(bb),len(aa));self.assertTrue(set(bb)<=set(aa))
        self.assertTrue(all(2<=len(v)<=5 for v in bb.values()))
        for k,v in bb.items():self.assertEqual([m.key for m in aa[k]],[m.key for m in v])

    def test_every_unit_uses_one_rigid_rotation_within_ten_degrees(self):
        a=units(rhythm.make_tree(version='v05'));b=rhythm.make_tree(version='density')
        bb=units(b)
        for u in b.canopy_diagnostics['units']:
            if not u['retained']:continue
            pivot=np.array(u['pivot_mm']);angle=u['rotation_deg'];self.assertLessEqual(abs(angle),8)
            for before,after in zip(a[u['key']],bb[u['key']]):
                expected=pivot+old.rotate(before.xy-pivot,np.deg2rad(angle))
                np.testing.assert_allclose(expected,after.xy,atol=1e-10)
                self.assertAlmostEqual(old.length(before.xy),old.length(after.xy),places=10)

    def test_pad_hierarchy_preserves_core_more_than_edge(self):
        for f in old.FAMILIES:
            t=rhythm.make_tree(f,height=60 if f=='understory' else 95)
            pads=t.canopy_diagnostics['pads'];states={p['state'] for p in pads}
            self.assertTrue({'dense','light','open'}<=states)
            rate=lambda area:sum(p[area]['retained'] for p in pads)/max(1,sum(p[area]['available'] for p in pads))
            self.assertGreater(rate('core'),rate('edge'))
            d=t.canopy_diagnostics;fraction=d['retained_foliage_paths']/d['source_foliage_paths']
            self.assertGreater(fraction,.70);self.assertLess(fraction,.95)

    def test_remnant_is_one_local_operator_and_not_random_extra_marks(self):
        a=rhythm.make_tree();b=rhythm.make_tree(remnant_pad=True)
        rem=[p for p in b.canopy_diagnostics['pads'] if p['state']=='remnant']
        self.assertEqual(len(rem),1);self.assertLessEqual(rem[0]['retained_units'],4)
        self.assertEqual(signature(body(a)),signature(body(b)))
        self.assertTrue(set(units(b))<=set(units(a)))
        self.assertEqual(a.structure,b.structure)

    def test_growth_refinement_preserves_axis_anchors_and_density_foliage(self):
        a=rhythm.make_tree(version='density');b=rhythm.make_tree()
        self.assertEqual(signature(leaves(a)),signature(leaves(b)))
        self.assertEqual(a.structure['axis_nodes_mm'],b.structure['axis_nodes_mm'])
        self.assertEqual(a.structure['branch_terminals_mm'],b.structure['branch_terminals_mm'])
        members=b.structure['members'];axis=np.concatenate([p for k,p in members.items() if k.startswith('axis/')])
        for k,p in members.items():
            if k.startswith('arm-'):self.assertLess(np.linalg.norm(axis-p[0],axis=1).min(),1e-8)

    def test_terminal_states_are_real_geometry_and_vary_across_objects(self):
        found=set()
        for f in old.FAMILIES:
            t=rhythm.make_tree(f)
            for item in t.structure['terminal_behavior']:
                found.add(item['state']);p=np.array(t.structure['members'][item['key']]);dy=p[-1,1]-p[-2,1]
                if item['state']=='droop':self.assertGreater(dy,0)
                if item['state']=='rise':self.assertLess(dy,0)
                if item['state']=='level':self.assertLess(abs(dy),.02)
        self.assertEqual(found,{'rise','level','droop'})

    def test_variable_body_spacing_and_real_fork_collars(self):
        t=rhythm.make_tree();w=t.structure['contour_spacing']
        self.assertGreater(w['maximum_side_spacing_mm'],w['minimum_side_spacing_mm']*3)
        self.assertEqual(len(w['fork_fractions']),3)
        self.assertGreater(sum(m.part=='bark-grain' for m in t.marks),0)
        self.assertTrue(all(np.isfinite(m.xy).all() and np.linalg.norm(m.xy[-1]-m.xy[0])>0 for m in t.marks))

    def test_middle_removes_surface_detail_and_keeps_same_unit_pattern(self):
        a=rhythm.make_tree();b=rhythm.make_tree(depth='middle')
        self.assertEqual(signature(leaves(a)),signature(leaves(b)))
        self.assertFalse(any(m.part in ('twig','bark-grain') for m in b.marks))

    def test_seasons_leave_body_and_branch_states_identical(self):
        a=rhythm.make_tree();b=rhythm.make_tree(season='summer');c=rhythm.make_tree(season='winter')
        self.assertEqual(signature(body(a)),signature(body(b)));self.assertEqual(signature(body(a)),signature(body(c)))
        self.assertEqual(a.structure,b.structure);self.assertEqual(a.structure,c.structure)
        self.assertGreater(len(leaves(b)),len(leaves(a)));self.assertEqual(len(leaves(c)),0)

    def test_shared_legacy_visibility_policy_and_owner_provenance(self):
        a=rhythm.make_tree(version='v05');b=rhythm.make_tree(version='density')
        points=np.array([[80,80],[90,100],[110,70],[90,149]],float)
        np.testing.assert_array_equal(old.foreground_gate(points,a),old.foreground_gate(points,b))
        trees=[rhythm.make_tree(root=(70+i*15,140+i*5),height=70,seed=30+i,identity=f't{i}') for i in range(3)]
        marks,stats=old.overlap(trees);self.assertGreater(stats['removed_mm'],0)
        rr=rhythm.vector_records(marks,trees)
        self.assertTrue(all(x['catalog_version']=='0.6' and x['ground_visibility_status']=='unresolved' for x in rr))

    def test_call_order_and_invalid_parameters(self):
        a=rhythm.make_tree(seed=9);rhythm.make_tree(seed=13);b=rhythm.make_tree(seed=9)
        self.assertEqual(signature(a.marks),signature(b.marks))
        self.assertEqual(a.canopy_diagnostics,b.canopy_diagnostics)
        for kwargs in [dict(version='unknown'),dict(rotation_limit_deg=11),dict(rotation_limit_deg=-1),dict(pad_retention={'dense':1,'light':.4,'open':.8})]:
            with self.assertRaises(ValueError):rhythm.make_tree(**kwargs)


if __name__=='__main__':unittest.main()
