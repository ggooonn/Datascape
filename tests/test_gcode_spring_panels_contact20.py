"""Panel seam ownership, frozen gestures, independent budgets and station parity."""
from copy import deepcopy
import unittest
from datascape.gcode.models import Point, Stroke
from datascape.gcode.motion import Fragment
from benchmarks.integrated_330_v01 import spring_panels_contact20 as n
from benchmarks.integrated_330_v01 import spring_physical_ink as s


def fragment(index, xs=(310,311), pressure=(.4,.6)):
    stroke=Stroke('source-'+str(index),tuple(Point(x,400,p) for x,p in zip(xs,pressure)),'A','INK','ink')
    return Fragment(stroke,'FULL','SHARED',tuple((x,500) for x in xs))


def groups(count, slot='LIGHT_INK'):
    return [[dict(source=i,pass_index=0,ink=slot,id=f'{i}:pass0')] for i in range(count)]


class PanelContactTests(unittest.TestCase):
    def setUp(self):
        self.policy=s.read(s.POLICY); self.profile=s.profile(self.policy)

    def test_boundary_endpoints_have_single_ownership(self):
        self.assertEqual(n.owner_for_x([299,300]),'P1')
        self.assertEqual(n.owner_for_x([300,301]),'P2')
        self.assertEqual(n.owner_for_x([300,300]),'P1')
        self.assertEqual(n.owner_for_x([300-1e-9,300]),'P1')
        with self.assertRaises(ValueError):n.owner_for_x([299,301])
        with self.assertRaises(ValueError):n.owner_for_x([-1,2])

    def test_partition_preserves_pressure_and_global_P2(self):
        fs=[fragment(0,(299,300)),fragment(1,(300,301))]
        owners,report=n.partition(fs)
        self.assertEqual(owners,{0:'P1',1:'P2'})
        self.assertEqual(report['boundary_touching_sources'],2)
        self.assertEqual(report['sources'][1]['x_min'],300)
        self.assertEqual(fs[1].work_xy[0],(300,500))

    def test_filter_never_creates_new_connections(self):
        source=groups(3); filtered=n.panel_groups(source,{0:'P2',1:'P1',2:'P2'},'P2')
        self.assertEqual(filtered,[source[0],source[2]])
        self.assertEqual(len(filtered),2)
        self.assertEqual(n.panel_groups([source[0]+source[1]],{0:'P1',1:'P2'},'P2'),[source[1]])
        self.assertEqual(n.panel_groups([source[0]+source[1]],{0:'P1',1:'P2'},'P1P2'),[source[0]+source[1]])

    def test_only_exact_seam_endpoint_connections_can_separate(self):
        fs=[fragment(0,(299,300)),fragment(1,(300,301))]
        g=groups(2);joined=[g[0]+g[1]]
        audit=n.seam_connections(joined,{0:'P1',1:'P2'},fs)
        self.assertEqual(len(audit),1)
        self.assertFalse(audit[0]['canonical_geometry_or_pressure_changed'])
        with self.assertRaises(ValueError):n.seam_connections(joined,{0:'P1',1:'P2'},[fragment(0,(299,300)),fragment(1,(301,302))])

    def test_twenty_contacts_not_twenty_vertices(self):
        fs=[fragment(i) for i in range(21)]
        c,m=n.build(groups(21),fs,self.profile,self.policy,20)
        self.assertEqual(m['total_loads'],2)
        self.assertEqual(m['loads'][1]['before_event'],'20:pass0')
        self.assertEqual(m['loads'][1]['reasons'],['contact_limit'])
        self.assertEqual(m['maximum_contacts_before_reload'],20)
        self.assertEqual(sum(x.action=='initial_contact' for x in c),21)
        self.assertEqual(sum(x.artistic_pressure is not None for x in c),42)

    def test_distance_only_is_disabled_contact_trigger_not_large_fake_limit(self):
        fs=[fragment(i) for i in range(25)]
        _,m=n.build(groups(25),fs,self.profile,self.policy,None)
        self.assertEqual(m['total_loads'],1)
        self.assertIsNone(m['loads'][0]['contact_limit'])
        self.assertEqual(m['maximum_contacts_before_reload'],25)
        self.assertFalse(any('contact_limit' in row['reasons'] for row in m['loads']))

    def test_atomic_long_gesture_crossing_is_not_interrupted_by_reload(self):
        fs=[fragment(0,(10,590,10),(.4,.5,.6)),fragment(1)]
        commands,m=n.build(groups(2),fs,self.profile,self.policy,20)
        self.assertGreater(m['maximum_atomic_distance_overrun_mm'],350)
        self.assertEqual(m['loads'][1]['reasons'],['distance_limit'])
        active=False
        for c in commands:
            if c.action=='source_begin':active=True
            if c.action=='source_complete':active=False
            if active:self.assertNotIn(c.time_category,('station_transfer','station_handling'))

    def test_concentration_changes_still_wash_absorb_rewet(self):
        fs=[fragment(0),fragment(1)]
        g=groups(2);g[1][0]['ink']='DARK_INK'
        commands,m=n.build(g,fs,self.profile,self.policy,20)
        actions=[x['action'] for x in m['station_operations']]
        self.assertEqual(actions[:5],['pigment_load','wash','absorbent_contact','controlled_rewet','pigment_load'])
        self.assertEqual(m['concentration_changes'],1)
        dips=[c.xyz for c in commands if c.action=='station_container_immersion']
        self.assertTrue(all(p==(840,45,20) for p in dips))

    def test_new_builder_matches_PR34_at_twelve(self):
        fs=[fragment(i) for i in range(14)];g=groups(14)
        new,m=n.build(g,fs,self.profile,self.policy,12)
        old,oldm=s.build(g,fs,self.profile,self.policy,12)
        self.assertEqual(new,old)
        self.assertEqual(m,dict(oldm,maximum_atomic_contact_overrun=0))

    def test_joined_sources_remain_one_contact_and_all_pressures(self):
        fs=[fragment(0,(310,311)),fragment(1,(311,312))]
        joined=[groups(2)[0]+groups(2)[1]]
        commands,m=n.build(joined,fs,self.profile,self.policy,20)
        self.assertEqual(m['actual_paper_engagements'],1)
        self.assertEqual(sum(c.artistic_pressure is not None for c in commands),4)
        air=s.air_projection(commands,self.profile)
        self.assertTrue(all(c.xyz[2]==35 for c in air if c.kind=='move'))
        self.assertEqual([c.xyz[:2] for c in commands if c.kind=='move'],[c.xyz[:2] for c in air if c.kind=='move'])


if __name__=='__main__':unittest.main()
