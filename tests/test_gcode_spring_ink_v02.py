"""Selection, projected precedence and fine-brush execution regressions."""
import unittest
from copy import deepcopy
from dataclasses import replace
from benchmarks.integrated_330_v01 import spring_ink_v02 as v
from benchmarks.integrated_330_v01 import spring_physical_ink as s
from benchmarks.integrated_330_v01 import spring_panels_contact20 as n
from tests.test_gcode_spring_panels_contact20 import fragment,groups

class InkV02Tests(unittest.TestCase):
    def test_project_omitted_intermediate_preserves_order(self):
        self.assertEqual(v.project_edges([(0,1),(1,2)],{0,2}),[(0,2)])
    def test_scheduler_never_trades_precedence_for_batch(self):
        rr=[dict(ink=x) for x in ['LIGHT_INK','DARK_INK','LIGHT_INK']]
        g,r=v.schedule([0,1,2],rr,[(0,1),(1,2)],{0:0,1:1,2:2},10)
        self.assertEqual([e['source'] for x in g for e in x],[0,1,2]);self.assertTrue(r['batches_ended'][0]['below_soft_target'])
    def test_scheduler_groups_ready_ink_without_forcing(self):
        rr=[dict(ink=x) for x in ['LIGHT_INK','DARK_INK','LIGHT_INK']]
        g,_=v.schedule([0,1,2],rr,[],{0:0,1:1,2:2},10)
        self.assertEqual([e['source'] for x in g for e in x],[0,2,1])
    def test_fine_main_conflict_is_explicit_not_overridden(self):
        r=[dict(index=0,classification='fine',role='branch-contour',reason=''),dict(index=1,classification='main',role='',reason='')]
        self.assertEqual(v.resolve_fine(r,[(0,1)]),[0]);self.assertEqual(r[0]['classification'],'color')
    def test_fine_transform_preserves_pressure_xy_and_station_contacts(self):
        cfg=s.read(v.POLICY);p=s.profile(s.read(s.POLICY));fine=v.fine_profile(p,cfg)
        fs=[fragment(0)];g=groups(1);c,m=n.build(g,fs,p,s.read(s.POLICY),20);d=v.fine_transform(c,fine)
        self.assertEqual([x.xyz[:2] for x in c if x.kind=='move'],[x.xyz[:2] for x in d if x.kind=='move'])
        self.assertEqual([x.artistic_pressure for x in c],[x.artistic_pressure for x in d])
        self.assertEqual([x.xyz for x in c if x.action=='station_container_immersion'],[x.xyz for x in d if x.action=='station_container_immersion'])
        self.assertEqual(fine.paper_first_touch_for('ink','INK'),12)
    def test_corrupt_pressure_geometry_rejected(self):
        p=s.profile(s.read(s.POLICY));fs=[fragment(0)];g=groups(1);c,_=n.build(g,fs,p,s.read(s.POLICY),20)
        text=s.BANNER+s._serialize(c,p,s.PLAN_SHA,'test','offline_review')
        v.verify(text,c,p,g,fs)
        with self.assertRaises(ValueError):v.verify(text.replace('M0\n','',1),c,p,g,fs)
        air=s.air_projection(c,p);t=s.BANNER+s._serialize(air,p,s.PLAN_SHA,'test','offline_review')
        with self.assertRaises(ValueError):v.verify(t.replace('Z35.000000000','Z20.000000000',1),air,p,g,fs,True)

if __name__=='__main__':unittest.main()
