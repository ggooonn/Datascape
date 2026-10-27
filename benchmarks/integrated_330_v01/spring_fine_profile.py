"""PR42 B-only physical fine profile revision; immutable source and material order."""
from pathlib import Path
from dataclasses import replace,asdict
from copy import deepcopy
from collections import defaultdict
from math import dist
import argparse,gzip,json,subprocess,hashlib
import numpy as np
from . import spring_physical_ink as s
from . import spring_panels_contact20 as n
from . import spring_a_hierarchy as a

PIN='cf010e6f41de36baee83ed7a04cacbc3f0931e23'
BASE='docs/spring_a_hierarchy_v01/review/'
POLICY=s.ROOT/'config/spring_fine_profile_v01/policy.json'

def pinned_bytes(name):
    rel=BASE+name;raw=subprocess.check_output(['git','show',PIN+':'+rel],cwd=s.ROOT)
    s.require(raw==(s.ROOT/rel).read_bytes(),'Inherited PR42 input changed '+name)
    return raw

def frozen(name):
    raw=pinned_bytes(name);return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

def profile(ceiling,cfg):
    s.require(np.isfinite(ceiling) and 0<ceiling<=6,'Positive provisional ceiling at most6mm required')
    d=deepcopy(frozen('profile.fine.PROVISIONAL.json'));b=d['brush_profiles']['ink']
    s.require(b['knots'][-1]==[1,-1],'Expected pinned1mm fine curve')
    b.update(knots=[[pressure,z*ceiling] for pressure,z in b['knots']],paper_first_touch_z_mm=10,
        brush_id='fine-target-z10-uncalibrated',status='unverified',observations=[],
        notes='Target mounting Z10, not measured. PR42 fine curve shape scaled to provisional ceiling; no calibrated force or safe compression claim.')
    d['profile_id']=f'B-FINE-TARGET-Z10-C{ceiling:g}-OFFLINE-REVIEW'
    d['notes']='Paper-only reference revision. Station XY and absolute Z are unchanged and require fine-tool clearance checks.'
    d['machine']['mounted_brush_id']='fine-target-z10-UNVERIFIED'
    d['motion'].update(paper_hover_mm=20,paper_approach_mm=15)
    d['material']['ink_reload_mm']=450
    p=s.Profile.from_dict(d);s.require(p.paper_heights_for('ink','INK')==(10,20,15),'Target heights inconsistent')
    s.require(p.data['stations']==frozen('profile.fine.PROVISIONAL.json')['stations'],'Station coordinates changed')
    return p

def command_from_dict(c):return s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None})

def baseline_IR(fragments):
    """Rebuild the exact pinned IR from frozen groups/policies, then prove byte identity."""
    groups=frozen('B_SELECTIVE_A_FINE.execution.json.gz')['groups']
    small=s.Profile.from_dict(frozen('profile.small.json'));old=s.Profile.from_dict(frozen('profile.fine.PROVISIONAL.json'))
    policy=n.frozen('policy.json');policy['distance_limit_mm']=450
    commands,material=n.build(groups,fragments,small,policy,10)
    commands=a.v.fine_transform(commands,old)
    s.require(material==frozen('B_SELECTIVE_A_FINE.reload.json.gz'),'Pinned material schedule differs')
    name='SPRING_P2_INK_B_SELECTIVE_A_FINE_REVIEW'
    text=s.BANNER+'; INITIAL CONDITIONING REQUIRED / NUMERICAL REVIEW ONLY\n'+s._serialize(commands,old,s.PLAN_SHA,name,'offline_review')
    s.require(text.encode()==gzip.decompress(pinned_bytes(name+'.gcode.gz')),'Pinned fine reconstruction differs')
    return commands,material,groups

def retarget(commands,p):
    b=s.RuntimeBuilder(p)
    for c in commands:
        if c.kind!='move':
            if c.kind=='pause':c=replace(c,message='FINE PROFILE CANDIDATE: mount/verify touchZ10, run progressive test and station clearance checks. No calibrated contact authorization. M0 is not an interlock.')
            b.commands.append(c);continue
        q=c.xyz
        if c.artistic_pressure is not None:q=(*q[:2],p.brush_for('ink','INK').work_z_for(c.artistic_pressure))
        elif c.action in ('initial_contact','release'):q=(*q[:2],10)
        elif c.action in ('approach','paper_release_clearance'):q=(*q[:2],15)
        elif c.action in ('paper_hover','retract') or (c.action=='travel' and q[2]==22):q=(*q[:2],20)
        b.time_context=c.time_category
        b.move(q,c.feed_mm_min,c.action,c.travel_state,source_id=c.source_id,fragment_id=c.fragment_id,
            source_vertex=c.source_vertex,artistic_pressure=c.artistic_pressure,travel_phase=c.travel_phase)
    return b.commands

