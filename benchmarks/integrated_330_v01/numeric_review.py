"""Real G-code for offline review, distinct from authorized machine export.

Uses nominal geometry explicitly requested by the operator. No physical evidence,
clearance boxes or authorization records are created; official gates are unchanged.
"""
from collections import Counter
from dataclasses import asdict
from math import dist
from pathlib import Path
import hashlib
import json

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile, vector, number
from datascape.gcode.production.trajectory import _station_geometry
from datascape.gcode.production.integrated_benchmark import validate, render_continuous
from datascape.gcode.production.exporter import _serialize, _MOVE, _DWELL, _atomic_output, save_json
from benchmarks.commissioning_330_v01.preview import ReviewBuilder
from .handoff import execution_request, execution_profile

STATUS = 'OFFLINE_REVIEW_NOT_AUTHORIZED_NOT_PHYSICALLY_VALIDATED'
NAMES = {k: 'BENCHMARK_330_' + k.upper() + '_REVIEW' for k in ('air', 'paint')}
BANNER = '; OFFLINE REVIEW ONLY - REAL MOTION COMMANDS - NOT AUTHORIZED TO RUN\n'


def nominal_profile(root):
    d = execution_profile(root).data
    # Preserve actual controller/home facts; never invent a measured profile.
    d.update(status='nominal_review', profile_id='OPERATOR-REQUESTED-330-NOMINAL-REVIEW', evidence=[])
    d['machine']['paper_surface_above_bed_mm'] = 1
    d['motion'].update(station_approach_mm_min=3000, paper_contact_z_range=[-10, 0])
    assumptions = {
        'status': STATUS, 'paper_above_bed_mm': 1,
        'well_lowest_floor_bed_z_mm': 5, 'well_shallow_floor_bed_z_mm': 10,
        'well_liquid_bed_z_range_mm': [10, 11], 'selected_well_liquid_bed_z_mm': 10,
        'well_initial_immersion_mm': 2, 'well_minimum_nominal_floor_gap_mm': 2,
        'well_xy_rule': 'deep Y = registered lower Y + 10; shallow Y = deep Y + historical 45-mm slope length',
        'well_xy_status': 'calculated REVIEW placements only; region endpoints are NOT measured contact endpoints',
        'well_geometry_limit': 'registered Y span 65 and historical interior length105 are not reconciled measurements',
        'a2_floor_bed_z_mm': 2, 'a2_liquid_above_floor_mm': 5,
        'a2_liquid_G54_z_mm': 6, 'a2_initial_immersion_mm': 2,
        'a2_pattern': 'provisional circle radius1mm, one revolution, 24 segments; brush/rim fit unverified',
        'station_contact_feed_mm_min': 60, 'station_dwell_seconds': 1,
        'station_exit_above_liquid_mm': 2,
        'calculated_review_coordinates_G54': {
            'water': {'deep_floor': [840,230,4], 'shallow_floor': [840,275,9], 'dip': [840,230,7], 'withdrawal_end': [840,275,11]},
            'ink': {'deep_floor': [840,380,4], 'shallow_floor': [840,425,9], 'dip': [840,380,7], 'withdrawal_end': [840,425,11]},
            'A2': {'center_xy': [824.5,554.5], 'floor_z': 1, 'liquid_z': 6, 'dip_z': 4, 'exit_z': 8}},
        'high_speed_and_minus9_minus10': 'operator-requested; NOT physically verified',
        'collision_clearance_verified': False, 'hardware_executed': False,
    }
    for role, start in (('water', 220), ('ink', 370)):
        st = d['stations'][role]
        st.update(status='nominal_review', coordinate_frame='G54',
                  deep_surface_xyz=[840, start+10, 4], shallow_surface_xyz=[840, start+55, 9],
                  liquid_reference_z=9, immersion_mm=2, stone_gap_mm=1, exit_above_liquid_mm=2,
                  feed_mm_min=60, dwell_seconds=1, contact_box_xyz=None, agitation_cycles=0)
        st['nominal_bed_geometry'].update(deep_floor_z=5, shallow_floor_z=10, liquid_z_range=[10, 11])
    d['stations']['water'].update(wash_cycles=1, rewet_immersion_mm=2, rewet_dwell_seconds=1)
    d['stations']['A2'].update(status='nominal_review', bottom_z=1, liquid_reference_z=6,
        immersion_mm=2, bottom_gap_mm=1, pattern='circle', radius_mm=1, revolutions=1,
        segments_per_revolution=24, exit_above_liquid_mm=2, feed_mm_min=60, dwell_seconds=1,
        contact_box_xyz=None)
    d['notes'] = (STATUS + '. Numeric station placements and depths are calculated nominal references, '
                  'not measured clearances. No new passed evidence or free/contact volume is supplied. '
                  'Official machine authorization is separate and remains blocked.')
    return Profile.from_dict(d), assumptions


