"""Reusable measured profiles, content-bound evidence and stage authorization."""
from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import json
from ..binding import digest
from ..calibration import BrushCalibration, CalibrationObservation

STAGES = ('fixture', 'air', 'calibration', 'painting')
BASE_CHECKS = ('installed_controller', 'homing_limits_estop', 'g54_registration',
               'motion_limits', 'swept_clearance', 'park', 'paper_flatness', 'paper_hover')
PAINT_CHECKS = ('station_contacts', 'brush_response', 'contamination_cleaning',
                'ink_to_color_inspection', 'paper_contact', 'microsegment_response',
                'registration_repeatability')


def number(v, positive=False):
    return type(v) in (int, float) and isfinite(v) and (not positive or v > 0)


def vector(v, size=3):
    return isinstance(v, (tuple, list)) and len(v) == size and all(number(x) for x in v)


def box(v):
    return (isinstance(v, (tuple, list)) and len(v) == 2 and vector(v[0])
            and vector(v[1]) and all(x < y for x, y in zip(*v)))


def air_minimum_z(profile):
    """Explicit no-contact local-hover trial; never enables production hover."""
    v = profile.data['motion']
    local = v.get('air_local_hover', {})
    return local['height_mm'] if local.get('enabled') is True else v['paper_hover_mm']


def exact_free_segments(machine):
    """Optional inspected full-tool segments in G54; no clearance volume inferred."""
    segments = machine.get('validated_free_segments', [])
    return (isinstance(segments, list) and bool(segments)
            and all(isinstance(s, list) and len(s) == 2 and all(vector(p) for p in s) for s in segments))


def brush(data):
    d = deepcopy(data)
    if d.pop('interpolation', 'piecewise_linear') != 'piecewise_linear':
        raise ValueError('only monotonic piecewise_linear is implemented; no silent spline fallback')
    d['knots'] = tuple(tuple(k) for k in d['knots'])
    d['observations'] = tuple(CalibrationObservation(**o) for o in d.get('observations', []))
    return BrushCalibration(**d)


