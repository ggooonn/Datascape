"""Same source/route in two Z modes; synthetic exports are never machine evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import test_gcode_integrated_330 as integrated_tests
from test_gcode_integrated_330 import bind, ROOT
from test_gcode_v03 import auth
from datascape.gcode.binding import digest
from datascape.gcode.production.integrated_benchmark import build, export_integrated
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import verify_export
from benchmarks.integrated_330_v01.handoff import execution_request

EXTRA = ('continuous_benchmark_contact', 'station_contacts', 'wet_motion',
         'air_station_ink', 'air_station_water', 'air_station_A2')


def fixture():
    _, previous = integrated_tests.IntegratedBenchmarkTests().depth_series()
    r = execution_request(ROOT); d = deepcopy(previous.data)
    d['motion'].update(ordinary_travel_mm_min=8000, draw_mm_min=5000, wet_loaded_mm_min=8000,
        z_travel_mm_min=3000, air_xy_mm_min=5000, paper_approach_mm_min=3000, pressure_z_mm_min=2000,
        wet_departure_mm_min=3000, wet_arrival_mm_min=3000, air_station_top_mm=35,
        air_station_roles=['ink', 'water', 'A2'], benchmark_plan_sha256=digest(r))
    d['machine']['stopping'] = {'independent_power_stop_verified': True,
                              'note': 'INVENTED UNIT FIXTURE, NOT ACTUAL MACHINE'}
    p = bind(d, EXTRA); d = deepcopy(p.data)
    for e in d['evidence']:
        if e['check'] == 'continuous_benchmark_contact': e['tested_depths_mm'] = [-9, -10]
    return r, Profile.from_dict(d)


def xy_route(commands):
    out = []
    for c in commands:
        if c.kind == 'move' and (not out or c.xyz[:2] != out[-1]): out.append(c.xyz[:2])
    return out


class PairedBenchmarkTests(unittest.TestCase):
    def test_same_40_paths_visits_feeds_zero_m0_and_only_final_park(self):
        r, p = fixture(); initial = deepcopy(r)
        air, am = build(r, p, 'air'); paint, pm = build(r, p, 'paint')
        self.assertEqual(xy_route(air), xy_route(paint))
        for commands, metrics in ((air, am), (paint, pm)):
            strokes = [c for c in commands if c.action == 'draw']
            self.assertEqual(len(strokes), 40)
            self.assertTrue(all(c.feed_mm_min == 5000 for c in strokes))
            self.assertEqual(metrics['M0_count'], 0)
            self.assertEqual(sum(c.action == 'park' for c in commands), 1)
            self.assertEqual(commands[-2].xyz, (800, 800, 32))
            self.assertEqual([c.message for c in commands if c.action == 'benchmark_station_visit'],
                ['ink:pigment_load', 'ink:same_color_reload', 'water:wash', 'A2:pigment_load', 'A2:same_color_reload'])
            self.assertTrue(any(c.feed_mm_min == 8000 and c.action == 'travel' for c in commands))
            self.assertTrue(any(c.feed_mm_min == 3000 and c.action == 'lift' for c in commands))
        self.assertTrue(all(c.xyz[2] >= 10 for c in air if c.kind == 'move'))
        self.assertEqual([c.xyz[2] for c in paint if c.action == 'draw'],
                         (list(range(-1, -11, -1)) + list(range(-10, 0))) * 2)
        self.assertEqual([c.source_id for c in air if c.action == 'draw'],
                         [c.source_id for c in paint if c.action == 'draw'])
        self.assertEqual(r, initial)

    def test_air_does_not_require_wet_z_depth_curve_or_wet_test(self):
        r, p = fixture(); d = deepcopy(p.data)
        d['brush_profiles'] = {}; d['machine']['junction_deviation_mm'] = None
        for k in ('paper_contact_mm_min', 'paper_release_mm_min', 'pressure_z_mm_min',
                  'wet_max_xy_acceleration_mm_s2', 'contact_max_z_acceleration_mm_s2'):
            d['motion'][k] = None
        for role in ('ink', 'water'):
            st = d['stations'][role]
            st['deep_surface_xyz'][2] = None; st['shallow_surface_xyz'][2] = None
        for role in ('ink', 'water', 'A2'):
            d['stations'][role].update(contact_box_xyz=None, liquid_reference_z=None, immersion_mm=None,
                                       bottom_z=None, feed_mm_min=None, dwell_seconds=None)
        p = bind(d, ('air_station_ink', 'air_station_water', 'air_station_A2'))
        commands, _ = build(r, p, 'air')
        self.assertEqual(sum(c.action == 'draw' for c in commands), 40)
        self.assertFalse(p.evidence_passed('wet_motion'))

    def test_missing_safety_and_contact_evidence_never_erase_into_zero_pause_jobs(self):
        r, p = fixture()
        for check, kind in (('homing_limits_estop', 'air'), ('motion_limits', 'air'),
                            ('air_station_ink', 'air'), ('air_run', 'paint'),
                            ('continuous_benchmark_contact', 'paint'), ('station_contacts', 'paint'),
                            ('wet_motion', 'paint')):
            d = deepcopy(p.data); d['evidence'] = [e for e in d['evidence'] if e['check'] != check]
            with self.assertRaisesRegex(ValueError, check): build(r, Profile.from_dict(d), kind)
        for change, error in (
            (lambda d: d['machine']['stopping'].update(independent_power_stop_verified=False), 'independent'),
            (lambda d: d['stations']['ink'].update(deep_surface_xyz=None), 'station XY'),
            (lambda d: d['stations']['A2'].update(radius_mm=None), 'loading radius'),
            (lambda d: d['motion'].update(paper_contact_z_range=[-8, 0]), 'test envelope')):
            d = deepcopy(p.data); change(d)
            with self.assertRaisesRegex(ValueError, error): build(r, bind(d, EXTRA), 'paint' if 'envelope' in error else 'air')
        d = deepcopy(p.data)
        for e in d['evidence']:
            if e['check'] == 'continuous_benchmark_contact': e['tested_depths_mm'] = [-8]
        with self.assertRaisesRegex(ValueError, '-9/-10'): build(r, Profile.from_dict(d), 'paint')

    def test_both_actual_serializers_readback_hashes_and_rehashed_mutation_detection(self):
        r, p = fixture()
        with tempfile.TemporaryDirectory() as temp:
            for kind, stage in (('air', 'air'), ('paint', 'calibration')):
                name = 'BENCHMARK_330_' + kind.upper(); out = Path(temp)/kind
                report = export_integrated(r, p, kind, auth(p, r, stage, [name]), out)
                self.assertEqual(report['plan_sha256'], digest(r))
                verified = verify_export(out)
                self.assertEqual(verified['jobs'][name]['M0_count'], 0)
                self.assertTrue(verified['jobs'][name]['production_verification_occurs_before_start'])
                path = out/(name+'.gcode'); text = path.read_text()
                self.assertTrue(text.endswith('M2\n')); self.assertNotIn('\nM0\n', text)
                path.write_text(text.replace('F5000.000000000', 'F4999.000000000', 1))
                hashes = json.loads((out/'MANIFEST_SHA256.json').read_text())
                hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
                with self.assertRaisesRegex(ValueError, 'planned motion'): verify_export(out)
        # Measuring contact Z later does not erase an actual Air result at safe Z.
        d = deepcopy(p.data)
        d['stations']['ink']['liquid_reference_z'] += .2
        d['stations']['ink']['deep_surface_xyz'][2] += .1
        self.assertTrue(Profile.from_dict(d).evidence_passed('air_run'))
        self.assertFalse(Profile.from_dict(d).evidence_passed('continuous_benchmark_contact'))


if __name__ == '__main__': unittest.main()
