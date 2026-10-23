"""Spatial material handling and synchronized XYZ IR, without device I/O."""
from dataclasses import dataclass, asdict
from copy import deepcopy
from math import sqrt, hypot, cos, sin, pi, dist
from collections import Counter
from ..layout import WorkToMachine
from ..motion import MotionSettings, stroke_events, Action
from ..estimation import rest_to_rest_seconds
from .profiles import number, vector, box, exact_free_segments


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
    direct = (exact_free_segments(machine) and machine.get('machine_bounds_reference') == 'axis_reference'
              and machine.get('keepout_boxes') == [])
    if not number(margin) or margin < 0:
        if not direct: raise ValueError('measured tool envelope or exact inspected full-tool path required')
        # This zero is only unused obstacle expansion, NOT a measured radius.
        # The actual tool is explicitly inspected over the exact segments below.
        margin = 0.
    bounds = machine['machine_bounds_xyz']
    # Axis-reference travel limits already describe carriage reference points.
    # Tool clearance is still enforced against expanded obstacles and full-tool
    # validated corridors. Legacy envelope bounds keep their existing erosion.
    if machine.get('machine_bounds_reference') == 'axis_reference':
        inner = bounds
    else:
        inner = [[x+margin for x in bounds[0]], [x-margin for x in bounds[1]]]
    for p in (offset.xyz(a), offset.xyz(b)):
        if any(not x-1e-9 <= q <= y+1e-9 for q, x, y in zip(p, *inner)):
            raise ValueError('unreachable machine trajectory after G54 offset/tool margin: ' + str(p))
    for obstacle in machine['keepout_boxes']:
        expanded = [[x-margin for x in obstacle[0]], [x+margin for x in obstacle[1]]]
        if interval_in_box(a, b, expanded) is not None:
            raise ValueError('swept-tool path intersects measured keepout')
    spans = [v for bounds in machine['validated_free_boxes']
             if (v := interval_in_box(a, b, bounds)) is not None]
    if direct:
        for start, end in machine['validated_free_segments']:
            delta = tuple(y-x for x,y in zip(start,end))
            norm2 = sum(d*d for d in delta)
            def on_segment(p):
                if norm2 < 1e-20: return dist(p,start) < 1e-9
                t = sum((x-y)*d for x,y,d in zip(p,start,delta))/norm2
                return -1e-10 <= t <= 1+1e-10 and dist(p,tuple(x+t*d for x,d in zip(start,delta))) < 1e-8
            if on_segment(a) and on_segment(b):
                spans.append((0.,1.))
                break
    spans.sort()
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
    time_category: str = ''
    travel_phase: str = ''