@dataclass(frozen=True)
class Profile:
    data: dict

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))

    @classmethod
    def from_dict(cls, data):
        # JSON canonicalization rejects NaN/Infinity, preserves a private copy.
        digest(data)
        if data.get('schema') != 'datascape.print_profile.v0.3':
            raise ValueError('unknown print profile schema')
        allowed = {'schema', 'profile_id', 'status', 'machine', 'motion', 'material',
                   'stations', 'brush_profiles', 'evidence', 'notes'}
        if set(data) - allowed:
            raise ValueError('unknown profile fields: ' + ', '.join(sorted(set(data) - allowed)))
        return cls(deepcopy(data))

    @property
    def sha256(self):
        return digest(self.data)

    @property
    def calibration_sha256(self):
        return digest({k: v for k, v in self.data.items() if k != 'evidence'})

    def brush_for(self, medium, slot):
        profiles = self.data['brush_profiles']
        return brush(profiles[slot] if slot in profiles else profiles[medium])

    def evidence_scope_sha256(self, check):
        machine = self.data.get('machine', {})
        motion = self.data.get('motion', {})
        stations = self.data.get('stations', {})
        geometry = {role:{k:st.get(k) for k in ('hardware_id','coordinate_frame','contact_box_xyz',
                        'center_xy','deep_surface_xyz','shallow_surface_xyz')} for role,st in stations.items()}
        context = {'machine':machine, 'check':check}
        if check in ('air_run', 'air_local_hover_clearance'):
            # A successful Air trial concerns this physical setup and dry policy.
            # A subsequent job has its own verified start and swept-path evidence;
            # adding measured contact corridors does not undo the past Air result.
            context['machine'] = {k:v for k,v in machine.items() if k not in
                ('start_work_xyz', 'validated_free_boxes', 'validated_free_segments',
                 'keepout_boxes', 'tool_envelope_margin_mm')}
            context['motion'] = {k:motion.get(k) for k in ('air_xy_mm_min', 'ordinary_travel_mm_min',
                'z_travel_mm_min', 'paper_hover_mm', 'station_clearance_mm', 'park_xyz', 'air_local_hover', 'air_station_roles',
                'benchmark_plan_sha256', 'air_station_top_mm', 'air_station_simulation_z_mm', 'wet_loaded_mm_min',
                'wet_departure_mm', 'wet_arrival_mm', 'wet_departure_mm_min', 'wet_arrival_mm_min')}
            if check == 'air_run':
                context['station_geometry'] = {k:geometry[k] for k in motion.get('air_station_roles', []) if k in geometry}
                if motion.get('benchmark_plan_sha256'):
                    context['station_geometry'] = {role: {k: st.get(k) for k in
                        ('hardware_id', 'coordinate_frame', 'center_xy', 'radius_mm', 'pattern',
                         'revolutions', 'segments_per_revolution', 'wash_cycles', 'agitation_cycles')}
                        | {k: (st[k][:2] if isinstance(st.get(k), (list, tuple)) else None)
                           for k in ('deep_surface_xyz', 'shallow_surface_xyz')}
                        for role, st in stations.items() if role in motion.get('air_station_roles', [])}
        elif check in ('brush_response','paper_contact','microsegment_response','continuous_seam','local_hover_clearance'):
            context.update(motion=motion, brushes=self.data.get('brush_profiles', {}))
        elif check in ('station_contacts','contamination_cleaning','ink_to_color_inspection','station_ink_trial','station_water_trial','cloth_purge_trial',
                       'continuous_benchmark_contact','wet_motion'):
            brushes = {name:{k:v for k,v in b.items() if k not in ('knots','observations')}
                       for name,b in self.data.get('brush_profiles', {}).items()}
            context.update(motion=motion, stations=stations, brushes=brushes, material=self.data.get('material', {}))
        elif check not in ('installed_controller','homing_limits_estop','g54_registration','registration_repeatability'):
            context.update(motion=motion, station_geometry=geometry)
        return digest(context)

    def evidence_passed(self, check):
        return any(e.get('check') == check and e.get('status') == 'passed'
                   and (e.get('scope_sha256') == self.evidence_scope_sha256(check)
                        or e.get('calibration_sha256') == self.calibration_sha256)
                   and all(isinstance(e.get(k), str) and e[k].strip()
                           for k in ('operator', 'date', 'method'))
                   for e in self.data.get('evidence', []))

    def issues(self, stage, slots=(), media=('ink','color')):
        """Aggregate missing measurements; no contact defaults are synthesized."""
        errors = []
        def need(ok, text):
            if not ok: errors.append(text)
        need(stage in STAGES, 'unknown readiness stage')
        fixture = stage == 'fixture'
        need(self.data.get('status') == ('synthetic_fixture' if fixture else 'measured'),
             'profile status must be ' + ('synthetic_fixture' if fixture else 'measured'))
        m = self.data.get('machine', {}); v = self.data.get('motion', {})
        need(m.get('controller') == 'FluidNC' and m.get('kinematics') == 'Cartesian',
             'verified FluidNC Cartesian configuration required')
        need(all(isinstance(m.get(k), str) and m[k].strip() for k in ('mounted_brush_id', 'hardware_version', 'substrate_id')),
             'record mounted brush, hardware assembly and substrate identities')
        need(bool(m.get('firmware_version')) and bool(m.get('installed_config_sha256')),
             'record installed firmware version and configuration SHA256')
        for key in ('g54_to_machine_xyz', 'start_work_xyz'):
            need(vector(m.get(key)), 'measure machine.' + key)
        need(box(m.get('machine_bounds_xyz')), 'measure usable machine bounds')
        for key in ('axis_max_rate_mm_min', 'axis_acceleration_mm_s2', 'steps_per_mm'):
            need(vector(m.get(key)) and all(number(x, True) for x in m.get(key, [])),
                 'measure positive machine.' + key)
        # Junction deviation is needed for the timing model, not for checking an
        # Air Run's coordinates, axis speed caps or complete swept corridors.
        if stage != 'air':
            need(number(m.get('junction_deviation_mm'), True), 'record controller junction deviation')
        need(m.get('machine_bounds_reference', 'tool_envelope') in ('tool_envelope', 'axis_reference'),
             'unknown machine bounds reference')
        exact_only = (exact_free_segments(m) and m.get('machine_bounds_reference') == 'axis_reference'
                      and m.get('keepout_boxes') == [])
        need((number(m.get('tool_envelope_margin_mm')) and m['tool_envelope_margin_mm'] >= 0) or exact_only,
             'measure tool-envelope margin')
        need((bool(m.get('validated_free_boxes')) and all(box(b) for b in m.get('validated_free_boxes', [])))
             or exact_only, 'measure swept-tool free-space boxes or inspect exact full-tool segments')
        need(isinstance(m.get('keepout_boxes'), list) and all(box(b) for b in m.get('keepout_boxes', [])),
             'record swept-tool keepout boxes (explicit [] allowed after inspection)')
        motion_keys = ('paper_hover_mm', 'station_clearance_mm', 'draw_mm_min', 'ordinary_travel_mm_min',
                    'partially_depleted_mm_min', 'wet_loaded_mm_min', 'station_approach_mm_min',
                    'z_travel_mm_min', 'contact_mm_min', 'wet_departure_mm', 'wet_departure_mm_min',
                    'wet_arrival_mm', 'wet_arrival_mm_min', 'paper_approach_mm_min',
                    'paper_contact_mm_min', 'paper_release_mm_min',
                    'paper_approach_mm', 'pressure_z_mm_min', 'wet_max_xy_acceleration_mm_s2',
                    'contact_max_z_acceleration_mm_s2')
        if stage == 'air':
            motion_keys = ('paper_hover_mm', 'station_clearance_mm', 'draw_mm_min',
                           'ordinary_travel_mm_min', 'z_travel_mm_min')
            if 'air_xy_mm_min' in v:
                need(number(v['air_xy_mm_min'], True), 'positive Air-only XY simulation feed required')
                motion_keys = tuple(k for k in motion_keys if k != 'draw_mm_min')
        for key in motion_keys:
            need(number(v.get(key), True), 'calibrate motion.' + key)
        if stage != 'air' and vector(m.get('axis_acceleration_mm_s2')):
            if number(v.get('wet_max_xy_acceleration_mm_s2'), True):
                need(max(m['axis_acceleration_mm_s2'][:2]) <= v['wet_max_xy_acceleration_mm_s2'],
                     'installed XY acceleration exceeds calibrated wet-brush limit; adjust controller manually')
            if number(v.get('contact_max_z_acceleration_mm_s2'), True):
                need(m['axis_acceleration_mm_s2'][2] <= v['contact_max_z_acceleration_mm_s2'],
                     'installed Z acceleration exceeds calibrated contact limit; adjust controller manually')
        if vector(m.get('start_work_xyz')) and number(v.get('paper_hover_mm')):
            need(m['start_work_xyz'][2] >= v['paper_hover_mm'], 'initial position must already be at verified no-contact hover or above')
        need(vector(v.get('park_xyz')), 'measure and validate parking target')
        if stage != 'air' and number(v.get('paper_hover_mm')) and number(v.get('paper_approach_mm')):
            need(0 < v['paper_approach_mm'] <= v['paper_hover_mm'], 'paper approach must lie below hover and above contact')
        if number(v.get('paper_hover_mm')) and number(v.get('station_clearance_mm')):
            need(v['station_clearance_mm'] >= v['paper_hover_mm'], 'station clearance below paper hover')
        if vector(v.get('park_xyz')) and number(v.get('station_clearance_mm')):
            need(v['park_xyz'][2] >= v['station_clearance_mm'], 'park below station clearance')
        air_local = v.get('air_local_hover', {})
        need(isinstance(air_local, dict), 'invalid Air local-hover policy')
        if stage == 'air' and isinstance(air_local, dict) and air_local.get('enabled'):
            need(air_local.get('enabled') is True and number(air_local.get('height_mm'), True)
                 and air_local['height_mm'] <= v['paper_hover_mm'], 'invalid Air local-hover height')
            need(self.evidence_passed('air_local_hover_clearance'),
                 'missing current-profile evidence: air_local_hover_clearance')
        local = v.get('local_hover') if stage != 'air' else None
        if local is not None:
            need(isinstance(local, dict) and type(local.get('enabled')) is bool, 'local_hover needs explicit enabled policy')
            if isinstance(local, dict) and local.get('enabled'):
                need(number(local.get('height_mm'), True) and number(v.get('paper_hover_mm'))
                     and number(v.get('paper_approach_mm'))
                     and v['paper_approach_mm'] <= local.get('height_mm', -1) <= v['paper_hover_mm'],
                     'local hover must clear the measured approach boundary and not exceed normal hover')
                need(number(local.get('max_distance_mm'), True), 'positive local hover distance threshold required')
                if stage == 'painting':
                    need(self.evidence_passed('local_hover_clearance'), 'missing current-profile evidence: local_hover_clearance')
        if stage in ('painting', 'fixture', 'calibration'):
            material = self.data.get('material', {})
            for k in ('ink_reload_mm', 'color_reload_mm'):
                need(number(material.get(k), True), 'positive material.' + k + ' required')
            for k in ('water_change_every_washes', 'manual_refill_every_loads'):
                n = material.get(k)
                need(n is None or (type(n) is int and n >= 1), 'checkpoint interval must be null (disabled) or a positive integer: ' + k)
            need(type(material.get('end_cleanup')) is bool, 'explicit end_cleanup policy required')
            need(material.get('liquid_levels') == 'manual_reference', 'manual liquid reference policy required')
            stations = self.data.get('stations', {})
            for role in (tuple(slots) if stage == 'calibration' else ('water', 'sponge', *(('ink',) if 'ink' in media else ()), *slots)):
                st = stations.get(role, {})
                need(bool(st), 'missing station ' + role)
                if not st: continue
                need(st.get('hardware_id') == {'water': 'WELL_1', 'ink': 'WELL_2', 'sponge': 'PURGE'}.get(role, role),
                     role + ': wrong physical station role mapping')
                need(st.get('coordinate_frame') == 'G54', role + ': measured G54 frame required')
                need(st.get('kind') == ('sloped_inkstone' if role in ('water','ink') else 'absorbent' if role == 'sponge' else 'palette'),
                     role + ': incorrect physical operation primitive')
                need(number(st.get('feed_mm_min'), True), role + ': calibrate contact feed')
                need(number(st.get('dwell_seconds')) and st['dwell_seconds'] >= 0, role + ': calibrate dwell')
                try:
                    from .trajectory import station_points, material_station, station_phase_feed
                    station_points(st)
                    if st.get('phase_feeds_mm_min') is not None:
                        for phase in (('purge_contact',) if role == 'sponge' else ('immersion','agitation','withdrawal')):
                            station_phase_feed(st, v, phase)
                    if role == 'sponge':
                        overrides = st.get('material_overrides', {})
                        if not isinstance(overrides, dict): raise ValueError('absorbent material overrides must be a mapping')
                        for material in overrides:
                            variant = material_station(st, material)
                            station_points(variant)
                            if not number(variant.get('dwell_seconds')) or variant['dwell_seconds'] < 0:
                                raise ValueError('invalid material-specific absorbent dwell')
                    if role == 'water':
                        need(type(st.get('wash_cycles')) is int and st['wash_cycles'] >= 1, role + ': calibrate wash cycles')
                        rewet = dict(st, immersion_mm=st.get('rewet_immersion_mm'), dwell_seconds=st.get('rewet_dwell_seconds'), agitation_cycles=0)
                        need(number(rewet['dwell_seconds']) and rewet['dwell_seconds'] >= 0, role + ': calibrate rewet dwell')
                        station_points(rewet)
                    if role == 'sponge':
                        need(type(st.get('repetitions',1)) is int and st.get('repetitions',1) >= 1, role + ': invalid contact repetitions')
                except (KeyError, TypeError, ValueError) as e:
                    errors.append(role + ': missing/invalid contact trajectory parameters: ' + str(e))
                if stage in ('painting', 'fixture'):
                    need(st.get('status') == ('synthetic_fixture' if fixture else 'measured'),
                         role + ': station contact calibration missing')
                need(box(st.get('contact_box_xyz')), role + ': measured allowed contact volume required')
                if number(v.get('station_clearance_mm')) and box(st.get('contact_box_xyz')):
                    need(v['station_clearance_mm'] > st['contact_box_xyz'][1][2],
                         role + ': clearance must exceed entire station contact volume')
            if stage in ('painting', 'fixture'):
                roles = (('ink',) if 'ink' in media else ()) + (('color',) if 'color' in media and not slots else ()) + tuple(slots)
                for role in roles:
                    try:
                        p = self.brush_for('ink' if role == 'ink' else 'color', role)
                        need(p.status == ('synthetic_preview' if fixture else 'measured'),
                             role + ': measured brush response required')
                        need(p.medium in ('ink' if role == 'ink' else 'color', 'unspecified') if fixture
                             else p.medium == ('ink' if role == 'ink' else 'color'),
                             role + ': incompatible brush medium')
                        if not fixture:
                            need(p.brush_id == m.get('mounted_brush_id') and p.hardware_version == m.get('hardware_version'),
                                 role + ': brush/mount hardware does not match measured machine profile')
                            need(p.substrate == m.get('substrate_id') and p.substrate_surface_height_mm == m.get('paper_surface_above_bed_mm'),
                                 role + ': substrate or contact-height context mismatch')
                            observations = [o for o in p.observations if o.stroke_width_mm is not None and o.stroke_width_mm >= 0
                                            and o.quality != 'unrecorded' and o.continuity != 'unrecorded'
                                            and o.water_loading and o.pigment_loading]
                            need(all(any(abs(o.tested_z_mm-z) < 1e-6 for o in observations) for _,z in p.knots),
                                 role + ': each chosen knot depth needs recorded width/continuity/loading observations')
                    except (KeyError, TypeError, ValueError) as e:
                        errors.append(role + ': invalid/missing brush profile: ' + str(e))
            need(vector(v.get('paper_contact_z_range'), 2)
                 and v['paper_contact_z_range'][0] < v['paper_contact_z_range'][1] <= 0,
                 'measure paper contact Z range; no -12 fallback')
        if not fixture:
            checks = list(BASE_CHECKS)
            if stage in ('calibration', 'painting'): checks.append('air_run')
            if stage == 'painting': checks += [c for c in PAINT_CHECKS if c != 'ink_to_color_inspection' or 'color' in media]
            for check in checks:
                need(self.evidence_passed(check), 'missing current-profile evidence: ' + check)
        return errors

    def require(self, stage, slots=(), media=('ink','color')):
        issues = self.issues(stage, slots, media)
        if issues: raise ValueError('EXPORT BLOCKED:\n- ' + '\n- '.join(issues))


