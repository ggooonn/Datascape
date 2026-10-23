"""Two commissioning jobs composed from PR28 plans and existing motion primitives.

No device I/O. An M0 continuation is an operator decision, never stored evidence.
Unmeasured required contact sections block the entire paint export atomically.
"""
from dataclasses import asdict
from math import dist
import json
from pathlib import Path

from ..binding import digest
from .profiles import Profile, number, vector, authorize, require_pre_run
from .trajectory import Builder, Materials, Command, palette_pattern_xy
from .calibration_jobs import validate_request, render_calibration

SOURCE_IDS = ('A_STABILITY', 'B_DEPTH_1', 'B_DEPTH_2', 'B_DEPTH_3', 'C_LOW', 'D_HOVER')
KINDS = {'air': ('BENCHMARK_AIR', 'air'), 'paint': ('BENCHMARK_PAINT', 'calibration')}


def continuous(request):
    return request.get('execution_mode') == 'continuous_40'


def job_kind(request, kind):
    return (('BENCHMARK_330_' + kind.upper()), KINDS[kind][1]) if continuous(request) else KINDS[kind]


def benchmark_columns():
    """The identical source geometry and depth sequence for both execution modes."""
    return [dict(depth_column(i), brush_lines=[dict(line, feed_mm_min=5000)
                 for line in depth_column(i)['brush_lines']]) for i in range(4)]


def station_roles(request):
    return ['ink', 'water', *(['sponge'] if request['include_cloth'] else []), *request['color_slots']]


