"""Prepare pinned Spring jobs, inspect readiness, or export an authorized stage."""
import argparse
import json
import sys
from pathlib import Path
from collections import Counter
from ..binding import load_bound_spring, digest
from ..layout import Layout, Registration
from ..validation import validate_layout
from .profiles import Profile, BASE_CHECKS, PAINT_CHECKS, require_physical_layout
from .sequence import reference_order, make_plan, pressure_distribution, verify_plan, accepted_family_distribution, apply_color_order
from .exporter import save_json, export_jobs, export_calibration, _atomic_output, verify_export


def load_json(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'export'):
        s = sub.add_parser(command)
        for key in ('machine', 'provenance', 's3a-order', 'output'): s.add_argument('--'+key, required=True, type=Path)
        s.add_argument('--layout', choices=('A', 'B', 'C', 'D'), default='D')
        s.add_argument('--gap-mm', type=float, default=0)
        s.add_argument('--registration', type=Path, help='JSON list of existing Registration fields')
        s.add_argument('--resume-after', type=Path, help='JSON job -> last completed source ID; complete source boundaries only')
        s.add_argument('--pressure-sidecar', type=Path, help='optional accepted sidecar for exact family labels')
        s.add_argument('--profile', type=Path, required=(command == 'export'))
        if command == 'export':
            s.add_argument('--stage', required=True, choices=('air', 'painting'))
            s.add_argument('--authorization', required=True, type=Path)
            s.add_argument('--jobs', nargs='+', help='only these job IDs; separate authorization can be used per panel')
    s = sub.add_parser('verify'); s.add_argument('--output', required=True, type=Path)
    s = sub.add_parser('readiness'); s.add_argument('--profile', required=True, type=Path)
    s.add_argument('--stage', required=True, choices=('air', 'calibration', 'painting'))
    s.add_argument('--layout', choices=('A','B','C','D'), default='D')
    s.add_argument('--slots', nargs='*', default=[])
    s.add_argument('--media', nargs='+', choices=('ink','color'), default=['ink','color'])
    s = sub.add_parser('calibration')
    for k in ('profile', 'plan', 'authorization', 'output'): s.add_argument('--'+k, required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.command == 'verify':
            print(json.dumps(verify_export(a.output), indent=2)); return 0
        if a.command == 'readiness':
            prof = Profile.load(a.profile); issues = prof.issues(a.stage, a.slots, a.media)
            try: require_physical_layout(prof, {'layout':{'mode':a.layout}}, a.stage)
            except ValueError as e: issues.append(str(e))
            print(json.dumps({'stage': a.stage, 'profile_sha256': prof.sha256,
                'calibration_sha256_for_evidence': prof.calibration_sha256,
                'preferred_evidence_scope_sha256': {c:prof.evidence_scope_sha256(c) for c in (*BASE_CHECKS,'air_run',*PAINT_CHECKS,'continuous_seam')},
                'structurally_ready': not issues, 'blocking_issues': issues,
                'operator_stage_authorization_still_required': True}, indent=2))
            return 2 if issues else 0
        if a.command == 'calibration':
            report = export_calibration(load_json(a.plan), Profile.load(a.profile),
                                        load_json(a.authorization), a.output)
        else:
            strokes, provenance = load_bound_spring(a.machine, a.provenance)
            reg = () if a.registration is None else tuple(Registration(**r) for r in load_json(a.registration))
            layout = Layout(a.layout, a.gap_mm, reg)
            order = reference_order(strokes, a.s3a_order)
            prof = None if a.profile is None else Profile.load(a.profile)
            palette_order = None if prof is None else prof.data.get('material', {}).get('color_order')
            if palette_order is not None: order = apply_color_order(strokes, order, palette_order)
            jobs, manifest = make_plan(strokes, layout, order,
                                      None if a.resume_after is None else load_json(a.resume_after), palette_order)
            if a.command == 'prepare':
                validation = validate_layout(strokes, layout)
                # A sequential setup cannot preserve global time order across all
                # crossing sources. It still preserves each fragment's direction.
                crossing = []
                if layout.mode != 'D':
                    shared = Layout('B')
                    from ..motion import fragments
                    from itertools import groupby
                    for sid, fs in groupby(fragments(strokes, shared), key=lambda f: f.stroke.origin_id):
                        fs = list(fs)
                        if len({f.panel for f in fs}) > 1:
                            crossing.append({'source_id': sid, 'first_panel': fs[0].panel,
                                             'sequential_P1_first_changes_global_fragment_time': fs[0].panel == 'P2'})
                slots = sorted({s.color_slot for s in strokes if s.medium == 'color'})
                report = {'schema': 'datascape.preparation_report.v0.3',
                    'plan_sha256': digest(manifest), 'source_validation': validation,
                    'S3a_reference_reused': True, 'no_artwork_or_pressure_generation': True,
                    'job_source_units': {k: len(v) for k, v in jobs.items()},
                    'job_fragments': {k: sum(len(u) for u in v) for k, v in jobs.items()},
                    'cross_panel_sources': crossing,
                    'actual_color_slots': slots,
                    'readiness': None if prof is None else {stage: prof.issues(stage, slots)
                                                          for stage in ('air', 'painting')},
                    'hardware_executed': False, 'production_Gcode_written': False}
                def write(root):
                    save_json(root/'plan.json.gz', manifest)
                    import gzip
                    written = json.loads(gzip.decompress((root/'plan.json.gz').read_bytes()))
                    report['actual_plan_readback'] = verify_plan(written, strokes, layout)
                    save_json(root/'summary.json', report)
                    if a.pressure_sidecar is not None:
                        save_json(root/'pressure_distribution_by_accepted_family.json', accepted_family_distribution(strokes, a.pressure_sidecar))
                    save_json(root/'pressure_distribution_by_available_family.json', pressure_distribution(strokes))
                    return report
                report = _atomic_output(a.output, write)
            else:
                report = export_jobs(jobs, manifest, Profile.load(a.profile), a.stage,
                                     load_json(a.authorization), a.output, a.jobs)
        print(json.dumps(report, indent=2)); return 0
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(str(e), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
