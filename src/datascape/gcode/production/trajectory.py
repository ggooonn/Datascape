"""Spatial material handling and synchronized XYZ IR, without device I/O."""
from dataclasses import dataclass, asdict
from copy import deepcopy
from math import sqrt, hypot, cos, sin, pi, dist
from collections import Counter
from ..layout import WorkToMachine
from ..motion import MotionSettings, stroke_events, Action
from ..estimation import rest_to_rest_seconds
from .profiles import number, vector, box


def interval_in_box(a, b, bounds):
    lo, hi = 0., 1.
    for x, y, low, high in zip(a, b, *bounds):
        delta = y-x
        if delta == 0:
            if not low <= x <= high: return None
        else:
            p, q = sorted(((low-x)/delta, (high-x)/delta))
            lo, hi = max(lo, p), min(hi, q)
            if lo > hi: return None
    return lo, hi


def require_path(a, b, machine):
    """Validate the complete segment, not just its endpoints or nominal XY fit."""
    offset = WorkToMachine(tuple(machine['g54_to_machine_xyz']), verified=True)
    margin = machine['tool_envelope_margin_mm']
    bounds = machine['machine_bounds_xyz']
    inner = [[x+margin for x in bounds[0]], [x-margin for x in bounds[1]]]
    for p in (offset.xyz(a), offset.xyz(b)):
        if any(not x-1e-9 <= q <= y+1e-9 for q, x, y in zip(p, *inner)):
            raise ValueError('unreachable machine trajectory after G54 offset/tool margin: ' + str(p))
    for obstacle in machine['keepout_boxes']:
        expanded = [[x-margin for x in obstacle[0]], [x+margin for x in obstacle[1]]]
        if interval_in_box(a, b, expanded) is not None:
            raise ValueError('swept-tool path intersects measured keepout')
    spans = sorted(v for bounds in machine['validated_free_boxes']
                   if (v := interval_in_box(a, b, bounds)) is not None)
    cursor = 0.
    for lo, hi in spans:
        if lo > cursor+1e-10: break
        cursor = max(cursor, hi)
    if cursor < 1-1e-10:
        raise ValueError('complete path is outside validated swept-tool free-space corridors')


@dataclass(frozen=True)
class Command:
    kind: str
    action: str
    xyz: tuple | None = None
    feed_mm_min: float | None = None
    travel_state: str = 'ordinary_travel'
    source_id: str | None = None
    fragment_id: str | None = None
    source_vertex: int | None = None
    artistic_pressure: float | None = None
    seconds: float | None = None
    message: str = ''
    projected_acceleration_mm_s2: float | None = None
    axis_velocity_mm_min: tuple | None = None


