"""Hybrid material, continuous gesture, container separation and numeric gates."""
from copy import deepcopy
from pathlib import Path
import unittest
import numpy as np
from shapely.geometry import LineString
from benchmarks.integrated_330_v01 import spring_physical_ink as s


class PhysicalInkTests(unittest.TestCase):
    def setUp(self):self.policy=s.read(s.POLICY)
    def test_confirmed_mounting_and_unchanged_PR32_pressure(self):
        p=s.profile(self.policy)
        self.assertEqual(p.paper_heights_for('ink','INK'),(10,20,15))
        self.assertEqual(p.data['brush_profiles']['ink']['knots'],[list(k) for k in s.RELATIVE_KNOTS])
        self.assertAlmostEqual(p.brush_for('ink','INK').work_z_for(.93),-.2)
        self.assertEqual(self.policy['backing_offset_added_mm'],0)
        self.assertFalse(p.data['machine']['target_config_installed'])
    def test_budgets_count_contacts_not_vertices_and_reset_both(self):
        b=s.HybridBudget();b.after('LIGHT_INK',100)
        self.assertEqual(b.slots['LIGHT_INK']['contacts'],1)
        for _ in range(11):b.after('LIGHT_INK',1)
        self.assertEqual(b.reasons('LIGHT_INK'),['contact_limit'])
        self.assertFalse(b.reasons('DARK_INK'));b.reset('LIGHT_INK')
        self.assertEqual(b.slots['LIGHT_INK'],dict(distance=0.,contacts=0))
    def test_distance_or_both_limits_and_atomic_overrun(self):
        b=s.HybridBudget(800,12)
        for _ in range(11):b.after('DARK_INK',70)
        self.assertFalse(b.reasons('DARK_INK'));b.after('DARK_INK',75)
        self.assertEqual(b.reasons('DARK_INK'),['distance_limit','contact_limit'])
        self.assertEqual(b.slots['DARK_INK']['distance'],845)
    def test_contact15_separate_configuration(self):
        b=s.HybridBudget(800,15)
        for _ in range(12):b.after('LIGHT_INK',1)
        self.assertFalse(b.reasons('LIGHT_INK'))
        with self.assertRaises(ValueError):s.HybridBudget(800,0)
    def test_container_independent_from_old_slope_and_selected_depth(self):
        p=s.profile(self.policy);b=s.RuntimeBuilder(p)
        s.container_operation(b,self.policy['new_water'],'wash')
        dip=[c for c in b.commands if c.action=='station_container_immersion']
        self.assertEqual(dip[0].xyz,(840,45,20))
        lip=next(c for c in b.commands if c.action=='station_container_lip_strip')
        self.assertEqual(lip.xyz,(775,45,25));self.assertEqual(lip.feed_mm_min,1500)
        self.assertFalse(any(c.xyz and c.xyz[2]==15 for c in b.commands))
        self.assertEqual(p.data['stations']['light_ink']['hardware_id'],'WELL_1')
        self.assertEqual(p.data['stations']['water']['kind'],'container')
        self.assertEqual(p.data['stations']['dark_ink']['hardware_id'],'WELL_2')
    def test_air_projection_all35_same_XY_no_pause(self):
        p=s.profile(self.policy);b=s.RuntimeBuilder(p);s.container_operation(b,self.policy['new_water'],'wash')
        b.commands.insert(0,s.Command('pause','gate'));a=s.air_projection(b.commands,p)
        self.assertFalse(any(c.kind=='pause' for c in a))
        original=[c.xyz[:2] for c in b.commands if c.kind=='move'];projected=[c.xyz[:2] for c in a if c.kind=='move']
        self.assertEqual(original,projected);self.assertTrue(all(c.xyz[2]==35 for c in a if c.kind=='move'))
    def test_sharp_structural_common_endpoint_allowed_without_reversal(self):
        rows=[dict(xy_mm=[[0,0],[1,0]],owner_id='tree'),dict(xy_mm=[[1,0],[.5,1]],owner_id='tree')]
        fs=[dict(family='tree',grammar='branch-contour',owner='tree')]*2
        events=[dict(source=i,ink='LIGHT_INK',pass_index=0,id=str(i)) for i in range(2)]
        shapes=[LineString(r['xy_mm']).buffer(.1) for r in rows]
        reason=s.join_reason(*events,rows,fs,self.policy,shapes)
        self.assertGreater(reason['turn_degrees'],90);self.assertEqual(reason['gap_mm'],0)
        groups,joins=s.gesture_groups(events,rows,fs,self.policy,shapes);self.assertEqual(len(groups),1)
    def test_foliage_and_intentional_gap_not_joined(self):
        rows=[dict(xy_mm=[[0,0],[1,0]],owner_id='tree'),dict(xy_mm=[[1.05,0],[1.5,1]],owner_id='tree')]
        fs=[dict(family='tree',grammar='branch-contour',owner='tree')]*2
        events=[dict(source=i,ink='LIGHT_INK',pass_index=0,id=str(i)) for i in range(2)]
        shapes=[LineString(r['xy_mm']).buffer(.1) for r in rows]
        self.assertIsNone(s.join_reason(*events,rows,fs,self.policy,shapes))
        rows[1]['xy_mm'][0]=[1,0];fs[1]=dict(family='tree',grammar='foliage-field',owner='tree')
        self.assertIsNone(s.join_reason(*events,rows,fs,self.policy,shapes))
    def test_added_passes_precede_protected_successors_and_no_dark_repeat(self):
        fs=[dict(ink='LIGHT_INK',family='A',depth_band='far',length_mm=5,allocation_score=1,A_light_parity=i%2,depth_m=10+i) for i in range(20)]
        events,r=s.events_schedule(fs,[(i,i+1) for i in range(19)],self.policy,True)
        rank={e['id']:i for i,e in enumerate(events)}
        self.assertGreater(r['extra_light_passes'],0);self.assertTrue(r['all_extra_passes_before_dependent_later_originals'])
        for e in events:
            if e['pass_index']:self.assertEqual(e['ink'],'LIGHT_INK')
        self.assertEqual(len({e['source'] for e in events if e['pass_index']==0}),20)
    def test_long_X300_crossing_source_is_one_engagement_and_not_reloaded_inside(self):
        from datascape.gcode.models import Point,Stroke
        from datascape.gcode.motion import Fragment
        st=Stroke('crossing-long',(Point(10,400,.5),Point(590,400,.5),Point(10,405,.5)),'A','INK','ink')
        f=Fragment(st,'FULL','SHARED',((10,500),(590,500),(10,495)))
        group=[[dict(source=0,pass_index=0,ink='LIGHT_INK',id='0:pass0')]]
        commands,m=s.build(group,[f],s.profile(self.policy),self.policy)
        begin=next(i for i,c in enumerate(commands) if c.action=='source_begin')
        end=next(i for i,c in enumerate(commands) if c.action=='source_complete')
        self.assertFalse(any(c.time_category=='station_handling' for c in commands[begin:end]))
        self.assertEqual(sum(c.action=='initial_contact' for c in commands),1)
        self.assertEqual(m['total_loads'],1)
        self.assertGreater(m['maximum_atomic_distance_overrun_mm'],350)
        values=[c.artistic_pressure for c in commands[begin:end] if c.artistic_pressure is not None]
        self.assertEqual(values,[.5,.5,.5])
    def test_calibration_audit_does_not_clamp_unknown_or_exceeded(self):
        from datascape.gcode.models import Point,Stroke
        from datascape.gcode.motion import Fragment
        st=Stroke('test',(Point(0,0,.5),Point(1,1,.93)),'D','INK','ink')
        f=Fragment(st,'FULL','SHARED',((0,900),(1,899)))
        row=s.compression_audit([f],self.policy)[0]
        self.assertEqual(row['status'],'small_brush_measured_range_missing');self.assertAlmostEqual(row['max_compression_mm'],10.2)
        self.policy['measured_max_compression_mm']=4
        row=s.compression_audit([f],self.policy)[0];self.assertEqual(row['status'],'exceeds_measured_range');self.assertFalse(row['pressure_clamped'])

if __name__=='__main__':unittest.main()
