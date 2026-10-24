"""Atomic numeric review delivery and regeneration-based readback; no device I/O."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import csv,gzip,hashlib,json
from datascape.gcode.binding import digest
from datascape.gcode.production.exporter import _atomic_output,save_json
from .data import PROJECT,ROOT,PIN,BASE_BRANCH,INPUT_SHA,load_json,settings,load_dots
from .plan import standard_plans,c4_test,remaining
from .motion import build_paint,project_air,serialize,readback,timing,PROFILE_PATH


def write_csv(path,rows):
    if not rows:return
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def mapping_rows(rows,profile,air):
    return [{**r,'machine_x_mm':r['g54_x_mm']+profile.data['machine']['g54_to_machine_xyz'][0],'machine_y_mm':r['g54_y_mm']+profile.data['machine']['g54_to_machine_xyz'][1],'machine_review_touch_z_mm':r['review_first_touch_z_mm']+profile.data['machine']['g54_to_machine_xyz'][2],'machine_review_press_z_mm':r['review_press_z_mm']+profile.data['machine']['g54_to_machine_xyz'][2],'paint_contact_planned':not air,'physical_contact_completed':False} for r in rows]


def job_set(config,completed=None,scenario=None):
    allplans=standard_plans(config=config);small=c4_test(config=config)
    jobs=[(small,False),(allplans[4],True)]+[(p,False) for p in allplans]
    if completed is not None:jobs.append((remaining(allplans[4],completed,scenario),False))
    return jobs


def generate(output,scenario_path=None,config_path=None,completed_path=None):
    config=settings(config_path);scenario=load_json(scenario_path or PROJECT/'config/review.nominal_offset0.json')
    completed=load_json(completed_path) if completed_path else None
    jobs=job_set(config,completed,scenario)
    def write(out):
        save_json(out/'settings.json',config);save_json(out/'scenario.json',scenario)
        if completed:save_json(out/'completion_record.json',completed)
        report=dict(schema='hanji.numeric_review_delivery.v01',backend_base_sha=PIN,backend_base_branch=BASE_BRANCH,source_csv_sha256=INPUT_SHA,backend_profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),status='OFFLINE_REVIEW_ONLY_NOMINAL_MOUNT_NOT_AUTHORIZED',hardware_transmission=False,physical_completion_inferred=False,main_job_count=10,jobs={})
        sample=None
        for p,air in jobs:
            name=p['job_id']+('_AIR' if air else '')
            profile,commands,rows,services=build_paint(p,scenario)
            if air:commands=project_air(profile,commands)
            text=serialize(commands,profile,p,scenario,air)
            checked=readback(text,commands,profile,p,rows,services,air)
            model=timing(commands,profile)
            (out/(name+'.gcode')).write_text(text)
            save_json(out/(name+'.plan.json'),p)
            save_json(out/(name+'.profile.json'),profile.data)
            write_csv(out/(name+'.mapping.csv'),mapping_rows(rows,profile,air))
            save_json(out/(name+'.services.json'),services)
            # Lossless IR is included for first40 and P04 AIR/paint; full-scene IR regenerates.
            if p['physical_panel_id']==4:save_json(out/(name+'.trajectory.json.gz'),[asdict(c) for c in commands])
            report['jobs'][name]=dict(plan_sha256=digest(p),profile_sha256=profile.sha256,gcode_sha256=hashlib.sha256(text.encode()).hexdigest(),air=air,readback=checked,timing=model,used_color_order=p['used_color_order'],colors=p['colors'],loads=p['loads'],same_color_reloads=p['same_color_reloads'],color_changes=p['color_changes'])
            if p['job_id']=='hanji_panel_04_C4_first40' and not air:
                sample=rows
                write_csv(out/'C4_first40_observations.csv',[dict(execution_sequence=r['execution_sequence'],study_dot_id=r['study_dot_id'],group='1-5' if r['execution_sequence']<=5 else '16-20' if 16<=r['execution_sequence']<=20 else '21-25' if 21<=r['execution_sequence']<=25 else '36-40' if r['execution_sequence']>=36 else 'other',contact_in_batch=r['contact_in_batch'],load_batch=r['load_batch'],local_x_mm=r['local_x_mm'],local_y_mm=r['local_y_mm'],z_design_mm=r['z_design_mm'],dry_width_mm='',dry_height_mm='',spread_mm='',density='',paper_deformation='',initial_water='',dilution='',loading_method='',operator_observations='') for r in rows])
            print(name,p['dot_count'],f"{model['acceleration_sensitive_seconds']/60:.2f} modeled min",flush=True)
        save_json(out/'verification.json',report)
        from .visuals import write_previews
        write_previews(out,report,scenario,config)
        (out/'README.md').write_text(delivery_readme(report))
        return report
    return _atomic_output(output,write)


def verify(output):
    out=Path(output);manifest=load_json(out/'MANIFEST_SHA256.json')
    actual={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}
    if actual!=set(manifest):raise ValueError('manifest coverage mismatch')
    for name,expected in manifest.items():
        p=(out/name).resolve()
        if not p.is_relative_to(out.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('artifact hash/path mismatch '+name)
    config=settings(out/'settings.json');scenario=load_json(out/'scenario.json');completion=load_json(out/'completion_record.json') if (out/'completion_record.json').exists() else None
    report=load_json(out/'verification.json')
    if report['source_csv_sha256']!=INPUT_SHA or report['backend_base_sha']!=PIN or report['status']!='OFFLINE_REVIEW_ONLY_NOMINAL_MOUNT_NOT_AUTHORIZED':raise ValueError('source/backend/review identity mismatch')
    jobs=job_set(config,completion,scenario)
    if set(report['jobs'])!={p['job_id']+('_AIR' if a else '') for p,a in jobs}:raise ValueError('job set differs')
    for p,air in jobs:
        name=p['job_id']+('_AIR' if air else '');profile,commands,rows,services=build_paint(p,scenario)
        if air:commands=project_air(profile,commands)
        if (out/(name+'.gcode')).read_text()!=serialize(commands,profile,p,scenario,air):raise ValueError('source/trajectory regenerated G-code differs '+name)
        if digest(load_json(out/(name+'.plan.json')))!=digest(p) or digest(load_json(out/(name+'.profile.json')))!=digest(profile.data):raise ValueError('plan/profile mutation')
        if readback((out/(name+'.gcode')).read_text(),commands,profile,p,rows,services,air)!=report['jobs'][name]['readback']:raise ValueError('readback report differs')
        with (out/(name+'.mapping.csv')).open(newline='') as f: saved_mapping=list(csv.DictReader(f))
        if saved_mapping!=[{k:str(v) for k,v in r.items()} for r in mapping_rows(rows,profile,air)]:raise ValueError('mapping CSV differs from source-derived coordinates')
        if load_json(out/(name+'.services.json'))!=services:raise ValueError('service schedule differs')
        if timing(commands,profile)!=report['jobs'][name]['timing']:raise ValueError('timing report differs')
        ir=out/(name+'.trajectory.json.gz')
        if ir.exists() and digest(json.loads(gzip.decompress(ir.read_bytes())))!=digest([asdict(c) for c in commands]):raise ValueError('saved trajectory differs')
    return dict(files_hashed=len(manifest),jobs_regenerated=len(jobs),numeric_readback_verified=True,main_jobs=10,machine_authorized=False)


def delivery_readme(report):
    lines=['# Hanji C numeric offline review','',
        '**These files contain real G1/G4/M2 commands. They are not machine-authorized programs.**',
        'The named scenario is nominal offset0, artwork XY at0/0, fixed G54 hover35. These are explicit review coordinates, not measured mounting values. Do not strip the review status or assume flat first-touch10 is included.',
        '', 'Default contact:3mm additional compression from local first touch; full1s dwell at depth; reload before point21 after20 contacts. Eight-color Hanji extension and right-first bottom-up serpentine are preserved.',
        '', 'Start for each independent job is G54 X0 Y900 Z35; end X800 Y800 Z35/M2. No homing/offset writes or routine M0. Stations and terminal cleanup reuse PR32. Terminal water3×10s/three agitation cycles, sponge2×4s, no final rewet.',
        '', 'Ten main jobs are alternatives: one full global job OR the nine local panel jobs. P04 benchmark uses hanji_panel_04_local.gcode. The additional C4_first40 overlaps40 points of that890-point job; do not execute both unchanged on the same artwork. No completion is inferred. The P04 AIR plans47 loads but consumes/completes zero actual contacts.',
        '', '| Job | Dots | Colors | Loads | Same-color refill | Changes | Modeled min |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,j in report['jobs'].items():
        lines.append(f"| {name} | {j['readback']['planned_dots']} | {len(j['colors'])} | {j['loads']} | {j['same_color_reloads']} | {j['color_changes']} | {j['timing']['acceleration_sensitive_seconds']/60:.2f} |")
    lines += ['', 'Timing uses the shared full-lookahead/JD0.01 model and configuration-reference XYZ acceleration1500/1500/1000mm/s². Junction deviation is assumed; streaming, finite buffers, step rounding, brush response and dry-mark size are not physically verified.',
        '', 'Open Hanji_C_Review.html for artwork, first40 numbered refill boundary, machine XZ/YZ, heights, offset/hover table, counters and time breakdown. Detailed dot IDs/coordinates/Z/counters are in each mapping CSV. Missing actual first-touch fields remain blank.',
        '', 'Reproduce: PYTHONPATH=src:. python -m projects.hanji_relief --output NEW_DIR',
        'Verify: PYTHONPATH=src:. python -m projects.hanji_relief --verify DIR',
        'Confirmed same-condition paint completion: add --completed-record RECORD.json to generate a separate remaining job. AIR/planned completion is rejected. No arbitrary-line restart.',
        '', 'The source CSV/GH code and previous Spring/backend files are unchanged. No mesh/STL or additional ink pass is generated.']
    return '\n'.join(lines)+'\n'
