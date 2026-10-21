"""Comment-only review layer. No machine offset, collision volume or station surface is synthesized.

All station XY transport is a nominal-center proxy. Unknown contact operations
remain symbolic; this layer cannot emit executable machine programs.
"""
from copy import deepcopy
from dataclasses import replace,asdict
from math import dist,hypot,sqrt
from types import SimpleNamespace
import gzip,json
from datascape.gcode.production.trajectory import Command,local_transition_geometry
from datascape.gcode.production.timing import estimate_prepared
from datascape.gcode.motion import MotionSettings,stroke_events,Action


class Review:
    def __init__(self,profile,axes):
        self.profile=profile
        # Retained timing-only wet edge lengths from the pinned synthetic scenario.
        # Physical candidate profile keeps both lengths null until measured.
        self.motion=dict(profile.data['motion'],wet_departure_mm=10,wet_arrival_mm=10);self.axes=axes
        self.position=tuple(self.motion['park_xyz']);self.commands=[];self.loaded=None;self.distance=0.
        self.loads=0;self.reloads=0;self.washes=0;self.purges=0;self.links=[]
        self.total_z=0.;self.last_retract=None;self.paper_end=None
    def marker(self,action,message='',**lineage):self.commands.append(Command('marker',action,message=message,**lineage))
    def unknown(self,action,details):self.commands.append(Command('unresolved',action,message=json.dumps(details,sort_keys=True)))
    def move(self,xyz,feed,action,category='non_drawing_travel',state='ordinary_travel',**lineage):
        xyz=tuple(xyz);delta=tuple(q-p for p,q in zip(self.position,xyz));length=sqrt(sum(d*d for d in delta));speed=feed
        if length:
            unit=tuple(abs(d)/length for d in delta)
            speed=min(feed,*(v/u for v,u in zip(self.axes['axis_max_rate_mm_min'],unit) if u))
            cap=self.motion['pressure_z_mm_min'] if action in ('draw','pressure_variation') else self.motion['z_travel_mm_min']
            if unit[2]:speed=min(speed,cap/unit[2])
        self.total_z+=abs(delta[2]);self.commands.append(Command('move',action,xyz,speed,state,time_category=category,**lineage));self.position=xyz
    def xy(self,xy,z,category,state):
        self.move((*self.position[:2],z),self.motion['z_travel_mm_min'],'lift',category,state)
        start=self.position;end=(*xy,z);length=dist(start,end);feed=self.motion[state+'_mm_min']
        if state=='wet_loaded' and length:
            d,a=self.motion['wet_departure_mm'],self.motion['wet_arrival_mm'];scale=min(1,length/(d+a))
            for phase,f,cap in [('departure',d*scale/length,self.motion['wet_departure_mm_min']),('main',1-a*scale/length,feed),('arrival',1.,self.motion['wet_arrival_mm_min'])]:
                p=tuple(v+f*(w-v) for v,w in zip(start,end));self.move(p,min(feed,cap),'travel',category,state,travel_phase=phase)
        else:self.move(end,feed,'travel',category,state)
    @property
    def state(self):
        if self.loaded is None:return 'ordinary_travel'
        m=self.profile.data['material'];limit=m['ink_reload_mm' if self.loaded=='ink' else 'color_reload_mm']
        return 'partially_depleted' if self.distance>=limit else 'wet_loaded'
    def station(self,role,action,material=None):
        s=self.profile.data['stations'][role];center=s['center_xy']
        self.xy(center,self.motion['station_clearance_mm'],'station_transfer',self.state)
        self.marker('nominal_station_center',role+'; historical frame unverified; not a measured deep/shallow point')
        target=None if role=='sponge' else s['liquid_reference_z']-s['rewet_immersion_mm' if action=='controlled_rewet' else 'immersion_mm']
        self.unknown(action,{'role':role,'nominal_center_xy':center,'provisional_target_z':target,
            'grammar':s['kind'],'deep_surface_xyz':s.get('deep_surface_xyz'),'shallow_surface_xyz':s.get('shallow_surface_xyz'),
            'sponge_surface_z':s.get('surface_z'),'sponge_compression_mm':s.get('compression_mm'),
            'contact_box_xyz':s['contact_box_xyz'],'feed_mm_min':s['feed_mm_min'],'dwell_seconds':s['dwell_seconds'],
            'wash_cycles':s.get('wash_cycles') if action=='wash' else None,
            'pattern':s.get('pattern'),'radius_mm':s.get('radius_mm'),'revolutions':s.get('revolutions'),
            'retract':'measured station exit -> global clearance 32; actual exit XY unresolved for stones',
            'transport_proxy_only':'timing resumes at nominal center Z32; unknown station handling excluded'})
    def service_before(self,unit):
        s=unit[0].stroke;target='ink' if s.medium=='ink' else s.color_slot;service=False
        if target!=self.loaded:
            if self.loaded is not None:
                old=self.loaded;self.loaded=None;self.distance=0.
                self.station('water','wash');self.station('sponge','absorbent_contact',old);self.purges+=1
                self.station('water','controlled_rewet');self.washes+=1
            self.marker('material_change',target);self.station('ink' if target=='ink' else target,'pigment_load');self.loads+=1;service=True
        elif self.distance>=self.profile.data['material']['ink_reload_mm' if target=='ink' else 'color_reload_mm']:
            self.station('ink' if target=='ink' else target,'same_material_reload');self.reloads+=1;self.loads+=1;service=True
        if service:self.distance=0.;self.loaded=target
        return service
    def build(self,units):
        self.marker('review_only','No physical readiness/authorization; all station contacts symbolic')
        previous=None
        for rank,unit in enumerate(units):
            service=self.service_before(unit)
            if previous is not None:
                a,z=previous[-1],unit[0];gap=dist(a.work_xy[-1],z.work_xy[0])
                eligible=local_transition_geometry(previous,unit,self.distance if not service else float('inf'),self.profile.data['material'],{'enabled':True,'max_distance_mm':float('inf')})
                self.links.append({'previous_source':a.stroke.origin_id,'next_source':z.stroke.origin_id,'distance_mm':gap,
                                   'eligible_without_clearance':eligible,'previous_retract_index':self.last_retract,'entry_indices':[]})
            self.marker('source_begin',str(rank),source_id=unit[0].stroke.origin_id)
            for f in unit:
                entry_indices=[];before=len(self.commands)
                height=self.motion['station_clearance_mm'] if service else self.motion['paper_hover_mm']
                self.xy(f.work_xy[0],height,'station_transfer' if service else 'non_drawing_travel',self.state)
                self.move((*f.work_xy[0],self.motion['paper_hover_mm']),self.motion['z_travel_mm_min'],'paper_hover','station_transfer' if service else 'non_drawing_travel',self.state)
                entry_indices=list(range(before,len(self.commands)))
                if previous is not None and f is unit[0]:self.links[-1]['entry_indices']=entry_indices
                brush=self.profile.brush_for(f.stroke.medium,f.stroke.color_slot)
                settings=MotionSettings(brush,hover_z_mm=10,approach_z_mm=1) # explicit timing-only boundary, physical profile keeps null
                for e in stroke_events(f,settings):
                    if e.action in (Action.LIFT,Action.TRAVEL):continue
                    feed={Action.DRAW:self.motion['draw_mm_min'],Action.APPROACH:self.motion['paper_approach_mm_min'],
                          Action.CONTACT:self.motion['paper_contact_mm_min'],Action.PRESSURE:self.motion['paper_contact_mm_min'],Action.RELEASE:self.motion['paper_release_mm_min']}[e.action]
                    self.move((*e.work_xy,e.preview_z_mm),feed,e.action.value,'drawing' if e.action==Action.DRAW else 'paper_engagement',self.state,
                              source_id=f.stroke.origin_id,fragment_id=f.stroke.stroke_id,source_vertex=e.source_vertex,artistic_pressure=e.artistic_pressure)
                self.move((*f.work_xy[-1],1),self.motion['paper_release_mm_min'],'paper_release_clearance','paper_engagement',self.state)
                self.move((*f.work_xy[-1],10),self.motion['z_travel_mm_min'],'retract','paper_engagement',self.state)
                self.last_retract=len(self.commands)-1;service=False
            self.distance+=sum(hypot(b.x-a.x,b.y-a.y) for f in unit for a,b in zip(f.stroke.points,f.stroke.points[1:]))
            self.marker('source_complete',str(rank),source_id=unit[0].stroke.origin_id);previous=unit
        self.xy(self.motion['park_xyz'][:2],32,'non_drawing_travel',self.state)
        self.move(self.motion['park_xyz'],self.motion['z_travel_mm_min'],'park');self.marker('program_end','M2')
        return self.commands,self.links