def station_signature(commands):
    return [(c.action,c.xyz,c.feed_mm_min,c.travel_phase,c.travel_state,c.seconds) for c in commands
            if c.time_category in ('station_handling','station_transfer') and c.kind in ('move','dwell')]

def station_audit(old,new,material):
    left=station_signature(old);right=station_signature(new)
    s.require(len(left)==len(right),'Station operation count changed')
    for a0,b0 in zip(left,right):
        s.require(a0[:2]==b0[:2] and a0[3:]==b0[3:],'Station absolute XYZ/action changed')
        s.require(a0[2]==b0[2],'Station feed changed')
    reports=[];previous=-1
    for op in material['station_operations']:
        end=op['after_command'];moves=[c for c in new[previous+1:end+1] if c.kind=='move' and c.action.startswith('station_')]
        if moves:
            reports.append(dict(station=op['station'],action=op['action'],minimum_commanded_z=min(c.xyz[2] for c in moves),
                maximum_commanded_z=max(c.xyz[2] for c in moves),absolute_xyz_feed=[[list(c.xyz),c.feed_mm_min,c.action] for c in moves]))
        previous=end
    return dict(all_station_XYZ_feeds_dwell_and_sequence_unchanged=True,station_motion_records=len(right),operations=reports,
        fine_brush_station_contact_certified=False,required_checks=['vessel bottom and fluid level','fine brush/holder insertion and withdrawal envelope',
        'inkstone shallow wipe and lip contact','PURGE surface height and compliance','all connecting swept paths'],paper_reference_delta_NOT_applied_to_stations=True)

def verify(text,commands,p,groups,fragments,air=False,test=False):
    rows=[l for l in text.splitlines() if l and not l.startswith(';')];expected=[c for c in commands if c.kind!='marker']
    s.require(rows[0]=='G21 G90 G94 G54' and rows[-1]=='M2' and len(rows)==len(expected)+2,'Dialect/command coverage')
    lines=iter(rows[1:-1]);pos=tuple(p.data['machine']['start_work_xyz']);bounds=[list(pos),list(pos)];active=None;seen=[];values=defaultdict(list)
    for c in commands:
        if c.action=='source_begin':s.require(active is None,'Nested source');active=c.message;seen.append(active)
        if c.action=='source_complete':s.require(active==c.message,'Source closure');active=None
        if active:s.require(c.time_category not in ('station_handling','station_transfer'),'Station inside original source')
        if c.kind=='marker':continue
        row=next(lines)
        if c.kind=='move':
            match=s._MOVE.fullmatch(row);s.require(match is not None,'Unapproved move');x,y,z,f=map(float,match.groups());q=(x,y,z)
            s.require(all(abs(a-b)<5.1e-10 for a,b in zip((*q,f),(*c.xyz,c.feed_mm_min))),'Numeric IR changed')
            s.check_move(pos,q,f,c.action,p,'air' if air else 'paint',exact_benchmark_draw=False)
            if air:s.require(z==35,'AIR descent/contact')
            elif c.action in ('initial_contact','release','approach','paper_release_clearance','paper_hover','retract'):
                required=10 if c.action in ('initial_contact','release') else 15 if c.action in ('approach','paper_release_clearance') else 20
                s.require(z==required,'Paper target changed')
            if c.time_category=='station_transfer' and pos[:2]!=q[:2]:s.require(pos[2]==z==35,'Station transfer below35')
            if c.action=='travel' and pos[:2]!=q[:2]:s.require(pos[2]==z and z in (20,35),'Lateral travel below hover')
            if c.artistic_pressure is not None:
                s.require(active is not None,'Pressure outside source');values[active].append((c.source_vertex,c.artistic_pressure,q[:2],z))
                if not air:s.require(abs(z-p.brush_for('ink','INK').work_z_for(c.artistic_pressure))<5.1e-10,'Mapping mismatch/clamp')
            if c.action=='draw' and not test:s.require(active is not None and c.artistic_pressure is not None,'Unaccounted drawing move')
            for k in range(3):bounds[0][k]=min(bounds[0][k],q[k]);bounds[1][k]=max(bounds[1][k],q[k])
            pos=q
        elif c.kind=='dwell':
            m=s._DWELL.fullmatch(row);s.require(m and abs(float(m.group(1))-c.seconds)<5.1e-10,'Dwell changed')
        elif c.kind=='pause':s.require(row=='M0','Missing review gate')
        else:raise ValueError('Unapproved command')
    events=[e for g in groups for e in g];s.require(seen==[e['id'] for e in events],'Source sequence changed')
    for e in events:
        frag=fragments[e['source']];v=values[e['id']];s.require(len(v)==len(frag.stroke.points),'Pressure sample coverage')
        for k,(index,pressure,xy,z) in enumerate(v):
            s.require(index==k and pressure==frag.stroke.points[k].pressure and all(abs(a-b)<5.1e-10 for a,b in zip(xy,frag.work_xy[k])),'Original XY/pressure/direction changed')
    pauses=sum(c.kind=='pause' for c in commands)
    s.require(rows.count('M0')==pauses and pauses==(0 if air else pauses if test else 1),'Review stop count')
    if not air:s.require(rows[1]=='M0','First movement precedes mounting review gate')
    s.require(pos==(800,800,35),'Terminal park changed')
    return dict(source_count=len(events),pressure_samples=sum(len(v) for v in values.values()),all_XY_pressure_direction_and_numeric_IR_verified=True,
        XYZ_bounds=bounds,final_XYZ=pos,M0_count=pauses,AIR_all_Z35=air,station_contact_authorized=False,machine_authorized=False)

