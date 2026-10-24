"""Post-benchmark Spring mapping, relative clearance and numeric review tests."""
from copy import deepcopy
from dataclasses import replace
from math import dist
from pathlib import Path
import os
import unittest

from benchmarks.integrated_330_v01 import spring_large_baegunmo as final
from benchmarks.integrated_330_v01 import paper_reference_1500 as benchmark
from benchmarks.integrated_330_v01.spring_pipeline import require_unified_profile
from benchmarks.integrated_330_v01.numeric_review import BANNER
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import serialized_feed_cap
from test_gcode_v03 import plan as fixture_plan

ROOT=Path(__file__).resolve().parents[1]


class LargeBaegunmoSpringTests(unittest.TestCase):
    def test_relative_clearances_and_exact_candidate_knots(self):
        p=final.profile(ROOT);self.assertEqual(p.paper_heights_for('ink','INK'),(10,20,15))
        self.assertEqual(p.paper_heights_for('color','A2'),(10,20,15))
        for medium,slot in [('ink','INK'),('color','A2')]:
            b=p.brush_for(medium,slot)
            for pressure,compression in final.COMPRESSION_KNOTS:
                self.assertAlmostEqual(-b.z_for(pressure),compression)
                self.assertAlmostEqual(b.work_z_for(pressure),10-compression)
            self.assertAlmostEqual(b.work_z_for(.93),-.2)
            self.assertEqual(b.work_z_for(1),-2)
            for pressure in (-.01,1.01):
                with self.assertRaises(ValueError):b.work_z_for(pressure)

    def test_ink_and_color_reference_and_curve_are_independent(self):
        d=deepcopy(final.profile(ROOT).data)
        d['brush_profiles']['color']['paper_first_touch_z_mm']=12
        d['motion']['paper_contact_z_range']=[-2,12]
        p=Profile.from_dict(d)
        self.assertEqual(p.paper_heights_for('color','A2'),(12,22,17))
        self.assertEqual(p.paper_heights_for('ink','INK'),(10,20,15))
        self.assertEqual(p.brush_for('color','A2').work_z_for(1),0)
        jobs,_=fixture_plan();commands,_=final.build(p,jobs['P1_COLOR'])
        self.assertTrue(all(c.xyz[2]==22 for c in commands if c.action=='retract'))
        self.assertTrue(all(c.xyz[2]==17 for c in commands if c.action=='approach'))
        self.assertTrue(all(c.xyz[2]==12 for c in commands if c.action=='initial_contact'))

    def test_stations_machine_coordinates_and_older_curve_not_shifted(self):
        p=final.profile(ROOT);old=benchmark.profile(ROOT)
        self.assertEqual(p.data['stations'],old.data['stations'])
        for key in ('g54_to_machine_xyz','start_work_xyz','machine_bounds_xyz','axis_max_rate_mm_min','axis_acceleration_mm_s2','target_config_sha256'):
            self.assertEqual(p.data['machine'][key],old.data['machine'][key])
        self.assertEqual(old.brush_for('ink','INK').z_for(1),-8)
        self.assertEqual(p.data['stations']['ink']['lip_stripping']['measured_contact_xyz'],[815,458,20])
        self.assertEqual(p.data['stations']['water']['lip_stripping']['measured_contact_xyz'],[815,298,20])
        self.assertEqual(p.data['stations']['A2']['liquid_reference_z']-p.data['stations']['A2']['immersion_mm'],5)

    def test_material_default_optional_and_runner_contract(self):
        p=final.profile(ROOT);require_unified_profile(p)
        self.assertEqual(p.data['material']['ink_reload_mm'],1500)
        self.assertEqual(p.data['material']['color_reload_mm'],1000)
        require_unified_profile(final.profile(ROOT,2000))
        with self.assertRaises(ValueError):final.profile(ROOT,1200)
        d=deepcopy(p.data);d['motion']['paper_hover_mm']=15
        with self.assertRaises(ValueError):require_unified_profile(Profile.from_dict(d))

    def test_shorter_reload_variant_changes_only_intervals_and_identity(self):
        old=deepcopy(final.profile(ROOT).data);new=deepcopy(final.profile(ROOT,1100,700).data)
        require_unified_profile(final.profile(ROOT,1100,700))
        for d in (old,new):
            for k in ('profile_id','notes'):d.pop(k)
            for k in ('ink_reload_mm','color_reload_mm'):d['material'].pop(k)
        self.assertEqual(old,new)
        for pair in ((1100,1000),(1500,700)):
            with self.assertRaises(ValueError):final.profile(ROOT,*pair)

    def test_shorter_intervals_trigger_reload_at_original_stroke_boundaries(self):
        from datascape.gcode.models import Point, Stroke
        from datascape.gcode.layout import Layout
        from datascape.gcode.production.sequence import make_plan
        for medium,slot,length in (('ink','INK',275),('color','C1',175)):
            strokes=tuple(Stroke(f'{medium}-{i}',(Point(20,20+i*5,.4),Point(20+length,20+i*5,.4)),
                                 'A',slot,medium,sequence=i) for i in range(6))
            jobs,m=make_plan(strokes,Layout('D'),tuple(range(6)))
            name='SHARED_'+medium.upper();units=jobs[name]
            before,old_metrics=final.build(final.profile(ROOT),units)
            after,new_metrics=final.build(final.profile(ROOT,1100,700),units)
            self.assertEqual(sum(old_metrics['loads_per_slot'].values()),1)
            self.assertEqual(sum(new_metrics['loads_per_slot'].values()),2)
            positions={}
            for label,commands in (('before',before),('after',after)):
                ids=[c.source_id for c in commands if c.action=='source_begin']
                self.assertEqual(ids,[s.stroke_id for s in strokes])
                positions[label]=[(c.xyz,c.artistic_pressure) for c in commands if c.artistic_pressure is not None]
            self.assertEqual(positions['before'],positions['after'])
            i=next(i for i,c in enumerate(after) if c.action=='same_color_reload')
            self.assertEqual(next(c.source_id for c in after[i+1:] if c.action=='source_begin'),f'{medium}-4')

    def test_physical_observations_are_qualitative_not_invented_width_or_authorization(self):
        r=final.observations(ROOT)
        self.assertTrue(r['benchmark_completed_operator_reported'])
        self.assertEqual(r['paper_first_touch_G54_Z'],10)
        self.assertEqual(r['brush_splitting_onset_compression_mm_approx'],12)
        self.assertEqual(r['ink_delivery_mm_reported_workable'],1500)
        self.assertIsNone(r['numerically_measured_stroke_widths_mm'])
        self.assertFalse(r['operator_streamed_file_hash_or_controller_yaml_readback_supplied'])
        p=final.profile(ROOT);self.assertEqual(p.data['evidence'],[])
        self.assertFalse(p.data['machine']['target_config_installed'])
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)

    def test_benchmark_generation_uses_Z20_hover_and_Z15_approach(self):
        p=final.profile(ROOT);request,programs=benchmark.build(ROOT,p)
        for kind,commands in programs.items():
            checked=benchmark.readback(benchmark.render(commands,p,request,kind),commands,p,request,kind)
            self.assertEqual(checked['paper_approach_boundary_z'],15)
            self.assertEqual(checked['drawing_xy_mm'],1500)
            self.assertTrue(all(c.xyz[2]==20 for c in commands if c.action=='retract'))
            if kind=='AIR':self.assertTrue(all(c.xyz[2]==20 for c in commands if c.action=='draw'))

    def test_numeric_pressure_lineage_hover_and_no_routine_M0(self):
        p=final.profile(ROOT);jobs,m=fixture_plan();commands,_=final.build(p,jobs['P1_INK'])
        r=final.readback(final.numeric_text(commands,p,'TEST'),commands,p,m['jobs']['P1_INK'])
        self.assertEqual(r['paper_hover_Z'],20);self.assertEqual(r['M0_count'],0)
        self.assertEqual(r['end_work_xyz'],[800,800,35])
        self.assertGreater(r['all_artistic_pressure_samples_verified'],0)
        for c in commands:
            if c.action in ('initial_contact','release'):self.assertEqual(c.xyz[2],10)
            if c.action=='retract':self.assertEqual(c.xyz[2],20)

    def test_complete_air_projection_never_contacts_stations_or_paper(self):
        p=final.profile(ROOT);jobs,m=fixture_plan();commands,_=final.build(p,jobs['P1_INK'])
        source={f['stroke']['source_id']:('ink','INK') for u in m['jobs']['P1_INK'] for f in u['fragments']}
        air=final.project_air(commands,p,source)
        r=final.readback(final.numeric_text(air,p,'TEST_AIR'),air,p,m['jobs']['P1_INK'],True)
        self.assertTrue(r['air_projection'])
        self.assertTrue(all(c.xyz[2]==35 for c in air if c.kind=='move' and c.time_category=='station_handling'))
        self.assertTrue(all(c.xyz[2]==20 for c in air if c.artistic_pressure is not None))

    def test_readback_rejects_fast_contact_pressure_or_wrong_hover(self):
        p=final.profile(ROOT);jobs,m=fixture_plan();commands,_=final.build(p,jobs['P1_INK'])
        for action,changes in [('initial_contact',dict(feed_mm_min=7000)),('release',dict(feed_mm_min=7000)),('retract',dict(xyz=(299,20,15)))]:
            bad=list(commands);i=next(i for i,c in enumerate(bad) if c.action==action);bad[i]=replace(bad[i],**changes)
            with self.assertRaises(ValueError):final.readback(final.numeric_text(bad,p,'BAD'),bad,p,m['jobs']['P1_INK'])

    def test_quantization_caps_feed_without_modifying_original_geometry(self):
        p=final.profile(ROOT);a=(20,20,5);b=(20.001,20,4.999111111111111)
        f=2000*dist(a,b)/abs(b[2]-a[2])
        limited=serialized_feed_cap(a,b,f,p.data['machine'],p.data['motion'],'draw')
        aq=tuple(round(x,9) for x in a);bq=tuple(round(x,9) for x in b)
        parsed=float(f'{limited:.9f}');actual=abs(bq[2]-aq[2])/dist(aq,bq)*parsed
        self.assertLessEqual(actual,2000+1e-6);self.assertLess(limited,f)
        self.assertEqual(b,(20.001,20,4.999111111111111))

    def test_delivered_full_scene_has_all_original_sources_samples_and_verified_bytes(self):
        out=os.environ.get('DATASCAPE_LARGE_BAEGUNMO_REVIEW')
        if not out:self.skipTest('full generated review package not supplied')
        r=final.verify(Path(out));self.assertEqual(r['full_numeric_files_verified'],3)
        self.assertEqual(r['original_strokes'],14951);self.assertEqual(r['accepted_pressure_samples'],240974)


if __name__=='__main__':unittest.main()