def with_local(commands,links,height,threshold):
    out=list(commands);selected=[]
    for link in links:
        if not link['eligible_without_clearance'] or link['distance_mm']>threshold+1e-12:continue
        indices=[link['previous_retract_index'],*link['entry_indices']]
        for i in indices:
            c=out[i]
            if c.kind=='move':out[i]=replace(c,xyz=(*c.xyz[:2],height))
        selected.append(link)
    return out,{'conditional_local_transitions':len(selected),'local_XY_mm':sum(v['distance_mm'] for v in selected),
                'reduced_Z_mm':2*(10-height)*len(selected),'clearance_verified':False,
                'physically_authorized_local_transitions':0}


def timing(commands,machine):
    position=tuple([800,900,32]);blocks=[]
    for c in commands:
        if c.kind=='move':
            length=dist(position,c.xyz)
            if length>1e-12:blocks.append((length,tuple((q-p)/length for p,q in zip(position,c.xyz)),c.feed_mm_min,c.time_category,c.action,c.travel_state,c.travel_phase))
            position=c.xyz
        elif c.kind=='unresolved':
            # A zero-time model boundary, never an emitted M0. Unknown station time is not assigned zero in the report.
            blocks.append((0.,(),0.,'station_handling','unresolved_boundary','',''))
    result=estimate_prepared(blocks,machine)
    for key in ('commanded_feed_seconds_by_category','acceleration_sensitive_seconds_by_category'):
        result[key]['station_handling']=None
    result['unresolved_station_handling_excluded']=True
    return result


