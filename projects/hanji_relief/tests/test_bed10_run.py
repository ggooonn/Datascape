"""Operator setup, exact +10 transform and final serialized program checks."""
import unittest
from copy import deepcopy
from projects.hanji_relief.data import PROJECT, load_json, settings
from projects.hanji_relief.plan import c4_test
from projects.hanji_relief.motion import build_paint
from projects.hanji_relief.run_export import setup, plans, serialize, checked_text


class Bed10RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=settings()
        cls.scenario=load_json(PROJECT/'config/mounting.bed10_hover35.json')
        cls.plan=c4_test(config=cls.config)
        cls.profile,cls.commands,cls.rows,cls.services=build_paint(cls.plan,cls.scenario)

    def test_user_accepted_five_mm_does_not_require_old_ten_mm(self):
        self.assertEqual(setup(self.config,self.scenario)['nominal_clearance_mm'],5)
        bad=deepcopy(self.config);bad['required_surface_clearance_mm']=10
        with self.assertRaises(ValueError):setup(bad,self.scenario)
        bad=deepcopy(self.scenario);bad['operator_requests_offline_programs']=False
        with self.assertRaises(ValueError):setup(self.config,bad)

    def test_p4_points_match_full_without_global_local_z_shift(self):
        full,p4=plans(self.config)
        self.assertEqual((full['dot_count'],p4['dot_count'],full['loads'],p4['loads']),(6200,890,209,32))
        subset={r['study_dot_id']:r for r in full['dots'] if r['physical_panel_id']=='4'}
        self.assertEqual(len(subset),890)
        for r in p4['dots']:
            source=subset[r['study_dot_id']]
            self.assertEqual(r['z_design_mm'],source['z_design_mm'])
            self.assertAlmostEqual(r['artwork_x_mm'],source['artwork_x_mm'])
            self.assertAlmostEqual(r['artwork_y_mm']+200,source['artwork_y_mm'])

    def test_exact_press_dwell_hover_and_fixed_xy_at_each_dot(self):
        for row in self.rows:
            self.assertAlmostEqual(row['review_first_touch_z_mm'],float(row['z_design_mm'])+10)
            self.assertAlmostEqual(row['review_press_z_mm'],float(row['z_design_mm'])+7)
            self.assertEqual(row['fixed_hover_g54_z_mm'],35)
            self.assertEqual(row['surface_correction_status'],'no_local_map_operator_selected_design_baseline')
        text=serialize(self.plan,self.profile,self.commands,self.scenario)
        report=checked_text(text,self.plan,self.profile,self.commands,self.rows,self.services,self.scenario)
        self.assertEqual(report['serialized_dot_dwell_s'],40)
        self.assertTrue(report['operator_setup_applied'])
        self.assertEqual(text.count('; terminal_cleanup_begin'),1)
        self.assertEqual([s['before_sequence'] for s in self.services],[1,31])

    def test_operator_file_numeric_tamper_is_rejected(self):
        text=serialize(self.plan,self.profile,self.commands,self.scenario)
        for changed in (text.replace('G4 P1.000000000','G4 P0.500000000',1),text.replace('G21 G90 G94 G54','G21 G90 G94 G54\nG92 Z0',1)):
            with self.assertRaises(ValueError):checked_text(changed,self.plan,self.profile,self.commands,self.rows,self.services,self.scenario)

    def test_only_artwork_z_changes_stations_and_machine_remain_identical(self):
        baseline=load_json(PROJECT/'config/review.nominal_offset0.json')
        p0,cs0,rows0,_=build_paint(self.plan,baseline)
        self.assertEqual(self.profile.data['stations'],p0.data['stations'])
        self.assertEqual(self.profile.data['machine'],p0.data['machine'])
        station=lambda cs:[c.xyz for c in cs if c.action.startswith('station_')]
        self.assertEqual(station(self.commands),station(cs0))
        for before,after in zip(rows0,self.rows):
            self.assertAlmostEqual(after['review_press_z_mm']-before['review_press_z_mm'],10)
            self.assertEqual(after['g54_x_mm'],before['g54_x_mm'])
            self.assertEqual(after['g54_y_mm'],before['g54_y_mm'])


if __name__=='__main__':unittest.main()
