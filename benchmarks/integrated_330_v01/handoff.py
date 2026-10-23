"""Current execution requests and truthful pending profiles; never exports hardware code.

Run this only to materialize inputs for the existing integrated exporter. No
physical test, stopping capability, contact measurement or authorization is inferred.
"""
from copy import deepcopy
import json
from pathlib import Path

from .design import configured_profile, plan
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.integrated_benchmark import validate, benchmark_columns

BASE_COMMIT = 'e3e51bfa22cca615d29c39f9a960f38d4a193da3'


def execution_request(root):
    request = plan(root)
    request.update(air_hover_mm=10, paint_trial='ink_a2_depth_series_40', color_slots=['A2'])
    request.update(execution_mode='continuous_40', benchmark_columns=benchmark_columns(),
                   air_station_roles=['ink', 'water', 'A2'])
    request['notes'] = ('One shared benchmark source, Air then uninterrupted ink/A2 paint. '
                        'Four 10-stroke columns, '
                        'depths -1..-10 / -10..-1 per material. Rehome before EACH job. '
                        'No cloth, no local hover, no manual loading substitution. '
                        'XY travel8000/drawing5000/wet-main8000, noncontact Z3000. '
                        'Actual Air result, full -10 contact tests, station and wet-motion validation '
                        'precede zero-M0 paint authorization; no in-job inspections substitute for them.')
    return request


def execution_profile(root, seed=None):
    """Optional measured-input seed preserves earlier scoped geometric records."""
    d = deepcopy((seed or configured_profile(root)).data)
    d['profile_id'] = 'INTEGRATED-330-Z10-INK-A2-PENDING-PHYSICAL-CHECKS'
    d['machine']['start_work_xyz'] = [0, 898, 35]
    d['machine']['stopping'] = {'physical_emergency_stop_installed': False,
                              'independent_power_stop_verified': None,
                              'feed_hold_verified': None, 'soft_reset_verified': None}
    v = d['motion']
    spring_motion = json.loads((root/'config/plotter_v03/profile.unmeasured.json').read_text())['motion']
    v.update(paper_hover_mm=10, air_local_hover={'enabled': False, 'height_mm': 5},
             local_hover={'enabled': False, 'height_mm': 5, 'max_distance_mm': 10},
             air_xy_mm_min=5000, ordinary_travel_mm_min=8000, draw_mm_min=5000,
             wet_loaded_mm_min=8000, wet_departure_mm_min=3000, wet_arrival_mm_min=3000,
             z_travel_mm_min=3000, paper_approach_mm_min=3000, pressure_z_mm_min=2000,
             paper_contact_mm_min=spring_motion['paper_contact_mm_min'],
             paper_release_mm_min=spring_motion['paper_release_mm_min'],
             air_station_top_mm=35, air_station_roles=['ink', 'water', 'A2'],
             benchmark_plan_sha256=digest(execution_request(root)))
    # Keep the existing -3 envelope; uninterrupted -10 contact at candidate
    # feeds needs actual prior physical validation, not in-job M0 observations.
    for role, limits in (('water', [220, 285]), ('ink', [370, 435])):
        st = d['stations'][role]
        st.update(coordinate_frame='G54', center_xy=[840, sum(limits)/2],
                  registered_region_xy=[[840, limits[0]], [840, limits[1]]],
                  withdrawal_direction='Y+',
                  nominal_bed_geometry={'deep_floor_z': 5, 'shallow_floor_z': 10,
                                        'liquid_z_range': [10, 11],
                                        'status': 'nominal references; not measured contact endpoints'})
    a2 = deepcopy(d['stations']['C1'])
    # A historical C1 calibration must never migrate to A2.
    a2.update(hardware_id='A2', center_xy=[824.5, 554.5], coordinate_frame='G54', status='unverified',
              contact_box_xyz=None, liquid_reference_z=None, bottom_z=None, bottom_gap_mm=None,
              immersion_mm=None, radius_mm=None, revolutions=None, dwell_seconds=None, feed_mm_min=None,
              exit_above_liquid_mm=None,
              nominal_bed_geometry={'floor_z': 2, 'liquid_above_floor_mm': 5, 'liquid_z': 7,
                                    'status': 'approximate fill target; no measured G54 Z inferred'})
    d['stations']['A2'] = a2
    d['notes'] = ('Current proposed benchmark: dry/wet-main F8000, drawing F5000, noncontact Z3000, '
        'pressure-Z cap2000; paper compression/release use the existing Spring candidates, '
        'independently configured from noncontact travel. These are not physical approvals. Station '
        'contact feeds remain independent; noncontact Z3000 never becomes a liquid/contact feed. '
        'No physical E-stop installed; no independent stopping '
        'test or Y-negative vibration resolution supplied. Normal hover Z10, local hover disabled. Both stones deepen toward Y-; '
        'withdrawal must be Y+ while raising Z. A2 XY registered; contact Z and pattern pending. '
        'Start is rehomed X0 Y898 Z35 for both jobs, not previous park. Historical -8 experience '
        'does not establish current -10 clearance. No actual Air result or job authorization inferred.')
    # Rebind only the unchanged factual subjects, never old path/dynamic approval.
    p = Profile.from_dict(d)
    reusable = {'installed_controller', 'g54_registration', 'park', 'paper_hover'}
    for e in d['evidence']:
        if e['check'] in reusable and e['status'] == 'passed':
            e.pop('calibration_sha256', None)
            e['scope_sha256'] = p.evidence_scope_sha256(e['check'])
        elif e.get('status') == 'passed':
            e['status'] = 'pending'
            e['method'] = 'New execution policy requires review; prior observation retained, no automatic pass. ' + e['method']
    return Profile.from_dict(d)


def write_inputs(root, output, seed=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    request, profile = execution_request(root), execution_profile(root, seed)
    validate(request, profile, 'air', physical=False)
    for name, value in [('execution.plan.json', request), ('profile.pending.json', profile.data)]:
        (output/name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'base_commit': BASE_COMMIT, 'profile_sha256': profile.sha256, 'plan_sha256': digest(request),
            'air_readiness_issues': profile.issues('air'),
            'air_missing_station_xy_or_pattern': [r for r in ('ink', 'water', 'A2')
                if _missing_dry_geometry(profile, r)],
            'independent_power_stop_verified': profile.data['machine']['stopping']['independent_power_stop_verified'],
            'paint_readiness_issues': profile.issues('calibration', ('ink', 'water', 'A2')),
            'paint_requested_contact_z_range': [-10, 0],
            'paint_current_contact_z_range': profile.data['motion']['paper_contact_z_range'],
            'paint_required_pre_run_checks': ['continuous_benchmark_contact (actual -9/-10 tested_depths_mm)',
                                             'station_contacts', 'wet_motion'],
            'air_required_station_corridor_checks': ['air_station_ink', 'air_station_water', 'air_station_A2'],
            'requested_jobs': ['BENCHMARK_330_AIR.gcode', 'BENCHMARK_330_PAINT.gcode'],
            'air_result_recorded': profile.evidence_passed('air_run'),
            'air_operator_authorization_received': False, 'paint_operator_authorization_received': False,
            'executable_export_attempted': False, 'hardware_executed': False}


def _missing_dry_geometry(profile, role):
    from datascape.gcode.production.integrated_benchmark import dry_station_xy
    try: dry_station_xy(profile.data['stations'][role])
    except (KeyError, TypeError, ValueError): return True
    return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed-profile')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = write_inputs(root, args.output, Profile.load(args.seed_profile) if args.seed_profile else None)
    Path(args.output, 'readiness.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