def authorize(authorization, profile, plan_hash, stage, job_ids):
    if stage == 'fixture':
        return
    a = authorization or {}
    if not (a.get('stage') == stage and a.get('profile_sha256') == profile.sha256
            and a.get('plan_sha256') == plan_hash and a.get('explicit_operator_authorization') is True
            and set(a.get('job_ids', [])) == set(job_ids)
            and all(isinstance(a.get(k), str) and a[k].strip() for k in ('operator', 'date'))):
        raise ValueError('explicit stage/job/profile/plan-bound operator authorization required')
    require_pre_run(a, stage, job_ids)


PRE_RUN_COMMON = ('coordinates_and_start_verified', 'paper_and_clearance_verified',
                  'tool_and_controller_state_verified')
PRE_RUN_PAINTING = ('brush_clean_and_prepared', 'materials_and_clean_water_prepared')


def require_pre_run(authorization, stage, job_ids):
    """Operator confirms conditions before starting; no routine startup M0."""
    if stage not in ('air', 'painting'): return
    confirmations = (authorization or {}).get('pre_run_confirmations', {})
    if not isinstance(confirmations, dict): raise ValueError('pre-run confirmations must be a job-keyed mapping')
    for name in job_ids:
        required = list(PRE_RUN_COMMON)
        if stage == 'painting':
            required += list(PRE_RUN_PAINTING)
            if name.endswith('_COLOR'): required.append('ink_dry_and_registration_verified')
            if name.startswith('SHARED_'): required.append('continuous_substrate_or_tested_seam_verified')
        record = confirmations.get(name, {})
        if not isinstance(record, dict): raise ValueError('invalid pre-run record for '+name)
        if any(record.get(k) is not True for k in required):
            raise ValueError('pre-run operator confirmation missing for '+name+': '+', '.join(k for k in required if record.get(k) is not True))


def require_physical_layout(profile, manifest, stage):
    """D is unsplit contact, including a physically tested adjacent-sheet seam."""
    if stage == 'painting' and manifest['layout']['mode'] == 'D':
        assembly = profile.data['machine'].get('substrate_assembly')
        if assembly not in ('continuous_sheet', 'adjacent_panels'):
            raise ValueError('Layout D requires explicit continuous_sheet or adjacent_panels substrate assembly')
        if assembly == 'adjacent_panels' and not profile.evidence_passed('continuous_seam'):
            raise ValueError('Layout D adjacent panels require current continuous_seam contact/clearance test evidence')
