"""Atomic export gate, constrained G-code dialect and independent read-back."""
from dataclasses import asdict
from pathlib import Path
import gzip
import hashlib
import json
import os
import re
import shutil
import tempfile
from ..binding import digest, SIDECAR_SHA
from .profiles import authorize, Profile, require_physical_layout
from .trajectory import build_job, Builder, Materials, Command, require_path


def _comment(text):
    return '; ' + ''.join(c if 32 <= ord(c) < 127 else '?' for c in str(text))[:115].rstrip()


def _serialize(commands, profile, plan_hash, job_id, stage):
    lines = [_comment('DATASCAPE v0.3 '+stage+' '+job_id),
             _comment('PROFILE '+profile.sha256), _comment('PLAN '+plan_hash),
             _comment('EXPECTED G54 offset '+str(profile.data['machine']['g54_to_machine_xyz'])),
             _comment('EXPECTED initial work XYZ '+str(profile.data['machine']['start_work_xyz'])),
             _comment('BEFORE START verify G54/start, G92/TLO zero, feed override 100%, paper, brush and supplies'),
             'G21 G90 G94 G54']
    for c in commands:
        if c.kind == 'move':
            x, y, z = c.xyz
            lines.append(f'G1 X{x:.9f} Y{y:.9f} Z{z:.9f} F{c.feed_mm_min:.9f}')
        elif c.kind == 'dwell': lines.append(f'G4 P{c.seconds:.9f}')
        elif c.kind == 'pause':
            lines.append(_comment(c.message)); lines.append('M0')
        elif c.kind == 'marker':
            tag = '' if c.source_id is None else hashlib.sha256(c.source_id.encode()).hexdigest()[:16]
            lines.append(_comment(c.action+' '+tag))
        else: raise ValueError('unsupported command')
    lines.append('M2')
    text = '\n'.join(lines)+'\n'
    if stage == 'fixture':
        # Real serializer exercised, but fixtures remain non-executable examples.
        text = '; SYNTHETIC FIXTURE; NOT A MACHINE JOB\n' + ''.join('; '+line+'\n' for line in lines)
    return text


_MOVE = re.compile(r'G1 X(-?\d+\.\d+) Y(-?\d+\.\d+) Z(-?\d+\.\d+) F(\d+\.\d+)\Z')
_DWELL = re.compile(r'G4 P(\d+\.\d+)\Z')


