"""Separate experimental execution manifests; canonical Stroke records stay locked."""
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
import json
from ..binding import digest, PAYLOAD_SHA, SIDECAR_SHA
from ..motion import fragments
from ..validation import validate_layout

SLOT_ORDER = ('C1', 'D1', 'A2', 'D2', 'C2', 'A4', 'A3', 'A5', 'C3', 'D4', 'C4', 'D5')
ORDER_SHA = '7c8c8dc60cab365294bdee76911e58e6b573117a409e0345b0974de9acea520d'
REFERENCE_SHA = 'df46a0aed239813af6b79f082b0551a447ca7198d421e28e8d8609b2b8d9c48f'


def source_hash(strokes):
    return digest([asdict(s) for s in strokes])


def reference_order(strokes, path):
    d = json.loads(Path(path).read_text())
    if (d['bound_payload_sha256'] != PAYLOAD_SHA or d['pressure_sidecar_sha256'] != SIDECAR_SHA
            or d['v02_S3a_file_sha256'] != REFERENCE_SHA):
        raise ValueError('wrong pinned S3a reference')
    order = d['source_sequences']
    if digest(order) != ORDER_SHA: raise ValueError('execution order differs from verified v02 S3a bytes')
    if any(type(i) is not int for i in order) or sorted(order) != list(range(len(strokes))):
        raise ValueError('S3a must be an exact source permutation')
    if digest([strokes[i].stroke_id for i in order]) != d['ordered_source_ID_sha256']:
        raise ValueError('S3a ID binding mismatch')
    ink = [i for i, s in enumerate(strokes) if s.medium == 'ink']
    if order[:len(ink)] != ink: raise ValueError('ink order differs from frozen source')
    visits = []
    for i in order[len(ink):]:
        slot = strokes[i].color_slot
        if not visits or visits[-1] != slot: visits.append(slot)
    if tuple(visits) != SLOT_ORDER: raise ValueError('not twelve one-pass light-to-dark batches')
    return tuple(order)


def apply_color_order(strokes, reference, palette_order):
    used = {s.color_slot for s in strokes if s.medium == 'color'}
    if len(palette_order) != len(set(palette_order)) or set(palette_order) != used:
        raise ValueError('physical color order must list each used slot exactly once')
    return tuple([i for i in reference if strokes[i].medium == 'ink'] +
                 [i for slot in palette_order for i in reference if strokes[i].medium == 'color' and strokes[i].color_slot == slot])


def make_plan(strokes, layout, order, resume_after=None, palette_order=None):
    """A: four jobs. B/C: two shared jobs with panel provenance. D: two full jobs.

    Canonical sources are atomic for reload and restart even if they clip into
    several fragments. No service is inserted between shared source fragments.
    """
    if any(type(i) is not int for i in order) or sorted(order) != list(range(len(strokes))): raise ValueError('incomplete permutation')
    ink = [i for i,s in enumerate(strokes) if s.medium == 'ink']
    if list(order[:len(ink)]) != ink: raise ValueError('complete ink-first frozen order required')
    used = {s.color_slot for s in strokes if s.medium == 'color'}
    palette_order = tuple(c for c in SLOT_ORDER if c in used) if palette_order is None else tuple(palette_order)
    expected = apply_color_order(strokes, order, palette_order)
    if tuple(order) != expected: raise ValueError('S3a requires one visit per used color in configured order')
    rank = {strokes[i].stroke_id: n for n, i in enumerate(order)}
    groups = defaultdict(list)
    for f in fragments(strokes, layout):
        name = f'{f.setup}_{f.stroke.medium.upper()}'
        groups[name].append(f)
    jobs = {}; resume_after = resume_after or {}
    if set(resume_after) - set(groups): raise ValueError('unknown resume job')
    for name, fs in sorted(groups.items()):
        fs.sort(key=lambda f: (rank[f.stroke.origin_id], f.stroke.source_locations[0].arc_mm))
        units = []
        for f in fs:
            if not units or units[-1][0].stroke.origin_id != f.stroke.origin_id: units.append([])
            units[-1].append(f)
        if name in resume_after:
            matching = [i for i, unit in enumerate(units) if unit[0].stroke.origin_id == resume_after[name]]
            if len(matching) != 1: raise ValueError('resume must follow an exact complete source boundary')
            units = units[matching[0]+1:]
            if not units: raise ValueError('no remaining source units after resume boundary')
        jobs[name] = tuple(tuple(u) for u in units)
    manifest = {'schema': 'datascape.print_plan.v0.3', 'policy': 'S3a_experimental_artist_selected',
                'known_v02_audited_dependency_violations': 15220 if all(s.pressure_sidecar_sha256 == SIDECAR_SHA for s in strokes) and palette_order == SLOT_ORDER else None,
                'execution_palette_order': list(palette_order),
                'reference_S3a_file_sha256': REFERENCE_SHA if all(s.pressure_sidecar_sha256 == SIDECAR_SHA for s in strokes) else None,
                'canonical_source_sha256': source_hash(strokes), 'layout': asdict(layout),
                'canonical_data_modified': False, 'resume_after_source': dict(resume_after),
                'jobs': {name: [{'source_id': u[0].stroke.origin_id,
                    'original_sequence': u[0].stroke.sequence,
                    'fragments': [asdict(f) for f in u]} for u in units]
                    for name, units in jobs.items()}}
    return jobs, manifest