class Builder:
    def __init__(self, profile):
        self.profile = profile
        self.m = profile.data['machine']; self.v = profile.data['motion']
        self.position = tuple(self.m['start_work_xyz'])
        self.commands = []; self.counts = Counter(); self.lengths = Counter()
        self.nominal_seconds = 0.; self.stop_segment_seconds = 0.; self.seconds_by_action = Counter()
        require_path(self.position, self.position, self.m)
        self.in_paper = False; self.last_panel = None; self.at_station = False

    def move(self, target, feed, action, state='ordinary_travel', **lineage):
        if not vector(target) or not number(feed, True): raise ValueError('invalid spatial motion')
        target = tuple(target); require_path(self.position, target, self.m)
        delta = tuple(y-x for x, y in zip(self.position, target)); length = sqrt(sum(d*d for d in delta))
        speed = feed; acceleration = min(self.m['axis_acceleration_mm_s2'])
        if length:
            unit = tuple(abs(d)/length for d in delta)
            speed = min(speed, *(r/u for r, u in zip(self.m['axis_max_rate_mm_min'], unit) if u))
            z_limit = self.v['pressure_z_mm_min'] if action in ('draw', 'pressure_variation') else self.v['z_travel_mm_min']
            if unit[2]: speed = min(speed, z_limit/unit[2])
            acceleration = min(r/u for r, u in zip(self.m['axis_acceleration_mm_s2'], unit) if u)
            axis_rates = tuple(speed*u for u in unit)
            self.nominal_seconds += length/speed*60
            self.seconds_by_action[action] += length/speed*60
            self.stop_segment_seconds += rest_to_rest_seconds(length, speed, acceleration)
        else: axis_rates = (0., 0., 0.)
        self.commands.append(Command('move', action, target, speed, state,
                                     projected_acceleration_mm_s2=acceleration,
                                     axis_velocity_mm_min=axis_rates, **lineage))
        if speed < feed-1e-9: self.counts['feed_limited_segments'] += 1
        self.counts[action] += 1
        self.lengths['synchronized_drawing_3d_mm' if action == 'draw' else 'non_draw_mm'] += length
        if action.startswith('station_'): self.lengths['station_operation_mm'] += length
        self.position = target

    def dwell(self, seconds, action):
        if not number(seconds) or seconds < 0: raise ValueError('invalid dwell')
        self.commands.append(Command('dwell', action, seconds=seconds))
        self.nominal_seconds += seconds; self.stop_segment_seconds += seconds
        self.seconds_by_action[action] += seconds
        self.counts[action] += 1

    def marker(self, action, message='', **lineage):
        self.commands.append(Command('marker', action, message=message, **lineage))
        self.counts[action] += 1

    def lift(self, height):
        # Raising only. Never descend at an unknown XY while switching regions.
        if self.position[2] < height:
            self.move((*self.position[:2], height), self.v['z_travel_mm_min'], 'lift')

    def xy(self, xy, height, state='ordinary_travel'):
        self.lift(height)
        feed = self.v[state+'_mm_min']
        start = self.position; end = (*xy, self.position[2]); length = dist(start, end)
        # Travel-only segmentation: low-speed wet departure AND arrival. FluidNC
        # lookahead handles acceleration; no per-move acceleration command exists.
        if state == 'wet_loaded' and length:
            edge = min(self.v['wet_departure_mm'], length/2)
            for f, cap in ((edge/length, self.v['wet_edge_mm_min']),
                           (1-edge/length, feed), (1., self.v['wet_edge_mm_min'])):
                p = tuple(a+f*(b-a) for a, b in zip(start, end))
                self.move(p, min(feed, cap), 'travel', state)
        else:
            self.move(end, feed, 'travel', state)

    def park(self, state='ordinary_travel'):
        p = tuple(self.v['park_xyz']); before = self.lengths['non_draw_mm']
        self.lift(max(self.v['station_clearance_mm'], p[2]))
        self.xy(p[:2], self.position[2], state)
        self.move(p, self.v['z_travel_mm_min'], 'park')
        if self.at_station: self.lengths['station_to_park_3d_mm'] += self.lengths['non_draw_mm']-before
        self.in_paper = False; self.last_panel = None; self.at_station = False

    def pause(self, reason, state='ordinary_travel'):
        self.park(state)
        self.commands.append(Command('pause', 'manual_checkpoint', message=reason))
        self.counts['manual_checkpoint'] += 1

    def result(self):
        self.lengths['station_transfer_3d_mm'] = sum(self.lengths[k] for k in ('station_access_3d_mm','station_return_3d_mm','station_to_park_3d_mm'))
        return {'counts': dict(self.counts), 'distances': dict(self.lengths),
                'commanded_feed_subtotal_seconds': self.nominal_seconds,
                'stop_each_segment_model_seconds': self.stop_segment_seconds,
                'commanded_feed_seconds_by_action': dict(self.seconds_by_action),
                'manual_and_drying_seconds': None,
                'controller_reached_speeds_verified': False,
                'full_job_time_verified': False,
                'M0_count': sum(c.kind == 'pause' for c in self.commands),
                'M0_reasons': [c.message for c in self.commands if c.kind == 'pause']}


