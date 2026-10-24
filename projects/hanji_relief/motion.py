"""Explicit point contact primitive over unchanged PR32 material/motion helpers.

Numeric review uses the backend's existing envelope-only sink. It does not
manufacture measured clearance volumes or bypass the official physical exporter.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict,replace
from math import dist
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile,authorize
from datascape.gcode.production.trajectory import Command,require_path,Builder
from datascape.gcode.production.exporter import _serialize,_MOVE,_DWELL
from datascape.gcode.production.timing import prepare_timing,estimate_prepared
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder,RuntimeMaterials
from benchmarks.integrated_330_v01.spring_end_cleanup import cleanup,PARK,POLICY
from benchmarks.integrated_330_v01.numeric_review import BANNER,check_move
from .data import ROOT,PROJECT,number,integer,mount_for,surface_delta,load_dots

PROFILE_PATH=ROOT/'benchmarks/integrated_330_v01/review_spring_reload_1100_700/profile.spring.large_baegunmo.json'


def review_profile(plan,scenario):
    p=Profile.load(PROFILE_PATH);d=deepcopy(p.data)
    if d['machine']['start_work_xyz']!=[0,900,35]: raise ValueError('unexpected backend independent start')
    if d['material']['end_cleanup'] is not False: raise ValueError('avoid duplicated legacy and appended terminal cleanup')
    cfg=plan['config'];mount=mount_for(scenario,plan['physical_panel_id'])
    hover=mount['fixed_hover_g54_z_mm']
    d.update(profile_id='HANJI-C-'+plan['job_id']+'-NUMERIC-REVIEW',status='nominal_review',evidence=[])
    d['motion'].update(paper_hover_mm=hover,local_hover={'enabled':False},paper_approach_mm_min=cfg['noncontact_z_feed_mm_min'],paper_contact_mm_min=cfg['contact_feed_mm_min'],paper_release_mm_min=cfg['release_feed_mm_min'],pressure_z_mm_min=cfg['contact_feed_mm_min'],z_travel_mm_min=cfg['noncontact_z_feed_mm_min'])
    # Planar relative heights/range are not authoritative for a variable relief.
    for key in ('paper_hover_clearance_mm','paper_approach_clearance_mm'):d['motion'].pop(key,None)
    for color in plan['used_color_order']:
        station=cfg['color_station_map'][color]
        if station not in d['stations']:raise ValueError('unknown backend station '+station)
    d['material']['color_order']=[cfg['color_station_map'][c] for c in plan['used_color_order']]
    d['material'].update(refill_policy='contact_count',refill_every_contacts=cfg['refill_every_contacts'])
    d['notes']='HANJI nominal numeric review, NOT authorized or measured. Shared station XYZ/feed and motion policies unchanged. Artwork uses explicit local first-touch minus constant compression, not Spring pressure curves. Clearance/registration needs physical review.'
    return Profile.from_dict(d),mount


class DotMaterials(RuntimeMaterials):
    """Count completed planned paper contacts; keep actual XY distance at zero."""
    def __init__(self,builder,limit):
        super().__init__(builder);self.limit=integer(limit,'refill limit',1);self.contacts=0
    @property
    def state(self):
        if self.loaded is None:return 'ordinary_travel'
        return 'partially_depleted' if self.contacts>=self.limit else 'wet_loaded'
    def station_travel_state(self):
        pending=getattr(self,'pending_station_return_state',None)
        if pending is not None:self.pending_station_return_state=None;return pending
        if self.loaded is not None and self.contacts>0:return 'partially_depleted'
        return self.state
    def wash(self):
        # The backend's distance>0 pending-return branch cannot see zero-length dots.
        if self.loaded is not None and self.contacts>0:self.pending_station_return_state='partially_depleted'
        super().wash();self.contacts=0
    def load(self,slot,same_color=False):
        super().load(slot,same_color);self.contacts=0
    def complete_contact(self):
        self.contacts+=1
        if self.contacts>self.limit:raise ValueError('contact budget exceeded before refill')


def transformed_rows(plan,scenario,mount):
    byid={d.study_dot_id:d for d in load_dots()};result=[]
    for r in plan['dots']:
        d=byid[int(r['study_dot_id'])];delta,status=surface_delta(d,scenario)
        x=number(r['artwork_x_mm'],'artwork x')+mount['g54_x_mm'];y=number(r['artwork_y_mm'],'artwork y')+mount['g54_y_mm']
        z=d.z_design_mm+mount['hanji_surface_offset_z_mm']+delta
        press=z-plan['config']['compression_depth_mm'];approach=z+plan['config']['approach_clearance_mm']
        if approach>mount['fixed_hover_g54_z_mm']:raise ValueError('approach exceeds fixed hover; change registration, not axis limits')
        result.append({**r,'g54_x_mm':x,'g54_y_mm':y,'surface_delta_applied_in_review_mm':delta,'surface_correction_status':status,'review_first_touch_z_mm':z,'review_press_z_mm':press,'review_approach_z_mm':approach,'fixed_hover_g54_z_mm':mount['fixed_hover_g54_z_mm'],'actual_first_touch_measured_z_mm':''})
    return result


def build_paint(plan,scenario):
    p,mount=review_profile(plan,scenario);rows=transformed_rows(plan,scenario,mount)
    if not rows:raise ValueError('empty painting plan')
    b=RuntimeBuilder(p);mat=DotMaterials(b,plan['config']['refill_every_contacts']);cfg=plan['config'];hover=mount['fixed_hover_g54_z_mm']
    services=[];b.marker('hanji_job_begin',plan['job_id']);canonical=load_dots()
    for r in rows:
        slot=cfg['color_station_map'][r['color_id']];kind=r['service_before']
        if kind:
            services.append(dict(before_sequence=r['execution_sequence'],before_study_dot_id=int(r['study_dot_id']),color_id=r['color_id'],action=kind,load_batch=r['load_batch']))
            b.marker('dot_service',kind,source_id=r['study_dot_id'])
            begin=len(b.commands)
            if kind=='color_change':mat.wash()
            mat.load(slot,same_color=(kind=='same_color_reload'))
            category='same_color_service' if kind=='same_color_reload' else 'color_change_service' if kind=='color_change' else 'initial_load'
            b.commands[begin:]=[replace(c,time_category=category) if c.kind in ('move','dwell') else c for c in b.commands[begin:]]
        elif slot!=mat.loaded:raise ValueError('material changed without scheduled service')
        if mat.contacts!=r['contact_in_batch']-1:raise ValueError('counter differs from planned batch')
        key={'source_id':r['study_dot_id']};x,y=r['g54_x_mm'],r['g54_y_mm'];touch=r['review_first_touch_z_mm'];press=r['review_press_z_mm'];approach=r['review_approach_z_mm']
        b.marker('dot_begin',str(r['execution_sequence']),**key)
        # Returning from a station stays at global station Z until above the dot.
        b.time_context=category if kind else 'paper_xy'
        b.xy((x,y),p.data['motion']['station_clearance_mm'] if b.at_station else hover,mat.state)
        if b.position[2]!=hover:b.move((x,y,hover),cfg['noncontact_z_feed_mm_min'],'paper_hover',mat.state,**key)
        b.at_station=False;b.time_context='paper_z_noncontact'
        b.move((x,y,approach),cfg['noncontact_z_feed_mm_min'],'approach',mat.state,**key)
        b.time_context='paper_contact'
        b.move((x,y,touch),cfg['contact_feed_mm_min'],'initial_contact',mat.state,**key)
        b.move((x,y,press),cfg['contact_feed_mm_min'],'pressure_variation',mat.state,**key)
        # FluidNC v4.1.1 G4 synchronizes the planner, then P seconds elapse.
        b.dwell(cfg['dwell_at_depth_s'],'dot_dwell');b.commands[-1]=replace(b.commands[-1],time_category='dot_dwell',source_id=r['study_dot_id'])
        b.move((x,y,touch),cfg['release_feed_mm_min'],'release',mat.state,**key)
        b.move((x,y,approach),cfg['release_feed_mm_min'],'paper_release_clearance',mat.state,**key)
        b.time_context='paper_z_noncontact';b.move((x,y,hover),cfg['noncontact_z_feed_mm_min'],'retract',mat.state,**key)
        b.marker('dot_complete',str(r['execution_sequence']),**key);mat.complete_contact();b.in_paper=True
        if mat.distance!=0:raise ValueError('no fake stroke distance may be accumulated')
    # Match the backend cleanup contract: arrive at PARK before appending FROM_PARK IR.
    begin=len(b.commands);b.time_context='end_cleanup';b.park(mat.station_travel_state())
    cp,tail=cleanup(p,'color',False)
    b.commands[begin:]=[replace(c,time_category='end_cleanup') if c.kind in ('move','dwell') else c for c in b.commands[begin:]]
    b.commands += [replace(c,time_category='end_cleanup') if c.kind in ('move','dwell') else c for c in tail]
    b.position=PARK;b.marker('hanji_job_complete',plan['job_id'])
    contacts=[c.xyz[2] for c in b.commands if c.action in ('initial_contact','pressure_variation','release')]
    # Hanji-only absolute range, never the original planar [-2,10] restriction.
    d=deepcopy(p.data);d['motion']['paper_contact_z_range']=[min(contacts),max(contacts)];p=Profile.from_dict(d)
    return p,b.commands,rows,services


def project_air(profile,commands):
    """Same planned XY/service schedule; no immersion, paper contact, or consumption."""
    b=RuntimeBuilder(profile)
    for c in commands:
        if c.kind=='move':
            b.time_context=c.time_category
            b.move((*c.xyz[:2],35.),c.feed_mm_min,'air_route',c.travel_state,source_id=c.source_id,travel_phase=c.travel_phase)
        elif c.kind=='dwell':b.marker('planned_'+c.action,str(c.seconds),source_id=c.source_id)
        elif c.kind=='marker':b.marker('planned_'+c.action,c.message,source_id=c.source_id)
        else:raise ValueError('unexpected contact/air command')
    return b.commands


def serialize(commands,profile,plan,scenario,air=False):
    name=plan['job_id']+('_AIR' if air else '')
    header=[BANNER.rstrip(),'HANJI independent Ilwolobongdo relief; C artwork; NOT a Spring revision',
        'ASSUMED NUMERIC SCENARIO: artwork XY plus configured placement; surface offsets are not measured',
        f"physical_panel={plan['physical_panel_id']} source_panel={plan['source_panel_id']} mode={plan['coordinate_mode']} dots={plan['dot_count']}",
        'MOUNT '+json_small(mount_for(scenario,plan['physical_panel_id'])),
        f"PRESS={plan['config']['compression_depth_mm']}mm DWELL={plan['config']['dwell_at_depth_s']}s REFILL={plan['config']['refill_every_contacts']}; provisional",
        'No original 2.8mm preview-to-compression conversion; no normalized pressure values',
        'No homing, G92, offsets, settings writes, physical approval or hardware transmission']
    return '\n'.join(s if s.startswith(';') else '; '+s for s in header)+'\n'+_serialize(commands,profile,digest({'plan':plan,'scenario':scenario}),name,'offline_review')


def json_small(obj):
    import json
    return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)


def readback(text,commands,profile,plan,rows,services,air=False):
    """Numeric dialect/IR readback plus independent per-dot and service checks."""
    if not text.startswith(BANNER):raise ValueError('missing unauthorized review banner')
    lines=[s for s in text.splitlines() if s and not s.startswith(';')]
    expected=[c for c in commands if c.kind!='marker']
    if not lines or lines[0]!='G21 G90 G94 G54' or lines[-1]!='M2' or len(lines)!=len(expected)+2:raise ValueError('modal/end/IR coverage mismatch')
    pos=tuple(profile.data['machine']['start_work_xyz']);bounds=[list(pos),list(pos)];feeds=[0.,0.,0.]
    for line,c in zip(lines[1:-1],expected):
        if len(line)>120:raise ValueError('controller line exceeds 120 characters')
        if c.kind=='move':
            m=_MOVE.fullmatch(line)
            if not m:raise ValueError('unapproved G-code command')
            values=tuple(map(float,m.groups()));q=values[:3];f=values[3]
            if any(abs(a-b)>5.1e-10 for a,b in zip(values,(*c.xyz,c.feed_mm_min))):raise ValueError('numeric coordinate/feed differs from IR')
            check_move(pos,q,f,c.action,profile,'paint',exact_benchmark_draw=False)
            if air and (q[2]!=35 or pos[2]!=35):raise ValueError('AIR contains contact descent')
            if c.action in ('initial_contact','pressure_variation','release','paper_release_clearance') and f>plan['config']['contact_feed_mm_min']+1e-6:raise ValueError('paper contact speed exceeded')
            if c.action=='travel' and pos[:2]!=q[:2]:
                if pos[2]!=q[2] or q[2]<rows[0]['fixed_hover_g54_z_mm']-1e-9:raise ValueError('lateral transit below fixed hover')
            length=dist(pos,q)
            for i in range(3):
                bounds[0][i]=min(bounds[0][i],q[i]);bounds[1][i]=max(bounds[1][i],q[i])
                if length:feeds[i]=max(feeds[i],abs(q[i]-pos[i])/length*f)
            pos=q
        elif c.kind=='dwell':
            m=_DWELL.fullmatch(line)
            if not m or abs(float(m.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell readback differs')
        else:raise ValueError('routine M0 or unresolved action')
    if pos!=PARK:raise ValueError('final park mismatch')
    if air:
        if any(c.kind=='dwell' or c.action in ('pressure_variation','dot_complete') for c in commands):raise ValueError('AIR consumed/completed a physical paper contact')
    else:
        ids=[c.source_id for c in commands if c.action=='dot_begin']
        if ids!=[r['study_dot_id'] for r in rows] or len(ids)!=len(set(ids)):raise ValueError('dot source/order mismatch')
        groups={}
        for c in commands:
            if c.action in ('initial_contact','pressure_variation','dot_dwell','release','paper_release_clearance','retract'):
                groups.setdefault(c.source_id,[]).append(c)
        for r in rows:
            group=groups.get(r['study_dot_id'],[])
            if [c.action for c in group]!=['initial_contact','pressure_variation','dot_dwell','release','paper_release_clearance','retract']:raise ValueError('explicit dot primitive sequence mismatch')
            touch,press,dwell,release=group[:4]
            if any(c.kind=='move' and c.xyz[:2]!=(r['g54_x_mm'],r['g54_y_mm']) for c in group):raise ValueError('XY moved during point contact')
            if abs(touch.xyz[2]-press.xyz[2]-plan['config']['compression_depth_mm'])>1e-8 or release.xyz!=touch.xyz:raise ValueError('local first-touch/compression/release mismatch')
            if dwell.seconds!=plan['config']['dwell_at_depth_s']:raise ValueError('dwell must remain full duration at depth')
        if sum(c.action=='terminal_cleanup_begin' for c in commands)!=1 or sum(c.action=='terminal_cleanup_complete' for c in commands)!=1:raise ValueError('terminal cleanup must occur once')
        tail=commands[next(i for i,c in enumerate(commands) if c.action=='terminal_cleanup_begin'):]
        ops=[c.action for c in tail if c.kind=='marker' and c.action in ('wash','absorbent_contact','controlled_rewet','pigment_load')]
        if ops!=['wash','wash','wash','absorbent_contact']:raise ValueError('terminal wash/purge/rewet order differs')
        if [c.seconds for c in tail if c.kind=='dwell']!=[10,10,10,4,4]:raise ValueError('terminal cleaning dwell differs')
        ops=[c.action for c in commands if c.kind=='marker']
        if ops.count('pigment_load')!=len(plan['used_color_order']) or ops.count('same_color_reload')!=plan['same_color_reloads'] or ops.count('full_wash')!=plan['color_changes']:raise ValueError('material count mismatch')
    return dict(numeric_readback_verified=True,configured_axis_reference_bounds=bounds,maximum_projected_axis_feeds_mm_min=feeds,planned_dots=plan['dot_count'],serialized_paper_contact_events=0 if air else plan['dot_count'],physically_completed_contacts=0,air_simulates_consumption=False if air else None,planned_loads=plan['loads'],planned_same_color_reloads=plan['same_color_reloads'],planned_color_changes=plan['color_changes'],planned_dot_dwell_s=plan['dot_count']*plan['config']['dwell_at_depth_s'],serialized_dot_dwell_s=0 if air else plan['dot_count']*plan['config']['dwell_at_depth_s'],M0_count=0,final_park=list(pos),M2_verified=True,physical_surface_or_swept_clearance_verified=False,machine_authorized=False)


def timing(commands,profile):
    machine=deepcopy(profile.data['machine']);machine['junction_deviation_mm']=.01
    model=estimate_prepared(prepare_timing(commands,profile),machine)
    model.update(junction_deviation_mm=.01,junction_status='assumed, not controller readback',axis_acceleration_mm_s2=machine['axis_acceleration_mm_s2'],physical_runtime_verified=False)
    return model


def require_physical_export(profile,plan,commands,authorization):
    """Keep existing official gates. Numeric review does not call this physical route."""
    profile.require('painting',[plan['config']['color_station_map'][c] for c in plan['used_color_order']],('color',))
    authorize(authorization,profile,digest({'plan':plan,'trajectory':[asdict(c) for c in commands]}),'painting',[plan['job_id']])
    for check in ('hanji_dry_surface','hanji_swept_tool','hanji_dot_contact','hanji_contact_reload'):
        if not profile.evidence_passed(check):raise ValueError('missing Hanji-specific physical evidence: '+check)
    position=tuple(profile.data['machine']['start_work_xyz'])
    for c in commands:
        if c.kind=='move':require_path(position,c.xyz,profile.data['machine']);position=c.xyz
