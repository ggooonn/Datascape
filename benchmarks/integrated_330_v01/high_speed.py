"""Reversible high-speed hardware candidate and numeric commissioning reviews.

No device I/O, passed physical evidence or authorized Spring export. Baseline
files remain immutable. The shared production travel/station grammar is reused.
"""
from copy import deepcopy
from dataclasses import asdict,replace
from pathlib import Path
from math import dist
import difflib
import hashlib
import json

import yaml

from datascape.gcode.binding import digest,load_bound_spring
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import (Builder,emit_station_operation,
    _station_geometry,shallow_wipe_points,build_job,Materials,Command)
from datascape.gcode.production.calibration_jobs import render_calibration,validate_request
from datascape.gcode.production.sequence import reference_order,make_plan,verify_plan
from datascape.gcode.production.exporter import (_atomic_output,_serialize,save_json,
    _MOVE,_DWELL,verify_draw_lineage)
from datascape.gcode.production.timing import prepare_timing,estimate_prepared
from .measured_stations import inputs as baseline_inputs,job_check
from .numeric_review import BANNER,STATUS,check_move,xy_route
from .spring_runtime import RuntimeBuilder,RuntimeMaterials

PIN='ab1c7abeb384b8e73dcba97a5bc7a224bc3abd60'
PLAN_SHA='8b4804f561f0eaab28753ae1790ce3b0f5b9ab8ba9a4a2ffe1e4daecbe2596bd'
PROFILE_PATH='docs/plotter_backend_v03/review/spring_z8_v01/profile.spring_z8.candidate.json'
APPROACH_MM=35.


def controller_candidate(root):
    path=root/'benchmarks/integrated_330_v01/review_measured_stations/config.X860.candidate.yaml'
    raw=path.read_bytes();parts=raw.decode().splitlines(True);axis=None;changes=[]
    for i,line in enumerate(parts):
        if line in ('  x:\n','  y:\n','  z:\n'):axis=line.strip()[:-1]
        if axis in ('x','y'):
            for key,value in (('max_rate_mm_per_min',20000.),('acceleration_mm_per_sec2',1500.)):
                if line.startswith('    '+key+':'):
                    old=float(line.split(':',1)[1]);parts[i]=f'    {key}: {value:.1f}\n'
                    changes.append(dict(path='axes.'+axis+'.'+key,old=old,new=value))
    candidate=''.join(parts).encode();before=yaml.safe_load(raw);after=yaml.safe_load(candidate)
    expected=deepcopy(before)
    for axis in ('x','y'):expected['axes'][axis].update(max_rate_mm_per_min=20000.,acceleration_mm_per_sec2=1500.)
    if after!=expected or len(changes)!=4 or after['axes']['x']['max_travel_mm']!=860:
        raise ValueError('YAML candidate must change exactly four XY speed/acceleration scalars')
    report=dict(source_PR31_X860_sha256=hashlib.sha256(raw).hexdigest(),
        high_speed_yaml_sha256=hashlib.sha256(candidate).hexdigest(),changes=changes,
        X_max_travel_mm=860,Z_configuration_unchanged=before['axes']['z']==after['axes']['z'],
        all_other_bytes_and_configuration_preserved=True,installed=False,read_back=False,
        physically_validated=False,soft_limits_setting_changed=False,
        note='All original comments retained as archival text; the four scalar edits and this record define the new candidate. No controller writes.')
    diff=''.join(difflib.unified_diff(raw.decode().splitlines(True),candidate.decode().splitlines(True),
        fromfile='PR31/config.X860.candidate.yaml',tofile='config.X860.high_speed.candidate.yaml'))
    return candidate,diff,report