def station_points(station):
    """Measured two-point slope, circle/cross palette, or gentle sponge contact."""
    kind = station['kind']; bounds = station['contact_box_xyz']
    def check(p):
        if not vector(p) or interval_in_box(p, p, bounds) is None:
            raise ValueError('station contact leaves calibrated volume')
        return tuple(p)
    if kind == 'sloped_inkstone':
        deep = station['deep_surface_xyz']; shallow = station['shallow_surface_xyz']
        if not vector(deep) or not vector(shallow): raise ValueError('measure deep/shallow stone points')
        level = station['liquid_reference_z']; immersion = station['immersion_mm']; gap = station['stone_gap_mm']
        if not all(number(v, True) for v in (immersion, gap)) or not number(level):
            raise ValueError('measured liquid reference, immersion and positive stone gap required')
        if not number(station['exit_above_liquid_mm'], True): raise ValueError('positive calibrated liquid exit height required')
        dip = check((*deep[:2], level-immersion))
        if dip[2] < deep[2]+gap: raise ValueError('inkstone immersion could scrape deep surface')
        end = check((*shallow[:2], max(shallow[2]+gap, level+station['exit_above_liquid_mm'])))
        # Linear withdrawal lies above the linearly measured stone slope because
        # its two endpoint gaps are nonnegative. No full 3D surface is invented.
        agitation = station.get('agitation_cycles', 0)
        if type(agitation) is not int or agitation < 0: raise ValueError('invalid gentle agitation cycle count')
        points = []
        if agitation:
            offset = station['agitation_xy_mm']; floor = station['agitation_floor_max_z']
            if not vector(offset, 2) or not number(floor) or dip[2] < floor+gap:
                raise ValueError('measure agitation-area maximum floor and non-scraping clearance')
            for _ in range(agitation):
                points += [check((dip[0]+offset[0], dip[1]+offset[1], dip[2])), dip]
        return dip, tuple(points)+(end,)
    if kind == 'palette':
        center = station['center_xy']; level = station['liquid_reference_z']
        immersion = station['immersion_mm']; radius = station['radius_mm']
        if not vector(center, 2) or not all(number(v, True) for v in (immersion, radius)) or not number(level):
            raise ValueError('measure palette center/level/immersion/radius')
        if not all(number(station[k]) for k in ('bottom_z', 'bottom_gap_mm')) or not number(station['exit_above_liquid_mm'], True):
            raise ValueError('measured palette floor/gap/exit required')
        z = level-immersion
        if z < station['bottom_z']+station['bottom_gap_mm'] or station['bottom_gap_mm'] <= 0:
            raise ValueError('palette bottom scrape risk')
        dip = check((*center, z)); points = []
        repeats = station['revolutions']; steps = station['segments_per_revolution']
        if type(repeats) is not int or repeats < 1 or type(steps) is not int or steps < 12:
            raise ValueError('positive revolutions and >=12 polygon segments required')
        pattern = station.get('pattern', 'circle')
        for _ in range(repeats):
            if pattern == 'circle':
                points += [check((center[0]+radius*cos(2*pi*j/steps),
                                  center[1]+radius*sin(2*pi*j/steps), z)) for j in range(steps+1)]
                points.append(dip)
            elif pattern == 'cross':
                for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                    points += [check((center[0]+dx, center[1]+dy, z)), dip]
            else: raise ValueError('unknown palette loading pattern')
        points.append(check((*center, level+station['exit_above_liquid_mm'])))
        return dip, tuple(points)
    if kind == 'absorbent':
        xy = station['center_xy']; surface = station['surface_z']; compression = station['compression_mm']
        if not vector(xy, 2) or not number(surface) or not number(compression, True):
            raise ValueError('measure absorbent surface and gentle compression')
        dip = check((*xy, surface-compression))
        wipe = station.get('wipe_xy_mm', [0, 0])
        if not vector(wipe, 2): raise ValueError('invalid optional short linear wipe')
        points = () if wipe == [0, 0] else (check((xy[0]+wipe[0], xy[1]+wipe[1], dip[2])), dip)
        return dip, points
    raise ValueError('unknown physical station kind')


def material_station(station, material):
    """Optional calibrated absorbent compression/dwell per ink, color or slot."""
    result = deepcopy(station)
    overrides = result.get('material_overrides', {})
    key = None if material is None else (material if material in overrides else ('ink' if material == 'ink' else 'color'))
    values = overrides.get(key, {})
    if not isinstance(values, dict) or set(values)-{'compression_mm', 'dwell_seconds'}:
        raise ValueError('absorbent overrides may change only compression_mm and dwell_seconds')
    result.update(values)
    return result