def validate(request, profile, kind, physical=True):
    if kind not in KINDS or request.get('schema') != 'datascape.integrated_benchmark.v0.3':
        raise ValueError('unknown integrated benchmark kind/schema')
    allowed = {'schema', 'substrate_mm', 'source_commit', 'sources', 'color_slots', 'include_cloth',
               'air_station_roles', 'recipe', 'notes'}
    optional = {'air_hover_mm', 'paint_trial', 'execution_mode', 'benchmark_columns'}
    if not allowed <= set(request) or set(request) - allowed - optional or request['substrate_mm'] != [330, 330]:
        raise ValueError('invalid integrated 330-mm request')
    if 'air_hover_mm' in request and request['air_hover_mm'] != 10:
        raise ValueError('explicit Air-only hover override must be Z10')
    if 'paint_trial' in request and request['paint_trial'] != 'ink_a2_depth_series_40':
        raise ValueError('unknown integrated paint trial')
    series = request.get('paint_trial') == 'ink_a2_depth_series_40'
    paired = continuous(request)
    if 'execution_mode' in request and not paired:
        raise ValueError('unknown benchmark execution mode')
    if paired and (not series or request.get('air_hover_mm') != 10 or
                   request.get('benchmark_columns') != benchmark_columns()):
        raise ValueError('continuous benchmark requires its shared 40-stroke source')
    if not paired and 'benchmark_columns' in request:
        raise ValueError('shared columns require continuous execution mode')
    if series and (request['color_slots'] != ['A2'] or request['include_cloth']):
        raise ValueError('40-stroke trial requires ink/A2 and no cloth')
    if request['source_commit'] != '29fccadc9a270afe65d46c7e8711c5c2ec0d8ea8':
        raise ValueError('integrated benchmark requires the pinned PR28 source')
    if set(request['sources']) != set(SOURCE_IDS): raise ValueError('incomplete PR28 source coverage')
    for name, source in request['sources'].items():
        if set(source) != {'sha256', 'plan'} or source['sha256'] != digest(source['plan']):
            raise ValueError('source plan binding mismatch: ' + name)
    colors = request['color_slots']
    if not isinstance(colors, list) or not 1 <= len(colors) <= 2 or len(set(colors)) != len(colors):
        raise ValueError('select one or two distinct color stations')
    if any(c not in profile.data['stations'] or profile.data['stations'][c].get('kind') != 'palette' for c in colors):
        raise ValueError('unknown representative palette')
    if type(request['include_cloth']) is not bool: raise ValueError('explicit optional cloth policy required')
    if profile.data['motion']['paper_hover_mm'] != 10:
        raise ValueError('this benchmark retains normal paper hover Z10')
    if series:
        if profile.data['motion'].get('local_hover', {}).get('enabled') is not False:
            raise ValueError('40-stroke trial disables production local hover')
        for column in range(4):
            validate_request(request['benchmark_columns'][column] if paired else depth_column(column),
                             profile, physical=physical and kind == 'paint')
    roles = request['air_station_roles']
    if not isinstance(roles, list) or len(roles) != len(set(roles)) or set(roles) - {'ink', 'water', 'sponge', *colors}:
        raise ValueError('invalid selected Air station roles')
    # Validate the source Air geometry with the existing independent adapter.
    from .benchmark import air_plan
    air_plan(request['sources']['A_STABILITY']['plan'])
    for name in SOURCE_IDS[1:]:
        part = request['sources'][name]['plan']
        validate_request(part, profile, physical=False, map_pressure=kind != 'air' and not series)
        if part.get('paper_region_xy') != [[10, 10], [320, 320]] or part.get('station_roles'):
            raise ValueError('source paper trial must remain independent of stations')
    for i in (1, 2, 3):
        lines = request['sources'][f'B_DEPTH_{i}']['plan'].get('brush_lines', [])
        if len(lines) != 1 or lines[0]['z_mm'] != -i:
            raise ValueError('retain progressive -1/-2/-3 mm contact trials')
    groups = request['sources']['D_HOVER']['plan'].get('hover_groups', [])
    if len(groups) != 2 or [g['hover_mm'] for g in groups] != [10, 5]:
        raise ValueError('retain normal 10 and local 5 mm comparison')
    if not request['sources']['C_LOW']['plan'].get('pressure_lines'):
        raise ValueError('retain low-pressure transition trial')
    if physical:
        if paired:
            v = profile.data['motion']
            if profile.data['machine'].get('stopping', {}).get('independent_power_stop_verified') is not True:
                raise ValueError('continuous benchmark requires a verified USB-independent physical power stop')
            if profile.data['machine']['start_work_xyz'] != [0, 898, 35]:
                raise ValueError('continuous benchmark starts at rehomed X0 Y898 Z35')
            if (v.get('ordinary_travel_mm_min'), v.get('draw_mm_min'), v.get('air_xy_mm_min'),
                v.get('wet_loaded_mm_min'), v.get('z_travel_mm_min')) != (8000, 5000, 5000, 8000, 3000):
                raise ValueError('continuous benchmark requires approved XY8000/draw5000/wet8000/noncontact-Z3000 policy')
            if roles != ['ink', 'water', 'A2'] or v.get('air_local_hover', {}).get('enabled') is not False:
                raise ValueError('continuous benchmark requires all three station routes and no local hover')
            if v.get('benchmark_plan_sha256') != digest(request):
                raise ValueError('motion/evidence must bind the shared benchmark source plan')
            if not number(v.get('air_station_top_mm'), True) or v['air_station_top_mm'] < v['station_clearance_mm']:
                raise ValueError('verify elevated Air station simulation top and clearance')
            for key in ('wet_departure_mm', 'wet_arrival_mm', 'wet_departure_mm_min', 'wet_arrival_mm_min'):
                if not number(v.get(key), True): raise ValueError('approve dry-simulated travel policy: ' + key)
            cycles = profile.data['stations']['water'].get('wash_cycles')
            if type(cycles) is not int or cycles < 1: raise ValueError('approve shared wash-cycle count')
            for role in roles:
                dry_station_xy(profile.data['stations'][role])
            if kind == 'paint':
                for check in ('continuous_benchmark_contact', 'station_contacts', 'wet_motion'):
                    if not profile.evidence_passed(check):
                        raise ValueError('missing current-profile pre-run evidence: ' + check)
                check = 'continuous_benchmark_contact'
                if not any(e.get('check') == check and e.get('status') == 'passed'
                           and (e.get('scope_sha256') == profile.evidence_scope_sha256(check)
                                or e.get('calibration_sha256') == profile.calibration_sha256)
                           and isinstance(e.get('tested_depths_mm'), list)
                           and all(z in e['tested_depths_mm'] for z in (-9, -10))
                           for e in profile.data['evidence']):
                    raise ValueError('record actual -9/-10 compression checks before uninterrupted paint')
        if kind == 'air':
            profile.require('air', media=('ink',))
            local = profile.data['motion'].get('air_local_hover', {})
            if request.get('air_hover_mm') == 10:
                if local.get('enabled') is not False:
                    raise ValueError('Z10-only Air requires disabled Air local hover')
            elif local.get('enabled') is not True or local.get('height_mm') != 5:
                raise ValueError('integrated Air requires explicit verified 5-mm no-contact trial')
            if profile.data['motion'].get('air_station_roles', []) != roles:
                raise ValueError('selected Air station roles differ from profile')
            for role in roles:
                st = profile.data['stations'][role]
                if st.get('coordinate_frame') != 'G54' or (not paired and not vector(st.get('center_xy'), 2)):
                    raise ValueError('measure G54 center for selected Air station: ' + role)
                if not profile.evidence_passed('air_station_' + role):
                    raise ValueError('missing current-profile Air station/corridor evidence: ' + role + ' (air_station_' + role + ')')
        else:
            profile.require('calibration', station_roles(request))
            if any(profile.data['stations'][r]['immersion_mm'] != 2 for r in ('ink', 'water')):
                raise ValueError('initial integrated well trial uses 2-mm immersion; 3 mm is a later reviewed expansion')
            # The first three constant lines establish observations inside this
            # job. Each deeper trial and C_LOW has an unconditional inspect M0.
            # This does not auto-pass paper_contact for later production exports.
            if series:
                if profile.data['machine']['start_work_xyz'] != [0, 898, 35]:
                    raise ValueError('40-stroke trial starts from explicitly rehomed G54 X0 Y898 Z35')
                for role in ('ink', 'water'):
                    st = profile.data['stations'][role]
                    deep, shallow = st['deep_surface_xyz'], st['shallow_surface_xyz']
                    if shallow[1] <= deep[1] or shallow[2] <= deep[2]:
                        raise ValueError(role + ': measured withdrawal must proceed Y+ and rise above deeper floor')
            else:
                for name in SOURCE_IDS[1:]:
                    validate_request(request['sources'][name]['plan'], profile, physical=True,
                                     in_job_checks=('paper_contact',) if name in ('C_LOW', 'D_HOVER') else ())
                for role in request['color_slots']:
                    validate_request(color_marks(role, request['color_slots'].index(role)), profile, physical=True)
    return request


