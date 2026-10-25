"""Thirty-contact scheduling and the independent bed-to-G54 registration."""
import unittest
from copy import deepcopy
from projects.hanji_relief.data import PROJECT, load_dots, load_json, settings
from projects.hanji_relief.plan import make_plan, standard_plans, c4_test
from projects.hanji_relief.motion import build_paint, serialize, readback


class Refill30Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = settings()
        cls.dots = load_dots()
        cls.scenario = load_json(PROJECT/'config/review.nominal_offset0.json')

    def test_current_default_and_completed_flat_comparison_are_independent(self):
        self.assertEqual((self.cfg['compression_depth_mm'], self.cfg['dwell_at_depth_s'], self.cfg['refill_every_contacts']), (3, 1, 30))
        flat = load_json(PROJECT/'benchmarks/flat_c2_330_v01/config.json')
        self.assertEqual(flat['refill_every_contacts'], 20)
        self.assertEqual(settings(PROJECT/'review/nominal_offset0/settings.json')['refill_every_contacts'], 20)

    def test_30_contact_boundaries_and_no_supply_after_final_contact(self):
        candidates = [d for d in self.dots if d.color_id == 'C2']
        for count in (0, 1, 29, 30, 31, 59, 60, 61):
            with self.subTest(count=count):
                plan = make_plan(candidates[:count], 'TEST', 'global', config=self.cfg)
                self.assertEqual(plan['loads'], (count+29)//30)
                self.assertEqual([r['execution_sequence'] for r in plan['dots'] if r['service_before']], list(range(1, count+1, 30)))
                self.assertTrue(all(1 <= r['contact_in_batch'] <= 30 for r in plan['dots']))

    def test_color_change_resets_without_redundant_old_color_reload(self):
        selected = [d for d in self.dots if d.color_id == 'C2'][:30] + [d for d in self.dots if d.color_id == 'A4'][:1]
        plan = make_plan(selected, 'TEST', 'global', config=self.cfg)
        self.assertEqual((plan['loads'], plan['same_color_reloads']), (2, 0))
        self.assertEqual((plan['dots'][30]['service_before'], plan['dots'][30]['contact_in_batch']), ('color_change', 1))

    def test_source_coordinates_colors_order_and_depth_are_unchanged(self):
        old = standard_plans(config=settings(PROJECT/'review/nominal_offset0/settings.json'))
        new = standard_plans(config=self.cfg)
        for before, after in zip(old, new):
            keys = ('study_dot_id', 'physical_panel_id', 'source_panel_id', 'artwork_x_mm', 'artwork_y_mm', 'z_design_mm', 'color_id')
            self.assertEqual([tuple(r[k] for k in keys) for r in before['dots']], [tuple(r[k] for k in keys) for r in after['dots']])
        self.assertEqual((new[0]['loads'], new[4]['loads']), (209, 32))

    def test_reload_between_retraction30_and_contact31_serialized(self):
        plan = c4_test(config=self.cfg)
        profile, commands, rows, services = build_paint(plan, self.scenario)
        self.assertEqual([s['before_sequence'] for s in services], [1, 31])
        start = next(i for i,c in enumerate(commands) if c.action == 'dot_complete' and c.source_id == rows[29]['study_dot_id'])
        end = next(i for i,c in enumerate(commands) if c.action == 'dot_begin' and c.source_id == rows[30]['study_dot_id'])
        self.assertEqual(commands[start-1].action, 'retract')
        boundary = commands[start+1:end]
        self.assertEqual(sum(c.action == 'same_color_reload' for c in boundary), 1)
        self.assertFalse(any(c.action in ('full_wash', 'wash') for c in boundary))
        report = readback(serialize(commands, profile, plan, self.scenario), commands, profile, plan, rows, services)
        self.assertEqual((report['planned_loads'], report['serialized_dot_dwell_s']), (2, 40))

    def test_bed_touch10_translates_relief_once_without_moving_stations(self):
        plan = c4_test(config=self.cfg)
        original, commands0, rows0, _ = build_paint(plan, self.scenario)
        scenario = deepcopy(self.scenario)
        scenario['individual_mount']['hanji_surface_offset_z_mm'] = 10
        profile, commands, rows, services = build_paint(plan, scenario)
        for before, after in zip(rows0, rows):
            self.assertAlmostEqual(after['review_first_touch_z_mm'], float(after['z_design_mm'])+10)
            self.assertAlmostEqual(after['review_press_z_mm'], float(after['z_design_mm'])+7)
            self.assertEqual(after['g54_x_mm'], before['g54_x_mm'])
        self.assertEqual(profile.data['stations'], original.data['stations'])
        stations = lambda cs: [c.xyz for c in cs if c.action.startswith('station_')]
        self.assertEqual(stations(commands), stations(commands0))
        report = readback(serialize(commands, profile, plan, scenario), commands, profile, plan, rows, services)
        self.assertFalse(report['machine_authorized'])
        # A changed coordinate number does not create the missing physical gap.
        self.assertEqual(35-(10+20), 5)
        old = settings(PROJECT/'review/refill30_offset0/settings.json')
        self.assertLess(35-(10+20), old['required_surface_clearance_mm'])
        self.assertEqual(35-(10+20), self.cfg['required_surface_clearance_mm'])


if __name__ == '__main__':
    unittest.main()