class Materials:
    def __init__(self, builder):
        self.b = builder; self.p = builder.profile.data['material']
        self.loaded = None; self.distance = 0.; self.washes = 0; self.loads = Counter(); self.overruns = []

    @property
    def state(self):
        if self.loaded is None: return 'ordinary_travel'
        limit = self.p['ink_reload_mm'] if self.loaded == 'ink' else self.p['color_reload_mm']
        return 'partially_depleted' if self.distance >= limit else 'wet_loaded'

    def station(self, role, action, material_key=None):
        b = self.b; st = deepcopy(b.profile.data['stations'][role])
        if role == 'sponge': st = material_station(st, material_key or self.loaded)
        if action == 'controlled_rewet':
            st['immersion_mm'] = st['rewet_immersion_mm']
            st['dwell_seconds'] = st['rewet_dwell_seconds']
            st['agitation_cycles'] = 0
        dip, points = station_points(st)
        if not number(st['feed_mm_min'], True): raise ValueError('station operation feed must be positive')
        # Approach above the station at GLOBAL clearance, then descend vertically.
        access_before = b.lengths['non_draw_mm']
        b.xy(dip[:2], b.v['station_clearance_mm'], self.state)
        b.lengths['station_access_3d_mm'] += b.lengths['non_draw_mm']-access_before
        approach = (*dip[:2], st['contact_box_xyz'][1][2])
        b.move(approach, b.v['station_approach_mm_min'], 'station_approach', 'station_approach')
        repeats = st.get('repetitions', 1) if st['kind'] == 'absorbent' else 1
        if type(repeats) is not int or repeats < 1: raise ValueError('positive gentle-contact repetition count required')
        for cycle in range(repeats):
            if cycle: b.move(approach, b.v['station_approach_mm_min'], 'station_approach', 'station_approach')
            b.move(dip, min(st['feed_mm_min'], b.v['contact_mm_min']), 'station_'+action, 'station_approach')
            b.dwell(st['dwell_seconds'], action+'_dwell')
            for p in points:
                b.move(p, min(st['feed_mm_min'], b.v['contact_mm_min']), 'station_'+action, 'station_approach')
        retract_before = b.lengths['non_draw_mm']
        b.lift(b.v['station_clearance_mm'])
        b.lengths['station_retract_3d_mm'] += b.lengths['non_draw_mm']-retract_before
        b.in_paper = False; b.last_panel = None; b.at_station = True
        b.marker(action, role)

    def wash(self):
        interval = self.p['water_change_every_washes']
        if interval is not None and self.washes > 0 and self.washes % interval == 0:
            self.b.pause('CHANGE/INSPECT clean water and brush; restore manual reference levels; resume only without moving axes', self.state)
        previous = self.loaded
        self.loaded = None; self.distance = 0.
        st = self.b.profile.data['stations']['water']; cycles = st['wash_cycles']
        if type(cycles) is not int or cycles < 1: raise ValueError('positive calibrated wash_cycles required')
        for _ in range(cycles): self.station('water', 'wash')
        self.station('sponge', 'absorbent_contact', previous)
        self.station('water', 'controlled_rewet')
        self.washes += 1; self.b.marker('full_wash')

    def load(self, slot, same_color=False):
        interval = self.p['manual_refill_every_loads']
        if interval is not None and self.loads[slot] > 0 and self.loads[slot] % interval == 0:
            self.b.pause('VERIFY manually maintained liquid reference in '+slot+'; inspect brush; do not jog or change offsets', self.state)
        self.station('ink' if slot == 'ink' else slot, 'same_color_reload' if same_color else 'pigment_load')
        self.loads[slot] += 1; self.loaded = slot; self.distance = 0.

    def before(self, unit):
        s = unit[0].stroke; target = 'ink' if s.medium == 'ink' else s.color_slot
        if target != self.loaded:
            if self.loaded is not None: self.wash()
            self.b.marker('material_change', target)
            self.load(target)
        elif self.distance >= (self.p['ink_reload_mm'] if target == 'ink' else self.p['color_reload_mm']):
            self.load(target, same_color=True)

    def after(self, unit):
        self.distance += sum(hypot(b.x-a.x, b.y-a.y) for f in unit
                             for a, b in zip(f.stroke.points, f.stroke.points[1:]))
        limit = self.p['ink_reload_mm'] if self.loaded == 'ink' else self.p['color_reload_mm']
        if self.distance > limit:
            self.overruns.append({'source_id': unit[0].stroke.origin_id,
                                  'distance_since_active_load_mm': self.distance,
                                  'overrun_mm': self.distance-limit})