def depth_column(column):
    """Four separated 45-mm lines per row; actual brush spread still needs inspection."""
    x = (20, 100, 180, 260)[column]
    depths = range(1, 11) if column % 2 == 0 else range(10, 0, -1)
    return {'schema': 'datascape.calibration_plan.v0.3', 'paper_region_xy': [[10, 10], [320, 320]],
            'brush_lines': [{'start_xy': [x, 30 + 27*i], 'end_xy': [x+45, 30 + 27*i],
                             'z_mm': -depth, 'feed_mm_min': 600} for i, depth in enumerate(depths)],
            'notes': 'Automatic material load/reload; ascending or descending constant-depth series. '
                     '27-mm row pitch, 35-mm column gap; reject spreading/fixtures outside inspected corridors.'}


def color_marks(role, index):
    return {'schema': 'datascape.calibration_plan.v0.3', 'paper_region_xy': [[10, 10], [320, 320]],
            'brush_lines': [{'start_xy': [30, 290 + 20 * index], 'end_xy': [90, 290 + 20 * index],
                             'z_mm': -1, 'feed_mm_min': 600}],
            'notes': 'Short constant-compression mark after explicit ' + role + ' load; no artistic source.'}


def render_air(request, profile, b, include_pending=False):
    if continuous(request):
        return render_continuous(request, profile, b, 'air')
    v = profile.data['motion']
    simulation_feed = v.get('air_xy_mm_min', v['draw_mm_min'])
    b.marker('benchmark_air', 'No paper/liquid/cloth contact; explicit Z10 override or isolated local-hover trial')
    paths = request['sources']['A_STABILITY']['plan']['paths']
    for path in paths:
        b.marker('source_begin', path['id'], source_id=path['id'])
        b.xy(path['work_xy'][0], v['station_clearance_mm'] if path is paths[0] else v['paper_hover_mm'])
        b.move((*path['work_xy'][0], 10), v['z_travel_mm_min'], 'paper_hover')
        for i, xy in enumerate(path['work_xy']):
            b.move((*xy, 10), simulation_feed, 'draw', source_id=path['id'], source_vertex=i)
        b.marker('source_complete', path['id'], source_id=path['id'])
    for name in SOURCE_IDS[1:]:
        part = request['sources'][name]['plan']
        groups = part.get('hover_groups')
        if groups is not None:
            for group in groups:
                h = request.get('air_hover_mm', group['hover_mm'])
                for i, line in enumerate(group['strokes']):
                    xy = line['start_xy']
                    b.xy(xy, 10 if i == 0 else h)
                    b.move((*xy, h), v['z_travel_mm_min'], 'paper_hover')
                    b.move((*line['end_xy'], h), simulation_feed, 'draw', source_id=name)
                    # Local links remain at h; never rebound to 10 between strokes.
                b.move((*group['strokes'][-1]['end_xy'], 10), v['z_travel_mm_min'], 'retract')
        else:
            lines = [([line['start_xy'], line['end_xy']], None) for line in part.get('brush_lines', [])]
            lines += [([s['xy'] for s in line['samples']], line['samples']) for line in part.get('pressure_lines', [])]
            for xy, samples in lines:
                b.xy(xy[0], 10)
                b.move((*xy[0], 10), v['z_travel_mm_min'], 'paper_hover')
                for i, point in enumerate(xy):
                    b.move((*point, 10), simulation_feed, 'draw', source_id=name, source_vertex=i,
                           artistic_pressure=None if samples is None else samples[i]['pressure'])
    for i, role in enumerate(request['color_slots']):
        line = color_marks(role, i)['brush_lines'][0]
        b.xy(line['start_xy'], 10)
        b.move((*line['start_xy'], 10), v['z_travel_mm_min'], 'paper_hover')
        b.move((*line['end_xy'], 10), simulation_feed, 'draw', source_id='color-' + role)
    for role in request['air_station_roles']:
        st = profile.data['stations'][role]
        if vector(st.get('center_xy'), 2):
            b.xy(st['center_xy'], v['station_clearance_mm'])
            b.move((*st['center_xy'], v['station_clearance_mm']), v['z_travel_mm_min'], 'paper_hover')
            b.marker('station_air_only', role)
        elif include_pending:
            b.commands.append(Command('unresolved', 'air_station_center', message=role))
        else: raise ValueError('unmeasured selected Air center')
    if include_pending:
        for role in station_roles(request):
            if role not in request['air_station_roles']:
                b.commands.append(Command('unresolved', 'omitted_air_station',
                    message=role + ': offline reference only; measured XY and complete corridor/evidence required'))
    b.park()