def write(out,name,commands,p,groups,fragments,air=False,test=False):
    text=s.BANNER+'; FINE TARGET Z10 / PROVISIONAL PHYSICAL PROFILE / NOT CONTACT AUTHORIZED\n'+s._serialize(commands,p,s.PLAN_SHA,name,'offline_review')
    report=verify(text,commands,p,groups,fragments,air,test)
    (out/(name+'.gcode')).write_text(text);(out/(name+'.gcode.gz')).write_bytes(gzip.compress(text.encode(),mtime=0))
    s.save(out/(name+'.readback.json'),report)
    return dict(**report,sha256=s.sha(out/(name+'.gcode')),runtime=s.runtime(commands,p))

def calibration(p,cfg,ceiling=5.5):
    """Sacrificial PAPER ONLY test; no automatic contact at unverified stations."""
    b=s.RuntimeBuilder(p);c=cfg['calibration'];b.commands.append(s.Command('pause','calibration_mount_gate',message='SACRIFICIAL SHEET ONLY. Physically mount/verify fine tip first touchZ10. Manually condition/load LIGHT ink. Each following depth is unverified; stop if unsuitable.'))
    levels=[x for x in c['compression_steps_mm'] if x<=ceiling]+([6.] if ceiling==6 else [])
    log=[];contacts=0;distance=0.
    for k,depth in enumerate(levels):
        x,y=c['work_x_start'],c['work_y_start']+k*c['row_spacing_mm'];b.xy((x,y),35 if k==0 else 20,'ordinary_travel')
        if k==0:b.move((x,y,20),7000,'paper_hover')
        refill=contacts>=cfg['fine_contacts'] or distance>=cfg['fine_distance_mm']
        if refill:contacts=0;distance=0.
        b.commands.append(s.Command('pause','calibration_depth_gate',message=(('MANUALLY replenish SAME LIGHT INK; reset distance/contact counters. ' if refill else '')+f'Next compression{depth:g}mm / targetZ{10-depth:g}. Inspect previous mark, bowing/holder/paper before continuing. Not a safety interlock.')))
        for z,action,feed in [(15,'approach',7000),(10,'initial_contact',c['contact_z_feed_mm_min']),
            (10-depth,'calibration_compress',c['contact_z_feed_mm_min'])]:b.move((x,y,z),feed,action)
        b.move((c['work_x_end'],y,10-depth),c['drawing_feed_mm_min'],'draw')
        for z,action,feed in [(10,'release',c['contact_z_feed_mm_min']),(15,'paper_release_clearance',c['contact_z_feed_mm_min']),(20,'retract',7000)]:b.move((c['work_x_end'],y,z),feed,action)
        contacts+=1;distance+=c['work_x_end']-x
        log.append(dict(level=k+1,compression_mm=depth,Z=10-depth,start_XY=[x,y],end_XY=[c['work_x_end'],y],
            manual_same_ink_reload_before=refill,contacts_since_manual_reload=contacts,distance_since_manual_reload_mm=distance))
    b.park();s.require(not any(x.action.startswith('station_') for x in b.commands),'Test must not touch stations')
    return b.commands,log