class Builder:
    def __init__(self, profile):
        self.profile = profile
        self.m = profile.data['machine']; self.v = profile.data['motion']
        self.position = tuple(self.m['start_work_xyz'])
        self.commands = []; self.counts = Counter(); self.lengths = Counter()
        self.nominal_seconds = 0.; self.stop_segment_seconds = 0.; self.seconds_by_action = Counter()
        require_path(self.position, self.position, self.m)
        self.in_paper = False; self.last_panel = None; self.at_station = False
        self.time_context = None
        self.paper_transfer_height = self.v['paper_hover_mm']

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
        category = self.time_context or ('drawing' if action == 'draw' else
            'paper_engagement' if action in ('approach', 'initial_contact', 'pressure_variation',
                'release', 'paper_release_clearance', 'retract') else
            'station_handling' if action.startswith('station_') else 'non_drawing_travel')
        self.commands.append(Command('move', action, target, speed, state,
                                     projected_acceleration_mm_s2=acceleration,
                                     axis_velocity_mm_min=axis_rates, time_category=category, **lineage))
        if speed < feed-1e-9: self.counts['feed_limited_segments'] += 1
        self.counts[action] += 1
        self.lengths['synchronized_drawing_3d_mm' if action == 'draw' else 'non_draw_mm'] += length
        if action.startswith('station_'): self.lengths['station_operation_mm'] += length
        self.position = target

    def dwell(self, seconds, action):
        if not number(seconds) or seconds < 0: raise ValueError('invalid dwell')
        self.commands.append(Command('dwell', action, seconds=seconds, time_category='station_handling'))
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
            departure, arrival = self.v['wet_departure_mm'], self.v['wet_arrival_mm']
            scale = min(1., length/(departure+arrival))
            for phase, f, cap in (('departure', departure*scale/length, self.v['wet_departure_mm_min']),
                           ('main', 1-arrival*scale/length, feed), ('arrival', 1., self.v['wet_arrival_mm_min'])):
                p = tuple(a+f*(b-a) for a, b in zip(start, end))
                self.move(p, min(feed, cap), 'travel', state, travel_phase=phase)
        else:
            self.move(end, feed, 'travel', state)

    def park(self, state='ordinary_travel'):
        p = tuple(self.v['park_xyz']); before = self.lengths['non_draw_mm']
        self.time_context = 'station_transfer' if self.at_station else None
        self.lift(max(self.v['station_clearance_mm'], p[2]))
        self.xy(p[:2], self.position[2], state)
        self.move(p, self.v['z_travel_mm_min'], 'park')
        if self.at_station: self.lengths['station_to_park_3d_mm'] += self.lengths['non_draw_mm']-before
        self.in_paper = False; self.last_panel = None; self.at_station = False
        self.time_context = None

    def pause(self, reason, state='ordinary_travel'):
        self.park(state)
        self.commands.append(Command('pause', 'manual_checkpoint', message=reason))
        self.counts['manual_checkpoint'] += 1

    def result(self):
        from .timing import estimate_commands
        timing = (estimate_commands(self.commands, self.profile)
                  if number(self.m.get('junction_deviation_mm'), True) else
                  {'available': False, 'reason': 'controller junction deviation unrecorded',
                   'verified_physical_time': False})
        self.lengths['station_transfer_3d_mm'] = sum(self.lengths[k] for k in ('station_access_3d_mm','station_return_3d_mm','station_to_park_3d_mm'))
        return {'counts': dict(self.counts), 'distances': dict(self.lengths),
                'commanded_feed_subtotal_seconds': self.nominal_seconds,
                'stop_each_segment_model_seconds': self.stop_segment_seconds,
                'commanded_feed_seconds_by_action': dict(self.seconds_by_action),
                'manual_and_drying_seconds': None,
                'controller_reached_speeds_verified': False,
                'full_job_time_verified': False,
                'M0_count': sum(c.kind == 'pause' for c in self.commands),
                'M0_reasons': [c.message for c in self.commands if c.kind == 'pause'],
                'timing': timing}


def palette_pattern_xy(station):
    """One shared XY grammar for wet loading and elevated dry simulation."""
    center = station['center_xy']; radius = station['radius_mm']
    repeats = station['revolutions']; steps = station['segments_per_revolution']
    if not vector(center, 2) or not number(radius, True):
        raise ValueError('measure palette center and approve loading radius')
    if type(repeats) is not int or repeats < 1 or type(steps) is not int or steps < 12:
        raise ValueError('positive revolutions and >=12 polygon segments required')
    points = []
    for _ in range(repeats):
        if station.get('pattern', 'circle') == 'circle':
            points += [(center[0]+radius*cos(2*pi*j/steps), center[1]+radius*sin(2*pi*j/steps))
                       for j in range(steps+1)]
            points.append(tuple(center))
        elif station['pattern'] == 'cross':
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                points += [(center[0]+dx, center[1]+dy), tuple(center)]
        else: raise ValueError('unknown palette loading pattern')
    return tuple(points)


def station_points(station):
    """Measured two-point slope, circle/cross palette, or gentle sponge contact."""
    bounds = station['contact_box_xyz']
    def check(p):
        if not vector(p) or interval_in_box(p, p, bounds) is None:
            raise ValueError('station contact leaves calibrated volume')
        return tuple(p)
    result = _station_geometry(station, check)
    shallow_wipe_points(station, check)
    return result


