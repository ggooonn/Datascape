"""Integrity of the actual saved integration checkpoint and its provenance."""
import gzip
import json
from pathlib import Path
from shapely.geometry import LineString
from shapely.ops import substring
from datascape.rendering.spring_checkpoint import DEFAULT, ROOT, channels, verify


def test_saved_checkpoint_sources_owners_and_composites():
    manifest = verify()
    ink, sets = channels()
    assert len(ink) == 3067 and len(sets['caseB']) == 3650 and len(sets['caseC']) == 3094
    assert not any(r['source_family'] == 'V' for r in ink)
    sites = json.loads((DEFAULT / 'artifacts/sites.json').read_text())
    owners = {site['object_id'] for site in sites}
    assert len(owners) == 119 == manifest['counts']['temporary_authored_sites']
    assert all(r['owner_id'] in owners or r['owner_id'].startswith('baseline/') for r in ink)
    raw = json.loads(gzip.decompress((DEFAULT / 'artifacts/source_ledger.json.gz').read_bytes()))
    baseline = json.loads(gzip.decompress((ROOT / 'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz').read_bytes()))
    sources = {r['id']: r for r in baseline['strokes'] + raw['new_sources']}
    for record in ink:
        original = sources[record['source_stroke_id']]
        expected = substring(LineString(original['xy_mm']), *record['source_arc_mm'])
        assert expected.hausdorff_distance(LineString(record['xy_mm'])) < 1e-6
    assert sets['caseB'][:2309] == sets['caseC'][:2309]