def readback(text, commands, profile, stage):
    """Reject dialect drift, coordinate mutation, unexpected actions or contact in air."""
    if stage == 'fixture':
        lines = text.splitlines()[1:]
        if any(not line.startswith('; ') for line in lines): raise ValueError('executable fixture line')
        text = '\n'.join(line[2:] for line in lines)
    executable = [x for x in text.splitlines() if x and not x.startswith(';')]
    if not executable or executable[0] != 'G21 G90 G94 G54' or executable[-1] != 'M2':
        raise ValueError('invalid modal prologue/end')
    parsed = []; pos = tuple(profile.data['machine']['start_work_xyz'])
    for line in executable[1:-1]:
        if len(line) > 120: raise ValueError('controller line length exceeded')
        if m := _MOVE.fullmatch(line):
            x, y, z, f = map(float, m.groups()); xyz = (x, y, z)
            if f <= 0: raise ValueError('nonpositive feed')
            require_path(pos, xyz, profile.data['machine'])
            if stage == 'air' and z < profile.data['motion']['paper_hover_mm']-1e-9:
                raise ValueError('air run contains contact/negative Z')
            from math import dist
            length = dist(pos, xyz)
            if length and any(abs(q-p)/length*f > limit+1e-6 for p,q,limit in zip(pos,xyz,profile.data['machine']['axis_max_rate_mm_min'])):
                raise ValueError('serialized axis feed exceeds measured controller rate')
            parsed.append(('move', xyz, f)); pos = xyz
        elif m := _DWELL.fullmatch(line): parsed.append(('dwell', float(m.group(1))))
        elif line == 'M0': parsed.append(('pause',))
        else: raise ValueError('unapproved G-code command: '+line)
    expected = [c for c in commands if c.kind != 'marker']
    if len(expected) != len(parsed): raise ValueError('G-code/IR command coverage mismatch')
    position = tuple(profile.data['machine']['start_work_xyz'])
    for c, row in zip(expected, parsed):
        if row[0] != c.kind: raise ValueError('G-code action ordering mismatch')
        if c.kind == 'move':
            if any(abs(a-b) > 5.1e-10 for a, b in zip(c.xyz, row[1])) or abs(c.feed_mm_min-row[2]) > 5.1e-10:
                raise ValueError('serialized coordinate/feed differs from planned motion')
            from math import dist
            length = dist(position, row[1]); motion = profile.data['motion']
            if stage != 'calibration':
                from .timing import requested_feed
                cap = requested_feed((length, (), c.feed_mm_min, c.time_category,
                                      c.action, c.travel_state, c.travel_phase), motion)
                if row[2] > cap+1e-6: raise ValueError('serialized feed exceeds motion-policy cap')
            z_cap = motion['pressure_z_mm_min'] if c.action in ('draw','pressure_variation') else motion['z_travel_mm_min']
            if length and abs(row[1][2]-position[2])/length*row[2] > z_cap+1e-6:
                raise ValueError('serialized Z velocity exceeds calibrated limit')
            position = row[1]
        if c.kind == 'dwell' and abs(c.seconds-row[1]) > 5.1e-10:
            raise ValueError('serialized dwell mismatch')
    if stage == 'calibration' and expected[0].kind != 'pause':
        raise ValueError('calibration requires its explicit startup pause')
    return {'commands_verified': len(parsed), 'all_moves_reachable_and_in_corridors': True,
            'dialect_whitelist_verified': True,
            'M0_count': sum(c.kind == 'pause' for c in commands),
            'M0_reasons': [c.message for c in commands if c.kind == 'pause'],
            'production_verification_occurs_before_start': stage != 'calibration'}


def save_json(path, value):
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = Path(path)
    if path.suffix == '.gz': path.write_bytes(gzip.compress(text.encode(), mtime=0))
    else: path.write_text(text)