def generate(output,context):
    out=Path(output);s.require(not out.exists(),'Fresh directory required');out.mkdir(parents=True)
    cfg=s.read(POLICY);_,rows,fragments=s.load_inputs(s.recover_context(Path(context)))
    commands,material,groups=baseline_IR(fragments);small=s.Profile.from_dict(frozen('profile.small.json'))
    mg=frozen('B_SELECTIVE_A_MAIN.execution.json.gz')['groups'];s.require(sum(map(len,mg))==985 and sum(map(len,groups))==224,'B allocation changed')
    s.save(out/'policy.json',cfg);s.save(out/'profile.small.PR42.unchanged.json',small.data)
    # Deliver the exact original main bytes and its original header/filename.
    for mode in ('INK','AIR'):
        name=f'SPRING_P2_{mode}_B_SELECTIVE_A_MAIN_REVIEW';raw=pinned_bytes(name+'.gcode.gz')
        (out/(name+'.gcode.gz')).write_bytes(raw);(out/(name+'.gcode')).write_bytes(gzip.decompress(raw))
    policy=n.frozen('policy.json');policy['distance_limit_mm']=800
    main_cmd,main_mat=n.build(mg,fragments,small,policy,20)
    s.require(main_mat==frozen('B_SELECTIVE_A_MAIN.reload.json.gz'),'Pinned main material schedule changed')
    for air,cmd in [(False,main_cmd),(True,s.air_projection(main_cmd,small))]:
        name=f'SPRING_P2_{"AIR" if air else "INK"}_B_SELECTIVE_A_MAIN_REVIEW'
        verify((out/(name+'.gcode')).read_text(),cmd,small,mg,fragments,air)
    s.save(out/'B_MAIN.execution.PR42.json.gz',dict(groups=mg));s.save(out/'B_MAIN.reload.PR42.json.gz',main_mat)
    s.save(out/'B_FINE.execution.PR42.json.gz',dict(groups=groups));s.save(out/'B_FINE.reload.PR42.json.gz',material)
    jobs={};mappings={};station_reports={}
    ps=[p.pressure for g in groups for e in g for p in fragments[e['source']].stroke.points]
    for peak,code in [(5.,'5P0'),(5.5,'5P5'),(6.,'6P0')]:
        p=profile(peak,cfg);new=retarget(commands,p)
        s.require(len(new)==len(commands),'Command scheduling changed')
        s.require([c.xyz[:2] for c in commands if c.kind=='move']==[c.xyz[:2] for c in new if c.kind=='move'],'XY path changed')
        n.audit_ir(new,material,groups,fragments,p);station_reports[code]=station_audit(commands,new,material)
        s.save(out/f'profile.fine.Z10.C{code}.PROVISIONAL.json',p.data)
        s.save(out/f'B_FINE_C{code}.IR.json.gz',[asdict(c) for c in new])
        s.save(out/f'B_FINE_C{code}.stations.json.gz',n.station_records(new,p))
        for air,cmd in [(False,new),(True,s.air_projection(new,p))]:
            name=f'SPRING_P2_{"AIR" if air else "INK"}_B_FINE_Z10_C{code}_REVIEW'
            jobs[name]=write(out,name,cmd,p,groups,fragments,air)
        compress=[10-p.brush_for('ink','INK').work_z_for(x) for x in ps]
        mappings[code]=dict(profile_ceiling_mm=peak,actual_artistic_pressure_min=min(ps),actual_artistic_pressure_max=max(ps),
            actual_compression_min_mm=min(compress),actual_compression_max_mm=max(compress),
            paper_Z_min=10-max(compress),paper_Z_max=10-min(compress),knots=p.data['brush_profiles']['ink']['knots'],
            full_numeric_Z_bounds=jobs[f'SPRING_P2_INK_B_FINE_Z10_C{code}_REVIEW']['XYZ_bounds'],
            physical_safe_range_measured=False)
        print(code,mappings[code]['paper_Z_min'],jobs[f'SPRING_P2_INK_B_FINE_Z10_C{code}_REVIEW']['runtime']['models']['configuration_reference']['acceleration_sensitive_seconds']/60,flush=True)
    for peak,code in [(5.5,'5P5'),(6.,'6P0')]:
        p=profile(peak,cfg);test,log=calibration(p,cfg,peak);s.save(out/f'CALIBRATION_{code}.levels.json',log)
        for air,cmd in [(False,test),(True,s.air_projection(test,p))]:
            name=f'FINE_PROGRESSIVE_{"AIR" if air else "CONTACT"}_UP_TO_{code}_REVIEW'
            jobs[name]=write(out,name,cmd,p,[],fragments,air,True)
    s.save(out/'station_motion_audit.json.gz',station_reports);s.save(out/'pressure_mapping.json',mappings)
    runtime_rows=['# B fine physical profile / numerical review','','All source allocation, material scheduling and station XYZ remain PR42. Times are modeled, not measured.','','| Ceiling | Actual max compression | Actual minimum paper Z | Fine minutes |','| --- | ---: | ---: | ---: |']
    for code,r in mappings.items():
        minutes=jobs[f'SPRING_P2_INK_B_FINE_Z10_C{code}_REVIEW']['runtime']['models']['configuration_reference']['acceleration_sensitive_seconds']/60
        runtime_rows.append(f"| {r['profile_ceiling_mm']} | {r['actual_compression_max_mm']:.6f} | {r['paper_Z_min']:.6f} | {minutes:.3f} |")
    runtime_rows+=['','Fine23 loads (16 light/7 dark),20 same-ink reloads,2 switches/full washes,3 terminal wash visits;450mm/10 contacts unchanged. Main66 loads/12 switches/800mm/20 contacts unchanged. Manual mounting, inspection, M0 waits and drying excluded. Progressive test is deliberately slower: Z300/draw600 only for calibration; full drawing/feed policy unchanged.','',
        '| Artistic pressure | Fine5mm Z | Fine5.5mm Z | Fine6mm Z |','| --- | ---: | ---: | ---: |']
    for k,(pressure,_) in enumerate(mappings['5P5']['knots']):
        runtime_rows.append('| '+str(pressure)+' | '+' | '.join(f"{10+mappings[code]['knots'][k][1]:.4f}" for code in ('5P0','5P5','6P0'))+' |')
    (out/'RUNTIME_MAPPING.md').write_text('\n'.join(runtime_rows)+'\n')

    s.save(out/'source_roles.PR42.unchanged.json.gz',frozen('source_roles.json.gz'))
    s.save(out/'retained_edges.PR42.unchanged.json.gz',frozen('retained_edges.json.gz'))
    s.save(out/'verification.json',dict(baseline=PIN,jobs=jobs,main_original_bytes_preserved=True,main_sources=985,fine_sources=224,
        fine_pressure_values=len(ps),fine_source_order_and_concentrations_unchanged=True,reload_schedule_unchanged=True,
        fine_loads=material['total_loads'],fine_switches=material['concentration_changes'],small_loads=main_mat['total_loads'],
        fine_max_contacts=material['maximum_contacts_before_reload'],fine_max_distance_mm=material['maximum_distance_before_reload_mm'],
        paper_target_mount_verified=False,station_contact_verified=False,machine_authorized=False))
    plots(out,mappings,cfg)
    s.save(out/'MANIFEST_SHA256.json',{f.name:s.sha(f) for f in sorted(out.iterdir()) if f.name!='MANIFEST_SHA256.json'})
    return audit(out,context)

