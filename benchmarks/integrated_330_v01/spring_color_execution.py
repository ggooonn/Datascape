"""PR35-compatible P2 pigment experiment, with immutable canonical inputs.

Numerical offline review uses the existing FluidNC IR, station primitives and
source-arc clipper. It does not create physical clearance or calibration evidence.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
from math import dist, hypot
from pathlib import Path
import argparse, csv, gzip, hashlib, json, subprocess
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely import STRtree

from datascape.gcode.binding import digest, SIDECAR_SHA
from datascape.gcode.models import Point, Stroke, SourceLocation, SourceSpan, PANELS
from datascape.gcode.clipping import clip_stroke
from datascape.gcode.motion import Fragment
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import (
    Command, emit_station_operation, _station_geometry, shallow_wipe_points)
from datascape.gcode.production.exporter import _serialize, _MOVE, _DWELL
from .spring_runtime import RuntimeBuilder
from .spring_physical_ink import container_operation, air_projection
from .spring_large_baegunmo import PLAN_SHA, runtime
from .numeric_review import check_move

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT/'config/spring_color_execution_v01/policy.json'
BASE = ROOT/'benchmarks/integrated_330_v01/review_spring_large_baegunmo'
REFERENCE_PATHS = [
    'artworks/spring_v13/visible_color.json.gz',
    'artworks/spring_v13/visible_ink.json.gz',
    'artworks/spring_v13/palette.json',
    'docs/experiments/seasonal_color_tone_v01/spring/P2_style_handoff.json.gz',
    'docs/experiments/seasonal_color_tone_v01/spring/style_intent.json.gz',
    'docs/experiments/seasonal_color_tone_v01/FRAMEWORK.md',
    'docs/experiments/seasonal_color_tone_v01/SPRING_P2_HANDOFF.md']
S3A = ['C1','D1','A2','D2','C2','A4','A3','A5','C3','D4','C4','D5']
BANNER = '; OFFLINE COLOR EXPERIMENT - UNCALIBRATED CONTACT/STATION CLEARANCE - REVIEW BEFORE RUN\n'


def read(path):
    path = Path(path); raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok: raise ValueError(message)


def recover(context, policy):
    context = Path(context)
    for path in REFERENCE_PATHS:
        target = context/path; target.parent.mkdir(parents=True, exist_ok=True)
        data = subprocess.check_output(['git','show',policy['seasonal_commit']+':'+path], cwd=ROOT)
        if target.exists(): require(target.read_bytes() == data, 'Stale pinned context: '+path)
        else: target.write_bytes(data)
    return context


def decode_stroke(data):
    data = deepcopy(data)
    data['points'] = tuple(Point(**p) for p in data['points'])
    data['source_locations'] = tuple(SourceLocation(**p) for p in data['source_locations'])
    data['source_spans'] = tuple(SourceSpan(**p) for p in data['source_spans'])
    s = Stroke(**data)
    return replace(s, stroke_id=s.origin_id, source_id=None, source_locations=(), source_spans=())


def load_inputs(context, policy):
    plan = json.loads(gzip.decompress(b''.join(p.read_bytes() for p in sorted(BASE.glob('canonical.plan.json.gz.part*')))))
    require(digest(plan) == PLAN_SHA, 'PR32 canonical plan binding')
    color = read(context/REFERENCE_PATHS[0])['strokes']
    ink = read(context/REFERENCE_PATHS[1])['strokes']
    styles = read(context/REFERENCE_PATHS[4])
    handoff = read(context/REFERENCE_PATHS[3])
    require(not handoff['execution_ready'] and handoff['physical_palette_map'] is None, 'Display handoff cannot be a pigment calibration')
    for path, expected in handoff['source_files'].items(): require(sha(context/path) == expected, 'PR40 source SHA: '+path)
    rich = {r['id']:r for r in color}; st = {r['source_id']:r for r in styles['color']}
    units = []
    for rank, u in enumerate(plan['jobs']['SHARED_COLOR']):
        require(len(u['fragments']) == 1, 'Canonical continuous color source')
        s = decode_stroke(u['fragments'][0]['stroke']); r = rich[s.stroke_id]
        require([[p.x,p.y] for p in s.points] == r['xy_mm'], 'Original color XY differs')
        require(s.pressure_sidecar_sha256 == SIDECAR_SHA, 'Accepted pressure sidecar binding')
        fragments = [Fragment(c,'P2','SHARED',tuple((p.x,900-p.y) for p in c.points)) for c in clip_stroke(s,PANELS[1])]
        if not fragments: continue
        length = sum(sum(hypot(q[0]-p[0],q[1]-p[1]) for p,q in zip(f.work_xy,f.work_xy[1:])) for f in fragments)
        xy = np.array([p for f in fragments for p in f.work_xy]); center = xy.mean(axis=0)
        style = st[s.origin_id]
        # Authored grouping, not a color assignment independently per ray.
        group = r.get('group_id') or r.get('patch_id') or r.get('carrier_basis') or r['owner_id']
        units.append(dict(id=s.origin_id, rank=rank, original=s, fragments=fragments,
            rich=r, style=style, length_mm=length, center=center.tolist(), group=group,
            body=r['owner_id'], legacy_slot=s.color_slot))
    return plan, color, ink, units, read(context/REFERENCE_PATHS[2])


def overlap_audit(units, ink, policy):
    part = read(ROOT/'docs/spring_panels_contact20_v01/review/partition.json.gz')
    physical = {r['source_id'] for r in part['sources'] if r['panel'] == 'P2'}
    ink = [r for r in ink if r['id'] in physical]
    require(len(ink) == 1851, 'PR35 P2 physical ink source inventory')
    lines = [LineString([(x,900-y) for x,y in r['xy_mm']]) for r in ink]
    widths = [max(r.get('width_profile_mm',[r['width_mm']])) for r in ink]
    footprints = [l.buffer(w/2,quad_segs=4) for l,w in zip(lines,widths)]
    tree = STRtree(footprints); out = []
    for u in units:
        color_line = unary_union([LineString(f.work_xy) for f in u['fragments']])
        hits = sorted(int(i) for i in tree.query(color_line,predicate='dwithin',distance=policy['crowded_ink_proxy_distance_mm']))
        exact = [i for i in hits if footprints[i].intersects(color_line)]
        fraction = 0. if not exact else color_line.intersection(unary_union([footprints[i] for i in exact])).length/max(color_line.length,1e-12)
        crowded = len(hits) >= policy['crowded_ink_proxy_neighbors'] and fraction >= policy['crowded_ink_proxy_fraction']
        u.update(ink_proxy_neighbors=len(hits), ink_proxy_covered_fraction=fraction, crowded=crowded,
                 nearby_ink_ids=[ink[i]['id'] for i in hits])
        out.append(dict(source_id=u['id'], neighbors=len(hits), authored_width_centerline_coverage_fraction=fraction,
                        crowded=crowded, nearby_PR35_ink_sources=u['nearby_ink_ids']))
    return out


def slot_for(u):
    r, sty, old = u['rich'],u['style'],u['legacy_slot']
    kind=r.get('color_kind'); role=sty['role']; depth=sty['depth_role']
    if kind == 'terrain':
        if depth == 'far': return 'A2'
        if old in ('D1','D2','D4','A4'): return 'A4'
        if old in ('D5','A5'): return 'A5'
        return 'A2'
    if kind in ('rock','Soil','trunk'):
        return 'A4' if old in ('D1','D2','D4','D5','A4') else 'A5' if old in ('A3','A5','C4') else 'A2'
    if role == 'base' or depth == 'far': return 'C1'
    if role == 'accent': return 'D1' if old in ('D1','D2') else 'C2'
    if old in ('C1','D1','D2'): return 'C1'
    if old == 'C3': return 'C3'
    if old == 'C2': return 'C2'
    return 'A5'


def select(units, policy):
    bodies=defaultdict(list)
    for i,u in enumerate(units):
        u.update(selected=True,selection_reason='Retain canonical flowing source',physical_slot=slot_for(u),dose_factor=1.)
        if u['rich'].get('color_kind') == 'terrain':
            if u['length_mm'] < policy['terrain_minimum_length_mm']:
                u.update(selected=False,selection_reason='Omit short terrain episode; retain longer canonical flow, no bridging')
            if u['crowded']:
                u.update(dose_factor=policy['crowded_color_dose_factor'],selection_reason='Retain terrain with explicitly reduced execution compression in crowded PR35 ink proxy')
                if u['length_mm'] < 9:
                    u.update(selected=False,selection_reason='Omit short terrain episode inside crowded PR35 ink proxy')
        elif u['rich']['source_family'] == 'RSU': bodies[u['body']].append(i)
        elif u['crowded']:
            u.update(dose_factor=policy['crowded_color_dose_factor'],selection_reason='Reduce compression of intentional color overlap with crowded existing ink')
    for body,indices in sorted(bodies.items()):
        depth=units[indices[0]]['style']['depth_role']; cap=policy['vegetation_rays_per_body'][depth]
        # Retain complete long outward rays distributed among existing branches.
        ranked=sorted(indices,key=lambda i:(-units[i]['length_mm'],units[i]['rank']))
        picked=[];branches=set()
        for i in ranked:
            branch=units[i]['rich'].get('growth_branch_id',units[i]['id'])
            if branch not in branches and len(picked)<cap:picked.append(i);branches.add(branch)
        for i in ranked:
            if len(picked)<cap and i not in picked:picked.append(i)
        for i in indices:
            u=units[i]
            if i not in picked:u.update(selected=False,selection_reason='Omit subordinate RSU ray; selected long rays retain this authored vegetation body')
            elif u['crowded']:u.update(dose_factor=policy['crowded_color_dose_factor'],selection_reason='Retain body ray at reduced trial compression in crowded PR35 ink proxy')
            else:u['selection_reason']='Retain coherent long rays across existing body branches'
    order=policy['physical_slot_order']; rank={s:i for i,s in enumerate(order)}
    for u in units:
        u['physical_role']=('base' if u['physical_slot'] in ('A2','A4','C1') else
            'accent' if u['physical_slot']=='D1' or (u['physical_slot']=='C2' and u['style']['role']=='accent') else 'structural')
        u['slot_rank']=rank[u['physical_slot']]
        u['overlap_decision']='omitted' if not u['selected'] else 'weakened trial compression' if u['dose_factor']<1 else 'intentional ink-plus-color / canonical support'
    return [u for u in units if u['selected']]


def footprints(units):
    # Authored display widths are a dependency proxy, never measured wet width.
    return [unary_union([LineString(f.work_xy).buffer(max(u['rich'].get('width_profile_mm',[u['rich']['width_mm']]))/2+.25,quad_segs=4) for f in u['fragments']]) for u in units]


def layering(units):
    shapes=footprints(units); tree=STRtree(shapes)
    pairs=tree.query(shapes,predicate='intersects'); edges=set()
    for i,j in pairs.T:
        i,j=int(i),int(j)
        if i>=j: continue
        a,b=units[i],units[j]
        # Pale mineral and vegetation underlays precede muted cores, jade,
        # fresh growing tips and sparse warm accents. Same-slot order retained.
        ka=(a['slot_rank'],a['rank']);kb=(b['slot_rank'],b['rank'])
        edges.add((i,j) if ka<kb else (j,i))
    last={}
    for i,u in sorted(enumerate(units),key=lambda p:p[1]['rank']):
        key=(u['group'],u['physical_slot'])
        if key in last:edges.add((last[key],i))
        last[key]=i
    return sorted(edges),shapes


def schedule(units, edges, policy):
    incoming=defaultdict(set)
    for a,b in edges:incoming[b].add(a)
    byslot={s:[i for i,u in enumerate(units) if u['physical_slot']==s] for s in policy['physical_slot_order']}
    # Seek an actual overlapping C1/C2 group whose C2 has no intervening-pigment
    # predecessor. This adds a meaningful local excursion, not repeated global
    # per-color visit quotas or switches after every small group.
    eligible=defaultdict(list)
    for i in byslot['C2']:
        if units[i]['style']['depth_role']=='far':continue
        preds=incoming[i]
        if any(units[j]['physical_slot'] in ('A5','C3') for j in preds):continue
        bases=[j for j in preds if units[j]['physical_slot']=='C1' and units[j]['group']==units[i]['group']]
        if bases:eligible[units[i]['group']].append(i)
    group=max(eligible,key=lambda g:(sum(units[i]['length_mm'] for i in eligible[g]),g)) if eligible else None
    early=set(eligible.get(group,[]));done=set();batches=[]
    # A dependency-ready C1/A5 body is the primary no-extra-switch opportunity.
    # C2 requests can be blocked by earlier C2 owners or intervening jade cores.
    pairs=defaultdict(list)
    for i in byslot['A5']:
        bases=[j for j in incoming[i] if units[j]['physical_slot']=='C1' and units[j]['group']==units[i]['group']]
        if bases:pairs[units[i]['group']].append(i)
    primary_group=max(pairs,key=lambda g:(sum(units[i]['length_mm'] for i in pairs[g]),g)) if pairs else None
    def consume(slot,allowed=None,tail_group=None,head_group=None):
        todo={i for i in byslot[slot] if i not in done and (allowed is None or i in allowed)};order=[]
        # Canonical S3a directed within-slot rank is retained, except moving the
        # selected wet-opportunity group to the tail where dependencies permit.
        while todo:
            ready=[i for i in todo if incoming[i]<=done]
            if not ready:break
            i=min(ready,key=lambda i:(units[i]['group']==tail_group if tail_group else False,
                units[i]['group']!=head_group if head_group else False,units[i]['rank']))
            order.append(i);todo.remove(i);done.add(i)
        if order:batches.append(dict(index=len(batches),slot=slot,unit_indices=order,
            purpose='local C1-to-C2 overlap opportunity' if allowed is not None else 'coherent pigment/role batch'))
        return todo
    for slot in policy['physical_slot_order']:
        require(not consume(slot,tail_group=primary_group if slot=='C1' else None,
            head_group=primary_group if slot=='A5' else None),'Unresolved pigment-level layering dependency')
        if slot=='C1' and early:consume('C2',early)
    require(len(done)==len(units),'Schedule did not cover selected sources')
    flat=[i for b in batches for i in b['unit_indices']];ranks={i:k for k,i in enumerate(flat)}
    require(all(ranks[a]<ranks[b] for a,b in edges),'Protected layering order violation')
    actual_early=[i for b in batches if b['purpose']=='local C1-to-C2 overlap opportunity' for i in b['unit_indices']]
    return flat,batches,dict(group=primary_group,primary_pair=['C1','A5'],early_C2_units=actual_early,
        requested_C2_candidates=len(early),blocked_C2_candidates=len(early)-len(actual_early),
        status='unmeasured wetness opportunity; protected order retained' if primary_group else 'no dependency-ready wet pair; retain dry layering',
        physical_wet_window_seconds=None)


def make_profile(policy):
    require((policy['paper_first_touch_z'],policy['paper_approach_z'],policy['paper_hover_z'])==(10,15,20),
        'This experiment retains the confirmed10/15/20 mounting. A changed touch datum requires a separately reviewed mechanical profile, not a silent G54/brush offset.')
    require(policy['distance_limit_mm']>0 and policy['contact_limit'] is None,'Retain the explicit distance-only color reload policy')
    data=read(ROOT/'docs/spring_fine_terrain_v01/review/profile.small.json')
    data['profile_id']='SPRING-P2-COLOR-V01-UNMEASURED';data['evidence']=[]
    b=data['brush_profiles']['color'];b['knots']=[[p,-c] for p,c in policy['color_compression_knots_mm']]
    b.update(brush_id='small-baegunmo-color-trial-v01',status='unverified',observations=[],
        notes=policy['color_response_status'],paper_first_touch_z_mm=policy['paper_first_touch_z'])
    data['motion']['paper_contact_z_range']=[10-max(c for _,c in policy['color_compression_knots_mm']),10]
    data['material']['color_order']=policy['physical_slot_order'];data['material']['color_reload_mm']=policy['distance_limit_mm']
    data['notes']='Offline review only. Retain PR41 machine/motion/station references; independent color curve and explicit unmeasured palette-lip connection.'
    return Profile.from_dict(data)


class ColorMaterials:
    def __init__(self,b,policy):
        self.b=b;self.policy=policy;self.loaded=None;self.distance=0.;self.loads=[];self.operations=[];self.contacts=0
    @property
    def state(self):return 'ordinary_travel' if self.loaded is None else 'partially_depleted' if self.distance>=self.policy['distance_limit_mm'] else 'wet_loaded'
    def water(self,action,cycles=1,dwell=None):
        water=self.b.profile.data['stations']['water']
        start=len(self.b.commands);container_operation(self.b,water,action,cycles,dwell)
        self.operations.append(dict(action=action,station='NEW_WATER_CONTAINER',first_command=start,last_command=len(self.b.commands)-1))
    def cloth(self,repetitions=1):
        st=deepcopy(self.b.profile.data['stations']['sponge']);st['repetitions']=repetitions
        start=len(self.b.commands)
        emit_station_operation(self.b,st,'absorbent_contact','partially_depleted',lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        self.operations.append(dict(action='absorbent_contact',station='PURGE',repetitions=repetitions,first_command=start,last_command=len(self.b.commands)-1))
    def before(self,u,slot=None):
        slot=slot or u['physical_slot'];reason='initial_load' if self.loaded is None else 'pigment_change' if self.loaded!=slot else 'distance_limit' if self.distance>=self.policy['distance_limit_mm'] else None
        if reason is None:return
        previous=self.loaded
        if reason=='pigment_change':self.water('wash');self.cloth();self.water('controlled_rewet',0,1)
        st=deepcopy(self.b.profile.data['stations'][slot]);start=len(self.b.commands)
        emit_station_operation(self.b,st,'pigment_load','partially_depleted' if previous else 'ordinary_travel',lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        # The PR34 color-lip record was not an executed/verified motion. Reuse its
        # explicit coordinates as a REVIEW candidate and release to global35
        # before any connection. Never descend diagonally to the lip.
        x=811 if slot[0] in ('A','C') else 850;y=st['center_xy'][1]
        self.b.time_context='station_transfer';self.b.xy((x,y),35,'partially_depleted');self.b.time_context='station_handling'
        self.b.move((x,y,28),1000,'station_palette_lip_contact','station_approach')
        self.b.move((x-15,y,28),1500,'station_palette_lip_strip','station_approach')
        self.b.lift(35);self.b.time_context=None;self.b.at_station=True;self.b.in_paper=False
        self.operations.append(dict(action='pigment_load',station=slot,first_command=start,last_command=len(self.b.commands)-1))
        self.loads.append(dict(before_source=u['id'],slot=slot,previous_slot=previous,reason=reason,
            previous_distance_mm=self.distance,previous_contacts=self.contacts,
            wash_performed=reason=='pigment_change',first_command=start,last_command=len(self.b.commands)-1))
        self.loaded=slot;self.distance=0.;self.contacts=0
        self.b.marker('material_loaded_'+slot,slot)
    def after(self,u):self.distance+=u['length_mm'];self.contacts+=len(u['fragments'])
    def terminal(self):
        self.b.marker('terminal_cleanup_begin')
        for _ in range(3):self.water('terminal_wash',3,10)
        self.cloth(2);self.b.park('partially_depleted');self.b.marker('terminal_cleanup_complete')


def draw_unit(b,u,material):
    for f in u['fragments']:
        xy=f.work_xy[0];b.time_context='station_transfer' if b.at_station else None
        b.xy(xy,35 if b.at_station else 20,material.state);b.time_context=None;b.at_station=False
        for z,feed,action in [(20,7000,'paper_hover'),(15,7000,'approach'),(10,2000,'initial_contact')]:b.move((*xy,z),feed,action,material.state)
        b.marker('source_fragment_begin',f.stroke.stroke_id,source_id=u['id'])
        curve=b.profile.brush_for('color',u['physical_slot'])
        for k,(xy,p) in enumerate(zip(f.work_xy,f.stroke.points)):
            compression=-curve.z_for(p.pressure)
            z=10-compression*u['dose_factor']
            b.move((*xy,z),2000 if k==0 else b.v['draw_mm_min'],'pressure_variation' if k==0 else 'draw',material.state,
                source_id=u['id'],fragment_id=f.stroke.stroke_id,source_vertex=k,artistic_pressure=p.pressure)
        b.marker('source_fragment_complete',f.stroke.stroke_id,source_id=u['id'])
        for z,feed,action in [(10,2000,'release'),(15,2000,'paper_release_clearance'),(20,7000,'retract')]:b.move((*b.position[:2],z),feed,action,material.state)
        b.in_paper=True;b.last_panel='P2'


def build(units,order,profile,policy,legacy_slots=False):
    b=RuntimeBuilder(profile);m=ColorMaterials(b,policy);events=[]
    b.marker('pre_run_confirmation_required','Clean conditioned small brush; calibrated color and inspected station paths; preserved PR35 P2 registration')
    for rank,i in enumerate(order):
        u=units[i];m.before(u,u['legacy_slot'] if legacy_slots else None)
        first=len(b.commands);b.marker('source_begin',str(rank),source_id=u['id'])
        draw_unit(b,u,m);m.after(u);b.marker('source_complete',str(rank),source_id=u['id'])
        events.append(dict(source_id=u['id'],slot=m.loaded,first_command=first,last_command=len(b.commands)-1,
            distance_since_load_mm=m.distance,contacts_since_load=m.contacts,
            atomic_distance_overrun_mm=max(0,m.distance-policy['distance_limit_mm'])))
    m.terminal()
    return b.commands,dict(loads=m.loads,station_operations=m.operations,events=events,
        pigment_changes=sum(r['reason']=='pigment_change' for r in m.loads),
        same_pigment_reloads=sum(r['reason']=='distance_limit' for r in m.loads),
        initial_loads=sum(r['reason']=='initial_load' for r in m.loads),total_loads=len(m.loads),
        wash_count=sum(r['action']=='wash' for r in m.operations),terminal_water_visits=3,
        maximum_atomic_distance_overrun_mm=max((r['atomic_distance_overrun_mm'] for r in events),default=0),
        drawing_length_mm=sum(units[i]['length_mm'] for i in order),source_count=len(order),
        contact_count=sum(len(units[i]['fragments']) for i in order),M0_count=0)


def unit_record(u):
    keys=['id','rank','length_mm','center','group','body','legacy_slot','physical_slot','physical_role','selected',
        'selection_reason','dose_factor','ink_proxy_neighbors','ink_proxy_covered_fraction','overlap_decision']
    return {k:u[k] for k in keys}|dict(PR40_role=u['style']['role'],depth_role=u['style']['depth_role'],
        family=u['rich']['source_family'],kind=u['rich'].get('color_kind'),
        original_stroke_sha256=digest(asdict(u['original'])),rich_source_sha256=digest(u['rich']),
        original_width_sha256=digest({k:u['rich'].get(k) for k in ['width_mm','width_profile_mm']}),
        canonical_pressure_sha256=digest([p.pressure for p in u['original'].points]),
        clipped_fragments=[asdict(f) for f in u['fragments']])


def verify_numeric(text,commands,profile,units,order,policy,air=False):
    rows=[r for r in text.splitlines() if r and not r.startswith(';')]
    require(rows[0]=='G21 G90 G94 G54' and rows[-1]=='M2','G54 modal prologue / M2')
    expected=[c for c in commands if c.kind!='marker'];require(len(rows)==len(expected)+2,'Numeric command coverage')
    pos=tuple(profile.data['machine']['start_work_xyz']);bounds=[list(pos),list(pos)];pressure_samples=0;rates=[0.,0.,0.]
    unit_map={u['id']:u for u in units};source_sequence=[];lineage=defaultdict(list)
    iterator=iter(rows[1:-1]);station_moves=0
    for c in commands:
        if c.action=='source_begin':source_sequence.append(c.source_id)
        if c.kind=='marker':continue
        row=next(iterator)
        if c.kind=='move':
            m=_MOVE.fullmatch(row);require(m is not None,'Unsupported numeric move')
            x,y,z,feed=map(float,m.groups());target=(x,y,z)
            require(all(abs(a-b)<=5.1e-10 for a,b in zip((*target,feed),(*c.xyz,c.feed_mm_min))),'Numeric XYZ/feed mutation')
            check_move(pos,target,feed,c.action,profile,'air' if air else 'paint',exact_benchmark_draw=False)
            if air:require(z==35,'AIR contains contact')
            if c.action=='travel' and pos[:2]!=target[:2]:require(pos[2]==z and z in (20,35),'XY transit below correct hover')
            if c.time_category=='station_transfer' and pos[:2]!=target[:2]:require(pos[2]==z==35,'Station transfer below global35')
            if c.action.startswith('station_'):station_moves+=1
            if c.artistic_pressure is not None:
                u=unit_map[c.source_id];f=next(f for f in u['fragments'] if f.stroke.stroke_id==c.fragment_id);k=c.source_vertex
                # Independent original-segment interpolation, not copied workXY.
                loc=f.stroke.source_locations[k];a=u['original'].points[loc.segment];b=u['original'].points[loc.segment+1];t=loc.t
                px=a.x+(b.x-a.x)*t;py=a.y+(b.y-a.y)*t;pr=a.pressure+(b.pressure-a.pressure)*t
                require(abs(px-x)<=5.1e-10 and abs(900-py-y)<=5.1e-10,'Original source arc / global P2 XY')
                require(abs(pr-c.artistic_pressure)<1e-12,'Clipped pressure interpolation')
                knots=policy['color_compression_knots_mm'];compression=float(np.interp(pr,[p for p,_ in knots],[v for _,v in knots]))
                require(air or abs(z-(10-compression*u['dose_factor']))<=5.1e-10,'Color trial pressure conversion')
                require(300-1e-9<=x<=600+1e-9 and 0<=y<=900,'P2 registration')
                lineage[c.fragment_id].append(k);pressure_samples+=1
            length=dist(pos,target)
            for k in range(3):
                bounds[0][k]=min(bounds[0][k],target[k]);bounds[1][k]=max(bounds[1][k],target[k])
                if length:rates[k]=max(rates[k],abs(target[k]-pos[k])/length*feed)
            pos=target
        elif c.kind=='dwell':
            m=_DWELL.fullmatch(row);require(m is not None and abs(float(m[1])-c.seconds)<=5.1e-10,'Numeric dwell mutation')
        else:raise ValueError('Unexpected pause/unresolved command')
    require(source_sequence==[units[i]['id'] for i in order],'Executed source identity/order')
    for i in order:
        for f in units[i]['fragments']:require(lineage[f.stroke.stroke_id]==list(range(len(f.stroke.points))),'Missing/repeated source vertex')
    require(pos==(800,800,35),'Terminal park')
    require(any(c.action=='terminal_cleanup_complete' for c in commands),'Terminal cleaning missing')
    return dict(numeric_commands=len(expected),source_count=len(source_sequence),pressure_samples=pressure_samples,
        original_arc_XY_pressure_verified=True,source_order_sha256=digest(source_sequence),AIR_all_Z35=air,
        bounds_G54=bounds,maximum_projected_axis_feeds=rates,station_moves=station_moves,
        terminal_park=list(pos),terminal_cleanup_verified=True,M0_count=0,
        physical_clearance_verified=False,color_response_measured=False,machine_authorized=False)


def export_program(out,name,units,order,profile,policy,commands=None,manifest=None):
    if commands is None:commands,manifest=build(units,order,profile,policy)
    reports={};metrics=runtime(commands,profile);reference=metrics['models']['configuration_reference']
    manifest.update(modeled_seconds=reference['acceleration_sensitive_seconds'],
        modeled_seconds_by_category=reference['acceleration_sensitive_seconds_by_category'],runtime_assumptions=metrics)
    for air in (False,True):
        label=name.replace('COLOR','AIR',1) if air else name;cmds=air_projection(commands,profile) if air else commands
        text=BANNER+_serialize(cmds,profile,digest([units[i]['id'] for i in order]),label,'air' if air else 'painting')
        report=verify_numeric(text,cmds,profile,units,order,policy,air)
        (out/(label+'.gcode')).write_text(text)
        (out/(label+'.gcode.gz')).write_bytes(gzip.compress(text.encode(),mtime=0))
        save(out/(label+'.readback.json'),report);reports['air' if air else 'color']=report
    save(out/(name+'.material.json.gz'),manifest)
    save(out/(name+'.commands.json.gz'),[asdict(c) for c in commands])
    return manifest,reports


def compatibility(units,ink,policy):
    path='docs/spring_a_hierarchy_v01/review/source_roles.json.gz'
    raw=subprocess.check_output(['git','show',policy['ink_compatibility_commit']+':'+path],cwd=ROOT)
    roles=json.loads(gzip.decompress(raw))
    require(len(roles)==1851,'PR42 P2 classifications')
    original_ink={r['id']:r for r in ink};counts=Counter()
    out=[]
    for r in roles:
        # Every newer deferred detail is already ink on the PR35 physical sheet.
        require(r['xy_mm']==original_ink[r['source_id']]['xy_mm'],'Future ink role geometry differs from physical PR35 source')
        detail=r['review_role'];role='fine' if detail.startswith('fine_') else 'color' if detail=='color' else 'main'
        counts[role]+=1
        future='evaluate as future color responsibility' if role=='color' else 'already executed by fine brush; do not duplicate as deferred ink' if role=='fine' else 'main ink; preserve canonical color support only'
        out.append(dict(source_id=r['source_id'],ink_source_index=r['index'],PR42_B_role=role,PR42_B_detail=detail,
            legacy_PR39_variant_B_field=r['variant_B'],
            first_PR35_sheet='already present in ink; no new color-deferred stroke added',
            future_dual_brush_action=future,geometry_in_primary_color=False,
            physical_color_assignment=None,requires_second_print_review=role=='color'))
    require(dict(counts)==dict(main=985,fine=224,color=642),'Pinned PR42 recommended B inventory')
    return dict(compatibility_reference='PR42 '+policy['ink_compatibility_commit'],
        branch=policy['ink_compatibility_branch'],variant='B',source_role_file=path,
        source_role_file_sha256=hashlib.sha256(raw).hexdigest(),
        role_field_contract='Use PR42 review_role for recommended B; inherited variant_B fields still describe PR39 and must not be used as the current allocation',
        unpublished_successor_used=False,records=out,counts=dict(counts),
        canonical_color_records=[dict(source_id=u['id'],primary_selected=u['selected'],
            slot=u['physical_slot'],reuse='unchanged original color geometry; reconsider overlap/dose against second ink sheet') for u in units],
        first_job_automatically_valid_for_second_sheet=False)


def calibration_outputs(out,selected,profile,policy):
    """Explicitly new spare-sheet coupons, isolated from canonical artwork."""
    slots=[s for s in policy['physical_slot_order'] if any(u['physical_slot']==s for u in selected)]
    b=RuntimeBuilder(profile);m=ColorMaterials(b,policy)
    for slot in slots:
        u=next(u for u in selected if u['physical_slot']==slot);m.before(u)
    m.terminal()
    export_program(out,'SPRING_P2_COLOR_STATIONS_ONLY_REVIEW',[],[],profile,policy,b.commands,
        dict(source_count=0,contact_count=0,drawing_length_mm=0,loads=m.loads,station_operations=m.operations,
             pigment_changes=len(slots)-1,same_pigment_reloads=0,total_loads=len(slots),terminal_water_visits=3,
             purpose='Station-only contact calibration trace; inspect holder, rim, bottom, immersion and lip first'))
    coupons=[]
    for row,slot in enumerate(slots):
        for column,pressure in enumerate((.2,.4,.6,.8)):
            x=320+column*65;y=55+row*32
            points=tuple(Point(x+v,y,pressure) for v in (0,15,40))
            s=Stroke(f'COLOR-RESPONSE-COUPON/{slot}/p{pressure:.1f}',points,'COLOR-CALIBRATION',slot,'color')
            fragments=[Fragment(c,'P2-SPARE-COUPON','SHARED',tuple((p.x,900-p.y) for p in c.points)) for c in clip_stroke(s,PANELS[1])]
            coupons.append(dict(id=s.origin_id,original=s,fragments=fragments,physical_slot=slot,legacy_slot=slot,
                dose_factor=1.,length_mm=40.,group='SPARE-COUPON-'+slot))
    # A second local pair deliberately shares a support strip to inspect the
    # C1/A5 interaction. The wash/load interval is part of the experiment.
    for slot,offset in [('C1',0.),('A5',.8)]:
        points=tuple(Point(350+v,275+offset,.4) for v in (0,20,60))
        s=Stroke('COLOR-OVERLAP-COUPON/'+slot,points,'COLOR-CALIBRATION',slot,'color')
        fragments=[Fragment(c,'P2-SPARE-COUPON','SHARED',tuple((p.x,900-p.y) for p in c.points)) for c in clip_stroke(s,PANELS[1])]
        coupons.append(dict(id=s.origin_id,original=s,fragments=fragments,physical_slot=slot,legacy_slot=slot,
            dose_factor=1.,length_mm=60.,group='SPARE-OVERLAP-COUPON'))
    export_program(out,'SPRING_P2_COLOR_RESPONSE_COUPON_SPARE_ONLY_REVIEW',coupons,list(range(len(coupons))),profile,policy)
    save(out/'COLOR_RESPONSE_COUPON_LAYOUT.json',dict(canonical_artwork=False,spare_hanji_only=True,
        registration='A separate300x330mm backed coupon at global X300..600,Y570..900; do not use the PR35 artwork',
        paper_touch_z=10,pressure_columns=[.2,.4,.6,.8],slot_rows=slots,
        original_top_down_y_rows=[55+row*32 for row in range(len(slots))],
        original_top_down_y_overlap=[275,275.8],color_curve=policy['color_compression_knots_mm'],
        observations_required=['actual touch','stroke width/taper','wet/dry hue','long-flow continuity','C1/A5 overlap state','wash contamination']))
    save(out/'calibration_source_units.json.gz',[dict(id=u['id'],original=asdict(u['original']),
        fragments=[asdict(f) for f in u['fragments']],physical_slot=u['physical_slot'],legacy_slot=u['legacy_slot'],
        dose_factor=u['dose_factor'],length_mm=u['length_mm'],group=u['group']) for u in coupons])
    return coupons


def generate(context,output,comparisons=True):
    policy=read(POLICY);context=recover(context,policy);out=Path(output)
    require(not out.exists(),'Use a fresh output directory');out.mkdir(parents=True)
    print('Loading pinned color, accepted pressure and PR35 physical ink',flush=True)
    plan,color,ink,units,palette=load_inputs(context,policy)
    overlaps=overlap_audit(units,ink,policy);selected=select(units,policy)
    edges,shapes=layering(selected);order,batches,wet=schedule(selected,edges,policy)
    profile=make_profile(policy);save(out/'profile.color.UNMEASURED.json',profile.data);save(out/'policy.json',policy)
    save(out/'source_selection.json.gz',[unit_record(u) for u in units])
    for r,u in zip(overlaps,units):r.update(decision=u['overlap_decision'],dose_factor=u['dose_factor'])
    save(out/'PR35_overlap_audit.json.gz',dict(physical_ink_sources=1851,added_deferred_ink_sources=0,
        proxy='Authored display ink widths and centerline intersections; not calibrated wet footprints',records=overlaps))
    save(out/'future_dual_brush_compatibility.json.gz',compatibility(units,ink,policy))
    save(out/'layering_constraints.json.gz',dict(display_proxy_only=True,edges=edges,
        unit_ids=[u['id'] for u in selected],palette_precedence=policy['physical_slot_order'],
        interpretation='Local pale support before grouped cores, jade before fresh tips; canonical within-slot overlapping source order'))
    save(out/'schedule.json',dict(batches=[b|dict(source_count=len(b['unit_indices']),
        drawing_length_mm=sum(selected[i]['length_mm'] for i in b['unit_indices'])) for b in batches],wet_opportunity=wet))
    print('Selected',len(selected),'of',len(units),'P2 color sources;',len(edges),'protected local edges;',len(batches),'pigment batches',flush=True)
    commands,manifest=build(selected,order,profile,policy)
    primary,reports=export_program(out,'SPRING_P2_COLOR_PR35_COMPLETE_REVIEW',selected,order,profile,policy,commands,manifest)
    # Independent files finish clean and parked; clean brush/start pose must be
    # restored manually. Wet-opportunity C1/C2 stays inside one stage.
    stage_groups=[('01_MINERAL_BASE',{'A2','A4'}),('02_PALE_GROWTH_AND_LOCAL_OVERLAP',{'C1','EARLY_C2'}),
                  ('03_GROUPED_CORES',{'A5','C3'}),('04_FRESH_TIPS_AND_ACCENTS',{'C2','D1'})]
    stages={};assigned=set()
    for label,slots in stage_groups:
        indexes=[]
        for b in batches:
            early=b['purpose']=='local C1-to-C2 overlap opportunity'
            key='EARLY_C2' if early else b['slot']
            if key in slots:indexes.extend(b['unit_indices'])
        indexes=[i for i in order if i in set(indexes)]
        if not indexes:continue
        require(not assigned.intersection(indexes),'Separated stage duplicate');assigned.update(indexes)
        print('Exporting stage',label,len(indexes),flush=True)
        m,r=export_program(out,'SPRING_P2_COLOR_PR35_'+label+'_REVIEW',selected,indexes,profile,policy);stages[label]=m
    require(assigned==set(order),'Separated stage coverage')
    # Source-count-restrained D4, not a display-alpha-to-dose conversion.
    d4=sorted([u for u in selected if u['legacy_slot']=='D4' and u['rich'].get('color_kind') in ('rock','Soil') and u['style']['depth_role']=='near'],key=lambda u:(-u['length_mm'],u['rank']))[:policy['D4_candidate_max_sources']]
    save(out/'D4_restrained_comparison.json',dict(primary_D4_sources=0,comparison_only=True,
        trial_sources=[dict(source_id=u['id'],primary_slot=u['physical_slot'],candidate_slot='D4',length_mm=u['length_mm']) for u in d4],
        drawing_length_mm=sum(u['length_mm'] for u in d4),concentration_recipe=None,
        note='Whole original structural paths only; zero D5 blanket substitution; candidate not added to main job'))
    compare={}
    if comparisons:
        scenarios=[('S3a_full_legacy',units,sorted(range(len(units)),key=lambda i:units[i]['rank']),True),
                   ('S3a_selected_legacy',selected,sorted(range(len(selected)),key=lambda i:selected[i]['rank']),True),
                   ('S3a_selected_mapped',selected,sorted(range(len(selected)),key=lambda i:(S3A.index(selected[i]['physical_slot']),selected[i]['rank'])),False)]
        for name,us,ids,legacy in scenarios:
            print('Timing comparison',name,flush=True)
            cs,ms=build(us,ids,profile,policy,legacy_slots=legacy);t=runtime(cs,profile)
            compare[name]=dict(source_count=len(ids),drawing_mm=ms['drawing_length_mm'],pigment_changes=ms['pigment_changes'],
                loads=ms['total_loads'],same_pigment_reloads=ms['same_pigment_reloads'],
                modeled_seconds=t['models']['configuration_reference']['acceleration_sensitive_seconds'],
                modeled_seconds_by_category=t['models']['configuration_reference']['acceleration_sensitive_seconds_by_category'],
                shared_color_trial_curve_and_station_policy=True,historical_execution_byte_replay=False)
            del cs
        compare['proposed']=dict(source_count=len(order),drawing_mm=primary['drawing_length_mm'],pigment_changes=primary['pigment_changes'],
            loads=primary['total_loads'],same_pigment_reloads=primary['same_pigment_reloads'],modeled_seconds=primary['modeled_seconds'],
            modeled_seconds_by_category=primary['modeled_seconds_by_category'])
        compare['attribution_seconds']=dict(content_reduction=compare['S3a_full_legacy']['modeled_seconds']-compare['S3a_selected_legacy']['modeled_seconds'],
            slot_mapping=compare['S3a_selected_legacy']['modeled_seconds']-compare['S3a_selected_mapped']['modeled_seconds'],
            protected_layering_and_overlap_cost=compare['proposed']['modeled_seconds']-compare['S3a_selected_mapped']['modeled_seconds'])
    save(out/'S3a_comparison.json',compare)
    slot_report=[]
    for slot in policy['physical_slot_order']:
        us=[u for u in selected if u['physical_slot']==slot]
        if not us:continue
        slot_report.append(dict(slot=slot,name=palette['slots'][slot]['name'],source_count=len(us),
            drawing_mm=sum(u['length_mm'] for u in us),contacts=sum(len(u['fragments']) for u in us),
            load_count=sum(r['slot']==slot for r in primary['loads']),
            batch_visits=sum(b['slot']==slot for b in batches),roles=dict(Counter(u['physical_role'] for u in us)),
            legacy_source_slots=dict(Counter(u['legacy_slot'] for u in us)),
            source_groups=sorted(set(u['group'] for u in us)),
            intended_overlap_slots=sorted(set(selected[b]['physical_slot'] for a,b in edges if selected[a]['physical_slot']==slot and selected[b]['physical_slot']!=slot))))
    save(out/'pigment_slots.json',slot_report)
    replacements=defaultdict(lambda:dict(count=0,length_mm=0.))
    for u in selected:
        k=u['legacy_slot']+' -> '+u['physical_slot'];replacements[k]['count']+=1;replacements[k]['length_mm']+=u['length_mm']
    save(out/'source_to_slot_replacements.json',dict(replacements))
    save(out/'fine_color_OFFLINE_ONLY.json',dict(contact_program_generated=False,reason='No measured fine-brush pigment response or tip registration',
        trial_reload_policy_after_calibration=dict(distance_mm=450,contacts=10,trigger='OR; before next source; atomic overrun logged'),
        candidate_source_ids=[u['id'] for u in selected if u['physical_role']=='accent' and u['length_mm']<8 and u['style']['depth_role']=='near'],
        primary_brush='small Baegunmo; no manual brush exchange'))
    summary=dict(status='Complete numerical offline review; physical calibration and station inspection pending',
        source_commit=policy['physical_ink_commit'],ink_compatibility_commit=policy['ink_compatibility_commit'],seasonal_commit=policy['seasonal_commit'],
        canonical_plan_sha256=PLAN_SHA,pinned_reference_hashes={p:sha(context/p) for p in REFERENCE_PATHS},
        total_P2_color_sources=len(units),selected_sources=len(selected),omitted_sources=len(units)-len(selected),
        original_P2_drawing_mm=sum(u['length_mm'] for u in units),primary=primary,stages=stages,
        pigment_order=[b['slot'] for b in batches],protected_edges=len(edges),wet_opportunity=wet,
        physical_tests_performed=False,machine_authorized=False)
    save(out/'summary.json',summary)
    calibration_outputs(out,selected,profile,policy)
    from .spring_color_review import make_review
    make_review(out,context,units,selected,order,batches,edges,commands,palette,ink,summary,d4)
    save(out/'verification.json',dict(primary_readback=reports,protected_edges_verified=len(edges),
        stage_partition_complete=True,PR35_deferred_ink_added=0,canonical_files_modified=False,
        original_source_pressure_and_widths_preserved=True,execution_compression_changes_documented=True,
        review_does_not_certify_physical_clearance=True))
    files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='MANIFEST_SHA256.json'}
    save(out/'MANIFEST_SHA256.json',files)
    print(json.dumps({k:summary[k] for k in ['total_P2_color_sources','selected_sources','omitted_sources','pigment_order']},indent=2),flush=True)
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--context',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--skip-comparison',action='store_true');a=ap.parse_args()
    generate(a.context,a.output,not a.skip_comparison)