def _atomic_output(output, write):
    output = Path(output).resolve()
    if output.exists(): raise ValueError('output must be new; existing jobs are never overwritten')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.datascape-stage-', dir=output.parent))
    try:
        report = write(temp)
        # Exact artifact hashes bind all IR, G-code, profiles and authorizations.
        hashes = {str(p.relative_to(temp)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(temp.rglob('*')) if p.is_file()}
        save_json(temp/'MANIFEST_SHA256.json', hashes)
        os.rename(temp, output)
        return report
    finally:
        if temp.exists(): shutil.rmtree(temp)


def export_jobs(jobs, manifest, profile, stage, authorization, output, selected_jobs=None):
    if stage not in ('fixture', 'air', 'painting'): raise ValueError('use separate calibration exporter')
    if stage != 'fixture' and manifest['layout']['mode'] in ('B','C'):
        raise ValueError('shared-session plans remain offline: physical v0.3 supports separate panel jobs (A) or continuous ink/color jobs (D); B/C remain planning-only')
    names = list(selected_jobs) if selected_jobs is not None else list(jobs)
    if not names or len(set(names)) != len(names) or set(names)-set(jobs): raise ValueError('invalid job selection')
    selected = {name: jobs[name] for name in names}
    slots = sorted({f.stroke.color_slot for units in selected.values() for u in units for f in u if f.stroke.medium == 'color'})
    media = sorted({f.stroke.medium for units in selected.values() for u in units for f in u})
    profile.require(stage, slots, media)
    require_physical_layout(profile, manifest, stage)
    plan_hash = digest(manifest)
    authorize(authorization, profile, plan_hash, stage, names)
    if stage == 'fixture' and any(f.stroke.pressure_sidecar_sha256 == SIDECAR_SHA
                                 for units in selected.values() for u in units for f in u):
        raise ValueError('synthetic physical profiles must not serialize real Spring jobs')
    # All jobs are planned AND validated before any final output is installed.
    def write(root):
        save_json(root/'plan.json.gz', manifest); save_json(root/'profile.json', profile.data)
        save_json(root/'authorization.json', authorization)
        reports = {}
        for name, units in selected.items():
            commands, metrics = build_job(profile, units, stage)
            text = _serialize(commands, profile, plan_hash, name, stage)
            verification = readback(text, commands, profile, stage)
            verification.update(verify_draw_lineage(commands, manifest['jobs'][name], profile, stage))
            suffix = '.example.txt' if stage == 'fixture' else '.nc'
            (root/(name+suffix)).write_text(text)
            save_json(root/(name+'.trajectory.json.gz'), [asdict(c) for c in commands])
            # Restart only from a completed ORIGINAL source; suffix regeneration
            # starts from the verified position with fresh pre-run confirmation/load.
            save_json(root/(name+'.restart.json'), {'plan_sha256': plan_hash,
                'allowed_resume_after_source_ids': [u[0].stroke.origin_id for u in units[:-1]],
                'arbitrary_line_resume_supported': False})
            reports[name] = {'metrics': metrics, 'readback': verification}
        report = {'schema': 'datascape.export_report.v0.3', 'stage': stage,
                  'profile_sha256': profile.sha256, 'plan_sha256': plan_hash,
                  'jobs': reports, 'hardware_executed': False}
        save_json(root/'report.json', report)
        return report
    return _atomic_output(output, write)


def export_calibration(request, profile, authorization, output):
    """Small explicit station/constant-Z tests; never substitutes Spring pressure."""
    if request.get('schema') != 'datascape.calibration_plan.v0.3': raise ValueError('unknown calibration plan')
    if set(request)-{'schema', 'station_roles', 'brush_lines', 'notes'}: raise ValueError('unknown calibration request fields')
    roles = request.get('station_roles', []); lines = request.get('brush_lines', [])
    if not roles and not lines: raise ValueError('empty calibration plan')
    profile.require('calibration', roles)
    plan_hash = digest(request); authorize(authorization, profile, plan_hash, 'calibration', ['CALIBRATION'])
    def write(root):
        b = Builder(profile)
        b.commands.append(Command('pause', 'startup_verification', message='CALIBRATION ONLY: verify G54/MPos/start; manual load; explicit contact test limits; abort on mismatch'))
        material = Materials(b)
        for role in roles:
            b.pause('INSPECT '+role+' and measured reference/geometry before this explicit station test')
            material.station(role, 'calibration_contact')
            b.pause('INSPECT station test result; abort before next test if uncertain')
        for i, line in enumerate(lines):
            if set(line) != {'start_xy', 'end_xy', 'z_mm', 'feed_mm_min'}: raise ValueError('invalid brush calibration line')
            low, high = b.v['paper_contact_z_range']; z = line['z_mm']
            if not number(z) or not low <= z <= high: raise ValueError('calibration depth outside measured test envelope')
            if not vector(line['start_xy'], 2) or not vector(line['end_xy'], 2): raise ValueError('invalid test XY')
            b.pause('BRUSH TEST '+str(i)+': manually set recorded loading; inspect/measure width, continuity and recovery after test')
            b.xy(line['start_xy'], b.v['station_clearance_mm'])
            x, y = line['start_xy']
            b.move((x, y, b.v['paper_hover_mm']), b.v['z_travel_mm_min'], 'paper_hover')
            b.move((x, y, b.v['paper_approach_mm']), b.v['paper_approach_mm_min'], 'approach')
            b.move((x, y, 0), b.v['paper_contact_mm_min'], 'initial_contact')
            b.move((x, y, z), b.v['paper_contact_mm_min'], 'calibration_compression')
            b.move((*line['end_xy'], z), line['feed_mm_min'], 'draw')
            b.move((*line['end_xy'], 0), b.v['paper_release_mm_min'], 'release')
            b.move((*line['end_xy'], b.v['paper_approach_mm']), b.v['paper_release_mm_min'], 'paper_release_clearance')
            b.lift(b.v['paper_hover_mm'])
        b.pause('CALIBRATION COMPLETE: record observations; do not automatically mark evidence passed')
        text = _serialize(b.commands, profile, plan_hash, 'CALIBRATION', 'calibration')
        result = {'stage': 'calibration', 'hardware_executed': False, 'metrics': b.result(),
                  'readback': readback(text, b.commands, profile, 'calibration')}
        (root/'CALIBRATION.nc').write_text(text)
        for n, d in [('plan', request), ('profile', profile.data), ('authorization', authorization),
                     ('report', result), ('trajectory', [asdict(c) for c in b.commands])]:
            save_json(root/(n+'.json'), d)
        return result
    return _atomic_output(output, write)

# Local import keeps the calibration request validator independent of CLI parsing.
from .profiles import number, vector


def verify_draw_lineage(commands, plan_units, profile, stage):
    expected = [(f, i, p) for unit in plan_units for f in unit['fragments']
                for i, p in enumerate(f['stroke']['points'])]
    actual = [c for c in commands if c.artistic_pressure is not None]
    if len(expected) != len(actual): raise ValueError('missing or extra serialized artistic sample')
    for (f, i, p), c in zip(expected, actual):
        s = f['stroke']; xy = f['work_xy'][i]
        z = profile.data['motion']['paper_hover_mm'] if stage == 'air' else profile.brush_for(s['medium'],s['color_slot']).z_for(p['pressure'])
        if not (c.source_id == s['source_id'] and c.fragment_id == s['stroke_id']
                and c.source_vertex == i and c.artistic_pressure == p['pressure']
                and tuple(c.xyz) == (*xy,z)):
            raise ValueError('trajectory changed canonical pressure, vertex traversal or G54 mapping')
    return {'all_artistic_pressure_samples_verified': len(actual),
            'all_draw_XYZ_synchronized_with_accepted_intent': True}


def verify_export(output):
    """Read and validate delivered artifacts after transfer, before manual sending."""
    root = Path(output); hashes = json.loads((root/'MANIFEST_SHA256.json').read_text())
    for name, sha in hashes.items():
        p = root/name
        if not p.resolve().is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError('export artifact hash/path mismatch: '+name)
    if any(str(p.relative_to(root)) not in hashes for p in root.rglob('*.nc')):
        raise ValueError('unmanifested executable file')
    report = json.loads((root/'report.json').read_text());stage = report['stage']
    profile = Profile.load(root/'profile.json');authorization = json.loads((root/'authorization.json').read_text())
    plan_path = root/('plan.json' if stage == 'calibration' else 'plan.json.gz')
    raw = plan_path.read_bytes();plan = json.loads(gzip.decompress(raw) if plan_path.suffix == '.gz' else raw)
    names = ['CALIBRATION'] if stage == 'calibration' else list(report['jobs'])
    authorize(authorization, profile, digest(plan), stage, names)
    if stage != 'calibration' and (report['profile_sha256'] != profile.sha256 or report['plan_sha256'] != digest(plan)):
        raise ValueError('export report hash binding mismatch')
    results = {}
    for name in names:
        path = root/('trajectory.json' if stage == 'calibration' else name+'.trajectory.json.gz')
        raw = path.read_bytes();data = json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)
        commands = [Command(**c) for c in data]
        suffix = '.example.txt' if stage == 'fixture' else '.nc'
        results[name] = readback((root/(name+suffix)).read_text(), commands, profile, stage)
        if stage != 'calibration':
            results[name].update(verify_draw_lineage(commands,plan['jobs'][name],profile,stage))
    return {'artifact_hashes_verified':len(hashes), 'jobs':results, 'hardware_executed':False}
