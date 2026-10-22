"""Generate two non-executable reviews and attempt only properly gated exports.

Run: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.run --output NEW_DIR
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from math import dist
from pathlib import Path
import xml.etree.ElementTree as ET

from datascape.gcode.binding import digest
from datascape.gcode.production.trajectory import Command
from datascape.gcode.production.integrated_benchmark import validate, render_air, render_paint, export_integrated, KINDS, station_roles
from datascape.gcode.production.exporter import _atomic_output, save_json
from benchmarks.commissioning_330_v01.preview import ReviewBuilder, write_review
from .design import plan, configured_profile, facts, CONTROLLER


def trajectory_svg(commands, profiles):
    svg = ET.Element('svg', {'xmlns': 'http://www.w3.org/2000/svg', 'width': '1120', 'height': '670', 'viewBox': '0 0 1120 670'})
    ET.SubElement(svg, 'rect', {'width': '1120', 'height': '670', 'fill': '#fafafa'})
    def text(x, y, value, size=13, fill='#222'):
        e = ET.SubElement(svg, 'text', {'x': str(x), 'y': str(y), 'font-size': str(size), 'font-family': 'sans-serif', 'fill': fill}); e.text = value
    for index, (kind, rows) in enumerate(commands.items()):
        profile = profiles[kind]
        ox, oy, scale = 42 + index * 560, 76, .53
        project = lambda p: (ox + p[0] * scale, oy + (898 - p[1]) * scale)
        text(ox, 34, KINDS[kind][0] + ' / OFFLINE ONLY', 19)
        text(ox, 56, 'Blue = Z10; orange = Z5; black = contact; gray = travel', 11)
        x, y = project((0, 330))
        ET.SubElement(svg, 'rect', {'x': str(x), 'y': str(y), 'width': str(330 * scale), 'height': str(330 * scale), 'fill': '#eaf4ee', 'stroke': '#5b8a68'})
        text(x + 4, y + 16, '330 x 330 paper', 11)
        px, py = project((0, 898))
        ET.SubElement(svg, 'rect', {'x': str(px), 'y': str(py), 'width': str(850 * scale), 'height': str(898 * scale), 'fill': 'none', 'stroke': '#aaa'})
        pos = profile.data['machine']['start_work_xyz']
        for c in rows:
            if c.kind != 'move': continue
            a, b = project(pos), project(c.xyz)
            if a != b:
                color = ('#171717' if c.xyz[2] <= 0 else '#dc761b' if c.xyz[2] == 5 else '#1976a6') if c.action in ('draw', 'air_path') else '#c2c7cd'
                ET.SubElement(svg, 'line', {'x1': str(a[0]), 'y1': str(a[1]), 'x2': str(b[0]), 'y2': str(b[1]), 'stroke': color, 'stroke-width': '1.1'})
            pos = c.xyz
        for role in ('ink', 'water', 'C1', 'sponge'):
            st = profile.data['stations'][role]; xy = st.get('center_xy')
            if xy:
                x, y = project(xy)
                ET.SubElement(svg, 'circle', {'cx': str(x), 'cy': str(y), 'r': '4', 'fill': 'none', 'stroke': '#a54d87', 'stroke-dasharray': '2 1'})
                text(x - 130, y - 7, role + ' nominal XY / PENDING', 10, '#8e366f')
        for label, point in [('HOME Z35', (0, 898)),
                             ('PARK Z32' if kind == 'air' else 'PAINT START / PARK Z32', (800, 800))]:
            x, y = project(point); text(x + 5 if label.startswith('HOME') else x - 155, y + 16, label, 11)
        text(ox, 598, 'Station marks are historical references, not verified G54 visits.', 11)
        text(ox, 618, 'Paint station paths/approaches remain UNRESOLVED, not guessed.', 11)
    return ET.tostring(svg, encoding='unicode')


def prepare(root, output):
    request = plan(root); profiles = {k: configured_profile(root, k) for k in KINDS}
    def write(out):
        save_json(out / 'integrated.plan.json', request)
        for kind, profile in profiles.items(): save_json(out / ('profile.' + kind + '.partial.json'), profile.data)
        save_json(out / 'confirmed_facts.json', facts(root))
        (out / 'controller.confirmed.txt').write_text(CONTROLLER)
        (out / 'config.installed.yaml').write_bytes((root / 'benchmarks/integrated_330_v01/config.installed.yaml').read_bytes())
        for filename in ('physical_inputs.TO_FILL.json', 'observations.CONSOLIDATED.json'):
            template = root / 'benchmarks/integrated_330_v01/review' / filename
            if template.exists(): (out / filename).write_bytes(template.read_bytes())
        summary = {'schema': 'datascape.integrated_benchmark_review.v0.3',
                   'source_pin': request['source_commit'], 'plan_sha256': digest(request),
                   'profile_sha256': {k:p.sha256 for k,p in profiles.items()}, 'hardware_executed': False,
                   'executable_files_written': 0, 'jobs': {}}
        all_commands = {}
        for kind, (name, stage) in KINDS.items():
            profile = profiles[kind]
            validate(request, profile, kind, physical=False)
            b = ReviewBuilder(profile)
            if kind == 'air': render_air(request, profile, b, include_pending=True)
            else:
                def unresolved_station(role, action, material_key=None):
                    b.commands.append(Command('unresolved', 'required_station_' + action,
                        message=json.dumps({'role': role, 'material_key': material_key, 'station': profile.data['stations'][role]}, sort_keys=True)))
                render_paint(request, profile, b, unresolved_station)
            all_commands[kind] = b.commands
            readback = write_review(out / (name + '.preview.txt'), b.commands, profile, request)
            save_json(out / (name + '.trajectory.json'), [asdict(c) for c in b.commands])
            save_json(out / (name + '.readback.json'), readback)
            authorization = {'stage': stage, 'profile_sha256': profile.sha256, 'plan_sha256': digest(request),
                'job_ids': [name], 'operator': None, 'date': None, 'explicit_operator_authorization': False,
                'pre_run_confirmations': {name: {c: False for c in ('coordinates_and_start_verified',
                    'paper_and_clearance_verified', 'tool_and_controller_state_verified')}}}
            save_json(out / (name + '.UNAUTHORIZED.json'), authorization)
            error = None
            try: export_integrated(request, profile, kind, authorization, out / ('BLOCKED_' + name))
            except (ValueError, KeyError, TypeError) as e: error = str(e)
            if error is None or (out / ('BLOCKED_' + name)).exists():
                raise AssertionError('incomplete actual profile must not export')
            pos = profile.data['machine']['start_work_xyz']; seconds = 0.; lengths = Counter(); segments = []
            for c in b.commands:
                if c.kind == 'move':
                    if all(v is not None for v in (*pos, *c.xyz)):
                        length = dist(pos, c.xyz); seconds += length / c.feed_mm_min * 60
                        lengths[c.action] += length; segments.append([list(pos), list(c.xyz)])
                    pos = c.xyz
            if kind == 'air':
                save_json(out / 'AIR_FULL_TOOL_SEGMENTS.TO_CONFIRM.json', {
                    'status': 'computed review geometry ONLY; NOT physically validated',
                    'profile_sha256': profile.sha256, 'plan_sha256': digest(request),
                    'segments_sha256': digest(segments), 'G54_segments': segments,
                    'note': 'Confirm full mounted-tool/cable clearance over these exact segments; no free-space box is inferred. '
                            'Only then may they be recorded as validated_free_segments with scoped operator evidence. '
                            'Unselected stations are excluded. Existing checked paper/park facts remain preserved.'})
            summary['jobs'][name] = {'kind': kind, 'stage': stage, 'readback': readback,
                'profile_sha256': profile.sha256, 'expected_start_work_xyz': profile.data['machine']['start_work_xyz'],
                'export_blocked': True, 'export_block_reason': error,
                'profile_blockers': profile.issues(stage, [] if kind == 'air' else station_roles(request)),
                'known_commanded_seconds_only': seconds, 'known_distance_mm_by_action': dict(lengths),
                'total_time_complete': readback['unresolved_operations'] == 0,
                'M0_count': readback['M0_count'], 'M0_reasons': readback['M0_reasons'],
                'physical_time_verified': False, 'authorized': False,
                'air_station_roles_selected': request['air_station_roles'] if kind == 'air' else None}
        (out / 'trajectories.svg').write_text(trajectory_svg(all_commands, profiles))
        save_json(out / 'summary.json', summary)
        return summary
    return _atomic_output(output, write)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); root = Path(__file__).resolve().parents[2]
    report = prepare(root, a.output)
    print(json.dumps({'output': str(a.output), 'plan_sha256': report['plan_sha256'],
        'profile_sha256': report['profile_sha256'], 'executable_files_written': 0,
        'jobs': {name: {'M0_count': j['M0_count'], 'readback_moves': j['readback']['numeric_moves_checked'],
                        'unresolved_operations': j['readback']['unresolved_operations']} for name, j in report['jobs'].items()}}, indent=2))


if __name__ == '__main__': main()
