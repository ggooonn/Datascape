"""Paper-only speed policy and acceleration-sensitive timing regressions."""
from copy import deepcopy
from dataclasses import replace
from math import sqrt
import unittest
from test_gcode_v03 import fixture, measured_test_profile, plan, ROOT
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import Builder, Materials, build_job
from datascape.gcode.production.exporter import _serialize, readback
from datascape.gcode.production.timing import estimate_commands, prepare_timing, estimate_prepared, CATEGORIES


def candidate():
    d=deepcopy(fixture().data)
    d['motion'].update(paper_approach_mm_min=5000,paper_contact_mm_min=1500,
                       paper_release_mm_min=1000,pressure_z_mm_min=2000,
                       wet_departure_mm_min=3000,wet_arrival_mm_min=3000)
    return Profile.from_dict(d)


class MotionPolicyTests(unittest.TestCase):
    def test_fast_approach_slow_contact_compression_release_then_fast_retraction(self):
        p=candidate();commands,m=build_job(p,plan()[0]['P1_INK'],'fixture')
        selected={c.action:c for c in commands if c.kind=='move' and c.source_id is not None}
        for action,z,feed in [('approach',1,5000),('initial_contact',0,1500),
                              ('release',0,1000),('paper_release_clearance',1,1000),('retract',10,6000)]:
            self.assertEqual((selected[action].xyz[2],selected[action].feed_mm_min),(z,feed))
        self.assertLessEqual(selected['pressure_variation'].feed_mm_min,1500)
        self.assertEqual([c.artistic_pressure for c in commands if c.artistic_pressure is not None],
                         [v.pressure for u in plan()[0]['P1_INK'] for f in u for v in f.stroke.points])
        text=_serialize(commands,p,'test','P1_INK','fixture')
        self.assertEqual(readback(text,commands,p,'fixture')['M0_count'],0)

    def test_paper_speeds_never_change_liquid_or_PURGE_contact_feeds(self):
        p=candidate();b=Builder(p);mat=Materials(b)
        mat.load('C1');mat.wash()
        contacts=[c for c in b.commands if c.action.startswith('station_') and c.action!='station_approach']
        self.assertTrue(contacts)
        self.assertTrue(all(c.feed_mm_min<=p.data['motion']['contact_mm_min'] for c in contacts))
        self.assertTrue(all(c.time_category=='station_handling' for c in contacts))

    def test_wet_departure_and_arrival_have_independent_distances_and_feeds(self):
        d=deepcopy(candidate().data);d['motion'].update(wet_departure_mm=10,wet_arrival_mm=20,wet_arrival_mm_min=2000)
        b=Builder(Profile.from_dict(d));b.xy((700,900),32,'wet_loaded')
        moves=[c for c in b.commands if c.action=='travel']
        self.assertEqual([c.xyz[0] for c in moves],[790,720,700])
        self.assertEqual([c.feed_mm_min for c in moves],[3000,9000,2000])
        b=Builder(Profile.from_dict(d));b.xy((785,900),32,'wet_loaded')
        self.assertEqual([c.xyz[0] for c in b.commands if c.action=='travel'],[795,795,785])

    def test_pressure_Z_cap_and_independent_readback_reject_tampered_IR(self):
        d=deepcopy(candidate().data);d['motion']['pressure_z_mm_min']=50
        p=Profile.from_dict(d);commands,_=build_job(p,plan()[0]['P1_COLOR'],'fixture')
        self.assertTrue(all(c.axis_velocity_mm_min[2]<=50+1e-8 for c in commands if c.action in ('draw','pressure_variation')))
        i=next(i for i,c in enumerate(commands) if c.action=='pressure_variation')
        commands[i]=replace(commands[i],feed_mm_min=100)
        with self.assertRaisesRegex(ValueError,'Z velocity'):
            readback(_serialize(commands,p,'test','job','fixture'),commands,p,'fixture')

    def test_categories_partition_the_real_IR_without_station_return_double_count(self):
        p=candidate();commands,m=build_job(p,plan()[0]['P1_COLOR'],'fixture')
        t=m['timing'];self.assertEqual(set(t['commanded_feed_seconds_by_category']),set(CATEGORIES))
        self.assertAlmostEqual(t['commanded_feed_seconds'],m['commanded_feed_subtotal_seconds'])
        self.assertAlmostEqual(t['acceleration_sensitive_seconds'],sum(t['acceleration_sensitive_seconds_by_category'].values()))
        self.assertGreater(t['commanded_feed_seconds_by_category']['station_transfer'],0)
        self.assertGreater(t['commanded_feed_seconds_by_category']['paper_engagement'],0)
        self.assertFalse(t['verified_physical_time'])

    def test_new_fields_boundary_and_calibration_evidence_are_mandatory(self):
        for key in ('paper_approach_mm_min','paper_contact_mm_min','paper_release_mm_min','wet_arrival_mm','wet_arrival_mm_min'):
            d=deepcopy(candidate().data);d['motion'][key]=None
            self.assertTrue(any(key in s for s in Profile.from_dict(d).issues('fixture',['C1'])))
        d=deepcopy(candidate().data);d['motion']['paper_approach_mm']=0
        self.assertTrue(Profile.from_dict(d).issues('fixture',['C1']))
        p=measured_test_profile();self.assertTrue(p.evidence_passed('paper_contact'))
        d=deepcopy(p.data);d['motion']['paper_approach_mm_min']+=1
        self.assertFalse(Profile.from_dict(d).evidence_passed('paper_contact'))
        self.assertTrue(Profile.load(ROOT/'config/plotter_v03/profile.unmeasured.json').issues('painting'))