def candidate_profile(root,wet=12000,approach_mm=APPROACH_MM):
    baseline=Profile.load(root/PROFILE_PATH);d=deepcopy(baseline.data)
    yaml_bytes,_,record=controller_candidate(root);axes=yaml.safe_load(yaml_bytes)['axes']
    d['profile_id']=f'HIGH-SPEED-XY15000-WET{wet}-INK1200-REVIEW'
    d['machine'].update(axis_max_rate_mm_min=[axes[a]['max_rate_mm_per_min'] for a in ('x','y','z')],
        axis_acceleration_mm_s2=[axes[a]['acceleration_mm_per_sec2'] for a in ('x','y','z')],
        target_config_sha256=record['high_speed_yaml_sha256'],target_config_installed=False)
    v=d['motion'];v.update(ordinary_travel_mm_min=15000,wet_loaded_mm_min=wet,
        partially_depleted_mm_min=15000)
    v['station_phase_limits_mm_min']['agitation']=1500
    v['segmented_travel']={}
    for state in ('ordinary_travel','wet_loaded','partially_depleted'):
        edge=5 if state=='wet_loaded' else approach_mm
        v['segmented_travel'][state]=dict(departure_mm=edge,arrival_mm=edge,
            station_arrival_mm=approach_mm,departure_mm_min=3000,arrival_mm_min=3000)
    d['material']['ink_reload_mm']=1200
    for role in ('ink','water'):
        st=d['stations'][role];st['agitation_xy_mm']=[10,0];st['phase_feeds_mm_min']['agitation']=1500
        st['lip_stripping']=dict(enabled=False,measured_contact_xyz=None,contact_feed_mm_min=None,
            relative_x_mm=-20,safe_retract_z=None,
            status='NOT IMPLEMENTED / NOT MEASURED. Relative X-20 from future measured contact; never absolute X-20.')
    d['notes']='Separate operator-requested high-speed candidate. No installation/readback or physical pass inferred. Spring Z-8 response unchanged; benchmark constant -10 depths remain. Existing two-pass wipe retained; stone-lip operation disabled.'
    if d['brush_profiles']!=baseline.data['brush_profiles']:raise ValueError('Spring pressure candidate changed')
    return Profile.from_dict(d)


def endurance_plan():
    lines=[]
    for n in range(18):
        x,y=(20,30+n*16) if n<15 else (180,30+(n-15)*32)
        lines.append(dict(id=f'ENDURANCE-{n+1:02}',start_xy=[x,y],end_xy=[x+80,y],
            z_mm=-2,feed_mm_min=6000,comparison='before reload' if n<15 else 'after reload'))
    return dict(schema='datascape.ink_endurance_review.v01',substrate_mm=[330,330],
        strokes=lines,threshold_mm=1200,total_drawing_mm=1440,
        expected_reload_before_stroke=16,
        contact_status='Explicit constant Z-2 trial; not a modification of Spring artistic pressure or benchmark40.',
        prior_operator_report='Ten80mm strokes (~800mm) without obvious problem; NOT proof of1200mm delivery')


def _draw(b,p,line,source):
    part=dict(schema='datascape.calibration_plan.v0.3',paper_region_xy=[[10,10],[320,320]],
              brush_lines=[{k:line[k] for k in ('start_xy','end_xy','z_mm','feed_mm_min')}],notes='Existing controlled contact/release primitive')
    validate_request(part,p,physical=False)
    b.marker('source_begin',source,source_id=source);n=len(b.commands)
    render_calibration(part,p,b,integrated=True,normal_paper_links=True)
    for i in range(n,len(b.commands)):
        if b.commands[i].action=='draw':b.commands[i]=replace(b.commands[i],source_id=source)
    b.marker('source_complete',source,source_id=source)


def build_benchmark(root,p,endurance=False):
    request=baseline_inputs(root)[0];b=RuntimeBuilder(p);m=RuntimeMaterials(b)
    def visit(role,action):
        b.marker('benchmark_station_visit',role+':'+action)
        m.station(role,action)
    visit('ink','pigment_load');m.loaded='ink';m.distance=0
    if endurance:
        plan=endurance_plan()
        for i,line in enumerate(plan['strokes']):
            if m.distance>=p.data['material']['ink_reload_mm']:
                b.marker('endurance_reload_boundary',str(i+1));visit('ink','same_color_reload');m.distance=0
            _draw(b,p,line,line['id']);m.distance+=dist(line['start_xy'],line['end_xy'])
    else:
        plan=request
        for column,part in enumerate(request['benchmark_columns']):
            role='ink' if column<2 else 'A2'
            if column in (1,3):visit(role,'same_color_reload');m.distance=0
            if column==2:
                for _ in range(p.data['stations']['water']['wash_cycles']):visit('water','wash')
                m.loaded='water';m.distance=0
                if request['include_cloth']:visit('sponge','absorbent_contact')
                visit('A2','pigment_load');m.loaded='A2'
            for index,line in enumerate(part['brush_lines']):
                _draw(b,p,line,f'{role}-column-{column+1}-stroke-{index+1}')
                m.distance+=dist(line['start_xy'],line['end_xy'])
    b.park(m.station_travel_state());b.marker('job_complete','Review only; no physical evidence or authorization')
    return plan,b.commands


