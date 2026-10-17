"""Frozen v10 vector references, independent of the compact review renderer."""
from pathlib import Path
import hashlib
import json
import unittest
from datascape.vegetation import tree_final_scale as gram


class CatalogAcceptanceTests(unittest.TestCase):
    def test_all_sixteen_accepted_reference_states_match_archived_vectors(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'docs/catalogs/tree_v10/reference_manifest.json').read_text())
        for state in manifest['reference_states']:
            with self.subTest(form=state['form'], height=state['nominal_height_mm']):
                tree = gram.make_tree(state['form'], height=state['nominal_height_mm'],
                                      root=state['root_mm'], seed=state['seed'],
                                      identity=state['identity'], profile=state['profile'])
                vectors = gram.vector_records(tree.marks, [tree])
                digest = hashlib.sha256(json.dumps(vectors, sort_keys=True, separators=(',', ':'),
                                                  allow_nan=False).encode()).hexdigest()
                self.assertEqual(digest, state['vectors_sha256'])
                self.assertEqual(len(vectors), state['paths'])
                self.assertEqual(sum(v['grammar_part'] == 'foliage-field' for v in vectors), state['leaf_paths'])


if __name__ == '__main__':
    unittest.main()