def render_paint(request, profile, b, station_contact=None):
    if continuous(request):
        return render_continuous(request, profile, b, 'paint', station_contact)
    if request.get('paint_trial') == 'ink_a2_depth_series_40':
        return render_depth_series(request, profile, b, station_contact)
    # Caller validates every section BEFORE serialization; M0 is no substitute
    # for missing floor, liquid, clearance, contact envelope or authorization.
    b.commands.append(Command('pause', 'startup_verification', message=
        'INTEGRATED CALIBRATION: verify registered start, approved contact envelope and all supplies; abort on mismatch'))
    material = Materials(b)
    contact = station_contact or (lambda role, action, material_key=None: material.station(role, action, material_key))
    def inspect(reason): b.pause('INSPECT: ' + reason + '; continue ONLY if passed, otherwise ABORT', material.state)
    inspect('FIRST LIQUID IMMERSION WELL_2: confirm measured level, 2-mm dip and floor gap')
    contact('ink', 'pigment_load'); material.loaded = 'ink'
    for i in (1, 2, 3):
        inspect(('ink loading and first paper contact at -1 mm' if i == 1 else
                 f'previous depth -{i-1} mm width, paper and recovery BEFORE deeper -{i} mm contact'))
        render_calibration(request['sources'][f'B_DEPTH_{i}']['plan'], profile, b, integrated=True)
    inspect('-3 mm result BEFORE low-pressure transitions; reject if any depth was unsafe')
    render_calibration(request['sources']['C_LOW']['plan'], profile, b, integrated=True)
    groups = request['sources']['D_HOVER']['plan']['hover_groups']
    for i, group in enumerate(groups):
        inspect('pressure/recovery BEFORE ordinary Z10 hover' if i == 0 else
                'ordinary-hover result and verified Z5 corridor BEFORE local hover')
        part = dict(request['sources']['D_HOVER']['plan'], hover_groups=[group])
        render_calibration(part, profile, b, integrated=True)
    def wash():
        previous_material = material.loaded
        inspect('FIRST/REPEAT WATER IMMERSION WELL_1: confirm wash geometry and controlled slope withdrawal')
        cycles = profile.data['stations']['water']['wash_cycles']
        if type(cycles) is not int or cycles < 1:
            if station_contact is None: raise ValueError('measured wash-cycle count required')
            b.commands.append(Command('unresolved', 'wash_cycles', message='Measured water wash-cycle count pending; single symbolic station placeholder follows'))
            contact('water', 'wash')
        else:
            for _ in range(cycles): contact('water', 'wash')
        material.loaded = 'water'
        if request['include_cloth']:
            inspect('CLOTH CONTACT: measured secured surface, compression and dwell')
            contact('sponge', 'absorbent_contact', previous_material)
    for i, role in enumerate(request['color_slots']):
        wash()
        inspect(('FIRST COLOR DIP ' if i == 0 else 'NEXT COLOR DIP ') + role +
                ': inspect cleaning, actual liquid level, loading depth and bottom gap')
        contact(role, 'pigment_load'); material.loaded = role
        b.marker('color_mark', role)
        render_calibration(color_marks(role, i), profile, b, integrated=True)
    b.park(material.state)
    b.marker('job_complete', 'Record final coordinates and observations; no automatic evidence pass')


