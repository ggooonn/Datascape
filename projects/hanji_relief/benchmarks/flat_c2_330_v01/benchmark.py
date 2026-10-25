"""Four-condition flat C2 point benchmark using immutable PR33 data and PR32 services."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict,replace
from decimal import Decimal
from pathlib import Path
import csv,gzip,hashlib,json

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import _serialize,_MOVE,_DWELL,_atomic_output,save_json
from benchmarks.integrated_330_v01.numeric_review import BANNER,check_move
from benchmarks.integrated_330_v01.spring_end_cleanup import cleanup,PARK
from projects.hanji_relief.data import load_dots,load_json,number,integer,INPUT_SHA,PROJECT
from projects.hanji_relief.plan import order_dots
from projects.hanji_relief.motion import DotMaterials,RuntimeBuilder,PROFILE_PATH,timing

HERE=Path(__file__).resolve().parent
HANJI_PIN='b53719eaad224c9caba1c142c8ce519f6c2bd5f7'
BACKEND_PIN='eda6069b12c8785d458a0e8a567a9a86980bc394'
NAMESPACE='FLAT_C2_330_V01'
ORDER=('Q2','Q1','Q3','Q4')


def config(path=None):
    d=load_json(path or HERE/'config.json')
    if d.get('schema')!='hanji.flat_c2_comparison.v01' or d.get('paper_size_mm')!=[330,330] or d.get('material')!='C2':raise ValueError('incorrect flat benchmark identity')
    if tuple(d.get('condition_order',[]))!=ORDER or set(d.get('conditions',{}))!=set(ORDER):raise ValueError('condition order/coverage differs')
    if integer(d.get('refill_every_contacts'),'refill count',1)!=20:raise ValueError('comparison requires20 contacts per supply')
    number(d.get('preview_diameter_mm'),'preview diameter',1e-9)
    if d.get('preview_diameter_measured') is not False or d.get('artwork_completion_eligible') is not False:raise ValueError('unmeasured experiment is not an artwork completion source')
    reference={
        'Q1':dict(compression_depth_mm=4.0,dwell_at_depth_s=.5,center_mm=[247.5,247.5],allowed_centers_xy_mm=[[185,185],[310,310]]),
        'Q2':dict(compression_depth_mm=3.0,dwell_at_depth_s=.5,center_mm=[82.5,247.5],allowed_centers_xy_mm=[[20,185],[145,310]]),
        'Q3':dict(compression_depth_mm=3.0,dwell_at_depth_s=1.,center_mm=[82.5,82.5],allowed_centers_xy_mm=[[20,20],[145,145]]),
        'Q4':dict(compression_depth_mm=4.0,dwell_at_depth_s=1.,center_mm=[247.5,82.5],allowed_centers_xy_mm=[[185,20],[310,145]])}
    for q in d['conditions'].values():
        number(q.get('compression_depth_mm'),'condition depth',0)
        number(q.get('dwell_at_depth_s'),'condition dwell',0)
    if d['conditions']!=reference:raise ValueError('preserve the requested quadrant placement/depth/dwell comparison')
    r=d.get('registration',{})
    if not isinstance(r.get('paper_lower_left_g54_xy_mm'),list) or len(r['paper_lower_left_g54_xy_mm'])!=2:raise ValueError('paper mounting XY required')
    for x in r['paper_lower_left_g54_xy_mm']:number(x,'paper offset')
    for k in ['flat_first_touch_g54_z_mm','paper_hover_g54_z_mm','paper_approach_g54_z_mm']:number(r.get(k),k)
    if not r['flat_first_touch_g54_z_mm']<r['paper_approach_g54_z_mm']<=r['paper_hover_g54_z_mm']<=35:raise ValueError('invalid flat touch/approach/hover or Z35 ceiling')
    if r.get('status') not in ('PR32_REFERENCE_NUMERIC_REVIEW_NOT_NEW_MEASUREMENT','recorded_registration'):raise ValueError('registration provenance required')
    if r['status']=='recorded_registration' and not r.get('actual_mounting_confirmation_record'):raise ValueError('recorded registration needs provenance')
    return d


def select_patch():
    """Exact-decimal distance to panel center, ID tie-break; never scale the patch."""
    candidates=[d for d in load_dots() if d.physical_panel_id==4 and d.color_id=='C2']
    if len(candidates)!=390:raise ValueError('P04 C2 source population changed')
    def at(cx,cy):
        selected=sorted(candidates,key=lambda d:((Decimal(d.original['local_x_mm'])-cx)**2+(Decimal(d.original['local_y_mm'])-cy)**2,d.study_dot_id))[:40]
        xs=[Decimal(d.original['local_x_mm']) for d in selected];ys=[Decimal(d.original['local_y_mm']) for d in selected]
        return selected,[min(xs),min(ys),max(xs),max(ys)]
    selected,box=at(Decimal(100),Decimal(100));rule='40 nearest P04 C2 source points to local(100,100), squared exact-decimal XY distance; study_dot_id breaks ties'
    if box[2]-box[0]>125 or box[3]-box[1]>125:
        choices=[]
        for anchor in sorted(candidates,key=lambda d:d.study_dot_id):
            points,bounds=at(Decimal(anchor.original['local_x_mm']),Decimal(anchor.original['local_y_mm']))
            w,h=bounds[2]-bounds[0],bounds[3]-bounds[1]
            if w<=125 and h<=125:choices.append(((max(w,h),w*h,anchor.study_dot_id),points,bounds))
        if not choices:raise ValueError('no unscaled40-point source patch fits125x125')
        _,selected,box=min(choices,key=lambda v:v[0]);rule+='; fallback: source-point-centered candidates, minimum max-side/area/anchor ID'
    ordered=order_dots(selected,'local','right')
    return ordered,dict(rule=rule,source_input_sha256=INPUT_SHA,source_physical_panel_id=4,source_color='C2',candidate_count=len(candidates),selected_count=40,bbox_mm=list(map(float,box)),width_mm=float(box[2]-box[0]),height_mm=float(box[3]-box[1]),source_bbox_center_mm=[float((box[0]+box[2])/2),float((box[1]+box[3])/2)],source_study_dot_ids_in_relative_execution_order=[d.study_dot_id for d in ordered],transform_policy='translation only; no scaling/rotation/mirroring/snapping',relative_order='ascending exact source Y; first occupied row right-to-left, then serpentine')


def make_plan(condition_ids=None,cfg=None):
    cfg=cfg or config();qs=list(ORDER if condition_ids is None else condition_ids)
    if not qs or len(qs)!=len(set(qs)) or any(q not in ORDER for q in qs):raise ValueError('invalid condition selection')
    patch,selection=select_patch();center=[Decimal(str(v)) for v in selection['source_bbox_center_mm']]
    rows=[]
    for rank,q in enumerate(qs,1):
        condition=cfg['conditions'][q];translation=[Decimal(str(v))-s for v,s in zip(condition['center_mm'],center)]
        for i,d in enumerate(patch,1):
            x=Decimal(d.original['local_x_mm'])+translation[0];y=Decimal(d.original['local_y_mm'])+translation[1]
            lower,upper=condition['allowed_centers_xy_mm']
            if not lower[0]<=x<=upper[0] or not lower[1]<=y<=upper[1]:raise ValueError('unscaled point patch leaves quadrant center bounds')
            r=cfg['registration'];touch=r['flat_first_touch_g54_z_mm'];press=touch-condition['compression_depth_mm']
            rows.append(dict(experiment_contact_id=f'{NAMESPACE}:{q}:S{d.study_dot_id}',study_dot_id=d.study_dot_id,source_physical_panel_id=4,source_panel_id=d.source_panel_id,quadrant=q,condition_execution_rank=rank,sequence_in_condition=i,execution_sequence=len(rows)+1,source_local_x_mm=d.local_x_mm,source_local_y_mm=d.local_y_mm,source_z_design_mm_REFERENCE_ONLY=d.z_design_mm,paper_x_mm=float(x),paper_y_mm=float(y),translation_x_mm=float(translation[0]),translation_y_mm=float(translation[1]),g54_x_mm=float(x)+r['paper_lower_left_g54_xy_mm'][0],g54_y_mm=float(y)+r['paper_lower_left_g54_xy_mm'][1],flat_first_touch_g54_z_mm=touch,compression_depth_mm=condition['compression_depth_mm'],press_g54_z_mm=press,dwell_at_depth_s=condition['dwell_at_depth_s'],color_id='C2',load_batch_in_condition=1 if i<=20 else 2,contact_in_batch=(i-1)%20+1,service_before='condition_prepare_and_initial_load' if i==1 else 'same_color_reload' if i==21 else '',artwork_completion_eligible=False,physically_completed=False))
    name='FLAT_C2_330_ALL_Q2_Q1_Q3_Q4' if len(qs)==4 else 'FLAT_C2_330_'+qs[0]
    return dict(schema='hanji.flat_comparison_plan.v01',job_id=name,config=cfg,condition_order=qs,selection=selection,contact_count=len(rows),pigment_loads=2*len(qs),condition_preparations=len(qs),same_color_reloads=len(qs),completion_namespace=NAMESPACE,artwork_completion_eligible=False,physically_completed_contacts=0,rows=rows)


def profile_for(plan):
    p=Profile.load(PROFILE_PATH);d=deepcopy(p.data);cfg=plan['config'];r=cfg['registration']
    if p.paper_first_touch_for('color','C2')!=10:raise ValueError('PR32 flat reference changed; inspect before replacing10')
    d.update(profile_id='FLAT-C2-330-FOUR-CONDITION-REVIEW',status='nominal_review',evidence=[])
    d['material'].update(color_order=['C2'],end_cleanup=False,refill_policy='contact_count',refill_every_contacts=20)
    d['motion'].update(paper_hover_mm=r['paper_hover_g54_z_mm'],paper_approach_mm=r['paper_approach_g54_z_mm'],paper_contact_z_range=[r['flat_first_touch_g54_z_mm']-4,r['flat_first_touch_g54_z_mm']],local_hover={'enabled':False})
    for key in ('paper_hover_clearance_mm','paper_approach_clearance_mm'):d['motion'].pop(key,None)
    for key in ('color','C2'):
        if key in d['brush_profiles']:d['brush_profiles'][key]['paper_first_touch_z_mm']=r['flat_first_touch_g54_z_mm']
    d['notes']='Independent flat330 C2 numeric review; reference first-touch10 is not freshly measured. Original relief Z is provenance only, not contact geometry. Stations/controller/Spring/artwork settings unchanged.'
    return Profile.from_dict(d)


class ComparisonMaterials(DotMaterials):
    def wash(self):
        # Preserve the used-brush FIRST return, then clear the paper budget before
        # water becomes the active load; wash/rewet travel must not inherit20 dots.
        if self.loaded is not None and self.contacts>0:self.pending_station_return_state='partially_depleted'
        self.contacts=0
        return super().wash()
    def station(self,role,action,material_key=None):
        # All four preparation passes use the same C2 absorbent policy, including a clean first brush.
        return super().station(role,action,'C2' if role=='sponge' else material_key)


def recolor_time(commands,start,category):
    commands[start:]=[replace(c,time_category=category) if c.kind in ('move','dwell') else c for c in commands[start:]]


def build(plan):
    p=profile_for(plan);v=p.data['motion'];r=plan['config']['registration'];b=RuntimeBuilder(p);m=ComparisonMaterials(b,20)
    b.marker('flat_benchmark_begin',plan['job_id']);current=None
    for row in plan['rows']:
        q=row['quadrant'];sid=row['experiment_contact_id']
        if row['sequence_in_condition']==1:
            b.marker('flat_condition_begin',q);b.marker('flat_preparation_begin',q)
            begin=len(b.commands);m.wash();m.load('C2');recolor_time(b.commands,begin,'condition_preparation')
            b.marker('flat_preparation_complete',q);current=q
        elif row['sequence_in_condition']==21:
            b.marker('flat_refill_begin',q,source_id=sid);begin=len(b.commands);m.load('C2',same_color=True);recolor_time(b.commands,begin,'same_color_refill');b.marker('flat_refill_complete',q,source_id=sid)
        if current!=q or m.contacts!=row['contact_in_batch']-1:raise ValueError('condition/contact counter mismatch')
        key={'source_id':sid};x,y=row['g54_x_mm'],row['g54_y_mm'];touch=row['flat_first_touch_g54_z_mm'];press=row['press_g54_z_mm']
        b.marker('flat_dot_begin',q+'/'+str(row['sequence_in_condition']),**key)
        category='condition_preparation' if row['sequence_in_condition']==1 else 'same_color_refill' if row['sequence_in_condition']==21 else 'paper_xy'
        b.time_context=category;b.xy((x,y),v['station_clearance_mm'] if b.at_station else r['paper_hover_g54_z_mm'],m.state)
        b.time_context='paper_z_noncontact'
        if b.position[2]!=r['paper_hover_g54_z_mm']:b.move((x,y,r['paper_hover_g54_z_mm']),v['z_travel_mm_min'],'paper_hover',m.state,**key)
        b.at_station=False
        # Fixed-XY PR33 point primitive adapted to one flat first-touch reference.
        b.move((x,y,r['paper_approach_g54_z_mm']),v['paper_approach_mm_min'],'approach',m.state,**key)
        b.time_context='paper_contact'
        b.move((x,y,touch),v['paper_contact_mm_min'],'initial_contact',m.state,**key)
        b.move((x,y,press),v['paper_contact_mm_min'],'pressure_variation',m.state,**key)
        b.dwell(row['dwell_at_depth_s'],'flat_dot_dwell');b.commands[-1]=replace(b.commands[-1],source_id=sid,time_category='depth_dwell')
        b.move((x,y,touch),v['paper_release_mm_min'],'release',m.state,**key)
        b.move((x,y,r['paper_approach_g54_z_mm']),v['paper_release_mm_min'],'paper_release_clearance',m.state,**key)
        b.time_context='paper_z_noncontact';b.move((x,y,r['paper_hover_g54_z_mm']),v['z_travel_mm_min'],'retract',m.state,**key)
        m.complete_contact();b.marker('flat_dot_complete',q+'/'+str(row['sequence_in_condition']),**key)
        if m.distance!=0:raise ValueError('point consumption must not invent drawing distance')
        if row['sequence_in_condition']==40:b.marker('flat_condition_complete',q)
    begin=len(b.commands);b.park(m.station_travel_state());recolor_time(b.commands,begin,'terminal_cleanup')
    _,tail=cleanup(p,'color',False);b.commands.extend(replace(c,time_category='terminal_cleanup') if c.kind in ('move','dwell') else c for c in tail)
    b.marker('flat_benchmark_complete',plan['job_id'])
    return p,b.commands


def serialize(plan,p,commands):
    r=plan['config']['registration']
    comments=[BANNER.rstrip(),'; FLAT C2 comparison only; experiment IDs are NOT artwork completions',
              '; FIRST-TOUCH reference='+str(r['flat_first_touch_g54_z_mm'])+'; status='+r['status'],
              '; PAPER origin G54 XY='+str(r['paper_lower_left_g54_xy_mm'])+'; stations are fixed',
              '; CONDITION order='+','.join(plan['condition_order'])+'; no guide labels/lines are painted',
              '; 20 contacts then reload before21; full at-depth G4 dwell; no normalized pressure',
              '; Source relief Z values are ignored for all flat contact and compression commands']
    return '\n'.join(comments)+'\n'+_serialize(commands,p,digest(plan),plan['job_id'],'offline_review')


def readback(text,plan,p,commands):
    if not text.startswith(BANNER):raise ValueError('missing numeric review status')
    lines=[s for s in text.splitlines() if s and not s.startswith(';')];expected=[c for c in commands if c.kind!='marker']
    if len(lines)!=len(expected)+2 or lines[0]!='G21 G90 G94 G54' or lines[-1]!='M2':raise ValueError('modal/coverage mismatch')
    pos=tuple(p.data['machine']['start_work_xyz']);bounds=[list(pos),list(pos)];groups={};indices={}
    for line,c in zip(lines[1:-1],expected):
        if len(line)>120:raise ValueError('controller line exceeds120')
        if c.kind=='move':
            match=_MOVE.fullmatch(line)
            if not match:raise ValueError('unexpected motion command')
            vals=tuple(map(float,match.groups()));q=vals[:3];feed=vals[3]
            if any(abs(a-b)>5.1e-10 for a,b in zip(vals,(*c.xyz,c.feed_mm_min))):raise ValueError('G-code XYZ/feed differs')
            check_move(pos,q,feed,c.action,p,'paint',exact_benchmark_draw=False)
            for i in range(3):bounds[0][i]=min(bounds[0][i],q[i]);bounds[1][i]=max(bounds[1][i],q[i])
            if c.action in ('initial_contact','pressure_variation','release','paper_release_clearance') and feed>2000+1e-6:raise ValueError('controlled contact exceeds2000')
            if c.action=='travel' and q[:2]!=pos[:2] and (q[2]!=pos[2] or q[2]<plan['config']['registration']['paper_hover_g54_z_mm']):raise ValueError('XY travel below flat hover')
            pos=q
        elif c.kind=='dwell':
            match=_DWELL.fullmatch(line)
            if not match or abs(float(match.group(1))-c.seconds)>5.1e-10:raise ValueError('at-depth dwell differs')
        else:raise ValueError('M0 or unresolved command')
    for i,c in enumerate(commands):
        if c.source_id:groups.setdefault(c.source_id,[]).append(c)
        if c.action=='flat_dot_begin':indices[c.source_id]=i
    if [c.source_id for c in commands if c.action=='flat_dot_begin']!=[r['experiment_contact_id'] for r in plan['rows']]:raise ValueError('experimental contact ID/order mismatch')
    for row in plan['rows']:
        sid=row['experiment_contact_id'];group=[c for c in groups[sid] if c.action in ('initial_contact','pressure_variation','flat_dot_dwell','release','paper_release_clearance','retract')]
        if [c.action for c in group]!=['initial_contact','pressure_variation','flat_dot_dwell','release','paper_release_clearance','retract']:raise ValueError('point primitive order differs')
        if any(c.kind=='move' and c.xyz[:2]!=(row['g54_x_mm'],row['g54_y_mm']) for c in group):raise ValueError('XY moved during contact')
        if group[0].xyz[2]!=row['flat_first_touch_g54_z_mm'] or group[1].xyz[2]!=row['press_g54_z_mm'] or group[2].seconds!=row['dwell_at_depth_s'] or group[3].xyz!=group[0].xyz:raise ValueError('flat touch/press/dwell/release differs')
    conditions=plan['condition_order']
    if [c.message for c in commands if c.action=='flat_condition_begin']!=conditions or [c.message for c in commands if c.action=='flat_preparation_begin']!=conditions:raise ValueError('condition initialization mismatch')
    for q in conditions:
        start=next(i for i,c in enumerate(commands) if c.action=='flat_condition_begin' and c.message==q);end=next(i for i,c in enumerate(commands) if c.action=='flat_condition_complete' and c.message==q)
        region=commands[start:end+1];ops=[c.action for c in region if c.kind=='marker']
        if ops.count('full_wash')!=1 or ops.count('pigment_load')!=1 or ops.count('same_color_reload')!=1:raise ValueError('condition preparation/refill count differs')
        prep_end=next(i for i,c in enumerate(region) if c.action=='flat_preparation_complete')
        if any(c.action=='flat_dot_begin' for c in region[:prep_end]):raise ValueError('contact before initial preparation')
        rows=[r for r in plan['rows'] if r['quadrant']==q];last20=rows[19]['experiment_contact_id'];first21=rows[20]['experiment_contact_id']
        end20=next(i for i,c in enumerate(commands) if c.action=='flat_dot_complete' and c.source_id==last20)
        boundary=commands[end20+1:indices[first21]]
        if sum(c.action=='same_color_reload' for c in boundary)!=1 or any(c.action in ('wash','full_wash') for c in boundary):raise ValueError('20-to21 refill boundary differs')
        if sum(c.action=='flat_dot_complete' for c in region)!=40:raise ValueError('condition must contain40 contacts')
    if sum(c.action=='terminal_cleanup_begin' for c in commands)!=1:raise ValueError('terminal cleanup must occur once')
    tail=commands[next(i for i,c in enumerate(commands) if c.action=='terminal_cleanup_begin'):]
    if [c.seconds for c in tail if c.kind=='dwell']!=[10,10,10,4,4] or any(c.action in ('controlled_rewet','pigment_load') for c in tail):raise ValueError('terminal cleanup differs')
    if pos!=PARK or any(c.artistic_pressure is not None or c.action=='draw' for c in commands):raise ValueError('park or explicit point semantics differ')
    return dict(numeric_readback_verified=True,contact_count=plan['contact_count'],pigment_loads=2*len(conditions),same_color_reloads=len(conditions),condition_preparations=len(conditions),at_depth_dwell_s=sum(r['dwell_at_depth_s'] for r in plan['rows']),axis_reference_bounds=bounds,start_G54_xyz=p.data['machine']['start_work_xyz'],end_G54_xyz=list(pos),terminal_cleanup_count=1,M0_count=0,M2_verified=True,relief_Z_applied=False,artwork_completion_eligible=False,physically_completed_contacts=0,machine_authorized=False,physical_flat_registration_or_tool_clearance_verified=False)


def condition_times(plan,p,commands):
    """Account each condition in one continuous planner model, without inserted stops."""
    current=None;tagged=[]
    for c in commands:
        if c.action=='flat_condition_begin':current=c.message
        if c.kind in ('move','dwell') and current:c=replace(c,time_category=current+'/'+c.time_category)
        tagged.append(c)
        if c.action=='flat_condition_complete':current=None
    model=timing(tagged,p)
    groups=model['acceleration_sensitive_seconds_by_category']
    return {q:{'modeled_seconds':sum(v for k,v in groups.items() if k.startswith(q+'/')),'by_category_seconds':{k.split('/',1)[1]:v for k,v in groups.items() if k.startswith(q+'/')}} for q in plan['condition_order']}


def write_csv(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def generate(output,config_path=None):
    cfg=config(config_path);plans=[make_plan(cfg=cfg)]+[make_plan([q],cfg) for q in ORDER]
    def write(out):
        save_json(out/'config.json',cfg);save_json(out/'selected_source_patch.json',select_patch()[1]);report=dict(schema='hanji.flat_c2_review.v01',hanji_source_sha=HANJI_PIN,backend_source_sha=BACKEND_PIN,status='numeric_reference_review_not_machine_authorized',source_C_csv_sha256=INPUT_SHA,jobs={},artwork_settings_changed=False,hardware_operation=False)
        for plan in plans:
            p,commands=build(plan);text=serialize(plan,p,commands);checked=readback(text,plan,p,commands);name=plan['job_id']
            (out/(name+'.gcode')).write_text(text);save_json(out/(name+'.plan.json'),plan);save_json(out/(name+'.profile.json'),p.data);save_json(out/(name+'.trajectory.json.gz'),[asdict(c) for c in commands]);write_csv(out/(name+'.mapping.csv'),plan['rows'])
            report['jobs'][name]=dict(readback=checked,timing=timing(commands,p),plan_sha256=digest(plan),profile_sha256=p.sha256,gcode_sha256=hashlib.sha256(text.encode()).hexdigest(),conditions=plan['condition_order'])
        full_p,full_commands=build(plans[0])
        report['integrated_condition_timing']=condition_times(plans[0],full_p,full_commands)
        breakdown=[]
        for job,data in report['jobs'].items():
            for category,seconds in data['timing']['acceleration_sensitive_seconds_by_category'].items():
                if seconds:breakdown.append(dict(job=job,scope='complete_job',category=category,modeled_seconds=seconds))
        for q,data in report['integrated_condition_timing'].items():
            for category,seconds in data['by_category_seconds'].items():breakdown.append(dict(job=plans[0]['job_id'],scope=q,category=category,modeled_seconds=seconds))
        write_csv(out/'time_breakdown.csv',breakdown)
        save_json(out/'verification.json',report)
        allrows=plans[0]['rows'];observations=[]
        for row in allrows:
            i=row['sequence_in_condition'];window='1-5' if i<=5 else '16-20' if 16<=i<=20 else '21-25' if 21<=i<=25 else '36-40' if i>=36 else 'other'
            observations.append({**row,'comparison_window':window,'dry_width_mm':'','dry_height_mm':'','bleed_mm':'','density':'','neighbor_overlap':'','paper_deformation':'','brush_initial_water':'','C2_dilution_and_binder':'','drying_time':'','run_id':'','operator':'','date':'','observations':''})
        write_csv(out/'observations_by_contact.csv',observations)
        summary=[dict(quadrant=q,window=w,source_IDs=';'.join(str(r['study_dot_id']) for r in allrows if r['quadrant']==q and lo<=r['sequence_in_condition']<=hi),dry_width_mm='',dry_height_mm='',bleed_mm='',density='',neighbor_overlap='',paper_deformation='',notes='') for q in ORDER for w,lo,hi in [('1-5',1,5),('16-20',16,20),('21-25',21,25),('36-40',36,40)]]
        write_csv(out/'observations_by_window.csv',summary)
        from .preview import write_previews
        write_previews(out,plans[0],report)
        (out/'README.md').write_text('Numeric offline reference review. Five alternative programs: integrated160contacts OR independent40-contact conditions. Actual paper mounting/first touch is unconfirmed; reference touch10, approach15, hover20. Keep fixed stations and current brush. No artwork completion is recorded. Guide labels are never painted. See parent README for reproduction and full policy.\n')
        return report
    return _atomic_output(output,write)


def verify(output):
    out=Path(output);hashes=load_json(out/'MANIFEST_SHA256.json');actual={str(p.relative_to(out)) for p in out.iterdir() if p.is_file() and p.name!='MANIFEST_SHA256.json'}
    if set(hashes)!=actual:raise ValueError('manifest coverage differs')
    for name,sha in hashes.items():
        path=(out/name).resolve()
        if not path.is_relative_to(out.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('delivery hash differs')
    cfg=config(out/'config.json');report=load_json(out/'verification.json')
    if report.get('status')!='numeric_reference_review_not_machine_authorized' or report.get('source_C_csv_sha256')!=INPUT_SHA or report.get('hanji_source_sha')!=HANJI_PIN or report.get('backend_source_sha')!=BACKEND_PIN or report.get('hardware_operation') is not False:raise ValueError('review identity/source status differs')
    plans=[make_plan(cfg=cfg)]+[make_plan([q],cfg) for q in ORDER]
    for plan in plans:
        name=plan['job_id'];p,commands=build(plan)
        if (out/(name+'.gcode')).read_text()!=serialize(plan,p,commands):raise ValueError('regenerated G-code differs')
        if load_json(out/(name+'.plan.json'))!=plan or load_json(out/(name+'.profile.json'))!=p.data:raise ValueError('plan/profile differs')
        if digest(json.loads(gzip.decompress((out/(name+'.trajectory.json.gz')).read_bytes())))!=digest([asdict(c) for c in commands]):raise ValueError('trajectory differs')
        with (out/(name+'.mapping.csv')).open(newline='') as f:saved=list(csv.DictReader(f))
        if saved!=[{k:str(v) for k,v in r.items()} for r in plan['rows']]:raise ValueError('mapping differs from original experiment')
        if readback((out/(name+'.gcode')).read_text(),plan,p,commands)!=report['jobs'][name]['readback'] or timing(commands,p)!=report['jobs'][name]['timing']:raise ValueError('verification or timing differs')
    full_p,full_commands=build(plans[0])
    if report.get('integrated_condition_timing')!=condition_times(plans[0],full_p,full_commands):raise ValueError('integrated condition timing differs')
    return dict(files_verified=len(hashes),jobs_regenerated=5,integrated_contacts=160,machine_authorized=False,artwork_completion_eligible=False)
