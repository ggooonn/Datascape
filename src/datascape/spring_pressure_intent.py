"""Fail-closed, offline-only binding of accepted Spring pressure to frozen XY.

Returns a new machine representation. No geometry, physical mapping or motion
code is generated; the frozen inputs and historical pressures are never edited.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'artworks/spring_v13'
CHECKPOINT = ROOT / 'artworks/spring_v13_pressure_intent_v01'
SIDECAR = CHECKPOINT / 'spring_v13.pressure_intent_v01.json.gz'
PIN = '67ba146b1213644d40bc9dabed9d52024d2bbe58'
PRESSURE_SHA256 = '0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e'
MACHINE = 'machine/spring_v13.offline.machine_vectors.json.gz'
WIDTH_KEYS = ('width_mm', 'width_profile_mm', 'expression', 'expressive_width_intent')


def require(condition, message):
    # Deliberately not assert: binding checks also run under python -O.
    if not condition:
        raise ValueError(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(obj) + b'\n'
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == '.gz' else data)


def apply_profiles(machine, rows, phases, sidecar, limits):
    """Validate every binding before copying/replacing every point pressure.

    Low-level in-memory API; use load_accepted() for file/hash verification.
    A missing profile/vertex/field raises; there is no pressure fallback.
    """
    require(machine['schema'] == 'datascape.machine_vectors.v0.1', 'machine schema')
    require(machine['artwork_size_mm'] == [600, 900], 'artwork size')
    require(sidecar['schema'] == 'datascape.pressure_intent.v0.1', 'pressure schema')
    require(sidecar['baseline_commit'] == PIN, 'baseline commit')
    require(sidecar['artwork_size_mm'] == [600, 900], 'pressure artwork size')
    require(sidecar['calibrated'] is False and sidecar['hardware_mapping'] is None,
            'artistic pressure only')
    require(sidecar['normalized_artistic_intent_only'] is True, 'pressure semantics')
    require(sidecar['offline_machine_placeholder_used'] is False, 'placeholder policy')
    ss = machine['strokes']; pp = sidecar['strokes']
    require(len(ss) == len(pp) == len(rows) == 14951, 'complete stroke count required')
    seen = set(); total = 0; historical = 0; historical_points = 0; bindings = []
    for seq, (s, p, r) in enumerate(zip(ss, pp, rows)):
        ident = r['id']; require(ident not in seen, 'duplicate ID: ' + ident); seen.add(ident)
        require(s['stroke_id'] == p['stroke_id'] == ident, 'ID/order binding: ' + ident)
        require(type(s['sequence']) is int and s['sequence'] == p['sequence'] == seq,
                'sequence: ' + ident)
        require(p['source_record_sha256'] == digest(r), 'source record hash: ' + ident)
        require(p['xy_sha256'] == digest(r['xy_mm']), 'XY hash: ' + ident)
        require(p['width_profile_sha256'] == digest({k: r[k] for k in WIDTH_KEYS if k in r}),
                'width/expression hash: ' + ident)
        points = s['points']; values = p['pressure_intent_samples']
        require(len(points) == len(values) == p['vertex_count'] == len(r['xy_mm']) >= 2,
                'vertex count: ' + ident)
        require([[v['x'], v['y']] for v in points] == r['xy_mm'], 'machine XY: ' + ident)
        require(all(len(xy) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in xy)
                    and 0 <= xy[0] <= 600 and 0 <= xy[1] <= 900 for xy in r['xy_mm']),
                'invalid geometry: ' + ident)
        require(any(a != b for a, b in zip(r['xy_mm'], r['xy_mm'][1:])), 'zero length: ' + ident)
        expected_medium = 'color' if 'palette_slot' in r else 'ink'
        require(s['medium'] == p['medium'] == expected_medium, 'medium: ' + ident)
        require(s['layer'] == p['layer'] == r['layer'], 'layer: ' + ident)
        require(s['color_slot'] == p['color_slot'] == r.get('palette_slot', 'INK'), 'slot: ' + ident)
        phase = next((v for v in phases if v['start'] <= seq < v['start'] + v['count']), None)
        require(phase is not None and s['order_group'] == p['order_group'] == phase['order_group'],
                'order group: ' + ident)
        require(all(v[k] is False for v in (s, p) for k in ('reorderable', 'reversible')),
                'direction/order lock: ' + ident)
        require(p['pressure_origin'] == 'new_painterly_pressure_intent_v01' and p['calibrated'] is False,
                'pressure provenance: ' + ident)
        old = r.get('pressure_intent_samples')
        expected_status = ('historical_experimental_recomputed' if old is not None
                           else 'no_historical_pressure_newly_computed')
        require(p['source_pressure_status'] == expected_status, 'historical provenance: ' + ident)
        # Validate the frozen input pressure too, but never use it in the output.
        expected_old = old if old is not None else [0.5] * len(points)
        require([v['pressure'] for v in points] == expected_old, 'frozen machine pressure: ' + ident)
        require(p['family'] in limits, 'unknown family: ' + ident)
        lo, hi = limits[p['family']]
        require(all(type(v) in (int, float) and math.isfinite(v) and 0 < v < 1 and lo <= v <= hi
                    for v in values), 'invalid pressure/family range: ' + ident)
        total += len(values)
        if old is not None:
            historical += 1; historical_points += len(values)
        bindings.append({k: p[k] for k in ('stroke_id', 'sequence', 'vertex_count', 'xy_sha256',
                         'width_profile_sha256', 'source_record_sha256', 'pressure_origin',
                         'source_pressure_status')})
    require(total == 240974 and historical == 675 and historical_points == 8975, 'total/provenance counts')
    result = deepcopy(machine)
    for s, p in zip(result['strokes'], pp):
        for point, value in zip(s['points'], p['pressure_intent_samples']):
            point['pressure'] = value
    require(all([v['pressure'] for v in s['points']] == p['pressure_intent_samples']
                for s, p in zip(result['strokes'], pp)), 'complete pressure replacement')
    provenance = dict(schema='datascape.pressure_intent.offline_binding.v01',
                      baseline_commit=PIN, pressure_sidecar_sha256=PRESSURE_SHA256,
                      strokes=14951, pressure_values=total, historical_profiles_replaced=historical,
                      historical_values_replaced=historical_points, placeholder_profiles_replaced=14276,
                      placeholder_values_replaced=231999, calibrated=False, hardware_mapping=None,
                      pressure_origin='new_painterly_pressure_intent_v01',
                      fallback_permitted=False, per_stroke=bindings)
    return result, provenance


def load_accepted(snapshot=SNAPSHOT, pressure=SIDECAR):
    snapshot = Path(snapshot); pressure = Path(pressure)
    acceptance = read(CHECKPOINT / 'acceptance.json')
    require(file_sha(pressure) == acceptance['sidecar_sha256'] == PRESSURE_SHA256,
            'accepted sidecar checksum')
    require(file_sha(snapshot / 'MANIFEST_SHA256.json') == acceptance['baseline_manifest_sha256'],
            'pinned baseline manifest checksum')
    source_manifest = read(snapshot / 'MANIFEST_SHA256.json')
    for name, expected in source_manifest.items():
        require(file_sha(snapshot / name) == expected, 'frozen source checksum: ' + name)
    config_path = ROOT / 'studies/spring_pressure_full_v01/config.json'
    sidecar = read(pressure); config = read(config_path)
    require(file_sha(config_path) == acceptance['config_sha256'] == sidecar['config_sha256'],
            'accepted coefficients checksum')
    require(digest(sidecar) == acceptance['sidecar_payload_sha256'], 'accepted payload checksum')
    rows = [r for m in ('ink', 'color') for r in read(snapshot / f'visible_{m}.json.gz')['strokes']]
    require(digest(rows) == acceptance['source_rich_records_sha256'], 'rich source aggregate checksum')
    phases = read(snapshot / 'ordering.json')['phases']; machine = read(snapshot / MACHINE)
    result, provenance = apply_profiles(machine, rows, phases, sidecar, config['limits'])
    provenance.update(frozen_machine_sha256=file_sha(snapshot / MACHINE),
                      baseline_manifest_sha256=acceptance['baseline_manifest_sha256'],
                      rich_source_sha256=digest(rows), config_sha256=sidecar['config_sha256'],
                      derived_machine_payload_sha256=digest(result))
    return result, provenance


def check_backend(machine_path, backend_directory):
    """Exercise only PR23 loader/models/scheduler; inspect every loaded pressure."""
    import sys
    from datascape.spring_checkpoint import backend_check
    report = backend_check(Path(machine_path), Path(backend_directory))
    loader = sys.modules['_spring_v13_contract_check.io'].load_strokes
    loaded = loader(machine_path)
    sidecar = read(SIDECAR)
    require(file_sha(SIDECAR) == PRESSURE_SHA256, 'canonical sidecar checksum')
    require(len(loaded) == len(sidecar['strokes']) == 14951, 'backend stroke count')
    for stroke, profile in zip(loaded, sidecar['strokes']):
        require(stroke.stroke_id == profile['stroke_id'], 'backend ID order')
        require([point.pressure for point in stroke.points] == profile['pressure_intent_samples'],
                'backend changed/missing pressure: ' + stroke.stroke_id)
    report.update(all_240974_loaded_pressures_equal_sidecar=True, fallback_used=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--pressure', type=Path, default=SIDECAR)
    parser.add_argument('--output', type=Path, help='New derived ordinary JSON; never frozen source')
    parser.add_argument('--provenance', type=Path, help='Separate derived binding provenance JSON')
    parser.add_argument('--backend-directory', type=Path, help='Optional PR23 gcode source directory; requires output')
    args = parser.parse_args()
    require(not args.backend_directory or bool(args.output), 'backend check requires derived output')
    require(bool(args.output) == bool(args.provenance), 'supply both output and provenance, or neither')
    if args.output:
        targets = [args.output.resolve(), args.provenance.resolve()]
        protected = [SNAPSHOT.resolve(), CHECKPOINT.resolve(), args.snapshot.resolve()]
        require(len(set(targets)) == 2 and all(not p.exists() for p in targets),
                'outputs must be distinct new files')
        require(all(not p.is_relative_to(root) for p in targets for root in protected),
                'outputs cannot overwrite frozen/checkpoint source directories')
        require(all(p.suffix == '.json' for p in targets), 'use ordinary JSON for PR23 loader/provenance')
    result, provenance = load_accepted(args.snapshot, args.pressure)
    if args.output:
        write(args.output, result); write(args.provenance, provenance)
    report = {k: v for k, v in provenance.items() if k != 'per_stroke'}
    if args.backend_directory:
        report['backend_check'] = check_backend(args.output, args.backend_directory)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