def check_move(start, target, feed, action, profile, kind):
    """Axis-reference envelope/rates only; NOT swept-brush or collision validation."""
    if not vector(target) or not number(feed, True): raise ValueError('nonfinite review move/feed')
    m, v = profile.data['machine'], profile.data['motion']
    for p in (start, target):
        mp = [x+o for x, o in zip(p, m['g54_to_machine_xyz'])]
        if any(not lo-1e-9 <= x <= hi+1e-9 for x, lo, hi in zip(mp, *m['machine_bounds_xyz'])):
            raise ValueError('review move outside configured machine axis envelope')
    if kind == 'air' and min(start[2], target[2]) < 10-1e-9:
        raise ValueError('Air review below paper no-contact plane')
    length = dist(start, target)
    if length:
        rates = [abs(y-x)/length*feed for x, y in zip(start, target)]
        if any(rate > cap+1e-6 for rate, cap in zip(rates, m['axis_max_rate_mm_min'])):
            raise ValueError('review exceeds installed axis feed limit')
        pressure = kind == 'paint' and action in ('draw', 'pressure_variation', 'calibration_compression',
                                                 'initial_contact', 'release', 'paper_release_clearance')
        if rates[2] > v['pressure_z_mm_min' if pressure else 'z_travel_mm_min']+1e-6:
            raise ValueError('review exceeds independent Z velocity limit')
    if action == 'draw' and feed != 5000: raise ValueError('benchmark stroke must retain F5000')


class NumericReviewBuilder(ReviewBuilder):
    def __init__(self, profile, kind):
        super().__init__(profile)
        self.kind = kind; self.lengths = Counter(); self.time_context = None
        self.in_paper = False; self.at_station = False; self.last_panel = None

    def move(self, target, feed, action, state='ordinary_travel', **lineage):
        check_move(self.position, target, feed, action, self.profile, self.kind)
        self.lengths['non_draw_mm'] += dist(self.position, target)
        super().move(target, feed, action, state, **lineage)


def build_review(request, profile, kind):
    validate(request, profile, kind, physical=False)
    if profile.data['status'] != 'nominal_review': raise ValueError('review requires explicitly nominal status')
    v = profile.data['motion']
    if (v['ordinary_travel_mm_min'], v['draw_mm_min'], v['wet_loaded_mm_min'], v['z_travel_mm_min'],
        v['pressure_z_mm_min'], v['paper_hover_mm'], v['station_clearance_mm'], v['air_station_top_mm']) != (
            8000, 5000, 8000, 3000, 2000, 10, 32, 35):
        raise ValueError('review policy differs from operator-requested fixed candidates')
    b = NumericReviewBuilder(profile, kind); loaded = None
    def contact(role, action):
        nonlocal loaded
        st = profile.data['stations'][role]
        def numeric_point(p):
            if not vector(p): raise ValueError('incomplete nominal station geometry')
            return tuple(p)
        dip, points = _station_geometry(st, numeric_point)
        state = 'ordinary_travel' if loaded is None else 'wet_loaded'
        # Same production station grammar without fabricating a calibrated box.
        b.xy(dip[:2], 32, state)
        b.move((*dip[:2], 32), profile.data['motion']['station_approach_mm_min'], 'station_approach')
        b.move(dip, st['feed_mm_min'], 'station_'+action)
        b.dwell(st['dwell_seconds'], action+'_dwell')
        for point in points: b.move(point, st['feed_mm_min'], 'station_'+action)
        b.lift(32); b.at_station = True; b.in_paper = False
        b.marker(action, role); loaded = role
    render_continuous(request, profile, b, kind, contact if kind == 'paint' else None)
    if any(c.kind not in ('move', 'dwell', 'marker') for c in b.commands):
        raise ValueError('numeric review must contain no unresolved actions or M0')
    return b.commands