def draw_fragment(b, fragment, material, stage):
    s = fragment.stroke
    if stage == 'air':
        depth = None
    else:
        depth = b.profile.brush_for(s.medium, s.color_slot)
        low, high = b.v['paper_contact_z_range']
        for p in s.points:
            z = depth.z_for(p.pressure)
            if not low <= z <= high: raise ValueError('pressure mapping outside measured paper contact Z range')
    # Reuse v0.2 event/contact model and each clipped vertex without resampling.
    settings = MotionSettings(depth, hover_z_mm=b.v['paper_hover_mm'], approach_z_mm=b.v['paper_approach_mm'])
    lineage = {'source_id': s.origin_id, 'fragment_id': s.stroke_id}
    height = b.v['paper_hover_mm']
    if not b.in_paper or b.last_panel != fragment.panel: height = b.v['station_clearance_mm']
    state = 'ordinary_travel' if material is None else material.state
    return_before = b.lengths['non_draw_mm']
    b.xy(fragment.work_xy[0], height, state)
    b.move((*fragment.work_xy[0], b.v['paper_hover_mm']), b.v['z_travel_mm_min'], 'paper_hover')
    if b.at_station: b.lengths['station_return_3d_mm'] += b.lengths['non_draw_mm']-return_before
    b.at_station = False
    for e in stroke_events(fragment, settings):
        if e.action in (Action.LIFT, Action.TRAVEL): continue
        z = b.v['paper_hover_mm'] if stage == 'air' else e.preview_z_mm
        xy = e.work_xy
        action = e.action.value
        feed = b.v['draw_mm_min'] if e.action == Action.DRAW else b.v['contact_mm_min']
        b.move((*xy, z), feed, action, state, **lineage,
               source_vertex=e.source_vertex, artistic_pressure=e.artistic_pressure)
    b.move((*fragment.work_xy[-1], b.v['paper_hover_mm']), b.v['z_travel_mm_min'], 'lift', **lineage)
    b.in_paper = True; b.last_panel = fragment.panel


def build_job(profile, units, stage):
    b = Builder(profile); material = None if stage == 'air' else Materials(b)
    b.marker('pre_run_confirmation_required', 'Verify G54/start, paper, clean brush and supplies BEFORE starting; export authorization records operator confirmation')
    if stage == 'air':
        for role in profile.data['motion'].get('air_station_roles', []):
            st = profile.data['stations'][role]
            xy = st.get('center_xy') or st.get('deep_surface_xyz', [])[:2]
            if not vector(xy, 2): raise ValueError('measure station XY for optional non-contact station air tour')
            b.xy(xy, b.v['station_clearance_mm']); b.marker('station_air_only', role)
    for n, unit in enumerate(units):
        if material is not None: material.before(unit)
        b.marker('source_begin', str(n), source_id=unit[0].stroke.origin_id)
        for f in unit: draw_fragment(b, f, material, stage)
        if material is not None: material.after(unit)
        b.marker('source_complete', str(n), source_id=unit[0].stroke.origin_id)
    if material is not None and profile.data['material']['end_cleanup']:
        material.wash()
    b.park('ordinary_travel' if material is None else material.state)
    b.marker('job_complete', 'Parked; program terminates with M2. Manual review/drying/preparation occurs between programs.')
    result = b.result()
    result['artwork_xy_drawing_mm'] = sum(hypot(q.x-p.x, q.y-p.y) for u in units for f in u for p,q in zip(f.stroke.points,f.stroke.points[1:]))
    result['threshold_overruns'] = [] if material is None else material.overruns
    result['loads_per_slot'] = {} if material is None else dict(material.loads)
    return b.commands, result