def elevated_air(commands,p):
    """Project the SAME station/paper IR, not a second independently drawn tour."""
    result=[]
    for c in commands:
        if c.kind=='move':
            # Station operations carry station_handling; transfers already Z35.
            height=35 if c.time_category=='station_handling' else max(15,c.xyz[2])
            c=replace(c,xyz=(*c.xyz[:2],height))
        result.append(c)
    if xy_route(result)!=xy_route(commands):raise ValueError('matched Air XY route changed')
    return result


def verify_numeric(text,commands,p,kind,count):
    if not text.startswith(BANNER):raise ValueError('missing review-only identity')
    rows=[r for r in text.splitlines() if r and not r.startswith(';')]
    expected=[c for c in commands if c.kind!='marker']
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or len(rows)!=len(expected)+2:
        raise ValueError('numeric command coverage/modal/M2 mismatch')
    pos=tuple(p.data['machine']['start_work_xyz']);visits=[];states={};max_rates=[0.,0.,0.];wipe=[];draw=[];returns=[]
    for row,c in zip(rows[1:-1],expected):
        if c.kind=='move':
            match=_MOVE.fullmatch(row)
            if not match:raise ValueError('unsupported numeric move')
            x,y,z,f=map(float,match.groups());target=(x,y,z)
            if any(abs(a-b)>5.1e-10 for a,b in zip((x,y,z,f),(*c.xyz,c.feed_mm_min))):raise ValueError('numeric trajectory read-back mismatch')
            check_move(pos,target,f,c.action,p,kind)
            length=dist(pos,target)
            if length:
                for i in range(3):max_rates[i]=max(max_rates[i],abs(target[i]-pos[i])/length*f)
            if c.action=='travel':states.setdefault(c.travel_state,set()).add(f)
            if c.travel_state=='partially_depleted' and c.travel_phase=='main' and length:returns.append(f)
            if c.travel_phase=='shallow_wipe':wipe.append(dict(start=list(pos),end=list(target),feed=f))
            if c.action=='draw':draw.append(dict(source=c.source_id,start=list(pos),end=list(target),feed=f))
            # Every station transfer must be purely XY at global35, or vertical.
            if c.time_category=='station_transfer' and pos[:2]!=target[:2] and (pos[2]!=35 or z!=35):
                raise ValueError('station lateral transfer below Z35')
            pos=target
        elif c.kind=='dwell':
            match=_DWELL.fullmatch(row)
            if not match or abs(float(match.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell read-back mismatch')
        else:raise ValueError('M0/unresolved action forbidden')
    arrivals=[]
    for i,c in enumerate(commands):
        if c.kind=='marker' and c.action=='benchmark_station_visit':visits.append(c.message)
        if c.kind=='move' and c.action=='station_approach':
            previous=next(row for row in reversed(commands[:i]) if row.kind=='move')
            if previous.xyz!=(*c.xyz[:2],35) or previous.action!='travel' or previous.feed_mm_min>3000:
                raise ValueError('station descent must follow capped XY arrival at global35')
            # Locate the exact preceding move rather than assuming marker-free IR.
            previous_index=max(j for j in range(i) if commands[j].kind=='move')
            prior=next((row.xyz for row in reversed(commands[:previous_index]) if row.kind=='move'),tuple(p.data['machine']['start_work_xyz']))
            arrivals.append(dict(from_xyz=list(prior),to_xyz=list(previous.xyz),length_mm=dist(prior,previous.xyz),feed_mm_min=previous.feed_mm_min))
    expected_visits=(['ink:pigment_load','ink:same_color_reload','water:wash','sponge:absorbent_contact','A2:pigment_load','A2:same_color_reload']
                     if count==40 else ['ink:pigment_load','ink:same_color_reload'])
    if visits!=expected_visits:raise ValueError('station visit sequence mismatch')
    if len(draw)!=count or pos!=(800,800,35):raise ValueError('source stroke count/park mismatch')
    if not returns or set(returns)!={15000}:raise ValueError('actual F15000 partially-depleted return missing')
    if kind=='paint':
        for w in wipe:
            if not (w['start'][2]==w['end'][2]==7.5 and w['end'][1]-w['start'][1]==20):raise ValueError('pressed wipe changed')
    result=dict(readback_verified=True,controller_axis_feed_caps=p.data['machine']['axis_max_rate_mm_min'],
        maximum_projected_axis_feeds=max_rates,complete_axis_segment_bounds_checked=True,
        physical_swept_clearance_verified=False,physical_high_speed_pass=False,authorized=False,
        expected_start=[0,898,35],end=list(pos),stroke_count=count,M0_count=0,M2=True,
        station_visits=visits,feeds_by_travel_state={s:sorted(v) for s,v in states.items()},
        F15000_partially_depleted_main_segments=len(returns),pressed_wipes=wipe,
        stroke_paths=draw,trajectory_sha256=digest([asdict(c) for c in commands]),
        station_arrival_cap_and_vertical_descent_verified=True,
        station_arrivals=arrivals,
        station_feeds_by_phase={phase:sorted({c.feed_mm_min for c in commands if c.kind=='move' and c.travel_phase==phase})
            for phase in p.data['motion']['station_phase_limits_mm_min']})
    if count==40 and kind=='paint':
        existing=job_check(text,commands,p,kind,{'candidate_sha256':p.data['machine']['target_config_sha256']})
        result['shared_two_pass_wipe_lift_reentry_purge_palette_checks']=existing
    return result


def approach_comparison(root):
    rows=[]
    for edge in (30,35,40):
        p=candidate_profile(root,approach_mm=edge);_,commands=build_benchmark(root,p)
        blocks=prepare_timing(commands,p);m=deepcopy(p.data['machine']);m['junction_deviation_mm']=.01
        t=estimate_prepared(blocks,m)
        lengths=[];pos=p.data['machine']['start_work_xyz']
        for c in commands:
            if c.kind=='move':
                if c.action=='travel' and c.travel_phase=='arrival' and c.time_category=='station_transfer':lengths.append(dist(pos,c.xyz))
                pos=c.xyz
        rows.append(dict(requested_station_arrival_mm=edge,actual_40stroke_station_arrival_lengths=lengths,
            modeled_seconds=t['acceleration_sensitive_seconds'],commanded_seconds=t['commanded_feed_seconds']))
    return dict(ideal_15000_to3000_mm=20.,ideal_12000_to3000_mm=12.5,
        XY_acceleration_mm_s2=1500,chosen_station_arrival_mm=APPROACH_MM,variants=rows,
        physically_verified=False,
        interpretation='35mm is a feed-capped final straight XY zone at Z35, not a guarantee of safe braking. Deceleration to its F3000 cap begins upstream under lookahead; the final XY-to-Z corner constrains speed again. Short paths shrink edge zones and omit the high-speed middle. Finite buffer, feed override, tool/wet dynamics and continuous UGS TCP streaming still need a trial.',
        primary_firmware_source='https://github.com/bdring/FluidNC/blob/v4.1.1/FluidNC/src/Planner.cpp',
        primary_firmware_blob_sha='eb0b1b81953feece3d3888941b623784aba368b4',
        junction_deviation_mm_assumed=.01)


def spring_runtime(root,machine,provenance):
    baseline=Profile.load(root/PROFILE_PATH)
    strokes,_=load_bound_spring(machine,provenance)
    order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    jobs,manifest=make_plan(strokes,Layout('D'),order,palette_order=baseline.data['material']['color_order'])
    if digest(manifest)!=PLAN_SHA:raise ValueError('canonical Spring plan changed')
    report=dict(plan_sha256=PLAN_SHA,source_readback=verify_plan(manifest,strokes,Layout('D')),
        pressure_curve_unchanged=True,stone_lip_stripping_included=False,physical_runtime_verified=False,
        junction_deviation_mm=.01,junction_status='ASSUMED, not controller read-back',scenarios={})
    for name,p in [('A_PR31_Z8',baseline),('B_HIGH_WET12000',candidate_profile(root)),('C_HIGH_WET15000',candidate_profile(root,15000))]:
        result={}
        for job,units in jobs.items():
            b=RuntimeBuilder(p);commands,metrics=build_job(p,units,'painting',offline_builder=b,offline_material=RuntimeMaterials(b))
            lineage=verify_draw_lineage(commands,manifest['jobs'][job],p,'painting')
            complete=None;pending=None;normal_links=0
            for i,c in enumerate(commands):
                if c.action=='source_begin' and complete is not None:pending=complete
                if c.artistic_pressure is not None and pending is not None:
                    link=commands[pending+1:i]
                    if not any(row.action.startswith('station_') for row in link):
                        if any(row.kind=='move' and row.xyz[2]>15+1e-9 for row in link):raise ValueError('unexpected Z35 paper link')
                        normal_links+=1
                    pending=None
                if c.action=='source_complete':complete=i
            blocks=prepare_timing(commands,p)
            # Exclusive extra category: do not double-count depleted travel in transfer.
            blocks=[(*block[:3],'partially_depleted_return',*block[4:]) if block[4]=='travel' and block[5]=='partially_depleted' else block for block in blocks]
            models={}
            for label,axes in [('configuration_reference',p.data['machine']['axis_acceleration_mm_s2']),('synthetic_low',[100,100,100])]:
                m=deepcopy(p.data['machine']);m.update(junction_deviation_mm=.01,axis_acceleration_mm_s2=axes)
                models[label]=estimate_prepared(blocks,m)
            result[job]=dict(models=models,profile_sha256=p.sha256,source_units=len(units),lineage=lineage,
                loads_per_slot=metrics['loads_per_slot'],M0_count=metrics['M0_count'],end=list(b.position),
                trajectory_sha256=digest([asdict(c) for c in commands]),normal_paper_links_without_Z35=normal_links,
                ink_reload_mm=p.data['material']['ink_reload_mm'],color_reload_mm=p.data['material']['color_reload_mm'])
            print(name,job,round(models['configuration_reference']['commanded_feed_seconds']/60,2),'commanded min',flush=True)
        report['scenarios'][name]=result
    return report


def export(root,output,machine=None,provenance=None):
    yaml_bytes,diff,controller=controller_candidate(root);baseline_request=baseline_inputs(root)[0]
    def write(out):
        (out/'config.X860.high_speed.candidate.yaml').write_bytes(yaml_bytes)
        (out/'config.X860.high_speed.diff').write_text(diff);save_json(out/'controller.json',controller)
        save_json(out/'baseline_40.plan.json',baseline_request);save_json(out/'endurance.plan.json',endurance_plan())
        save_json(out/'profile.baseline_z8.snapshot.json',Profile.load(root/PROFILE_PATH).data)
        report=dict(schema='datascape.high_speed_review.v01',base_commit=PIN,status=STATUS,authorized=False,
            prior_800mm_operator_report_not1200_validation=True,stone_lip_enabled=False,
            profiles={},jobs={},station_approach_comparison=approach_comparison(root))
        for wet in (12000,15000):
            p=candidate_profile(root,wet);save_json(out/f'profile.high_wet{wet}.json',p.data)
            report['profiles'][str(wet)]=p.sha256
            plan,paint=build_benchmark(root,p);air=elevated_air(paint,p)
            for kind,commands,fill in [('AIR',air,'NO MATERIAL CONTACT'),('WATER_ONLY',paint,'WATER WELL_2/A2; CLEAN WATER WELL_1'),('INK_GOUACHE',paint,'INK WELL_2; GOUACHE A2; CLEAN WATER WELL_1')]:
                name=f'BENCHMARK_330_HIGH_WET{wet}_{kind}_REVIEW'
                text=BANNER+'; HIGH-SPEED YAML NOT INSTALLED/READ BACK; NEW DYNAMICS NOT PHYSICALLY PASSED\n; '+fill+'\n'+_serialize(commands,p,digest(plan),name,'offline_review')
                (out/(name+'.gcode')).write_text(text)
                check=verify_numeric((out/(name+'.gcode')).read_text(),commands,p,'air' if kind=='AIR' else 'paint',40)
                save_json(out/(name+'.readback.json'),check);report['jobs'][name]=check
            if wet==12000:
                plan,paint=build_benchmark(root,p,endurance=True);air=elevated_air(paint,p)
                for kind,commands in [('AIR',air),('INK',paint)]:
                    name=f'INK_ENDURANCE_1200_{kind}_REVIEW'
                    text=BANNER+'; 18x80mm; RELOAD AFTER15 COMPLETE STROKES / BEFORE16; CONSTANT Z-2 CONTACT CANDIDATE\n'+_serialize(commands,p,digest(plan),name,'offline_review')
                    (out/(name+'.gcode')).write_text(text)
                    check=verify_numeric((out/(name+'.gcode')).read_text(),commands,p,'air' if kind=='AIR' else 'paint',18)
                    check['reload_before_strokes']=[int(c.message) for c in commands if c.action=='endurance_reload_boundary']
                    if check['reload_before_strokes']!=[16]:raise ValueError('endurance must exercise1200mm boundary then real reload')
                    save_json(out/(name+'.readback.json'),check);report['jobs'][name]=check
        if machine and provenance:
            runtime=spring_runtime(root,machine,provenance);save_json(out/'spring_runtime.json',runtime)
            runtime_markdown(out,runtime)
        save_json(out/'verification.json',report);(out/'README.md').write_text(README)
        return report
    return _atomic_output(output,write)


def runtime_markdown(out,report):
    rows=['# Canonical Spring offline runtime (minutes)',
        '', 'Same Z-8 response, XY, accepted pressure and S3a in every scenario. Future lip contact excluded. JD0.01 is ASSUMED; no time is physically verified.', '',
        '| Scenario/job | Commanded | Config acceleration | Synthetic100 acceleration | Ink load count |',
        '|---|---:|---:|---:|---:|']
    detail=['', '## Exclusive commanded-motion categories (minutes)', '',
        '| Scenario/job | Drawing | Paper engagement | Other travel | Other station transfers | Used-brush return | Station handling |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,jobs in report['scenarios'].items():
        for job,r in sorted(jobs.items()):
            m=r['models']['configuration_reference'];low=r['models']['synthetic_low']
            rows.append(f"| {name}/{job} | {m['commanded_feed_seconds']/60:.2f} | {m['acceleration_sensitive_seconds']/60:.2f} | {low['acceleration_sensitive_seconds']/60:.2f} | {r['loads_per_slot'].get('ink','—')} |")
            cats=m['commanded_feed_seconds_by_category']
            detail.append('| '+name+'/'+job+' | '+' | '.join(f'{cats.get(k,0)/60:.2f}' for k in
                ('drawing','paper_engagement','non_drawing_travel','station_transfer','partially_depleted_return','station_handling'))+' |')
    (out/'RUNTIME.md').write_text('\n'.join(rows+detail)+'''

Configuration-reference: baseline XY1200/Z1000, high-speed XY1500/Z1000mm/s²;
all rates come from their respective YAML/profile. Synthetic low:100 on all
axes for all scenarios. Both use projected axes, actual XYZ/junction geometry,
reverse braking/forward acceleration and the same assumedJD0.01. Adequate full
lookahead is assumed; finite buffer/TCP/step overhead is not established. Global
XY acceleration also affects drawing/station motions; slow contact feeds do not
constitute a separate hardware acceleration limit. Initial wet12000 is preferred:
wet15000 has modest modeled benefit and requires its own wet-motion trial.
''')


def verify_package(root,output):
    """Read hashes, regenerate all numeric files and compare real motion exactly."""
    out=Path(output);manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(manifest)!={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}:raise ValueError('manifest coverage mismatch')
    for name,h in manifest.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=h:raise ValueError('artifact SHA256 mismatch: '+name)
    if (out/'config.X860.high_speed.candidate.yaml').read_bytes()!=controller_candidate(root)[0]:raise ValueError('YAML regeneration mismatch')
    count=0
    for wet in (12000,15000):
        p=candidate_profile(root,wet)
        if Profile.load(out/f'profile.high_wet{wet}.json').sha256!=p.sha256:raise ValueError('profile regeneration mismatch')
        plan,paint=build_benchmark(root,p);air=elevated_air(paint,p)
        variants=[(f'BENCHMARK_330_HIGH_WET{wet}_{kind}_REVIEW',plan,rows,'air' if kind=='AIR' else 'paint',40)
            for kind,rows in [('AIR',air),('WATER_ONLY',paint),('INK_GOUACHE',paint)]]
        if wet==12000:
            ep,pc=build_benchmark(root,p,True);ac=elevated_air(pc,p)
            variants += [(f'INK_ENDURANCE_1200_{kind}_REVIEW',ep,rows,'air' if kind=='AIR' else 'paint',18) for kind,rows in [('AIR',ac),('INK',pc)]]
        for name,plan,rows,kind,strokes in variants:
            text=(out/(name+'.gcode')).read_text();serialized=_serialize(rows,p,digest(plan),name,'offline_review')
            if text[text.index('; DATASCAPE'): ]!=serialized:raise ValueError('numeric regeneration mismatch: '+name)
            actual=verify_numeric(text,rows,p,kind,strokes)
            saved=json.loads((out/(name+'.readback.json')).read_text())
            if strokes==18:actual['reload_before_strokes']=[int(c.message) for c in rows if c.action=='endurance_reload_boundary']
            if actual!=saved:raise ValueError('read-back regeneration mismatch: '+name)
            count+=1
    return dict(regenerated_numeric_Gcode_files=count,all_SHA256_verified=True,authorized=False,physical_pass=False)


README='''# High-speed commissioning candidate (PR31)

Numeric G1/G4/M2 offline REVIEW programs, not machine-authorized exports. No
configuration is installed and no new physical safety evidence is created.
The existing40-stroke baseline, Spring v13/F2-C, Pressure Intent/S3a,12 colors
and explicit Z-8 response remain unchanged. No final Spring G-code is exported.

The complete YAML differs from the prior X860 candidate at exactly four scalars:
XY rates15000->20000, XY accelerations1200->1500. X860 and all Z/homing/direction/
motor/pin/step/pull-off/controller settings stay byte-identical. Historical YAML
comments remain archival; consult the exact diff/controller record for intent.

Profile: dry15000, wet12000 (separate15000 variant), used-brush return15000,
draw6000, noncontactZ7000, pressure/contact/release2000, paper15/localoff,
station35, start0/898/35, park800/800/35/M2, ink1200/color800. Z-8 is Spring-only;
the40 explicit constant-Z trials still reach-10. Stations retain two pressed
20mm Y+ passes at7.5, reentry17.5 before X-10, purge1.5/dwell4s and palette5/
radius5. Ink2s/water5s. Agitation X±10 at1500; other contact feeds unchanged.

The SAME40 XY/depth/source/order plan has two separate wet-speed sets. Each has
matched AIR (station motion elevated35/paper15), WATER_ONLY and INK_GOUACHE.
Water/pigment numeric commands are identical; change the contents manually.
The scheduled reload after each10-line450mm column is preserved for baseline
comparison and is not evidence of1200mm endurance. Independent endurance uses
15x80mm at constantZ-2 (1200mm), actual automatic ink reload before line16, then
three80mm comparison marks in a separate column (1440mm total). Reported prior
ten80mm marks establish only~800mm, not success at1200mm. Previous ink1000
profile is preserved; color threshold stays800. No canonical stroke is split.

Station access is vertical to35, segmented straight XY, then vertical descent.
Final35mm XY is capped3000. Used-brush departure also35mm/3000. Wet-paper edges
retain5mm/3000, wet station arrival35mm/3000. Short paths shrink edge zones and
omit high-feed main; commands do not force attained speed. A15000->3000 ramp
at1500mm/s² needs20mm ideally. That deceleration begins BEFORE the final capped
zone; a35mm zone is not a physical safety certificate. Actual corner angles,
projected axis acceleration, forward/backward planning and dwell stops enter
the offline model. Adequate lookahead/streaming and assumedJD0.01 are explicit;
finite planner buffer, step rounding, TCP timing, feed override and wet dynamics
are not measured.30/35/40mm actual-route comparisons are recorded. FluidNC4.1.1
Planner.cpp source blob eb0b1b81953feece3d3888941b623784aba368b4 was inspected.

Both wells have separate disabled lip_stripping fields: measured_contact_xyz,
contact_feed_mm_min, relative_x_mm=-20 and safe_retract_z. Missing values stay
null. Enabling fails before any station motion; no lip contact implementation
or invented location is present. Future X-20 means measured contact X minus20,
never absolute machine X=-20. Future one-wipe/lip sequence is NOT active here.

Spring runtime uses the same Z-8 source/plan for A baseline1000-ink, B new1200,
C wet15000. Commanded feed, configuration-reference acceleration and synthetic
100mm/s² comparisons share assumedJD0.01. Categories are exclusive, with used-
brush return separated from other station transfers. Future lip time excluded;
physical times/attained feeds and new brush response are not claimed verified.

Reproduce (existing recovered bound inputs, no artwork regeneration):
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.high_speed --output NEW_DIR
Add --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json
for the complete canonical Spring runtime comparison. Existing formal physical
profile, clearance, installed-config, stopping/evidence and authorization gates
remain intact. Review filenames are intentionally not authorized Spring jobs.
'''


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--machine',type=Path);ap.add_argument('--provenance',type=Path)
    args=ap.parse_args();root=Path(__file__).resolve().parents[2]
    if args.verify:print(json.dumps(verify_package(root,args.output)))
    else:export(root,args.output,args.machine,args.provenance)