class TimingTests(unittest.TestCase):
    def builder(self):
        d=deepcopy(candidate().data);d['machine'].update(start_work_xyz=[0,0,10],axis_acceleration_mm_s2=[1,1,1])
        return Builder(Profile.from_dict(d))

    def test_analytic_trapezoid_collinear_split_and_reversal(self):
        b=self.builder();b.move((100,0,10),60,'travel')
        self.assertAlmostEqual(b.result()['timing']['acceleration_sensitive_seconds'],101)
        b=self.builder();b.move((50,0,10),60,'travel');b.marker('source_begin');b.move((100,0,10),60,'travel')
        t=b.result()['timing'];self.assertAlmostEqual(t['acceleration_sensitive_seconds'],101)
        self.assertAlmostEqual(t['stop_each_segment_seconds'],102)
        b=self.builder();b.move((100,0,10),60,'travel');b.move((0,0,10),60,'travel')
        self.assertAlmostEqual(b.result()['timing']['acceleration_sensitive_seconds'],202)

    def test_short_move_cannot_instantly_reach_programmed_feed(self):
        b=self.builder();b.move((.01,0,10),6000,'travel')
        t=b.result()['timing'];self.assertAlmostEqual(t['acceleration_sensitive_seconds'],2*sqrt(.01))
        self.assertGreater(t['acceleration_sensitive_seconds'],t['commanded_feed_seconds'])

    def test_dwell_is_a_stop_and_zero_move_is_not_a_stop(self):
        b=self.builder();b.move((50,0,10),60,'travel');b.move((50,0,10),60,'travel');b.move((100,0,10),60,'travel')
        self.assertAlmostEqual(b.result()['timing']['acceleration_sensitive_seconds'],101)
        b=self.builder();b.move((50,0,10),60,'travel');b.dwell(2,'test_dwell');b.move((100,0,10),60,'travel')
        self.assertAlmostEqual(b.result()['timing']['acceleration_sensitive_seconds'],104)

    def test_junction_deviation_and_projected_axis_acceleration_change_time(self):
        b=self.builder();b.move((100,0,10),6000,'travel');b.move((100,100,10),6000,'travel')
        blocks=prepare_timing(b.commands,b.profile);m=deepcopy(b.m)
        small=estimate_prepared(blocks,m);m['junction_deviation_mm']=1
        large=estimate_prepared(blocks,m)
        self.assertLess(large['acceleration_sensitive_seconds'],small['acceleration_sensitive_seconds'])
        self.assertGreaterEqual(small['stop_each_segment_seconds'],small['acceleration_sensitive_seconds'])
        m['axis_acceleration_mm_s2']=[.1,.1,.1]
        self.assertGreater(estimate_prepared(blocks,m)['acceleration_sensitive_seconds'],large['acceleration_sensitive_seconds'])

    def test_feed_only_comparison_matches_fresh_build_and_preserves_geometry(self):
        from datascape.gcode.production.motion_comparison import scenarios
        p=candidate();units=plan()[0]['P1_COLOR'];commands,_=build_job(p,units,'fixture')
        blocks=prepare_timing(commands,p)
        for label,motion in scenarios(p.data['motion']):
            d=deepcopy(p.data);d['motion']=motion;q=Profile.from_dict(d)
            fresh,m=build_job(q,units,'fixture')
            self.assertEqual([(c.xyz,c.artistic_pressure) for c in fresh],
                             [(c.xyz,c.artistic_pressure) for c in commands],label)
            t=estimate_prepared(blocks,p.data['machine'],motion)
            self.assertAlmostEqual(t['commanded_feed_seconds'],m['timing']['commanded_feed_seconds'],msg=label)
            self.assertAlmostEqual(t['acceleration_sensitive_seconds'],m['timing']['acceleration_sensitive_seconds'],msg=label)


if __name__=='__main__':unittest.main()
