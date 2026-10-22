"""PR28 composition and truthful operator/configuration records; no auto-authorization."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from benchmarks.commissioning_330_v01.design import profile as original_profile
from studies.local_hover_v01.config import historical_xy

PIN = '29fccadc9a270afe65d46c7e8711c5c2ec0d8ea8'
CONFIG_SHA = '884fb232dfbe9f5396155f5ad90c231458913a29aaa723e415ba5a4ee2ed3280'
CONTROLLER = '''<Idle|MPos:0.000,898.000,35.000|FS:0,0>
[G54:0.000,0.000,0.000]
[G92:0.000,0.000,0.000]
[TLO:0.000,0.000,0.000]
[GC:G0 G54 G17 G21 G90 G94 M5 M9 T0 F0 S0]
[VER:4.1 FluidNC v4.1.1 (esp32-wifi)]
[MSG:Machine: DATASCAPE_HOME_FRAME_X0_Y898_Z35_261022]
'''


def plan(root):
    sources = {}
    for name in ('A_STABILITY', 'B_DEPTH_1', 'B_DEPTH_2', 'B_DEPTH_3', 'C_LOW', 'D_HOVER'):
        p = json.loads((root / 'benchmarks/commissioning_330_v01/plans' / (name + '.json')).read_text())
        sources[name] = {'plan': p, 'sha256': digest(p)}
    return {'schema': 'datascape.integrated_benchmark.v0.3', 'substrate_mm': [330, 330],
            'source_commit': PIN, 'sources': sources, 'color_slots': ['C1'], 'include_cloth': False,
            'air_station_roles': [],
            'recipe': {'water_mL_approx': 50, 'gouache_small_palette_knife_scoops_approx': 6,
                       'pigment_mass_g': None, 'status': 'provisional mixing reference; not a measured concentration'},
            'notes': 'One Air and one paint job. Original PR28 paper paths/pressure samples reused. '
                     'Ink and water required for paint. Cloth optional; second color C2 opt-in. '
                     'Air station roles explicitly selected only after G54 XY/corridor confirmation; omitted stations stay offline. '
                     'No automatic certification or production Spring output.'}


def configured_profile(root, kind='air'):
    if kind not in ('air', 'paint'): raise ValueError('unknown benchmark profile kind')
    import yaml
    raw = (root / 'benchmarks/integrated_330_v01/config.installed.yaml').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONFIG_SHA: raise ValueError('installed YAML identity changed')
    installed = yaml.safe_load(raw)
    d = deepcopy(original_profile(root).data)
    d['profile_id'] = 'INTEGRATED-330-OPERATOR-CONFIRMED-PARTIAL-v01'
    m = d['machine']
    m.update(firmware_version='FluidNC v4.1.1 (esp32-wifi)', installed_config_sha256=CONFIG_SHA,
             g54_to_machine_xyz=[0, 0, 0], start_work_xyz=[0, 898, 35],
             machine_bounds_xyz=[[0, 0, -11], [850, 898, 35]], machine_bounds_reference='axis_reference',
             validated_free_segments=[], paper_surface_above_bed_mm=None)
    if kind == 'paint': m['start_work_xyz'] = [800, 800, 32]
    for dest, source in [('axis_max_rate_mm_min', 'max_rate_mm_per_min'),
                         ('axis_acceleration_mm_s2', 'acceleration_mm_per_sec2'), ('steps_per_mm', 'steps_per_mm')]:
        m[dest] = [installed['axes'][k][source] for k in 'xyz']
    v = d['motion']
    v.update(air_xy_mm_min=5000, ordinary_travel_mm_min=5000, draw_mm_min=600,
             z_travel_mm_min=300, paper_approach_mm_min=300, paper_approach_mm=5,
             paper_contact_z_range=[-3, 0], wet_departure_mm=5, wet_arrival_mm=5,
             air_local_hover={'enabled': True, 'height_mm': 5}, air_station_roles=[])
    template = json.loads((root / 'config/plotter_v03/profile.unmeasured.json').read_text())
    xy = historical_xy(root / 'hardware/fluidnc/tool_coordinates.yaml')
    for role in ('C1', 'C2'):
        d['stations'][role] = deepcopy(template['stations'][role])
        d['stations'][role].update(center_xy=[xy[role]['x'], xy[role]['y']], coordinate_frame=None)
    # Whole well locations remain historical references, never invented deep or
    # shallow contact points. The supplied bed elevations are recorded separately.
    for role, well in (('water', 'WELL_1'), ('ink', 'WELL_2')):
        ref = xy[well]
        d['stations'][role].update(center_xy=[ref['x'], (ref['y_start'] + ref['y_end']) / 2],
            coordinate_frame=None, feed_mm_min=60, dwell_seconds=1, stone_gap_mm=1,
            exit_above_liquid_mm=2)
    d['stations']['water'].update(wash_cycles=1, rewet_dwell_seconds=1)
    d['notes'] = ('Actual operator controller transcript confirms firmware, MPos/WPos home and zero G54/G92/TLO. '
        'Configured axis limits and operator-reported travel preserved; axis-reference bounds are declared configured travel, '
        'not a fabricated full free-space volume. Paper/park interference checks are operator reports, not backend Air results. '
        'Z5 Air clearance, complete integrated swept paths/stop procedure and stage authorization still pending. '
        'F5000 is Air/dry travel only; contact drawing 600, Z300, paper contact/release 60, pressure Z120. '
        'Approach Z5 and [-3,0] envelope, 5-mm wet edges, station feed60/dwell1/gap1/exit2 and wash1 are '
        'unapproved initial trial parameters. Actual liquid, slope XYZ, contact volumes and color depths remain null. '
        'Brush knots are unmeasured; status unverified; cloth inactive; no hardware motion.')
    if kind == 'paint':
        d['notes'] += (' Expected PAINT start is the AIR final park [800,800,32], conditional on actual AIR '
                       'arrival and fresh pre-run verification. It is not asserted as the current machine position.')
    # These two checks are backed by the newly supplied installed bytes and
    # verbatim controller query, not synthetic trials or inferred physical data.
    partial = Profile.from_dict(d)
    d['evidence'] = [{'check': check, 'status': 'passed', 'scope_sha256': partial.evidence_scope_sha256(check),
        'operator': 'user (explicit controller report)', 'date': '2026-10-22',
        'method': method} for check, method in (
            ('installed_controller', 'User identifies this installed YAML; SHA256 ' + CONFIG_SHA + '; controller query confirms FluidNC v4.1.1 and exact machine name.'),
            ('g54_registration', 'Verbatim Idle controller query: MPos [0,898,35], G54/G92/TLO all zero; user confirms identical WPos and first contact Z0.'),
            ('park', 'User explicitly confirms planned paper/park trajectories checked for interference; candidate endpoint [800,800,32] retained. Actual benchmark arrival is not claimed; new full paths still require swept-clearance inspection.'),
            ('paper_hover', 'User confirms first contact Z0 and existing planned paper trajectories checked for interference at normal Z10. This does not certify new Z5 links.'))]
    return Profile.from_dict(d)


def facts(root):
    old = json.loads((root / 'benchmarks/commissioning_330_v01/review/measurements.json').read_text())
    return {'source': 'Explicit operator confirmations, 2026-10-22; no independent physical observation by software',
        'installed_yaml_sha256': CONFIG_SHA, 'controller_transcript': CONTROLLER,
        'confirmed': {'MPos_after_homing': [0, 898, 35], 'G54_WPos_after_homing': [0, 898, 35],
            'G54_G92_TLO_zero': True, 'firmware': 'FluidNC v4.1.1 (esp32-wifi)',
            'XYZ_directions_limits_repeated_homing_working': True, 'paper_first_contact_G54_z': 0,
            'downward_travel_from_Z35_mm_approx': 46, 'X_travel_physically_checked': True,
            'configured_X_max_mm': 850, 'planned_paper_and_park_interference_checked': True,
            'USB_improved_after_port_change': True},
        'candidates': {'park_G54_xyz': [800, 800, 32], 'paper_mm_approx': [330, 330],
            'liquid_bed_z_mm': [10, 11], 'deep_floor_bed_z_mm': 6, 'shallow_floor_bed_z_mm': 10,
            'immersion_initial_mm': 2, 'immersion_later_after_inspection_mm': 3},
        'preserved_well_regions_XY': old['reported']['well_regions_XY'],
        'preserved_well_geometry_bed_mm': old['reported']['well_geometry_bed_mm'],
        'nominal_only_if_paper_is_1mm_above_bed': {'liquid_G54_z_mm': [9, 10], 'deep_floor_G54_z': 5,
            'shallow_floor_G54_z': 9, 'dip_2mm_G54_z_range': [7, 8], 'deep_floor_tip_gap_mm_range': [2, 3]},
        'independent_A_SHORT_numerical_check_is_not_backend_authorization': True,
        'not_yet_confirmed': ['new integrated Z5 full-tool paths and exact reviewed segment scope',
            'physical emergency-stop/USB-loss stop procedure', 'initial wet/contact acceleration trial limits',
            'exact G54 deep/shallow points and liquid reference for each well; contact volumes',
            'representative color G54 registration/level/floor/loading geometry',
            'actual integrated Air result before paint', 'per-stage content-bound authorization'],
        'optional_only': ['cloth fixed surface G54 Z/contact volume/compression/dwell if enabled', 'second representative color if selected']}