def render_depth_series(request, profile, b, station_contact=None):
    """One wet job; automatic same-material reloads, progressive inspection at hover."""
    material = Materials(b)
    contact = station_contact or (lambda role, action: material.station(role, action))
    def inspect(reason):
        # Every paper line has already released to Z10; stations retract to Z32.
        # Keep the inspection there rather than parking and returning 27 times.
        if b.position[2] < profile.data['motion']['paper_hover_mm']:
            raise ValueError('inspection pause must be above verified paper hover')
        b.commands.append(Command('pause', 'manual_checkpoint', message=
            'INSPECT: ' + reason + '; continue ONLY if passed, otherwise ABORT; do not jog or change offsets'))
    inspect('FIRST LIQUID IMMERSION WELL_2: actual liquid level, 2-mm dip, floor gap and Y+ withdrawal')
    contact('ink', 'pigment_load'); material.loaded = 'ink'
    for column in range(4):
        role = 'ink' if column < 2 else 'A2'
        if column in (1, 3):
            inspect('previous series and same-material automatic reload ' + role)
            contact(role, 'pigment_load'); material.loaded = role
        if column == 2:
            inspect('FIRST WATER IMMERSION WELL_1: floor gap, measured Y+ rising withdrawal; inspect washed brush before A2')
            for _ in range(profile.data['stations']['water']['wash_cycles']):
                contact('water', 'wash')
            material.loaded = 'water'
            inspect('FIRST COLOR DIP A2: inspect cleaning, actual liquid level and bottom gap')
            contact('A2', 'pigment_load'); material.loaded = 'A2'
        part = depth_column(column)
        for index, line in enumerate(part['brush_lines']):
            if column % 2 == 0 or index == 0:
                inspect(f'{role} column {column+1} BEFORE depth {line["z_mm"]} mm: prior width, paper, holder clearance and brush recovery; reject any overlap')
            b.marker('depth_trial', role, source_id=f'{role}-column-{column+1}-depth-{abs(line["z_mm"])}')
            render_calibration(dict(part, brush_lines=[line]), profile, b, integrated=True)
    b.park(material.state)
    b.marker('job_complete', 'Record 40 strokes, loading, washing and recovery; no automatic calibration pass')