def readback_review(text, commands, profile, kind):
    if not text.startswith(BANNER): raise ValueError('missing explicit unauthorized review banner')
    rows = [r for r in text.splitlines() if r and not r.startswith(';')]
    if rows[0] != 'G21 G90 G94 G54' or rows[-1] != 'M2': raise ValueError('review modal/end mismatch')
    expected = [c for c in commands if c.kind != 'marker']
    if len(rows)-2 != len(expected): raise ValueError('review command coverage mismatch')
    position = tuple(profile.data['machine']['start_work_xyz']); moves = 0
    for row, c in zip(rows[1:-1], expected):
        if c.kind == 'move':
            m = _MOVE.fullmatch(row)
            if not m: raise ValueError('review dialect/move mismatch')
            x, y, z, f = map(float, m.groups())
            if any(abs(a-b) > 5.1e-10 for a, b in zip((x,y,z,f), (*c.xyz,c.feed_mm_min))):
                raise ValueError('review coordinate/feed differs from shared plan')
            check_move(position, (x,y,z), f, c.action, profile, kind)
            position = (x,y,z); moves += 1
        elif c.kind == 'dwell':
            m = _DWELL.fullmatch(row)
            if not m or abs(float(m.group(1))-c.seconds) > 5.1e-10: raise ValueError('review dwell mismatch')
        else: raise ValueError('unexpected review action')
    strokes = [c for c in commands if c.action == 'draw']
    if len(strokes) != 40 or position != tuple(profile.data['motion']['park_xyz']): raise ValueError('stroke count/final park mismatch')
    return {'numeric_commands_read_back': len(expected), 'moves_read_back': moves,
            'configured_axis_reference_envelope_checked': True, 'axis_and_Z_rate_caps_checked': True,
            'stroke_count': 40, 'M0_count': 0, 'M2_verified': True,
            'start_G54_xyz': profile.data['machine']['start_work_xyz'], 'end_G54_xyz': list(position),
            'min_Z': min(c.xyz[2] for c in commands if c.kind == 'move'),
            'collision_clearance_verified': False, 'physically_validated': False,
            'controller_attained_speeds_verified': False,
            'authorized_for_machine_execution': False}


def xy_route(commands):
    out = []
    for c in commands:
        if c.kind == 'move' and (not out or out[-1] != c.xyz[:2]): out.append(c.xyz[:2])
    return out


