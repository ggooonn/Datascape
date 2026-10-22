"""Prepare review-only commissioning artifacts; never writes a runnable .nc."""
import argparse,json,hashlib
from dataclasses import asdict
from pathlib import Path
from math import dist
from datascape.gcode.binding import digest
from datascape.gcode.production.exporter import save_json,export_calibration,export_jobs
from datascape.gcode.production.profiles import Profile,BASE_CHECKS
from datascape.gcode.production.benchmark import air_plan,prepare_air,require_air_profile
from datascape.gcode.production.calibration_jobs import validate_request,EXTRA_EVIDENCE
from .design import profile,designs,yaml_audit,measurements
from .preview import calibration_review,air_review,write_review


def run(output,controller_yaml):
    root=Path(__file__).resolve().parents[2];out=Path(output)
    if out.exists():raise ValueError('output must be new')
    out.mkdir(parents=True);p=profile(root);audit=yaml_audit(controller_yaml);record=measurements(audit)
    save_json(out/'profile.provisional.json',p.data);save_json(out/'measurements.json',record)
    summary={'backend_pin':record['backend_pin'],'local_hover_pin':record['study_pin'],
             'profile_sha256':p.sha256,'authorized':False,'hardware_executed':False,'executable_files_delivered':0,
             'evidence_scope_sha256':{k:p.evidence_scope_sha256(k) for k in (*BASE_CHECKS,'air_run','paper_contact','local_hover_clearance',*EXTRA_EVIDENCE)},'stages':{}}
    (out/'plans').mkdir();(out/'previews').mkdir();(out/'authorization_templates').mkdir()
    for name,request in designs().items():
        save_json(out/'plans'/(name+'.json'),request);is_air=name.startswith('A_');stage='air' if is_air else 'calibration'
        plan_hash=digest(request);job_ids=['CALIBRATION'];issues=p.issues(stage,request.get('station_roles',[]),media=('ink',))
        if is_air:
            _,jobs,manifest=air_plan(request);plan_hash=digest(manifest);job_ids=list(jobs)
            prepare_air(request,p,out/('prepared_'+name))
            try:require_air_profile(request,p)
            except ValueError as e:issues.append(str(e))
        else:
            for check in request.get('requires_evidence',[]):
                if not p.evidence_passed(check):issues.append('missing current-profile calibration prerequisite: '+check)
        authorization={'stage':stage,'profile_sha256':p.sha256,'plan_sha256':plan_hash,'job_ids':job_ids,
                       'operator':None,'date':None,'explicit_operator_authorization':False,
                       'pre_run_confirmations':{job:{k:False for k in ('coordinates_and_start_verified','paper_and_clearance_verified','tool_and_controller_state_verified')} for job in job_ids}}
        save_json(out/'authorization_templates'/(name+'.UNAUTHORIZED.json'),authorization)
        commands=air_review(request,p) if is_air else calibration_review(request,p)
        readback=write_review(out/'previews'/(name+'.preview.txt'),commands,p,request)
        save_json(out/'previews'/(name+'.trajectory.json'),[asdict(c) for c in commands])
        # Try only the real gated exporter with the actual incomplete profile and FALSE authorization.
        # Failure is required; no synthetic machine/evidence is created to force this export.
        target=out/('BLOCKED_'+name)
        try:
            if is_air:export_jobs(jobs,manifest,p,'air',authorization,target)
            else:export_calibration(request,p,authorization,target)
        except ValueError as e:blocked=str(e)
        else:raise RuntimeError('unverified commissioning profile unexpectedly exported executable output')
        if target.exists():raise RuntimeError('blocked export left partial output')
        pos=tuple(p.data['machine']['start_work_xyz']);known_time=0.;partial=False
        for c in commands:
            if c.kind=='move':
                if all(v is not None for v in pos):known_time+=dist(pos,c.xyz)/c.feed_mm_min*60
                else:partial=True
                pos=c.xyz
            elif c.kind=='unresolved':partial=True;pos=(None,None,None)
        summary['stages'][name]={'stage':stage,'plan_sha256':plan_hash,'request_sha256':digest(request),
            'blockers':issues,'actual_gated_export_blocked':True,'export_block_reason':blocked,
            'readback':readback,'candidate_known_commanded_seconds':known_time,
            'time_incomplete':partial,'physical_time_verified':False}
    if list(out.rglob('*.nc')):raise RuntimeError('unexpected executable file in review package')
    observations={'schema':'datascape.commissioning_observations.v01','status':'not_tested','operator':None,'date':None,
       'installed_firmware':None,'installed_config_sha256':None,'home_MPos':None,'home_WPos':[0,898,35],
       'home_WCO':None,'G54_offset':None,'G92_offset':None,'tool_length_offset':None,'feed_override_percent':None,
       'paper_work_origin_xy':None,'measured_paper_above_bed_mm':None,
       'swept_safe_volumes_and_park_record':None,'measured_well_1_deep_surface_xyz':None,'measured_well_1_shallow_surface_xyz':None,
       'measured_well_2_deep_surface_xyz':None,'measured_well_2_shallow_surface_xyz':None,'liquid_reference_z_before_each_station_trial':None,
       'secured_cloth_surface_z':None,
       'tests':[{ 'stage':name,'executed':False,'actual_feed':None,'tested_depths':[],
           'intended_line_length_mm':60 if name.startswith('B_') or name=='E_INK_REAPPLY' else None,
           'width_mm_start_middle_end':None,'continuity':None,'ink_transfer_distribution':None,'paper_response':None,
           'brush_recovery_seconds_and_clearance':None,'water_and_ink_loading':None,'USB_elapsed_minutes':None,
           'disconnect_or_alarm':None,'reference_position_error_mm':None,'physical_pass':None,'notes':''} for name in summary['stages']]}
    save_json(out/'observations.TO_FILL.json',observations);save_json(out/'summary.json',summary)
    return summary


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',required=True,type=Path);a.add_argument('--controller-yaml',required=True,type=Path)
    args=a.parse_args();s=run(args.output,args.controller_yaml)
    print(json.dumps({'stages_prepared':len(s['stages']),'executable_files_delivered':0,'all_actual_exports_blocked':all(x['actual_gated_export_blocked'] for x in s['stages'].values())}))
