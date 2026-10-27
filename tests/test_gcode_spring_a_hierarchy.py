"""A reassignment evidence, exact stage bounds and brush-specific reload regression."""
import unittest
from copy import deepcopy
from benchmarks.integrated_330_v01 import spring_a_hierarchy as a
from benchmarks.integrated_330_v01 import spring_physical_ink as s
from benchmarks.integrated_330_v01 import spring_panels_contact20 as n
from tests.test_gcode_spring_panels_contact20 import fragment,groups

class AHierarchyTests(unittest.TestCase):
    def test_only_global_distant_pair_released_original_and_parent_retained(self):
        from unittest.mock import patch
        rows=[dict(xy_mm=[[0,y],[1,y]],width_mm=.2) for y in (0,100,200)]
        fs=[dict(family='A',parent_contour=parent,source_id=str(i)) for i,parent in enumerate(('x','y','y'))]
        with patch.object(a.n,'frozen',return_value={'edges':[(0,2)]}):
            kept,strict,report=a.dependency_review(rows,fs,{0,1,2},[0,1,2])
        self.assertIn((0,2),kept);self.assertIn((1,2),kept);self.assertNotIn((0,1),kept)
        self.assertEqual(report['removed_original_protected_edges'],0)
        self.assertEqual(report['released_global_only_edges'],1)
    def test_stage_bound_two_and_three_are_distinct(self):
        self.assertEqual(a.stage_lower_bound([0,1,2],[(0,1),(1,2)],{2})['minimum_alternating_programs'],2)
        r=a.stage_lower_bound([0,1,2],[(0,1),(1,2)],{1})
        self.assertEqual(r['minimum_alternating_programs'],3);self.assertTrue(r['three_stage_feasible'])
    def test_four_stage_order_not_silently_forced_into_three(self):
        r=a.stage_lower_bound([0,1,2,3],[(0,1),(1,2),(2,3)],{1,3})
        self.assertEqual(r['minimum_alternating_programs'],4);self.assertFalse(r['three_stage_feasible'])
    def test_dark_A_and_far_and_protected_successors_rejected(self):
        cfg=s.read(a.POLICY)
        def row(i,**kw):
            d=dict(index=i,depth_band='middle',ink='LIGHT_INK',length_mm=20,neighbor_count=4,median_spacing_mm=1,center_xy=[350+i*10,500])
            d.update(kw);return d
        diag=[row(0,ink='DARK_INK'),row(1,depth_band='far'),row(2),row(3)]
        selected,_=a.choose(diag,{0,1,2,3},{2:{3}},{'near':2,'middle':2},cfg)
        self.assertEqual(selected,[3])
    def test_fine_material_resets_at_ten_contacts_without_wash(self):
        fs=[fragment(i) for i in range(11)];p=s.profile(s.read(s.POLICY));policy=s.read(s.POLICY);policy['distance_limit_mm']=450
        cmd,m=n.build(groups(11),fs,p,policy,10)
        self.assertEqual(m['total_loads'],2);self.assertEqual(m['concentration_changes'],0)
        self.assertEqual(m['maximum_contacts_before_reload'],10)
        self.assertEqual(m['loads'][1]['distance_limit_mm'],450)
        self.assertFalse(any(c.kind=='marker' and c.action=='wash' for c in cmd))
    def test_fine_distance_trigger_and_atomic_overrun(self):
        fs=[fragment(0,(310,590,310),(.4,.5,.6)),fragment(1)]
        p=s.profile(s.read(s.POLICY));policy=s.read(s.POLICY);policy['distance_limit_mm']=450
        cmd,m=n.build(groups(2),fs,p,policy,10)
        self.assertEqual(m['loads'][1]['reasons'],['distance_limit'])
        self.assertGreater(m['maximum_atomic_distance_overrun_mm'],100)
        self.assertEqual(sum(c.action=='initial_contact' for c in cmd),2)

if __name__=='__main__':unittest.main()
