"""Offline programs for the operator-selected bed10/hover35 installation.

Use the existing Hanji primitive, material planner, shared serializer, envelope
checks and timing model. Record the operator's setup values without inventing
measured profiles, local surface maps or passed physical evidence. No device I/O.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import csv
import hashlib
import json

from datascape.gcode.binding import digest
from datascape.gcode.production.exporter import _atomic_output, _serialize, save_json
from .data import PROJECT, PIN, BASE_BRANCH, INPUT_SHA, PANEL_MAP, load_json, settings, mount_for
from .plan import standard_plans
from .motion import build_paint, serialize as review_serialize, readback, timing
from .export import write_csv, mapping_rows
from .visuals import xy_svg, machine_projection

SCENARIO_PATH = PROJECT/'config/mounting.bed10_hover35.json'
JOB_NAMES = ('hanji_full_600x600_Z10_Z35_R30', 'hanji_P4_local_Z10_Z35_R30')
STATUS = 'OPERATOR_SPECIFIED_OFFLINE_PROGRAMS'


def setup(config, scenario):
    if scenario.get('status') != 'operator_specified_registration':
        raise ValueError('explicit operator setup is required')
    if scenario.get('operator_requests_offline_programs') is not True or not scenario.get('operator_acceptance_record'):
        raise ValueError('operator request and accepted setup must be recorded')
    if scenario.get('model_design_zero_is_bed_confirmed_by_operator') is not True:
        raise ValueError('bed/model datum relation must be confirmed')
    if (config['compression_depth_mm'], config['dwell_at_depth_s'], config['refill_every_contacts']) != (3, 1, 30):
        raise ValueError('this named run requires 3mm/1s/30contacts')
    for panel in (None, 4):
        mount = mount_for(scenario, panel)
        if (mount['g54_x_mm'], mount['g54_y_mm'], mount['hanji_surface_offset_z_mm'], mount['fixed_hover_g54_z_mm']) != (0, 0, 10, 35):
            raise ValueError('this named installation requires XY0/0, bed10 and hover35')
    if scenario.get('local_surface_corrections'):
        raise ValueError('this installation uses the selected design baseline, not a supplied local map')
    if scenario.get('operator_bed_first_touch_g54_z_mm') != 10:
        raise ValueError('bed first-touch reference must match artwork transform')
    gap = 35-(10+20)  # Immutable GH source analytic bed-to-top ceiling includes Base2.
    accepted = scenario.get('operator_accepted_minimum_nominal_clearance_mm')
    if accepted != 5 or config['required_surface_clearance_mm'] != 5:
        raise ValueError('this run requires the operator-accepted 5mm clearance')
    if gap < config['required_surface_clearance_mm']:
        raise ValueError('nominal full-scene gap is insufficient')
    return dict(design_upper_bound_mm=20, bed_first_touch_g54_z_mm=10,
                highest_nominal_touch_g54_z_mm=30, fixed_hover_g54_z_mm=35,
                nominal_clearance_mm=gap, required_clearance_mm=5,
                clearance_basis='operator accepts 5mm; original analytic design ceiling20 includes Base2',
                local_surface_map_supplied=False, physical_evidence_fabricated=False)


def plans(config):
    all_plans = standard_plans(config=config)
    selected = [deepcopy(all_plans[i]) for i in (0, 4)]
    for plan, name in zip(selected, JOB_NAMES):
        plan['job_id'] = name
    return selected


def serialize(plan, profile, commands, scenario):
    label = 'P1-P9 / source P07-P09,P04-P06,P01-P03' if plan['physical_panel_id'] is None else 'P4 / source P04'
    header = [
        '; HANJI OPERATOR-SPECIFIED PROGRAM - GENERATED OFFLINE',
        '; '+label+'; coordinate_mode='+plan['coordinate_mode']+'; dots='+str(plan['dot_count']),
        '; SETUP artwork lower-left G54 X0 Y0; model datum is bed; bed first touch G54 Z10',
        '; Z_touch=designZ+10; Z_press=designZ+7; hover=G54 Z35; accepted nominal gap=5mm',
        '; COMPRESSION=3mm; DWELL_AT_DEPTH=1s; REFILL_AFTER=30 contacts before31; no wash on same-color refill',
        '; Operator-selected setup; no local measured correction map; no fabricated measurement/evidence',
        '; Fixed stations unchanged; no homing, G92, work-offset/controller writes or automatic transmission',
        '; START G54 X0 Y900 Z35; END G54 X800 Y800 Z35 / M2',
        '; Alternative full/P4 programs; no artwork completion inferred from this file',
    ]
    return '\n'.join(header)+'\n'+_serialize(commands, profile, digest({'plan':plan, 'scenario':scenario}), plan['job_id'], 'operator_specified')


def checked_text(text, plan, profile, commands, rows, services, scenario):
    # The inherited readback validates every numeric move, dwell and material
    # sequence. The user-program serialization must match those same commands.
    reviewed = review_serialize(commands, profile, plan, scenario)
    result = readback(reviewed, commands, profile, plan, rows, services)
    if text != serialize(plan, profile, commands, scenario):
        raise ValueError('operator-program content differs from regenerated serialization')
    numeric = lambda s: [line for line in s.splitlines() if line and not line.startswith(';')]
    if numeric(text) != numeric(reviewed):
        raise ValueError('user-program numeric commands differ from checked shared trajectory')
    return {**result, 'operator_setup_applied':True, 'nominal_clearance_accepted_by_operator':True}


def generate(output, scenario_path=SCENARIO_PATH, config_path=None):
    config=settings(config_path);scenario=load_json(scenario_path);clearance=setup(config,scenario)
    def write(out):
        save_json(out/'settings.json',config);save_json(out/'mounting.json',scenario)
        report=dict(schema='hanji.operator_program_delivery.v01',status=STATUS,
                    backend_base_sha=PIN,backend_base_branch=BASE_BRANCH,
                    source_csv_sha256=INPUT_SHA,clearance=clearance,
                    physical_panel_source_map=PANEL_MAP,hardware_transmission=False,
                    physical_completion_inferred=False,jobs={})
        for plan in plans(config):
            name=plan['job_id'];profile,commands,rows,services=build_paint(plan,scenario)
            text=serialize(plan,profile,commands,scenario)
            checked=checked_text(text,plan,profile,commands,rows,services,scenario)
            model=timing(commands,profile)
            (out/(name+'.gcode')).write_text(text)
            save_json(out/(name+'.plan.json'),plan);save_json(out/(name+'.profile.json'),profile.data)
            write_csv(out/(name+'.mapping.csv'),mapping_rows(rows,profile,False))
            save_json(out/(name+'.services.json'),services)
            (out/(name+'.xy.svg')).write_text(xy_svg(plan))
            if plan['physical_panel_id']==4:
                ir=[asdict(command) for command in commands]
                for axis in ('X','Y'):
                    (out/(name+'.'+axis.lower()+'z.svg')).write_text(machine_projection(rows,ir,axis))
            report['jobs'][name]=dict(gcode_sha256=hashlib.sha256(text.encode()).hexdigest(),
                plan_sha256=digest(plan),profile_sha256=profile.sha256,readback=checked,
                loads=plan['loads'],same_color_reloads=plan['same_color_reloads'],
                color_changes=plan['color_changes'],colors=plan['colors'],timing=model)
        save_json(out/'verification.json',report)
        write_csv(out/'time_breakdown.csv',[dict(job=name,category=category,seconds=seconds) for name,j in report['jobs'].items() for category,seconds in j['timing']['acceleration_sensitive_seconds_by_category'].items()])
        (out/'README.md').write_text(readme(report))
        return report
    return _atomic_output(output,write)


def verify(output):
    out=Path(output).resolve();hashes=load_json(out/'MANIFEST_SHA256.json')
    actual={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}
    if set(hashes)!=actual:raise ValueError('manifest coverage differs')
    for name,sha in hashes.items():
        path=(out/name).resolve()
        if not path.is_relative_to(out) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('artifact hash/path differs')
    config=settings(out/'settings.json');scenario=load_json(out/'mounting.json');clearance=setup(config,scenario)
    report=load_json(out/'verification.json')
    if report['status']!=STATUS or report['source_csv_sha256']!=INPUT_SHA or report['backend_base_sha']!=PIN or report['clearance']!=clearance:
        raise ValueError('source/setup/report identity differs')
    if set(report['jobs'])!=set(JOB_NAMES):raise ValueError('job set differs')
    for plan in plans(config):
        name=plan['job_id'];profile,commands,rows,services=build_paint(plan,scenario)
        text=(out/(name+'.gcode')).read_text()
        checked=checked_text(text,plan,profile,commands,rows,services,scenario)
        j=report['jobs'][name]
        if checked!=j['readback'] or timing(commands,profile)!=j['timing'] or hashlib.sha256(text.encode()).hexdigest()!=j['gcode_sha256']:
            raise ValueError('numeric/timing report differs')
        if digest(load_json(out/(name+'.plan.json')))!=digest(plan) or digest(load_json(out/(name+'.profile.json')))!=digest(profile.data):
            raise ValueError('source plan/profile differs')
        if load_json(out/(name+'.services.json'))!=services:raise ValueError('material service differs')
        with (out/(name+'.mapping.csv')).open(newline='') as f:saved=list(csv.DictReader(f))
        if saved!=[{k:str(v) for k,v in row.items()} for row in mapping_rows(rows,profile,False)]:
            raise ValueError('coordinate/contact mapping differs')
    return dict(files_hashed=len(hashes),jobs_regenerated=2,numeric_readback_verified=True,
                bed_first_touch_g54_z_mm=10,fixed_hover_g54_z_mm=35,
                operator_accepted_nominal_gap_mm=5,hardware_transmission=False)


def readme(report):
    lines=['# Hanji bed10 / hover35 / 30-contact programs','',
        'Two operator-requested alternatives: full600x600 assembly OR physical P4 in local200x200 coordinates. These files contain actual motion commands. Generation is offline; no machine was connected or operated.',
        '', 'Place the artwork nominal outer lower-left at existing G54 X0 Y0. The full program uses global XY; P4 uses unchanged panel-local XY and full design Z. Do not shift G54 or station coordinates to reposition the artwork.',
        '', 'Operator-selected setup: model datum=bed; first bed touch G54 Z10; first touch=designZ+10; press=designZ+7;3mm compression, full1s at depth; hover35. Analytic design ceiling20 already includes Base2. Nominal full-scene gap5mm is explicitly accepted by the operator, replacing the earlier10mm criterion. No local correction map or new measurement is fabricated.',
        '', 'Each independent file starts at G54 X0Y900Z35 and ends at X800Y800Z35/M2. Same-color supply follows30completed contacts/retraction, before31/61/etc; color changes use the existing wash/purge/rewet/load and reset. No redundant load after a final color dot. Terminal PR32 cleanup occurs once. Station coordinates, rates, controller limits and G54-to-machine registration remain unchanged.',
        '', 'Use the spare P4 for the preliminary complete-panel test. The full program includes all890P4 dots; painting an original panel with P4 then running the unchanged full program on that same panel repeats those dots. No physical completion is inferred or recorded here.',
        '', '| Program | Dots | Loads | Modeled minutes |','| --- | ---: | ---: | ---: |']
    for name,j in report['jobs'].items():lines.append(f"| {name}.gcode | {j['readback']['planned_dots']} | {j['loads']} | {j['timing']['acceleration_sensitive_seconds']/60:.2f} |")
    lines += ['', 'Timing uses the existing Cartesian full-lookahead model, configured acceleration1500/1500/1000mm/s² and assumed JD0.01. It is not measured execution time. Dwell begins after the press move completes. Motion/hold/load/wash categories are included in time_breakdown.csv.',
        '', 'Physical panel labels are P1-P9 from front-view top-left to bottom-right. Original source IDs remain separate: P1/sourceP07, P2/sourceP08, P3/sourceP09, P4/sourceP04, P5/sourceP05, P6/sourceP06, P7/sourceP01, P8/sourceP02, P9/sourceP03. C2/C4 are color IDs. Preview diameter2.8mm is an unmeasured display assumption; SVG labels never paint.',
        '', 'Numeric verification re-creates the two plans, shared trajectory, final serialized moves/dwell, per-contact mapping and material schedule. Operator setup/acceptance is recorded separately from measured-profile evidence; existing official physical exporter gates remain unchanged. No homing, G92, controller/offset writes, routineM0, transmission, physical measurements or completion claims are added.',
        '', f'Backend base: {BASE_BRANCH} / {PIN}. Source CSV SHA256: {INPUT_SHA}.',
        '', 'Reproduce: PYTHONPATH=src:. python -m projects.hanji_relief.run_export --output NEW_DIR',
        'Verify: PYTHONPATH=src:. python -m projects.hanji_relief.run_export --verify DIR']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output');parser.add_argument('--verify')
    args=parser.parse_args()
    if bool(args.output)==bool(args.verify):parser.error('choose --output NEW_DIR or --verify DIR')
    result=verify(args.verify) if args.verify else generate(args.output)
    print(json.dumps(result if args.verify else {k:dict(dots=j['readback']['planned_dots'],loads=j['loads'],modeled_minutes=round(j['timing']['acceleration_sensitive_seconds']/60,2)) for k,j in result['jobs'].items()},indent=2))