def export_review(root, output):
    request = execution_request(root); profile, assumptions = nominal_profile(root)
    commands = {k: build_review(request, profile, k) for k in NAMES}
    if xy_route(commands['air']) != xy_route(commands['paint']): raise ValueError('Air/Paint XY routing mismatch')
    visits = lambda rows: [c.message for c in rows if c.action == 'benchmark_station_visit']
    if visits(commands['air']) != visits(commands['paint']): raise ValueError('Air/Paint visit order mismatch')
    def write(out):
        save_json(out/'plan.json', request); save_json(out/'profile.nominal.json', profile.data)
        save_json(out/'nominal_assumptions.json', assumptions)
        report = {'schema': 'datascape.numeric_gcode_review.v0.3', 'status': STATUS,
                  'plan_sha256': digest(request), 'nominal_profile_sha256': profile.sha256,
                  'same_40_stroke_plan_and_XY_route': True, 'station_visit_order': visits(commands['air']),
                  'physical_collision_validation_performed': False, 'authorized': False, 'jobs': {}}
        for kind, name in NAMES.items():
            text = (BANNER +
                    '; NOMINAL GEOMETRY / HIGH SPEED / MINUS9-MINUS10 NOT PHYSICALLY VERIFIED\n'
                    '; NO PASSED SAFETY EVIDENCE OR COLLISION-FREE CORRIDOR IS INFERRED\n' +
                    _serialize(commands[kind], profile, digest(request), name, 'offline_review'))
            (out/(name+'.gcode')).write_text(text)
            save_json(out/(name+'.trajectory.json'), [asdict(c) for c in commands[kind]])
            checked = readback_review((out/(name+'.gcode')).read_text(), commands[kind], profile, kind)
            save_json(out/(name+'.readback.json'), checked); report['jobs'][name] = checked
        save_json(out/'verification.json', report)
        (out/'README.md').write_text('''# Numeric G-code review package

These are actual G1/G4/M2 files with zero M0, NOT commented previews. They are
operator-requested offline review files, NOT authorized or physically validated.
Do not stream them as machine-approved programs. Official export gates remain
unchanged; no passed evidence, free-space box or calibrated contact volume was
created to produce these files.

Both modes use the same 40 strokes, XY route and material visit order. Start
after homing at G54 X0 Y898 Z35; final X800 Y800 Z32 and M2. Dry/wet-main XY8000,
stroke XY5000, noncontact Z3000, pressure-Z cap2000. Paper compression/release
use separate Spring candidates2000/2000; station contact60, dwell1s, dip2mm,
palette radius1mm/one circle are independent provisional review settings.

Air: paper Z10, station XY simulated at Z32 with Z35 approach. Paint: actual
numeric requested depths -1..-10 and -10..-1, automatic ink/water/A2 operations.
Calculated well deep Y = registered lower Y+10, shallow Y = lower Y+55. These
are REVIEW placements using the historical 45-mm slope, not measured endpoints.
Latest nominal well floor bed+5 overrides the earlier bed+6 reference. At nominal
paper bed+1, selected well liquid Z9 gives dipZ7; A2 liquidZ6 gives dipZ4. See
nominal_assumptions.json for every calculated contact coordinate and uncertainty.

Offline checks cover exact read-back, full configured axis-reference segment
envelope, per-axis feed/Z limits, 40 strokes, visit order, M0=0 and final M2.
They do NOT verify mounted-tool clearance, actual collision freedom, liquid
levels, high-speed dynamics, stopping or -9/-10 brush response. No controller
runtime estimate is represented as measured time.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.numeric_review --output NEW_DIR
Verify: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.numeric_review --output DIR --verify

Machine-authorized Air still needs independent physical stopping and Y-negative
motion verification, full paper/station/transfer tool clearance and explicit
stage authorization. Authorized Paint additionally needs actual Air outcome,
measured station contacts/floor gaps, -9/-10 checks, wet/contact dynamics and
pre-run approval. Established nominal fill levels are not requested again.
After results: calibrate existing profiles, full Spring Air, SHARED_INK/COLOR;
preserve Spring artwork, Pressure Intent and S3a.
''')
        return report
    return _atomic_output(output, write)


def verify_review_package(output):
    out = Path(output); hashes = json.loads((out/'MANIFEST_SHA256.json').read_text())
    actual = {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name != 'MANIFEST_SHA256.json'}
    if actual != set(hashes): raise ValueError('review manifest coverage mismatch')
    for name, expected in hashes.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest() != expected: raise ValueError('review SHA256 mismatch')
    request = json.loads((out/'plan.json').read_text()); profile = Profile.load(out/'profile.nominal.json')
    report = json.loads((out/'verification.json').read_text())
    if report.get('status') != STATUS or report.get('authorized') is not False or report.get('physical_collision_validation_performed') is not False:
        raise ValueError('review cannot assert authorization or physical collision validation')
    if report['plan_sha256'] != digest(request) or report['nominal_profile_sha256'] != profile.sha256:
        raise ValueError('review profile/plan binding mismatch')
    commands = {kind: build_review(request, profile, kind) for kind in NAMES}
    if xy_route(commands['air']) != xy_route(commands['paint']): raise ValueError('review XY route mismatch')
    for kind, name in NAMES.items():
        if digest(json.loads((out/(name+'.trajectory.json')).read_text())) != digest([asdict(c) for c in commands[kind]]):
            raise ValueError('review trajectory regeneration mismatch')
        checked = readback_review((out/(name+'.gcode')).read_text(), commands[kind], profile, kind)
        if checked != report['jobs'][name] or checked != json.loads((out/(name+'.readback.json')).read_text()):
            raise ValueError('review read-back report mismatch')
    return {'SHA256_files_checked': len(hashes), 'shared_plan_regenerated': True, 'authorized': False}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', required=True)
    ap.add_argument('--verify', action='store_true'); args = ap.parse_args()
    result = (verify_review_package(args.output) if args.verify else
              export_review(Path(__file__).resolve().parents[2], args.output))
    print(json.dumps(result, indent=2))