def shallow_wipe_xy(station):
    """Separately registered solid section; never extend the liquid slope line."""
    w = station.get('shallow_wipe', {})
    if not w.get('enabled'): return ()
    start, end, middle = w.get('start_xy'), w.get('end_xy'), w.get('return_xy')
    count, offset = w.get('passes'), w.get('second_pass_x_offset_mm')
    if (not all(vector(p, 2) for p in (start,end,middle)) or
        type(count) is not int or count < 1 or not number(offset) or
        start[1] <= station['shallow_surface_xyz'][1] or end[1] <= start[1]):
        raise ValueError('register distinct Y+ shallow solid-section XY and pass count')
    points = [tuple(start), tuple(end)]
    for _ in range(1,count):
        x = start[0]+offset
        points += [(x,end[1]), (x,middle[1]), (x,start[1]), (x,end[1])]
    return tuple(points)


def shallow_wipe_points(station, check=None):
    """Measured solid contact plus lifted re-entry, with separately auditable feeds.

    A nominal sloped floor cannot supply these surface/compliance measurements.
    Missing values fail before the first physical station command is emitted.
    """
    xy = shallow_wipe_xy(station)
    if not xy: return ()
    w = station['shallow_wipe']
    surface, compression, lift = (w.get(k) for k in ('surface_z','compression_mm','reentry_lift_mm'))
    if not number(surface) or not number(compression, True) or not number(lift, True):
        raise ValueError('shallow_wipe requires actual surface_z, compression_mm and reentry_lift_mm')
    contact = surface-compression
    clear = max(surface+lift, station['shallow_surface_xyz'][2]+station['stone_gap_mm'],
                station['liquid_reference_z']+station['exit_above_liquid_mm'])
    if clear >= 35: raise ValueError('shallow wipe re-entry must fit below global Z35')
    if check is None:
        def check(p):
            if interval_in_box(p,p,station['contact_box_xyz']) is None:
                raise ValueError('shallow wipe leaves calibrated contact/re-entry volume')
            return tuple(p)
    out = [(check((*station['shallow_surface_xyz'][:2], clear)), 'reentry')]
    out += [(check((*xy[0],clear)), 'reentry'), (check((*xy[0],contact)), 'shallow_contact'),
            (check((*xy[1],contact)), 'shallow_wipe')]
    for i in range(2,len(xy),4):
        side, middle, start, end = xy[i:i+4]
        out += [(check((*side,contact)), 'shallow_wipe'), (check((*side,clear)), 'reentry'),
                (check((*middle,clear)), 'reentry'), (check((*start,clear)), 'reentry'),
                (check((*start,contact)), 'shallow_contact'), (check((*end,contact)), 'shallow_wipe')]
    return tuple(out)


def _station_geometry(station, check):
    """Shared numeric grammar; official station_points always adds physical bounds."""
    kind = station['kind']
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
                if station.get('agitation_bidirectional', False):
                    points += [check((dip[0]-offset[0], dip[1]-offset[1], dip[2]))]
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
        points += [check((*xy, z)) for xy in palette_pattern_xy(station)]
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


def station_phase_feed(station, motion, phase):
    """Explicit liquid/fabric caps are independent of the legacy contact clamp."""
    feeds = station.get('phase_feeds_mm_min')
    if feeds is None:
        return min(station['feed_mm_min'], motion['contact_mm_min'])
    cap = motion.get('station_phase_limits_mm_min', {}).get(phase)
    feed = feeds.get(phase)
    if not number(feed, True) or not number(cap, True) or feed > cap:
        raise ValueError('station phase feed requires an independent positive cap: ' + phase)
    return feed


