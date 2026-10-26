"""Small-Baegunmo Spring INK review: immutable source, explicit execution layer.

Numerical programs are calibration-gated review artifacts, not machine approval.
No controller I/O, FluidNC writes, color output or pressure clamping is provided.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict,replace
from pathlib import Path
from math import dist,hypot,acos,degrees
import argparse,csv,gzip,hashlib,heapq,io,json,subprocess
import numpy as np
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString
from shapely import STRtree
from datascape.gcode.binding import digest,SIDECAR_SHA
from datascape.gcode.models import Point,Stroke,SourceLocation,SourceSpan
from datascape.gcode.motion import Fragment
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import Command,emit_station_operation,_station_geometry,shallow_wipe_points,serialized_feed_cap
from datascape.gcode.production.exporter import _serialize,_MOVE,_DWELL,save_json
from .spring_runtime import RuntimeBuilder
from .spring_large_baegunmo import PLAN_SHA,COMPRESSION_KNOTS,RELATIVE_KNOTS,reference_z,runtime
from .numeric_review import BANNER,check_move

ROOT=Path(__file__).resolve().parents[2]
POLICY=ROOT/'config/spring_physical_ink_v01/policy.json'
BASE=ROOT/'benchmarks/integrated_330_v01/review_spring_large_baegunmo'
INK_SHA='4501ccbb589e20d304e74957cb36f32bf605b9a22eff20011ce32c938f4406b5'
STRUCTURAL={'trunk-contour','branch-contour','ink-contour','primary-joint','feature-shoulder','bedding-band','cross-fracture','D'}


def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)
def save(p,obj):save_json(Path(p),obj)
def csv_write(p,rows):
    if not rows:return
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def length(xy):return float(np.linalg.norm(np.diff(np.asarray(xy),axis=0),axis=1).sum())
def percentile(values):
    a=np.asarray(values);order=np.argsort(np.argsort(a,kind='stable'),kind='stable');return order/max(1,len(a)-1)


def recover_context(destination):
    """Read pinned context objects only; never check out or execute old source."""
    destination=Path(destination)
    names=['visible_ink.json.gz','source/fields_manifest.json']+[f'source/fields.npz.part{i:02d}' for i in range(5)]
    pin=read(POLICY)['spring_source_commit']
    for name in names:
        p=destination/name
        if not p.exists():
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(subprocess.check_output(['git','show',pin+':artworks/spring_v13/'+name],cwd=ROOT))
    return destination


def load_inputs(context):
    parts=sorted(BASE.glob('canonical.plan.json.gz.part*'))
    plan=read(BASE/'canonical.plan.json.gz') if not parts else json.loads(gzip.decompress(b''.join(p.read_bytes() for p in parts)))
    require(digest(plan)==PLAN_SHA,'PR32 canonical plan hash mismatch')
    units=plan['jobs']['SHARED_INK'];require(len(units)==3345,'complete Spring ink required')
    require(sha(context/'visible_ink.json.gz')==INK_SHA,'pinned rich ink hash mismatch')
    rows=read(context/'visible_ink.json.gz')['strokes'];fragments=[]
    for i,(u,r) in enumerate(zip(units,rows)):
        require(u['source_id']==r['id'] and len(u['fragments'])==1,'canonical source identity')
        f=u['fragments'][0];s=dict(f['stroke']);s['points']=tuple(Point(**p) for p in s['points'])
        s['source_locations']=tuple(SourceLocation(**p) for p in s['source_locations']);s['source_spans']=tuple(SourceSpan(**p) for p in s['source_spans'])
        stroke=Stroke(**s);frag=Fragment(stroke,f['panel'],f['setup'],tuple(tuple(p) for p in f['work_xy']))
        require([[p.x,p.y] for p in stroke.points]==r['xy_mm'],'canonical XY changed')
        require(list(frag.work_xy)==[(p.x,900-p.y) for p in stroke.points],'G54 projection changed')
        require(stroke.pressure_sidecar_sha256==SIDECAR_SHA and not stroke.reversible and not stroke.reorderable,'source pressure/direction locks')
        fragments.append(frag)
    require(sum(len(f.stroke.points) for f in fragments)==69101,'ink pressure sample count')
    return plan,rows,fragments


def features(context,rows):
    m=read(context/'source/fields_manifest.json');raw=[]
    for part in m['parts']:
        p=context/'source'/part['path'];require(sha(p)==part['sha256'],'terrain context part changed');raw.append(p.read_bytes())
    payload=b''.join(raw);require(hashlib.sha256(payload).hexdigest()==m['file_sha256'],'terrain context aggregate')
    data=np.load(io.BytesIO(payload));occupied=data['f_occupied'].astype(bool)
    distance,indices=distance_transform_edt(~occupied,return_indices=True);xyz=data['f_xyz'];q=data['f_depth']
    out=[]
    for i,r in enumerate(rows):
        xy=np.asarray(r['xy_mm']);pix=np.clip(np.floor(xy).astype(int),[0,0],[599,899]);x=pix[:,0];y=pix[:,1]
        yy=indices[0,y,x];xx=indices[1,y,x];valid=distance[y,x]<=6
        z=xyz[yy,xx,2];depth=q[yy,xx]
        sourceq=r.get('source_forward_profile_m')
        if sourceq is not None:depth=np.asarray(sourceq)
        elif r.get('source_object_depth_m',r.get('source_forward_m')) is not None:depth=np.full(len(xy),r.get('source_object_depth_m',r.get('source_forward_m')))
        delta=np.diff(xy,axis=0);norm=np.linalg.norm(delta,axis=1);u=delta/np.maximum(norm[:,None],1e-12)
        angles=np.arccos(np.clip(np.sum(u[:-1]*u[1:],axis=1),-1,1)) if len(u)>1 else np.array([0.])
        out.append(dict(index=i,source_id=r['id'],family=r['source_family'],grammar=r.get('grammar_part',''),
            owner=r['owner_id'],length_mm=length(xy),depth_m=float(np.nanmedian(depth)),
            source_terrain_elevation_m=float(np.nanmedian(z[valid])) if valid.any() else None,
            terrain_attachment_valid_fraction=float(valid.mean()),curvature=float(np.sum(angles)/max(length(xy),.1)),
            maximum_turn_degrees=float(np.max(angles)*180/np.pi),sharp_turns_over_90=int(np.sum(angles>np.pi/2)),
            original_width_mm=float(r['width_mm']),parent_contour=r.get('upstream_source_stroke_id',r['id'])))
    depths=np.array([r['depth_m'] for r in out]);lo,hi=np.quantile(depths,[1/3,2/3])
    for r in out:r['depth_band']='near' if r['depth_m']<=lo else 'middle' if r['depth_m']<=hi else 'far'
    return out,dict(context_fields_sha256=m['file_sha256'],depth_band_cutpoints_m=[float(lo),float(hi)],
        elevation='Preserved F2 world Z; nearest occupied projected sample within6mm; not screen-Y height or authoritative source-mass identity',
        depth='Original per-stroke forward depth where present, otherwise sampled F2 forward depth; near/middle/far are study tertiles',
        height_not_authoritative_for_object_tree_tops=True)


def allocate(fs,policy):
    n=len(fs);target=round(n*policy['dark_source_fraction_target']);L=np.array([f['length_mm'] for f in fs]);height=np.array([f['source_terrain_elevation_m'] or 0 for f in fs]);h=percentile(height);curve=percentile([f['curvature'] for f in fs])
    score=.45*h+.35*curve
    eligible=[];mandatory=[i for i,f in enumerate(fs) if f['family']=='D']
    for i,f in enumerate(fs):
        fam=f['family'];grammar=f['grammar'];bonus={'A':0,'B':.25,'D':2,'rock':.55,'Soil':-.9,'tree':.0,'RSU':-.25}[fam]
        if grammar in STRUCTURAL:bonus+=.5
        if grammar in ('foliage-field','twig'):bonus-=.45
        if f['depth_band']=='near':bonus-=.25
        score[i]+=bonus
        # A remains predominantly light; only elevated/curved candidates enter.
        if fam!='A' or h[i]>=.65 or curve[i]>=.75:eligible.append(i)
    A_cap=int(sum(f['family']=='A' for f in fs)*policy['A_dark_source_fraction_cap'])
    want=L.sum()*policy['dark_length_fraction_target'];mandatory=set(mandatory)
    def choose(lam):
        ranked=sorted((i for i in eligible if i not in mandatory),key=lambda i:(-(score[i]+lam*L[i]/max(float(np.median(L)),1)),i))
        result=set(mandatory);a=0
        for i in ranked:
            if fs[i]['family']=='A':
                if a>=A_cap:continue
                a+=1
            result.add(i)
            if len(result)==target:break
        require(len(result)==target,'insufficient eligible dark source candidates')
        return result
    low,high=-20.,20.;candidates=[]
    for _ in range(70):
        mid=(low+high)/2;pick=choose(mid);total=sum(L[i] for i in pick);candidates.append(pick)
        if total<want:low=mid
        else:high=mid
    dark=min(candidates,key=lambda pick:(abs(sum(L[i] for i in pick)-want),sorted(pick)))
    for i,f in enumerate(fs):
        f['ink']='DARK_INK' if i in dark else 'LIGHT_INK';f['allocation_score']=float(score[i]);f['elevation_rank']=float(h[i]);f['curvature_rank']=float(curve[i])
        f['allocation_reason']='D emphasis' if f['family']=='D' else ('ranked high/elevated/curved or structural accent; length/count balanced' if i in dark else 'primary light field / subordinate detail')
    return dict(original_sources=n,original_drawing_mm=float(L.sum()),target_dark_sources=target,
        light_sources=n-len(dark),dark_sources=len(dark),dark_source_fraction=len(dark)/n,
        light_drawing_mm=float(sum(L[i] for i in range(n) if i not in dark)),dark_drawing_mm=float(sum(L[i] for i in dark)),
        dark_drawing_fraction=float(sum(L[i] for i in dark)/L.sum()),A_dark_sources=sum(fs[i]['family']=='A' for i in dark),
        A_total_sources=sum(f['family']=='A' for f in fs),all_D_dark=all(f['ink']=='DARK_INK' for f in fs if f['family']=='D'))


def constraints(rows,fs,policy):
    shapes=[LineString(r['xy_mm']).buffer(max(r.get('width_profile_mm',[r['width_mm']]))/2,quad_segs=6) for r in rows]
    arr=np.array(shapes,dtype=object);pairs=STRtree(arr).query(arr,predicate='dwithin',distance=2*policy['display_dependency_guard_mm']);pairs=pairs[:,pairs[0]<pairs[1]].T
    edges={tuple(map(int,v)) for v in pairs};last={};contours=defaultdict(list)
    for i,f in enumerate(fs):
        owner=f['owner']
        if not owner.startswith('baseline/'):
            if owner in last:edges.add((last[owner],i))
            last[owner]=i
        if f['family']=='A':contours[f['parent_contour']].append(i)
    # Preserve fragment order within authored parent contours.
    for group in contours.values():edges.update(zip(group,group[1:]))
    # Bipartite nearest-contour spanning forest. Cycles are NOT claimed to be
    # perfectly alternating: their frustrated parity is explicitly audited.
    A=[i for i,f in enumerate(fs) if f['family']=='A' and f['ink']=='LIGHT_INK'];neighbor={};tree=STRtree(np.array([shapes[i] for i in A],dtype=object))
    graph=defaultdict(set);adjacent=set()
    for ii,i in enumerate(A):
        hits=tree.query(shapes[i],predicate='dwithin',distance=policy['contour_adjacency_mm'])
        hits=[A[int(j)] for j in hits if A[int(j)]!=i and fs[A[int(j)]]['parent_contour']!=fs[i]['parent_contour']]
        if hits:
            j=min(hits,key=lambda j:(shapes[i].distance(shapes[j]),j));graph[i].add(j);graph[j].add(i);adjacent.add(tuple(sorted((i,j))))
    parity={}
    for seed in A:
        if seed in parity:continue
        parity[seed]=0;queue=[seed]
        for u in queue:
            for v in sorted(graph[u]):
                if v not in parity:parity[v]=1-parity[u];queue.append(v)
    for i,f in enumerate(fs):f['A_light_parity']=parity.get(i);f['pass_index']=0
    return sorted(edges),shapes,sorted(adjacent)


def events_schedule(fs,edges,policy,layered=True):
    events=[dict(source=i,pass_index=0,ink=f['ink'],id=f'{i}:pass0') for i,f in enumerate(fs)];extra={}
    if layered:
        for band,key in [('middle','mid_light_repeat_fraction'),('far','far_light_repeat_fraction')]:
            eligible=[i for i,f in enumerate(fs) if f['depth_band']==band and f['ink']=='LIGHT_INK' and f['family'] in ('A','B') and f['length_mm']<=policy['max_repeated_source_length_mm']]
            take=round(len(eligible)*policy[key]);chosen=sorted(eligible,key=lambda i:(-fs[i]['allocation_score'],i))[:take]
            for i in chosen:extra[i]=len(events);events.append(dict(source=i,pass_index=1,ink='LIGHT_INK',id=f'{i}:pass1'))
    graph=set(edges)
    for i,j in edges:
        if i in extra:graph.add((extra[i],j))
    for i,k in extra.items():graph.add((i,k))
    adj=defaultdict(list);degree=[0]*len(events)
    for i,j in graph:adj[i].append(j);degree[j]+=1
    ready=set(i for i,d in enumerate(degree) if not d);order=[];current='LIGHT_INK'
    while ready:
        # Retain terrain-first barrier while allowing source-safe odd/even.
        terrain=[i for i in ready if fs[events[i]['source']]['family']=='A']
        pool=terrain or list(ready);same=[i for i in pool if events[i]['ink']==current];pool=same or pool
        def key(k):
            e=events[k];f=fs[e['source']];return (e['pass_index'],f['A_light_parity'] or 0,f['depth_m'],e['source'])
        pick=min(pool,key=key);ready.remove(pick);order.append(pick);current=events[pick]['ink']
        for j in adj[pick]:
            degree[j]-=1
            if degree[j]==0:ready.add(j)
    require(len(order)==len(events),'cyclic/incomplete execution proposal')
    result=[events[i] for i in order];rank={e['id']:i for i,e in enumerate(result)}
    require(all(rank[f'{a}:pass0']<rank[f'{b}:pass0'] for a,b in edges),'source dependency changed')
    return result,dict(protected_source_edges=len(edges),protected_edges_violated=0,extra_light_passes=len(extra),dark_extra_passes=0,
        near_extra_passes=0,all_extra_passes_before_dependent_later_originals=all(rank[f'{a}:pass1']<rank[f'{b}:pass0'] for a,b in edges if a in extra),
        layering_does_not_guarantee_drying=True,original_canonical_sources_unchanged=True)


def join_reason(a,b,rows,fs,policy,shapes):
    i,j=a['source'],b['source'];r,s=rows[i],rows[j]
    if a['ink']!=b['ink'] or a['pass_index']!=0 or b['pass_index']!=0:return None
    role=lambda k: 'D' if fs[k]['family']=='D' else fs[k]['grammar']
    if role(i) not in STRUCTURAL or role(j) not in STRUCTURAL or fs[i]['owner']!=fs[j]['owner']:return None
    p=np.asarray(r['xy_mm']);q=np.asarray(s['xy_mm']);gap=float(np.linalg.norm(p[-1]-q[0]))
    v=p[-1]-p[-2];w=q[1]-q[0];turn=degrees(acos(float(np.clip(v@w/max(np.linalg.norm(v)*np.linalg.norm(w),1e-12),-1,1))))
    if turn>policy['max_join_turn_degrees']:return None
    if gap==0:return dict(reason='exact canonical shared endpoint; no added XY',gap_mm=0.,turn_degrees=turn)
    # Positive-gap joining is limited to explicit shared junction provenance and
    # existing authored stroke footprints. No foliage/dots/mist/clipping repair.
    junction=r.get('junction_source_id')
    if not junction or junction!=s.get('junction_source_id') or gap>policy['max_positive_connector_mm']:return None
    if r.get('omission_reasons') or s.get('omission_reasons'):return None
    if not shapes[i].union(shapes[j]).buffer(1e-9).covers(LineString([p[-1],q[0]])):return None
    return dict(reason='shared authored junction; connector contained in existing display support',gap_mm=gap,turn_degrees=turn,
                connector_depth_origin='execution-only linear connection of mapped endpoint Z; no new canonical pressure record')


def gesture_groups(events,rows,fs,policy,shapes):
    groups=[];joins=[]
    for e in events:
        candidate=join_reason(groups[-1][-1],e,rows,fs,policy,shapes) if groups and len(groups[-1])<policy['max_join_sources'] else None
        if candidate:
            joins.append(dict(from_event=groups[-1][-1]['id'],to_event=e['id'],**candidate));groups[-1].append(e)
        else:groups.append([e])
    return groups,joins


def profile(policy):
    require((policy['paper_first_touch_z'],policy['paper_hover_z'],policy['paper_approach_z'],policy['backing_offset_added_mm'])==(10,20,15,0),'confirmed mounting must not silently change')
    d=read(ROOT/'benchmarks/integrated_330_v01/review_spring_reload_1100_700/profile.spring.large_baegunmo.json')
    d['profile_id']='SPRING-SMALL-BAEGUNMO-INK-HYBRID800-12-REVIEW';d['notes']='Operator-confirmed small brush touch10/hover20/approach15 on3mm backing. No extra substrate offset. PR32 compression unchanged, safe compression and new vessel swept clearance unresolved. Calibration-gated numerical review only.'
    d['machine'].update(mounted_brush_id='small-baegunmo-operator-mounted',substrate_assembly='operator-confirmed paper on3mm wooden backing; touch10 already includes mounting',substrate_id='spring-3mm-wood-backed',paper_surface_above_bed_mm=None)
    for b in d['brush_profiles'].values():
        b.update(brush_type='small_baegunmo',paper_first_touch_z_mm=10,status='unverified',observations=[],notes='Confirmed mounting reference, NOT a measured small-brush compression/width calibration. Preserve PR32 knot response.')
    d['material'].update(ink_reload_mm=800,color_reload_mm=600,end_cleanup=False)
    d['stations']['light_ink']=deepcopy(d['stations']['water']);d['stations']['light_ink']['hardware_id']='WELL_1'
    d['stations']['dark_ink']=deepcopy(d['stations']['ink']);d['stations']['dark_ink']['hardware_id']='WELL_2'
    d['stations']['water']=deepcopy(policy['new_water']);d['stations']['water']['hardware_id']='NEW_WATER_CONTAINER'
    d['motion']['air_station_roles']=['light_ink','dark_ink','water','sponge']
    # The new container is not passed to the inherited sloped-station primitive.
    p=Profile.from_dict(d)
    require(p.data['brush_profiles']['ink']['knots']==[list(k) for k in RELATIVE_KNOTS],'pressure mapping changed')
    return p


class HybridBudget:
    def __init__(self,distance=800,contacts=12):
        require(distance>0 and type(contacts) is int and contacts>0,'positive independent reload limits')
        self.limit=distance;self.contact_limit=contacts;self.slots={s:dict(distance=0.,contacts=0) for s in ['LIGHT_INK','DARK_INK']}
    def reasons(self,slot):
        b=self.slots[slot];return (['distance_limit'] if b['distance']>=self.limit else [])+(['contact_limit'] if b['contacts']>=self.contact_limit else [])
    def reset(self,slot):self.slots[slot]=dict(distance=0.,contacts=0)
    def after(self,slot,distance):self.slots[slot]['distance']+=distance;self.slots[slot]['contacts']+=1


def container_operation(b,water,action,cycles=1,dwell=None):
    """Independent container geometry: no slope withdrawal/shallow stone wipe."""
    require(water['kind']=='container' and water['contact_z']==20,'selected container/depth changed')
    x,y=water['center_xy'];z=water['contact_z'];state='partially_depleted';b.time_context='station_transfer'
    b.xy((x,y),35,state);b.time_context='station_handling'
    b.move((x,y,water['approach_z']),7000,'station_container_approach',state)
    b.move((x,y,z),1000,'station_container_immersion',state)
    b.dwell(water['dwell_seconds'] if dwell is None else dwell,'container_'+action+'_dwell')
    for _ in range(cycles):
        b.move((x,y,z+water['vertical_agitation_release_mm']),1000,'station_container_vertical_release',state)
        b.move((x,y,z),1000,'station_container_vertical_reentry',state)
    b.move((x,y,water['approach_z']),1000,'station_container_withdraw',state)
    b.lift(35)
    # Approach lip from ABOVE at global35; descend vertically only at its start.
    lip=water['lip_start_xyz'];b.xy(lip[:2],35,state);b.time_context='station_handling'
    b.move(lip,1000,'station_container_lip_contact',state)
    end=(lip[0]+water['lip_relative_x_mm'],lip[1],lip[2])
    b.move(end,water['lip_feed_mm_min'],'station_container_lip_strip',state)
    b.lift(35);b.marker(action,'NEW_WATER_CONTAINER');b.in_paper=False;b.at_station=True;b.last_panel=None;b.time_context=None


class InkMaterials:
    def __init__(self,b,policy):
        self.b=b;self.policy=policy;self.budget=HybridBudget(policy['distance_limit_mm'],policy['contact_limit']);self.loaded=None;self.loads=[];self.operations=[]
    @property
    def state(self):return 'partially_depleted' if self.loaded and self.budget.reasons(self.loaded) else 'wet_loaded' if self.loaded else 'ordinary_travel'
    def station(self,role,action):
        st=self.b.profile.data['stations'][role]
        emit_station_operation(self.b,st,action,'partially_depleted',lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        self.b.marker(action,st['hardware_id']);self.operations.append(dict(action=action,station=role,after_command=len(self.b.commands)-1))
    def water(self,action,cycles=1,dwell=None):
        container_operation(self.b,self.policy['new_water'],action,cycles,dwell)
        self.operations.append(dict(action=action,station='NEW_WATER_CONTAINER',after_command=len(self.b.commands)-1))
    def before(self,group):
        slot=group[0]['ink'];reasons=self.budget.reasons(slot) if self.loaded==slot else ['initial_load' if self.loaded is None else 'concentration_change']
        if reasons:
            previous=deepcopy(self.budget.slots)
            if self.loaded is not None and self.loaded!=slot:
                self.water('wash');self.station('sponge','absorbent_contact');self.water('controlled_rewet',0,1)
            role='light_ink' if slot=='LIGHT_INK' else 'dark_ink';self.station(role,'pigment_load')
            self.loads.append(dict(before_event=group[0]['id'],ink=slot,reasons=reasons,previous_slot=self.loaded,
                previous_budgets=previous,distance_limit_mm=self.budget.limit,contact_limit=self.budget.contact_limit,
                distance_overrun_before_reload_mm=max(0,previous[slot]['distance']-self.budget.limit) if self.loaded==slot else 0,
                contact_overrun_before_reload=max(0,previous[slot]['contacts']-self.budget.contact_limit) if self.loaded==slot else 0,
                both_counters_reset=True))
            self.loaded=slot;self.budget.reset(slot)
    def after(self,group,distance):self.budget.after(group[0]['ink'],distance)
    def terminal(self):
        self.b.marker('terminal_cleanup_begin')
        for _ in range(self.policy['terminal_cleaning']['water_visits']):self.water('terminal_wash',self.policy['terminal_cleaning']['vertical_cycles'],self.policy['terminal_cleaning']['dwell_seconds'])
        st=deepcopy(self.b.profile.data['stations']['sponge']);st['repetitions']=2
        emit_station_operation(self.b,st,'absorbent_contact','partially_depleted',lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        self.operations.append(dict(action='terminal_absorbent_contact_twice',station='PURGE',after_command=len(self.b.commands)-1));self.b.park('partially_depleted');self.b.marker('terminal_cleanup_complete')


def draw_gesture(b,group,fragments,material):
    first=fragments[group[0]['source']];xy=first.work_xy[0];v=b.v
    b.time_context='station_transfer' if b.at_station else None
    b.xy(xy,35 if b.at_station else 20,material.state);b.time_context=None;b.at_station=False
    for z,feed,action in [(20,7000,'paper_hover'),(15,7000,'approach'),(10,2000,'initial_contact')]:b.move((*xy,z),feed,action,material.state)
    for e in group:
        f=fragments[e['source']];ident=f.stroke.origin_id;occurrence=e['id'];b.marker('source_begin',occurrence,source_id=ident);b.marker('execution_pass_'+str(e['pass_index']),occurrence)
        # Every original vertex and pressure is emitted in its original order.
        # A positive connector, if admitted, is a separately labeled execution
        # move; it never replaces either endpoint or a canonical pressure sample.
        if b.position[:2]!=f.work_xy[0]:
            b.move((*f.work_xy[0],b.profile.brush_for('ink','INK').work_z_for(f.stroke.points[0].pressure)),min(1500,v['draw_mm_min']),'execution_connector',material.state)
        for k,(point,p) in enumerate(zip(f.work_xy,f.stroke.points)):
            z=b.profile.brush_for('ink','INK').work_z_for(p.pressure)
            b.move((*point,z),2000 if k==0 else v['draw_mm_min'],'pressure_variation' if k==0 else 'draw',material.state,
                source_id=ident,fragment_id=occurrence,source_vertex=k,artistic_pressure=p.pressure)
        b.marker('source_complete',occurrence,source_id=ident)
    xy=b.position[:2]
    for z,feed,action in [(10,2000,'release'),(15,2000,'paper_release_clearance'),(20,7000,'retract')]:b.move((*xy,z),feed,action,material.state)
    b.in_paper=True;b.last_panel='FULL'


def build(groups,fragments,p,policy,contact_limit=None):
    cfg=deepcopy(policy)
    if contact_limit is not None:cfg['contact_limit']=contact_limit
    b=RuntimeBuilder(p);m=InkMaterials(b,cfg);audit=[]
    # Intentional machine stop distinguishes this candidate from a cleared job.
    # It is NOT a safety interlock; the user must not bypass unresolved gates.
    b.commands.append(Command('pause','calibration_gate',message='REVIEW ONLY: verify small-brush compression, registration and new-container swept clearance before any contact. AIR first.'))
    for rank,group in enumerate(groups):
        m.before(group);before=deepcopy(m.budget.slots[group[0]['ink']]);start=len(b.commands)
        draw_gesture(b,group,fragments,m)
        drawn=sum(length(fragments[e['source']].work_xy) for e in group)
        bridge=sum(dist(fragments[a['source']].work_xy[-1],fragments[c['source']].work_xy[0]) for a,c in zip(group,group[1:]));drawn+=bridge
        m.after(group,drawn);after=deepcopy(m.budget.slots[group[0]['ink']])
        audit.append(dict(gesture_rank=rank,events=[e['id'] for e in group],source_ids=[fragments[e['source']].stroke.origin_id for e in group],
            ink=group[0]['ink'],source_count=len(group),actual_paper_engagements=1,drawn_mm=drawn,connector_mm=bridge,
            before=before,after=after,distance_overrun_mm=max(0,after['distance']-cfg['distance_limit_mm']),
            contacts_overrun=max(0,after['contacts']-cfg['contact_limit']),first_command=start,last_command=len(b.commands)-1))
    m.terminal()
    return b.commands,dict(loads=m.loads,station_operations=m.operations,gestures=audit,terminal_budgets=m.budget.slots,
        contact_limit=cfg['contact_limit'],total_loads=len(m.loads),same_concentration_reloads=sum('concentration_change' not in x['reasons'] and 'initial_load' not in x['reasons'] for x in m.loads),
        concentration_changes=sum('concentration_change' in x['reasons'] for x in m.loads),
        maximum_contacts_before_reload=max((a['after']['contacts'] for a in audit),default=0),
        maximum_distance_before_reload_mm=max((a['after']['distance'] for a in audit),default=0),
        maximum_atomic_distance_overrun_mm=max((a['distance_overrun_mm'] for a in audit),default=0),
        actual_paper_engagements=len(groups),no_service_inside_original_or_joined_gesture=True)


def air_projection(commands,p):
    # Full-air is above paper AND every station at the inherited global35 plane.
    # Re-cap feeds after flattening Z so a synchronized diagonal's feed cannot
    # produce an excessive XY speed on the flattened path.
    out=[];previous=tuple(p.data['machine']['start_work_xyz'])
    for c in commands:
        if c.kind=='pause':continue
        if c.kind=='move':
            xyz=(*c.xyz[:2],35.)
            feed=serialized_feed_cap(previous,xyz,c.feed_mm_min,p.data['machine'],p.data['motion'],'travel')
            c=replace(c,xyz=xyz,feed_mm_min=feed);previous=xyz
        out.append(c)
    return out


def verify_numeric(text,commands,p,groups,fragments,air=False):
    rows=[s for s in text.splitlines() if s and not s.startswith(';')];expected=[c for c in commands if c.kind!='marker']
    require(rows[0]=='G21 G90 G94 G54' and rows[-1]=='M2' and len(rows)==len(expected)+2,'numeric dialect/coverage')
    pos=tuple(p.data['machine']['start_work_xyz']);bounds=[list(pos),list(pos)];rates=[0.,0.,0.];active=None;seen=[];values=defaultdict(list);station_inside=0
    rowiter=iter(rows[1:-1]);first_physical=False
    for c in commands:
        if c.action=='source_begin':
            require(active is None,'nested source');active=c.message;seen.append(c.message)
        if c.action=='source_complete':require(active==c.message,'source closure');active=None
        if c.time_category in ('station_handling','station_transfer') and active:station_inside+=1
        if c.kind=='marker':continue
        row=next(rowiter)
        if c.kind=='move':
            match=_MOVE.fullmatch(row);require(match is not None,'unapproved motion');x,y,z,feed=map(float,match.groups());q=(x,y,z)
            require(all(abs(a-b)<=5.1e-10 for a,b in zip((x,y,z,feed),(*c.xyz,c.feed_mm_min))),'serialized motion differs')
            check_move(pos,q,feed,c.action,p,'air' if air else 'paint',exact_benchmark_draw=False)
            if air:require(z==35,'AIR contact/descend')
            if c.time_category=='station_transfer' and pos[:2]!=q[:2]:require(pos[2]==z==35,'station transfer below35')
            if c.action=='travel' and pos[:2]!=q[:2]:require(pos[2]==z and z in (20,35),'paper traverse below hover')
            if c.artistic_pressure is not None:
                require(active is not None,'pressure outside source');values[active].append((c.source_vertex,c.artistic_pressure,(x,y),z))
                if not air:require(abs(z-(10+reference_z(c.artistic_pressure,RELATIVE_KNOTS)))<5.1e-10,'pressure clamped/changed')
            if c.action in ('initial_contact','release','paper_release_clearance') and not air:
                require(z=={'initial_contact':10,'release':10,'paper_release_clearance':15}[c.action],'touch/approach changed')
            d=dist(pos,q)
            for k in range(3):
                bounds[0][k]=min(bounds[0][k],q[k]);bounds[1][k]=max(bounds[1][k],q[k]);rates[k]=max(rates[k],abs(q[k]-pos[k])/d*feed if d else 0)
            pos=q
        elif c.kind=='dwell':
            m=_DWELL.fullmatch(row);require(m and abs(float(m.group(1))-c.seconds)<5.1e-10,'dwell mismatch')
        elif c.kind=='pause':require(row=='M0','missing calibration gate')
        else:raise ValueError('unapproved command')
    events=[e for g in groups for e in g];require(seen==[e['id'] for e in events],'occurrence/source order lost')
    for e in events:
        f=fragments[e['source']];v=values[e['id']]
        require(len(v)==len(f.stroke.points),'missing/duplicated pressure vertices')
        for i,(vertex,pressure,xy,z) in enumerate(v):
            require(vertex==i and pressure==f.stroke.points[i].pressure and all(abs(a-b)<5.1e-10 for a,b in zip(xy,f.work_xy[i])),'source XY/pressure/direction changed')
    require(station_inside==0 and pos==(800,800,35),'atomic source/park mismatch')
    require(sum(c.kind=='pause' for c in commands)==(0 if air else 1),'calibration gate count')
    return dict(all_numeric_IR_moves_and_dwell_values_verified=True,all_original_and_repeat_XY_pressure_vertices_verified=True,
        pressure_samples=sum(len(v) for v in values.values()),source_occurrences=len(events),unique_original_sources=len({e['source'] for e in events}),
        axis_reference_bounds=bounds,maximum_projected_axis_feeds_mm_min=rates,station_inside_source_count=0,
        final_work_xyz=list(pos),M0_count=0 if air else 1,AIR_all_move_Z35=air,physical_swept_clearance_certified=False,machine_authorized=False)


def compression_audit(fragments,policy):
    result=[];limit=policy['measured_max_compression_mm']
    for i,f in enumerate(fragments):
        c=[-reference_z(p.pressure,RELATIVE_KNOTS) for p in f.stroke.points]
        result.append(dict(source_index=i,source_id=f.stroke.origin_id,min_compression_mm=min(c),max_compression_mm=max(c),
            min_paper_Z=10-max(c),status='small_brush_measured_range_missing' if limit is None else 'exceeds_measured_range' if max(c)>limit else 'inside_operator_supplied_range',
            pressure_clamped=False,measured_limit_mm=limit))
    return result


def write_job(out,name,commands,p,groups,fragments,air=False):
    text=BANNER+'; SPRING SMALL BAEGUNMO / NUMERICAL REVIEW / NOT MACHINE AUTHORIZED\n'+_serialize(commands,p,PLAN_SHA,name,'offline_review')
    checked=verify_numeric(text,commands,p,groups,fragments,air)
    (out/(name+'.gcode')).write_text(text)
    (out/(name+'.gcode.gz')).write_bytes(gzip.compress(text.encode(),mtime=0))
    save(out/(name+'.readback.json'),checked)
    return dict(**checked,filename=name+'.gcode',gcode_sha256=hashlib.sha256(text.encode()).hexdigest(),runtime=runtime(commands,p))


def generate(args):
    out=Path(args.output);require(not out.exists(),'new output directory required');out.mkdir(parents=True)
    policy=read(POLICY)
    if args.measured_max_compression_mm is not None:
        require(np.isfinite(args.measured_max_compression_mm) and args.measured_max_compression_mm>0,'positive finite measured compression limit required')
        policy['measured_max_compression_mm']=args.measured_max_compression_mm
    context=recover_context(Path(args.context));plan,rows,fragments=load_inputs(context);before=digest(plan)
    fs,context_report=features(context,rows);allocation=allocate(fs,policy);edges,shapes,adjacency=constraints(rows,fs,policy)
    print('Allocation',allocation,flush=True)
    p=profile(policy);save(out/'profile.small_baegunmo.json',p.data);save(out/'policy.json',policy);save(out/'source_features.json.gz',fs)
    save(out/'source_context_provenance.json',context_report);save(out/'allocation.json',allocation);save(out/'compression_calibration_audit.json.gz',compression_audit(fragments,policy))
    plans={};report=dict(baseline_commit=policy['baseline_commit'],canonical_plan_sha256=PLAN_SHA,pressure_sidecar_sha256=SIDECAR_SHA,
        original_ink_sources=3345,original_ink_pressure_values=69101,original_all_medium_sources_in_frozen_plan=14951,
        mounting_reference_operator_confirmed=True,backing_offset_added_mm=0,machine_authorized=False,jobs={})
    for label,layered in [('SINGLE_PASS',False),('SELECTIVE_LAYERED',True)]:
        events,order_report=events_schedule(fs,edges,policy,layered);groups,joins=gesture_groups(events,rows,fs,policy,shapes)
        plans[label]=dict(events=events,groups=groups,joins=joins,diagnostics=order_report)
        name='SPRING_INK_'+label+'_REVIEW';commands,material=build(groups,fragments,p,policy)
        report['jobs'][name]=write_job(out,name,commands,p,groups,fragments)
        save(out/(label+'.reload_manifest.json.gz'),material);save(out/(label+'.execution_manifest.json.gz'),plans[label])
        if layered:
            air=air_projection(commands,p);report['jobs']['SPRING_INK_FULL_AIR_REVIEW']=write_job(out,'SPRING_INK_FULL_AIR_REVIEW',air,p,groups,fragments,True)
            save(out/'full_numeric_IR.json.gz',[asdict(c) for c in commands])
            # Counter15 is a separate material comparison, not another scene.
            c15,m15=build(groups,fragments,p,policy,15);save(out/'contact15_reload_comparison.json.gz',m15);del c15
        del commands
        print(label,'events',len(events),'joins',len(joins),'loads',material['total_loads'],'contacts',material['maximum_contacts_before_reload'],flush=True)
    # Representative intact canonical sources; original G54 registration retained.
    for kind,families,bounds in [('TERRAIN',{'A','D'},(150,240,400,430)),('TREES',{'tree','RSU'},(360,610,570,845)),('ROCKS',{'rock','Soil'},(350,650,590,875))]:
        selected=[]
        for e in plans['SINGLE_PASS']['events']:
            i=e['source'];xy=np.array(rows[i]['xy_mm']);x0,y0,x1,y1=bounds
            if fs[i]['family'] in families and np.all((xy[:,0]>=x0)&(xy[:,0]<=x1)&(xy[:,1]>=y0)&(xy[:,1]<=y1)):selected.append(e)
        selected=selected[:30];require(selected,'empty representative crop '+kind)
        groups,joins=gesture_groups(selected,rows,fs,policy,shapes);cmd,mat=build(groups,fragments,p,policy)
        name=kind+'_INK_CROP_REVIEW';report['jobs'][name]=write_job(out,name,cmd,p,groups,fragments)
        report['jobs'][kind+'_AIR_CROP_REVIEW']=write_job(out,kind+'_AIR_CROP_REVIEW',air_projection(cmd,p),p,groups,fragments,True)
        save(out/(kind+'.test_manifest.json'),dict(original_artwork_bounds=bounds,not_relocated_or_scaled=True,source_ids=[rows[e['source']]['id'] for e in selected],reloads=mat['loads']))
    # Standalone elevated station route BEFORE considering any contact-capable job.
    b=RuntimeBuilder(p);m=InkMaterials(b,policy)
    m.water('wash');m.station('sponge','absorbent_contact');m.water('controlled_rewet',0,1)
    m.station('light_ink','pigment_load');m.station('dark_ink','pigment_load');b.park()
    air=air_projection(b.commands,p);report['jobs']['STATIONS_AIR_FIRST_REVIEW']=write_job(out,'STATIONS_AIR_FIRST_REVIEW',air,p,[],fragments,True)
    save(out/'station_operations.validation_air.json',m.operations)
    require(digest(plan)==before,'canonical plan mutated')
    report['allocation']=allocation;report['source_geometry_and_pressure_unchanged']=True;report['protected_order_edges']=len(edges)
    ca=compression_audit(fragments,policy);report['compression_calibration']=dict(operator_confirmed_paper_touch=10,measured_small_brush_max_mm=policy['measured_max_compression_mm'],maximum_mapped_compression_mm=max(r['max_compression_mm'] for r in ca),source_status_counts=dict(Counter(r['status'] for r in ca)),clamped_samples=0)
    report['connections']=dict(joins=len(plans['SELECTIVE_LAYERED']['joins']),positive_gap_connectors=sum(j['gap_mm']>0 for j in plans['SELECTIVE_LAYERED']['joins']),added_connector_XY_mm=sum(j['gap_mm'] for j in plans['SELECTIVE_LAYERED']['joins']),tree_or_rock_catalog_redesign=False)
    report['original_X300_crossing_ink_sources']=sum(min(p.x for p in f.stroke.points)<300<max(p.x for p in f.stroke.points) for f in fragments)
    report['original_sharp_turns_preserved']=sum(f['sharp_turns_over_90'] for f in fs)
    ranks={e['source']:k for k,e in enumerate(plans['SINGLE_PASS']['events'])};report['A_adjacency']=dict(pairs=len(adjacency),before_median_rank_gap=float(np.median([b-a for a,b in adjacency])),after_median_rank_gap=float(np.median([abs(ranks[b]-ranks[a]) for a,b in adjacency])),frustrated_nearest_parity_pairs=sum(fs[a]['A_light_parity']==fs[b]['A_light_parity'] for a,b in adjacency),both_parities_use_light_ink=True,drying_guaranteed=False)
    save(out/'protected_source_dependencies.json.gz',dict(edges=edges,contour_adjacency=adjacency))
    save(out/'verification.json',report)
    from .spring_physical_ink_review import render_review
    render_review(out,rows,fs,plans,report)
    future=dict(policy['future_color_lips_record_only'],color_jobs_generated=False,slots={})
    for slot,station in p.data['stations'].items():
        if len(slot)==2 and slot[0] in 'ABCD' and slot[1] in '12345':
            x=811 if slot[0] in 'AC' else 850;y=station['center_xy'][1]
            future['slots'][slot]=dict(start_xyz=[x,y,28],end_xyz=[x-15,y,28],verified=False,generated_motion=False)
    save(out/'future_color_lips.RECORD_ONLY.json',future)
    save(out/'MANIFEST_SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='MANIFEST_SHA256.json'})
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--context',type=Path,required=True);ap.add_argument('--measured-max-compression-mm',type=float)
    a=ap.parse_args();r=generate(a);print(json.dumps({name:dict(sources=v['source_occurrences'],runtime_minutes=v['runtime']['models']['configuration_reference']['acceleration_sensitive_seconds']/60) for name,v in r['jobs'].items()},indent=2))
