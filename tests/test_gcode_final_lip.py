"""Final measured lip sequence and unchanged Y900/benchmark source regressions."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
import yaml

from benchmarks.integrated_330_v01 import final_lip as final
from benchmarks.integrated_330_v01 import y900_lip as previous
from benchmarks.integrated_330_v01.numeric_review import xy_route
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import lip_stripping_points, emit_station_operation, station_points

ROOT=Path(__file__).resolve().parents[1]


class FinalLipTests(unittest.TestCase):
    def test_yaml_cleanup_changes_only_name_not_configuration_scalars(self):
        raw,diff,report=final.yaml_candidate(ROOT)
        old=yaml.safe_load((ROOT/final.BASE/'config.X860.Y900.high_speed.candidate.yaml').read_bytes())
        new=yaml.safe_load(raw);old['name']='DATASCAPE_HOME_FRAME_X0_Y900_Z35_261024'
        self.assertEqual(new,old);self.assertNotIn('Y898',raw.decode());self.assertNotIn('G10 L20',raw.decode())
        self.assertEqual(new['axes']['y']['homing']['mpos_mm'],900)
        self.assertEqual(new['axes']['y']['max_travel_mm'],900)
        self.assertFalse(report['installed']);self.assertIn('-name: DATASCAPE_HOME_FRAME_X0_Y898',diff)

    def test_only_lip_profile_dependencies_change(self):
        old=previous.frame_profile(ROOT);p=final.profile(ROOT)
        for key in ('motion','material','brush_profiles'):self.assertEqual(p.data[key],old.data[key])
        for role,st in old.data['stations'].items():
            actual=deepcopy(p.data['stations'][role]);actual['lip_stripping']=st.get('lip_stripping')
            expected=deepcopy(st);expected['lip_stripping']=st.get('lip_stripping')
            self.assertEqual(actual,expected)
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)
        self.assertFalse(p.data['machine']['target_config_installed'])
        self.assertEqual(p.data['evidence'],[])
        self.assertEqual(final.profile(ROOT,15000).data['motion']['wet_loaded_mm_min'],15000)

    def test_configurable_negative_displacement_and_independent_feed(self):
        st=deepcopy(final.profile(ROOT).data['stations']['ink'])
        st['lip_stripping'].update(relative_x_mm=-5,contact_feed_mm_min=200)
        points=lip_stripping_points(st)
        self.assertEqual(points,((815,458,35),(815,458,20),(810,458,20),(810,458,35)))
        for field,value in [('relative_x_mm',20),('relative_x_mm',0),('relative_x_mm',float('nan')),
            ('contact_feed_mm_min',301),('measured_contact_xyz',None),('safe_retract_z',20),
            ('coordinate_source','invented')]:
            invalid=deepcopy(st);invalid['lip_stripping'][field]=value;b=RuntimeBuilder(final.profile(ROOT))
            with self.assertRaisesRegex(ValueError,'stone-lip'):emit_station_operation(b,invalid,'wash','wet_loaded')
            self.assertEqual(b.commands,[])

    def test_official_contact_volume_includes_new_lip_not_just_old_stone(self):
        st=deepcopy(final.profile(ROOT).data['stations']['ink'])
        st['contact_box_xyz']=[[825,370,0],[855,475,35]]
        # Prior stone and single wipe fit, new lip X815/795 does not.
        with self.assertRaisesRegex(ValueError,'calibrated volume'):station_points(st)

    def test_shared_emitter_lifts_before_lip_and_retracts_before_transfer(self):
        p=final.profile(ROOT);plan,programs=final.jobs(ROOT,p)
        previous_plan,old=previous.jobs(ROOT,previous.frame_profile(ROOT));self.assertEqual(plan,previous_plan)
        self.assertEqual(programs['WATER_ONLY'],programs['INK_GOUACHE'])
        self.assertEqual(xy_route(programs['AIR']),xy_route(programs['WATER_ONLY']))
        for name,commands in programs.items():
            result=final.readback(final.render(commands,p,plan,name),commands,p,name)
            self.assertEqual(result['source_strokes'],40);self.assertEqual(result['M0_count'],0)
            self.assertEqual(result['start_work_xyz'],[0,900,35]);self.assertEqual(result['end_work_xyz'],[800,800,35])
            self.assertEqual(result['lip_contact_strokes'],0 if name=='AIR' else 3)
            self.assertEqual(result['pressed_shallow_passes'],0 if name=='AIR' else 3)
            self.assertFalse(result['authorized']);self.assertFalse(result['physical_new_sequence_verified'])

    def test_ordering_checker_rejects_lift_or_strip_feed_mutation(self):
        from dataclasses import replace
        p=final.profile(ROOT);plan,programs=final.jobs(ROOT,p);original=programs['WATER_ONLY']
        i=next(i for i,c in enumerate(original) if c.travel_phase=='lip_strip')
        for index,changes in [(i,dict(feed_mm_min=15000)),(i-1,dict(xyz=(815,458,19))),
                              (i+1,dict(xyz=(795,458,20)))]:
            commands=list(original);commands[index]=replace(commands[index],**changes)
            with self.assertRaises(ValueError):final.readback(final.render(commands,p,plan,'WATER_ONLY'),commands,p,'WATER_ONLY')

    def test_complete_package_regenerates_and_payload_tamper_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review';final.export(ROOT,out)
            self.assertEqual(final.verify(ROOT,out)['numeric_review_files_regenerated'],3)
            path=out/(final.STEM+'WATER_ONLY_REVIEW.gcode')
            path.write_text(path.read_text().replace('X795.000000000','X794.000000000',1))
            with self.assertRaisesRegex(ValueError,'SHA256'):final.verify(ROOT,out)

    def test_previous_published_no_lip_reviews_remain_reproducible(self):
        self.assertEqual(previous.verify(ROOT,ROOT/final.BASE)['numeric_review_files_regenerated'],5)


if __name__=='__main__':unittest.main()
