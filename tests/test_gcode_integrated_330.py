"""Integrated commissioning contracts; every passing physical profile is synthetic."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_gcode_v03 import measured_test_profile, auth
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile, BASE_CHECKS
from datascape.gcode.production.trajectory import Builder, require_path
from datascape.gcode.production.exporter import verify_export
from datascape.gcode.production.integrated_benchmark import build, export_integrated, validate, depth_column
from benchmarks.integrated_330_v01.design import plan, configured_profile, facts
from benchmarks.commissioning_330_v01.design import KNOTS
from benchmarks.integrated_330_v01.handoff import execution_profile, execution_request

ROOT = Path(__file__).resolve().parents[1]


def bind(d, extra=()):
    p = Profile.from_dict(d)
    d['evidence'] = [{'check': c, 'status': 'passed', 'scope_sha256': p.evidence_scope_sha256(c),
                     'operator': 'synthetic-unit-test', 'date': 'synthetic-test',
                     'method': 'invented unit fixture; never delivered as physical evidence'}
                    for c in (*BASE_CHECKS, 'air_run', 'air_local_hover_clearance', *extra)]
    return Profile.from_dict(d)


def unit_profile():
    d = deepcopy(measured_test_profile().data)
    d['machine'].update(g54_to_machine_xyz=[0, 0, 0], start_work_xyz=[0, 898, 35])
    d['motion'].update(air_xy_mm_min=5000, ordinary_travel_mm_min=5000, draw_mm_min=600,
        z_travel_mm_min=300, paper_approach_mm=5, paper_approach_mm_min=300,
        paper_contact_z_range=[-3, 0], paper_contact_mm_min=60, paper_release_mm_min=60,
        contact_mm_min=60, pressure_z_mm_min=120, park_xyz=[800, 800, 32],
        wet_loaded_mm_min=600, wet_departure_mm=5, wet_arrival_mm=5,
        wet_departure_mm_min=300, wet_arrival_mm_min=300,
        air_local_hover={'enabled': True, 'height_mm': 5}, air_station_roles=[],
        local_hover={'enabled': False, 'height_mm': 5, 'max_distance_mm': 10})
    d['brush_profiles']['ink']['knots'] = deepcopy(KNOTS)
    for role in ('ink', 'water'): d['stations'][role]['immersion_mm'] = 2
    d['stations']['water']['wash_cycles'] = 1
    d['stations']['sponge'].update(wipe_xy_mm=[0, 0], repetitions=1)
    d['stations']['C2'] = deepcopy(d['stations']['C1']); d['stations']['C2']['hardware_id'] = 'C2'
    return bind(d)


class IntegratedBenchmarkTests(unittest.TestCase):
    def test_handoff_records_confirmed_registration_without_inventing_contacts_or_stops(self):
        p = execution_profile(ROOT); r = execution_request(ROOT)
        validate(r, p, 'air', physical=False)
        self.assertEqual(p.data['machine']['start_work_xyz'], [0, 898, 35])
        self.assertEqual(p.data['stations']['A2']['center_xy'], [824.5, 554.5])
        self.assertEqual(p.data['stations']['A2']['coordinate_frame'], 'G54')
        self.assertIsNone(p.data['stations']['A2']['liquid_reference_z'])
        self.assertIsNone(p.data['stations']['A2']['bottom_z'])
        self.assertIsNone(p.data['stations']['ink']['deep_surface_xyz'])
        self.assertFalse(p.data['machine']['stopping']['physical_emergency_stop_installed'])
        self.assertFalse(p.evidence_passed('air_run'))
        self.assertFalse(p.evidence_passed('homing_limits_estop'))
        self.assertFalse(p.evidence_passed('motion_limits'))
        self.assertFalse(any('air_local_hover_clearance' in s for s in p.issues('air')))
        self.assertEqual(p.data['motion']['paper_contact_z_range'], [-3, 0])

    def depth_series(self):
        r = plan(ROOT)
        r.update(air_hover_mm=10, paint_trial='ink_a2_depth_series_40', color_slots=['A2'])
        d = deepcopy(unit_profile().data)
        d['motion'].update(air_local_hover={'enabled': False, 'height_mm': 5}, paper_contact_z_range=[-10, 0])
        d['stations']['A2'] = deepcopy(d['stations']['C1'])
        d['stations']['A2'].update(hardware_id='A2', center_xy=[824.5, 554.5],
                                    contact_box_xyz=[[814, 544, 5], [835, 565, 16]])
        for role in ('ink', 'water'):
            d['stations'][role].update(deep_surface_xyz=[700, 200, 5], shallow_surface_xyz=[700, 220, 9],
                                      contact_box_xyz=[[680, 180, 0], [720, 260, 12]])
        # These invented station values exist ONLY inside this unit fixture.
        return r, bind(d)

    def test_z10_air_keeps_sources_and_has_no_local_or_contact_dependencies(self):
        r, p = self.depth_series()
        original_sources = deepcopy(r['sources'])
        d = deepcopy(p.data); d['brush_profiles'] = {}; d['machine']['junction_deviation_mm'] = None
        d['evidence'] = [e for e in bind(d).data['evidence'] if e['check'] != 'air_local_hover_clearance']
        p = Profile.from_dict(d)
        commands, metrics = build(r, p, 'air')
        self.assertTrue(all(c.xyz[2] >= 10 for c in commands if c.kind == 'move'))
        self.assertEqual(metrics['M0_count'], 0)
        self.assertEqual(commands[-2].xyz, (800, 800, 32))
        self.assertEqual(sum(c.action == 'park' for c in commands), 1)
        self.assertEqual(r['sources'], original_sources)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)/'air'
            export_integrated(r, p, 'air', auth(p, r, 'air', ['BENCHMARK_AIR']), out)
            self.assertTrue(verify_export(out)['regenerated_from_authorized_plan'])
        bad = deepcopy(p.data); bad['motion']['air_local_hover']['enabled'] = True
        with self.assertRaisesRegex(ValueError, 'disabled Air local hover'): build(r, bind(bad), 'air')

    def test_40_strokes_four_columns_automatic_reload_and_ordered_inspection(self):
        r, p = self.depth_series(); commands, metrics = build(r, p, 'paint')
        strokes = [c for c in commands if c.action == 'draw' and c.kind == 'move']
        self.assertEqual(len(strokes), 40)
        expected = list(range(-1, -11, -1)) + list(range(-10, 0))
        self.assertEqual([c.xyz[2] for c in strokes], expected * 2)
        self.assertEqual(metrics['M0_count'], 27)
        for depth in (-9, -10):
            self.assertEqual(sum(f'BEFORE depth {depth} mm' in s for s in metrics['M0_reasons']), 4 if depth == -10 else 2)
        markers = [c.message for c in commands if c.action == 'depth_trial']
        self.assertEqual(markers, ['ink']*20 + ['A2']*20)
        loads = [c for c in commands if c.action == 'pigment_load']
        self.assertEqual(len(loads), 4)
        self.assertEqual(sum(c.action == 'wash' for c in commands), 1)
        self.assertTrue(all(c.feed_mm_min <= 600 for c in strokes))
        self.assertEqual(commands[-2].xyz, (800, 800, 32))
        for column in range(4):
            lines = depth_column(column)['brush_lines']
            self.assertTrue(all(10 <= v <= 320 for l in lines for k in ('start_xy', 'end_xy') for v in l[k]))
        # Exported synthetic bytes must independently regenerate from the plan.
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)/'paint'
            export_integrated(r, p, 'paint', auth(p, r, 'calibration', ['BENCHMARK_PAINT']), out)
            result = verify_export(out)
            self.assertTrue(result['regenerated_from_authorized_plan'])
            self.assertEqual((out/'BENCHMARK_PAINT.gcode').read_text().splitlines().count('M0'), 27)

    def test_40_stroke_unsafe_depth_slope_start_air_result_and_stopping_still_block(self):
        r, p = self.depth_series()
        for mutation, error in (
            (lambda d: d['motion'].update(paper_contact_z_range=[-3, 0]), 'test envelope'),
            (lambda d: d['machine'].update(start_work_xyz=[800, 800, 32]), 'explicitly rehomed'),
            (lambda d: d['stations']['ink'].update(shallow_surface_xyz=[700, 190, 9]), 'Y\\+'),
            (lambda d: d['motion']['local_hover'].update(enabled=True), 'disables production local hover')):
            d = deepcopy(p.data); mutation(d)
            with self.assertRaisesRegex(ValueError, error): build(r, bind(d), 'paint')
        for check, kind in (('air_run', 'paint'), ('homing_limits_estop', 'air'), ('motion_limits', 'air')):
            d = deepcopy(p.data); d['evidence'] = [e for e in d['evidence'] if e['check'] != check]
            with self.assertRaisesRegex(ValueError, check): build(r, Profile.from_dict(d), kind)

    def test_confirmed_controller_facts_and_source_plans_preserved_without_auto_air_pass(self):
        p = configured_profile(ROOT); r = plan(ROOT); f = facts(ROOT)
        self.assertEqual(p.data['machine']['g54_to_machine_xyz'], [0, 0, 0])
        self.assertIn('v4.1.1', p.data['machine']['firmware_version'])
        self.assertEqual(p.data['machine']['start_work_xyz'], [0, 898, 35])
        self.assertTrue(p.evidence_passed('installed_controller')); self.assertTrue(p.evidence_passed('g54_registration'))
        self.assertTrue(p.evidence_passed('park')); self.assertTrue(p.evidence_passed('paper_hover'))
        self.assertFalse(p.evidence_passed('air_run')); self.assertFalse(p.evidence_passed('homing_limits_estop'))
        self.assertEqual(f['candidates']['deep_floor_bed_z_mm'], 6)
        for name, source in r['sources'].items():
            self.assertEqual(source['plan'], json.loads((ROOT/'benchmarks/commissioning_330_v01/plans'/f'{name}.json').read_text()))
        self.assertEqual(r['recipe']['pigment_mass_g'], None)
        self.assertEqual(configured_profile(ROOT, 'paint').data['machine']['start_work_xyz'], [800, 800, 32])

    def test_air_exports_without_wet_contact_curve_or_junction_measurements(self):
        d = deepcopy(unit_profile().data)
        d['machine']['junction_deviation_mm'] = None; d['brush_profiles'] = {}
        for key in ('wet_max_xy_acceleration_mm_s2', 'contact_max_z_acceleration_mm_s2',
                    'wet_departure_mm', 'wet_arrival_mm', 'paper_approach_mm', 'station_approach_mm_min',
                    'paper_contact_mm_min', 'paper_release_mm_min', 'pressure_z_mm_min', 'draw_mm_min'):
            d['motion'][key] = None
        p = bind(d); r = plan(ROOT)
        self.assertFalse(p.issues('air'))
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)/'air'; a = auth(p, r, 'air', ['BENCHMARK_AIR'])
            export_integrated(r, p, 'air', a, out)
            result = verify_export(out)
            self.assertEqual(result['jobs']['BENCHMARK_AIR']['M0_count'], 0)
            text = (out/'BENCHMARK_AIR.gcode').read_text()
            self.assertIn('F5000.000000000', text); self.assertTrue(text.endswith('M2\n'))
            c = json.loads((out/'trajectory.json').read_text())
            self.assertTrue(all(v['xyz'][2] >= 5 for v in c if v['kind'] == 'move'))
            self.assertFalse(any(v['action'].startswith('station_') for v in c))

    def test_air_local_links_do_not_rebound_to_ten(self):
        commands, _ = build(plan(ROOT), unit_profile(), 'air')
        moves = [c for c in commands if c.kind == 'move']
        a = next(i for i, c in enumerate(moves) if c.xyz == (50, 250, 5))
        b = next(i for i, c in enumerate(moves[a+1:], a+1) if c.xyz == (55, 250, 5))
        self.assertTrue(all(c.xyz[2] == 5 for c in moves[a:b+1]))
        self.assertTrue(all(c.feed_mm_min == 5000 for c in moves if c.action == 'draw'))

    def test_air_local_and_station_evidence_are_required_separately(self):
        r = plan(ROOT); d = deepcopy(unit_profile().data)
        d['evidence'] = [e for e in d['evidence'] if e['check'] != 'air_local_hover_clearance']
        with self.assertRaisesRegex(ValueError, 'air_local_hover_clearance'): build(r, Profile.from_dict(d), 'air')
        r['air_station_roles'] = ['ink']; d = deepcopy(unit_profile().data); d['motion']['air_station_roles'] = ['ink']
        d['stations']['ink']['center_xy'] = [700, 200]
        with self.assertRaisesRegex(ValueError, 'Air station/corridor evidence'): build(r, bind(d), 'air')
        p = bind(d, ('air_station_ink',)); commands, _ = build(r, p, 'air')
        self.assertTrue(any(c.action == 'station_air_only' for c in commands))
        self.assertTrue(all(c.xyz[2] >= 32 for c in commands if c.kind == 'move' and c.xyz[:2] == (700, 200)))
        # An Air-only cloth approach needs neither cloth contact height nor an
        # enabled cloth contact in the separate paint job.
        r['air_station_roles'] = ['sponge']; d['motion']['air_station_roles'] = ['sponge']
        d['stations']['sponge']['surface_z'] = None
        build(r, bind(d, ('air_station_sponge',)), 'air')

    def test_real_partial_profile_and_false_authorization_never_create_gcode(self):
        p = configured_profile(ROOT); r = plan(ROOT)
        with tempfile.TemporaryDirectory() as t:
            for kind in ('air', 'paint'):
                out = Path(t)/kind
                with self.assertRaisesRegex(ValueError, 'EXPORT BLOCKED'): export_integrated(r, p, kind, {}, out)
                self.assertFalse(out.exists())
            p = unit_profile()
            a = auth(p, r, 'air', ['BENCHMARK_AIR']); a['explicit_operator_authorization'] = False
            with self.assertRaisesRegex(ValueError, 'authorization'): export_integrated(r, p, 'air', a, Path(t)/'noauth')
            self.assertFalse(list(Path(t).rglob('*.gcode')))

    def test_paint_reuses_stations_and_has_ten_ordered_inspections(self):
        p = unit_profile(); r = plan(ROOT); commands, metrics = build(r, p, 'paint')
        self.assertEqual(metrics['M0_count'], 10)
        self.assertTrue(commands[0].kind == 'pause')
        reasons = metrics['M0_reasons']
        self.assertTrue(any('BEFORE deeper -2' in s for s in reasons)); self.assertTrue(any('BEFORE deeper -3' in s for s in reasons))
        self.assertTrue(any('FIRST LIQUID' in s for s in reasons)); self.assertTrue(any('FIRST COLOR DIP' in s for s in reasons))
        self.assertFalse(any('CLOTH' in s for s in reasons))
        pressure = [c for c in commands if c.artistic_pressure is not None]
        samples = r['sources']['C_LOW']['plan']['pressure_lines'][0]['samples']
        self.assertEqual([c.artistic_pressure for c in pressure], [s['pressure'] for s in samples])
        self.assertTrue(all(c.xyz[2] >= -3 for c in commands if c.kind == 'move'))
        self.assertTrue(all(c.feed_mm_min <= 600 for c in commands if c.action == 'draw'))
        self.assertFalse(any(c.action == 'full_wash' for c in commands))
        self.assertTrue(any(c.action == 'station_wash' for c in commands))
        self.assertTrue(any(c.action == 'station_pigment_load' for c in commands))
        self.assertEqual(commands[-2].xyz, (800, 800, 32))
        pos = p.data['machine']['start_work_xyz']
        for c in commands:
            if c.kind == 'move':
                if c.action == 'travel' and pos[:2] != c.xyz[:2]:self.assertGreaterEqual(min(pos[2], c.xyz[2]), 5)
                pos = c.xyz

    def test_same_job_observations_do_not_persist_paper_contact_evidence(self):
        d = deepcopy(unit_profile().data); before = deepcopy(d); p = bind(d)
        self.assertFalse(p.evidence_passed('paper_contact'))
        build(plan(ROOT), p, 'paint')
        self.assertFalse(p.evidence_passed('paper_contact'))
        # No profile mutation, and legacy standalone pressure trials still need evidence.
        from datascape.gcode.production.calibration_jobs import validate_request
        with self.assertRaisesRegex(ValueError, 'paper_contact'):
            validate_request(plan(ROOT)['sources']['C_LOW']['plan'], p)

    def test_wet_acceleration_air_result_and_contact_envelope_remain_gated(self):
        r = plan(ROOT); d = deepcopy(unit_profile().data)
        d['motion']['wet_max_xy_acceleration_mm_s2'] = 1
        with self.assertRaisesRegex(ValueError, 'XY acceleration'): build(r, bind(d), 'paint')
        d = deepcopy(unit_profile().data); d['motion']['paper_contact_z_range'] = [-2, 0]
        with self.assertRaisesRegex(ValueError, 'test envelope'): build(r, bind(d), 'paint')
        d = deepcopy(unit_profile().data); d['evidence'] = [e for e in d['evidence'] if e['check'] != 'air_run']
        with self.assertRaisesRegex(ValueError, 'air_run'): build(r, Profile.from_dict(d), 'paint')

    def test_color_well_floor_guard_and_optional_cloth_are_not_bypassed(self):
        r = plan(ROOT); d = deepcopy(unit_profile().data); d['stations']['C1']['immersion_mm'] = 20
        with self.assertRaises(ValueError): build(r, bind(d), 'paint')
        r['include_cloth'] = True; r['color_slots'] = ['C1', 'C2']
        d = deepcopy(unit_profile().data)
        d['stations']['sponge']['material_overrides'] = {'ink': {'compression_mm': .25}, 'color': {'compression_mm': .5}}
        p = bind(d); commands, metrics = build(r, p, 'paint')
        self.assertEqual(metrics['M0_count'], 14)
        sponge = [c for c in commands if c.action == 'station_absorbent_contact']
        self.assertEqual(len(sponge), 2)
        xy = tuple(unit_profile().data['stations']['sponge']['center_xy'])
        self.assertTrue(all(c.xyz[:2] == xy for c in sponge))
        surface = p.data['stations']['sponge']['surface_z']
        self.assertEqual([c.xyz[2] for c in sponge], [surface - .25, surface - .5])

    def test_axis_reference_bounds_do_not_erode_home_but_keep_obstacles(self):
        m = deepcopy(unit_profile().data['machine'])
        m.update(machine_bounds_reference='axis_reference', machine_bounds_xyz=[[0, 0, -11], [850, 898, 35]])
        require_path((0, 898, 35), (15, 15, 35), m)
        with self.assertRaisesRegex(ValueError, 'unreachable'):require_path((0, 898, 35), (-.001, 898, 35), m)
        m['keepout_boxes'] = [[[2, 490, 34], [10, 510, 36]]]
        with self.assertRaisesRegex(ValueError, 'keepout'):require_path((0, 898, 35), (15, 15, 35), m)

    def test_exact_full_tool_segments_allow_no_invented_volume_or_radius(self):
        m = deepcopy(unit_profile().data['machine'])
        m.update(machine_bounds_reference='axis_reference', machine_bounds_xyz=[[0, 0, -11], [850, 898, 35]],
                 tool_envelope_margin_mm=None, validated_free_boxes=[],
                 validated_free_segments=[[[0, 898, 35], [15, 15, 35]]])
        require_path((0, 898, 35), (15, 15, 35), m)
        require_path((15, 15, 35), (0, 898, 35), m)
        with self.assertRaisesRegex(ValueError, 'corridors'):require_path((0, 898, 35), (16, 15, 35), m)
        m['keepout_boxes'] = [[[400, 400, 0], [410, 410, 20]]]
        with self.assertRaisesRegex(ValueError, 'tool envelope'):require_path((0, 898, 35), (15, 15, 35), m)

    def test_air_evidence_survives_later_wet_depths_but_not_dry_geometry_changes(self):
        d = deepcopy(unit_profile().data); p = bind(d)
        d['evidence'] = deepcopy(p.data['evidence'])
        d['motion']['paper_contact_mm_min'] = 70; d['stations']['ink']['liquid_reference_z'] += .1
        d['machine']['start_work_xyz'] = [800, 800, 32]
        d['machine']['validated_free_segments'] = [[[800, 800, 32], [700, 200, 32]]]
        self.assertTrue(Profile.from_dict(d).evidence_passed('air_run'))
        d['motion']['air_local_hover']['height_mm'] = 3
        self.assertFalse(Profile.from_dict(d).evidence_passed('air_run'))

    def test_delivered_gcode_is_regenerated_and_unmanifested_gcode_rejected(self):
        r = plan(ROOT); p = unit_profile()
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)/'paint'; a = auth(p, r, 'calibration', ['BENCHMARK_PAINT'])
            export_integrated(r, p, 'paint', a, out); self.assertTrue(verify_export(out)['regenerated_from_authorized_plan'])
            text = (out/'BENCHMARK_PAINT.gcode').read_text(); self.assertTrue(text.endswith('M2\n')); self.assertEqual(text.splitlines().count('M0'), 10)
            trajectory = json.loads((out/'trajectory.json').read_text())
            i = next(i for i,c in enumerate(trajectory) if c['artistic_pressure'] is not None)
            trajectory[i]['xyz'][2] -= .01
            (out/'trajectory.json').write_text(json.dumps(trajectory))
            hashes = json.loads((out/'MANIFEST_SHA256.json').read_text())
            hashes['trajectory.json'] = hashlib.sha256((out/'trajectory.json').read_bytes()).hexdigest()
            (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError, 'authorized plan'):verify_export(out)
            (out/'unexpected.gcode').write_text('M2\n')
            with self.assertRaisesRegex(ValueError, 'unmanifested'):verify_export(out)


if __name__ == '__main__': unittest.main()