def plots(out,mappings,cfg):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
    old=frozen('profile.small.json')['brush_profiles']['ink']['knots'];ax.plot([k[0] for k in old],[-k[1] for k in old],label='Unchanged small Baegunmo')
    for code,r in mappings.items():ax.plot([k[0] for k in r['knots']],[-k[1] for k in r['knots']],'-o',label=f'Fine ceiling{r["profile_ceiling_mm"]}mm / provisional')
    ax.axvspan(mappings['5P5']['actual_artistic_pressure_min'],mappings['5P5']['actual_artistic_pressure_max'],alpha=.08,color='green',label='Actual B-fine artistic range')
    ax.set(xlabel='Original artistic pressure (unchanged)',ylabel='Intended compression (mm)',title='NOT a physically calibrated force or safety map');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(out/'pressure_mapping.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(5,7),constrained_layout=True);c=cfg['calibration']
    for k,depth in enumerate(c['compression_steps_mm']):
        y=c['work_y_start']+k*c['row_spacing_mm'];ax.plot([c['work_x_start'],c['work_x_end']],[y,y],color='black');ax.text(c['work_x_end']+3,y,f'{k+1}: {depth:g}mm / Z{10-depth:g}',fontsize=8,va='center')
    ax.set(xlim=(330,410),ylim=(690,810),xlabel='Global G54 X (mm)',ylabel='Global G54 Y (mm)',title='Sacrificial-sheet test only / 5.5mm candidate');ax.set_aspect('equal');fig.savefig(out/'progressive_test_map.png',dpi=150);plt.close(fig)

def audit(output,context,independent=None):
    out=Path(output);_,rows,fragments=s.load_inputs(Path(context));report=s.read(out/'verification.json');cfg=s.read(out/'policy.json')
    old,mat,groups=baseline_IR(fragments);s.require(mat==s.read(out/'B_FINE.reload.PR42.json.gz'),'Reload manifest changed')
    s.require(s.read(out/'B_MAIN.reload.PR42.json.gz')==frozen('B_SELECTIVE_A_MAIN.reload.json.gz'),'Main reload manifest changed')
    s.require(groups==s.read(out/'B_FINE.execution.PR42.json.gz')['groups'],'Group order changed')
    checks={}
    for code in ('5P0','5P5','6P0'):
        p=s.Profile.load(out/f'profile.fine.Z10.C{code}.PROVISIONAL.json');cmd=[command_from_dict(c) for c in s.read(out/f'B_FINE_C{code}.IR.json.gz')]
        station_audit(old,cmd,mat);n.audit_ir(cmd,mat,groups,fragments,p)
        for air,commands in [(False,cmd),(True,s.air_projection(cmd,p))]:
            name=f'SPRING_P2_{"AIR" if air else "INK"}_B_FINE_Z10_C{code}_REVIEW';raw=(out/(name+'.gcode')).read_bytes()
            s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes())==raw,'Gzip mismatch');checks[name]=verify(raw.decode(),commands,p,groups,fragments,air)
    for peak,code in [(5.5,'5P5'),(6.,'6P0')]:
        p=profile(peak,cfg);commands,log=calibration(p,cfg,peak)
        s.require(max(x['contacts_since_manual_reload'] for x in log)<=10,'Calibration manual budget')
        for air,c in [(False,commands),(True,s.air_projection(commands,p))]:
            name=f'FINE_PROGRESSIVE_{"AIR" if air else "CONTACT"}_UP_TO_{code}_REVIEW';raw=(out/(name+'.gcode')).read_bytes()
            s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes())==raw,'Calibration gzip mismatch');checks[name]=verify(raw.decode(),c,p,[],fragments,air,True)
    for mode in ('INK','AIR'):
        name=f'SPRING_P2_{mode}_B_SELECTIVE_A_MAIN_REVIEW';s.require((out/(name+'.gcode.gz')).read_bytes()==pinned_bytes(name+'.gcode.gz'),'Main gzip changed')
        s.require((out/(name+'.gcode')).read_bytes()==gzip.decompress(pinned_bytes(name+'.gcode.gz')),'Main bytes changed')
    refs=s.read(out/'source_roles.PR42.unchanged.json.gz')
    for r in refs:s.require(r['source_record_sha256']==s.digest(rows[r['index']]) and r['canonical_stroke_sha256']==s.digest(asdict(fragments[r['index']].stroke)),'Source width/pressure hash changed')
    m=s.read(out/'MANIFEST_SHA256.json');s.require(all(s.sha(out/name)==sha for name,sha in m.items()),'SHA mismatch');equality={}
    if independent:
        for name in m:equality[name]=(out/name).read_bytes()==(Path(independent)/name).read_bytes()
        s.require(all(equality.values()),'Nondeterministic regeneration')
    result=dict(numeric_programs=len(checks)+2,programs=checks,main_exact_PR42_bytes=True,source_pressure_width_integrity=True,
        artistic_pressures_not_renormalized_or_clamped=True,station_absolute_XYZ_feed_dwell_unchanged=True,
        material_schedule_exact_PR42=True,independent_byte_equality=equality,machine_authorized=False)
    s.save(out/'delivered_audit.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--output',required=True);p.add_argument('--context',required=True);p.add_argument('--verify',action='store_true');p.add_argument('--independent');a0=p.parse_args()
    r=audit(a0.output,a0.context,a0.independent) if a0.verify else generate(a0.output,a0.context)
    print(json.dumps(r))
