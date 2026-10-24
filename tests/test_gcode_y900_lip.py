"""Unchanged Y0, upper-only extension and no unmeasured lip contact."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

import yaml

from benchmarks.integrated_330_v01.y900_lip import (BASE,yaml_candidate,frame_profile,
    reconciliation_template,validate_reconciliation,lip_candidates,contact_blockers,
    require_contact_ready,jobs,readback,export,verify)
from benchmarks.integrated_330_v01.high_speed import build_benchmark,verify_package
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder
from benchmarks.integrated_330_v01.numeric_review import BANNER,xy_route,check_move
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import emit_station_operation
from datascape.gcode.production.exporter import _serialize

ROOT=Path(__file__).resolve().parents[1]


def synthetic_readback():
    r=reconciliation_template()
    r.update(operator='SYNTHETIC UNIT TEST ONLY',date='TEST',method='synthetic readback; not real evidence',
        active_yaml_sha256=yaml_candidate(ROOT)[2]['candidate_sha256'],post_home_mpos=[0,900,35],
        post_home_wpos=[0,900,35],g54_offset=[0,0,0],g92_offset=[0,0,0],tool_offset=[0,0,0],
        reference_mpos_y=554.5,reference_wpos_y=554.5,lower_Y0_mpos_y=0,lower_Y0_wpos_y=0,
        physical_travel900_confirmed=True)
    return r


class Y900LipTests(unittest.TestCase):
    def test_yaml_only_upper_label_and_travel_settings_change(self):
        raw,diff,report=yaml_candidate(ROOT);base=(ROOT/BASE/'config.X860.high_speed.candidate.yaml').read_bytes()
        a=yaml.safe_load(raw);b=yaml.safe_load(base);b['axes']['y']['homing']['mpos_mm']=900.;b['axes']['y']['max_travel_mm']=900.
        self.assertEqual(a,b);self.assertEqual(len(report['settings_changed']),2)
        self.assertEqual(a['axes']['x']['max_travel_mm'],860)
        self.assertEqual([a['axes'][axis]['max_rate_mm_per_min'] for axis in ('x','y')],[20000,20000])
        self.assertIn('+      mpos_mm: 900.0',diff);self.assertIn('+    max_travel_mm: 900.0',diff)
        self.assertTrue(report['physical_Y0_unchanged_operator_reported'])
        self.assertFalse(report['installed']);self.assertFalse(report['read_back']);self.assertFalse(report['physical_range_verified'])

    def test_profile_changes_no_station_or_paper_coordinates_and_no_pressure(self):
        p=frame_profile(ROOT);old=Profile.load(ROOT/BASE/'profile.high_wet12000.json')
        for key in ('brush_profiles','motion','material'):self.assertEqual(p.data[key],old.data[key])
        self.assertEqual(p.data['machine']['machine_bounds_xyz'],[[0,0,-11],[860,900,35]])
        self.assertEqual(p.data['machine']['start_work_xyz'],[0,900,35]);self.assertEqual(p.data['machine']['g54_to_machine_xyz'],[0,0,0])
        for role,st in old.data['stations'].items():
            for key in ('center_xy','deep_surface_xyz','shallow_surface_xyz','registered_region_xy','bottom_z','liquid_reference_z','immersion_mm'):
                self.assertEqual(p.data['stations'][role].get(key),st.get(key))
        for role in ('ink','water'):
            self.assertEqual(old.data['stations'][role]['shallow_wipe']['passes'],2)
            self.assertEqual(p.data['stations'][role]['shallow_wipe']['passes'],1)
            self.assertIsNone(p.data['stations'][role]['lip_stripping']['relative_x_mm'])
            self.assertEqual(p.data['stations'][role]['lip_stripping']['historical_proposed_relative_x_mm'],-20)
            for key in ('start_xy','end_xy','surface_z','compression_mm','return_xy'):
                self.assertEqual(p.data['stations'][role]['shallow_wipe'][key],old.data['stations'][role]['shallow_wipe'][key])
        self.assertEqual(frame_profile(ROOT,15000).data['motion']['wet_loaded_mm_min'],15000)

    def test_new_readback_missing_is_not_filled_as_success(self):
        r=reconciliation_template();self.assertIsNone(r['post_home_mpos']);self.assertTrue(r['fixed_fixtures_unchanged'])
        with self.assertRaises(ValueError):frame_profile(ROOT,record=r)
        p=frame_profile(ROOT)
        self.assertFalse(p.data['machine']['coordinate_reconciliation_confirmed'])
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)

    def test_consistent_operator_record_updates_frame_dependencies_but_not_authorization(self):
        p=frame_profile(ROOT,record=synthetic_readback())
        self.assertTrue(p.data['machine']['coordinate_reconciliation_confirmed'])
        self.assertEqual(p.data['machine']['start_work_xyz'],[0,900,35]);self.assertEqual(p.data['evidence'],[])
        self.assertEqual(p.data['status'],'nominal_review')
        with self.assertRaises(ValueError):p.require('air')

    def test_plus2_or_wrong_lower_zero_is_diagnostic_failure_not_translation(self):
        for field,value in [('g54_offset',[0,2,0]),('post_home_wpos',[0,898,35]),
            ('reference_mpos_y',556.5),('lower_Y0_mpos_y',2),('g92_offset',[0,2,0]),
            ('physical_travel900_confirmed',False),('active_yaml_sha256','WRONG')]:
            r=synthetic_readback();r[field]=value
            with self.assertRaises(ValueError,msg=field):frame_profile(ROOT,record=r)

    def test_one_wipe_replaces_two_and_all_40_sources_depths_remain(self):
        p=frame_profile(ROOT);plan,programs=jobs(ROOT,p)
        old=Profile.load(ROOT/BASE/'profile.high_wet12000.json');old_plan,old_commands=build_benchmark(ROOT,old)
        self.assertEqual(plan,old_plan)
        draw=lambda rows:[(c.source_id,c.xyz,c.feed_mm_min) for c in rows if c.action=='draw']
        paint=programs['ONE_WIPE_330_WATER_ONLY'];self.assertEqual(draw(paint),draw(old_commands))
        wipes=[c for c in paint if c.travel_phase=='shallow_wipe']
        self.assertEqual([c.xyz for c in wipes],[(840,465,7.5),(840,465,7.5),(840,315,7.5)])
        self.assertFalse(any(c.kind=='move' and c.travel_phase=='reentry' and c.xyz[0]==830 for c in paint))
        self.assertEqual(programs['ONE_WIPE_330_INK_GOUACHE'],paint)
        self.assertEqual(xy_route(programs['ONE_WIPE_330_AIR']),xy_route(paint))
        for name,commands in programs.items():
            text=BANNER+_serialize(commands,p,'PLAN',name,'offline_review')
            checked=readback(text,commands,p,name)
            self.assertEqual(checked['start_machine_xyz'],[0,900,35]);self.assertEqual(checked['end_machine_xyz'],[800,800,35])
            self.assertEqual(checked['M0_count'],0);self.assertFalse(checked['lip_contact_emitted'])

    def test_lip_clearance_is_not_a_Z20_probe_or_contact_stroke(self):
        p=frame_profile(ROOT);_,programs=jobs(ROOT,p);commands=programs['LIP_APPROACH_AIR']
        self.assertTrue(all(c.xyz[2]==35 for c in commands if c.kind=='move'))
        moves=[c for c in commands if c.action=='lip_clearance_only']
        self.assertTrue(all(c.feed_mm_min==500 for c in moves))
        self.assertIn((815,458,35),[c.xyz for c in moves]);self.assertIn((815,298,35),[c.xyz for c in moves])
        self.assertFalse(any(c.xyz[0]<0 for c in commands if c.kind=='move'))

    def test_distinct_shallow_surfaces_and_contact_gate_stay_closed(self):
        proposals=lip_candidates();self.assertEqual(proposals['ink']['Y_interval_overlap_mm'],17)
        self.assertEqual(proposals['water']['Y_interval_overlap_mm'],13)
        self.assertFalse(proposals['water']['wipe_end_inside_lip_Y_region'])
        self.assertEqual(proposals['water']['clearance_reposition_Y_to_region_center_mm'],-17)
        p=frame_profile(ROOT)
        for role,record in proposals.items():
            self.assertEqual(record['clearance_only_delta_X_mm'],-25)
            self.assertIsNone(record['measured_contact_start_xyz']);self.assertIsNone(record['confirmed_relative_x_mm'])
            self.assertGreater(len(contact_blockers(p,role,record)),5)
            with self.assertRaisesRegex(ValueError,'lip contact export blocked'):require_contact_ready(p,role,record)
            st=deepcopy(p.data['stations'][role]);st['lip_stripping']['enabled']=True;b=RuntimeBuilder(p)
            with self.assertRaisesRegex(ValueError,'stone-lip contact'):emit_station_operation(b,st,'wash','wet_loaded')
            self.assertEqual(b.commands,[])

    def test_new_Y_bounds_and_Z_rate_are_checked(self):
        p=frame_profile(ROOT)
        check_move((0,900,35),(10,899,35),15000,'travel',p,'air')
        with self.assertRaises(ValueError):check_move((0,900,35),(0,900.1,35),1000,'travel',p,'air')
        with self.assertRaises(ValueError):check_move((0,900,35),(0,-.1,35),1000,'travel',p,'air')
        with self.assertRaises(ValueError):check_move((0,900,35),(0,900,34),8000,'lift',p,'air')

    def test_five_programs_regenerate_and_payload_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review';export(ROOT,out)
            self.assertEqual(len(list(out.glob('*.gcode'))),5)
            self.assertEqual(verify(ROOT,out)['numeric_review_files_regenerated'],5)
            self.assertFalse(list(out.glob('*OFFSET2*')))
            file=next(out.glob('*LIP_APPROACH_AIR_REVIEW.gcode'))
            file.write_text(file.read_text().replace('Z35.000000000','Z20.000000000',1))
            with self.assertRaisesRegex(ValueError,'SHA256'):verify(ROOT,out)

    def test_operator_record_regenerates_consistently_without_opening_contact_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'reported';export(ROOT,out,record=synthetic_readback())
            self.assertTrue(json.loads((out/'controller.Y900.json').read_text())['read_back'])
            self.assertTrue((out/'reconciliation.OPERATOR_REPORTED.json').exists())
            self.assertEqual(verify(ROOT,out)['numeric_review_files_regenerated'],5)
            self.assertFalse(json.loads((out/'verification.json').read_text())['lip_contact_program_exported'])

    def test_existing_two_pass_high_speed_review_still_regenerates(self):
        self.assertEqual(verify_package(ROOT,ROOT/BASE)['regenerated_numeric_Gcode_files'],8)


if __name__=='__main__':unittest.main()
