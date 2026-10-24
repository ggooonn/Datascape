"""Paper-only first-touch conversion, contact safety and repeated depth trial."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from benchmarks.integrated_330_v01 import paper_reference_1500 as final
from benchmarks.integrated_330_v01 import final_ink_endurance as previous
from benchmarks.integrated_330_v01.numeric_review import xy_route
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder, RuntimeMaterials
from benchmarks.integrated_330_v01.spring_pipeline import require_unified_profile
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.calibration_jobs import validate_request, render_calibration
from datascape.gcode.production.trajectory import build_job
from datascape.gcode.production.exporter import verify_draw_lineage
from datascape.gcode.motion import MotionSettings
from test_gcode_v03 import plan as fixture_plan

ROOT=Path(__file__).resolve().parents[1]


class PaperReferenceTests(unittest.TestCase):
    def test_per_brush_formula_relative_curve_and_no_unapproved_extrapolation(self):
        p=final.profile(ROOT);ink=p.brush_for('ink','INK')
        self.assertEqual([ink.compression_to_work_z(c) for c in (1,7,15)],[9,3,-5])
        self.assertEqual(ink.z_for(1),-8);self.assertEqual(ink.work_z_for(1),2)
        self.assertEqual(ink.z_for(.2),-1);self.assertEqual(ink.work_z_for(.2),9)
        d=deepcopy(p.data);d['brush_profiles']['color']['paper_first_touch_z_mm']=12
        q=Profile.from_dict(d);self.assertEqual(q.brush_for('color','A2').compression_to_work_z(7),5)
        self.assertEqual(q.brush_for('ink','INK').compression_to_work_z(7),3)
        for value in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):ink.compression_to_work_z(value)
        for pressure in (-.01,1.01):
            with self.assertRaises(ValueError):ink.work_z_for(pressure)

    def test_profile_preserves_stations_yaml_g54_and_historical_knots(self):
        old=previous.profile(ROOT);p=final.profile(ROOT)
        self.assertEqual(old.data['stations'],p.data['stations']);self.assertEqual(old.data['machine'],p.data['machine'])
        for role in old.data['brush_profiles']:
            self.assertEqual(old.data['brush_profiles'][role]['knots'],p.data['brush_profiles'][role]['knots'])
            self.assertEqual(p.data['brush_profiles'][role]['paper_first_touch_z_mm'],10)
        self.assertEqual(p.data['motion']['paper_hover_mm'],15)
        self.assertEqual(p.data['motion']['paper_approach_mm'],15)
        self.assertEqual(p.data['motion']['paper_contact_z_range'],[-5,10])
        self.assertEqual(p.data['material']['ink_reload_mm'],1500)
        self.assertEqual(p.data['material']['color_reload_mm'],800)
        self.assertFalse(p.data['material']['spring_pressure_response_selected'])
        h=final.handoff(ROOT,p)
        self.assertIsNone(h['selected_pressure_to_compression_knots']);self.assertFalse(h['possible_3_to_15mm_range_selected'])
        self.assertTrue(any('pressure distribution pending' in e for e in p.issues('painting')))
        self.assertFalse(any('pressure distribution pending' in e for e in p.issues('calibration')))

    def test_exact1500_all15_compressions_twice_and_paired_geometry(self):
        p=final.profile(ROOT);request=final.plan(p)
        self.assertEqual(len(request['strokes']),30)
        self.assertEqual(sum(s['drawing_xy_mm'] for s in request['strokes']),1500)
        for i in range(15):
            a,b=request['strokes'][i],request['strokes'][i+15]
            self.assertEqual(a['compression_mm'],i+1);self.assertEqual(a['z_mm'],9-i)
            self.assertEqual(a['z_mm'],b['z_mm']);self.assertEqual(a['start_xy'][0],b['start_xy'][0])
            self.assertEqual(b['start_xy'][1]-a['start_xy'][1],160)
        for line in request['strokes']:
            self.assertEqual(line['end_xy'][0]-line['start_xy'][0],50)
            for xy in (line['start_xy'],line['end_xy']):self.assertTrue(all(10<=v<=320 for v in xy))

    def test_complete_air_and_ink_readback_no_reload_or_fast_plane_crossing(self):
        p=final.profile(ROOT);request,programs=final.build(ROOT,p)
        self.assertEqual(xy_route(programs['AIR']),xy_route(programs['INK']))
        for kind,commands in programs.items():
            checked=final.readback(final.render(commands,p,request,kind),commands,p,request,kind)
            self.assertEqual(checked['drawing_xy_mm'],1500);self.assertEqual(checked['source_strokes'],30)
            self.assertEqual(checked['station_visits'],['ink:pigment_load'])
            self.assertEqual(checked['reloads_during_test'],0);self.assertEqual(checked['M0_count'],0)
            self.assertEqual(checked['start_work_xyz'],[0,900,35]);self.assertEqual(checked['end_work_xyz'],[800,800,35])
            self.assertTrue(checked['no_fast_Z_crossing_actual_contact_plane_verified'])
            self.assertFalse(checked['Spring_pressure_finalized']);self.assertFalse(checked['authorized'])

    def test_rejects_fast_approach_contact_compression_or_release_mutations(self):
        p=final.profile(ROOT);request,programs=final.build(ROOT,p);original=programs['INK']
        cases=[('approach',dict(xyz=(20,20,5))),('initial_contact',dict(feed_mm_min=7000)),
            ('calibration_compression',dict(feed_mm_min=7000)),('release',dict(feed_mm_min=7000)),
            ('paper_release_clearance',dict(feed_mm_min=7000)),('calibration_compression',dict(xyz=(20,20,-1)))]
        for action,change in cases:
            commands=list(original);i=next(i for i,c in enumerate(commands) if c.action==action)
            commands[i]=replace(commands[i],**change)
            with self.assertRaises(ValueError):final.readback(final.render(commands,p,request,'INK'),commands,p,request,'INK')

    def test_invalid_first_touch_and_fast_approach_boundary_fail(self):
        p=final.profile(ROOT);d=deepcopy(p.data);d['motion']['paper_approach_mm']=5;q=Profile.from_dict(d)
        self.assertTrue(any('fast paper approach' in e for e in q.issues('calibration')))
        with self.assertRaisesRegex(ValueError,'first-touch'):final.build(ROOT,q)
        with self.assertRaises(ValueError):MotionSettings(p.brush_for('ink','INK'),hover_z_mm=15,approach_z_mm=5)
        for value in (None,float('nan'),float('inf')):
            d=deepcopy(p.data);d['brush_profiles']['ink']['paper_first_touch_z_mm']=value
            with self.assertRaises((ValueError,TypeError)):Profile.from_dict(d).brush_for('ink','INK')

    def test_calibration_accepts_positive_absolute_z_and_uses_brush_contact(self):
        p=final.profile(ROOT)
        request=dict(schema='datascape.calibration_plan.v0.3',paper_region_xy=[[10,10],[320,320]],
            brush_lines=[dict(start_xy=[20,20],end_xy=[70,20],z_mm=9,feed_mm_min=6000)])
        validate_request(request,p,physical=False);b=RuntimeBuilder(p);render_calibration(request,p,b,integrated=True)
        expected={'initial_contact':10,'calibration_compression':9,'release':10,'paper_release_clearance':15}
        for action,z in expected.items():
            c=next(c for c in b.commands if c.action==action);self.assertEqual(c.xyz[2],z);self.assertEqual(c.feed_mm_min,2000)
        bad=deepcopy(request);bad['brush_lines'][0]['z_mm']=11
        with self.assertRaises(ValueError):validate_request(bad,p,physical=False)

    def test_pressure_calibration_and_production_lineage_add_reference_only_once(self):
        p=final.profile(ROOT);request=dict(schema='datascape.calibration_plan.v0.3',requires_evidence=['paper_contact'],
            pressure_lines=[dict(samples=[dict(xy=[20,20],pressure=.2),dict(xy=[70,20],pressure=1)],
                feed_mm_min=6000,medium='ink',slot='INK')])
        validate_request(request,p,physical=False);b=RuntimeBuilder(p);render_calibration(request,p,b,integrated=True)
        self.assertEqual([c.xyz[2] for c in b.commands if c.artistic_pressure is not None],[9,2])
        jobs,manifest=fixture_plan();units=jobs['P1_INK'];b=RuntimeBuilder(p)
        commands,_=build_job(p,units,'fixture',offline_builder=b,offline_material=RuntimeMaterials(b))
        checked=verify_draw_lineage(commands,manifest['jobs']['P1_INK'],p,'fixture')
        self.assertGreater(checked['all_artistic_pressure_samples_verified'],0)
        for c in commands:
            if c.artistic_pressure is not None:self.assertEqual(c.xyz[2],10+p.brush_for('ink','INK').z_for(c.artistic_pressure))
            if c.action in ('initial_contact','release'):self.assertEqual(c.xyz[2],10)

    def test_first_touch_changes_bind_paper_evidence_and_constant_mode(self):
        p=final.profile(ROOT);d=deepcopy(p.data);d['brush_profiles']['ink']['paper_first_touch_z_mm']=11;q=Profile.from_dict(d)
        for check in ('air_run','paper_hover','paper_contact','brush_response'):
            self.assertNotEqual(p.evidence_scope_sha256(check),q.evidence_scope_sha256(check))
        setting=MotionSettings(p.brush_for('ink','INK'),mode='constant',constant_z_mm=-7,hover_z_mm=15,approach_z_mm=15)
        self.assertEqual(setting.depth(.5),3)

    def test_no_fabricated_physical_evidence_and_no_final_Spring_choice(self):
        p=final.profile(ROOT);self.assertEqual(p.data['evidence'],[])
        self.assertEqual(p.data['status'],'nominal_review');self.assertFalse(p.data['machine']['target_config_installed'])
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)

    def test_constant_compression_trial_does_not_depend_on_a_selected_pressure_curve(self):
        d=deepcopy(final.profile(ROOT).data)
        for b in d['brush_profiles'].values():b['knots']=[]
        p=Profile.from_dict(d);request,programs=final.build(ROOT,p)
        checked=final.readback(final.render(programs['INK'],p,request,'INK'),programs['INK'],p,request,'INK')
        self.assertEqual(checked['drawing_xy_mm'],1500)
        self.assertFalse(p.data['material']['spring_pressure_response_selected'])

    def test_two_programs_regenerate_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review';final.export(ROOT,out)
            self.assertEqual(len(list(out.glob('*.gcode'))),2)
            self.assertEqual(final.verify(ROOT,out)['numeric_review_files_regenerated'],2)
            path=out/(final.STEM+'INK_REVIEW.gcode')
            path.write_text(path.read_text().replace('Z9.000000000','Z-1.000000000',1))
            with self.assertRaisesRegex(ValueError,'SHA256'):final.verify(ROOT,out)

    def test_historical_negative_z_files_are_reproducible_not_rewritten(self):
        self.assertEqual(previous.verify(ROOT,ROOT/'benchmarks/integrated_330_v01/review_final_ink_endurance')['numeric_review_files_regenerated'],4)

    def test_Spring_runner_accepts_corrected_handoff_not_stale_defaults(self):
        p=final.profile(ROOT);require_unified_profile(p)
        for field,value in [('ink_reload_mm',1200),('color_reload_mm',1000)]:
            d=deepcopy(p.data);d['material'][field]=value
            with self.assertRaises(ValueError):require_unified_profile(Profile.from_dict(d))
        d=deepcopy(p.data);d['machine']['start_work_xyz']=[0,898,35]
        with self.assertRaises(ValueError):require_unified_profile(Profile.from_dict(d))
        d=deepcopy(p.data);d['motion']['segmented_travel']['ordinary_travel']['departure_mm_min']=3000
        with self.assertRaises(ValueError):require_unified_profile(Profile.from_dict(d))


if __name__=='__main__':unittest.main()