def write_preview(path,commands,profile,plan_hash,job,review_policy=None):
    if not str(path).endswith('.preview.txt.gz'):raise ValueError('review output must be a compressed comment-only preview')
    lines=['; REVIEW ONLY; INCOMPLETE STATION GEOMETRY; NOT A MACHINE JOB',
           '; PROFILE '+profile.sha256,'; PLAN '+plan_hash,'; JOB '+job,
           '; HYPOTHETICAL_POLICY '+json.dumps(review_policy,sort_keys=True),
           '; All XY/station targets provisional; machine offsets, volumes and physical readiness unverified',
           '; G21 G90 G94 G54']
    for c in commands:
        if c.kind=='move':
            if c.artistic_pressure is not None:lines.append('; SAMPLE '+json.dumps({'source':c.source_id,'fragment':c.fragment_id,'vertex':c.source_vertex,'pressure':c.artistic_pressure},sort_keys=True))
            lines.append('; G1 '+' '.join(k+f'{v:.9f}' for k,v in zip('XYZ',c.xyz))+f' F{c.feed_mm_min:.9f}')
        elif c.kind=='unresolved':lines.append('; UNRESOLVED '+c.action+' '+c.message)
        else:lines.append('; '+c.action+' '+(c.source_id or '')+' '+c.message)
    lines.append('; M2');text='\n'.join(lines)+'\n';path.write_bytes(gzip.compress(text.encode(),mtime=0))
    # Independent delivered-file read-back of numbers, complete sample tags and placeholders.
    decoded=gzip.decompress(path.read_bytes()).decode().splitlines()
    if any(not s.startswith(';') for s in decoded):raise ValueError('executable preview line')
    samples=[json.loads(s[9:]) for s in decoded if s.startswith('; SAMPLE ')]
    expected=[{'source':c.source_id,'fragment':c.fragment_id,'vertex':c.source_vertex,'pressure':c.artistic_pressure} for c in commands if c.artistic_pressure is not None]
    if samples!=expected:raise ValueError('preview source/pressure read-back mismatch')
    moves=[s for s in decoded if s.startswith('; G1 ')]
    actual=[c for c in commands if c.kind=='move']
    if len(moves)!=len(actual):raise ValueError('preview motion coverage')
    for s,c in zip(moves,actual):
        values=[float(x[1:]) for x in s[5:].split()]
        if any(abs(a-b)>5.1e-10 for a,b in zip(values,[*c.xyz,c.feed_mm_min])):raise ValueError('preview coordinate/feed read-back')
    count=sum(s.startswith('; UNRESOLVED ') for s in decoded)
    if count!=sum(c.kind=='unresolved' for c in commands) or decoded[-1]!='; M2':raise ValueError('lost unresolved operations or termination')
    return {'all_lines_commented':True,'pressure_samples_read_back':len(samples),'numeric_moves_read_back':len(moves),
            'unresolved_station_operations':count,'M0_count':0,'final_M2_commented':True,'machine_reachability_verified':False}