def dry_station_xy(st):
    """Only XY geometry; no liquid, compression, contact Z or floor calibration."""
    if st['kind'] == 'sloped_inkstone':
        points = []
        for key in ('deep_surface_xyz', 'shallow_surface_xyz'):
            p = st.get(key)
            if not isinstance(p, (list, tuple)) or not vector(p[:2], 2):
                raise ValueError('record actual deep/shallow station XY; region limits are not contact endpoints')
            points.append(tuple(p[:2]))
        if points[1][1] <= points[0][1]: raise ValueError('station withdrawal XY must proceed Y+')
        if st.get('agitation_cycles', 0) != 0:
            raise ValueError('continuous benchmark uses the initial no-agitation well grammar')
        return tuple(points)
    if st['kind'] == 'palette':
        return (tuple(st['center_xy']), *palette_pattern_xy(st), tuple(st['center_xy']))
    raise ValueError('unsupported shared benchmark station')


def render_continuous(request, profile, b, kind, station_contact=None):
    """One operation order and one source of all forty strokes, two Z modes."""
    v = profile.data['motion']; material = Materials(b)
    def station(role, action):
        b.marker('benchmark_station_visit', role + ':' + action)
        if kind == 'paint':
            (station_contact or material.station)(role, action)
        else:
            points = dry_station_xy(profile.data['stations'][role])
            # Safe simulation plane is independent of unmeasured liquid Z.
            b.xy(points[0], v['air_station_top_mm'], material.state)
            b.move((*points[0], v['station_clearance_mm']), v['z_travel_mm_min'], 'paper_hover')
            for xy in points[1:]:
                b.move((*xy, v['station_clearance_mm']), v['air_xy_mm_min'], 'travel',
                       source_id='station-' + role)
            b.move((*points[-1], v['air_station_top_mm']), v['z_travel_mm_min'], 'lift')
            b.at_station = True
        material.loaded = role
    station('ink', 'pigment_load')
    for column, part in enumerate(request['benchmark_columns']):
        role = 'ink' if column < 2 else 'A2'
        if column in (1, 3): station(role, 'same_color_reload')
        if column == 2:
            for _ in range(profile.data['stations']['water']['wash_cycles']): station('water', 'wash')
            station('A2', 'pigment_load')
        for index, line in enumerate(part['brush_lines']):
            source = f'{role}-column-{column+1}-stroke-{index+1}'
            b.marker('depth_trial', role, source_id=source)
            if kind == 'paint':
                before = len(b.commands)
                render_calibration(dict(part, brush_lines=[line]), profile, b, integrated=True)
                # Preserve explicit stroke provenance in either execution mode.
                from dataclasses import replace
                for i in range(before, len(b.commands)):
                    if b.commands[i].action == 'draw':
                        b.commands[i] = replace(b.commands[i], source_id=source)
            else:
                b.xy(line['start_xy'], v['station_clearance_mm'], material.state)
                b.move((*line['start_xy'], 10), v['z_travel_mm_min'], 'paper_hover')
                b.move((*line['end_xy'], 10), line['feed_mm_min'], 'draw', source_id=source)
    b.park(material.state)
    b.marker('job_complete', '40 original benchmark strokes; zero routine M0; physical results recorded separately')


