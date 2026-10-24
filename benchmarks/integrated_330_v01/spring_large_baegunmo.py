"""Canonical Spring integration after the large-Baegunmo physical benchmark.

Full numeric offline reviews, not machine-authorized exports. No artwork or
pressure generation, controller I/O or manufactured physical safety evidence.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
from math import dist
from pathlib import Path
import gzip
import hashlib
import json

from datascape.gcode.binding import digest, load_bound_spring
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import reference_order, make_plan, verify_plan
from datascape.gcode.production.trajectory import build_job
from datascape.gcode.production.exporter import _atomic_output, _serialize, _MOVE, _DWELL, save_json, verify_draw_lineage
from datascape.gcode.production.timing import prepare_timing, estimate_prepared
from .paper_reference_1500 import profile as prior_profile
from .spring_runtime import RuntimeBuilder, RuntimeMaterials
from .spring_z8_preview import PLAN_SHA, reference_z, stats, load_visual_records, visual_arrays, draw_image, ROIS
from .numeric_review import BANNER, STATUS, check_move
from .final_lip import yaml_candidate

PIN='e5e11ff4aa91eebc46eab44172b0da13ee03fd9c'
COMPRESSION_KNOTS=((0.,0.),(.2,1.),(.4,3.5),(.6,5.8),(.8,8.2),(.93,10.2),(1.,12.))
RELATIVE_KNOTS=tuple((p,-c) for p,c in COMPRESSION_KNOTS)
PAPER_ACTIONS={'paper_hover','approach','initial_contact','pressure_variation','draw','release','paper_release_clearance','retract'}


def profile(root,ink_reload=1500,color_reload=1000):
    if (ink_reload,color_reload) not in ((1500,1000),(2000,1000),(1100,700)):
        raise ValueError('select historical1500/1000, optional2000/1000, or revised1100/700')
    d=deepcopy(prior_profile(root).data);d['profile_id']=f'SPRING-LARGE-BAEGUNMO-TOUCH10-HOVER20-INK{ink_reload}-COLOR{color_reload}-REVIEW'
    d['motion'].update(paper_hover_mm=20,paper_approach_mm=15,paper_hover_clearance_mm=10,
        paper_approach_clearance_mm=5,paper_contact_z_range=[-2,10])
    d['material'].update(ink_reload_mm=ink_reload,color_reload_mm=color_reload,spring_pressure_response_selected=True,
        spring_pressure_response_status='operator-selected physical compression CANDIDATE; not calibrated width or machine authorization')
    for medium,b in d['brush_profiles'].items():
        b.update(paper_first_touch_z_mm=10,brush_type='large_baegunmo',family='baegunmo',
            knots=[list(k) for k in RELATIVE_KNOTS],status='unverified',observations=[],
            notes='Large Baegunmo operator-selected; first-touch10 and1..15mm benchmark reported completed. Numeric widths not measured. New user-specified0..12mm response CANDIDATE, actual Spring pressure<=.93 maps<=10.2mm. Ink/color remain independent. Splitting begins around12mm per operator; no full Spring/width/dynamics authorization inferred.')
    d['machine']['Y900_operation_operator_reported_working']=True
    d['notes']='Post-physical-benchmark Spring review: paper touch10 + relative hover10=absolute20, approach+5=15; stations/global35/Y900/G54 unchanged. Ink1500 default/optional2000,color1000. Accepted artwork/Pressure Intent/S3a frozen. Physical qualitative observations are separate from numeric width calibration, measured-profile evidence and machine authorization.'
    if (ink_reload,color_reload)==(1100,700):
        d['notes']=d['notes'].replace('Ink1500 default/optional2000,color1000.','Selected ink1100,color700; historical1500/1000 and optional2000/1000 preserved separately.')
    return Profile.from_dict(d)


def observations(root):
    base=root/'benchmarks/integrated_330_v01/review_paper_reference_1500'
    files=['benchmark1500.plan.json','INK_1500_PAPER_Z10_COMP1_15_INK_REVIEW.gcode','verification.json','MANIFEST_SHA256.json']
    return dict(schema='datascape.large_baegunmo_operator_observations.v01',reported_on='2026-10-24',
        source='operator message: Final Large Baegunmo Calibration and Spring Integration',
        brush='large Baegunmo',paper_first_touch_G54_Z=10,physical_compression_tested_mm=[1,15],
        prior_excess_width_cause_operator_reported='incorrect paper Z reference, not simply large brush size',
        clear_width_differences_visible=True,numerically_measured_stroke_widths_mm=None,
        brush_splitting_onset_compression_mm_approx=12,ink_delivery_mm_reported_workable=1500,
        ink_fading='gradual fading toward the end',lip_stripping='operator reports working correctly',
        washing_and_recovery='operator reports working correctly',Y900_configuration='operator reports working correctly',
        benchmark_completed_operator_reported=True,reference_program_hashes={f:hashlib.sha256((base/f).read_bytes()).hexdigest() for f in files},
        operator_streamed_file_hash_or_controller_yaml_readback_supplied=False,
        scope='Qualitative physical observations linked to the intended preserved benchmark; not an asserted streamed-byte/hash match, exact widths, all-Spring swept-clearance certificate, measured knot widths or formal stage authorization.')


def load_scene(root,machine,provenance):
    strokes,_=load_bound_spring(machine,provenance)
    order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    jobs,manifest=make_plan(strokes,Layout('D'),order,palette_order=profile(root).data['material']['color_order'])
    if digest(manifest)!=PLAN_SHA:raise ValueError('canonical Spring plan changed')
    preserved=verify_plan(manifest,strokes,Layout('D'))
    if preserved['D_original_strokes_unsplit']!=14951 or preserved['written_pressure_samples']!=240974 or preserved['D_X300_crossing_strokes_continuous']!=50:raise ValueError('canonical coverage changed')
    return strokes,order,jobs,manifest,preserved


def project_air(commands,p,source_brush):
    result=[];hover=p.data['motion']['paper_hover_mm']
    for c in commands:
        if c.action=='source_begin':
            medium,slot=source_brush[c.source_id];hover=p.paper_heights_for(medium,slot)[1]
        if c.kind=='move':
            h=p.data['motion']['station_clearance_mm'] if c.time_category=='station_handling' else max(hover,c.xyz[2])
            c=replace(c,xyz=(*c.xyz[:2],h))
        result.append(c)
    return result


def build(p,units):
    b=RuntimeBuilder(p)
    commands,metrics=build_job(p,units,'painting',offline_builder=b,offline_material=RuntimeMaterials(b))
    return commands,metrics


def numeric_text(commands,p,name):
    return BANNER+'; FULL CANONICAL SPRING / LARGE BAEGUNMO / NO MACHINE AUTHORIZATION\n'+_serialize(commands,p,PLAN_SHA,name,'offline_review')


def readback(text,commands,p,plan_units,air=False):
    """Independent numeric parser, lineage, contact-plane and material audit."""
    if not text.startswith(BANNER):raise ValueError('review identity missing')
    rows=[r for r in text.splitlines() if r and not r.startswith(';')]
    expected=[c for c in commands if c.kind!='marker']
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or len(rows)!=len(expected)+2:raise ValueError('modal/M2/command coverage mismatch')
    lineage=verify_draw_lineage(commands,plan_units,p,'air' if air else 'painting')
    source_brush={f['stroke']['source_id']:(f['stroke']['medium'],f['stroke']['color_slot']) for u in plan_units for f in u['fragments']}
    pos=tuple(p.data['machine']['start_work_xyz']);rates=[0.,0.,0.];bounds=[list(pos),list(pos)]
    source_order=[];touch,hover,approach=p.paper_heights_for('ink','INK');paper_z=[];pressure=[]
    links=0;after_source=False;service=False;source_active=False;services=[];used_feeds=set();wipes=0;lips=0;hash_ir=hashlib.sha256()
    # Check complete source-to-source links, including lifts before XY travel.
    complete=None;pending=None;normal_links=0
    for i,c in enumerate(commands):
        if c.action=='source_begin' and complete is not None:pending=complete
        if c.artistic_pressure is not None and pending is not None:
            link=commands[pending+1:i]
            if not any(r.time_category=='station_handling' for r in link):
                _,h,_=p.paper_heights_for(*source_brush[c.source_id])
                if any(r.kind=='move' and r.xyz[2]>h+1e-8 for r in link):raise ValueError('unintended Z35 between normal paper strokes')
                normal_links+=1
            pending=None
        if c.action=='source_complete':complete=i
    row_iter=iter(rows[1:-1])
    for c in commands:
        hash_ir.update(json.dumps(asdict(c),sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
        if c.kind=='marker':
            if c.action=='source_begin':
                source_order.append(c.source_id);source_active=True
                touch,hover,approach=p.paper_heights_for(*source_brush[c.source_id])
                if after_source and not service:links+=1
                after_source=False;service=False
            elif c.action=='source_complete':source_active=False;after_source=True;service=False
            if c.action in ('pigment_load','same_color_reload','wash','absorbent_contact','controlled_rewet'):
                services.append(dict(action=c.action,station=c.message))
            continue
        row=next(row_iter)
        if c.kind=='move':
            m=_MOVE.fullmatch(row)
            if not m:raise ValueError('unapproved motion command')
            x,y,z,f=map(float,m.groups());target=(x,y,z)
            if any(abs(a-b)>5.1e-10 for a,b in zip((x,y,z,f),(*c.xyz,c.feed_mm_min))):raise ValueError('numeric move differs from IR')
            check_move(pos,target,f,c.action,p,'air' if air else 'paint',exact_benchmark_draw=False)
            length=dist(pos,target);zrate=0 if not length else abs(z-pos[2])/length*f
            if length:
                for i in range(3):rates[i]=max(rates[i],abs(target[i]-pos[i])/length*f)
            for i,v in enumerate(target):bounds[0][i]=min(bounds[0][i],v);bounds[1][i]=max(bounds[1][i],v)
            if c.time_category=='station_handling':
                service=True
                if air and z!=35:raise ValueError('Air station contact')
            if c.time_category=='station_transfer' and pos[:2]!=target[:2] and (pos[2]!=35 or z!=35):raise ValueError('station transfer below35')
            if c.action=='travel' and pos[:2]!=target[:2]:
                if abs(pos[2]-z)>1e-8 or not (abs(z-hover)<1e-8 or z==35):raise ValueError('lateral paper travel at wrong absolute hover')
                if c.travel_state=='partially_depleted' and c.travel_phase in ('departure','main'):used_feeds.add(f)
            if c.action in PAPER_ACTIONS:
                if air:
                    if min(pos[2],z)<hover-1e-8:raise ValueError('Air paper motion below derived hover')
                else:
                    if c.action in ('paper_hover','retract') and min(pos[2],z)<approach-1e-8:raise ValueError('fast paper movement below approach boundary')
                    if c.action in ('paper_hover','retract') and z!=hover:raise ValueError('wrong absolute paper hover')
                    if c.action=='approach' and z!=approach:raise ValueError('wrong approach boundary')
                    if c.action=='paper_release_clearance' and z!=approach:raise ValueError('wrong controlled release boundary')
                    if c.action in ('initial_contact','release') and z!=touch:raise ValueError('wrong paper first-touch/release')
                    if c.action in ('initial_contact','pressure_variation','release','paper_release_clearance') and zrate>2000+1e-6:raise ValueError('controlled paper Z exceeds2000')
                    if z!=pos[2] and min(pos[2],z)<=touch+1e-8 and zrate>2000+1e-6:raise ValueError('high-speed motion through paper contact')
                if c.artistic_pressure is not None:
                    paper_z.append(z);pressure.append(c.artistic_pressure)
                    if not air:
                        compression=-reference_z(c.artistic_pressure,RELATIVE_KNOTS)
                        if abs((touch-z)-compression)>1e-8:raise ValueError('compression interpolation/absolute conversion mismatch')
            if source_active and c.action in PAPER_ACTIONS and c.action!='paper_hover' and z>hover+1e-8:raise ValueError('unexpected global35 inside source stroke')
            if c.travel_phase=='shallow_wipe':wipes+=1
            if c.travel_phase=='lip_strip':
                lips+=1
                if f!=1500 or x!=795 or y not in (458,298) or z!=(35 if air else 20):raise ValueError('accepted lip routine changed')
            pos=target
        elif c.kind=='dwell':
            m=_DWELL.fullmatch(row)
            if not m or abs(float(m.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell mismatch')
        else:raise ValueError('M0/unresolved command forbidden')
    ids=[u['source_id'] if 'source_id' in u else u['fragments'][0]['stroke']['source_id'] for u in plan_units]
    if source_order!=ids or len(source_order)!=len(set(source_order)):raise ValueError('unsplit source order changed')
    if pos!=(800,800,35):raise ValueError('final park mismatch')
    if any(c.kind=='pause' for c in commands):raise ValueError('routine M0')
    return dict(numeric_readback_verified=True,source_strokes=len(source_order),source_order_sha256=digest(source_order),
        **lineage,profile_sha256=p.sha256,canonical_plan_sha256=PLAN_SHA,
        start_work_xyz=p.data['machine']['start_work_xyz'],end_work_xyz=list(pos),G54_offset_xyz=p.data['machine']['g54_to_machine_xyz'],
        actual_axis_reference_bounds=bounds,candidate_machine_bounds=p.data['machine']['machine_bounds_xyz'],
        maximum_projected_axis_feeds=rates,controller_axis_caps=p.data['machine']['axis_max_rate_mm_min'],
        paper_first_touch_Z=10,paper_hover_Z=20,paper_hover_clearance_mm=10,paper_approach_Z=15,
        paper_sample_Z=stats(paper_z),artistic_pressure=stats(pressure),
        normal_paper_links_checked=normal_links,no_artificial_X300_split=True,material_operations=services,
        shallow_wipe_moves=wipes,lip_strips=lips,used_return_departure_main_feeds=sorted(used_feeds),
        M0_count=0,M2_verified=True,axis_bounds_and_feeds_verified=True,high_speed_paper_plane_crossings=0,
        trajectory_sha256=hash_ir.hexdigest(),trajectory_hash_contract='sorted canonical command JSON plus LF per command',
        physical_full_scene_clearance_verified=False,machine_authorized=False,air_projection=air)


def runtime(commands,p):
    blocks=prepare_timing(commands,p);models={}
    reference=p.data['machine']['axis_acceleration_mm_s2']
    for name,accel in [('configuration_reference',reference),('synthetic_low',[100,100,100])]:
        m=deepcopy(p.data['machine']);m.update(axis_acceleration_mm_s2=accel,junction_deviation_mm=.01)
        models[name]=estimate_prepared(blocks,m)
    return dict(models=models,axis_accelerations_mm_s2=dict(configuration_reference=reference,synthetic_low=[100,100,100]),
        junction_deviation_mm=.01,junction_status='ASSUMED, not read back',
        lip_stripping_and_all_station_handling_included=True,physical_runtime_verified=False)


def pressure_summary(strokes,p):
    values=defaultdict(lambda:[[],[],[]])
    for s in strokes:
        b=p.brush_for(s.medium,s.color_slot)
        for pt in s.points:
            compression=-reference_z(pt.pressure,RELATIVE_KNOTS)
            if abs(b.work_z_for(pt.pressure)-(10-compression))>1e-10:raise ValueError('pressure knot interpolation')
            for group in ('all',s.medium,s.medium+'/'+s.layer):
                v=values[group];v[0].append(pt.pressure);v[1].append(compression);v[2].append(10-compression)
    return {name:dict(pressure=stats(v[0]),compression_mm=stats(v[1]),absolute_paper_Z=stats(v[2])) for name,v in values.items()}


def visual_preview(out,strokes,order,p,rich,sidecar):
    import numpy as np
    from matplotlib import colormaps
    records,palette=load_visual_records(rich,strokes,Path(rich)/'palette.json',sidecar)
    arrays=visual_arrays(strokes,records,palette,order,p)
    draw_image(out/'Spring_complete_canonical.png',arrays,style='canonical',px_per_mm=3)
    draw_image(out/'Spring_complete_compression_proxy.png',arrays,style='proxy',px_per_mm=3)
    draw_image(out/'Spring_ink_compression_proxy.png',arrays,mode='ink',style='proxy',px_per_mm=3)
    depth=deepcopy(arrays);depth['rgba']=colormaps['viridis'](np.clip(arrays['depth']/12,0,1));depth['width']=np.maximum(arrays['width'],.55)
    draw_image(out/'Spring_physical_compression.png',depth,style='canonical',px_per_mm=3)
    for name,roi in ROIS.items():draw_image(out/f'Spring_crop_{name}.png',arrays,style='proxy',roi=roi,px_per_mm=5)
    # Family summaries use the actual accepted sidecar, not invented classifications.
    families=defaultdict(list)
    for s,r in zip(strokes,records):
        b=p.brush_for(s.medium,s.color_slot)
        families[s.medium+'/'+r['_family']].extend(-b.z_for(pt.pressure) for pt in s.points)
    save_json(out/'family_compression.json',{k:stats(v) for k,v in sorted(families.items())})
    import matplotlib.pyplot as plt
    k=np.array(COMPRESSION_KNOTS);fig,ax=plt.subplots(figsize=(7,4),constrained_layout=True)
    ax.plot(k[:,0],k[:,1],'-o',label='Operator-selected candidate');ax.axhline(12,color='#a34d32',ls='--',label='Splitting begins ~12mm (qualitative)')
    ax.axvline(.93,color='#557777',ls=':',label='Spring maximum accepted pressure .93')
    ax.set(xlabel='Unchanged artistic pressure',ylabel='Physical compression (mm)',xlim=(0,1),ylim=(0,13));ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(out/'Pressure_compression_curve.png',dpi=140);plt.close(fig)
    (out/'Spring_review.html').write_text('''<!doctype html><meta charset="utf-8"><title>Spring / large Baegunmo</title>
<style>body{font:16px system-ui;max-width:1250px;margin:auto;padding:24px;background:#f4f3f0;color:#243238}img{max-width:100%;background:white}button{font:inherit;padding:8px;margin:5px}#scene{max-width:800px;display:block;margin:auto}p{line-height:1.5}</style>
<h1>Canonical Spring / large Baegunmo</h1><p>14951 unsplit strokes /240974 accepted pressures /F2-C v13 /Layout D /unchanged S3a and twelve colors.</p>
<p><b>Width proxy is illustrative, NOT measured stroke width or ink diffusion:</b> authored width ×(0.35+compression/4mm). Canonical-width view preserves the original authored width/opacity. Semantic depth colors: purple0mm to yellow12mm; actual accepted Spring range stays below10.2mm.</p>
<button onclick="scene.src='Spring_complete_canonical.png'">Canonical width/color</button><button onclick="scene.src='Spring_complete_compression_proxy.png'">Compression proxy</button><button onclick="scene.src='Spring_ink_compression_proxy.png'">Ink only proxy</button><button onclick="scene.src='Spring_physical_compression.png'">Compression colors</button>
<img id="scene" src="Spring_complete_compression_proxy.png"><h2>Candidate curve</h2><img src="Pressure_compression_curve.png">
<h2>Representative unchanged regions / proxy widths</h2><img src="Spring_crop_mountain.png"><img src="Spring_crop_foreground.png"><img src="Spring_crop_vegetation.png">
<p>Paper first-touch10; relative hover10→absolute20; approach+5→15; global35. Numeric review files remain separate from physical machine authorization.</p>''')


def export(root,output,machine,provenance,rich=None,sidecar=None,ink_reload=1500,color_reload=1000):
    p=profile(root,ink_reload,color_reload);strokes,order,jobs,manifest,preserved=load_scene(root,machine,provenance)
    def write(out):
        save_json(out/'profile.spring.large_baegunmo.json',p.data);save_json(out/'profile.spring.ink2000.optional.json',profile(root,2000).data)
        save_json(out/'physical_benchmark_observations.json',observations(root))
        save_json(out/'historical_Z8_brush_profiles.json',prior_profile(root).data['brush_profiles'])
        save_json(out/'canonical.plan.json.gz',manifest);save_json(out/'pressure_distribution.json',pressure_summary(strokes,p))
        raw,_,controller=yaml_candidate(root);(out/'config.X860.Y900.unchanged.yaml').write_bytes(raw);save_json(out/'controller_record.json',controller)
        report=dict(schema='datascape.spring_large_baegunmo_integration.v01',base_commit=PIN,status=STATUS,
            source_readback=preserved,canonical_plan_sha256=PLAN_SHA,profile_sha256=p.sha256,
            canonical_source_sha256=manifest['canonical_source_sha256'],canonical_artwork_or_pressure_changed=False,
            old_benchmark_files_preserved=True,physical_observations_recorded=True,machine_authorized=False,jobs={})
        runtime_report={}
        source_brush={s.origin_id:(s.medium,s.color_slot) for s in strokes}
        for name,units in [('SHARED_INK',jobs['SHARED_INK']),('SHARED_COLOR',jobs['SHARED_COLOR']),('SPRING_AIR',jobs['SHARED_INK']+jobs['SHARED_COLOR'])]:
            print('building',name,len(units),flush=True)
            commands,metrics=build(p,units);air=name=='SPRING_AIR'
            if air:commands=project_air(commands,p,source_brush)
            selected=manifest['jobs']['SHARED_INK']+manifest['jobs']['SHARED_COLOR'] if air else manifest['jobs'][name]
            filename=name+'_REVIEW.gcode';text=numeric_text(commands,p,name)
            (out/filename).write_text(text);(out/(filename+'.gz')).write_bytes(gzip.compress(text.encode(),mtime=0))
            checked=readback((out/filename).read_text(),commands,p,selected,air)
            checked.update(gcode_sha256=hashlib.sha256(text.encode()).hexdigest(),source_units=len(units),
                loads_per_slot=metrics['loads_per_slot'],threshold_overruns=metrics['threshold_overruns'])
            save_json(out/(name+'.readback.json'),checked);report['jobs'][name]=checked
            runtime_report[name]=runtime(commands,p)
            print('verified',name,len(commands),'commands',flush=True)
            del commands,text
        save_json(out/'runtime.json',runtime_report);save_json(out/'verification.json',report)
        runtime_markdown(out,runtime_report)
        if rich and sidecar:visual_preview(out,strokes,order,p,rich,sidecar)
        readme=README
        if (ink_reload,color_reload)!=(1500,1000):
            readme=readme.replace('Ink1500 default/optional2000, color1000.',f'Ink{ink_reload} selected, color{color_reload}. Historical1500/1000 remains preserved separately.')
            readme+=f'\nReproduce this reload variant with --ink-reload {ink_reload} --color-reload {color_reload}.\n'
        (out/'README.md').write_text(readme)
        return report
    return _atomic_output(output,write)


def runtime_markdown(out,report):
    rows=['# Spring offline runtime / minutes','','JD0.01 and full lookahead are assumed, not controller/physical runtime measurements. All station handling/lip operations included.','','| Job | Commanded | Configuration-reference acceleration | Synthetic100 acceleration |','|---|---:|---:|---:|']
    for job,r in report.items():
        a=r['models']['configuration_reference'];low=r['models']['synthetic_low']
        rows.append(f"| {job} | {a['commanded_feed_seconds']/60:.2f} | {a['acceleration_sensitive_seconds']/60:.2f} | {low['acceleration_sensitive_seconds']/60:.2f} |")
    rows+=['','| Job | Drawing | Paper engagement | Non-drawing travel | Station transfer | Material handling |','|---|---:|---:|---:|---:|---:|']
    for job,r in report.items():
        cats=r['models']['configuration_reference']['commanded_feed_seconds_by_category']
        rows.append('| '+job+' | '+' | '.join(f'{cats.get(k,0)/60:.2f}' for k in ('drawing','paper_engagement','non_drawing_travel','station_transfer','station_handling'))+' |')
    (out/'RUNTIME.md').write_text('\n'.join(rows)+'\n')


def verify(output):
    """Verify the delivered bytes and their generation-time numeric audits."""
    out=Path(output);manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    expected={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and not p.name.startswith('.') and p.name!='MANIFEST_SHA256.json'}
    if set(manifest)!=expected:raise ValueError('manifest coverage mismatch')
    for name,sha in manifest.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha:raise ValueError('SHA256 mismatch: '+name)
    canonical=out/'canonical.plan.json.gz'
    plan_bytes=canonical.read_bytes() if canonical.exists() else b''.join(f.read_bytes() for f in sorted(out.glob('canonical.plan.json.gz.part*')))
    plan=json.loads(gzip.decompress(plan_bytes))
    if digest(plan)!=PLAN_SHA:raise ValueError('canonical plan hash mismatch')
    p=Profile.load(out/'profile.spring.large_baegunmo.json');report=json.loads((out/'verification.json').read_text())
    if p.sha256!=report['profile_sha256']:raise ValueError('profile binding mismatch')
    for name,r in report['jobs'].items():
        file=name+'_REVIEW.gcode';raw=gzip.decompress((out/(file+'.gz')).read_bytes())
        if ((out/file).exists() and raw!=(out/file).read_bytes()) or hashlib.sha256(raw).hexdigest()!=r['gcode_sha256']:raise ValueError('G-code/gzip/readback SHA mismatch')
        text=raw.decode();rows=[x for x in text.splitlines() if x and not x.startswith(';')]
        if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or any(x=='M0' for x in rows):raise ValueError('modal/M0/M2 mismatch')
        saved=json.loads((out/(name+'.readback.json')).read_text())
        if saved!=r or r['M0_count']!=0 or r['end_work_xyz']!=[800,800,35]:raise ValueError('readback report mismatch')
    return dict(full_numeric_files_verified=3,all_SHA256_verified=True,compressed_bytes_match=True,
        original_strokes=14951,accepted_pressure_samples=240974,canonical_plan_sha256=PLAN_SHA,machine_authorized=False)


README='''# Spring integration / large Baegunmo physical benchmark

Operator reports the final1..15mm benchmark completed: corrected first-touch10,
clear width differences, splitting beginning around12mm,1500mm ink workable with
gradual fading, lip/wash/recovery/Y900 working. No exact widths or streamed-file/
active-YAML hash were supplied. Observations are preserved separately from formal
machine/profile evidence; prior source/G-code artifacts remain unchanged.

Paper: per-brush first-touch10, relative hover10→absolute20, approach+5→15.
F7000 applies to noncontact Z; contact/compression/release useF2000. Stations,
lip, washing, palette, purge and global35 are ABSOLUTE and never shifted.
Ink1500 default/optional2000, color1000. Reload at the next original-stroke
boundary only; same material never washes. Color changes retain the existing
wash/purge/rewet routine. Dry/used15000 with controlled arrival3000, wet12000,
draw6000, normal20/localoff, start0/900/35, park800/800/35/M2, routineM0=0.

New USER-SPECIFIED candidate compression knots (pressure,mm):
0:0,.2:1,.4:3.5,.6:5.8,.8:8.2,.93:10.2,1:12.
Absolute paper Z=10−compression. Actual Spring pressure<=.93 therefore maps
<=10.2mm, not automatically to12mm. Ink/color curves and first-touch remain
independent. The old Z-8 response is saved as history, not silently reused.
New knot widths/complete Spring physical behavior remain unmeasured; curve and
color calibration are not misrepresented as fully machine-authorized.

SHARED_INK_REVIEW.gcode and SHARED_COLOR_REVIEW.gcode are separate complete
executions, EACH expected to start after manual homing at0/900/35. Manual brush/
water/palette/drying/registration review occurs BETWEEN them. No startup wash
or M0 is added to the prepared color job; automatic washing between colors stays.
SPRING_AIR_REVIEW.gcode is ONE full-scene no-contact simulation of the same ink
then color order and material itinerary, including simulated ink→color wash.
Paper motions project to20/station operations35; it does not prove contact.
It is not a single continuous pigment production program.

All are numeric OFFLINE REVIEW files, NOT completed machine authorization.
No fabricated measured volumes, exact widths, passed stopping/full-scene swept
clearance or installed-YAML hash is supplied. Existing formal export gates stay.
14951 original strokes/240974 pressures/50 continuous X300 crossings, F2-C/v13,
XY/direction/S3a/twelve colors and canonical plan hash remain unchanged.
Only physical execution mapping/material parameters change. No artwork generated.

Visual overview uses original canonical colors/opacity/XY. Canonical-width view
and explicitly labeled unmeasured compression-width proxy are separate. No ink
diffusion or pigmentation is claimed physically simulated. Full PNGs/crops and
HTML are included. Runtime uses actual candidate limits with assumedJD0.01/full
lookahead; separate synthetic100 acceleration reference, never promised duration.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_large_baegunmo --output NEW_DIR --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json --rich RECOVERED/artworks/spring_v13 --sidecar RECOVERED/artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz
Complete G-code is also losslessly gzip-compressed for repository publication;
SHA256 records identify uncompressed commands. Extract before inspection/use.
'''

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--verify',action='store_true')
    for n in ('machine','provenance'):ap.add_argument('--'+n,type=Path)
    ap.add_argument('--rich',type=Path);ap.add_argument('--sidecar',type=Path)
    ap.add_argument('--ink-reload',type=int,default=1500)
    ap.add_argument('--color-reload',type=int,default=1000)
    a=ap.parse_args()
    if a.verify:print(json.dumps(verify(a.output)))
    else:export(Path(__file__).resolve().parents[2],a.output,a.machine,a.provenance,a.rich,a.sidecar,a.ink_reload,a.color_reload)