def emit_station_operation(b, station, action, state, geometry=station_points):
    """Shared measured/review grammar; the official default checks contact volume."""
    st = station; dip, points = geometry(st)
    wipes = shallow_wipe_points(st)
    explicit = st.get('phase_feeds_mm_min') is not None
    if explicit:
        approach_z = st.get('approach_z')
        reference = st.get('surface_z') if st['kind'] == 'absorbent' else st.get('liquid_reference_z')
        if not number(approach_z) or not number(reference) or not reference < approach_z <= b.v['station_clearance_mm']:
            raise ValueError('station fast approach must end above contact reference and below global clearance')
    else: approach_z = st['contact_box_xyz'][1][2]
    access_before = b.lengths['non_draw_mm']; b.time_context = 'station_transfer'
    b.xy(dip[:2], b.v['station_clearance_mm'], state)
    b.lengths['station_access_3d_mm'] += b.lengths['non_draw_mm']-access_before
    b.time_context = 'station_handling'
    approach = (*dip[:2], approach_z)
    b.move(approach, b.v['station_approach_mm_min'], 'station_approach', 'station_approach')
    repeats = st.get('repetitions', 1) if st['kind'] == 'absorbent' else 1
    if type(repeats) is not int or repeats < 1: raise ValueError('positive contact repetition count required')
    for cycle in range(repeats):
        if cycle: b.move(approach, b.v['station_approach_mm_min'], 'station_approach', 'station_approach')
        phase = 'purge_contact' if st['kind'] == 'absorbent' else 'immersion'
        b.move(dip, station_phase_feed(st, b.v, phase), 'station_'+action, 'station_approach', travel_phase=phase)
        b.dwell(st['dwell_seconds'], action+'_dwell')
        for index, point in enumerate(points):
            phase = ('withdrawal' if index == len(points)-1 else
                     'palette_loading' if st['kind'] == 'palette' and 'palette_loading' in st.get('phase_feeds_mm_min',{}) else 'agitation')
            b.move(point, station_phase_feed(st, b.v, phase), 'station_'+action, 'station_approach', travel_phase=phase)
        for point, phase in wipes:
            b.move(point, station_phase_feed(st, b.v, phase), 'station_'+action,
                   'station_approach', travel_phase=phase)
        if explicit and st['kind'] == 'absorbent':
            b.move(approach, station_phase_feed(st, b.v, 'purge_contact'),
                   'station_'+action, 'station_approach', travel_phase='purge_release')
    retract_before = b.lengths['non_draw_mm']; b.lift(b.v['station_clearance_mm'])
    b.lengths['station_retract_3d_mm'] += b.lengths['non_draw_mm']-retract_before
    b.in_paper = False; b.last_panel = None; b.at_station = True; b.time_context = None


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
        if not number(st['feed_mm_min'], True): raise ValueError('station operation feed must be positive')
        emit_station_operation(b, st, action, self.state)
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


def local_transition_geometry(previous, following, distance_since_load, material, policy):
    """Only consecutive complete original sources; never hides a material service."""
    if not policy or not policy.get('enabled') or not following: return False
    a,z=previous[-1],following[0]
    if (a.setup,a.panel,a.stroke.medium,a.stroke.color_slot)!=(z.setup,z.panel,z.stroke.medium,z.stroke.color_slot): return False
    if a.stroke.origin_id==z.stroke.origin_id: return False
    limit=material['ink_reload_mm'] if a.stroke.medium=='ink' else material['color_reload_mm']
    if distance_since_load >= limit: return False
    return dist(a.work_xy[-1],z.work_xy[0]) <= policy['max_distance_mm']+1e-12


def local_transition_height(profile, previous, following, distance_since_load, stage):
    normal=profile.data['motion']['paper_hover_mm'];policy=profile.data['motion'].get('local_hover')
    if stage=='air' or not local_transition_geometry(previous,following,distance_since_load,profile.data['material'],policy):return normal
    if stage=='painting' and not profile.evidence_passed('local_hover_clearance'):
        raise ValueError('local hover requires current clearance/recovery evidence')
    h=policy['height_mm'];a=(*previous[-1].work_xy[-1],h);z=(*following[0].work_xy[0],h)
    try:require_path(a,z,profile.data['machine'])
    except ValueError:return normal  # A blocked low corridor falls back to normal; the actual path is still validated.
    return h


