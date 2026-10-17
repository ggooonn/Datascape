"""Golden archived vectors and unchanged accepted runtime, independent of old runners."""
from pathlib import Path
import hashlib,json
import pytest
from datascape.rendering.rock_ground_catalog import build

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/'docs/catalogs/rock_ground_v05/reference_manifest.json').read_text())

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

@pytest.fixture(scope='module')
def generated():return build()

def test_every_archived_source_and_final_record_matches(generated):
    for index,key in [(2,'final_state_sha256'),(3,'source_state_sha256')]:
        actual={name:digest(paths) for name,paths in generated[index].items()}
        assert actual==MANIFEST[key]

def test_accepted_runtime_bytes_are_preserved():
    for name,expected in MANIFEST['runtime_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected

def test_standalone_catalog_has_no_historical_runner_dependency():
    import ast
    for name in ['rock_ground_catalog.py','rock_ground_catalog_support.py','rock_ground_catalog_fixtures.py']:
        tree=ast.parse((ROOT/'src/datascape/rendering'/name).read_text())
        imports=[node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
        assert not any(m and m.endswith(('_study','rock_ground_study')) for m in imports)

def test_complete_fixture_regeneration_is_deterministic(generated):
    again=build()
    assert generated[2]==again[2] and generated[3]==again[3]
    assert generated[4]==again[4] and generated[6:]==again[6:]
