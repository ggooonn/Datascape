"""Accepted-data binding and fail-closed mutation checks, without source writes."""
from copy import deepcopy
from pathlib import Path
import math
import unittest
from unittest.mock import patch
from datascape import spring_pressure_intent as p


class PressureBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.machine = p.read(p.SNAPSHOT / p.MACHINE)
        cls.sidecar = p.read(p.SIDECAR)
        cls.rows = [r for m in ('ink', 'color') for r in
                    p.read(p.SNAPSHOT / f'visible_{m}.json.gz')['strokes']]
        cls.phases = p.read(p.SNAPSHOT / 'ordering.json')['phases']
        cls.limits = p.read(p.ROOT / 'studies/spring_pressure_full_v01/config.json')['limits']

    def test_complete_binding_and_all_pressure_replacement(self):
        before = p.digest(self.machine)
        derived, provenance = p.load_accepted()
        self.assertEqual(provenance['pressure_values'], 240974)
        self.assertEqual(provenance['historical_values_replaced'], 8975)
        self.assertEqual(provenance['placeholder_values_replaced'], 231999)
        self.assertEqual(len(derived['strokes']), 14951)
        self.assertFalse(provenance['fallback_permitted'])
        old_historical = new_historical = 0
        for old, new, side, row in zip(self.machine['strokes'], derived['strokes'],
                                        self.sidecar['strokes'], self.rows):
            self.assertEqual([v['pressure'] for v in new['points']], side['pressure_intent_samples'])
            self.assertEqual({k: v for k, v in old.items() if k != 'points'},
                             {k: v for k, v in new.items() if k != 'points'})
            self.assertEqual([{k: v for k, v in point.items() if k != 'pressure'} for point in old['points']],
                             [{k: v for k, v in point.items() if k != 'pressure'} for point in new['points']])
            if 'pressure_intent_samples' in row:
                old_historical += 1
                new_historical += [v['pressure'] for v in new['points']] != row['pressure_intent_samples']
        self.assertEqual((old_historical, new_historical), (675, 675))
        self.assertEqual(before, p.digest(self.machine))
        # Every pressure vector is separately allocated, with no alias into the sidecar/source.
        derived['strokes'][0]['points'][0]['pressure'] = -1
        self.assertNotEqual(self.machine['strokes'][0]['points'][0]['pressure'], -1)
        self.assertNotEqual(self.sidecar['strokes'][0]['pressure_intent_samples'][0], -1)

    def test_invalid_binding_rejected(self):
        kinds = ('missing_profile', 'missing_value', 'duplicate_ID', 'reordered_profiles',
                 'wrong_sequence', 'wrong_XY', 'wrong_width', 'wrong_source_hash',
                 'wrong_vertex_count', 'wrong_medium', 'wrong_slot', 'wrong_layer',
                 'wrong_group', 'reversal', 'reordering', 'historical_origin',
                 'old_pressure_in_machine_changed', 'outside_family_range', 'nan',
                 'boolean_pressure', 'missing_pressure_key', 'wrong_baseline',
                 'calibrated', 'wrong_historical_status')
        for kind in kinds:
            with self.subTest(kind=kind):
                machine = dict(self.machine, strokes=list(self.machine['strokes']))
                sidecar = dict(self.sidecar, strokes=list(self.sidecar['strokes']))
                rows = list(self.rows)
                s = machine['strokes'][0] = deepcopy(machine['strokes'][0])
                q = sidecar['strokes'][0] = deepcopy(sidecar['strokes'][0])
                r = rows[0] = deepcopy(rows[0])
                if kind == 'missing_profile': sidecar['strokes'].pop()
                elif kind == 'missing_value': q['pressure_intent_samples'].pop()
                elif kind == 'duplicate_ID': sidecar['strokes'][1] = q
                elif kind == 'reordered_profiles': sidecar['strokes'][:2] = sidecar['strokes'][1::-1]
                elif kind == 'wrong_sequence': q['sequence'] = 1
                elif kind == 'wrong_XY': s['points'][0]['x'] += .001
                elif kind == 'wrong_width': r['width_mm'] += .001
                elif kind == 'wrong_source_hash': q['source_record_sha256'] = '0' * 64
                elif kind == 'wrong_vertex_count': q['vertex_count'] += 1
                elif kind == 'wrong_medium': s['medium'] = 'color'
                elif kind == 'wrong_slot': s['color_slot'] = 'A1'
                elif kind == 'wrong_layer': s['layer'] = 'other'
                elif kind == 'wrong_group': s['order_group'] = 'other'
                elif kind == 'reversal': s['reversible'] = True
                elif kind == 'reordering': s['reorderable'] = True
                elif kind == 'historical_origin': q['pressure_origin'] = 'historical_experiment'
                elif kind == 'old_pressure_in_machine_changed': s['points'][0]['pressure'] = .4
                elif kind == 'outside_family_range': q['pressure_intent_samples'][0] = .99
                elif kind == 'nan': q['pressure_intent_samples'][0] = math.nan
                elif kind == 'boolean_pressure': q['pressure_intent_samples'][0] = True
                elif kind == 'missing_pressure_key': del q['pressure_intent_samples']
                elif kind == 'wrong_baseline': sidecar['baseline_commit'] = 'other'
                elif kind == 'calibrated': sidecar['calibrated'] = True
                elif kind == 'wrong_historical_status': q['source_pressure_status'] = 'fallback'
                with self.assertRaises((ValueError, KeyError)):
                    p.apply_profiles(machine, rows, self.phases, sidecar, self.limits)

    def test_corrupted_files_rejected_before_binding(self):
        original = p.file_sha
        targets = [p.SIDECAR, p.SNAPSHOT / 'MANIFEST_SHA256.json',
                   p.SNAPSHOT / 'visible_ink.json.gz',
                   p.ROOT / 'studies/spring_pressure_full_v01/config.json']
        for target in targets:
            with self.subTest(file=str(target)):
                def corrupted(path):
                    return '0' * 64 if Path(path) == target else original(path)
                with patch.object(p, 'file_sha', side_effect=corrupted):
                    with self.assertRaises(ValueError):
                        p.load_accepted()


if __name__ == '__main__':
    unittest.main()