def build(request, profile, kind):
    validate(request, profile, kind, physical=True)
    b = Builder(profile)
    (render_air if kind == 'air' else render_paint)(request, profile, b)
    return b.commands, b.result()


def export_integrated(request, profile, kind, authorization, output):
    from .exporter import _atomic_output, _serialize, readback, save_json
    name, stage = job_kind(request, kind)
    validate(request, profile, kind, physical=True)
    authorize(authorization, profile, digest(request), stage, [name])
    # Calibration also confirms common conditions BEFORE starting, then keeps
    # its intentional in-job M0 inspections for first physical experiments.
    require_pre_run(authorization, 'painting' if continuous(request) and kind == 'paint' else 'air', [name])
    commands, metrics = build(request, profile, kind)
    text = _serialize(commands, profile, digest(request), name, stage)
    checked = readback(text, commands, profile, stage, continuous_calibration=continuous(request) and kind == 'paint')
    def write(root):
        for filename, value in [('plan.json', request), ('profile.json', profile.data),
                                ('authorization.json', authorization), ('trajectory.json', [asdict(c) for c in commands])]:
            save_json(root / filename, value)
        (root / (name + '.gcode')).write_text(text)
        report = {'schema': 'datascape.integrated_benchmark_export.v0.3', 'kind': kind,
                  'stage': stage, 'job_id': name, 'profile_sha256': profile.sha256,
                  'plan_sha256': digest(request), 'metrics': metrics, 'readback': checked,
                  'station_air_roles_included': request['air_station_roles'] if kind == 'air' else None,
                  'station_air_roles_omitted': [r for r in station_roles(request) if r not in request['air_station_roles']] if kind == 'air' else [],
                  'hardware_executed': False, 'arbitrary_line_resume_supported': False}
        save_json(root / 'report.json', report)
        return report
    return _atomic_output(output, write)


def verify_integrated(root, hashes):
    """Used by existing delivered-file verifier AFTER SHA256/path checks."""
    from .exporter import readback
    root = Path(root)
    report = json.loads((root / 'report.json').read_text())
    request = json.loads((root / 'plan.json').read_text())
    profile = Profile.load(root / 'profile.json')
    authorization = json.loads((root / 'authorization.json').read_text())
    name, stage = job_kind(request, report['kind'])
    required = {'plan.json', 'profile.json', 'authorization.json', 'trajectory.json', 'report.json', name + '.gcode'}
    if not required <= hashes.keys(): raise ValueError('unmanifested required integrated artifact')
    if report['stage'] != stage or report['job_id'] != name or report['profile_sha256'] != profile.sha256 or report['plan_sha256'] != digest(request):
        raise ValueError('integrated export binding mismatch')
    authorize(authorization, profile, digest(request), stage, [name])
    require_pre_run(authorization, 'painting' if continuous(request) and report['kind'] == 'paint' else 'air', [name])
    commands, metrics = build(request, profile, report['kind'])
    if digest(json.loads((root / 'trajectory.json').read_text())) != digest([asdict(c) for c in commands]):
        raise ValueError('delivered integrated trajectory differs from authorized plan')
    checked = readback((root / (name + '.gcode')).read_text(), commands, profile, stage,
                       continuous_calibration=continuous(request) and report['kind'] == 'paint')
    if digest(report['readback']) != digest(checked) or digest(report['metrics']) != digest(metrics):
        raise ValueError('integrated report differs from regenerated verification')
    return {'artifact_hashes_verified': len(hashes), 'regenerated_from_authorized_plan': True,
            'jobs': {name: checked}, 'hardware_executed': False}
