"""Actual numeric review files never become measured/authorized machine exports."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.integrated_330_v01.numeric_review import export_review, verify_review_package, nominal_profile, NAMES
from benchmarks.integrated_330_v01.handoff import execution_request
from datascape.gcode.production.integrated_benchmark import export_integrated
from datascape.gcode.production.trajectory import station_points

ROOT = Path(__file__).resolve().parents[1]


class NumericReviewTests(unittest.TestCase):
    def test_real_commands_same_paths_readback_and_no_measured_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'review'; report = export_review(ROOT, out)
            self.assertTrue(verify_review_package(out)['shared_plan_regenerated'])
            for kind, name in NAMES.items():
                text = (out/(name+'.gcode')).read_text()
                self.assertIn('\nG1 X', text); self.assertTrue(text.endswith('M2\n'))
                self.assertNotIn('\nM0\n', text)
                self.assertEqual(report['jobs'][name]['stroke_count'], 40)
                self.assertFalse(report['jobs'][name]['collision_clearance_verified'])
                self.assertFalse(report['jobs'][name]['authorized_for_machine_execution'])
            p, assumptions = nominal_profile(ROOT)
            self.assertEqual(p.data['status'], 'nominal_review'); self.assertEqual(p.data['evidence'], [])
            self.assertEqual(assumptions['well_lowest_floor_bed_z_mm'], 5)
            self.assertEqual(p.data['stations']['ink']['liquid_reference_z'], 9)
            self.assertEqual(p.data['stations']['A2']['liquid_reference_z'], 6)
            for role in ('ink', 'water', 'A2'): self.assertIsNone(p.data['stations'][role]['contact_box_xyz'])

    def test_official_gates_and_calibrated_contact_volume_are_not_bypassed(self):
        p, _ = nominal_profile(ROOT)
        with self.assertRaises(ValueError): p.require('air')
        with self.assertRaises((ValueError, TypeError)): station_points(p.data['stations']['ink'])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'unauthorized'
            with self.assertRaises(ValueError): export_integrated(execution_request(ROOT), p, 'paint', {}, out)
            self.assertFalse(out.exists())

    def test_rehashed_numeric_mutation_and_missing_review_banner_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'review'; export_review(ROOT, out)
            path = out/'BENCHMARK_330_PAINT_REVIEW.gcode'
            original = path.read_text()
            for text in (original.replace('F5000.000000000', 'F5001.000000000', 1),
                         '\n'.join(original.splitlines()[1:])+'\n'):
                path.write_text(text)
                hashes = json.loads((out/'MANIFEST_SHA256.json').read_text())
                hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
                with self.assertRaisesRegex(ValueError, 'shared plan|banner'): verify_review_package(out)


if __name__ == '__main__': unittest.main()