def draw_fragment(b, fragment, material, stage, retract_height=None):
    s = fragment.stroke
    if stage == 'air':
        # An Air Run does not instantiate the contact-event model or require
        # its unmeasured approach boundary, pressure curve or wet-brush limits.
        lineage = {'source_id': s.origin_id, 'fragment_id': s.stroke_id}
        b.xy(fragment.work_xy[0], b.v['station_clearance_mm'] if not b.in_paper else b.v['paper_hover_mm'])
        b.move((*fragment.work_xy[0], b.v['paper_hover_mm']), b.v['z_travel_mm_min'], 'paper_hover')
        for i, (xy, p) in enumerate(zip(fragment.work_xy, s.points)):
            b.move((*xy, b.v['paper_hover_mm']), b.v.get('air_xy_mm_min', b.v['draw_mm_min']), 'draw',
                   **lineage, source_vertex=i, artistic_pressure=p.pressure)
        b.in_paper = True; b.last_panel = fragment.panel
        return
    else:
        depth = b.profile.brush_for(s.medium, s.color_slot)
        low, high = b.v['paper_contact_z_range']
        for p in s.points:
            z = depth.z_for(p.pressure)
            if not low <= z <= high: raise ValueError('pressure mapping outside measured paper contact Z range')
    # Reuse v0.2 event/contact model and each clipped vertex without resampling.
    settings = MotionSettings(depth, hover_z_mm=b.v['paper_hover_mm'], approach_z_mm=b.v['paper_approach_mm'])
    lineage = {'source_id': s.origin_id, 'fragment_id': s.stroke_id}
    entry = b.paper_transfer_height if b.in_paper and b.last_panel==fragment.panel else b.v['paper_hover_mm']
    height = entry
    if not b.in_paper or b.last_panel != fragment.panel: height = b.v['station_clearance_mm']
    state = 'ordinary_travel' if material is None else material.state
    return_before = b.lengths['non_draw_mm']
    b.time_context = 'station_transfer' if b.at_station else None
    b.xy(fragment.work_xy[0], height, state)
    b.move((*fragment.work_xy[0], entry), b.v['z_travel_mm_min'], 'paper_hover')
    if b.at_station: b.lengths['station_return_3d_mm'] += b.lengths['non_draw_mm']-return_before
    b.at_station = False
    b.time_context = None
    for e in stroke_events(fragment, settings):
        if e.action in (Action.LIFT, Action.TRAVEL): continue
        z = b.v['paper_hover_mm'] if stage == 'air' else e.preview_z_mm
        xy = e.work_xy
        action = e.action.value
        feed = {Action.DRAW: b.v['draw_mm_min'], Action.APPROACH: b.v['paper_approach_mm_min'],
                Action.CONTACT: b.v['paper_contact_mm_min'], Action.PRESSURE: b.v['paper_contact_mm_min'],
                Action.RELEASE: b.v['paper_release_mm_min']}[e.action]
        b.move((*xy, z), feed, action, state, **lineage,
               source_vertex=e.source_vertex, artistic_pressure=e.artistic_pressure)
    if stage != 'air':
        b.move((*fragment.work_xy[-1], b.v['paper_approach_mm']), b.v['paper_release_mm_min'],
               'paper_release_clearance', state, **lineage)
    retract_height=b.v['paper_hover_mm'] if retract_height is None else retract_height
    b.move((*fragment.work_xy[-1], retract_height), b.v['z_travel_mm_min'], 'retract', state, **lineage)
    b.paper_transfer_height=retract_height
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
        distance_after=0. if material is None else material.distance+sum(hypot(b.x-a.x,b.y-a.y) for f in unit for a,b in zip(f.stroke.points,f.stroke.points[1:]))
        following=units[n+1] if n+1<len(units) else None
        retract=local_transition_height(profile,unit,following,distance_after,stage)
        for i,f in enumerate(unit):draw_fragment(b,f,material,stage,retract if i==len(unit)-1 else None)
        if material is not None: material.after(unit)
        b.marker('source_complete', str(n), source_id=unit[0].stroke.origin_id)
        if retract < b.v['paper_hover_mm']:b.marker('local_hover_transfer',str(retract),source_id=unit[0].stroke.origin_id)
    if material is not None and profile.data['material']['end_cleanup']:
        material.wash()
    b.park('ordinary_travel' if material is None else material.state)
    b.marker('job_complete', 'Parked; program terminates with M2. Manual review/drying/preparation occurs between programs.')
    result = b.result()
    result['artwork_xy_drawing_mm'] = sum(hypot(q.x-p.x, q.y-p.y) for u in units for f in u for p,q in zip(f.stroke.points,f.stroke.points[1:]))
    result['threshold_overruns'] = [] if material is None else material.overruns
    result['loads_per_slot'] = {} if material is None else dict(material.loads)
    return b.commands, result