def pressure_distribution(strokes):
    """Available bound `layer` families only; no invented semantic hierarchy."""
    by = defaultdict(list)
    for s in strokes: by[(s.medium, s.layer)].extend(p.pressure for p in s.points)
    out = []
    for (medium, family), values in sorted(by.items()):
        v = sorted(values)
        def q(f):
            i = (len(v)-1)*f; n = int(i)
            return v[n] + (i-n)*(v[min(n+1, len(v)-1)]-v[n])
        out.append({'medium': medium, 'available_family_layer': family, 'samples': len(v),
                    'min': v[0], 'p10': q(.1), 'p25': q(.25), 'median': q(.5),
                    'p75': q(.75), 'p90': q(.9), 'max': v[-1],
                    'candidate_region_counts': [sum(x < .4 for x in v),
                        sum(.4 <= x < .6 for x in v), sum(x >= .6 for x in v)]})
    return out


def accepted_family_distribution(strokes, sidecar_path):
    """Read accepted sidecar family labels; never recompute pressure coefficients."""
    import gzip
    import hashlib
    raw = Path(sidecar_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SIDECAR_SHA:
        raise ValueError('not the accepted Pressure Intent sidecar')
    records = json.loads(gzip.decompress(raw))['strokes']
    if len(records) != len(strokes): raise ValueError('sidecar family completeness')
    family_strokes = []
    from dataclasses import replace
    for s, r in zip(strokes, records):
        if s.stroke_id != r['stroke_id'] or [p.pressure for p in s.points] != r['pressure_intent_samples']:
            raise ValueError('accepted family/sample binding mismatch')
        family_strokes.append(replace(s, layer=r['family']))
    return {'accepted_sidecar_sha256': SIDECAR_SHA, 'grouping': 'accepted_sidecar_family',
            'regions_are_provisional_not_Z_depths': True,
            'families': pressure_distribution(family_strokes)}


def verify_plan(manifest, strokes, layout):
    """Audit actual serialized plan geometry, material, arc and pressure bindings."""
    from math import isclose
    if manifest['canonical_source_sha256'] != source_hash(strokes):
        raise ValueError('serialized plan canonical hash mismatch')
    originals = {s.stroke_id:s for s in strokes}; seen = set(); samples = 0
    coverage = defaultdict(list)
    for job, units in manifest['jobs'].items():
        for unit in units:
            original = originals[unit['source_id']]; previous_arc = -1.
            for f in unit['fragments']:
                r = f['stroke']; panel = next(p for p in layout.panels if p.name == f['panel'])
                if r['stroke_id'] in seen: raise ValueError('duplicate written fragment')
                seen.add(r['stroke_id'])
                if not (r['source_id'] == original.stroke_id and r['sequence'] == original.sequence
                        and r['medium'] == original.medium and r['color_slot'] == original.color_slot
                        and r['pressure_sidecar_sha256'] == original.pressure_sidecar_sha256
                        and r['reorderable'] == original.reorderable and r['reversible'] == original.reversible):
                    raise ValueError('written canonical provenance differs')
                if not len(r['points']) == len(r['source_locations']) == len(f['work_xy']):
                    raise ValueError('written vertex coverage differs')
                for p, loc, xy in zip(r['points'], r['source_locations'], f['work_xy']):
                    a,b = original.points[loc['segment']:loc['segment']+2]; t=loc['t']
                    if not 0 <= t <= 1 or loc['arc_mm'] < previous_arc: raise ValueError('written traversal changed')
                    previous_arc = loc['arc_mm']
                    for k in ('x','y','pressure'):
                        if not isclose(p[k],getattr(a,k)+(getattr(b,k)-getattr(a,k))*t,abs_tol=1e-10,rel_tol=1e-12):
                            raise ValueError('written original sample interpolation differs')
                    if any(not isclose(q,w,abs_tol=1e-10) for q,w in zip(xy,layout.work_xy(panel,p['x'],p['y']))):
                        raise ValueError('written G54 transformation differs')
                    samples += 1
                for span in r['source_spans']:
                    coverage[(original.stroke_id,span['segment'])].append((span['t_start'],span['t_end']))
    if not manifest['resume_after_source']:
        for s in strokes:
            for i in range(len(s.points)-1):
                cursor = 0.
                for a,b in sorted(coverage[(s.stroke_id,i)]):
                    if not isclose(a,cursor,abs_tol=1e-12):raise ValueError('serialized span gap or duplication')
                    cursor = b
                if not isclose(cursor,1.,abs_tol=1e-12):raise ValueError('serialized source span incomplete')
    return {'written_fragment_count':len(seen),'written_pressure_samples':samples,
            'all_written_source_pressure_and_work_transform_bindings_verified':True,
            'complete_source_partition':not bool(manifest['resume_after_source'])}
