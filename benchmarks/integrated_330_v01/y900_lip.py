"""Y900 frame reconciliation and one-wipe/lip-clearance numeric reviews.

All profiles/files are conditional reviews, never physical authorization. No
installed YAML, old candidates, canonical artwork or Spring response is edited.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from math import dist
import difflib
import hashlib
import json

import yaml

from datascape.gcode.binding import digest,load_bound_spring
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile,number,vector
from datascape.gcode.production.sequence import reference_order,make_plan,verify_plan
from datascape.gcode.production.trajectory import travel_segments
from datascape.gcode.production.exporter import _atomic_output,_serialize,_MOVE,_DWELL,save_json
from .high_speed import build_benchmark,elevated_air,PLAN_SHA
from .numeric_review import BANNER,STATUS,check_move,xy_route
from .spring_runtime import RuntimeBuilder

PIN='619d18b0ccbb2624e653bf8450d2fac2ff9e2400'
BASE='benchmarks/integrated_330_v01/review_high_speed'
REFERENCE_ID='A2'
REFERENCE_XY=[824.5,554.5]
LIP_REGIONS={'ink':dict(hardware_id='WELL_2',x=815.,y=458.,y_range=[448.,468.],z=20.),
         'water':dict(hardware_id='WELL_1',x=815.,y=298.,y_range=[288.,308.],z=20.)}


def yaml_candidate(root):
    source=(root/BASE/'config.X860.high_speed.candidate.yaml').read_bytes()
    lines=source.decode().splitlines(True);axis=None;homing=False;changes=[]
    for i,line in enumerate(lines):
        if line in ('  x:\n','  y:\n','  z:\n'):axis=line.strip()[:-1];homing=False
        if axis=='y':
            if line=='    homing:\n':homing=True
            if line.startswith('    max_travel_mm:'):
                lines[i]='    max_travel_mm: 900.0\n';changes.append('axes.y.max_travel_mm')
            if homing and line.startswith('      mpos_mm:'):
                lines[i]='      mpos_mm: 900.0\n';changes.append('axes.y.homing.mpos_mm')
    header=('# Y900 COMMISSIONING CANDIDATE - NOT INSTALLED / NOT PHYSICALLY VERIFIED\n'
        '# Physical Y0 and station registration are unchanged; only upper hardware travel extends to900.\n'
        '# Expected post-home MPos/WPos:0/900/35 with existing zero G54/G92/TLO. Verify read-back.\n'
        '# Do not translate stations or add a G54+2 correction; investigate any unexpected mismatch.\n'
        '# Historical comments/name below remain archival; DO NOT execute their old G10 example.\n'
        '# Y max_travel900: upper extension operator-reported; actual home/end-margin checks still pending.\n')
    candidate=(header+''.join(lines)).encode();old=yaml.safe_load(source);new=yaml.safe_load(candidate)
    expected=deepcopy(old);expected['axes']['y']['homing']['mpos_mm']=900.;expected['axes']['y']['max_travel_mm']=900.
    if new!=expected:raise ValueError('unrelated YAML setting changed')
    diff=''.join(difflib.unified_diff(source.decode().splitlines(True),candidate.decode().splitlines(True),
        fromfile='PR31/config.X860.high_speed.candidate.yaml',tofile='config.X860.Y900.high_speed.candidate.yaml'))
    record=dict(source_sha256=hashlib.sha256(source).hexdigest(),candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        settings_changed=changes,Y_homing_mpos_mm=900,Y_max_travel_mm=900,
        nominal_axis_reference_Y_bounds=[0,900],nominal_bounds_not_measured=True,
        physical_Y0_unchanged_operator_reported=True,upper_hardware_extension_operator_reported=True,
        installed=False,read_back=False,physical_range_verified=False,
        all_other_settings_preserved=True,historical_name_and_comments_not_configuration_evidence=True,
        firmware_reference='FluidNC v4.1.1 Machine/Homing.cpp set_mpos assigns homing label after pull-off; Axis.cpp defines max_travel from post-home position',
        firmware_blobs=['27b5833afd94e5418c1f390da2fa828db6d59a1a','0463579a955c118fd247aa93abbf567d345ca7da'])
    return candidate,diff,record


def reconciliation_template():
    return dict(status='NOT SUPPLIED / NOT CONFIRMED',operator=None,date=None,method=None,
        active_yaml_sha256=None,post_home_mpos=None,post_home_wpos=None,
        g54_offset=None,g92_offset=None,tool_offset=None,known_reference_id=REFERENCE_ID,
        old_registered_reference_work_xy=REFERENCE_XY,reference_mpos_y=None,reference_wpos_y=None,
        fixed_fixtures_unchanged=True,physical_Y0_unchanged_operator_reported=True,
        upper_assembly_extension_operator_reported=True,physical_travel900_confirmed=False,
        lower_Y0_mpos_y=None,lower_Y0_wpos_y=None,
        note='Unchanged physical Y0/fixtures are already operator-reported. Supply NEW controller/home/reference/end-range read-back; expected G54 remains0. No automatic offset correction and no passed record is created.')


def validate_reconciliation(record,target_sha):
    """Check operator-supplied read-back; never set machine offsets or evidence."""
    for key in ('operator','date','method'):
        if not isinstance(record.get(key),str) or not record[key].strip():raise ValueError('supply actual '+key)
    if record.get('active_yaml_sha256')!=target_sha:raise ValueError('actual active YAML read-back SHA256 required')
    if record.get('post_home_mpos')!=[0,900,35]:raise ValueError('confirm new actual post-home MPos')
    if record.get('g92_offset')!=[0,0,0] or record.get('tool_offset')!=[0,0,0]:raise ValueError('resolve actual G92/TLO before using this zero-secondary-offset workflow')
    g54=record.get('g54_offset');wpos=record.get('post_home_wpos')
    if g54!=[0,0,0] or wpos!=[0,900,35]:raise ValueError('unchanged Y0 expects preserved zero G54 and home WPos900; investigate mismatch, do not add+2')
    if record.get('known_reference_id')!=REFERENCE_ID or record.get('old_registered_reference_work_xy')!=REFERENCE_XY or record.get('fixed_fixtures_unchanged') is not True:
        raise ValueError('verify same fixed A2 reference/fixtures; do not translate relocated objects globally')
    m=record.get('reference_mpos_y');w=record.get('reference_wpos_y')
    if not number(m) or not number(w):raise ValueError('supply actual fixed-reference MPos/WPos')
    if abs(w-REFERENCE_XY[1])>1e-3 or abs(m-REFERENCE_XY[1])>1e-3:
        raise ValueError('fixed reference disagrees with unchanged Y0; investigate homing/config/offset, do not translate stations')
    for key in ('lower_Y0_mpos_y','lower_Y0_wpos_y'):
        if not number(record.get(key)) or abs(record[key])>1e-3:raise ValueError('verify unchanged mechanical Y0 against actual '+key)
    if record.get('physical_travel900_confirmed') is not True:raise ValueError('actual900 travel and end margins are not confirmed')


def frame_profile(root,wet=12000,record=None):
    base=Profile.load(root/BASE/f'profile.high_wet{wet}.json');d=deepcopy(base.data)
    _,_,target=yaml_candidate(root)
    if record is not None:validate_reconciliation(record,target['candidate_sha256'])
    d['profile_id']=f'Y900-UNCHANGED-Y0-WET{wet}-ONE-WIPE-REVIEW'
    m=d['machine'];m.update(start_work_xyz=[0,900,35],g54_to_machine_xyz=[0,0,0],
        target_config_sha256=target['candidate_sha256'],target_config_installed=False,
        expected_post_home_machine_xyz=[0,900,35],coordinate_reconciliation_confirmed=record is not None,
        physical_Y0_unchanged_operator_reported=True,upper_hardware_extension_operator_reported=True,
        coordinate_frame_status='operator-reported read-back reconciliation only' if record else 'UNCHANGED Y0 operator-reported; new controller/home/reference verification pending')
    m['machine_bounds_xyz'][0][1]=0;m['machine_bounds_xyz'][1][1]=900
    if record is not None:
        m.update(installed_config_sha256=record['active_yaml_sha256'],target_config_installed=True,
            coordinate_reconciliation_record_sha256=digest(record))
    for role,st in d['stations'].items():
        st['new_home_registration_status']='existing unchanged-Y0 G54 registration retained; new home/config verification pending'
        if role in LIP_REGIONS:
            st['shallow_wipe']['passes']=1
            proposal=LIP_REGIONS[role]
            st['lip_stripping'].update(enabled=False,relative_x_mm=None,
                historical_proposed_relative_x_mm=-20,
                candidate_xyz=[proposal['x'],proposal['y'],proposal['z']],
                candidate_is_measured_contact=False,measured_contact_xyz=None,
                contact_feed_mm_min=None,safe_retract_z=None,release_path_xyz=None,
                holder_clearance_confirmed=False,
                status='CONTACT DISABLED: region proposal is not verified lip contact or holder clearance; actual displacement remains null')
    d['notes']='Separate Y900 upper-travel extension and ONE shallow-wipe review. Physical Y0 and every existing station/paper work coordinate are preserved. No+2 offset or translation. Actual new configuration/home/end-range read-back remains pending. Lip contact disabled; Spring Z-8 untouched.'
    if d['brush_profiles']!=base.data['brush_profiles'] or d['motion']!=base.data['motion']:
        raise ValueError('pressure or accepted motion policy changed')
    return Profile.from_dict(d)


def lip_candidates():
    out={}
    for role,old in LIP_REGIONS.items():
        wipe=[445,465] if role=='ink' else [295,315];low,high=old['y_range']
        overlap=max(0,min(wipe[1],high)-max(wipe[0],low))
        out[role]=dict(hardware_id=old['hardware_id'],candidate_frame='UNCHANGED physical Y0 / existing G54; operator-reported regions, NOT measured contact geometry',
            operator_candidate_xyz=[old['x'],old['y'],old['z']],operator_candidate_y_range=old['y_range'],
            contact_or_holder_clearance_verified=False,contact_enabled=False,
            proposed_direction='decreasing X',clearance_only_X_move=[840,815],clearance_only_delta_X_mm=-25,
            historical_relative_X_proposal_mm=-20,relative_displacement_is_not_absolute_coordinate=True,
            proposed_first_contact_feed_mm_min=300,proposed_first_contact_displacement_mm=-1,
            proposals_not_applied_without_actual_contact_confirmation=True,
            measured_contact_start_xyz=None,confirmed_relative_x_mm=None,confirmed_contact_feed_mm_min=None,
            confirmed_release_path_xyz=None,confirmed_retract_z=None,holder_clearance_confirmed=False,
            replacement_routine=['deep immersion and X agitation','original Y+ sloped withdrawal',
                'ONE pressed shallow Y+ wipe at provisional Z7.5','vertical controlled release then liftZ35',
                'verified lip approach: DISABLED until geometry/corridor confirmation',
                'ONE short low-speed X-negative strip: DISABLED until measured contact/approval',
                'confirmed release and verticalZ35 before long XY travel'],
            shallow_wipe_work_y=wipe,shallow_wipe_contact_z=7.5,shallow_surface_z_assumption=9,
            Y_interval_overlap_mm=overlap,wipe_end_inside_lip_Y_region=low<=wipe[1]<=high,
            clearance_reposition_Y_to_region_center_mm=old['y']-wipe[1],
            compatibility='Y overlap alone does not validate contact: wiping X840/Z7.5 and proposed lip X815/Z20 are distinct. Release and lift35 before X/Y reposition; no pressed extension or shared-surface inference.')
    return out


def contact_blockers(profile,role,request):
    blockers=[]
    if not profile.data['machine'].get('coordinate_reconciliation_confirmed'):blockers.append('actual new-frame/G54 fixed-reference reconciliation')
    for key in ('measured_contact_start_xyz','confirmed_relative_x_mm','confirmed_contact_feed_mm_min',
                'confirmed_release_path_xyz','confirmed_retract_z'):
        if request.get(key) is None:blockers.append(role+': '+key)
    if request.get('holder_clearance_confirmed') is not True:blockers.append(role+': mounted brush/holder clearance and safe release/retract confirmation')
    blockers.append('separate current-profile low-speed lip trial authorization; existing production lip-enable guard remains closed')
    return blockers


def require_contact_ready(profile,role,request):
    errors=contact_blockers(profile,role,request)
    if errors:raise ValueError('lip contact export blocked: '+'; '.join(errors))


def clearance_xy(b,xy,arrival_feed=1000):
    b.lift(35);v=deepcopy(b.v);v['segmented_travel']['ordinary_travel']['arrival_mm_min']=arrival_feed
    b.time_context='station_transfer'
    for point,feed,phase in travel_segments(b.position,(*xy,35),'ordinary_travel',v,True):
        b.move(point,feed,'travel','ordinary_travel',travel_phase=phase)
    b.time_context=None


def frame_air(p):
    b=RuntimeBuilder(p);b.marker('frame_reference',REFERENCE_ID+' unchanged G54 center; verification only, no offset setting')
    clearance_xy(b,REFERENCE_XY);b.dwell(2,'reference_observation')
    # Stay at global35; lower stopper/end-limit verification is a manual task.
    clearance_xy(b,[10,10])
    for xy in ([320,10],[320,320],[10,320],[10,10]):b.move((*xy,35),6000,'frame_outline')
    b.park();return b.commands


def lip_air(p):
    b=RuntimeBuilder(p)
    for role,old in LIP_REGIONS.items():
        y=old['y'];b.marker('lip_clearance_begin',role+' unchanged-Y0 candidate region; NO DESCENT TO20')
        clearance_xy(b,[840,y])
        for xy in ([815,y],[815,old['y_range'][0]],[815,old['y_range'][1]],[815,y],[840,y]):
            b.move((*xy,35),500,'lip_clearance_only',travel_phase='lip_clearance')
        b.marker('lip_clearance_complete',role)
    b.park();return b.commands


def jobs(root,p):
    plan,paint=build_benchmark(root,p);air=elevated_air(paint,p)
    return plan,{'FRAME_AIR':frame_air(p),'LIP_APPROACH_AIR':lip_air(p),
        'ONE_WIPE_330_AIR':air,'ONE_WIPE_330_WATER_ONLY':paint,'ONE_WIPE_330_INK_GOUACHE':paint}


def readback(text,commands,p,name):
    if not text.startswith(BANNER):raise ValueError('review identity missing')
    rows=[r for r in text.splitlines() if r and not r.startswith(';')];expected=[c for c in commands if c.kind!='marker']
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or len(rows)!=len(expected)+2:raise ValueError('modal/command/M2 coverage mismatch')
    pos=tuple(p.data['machine']['start_work_xyz']);offset=p.data['machine']['g54_to_machine_xyz'];air='AIR' in name
    rates=[0.,0.,0.];wipes=[];draws=[];visits=[];positions=[pos];paper_links=0
    for row,c in zip(rows[1:-1],expected):
        if c.kind=='move':
            match=_MOVE.fullmatch(row)
            if not match:raise ValueError('unrecognized move')
            x,y,z,feed=map(float,match.groups());target=(x,y,z)
            if any(abs(a-b)>5.1e-10 for a,b in zip((x,y,z,feed),(*c.xyz,c.feed_mm_min))):raise ValueError('numeric read-back differs from IR')
            check_move(pos,target,feed,c.action,p,'air' if air else 'paint')
            length=dist(pos,target)
            if length:
                for i in range(3):rates[i]=max(rates[i],abs(target[i]-pos[i])/length*feed)
            if c.time_category=='station_transfer' and pos[:2]!=target[:2] and (pos[2]!=35 or z!=35):raise ValueError('station XY transfer must be at35')
            if c.action=='lip_clearance_only' and (pos[2]!=35 or z!=35 or feed>500):raise ValueError('lip tour must remain noncontact35 and slow')
            if c.action=='travel' and pos[:2]!=target[:2] and pos[2]==z==15:paper_links+=1
            if c.action=='draw':draws.append(dict(source=c.source_id,end=list(target),feed=feed))
            if c.travel_phase=='shallow_wipe':wipes.append(dict(start=list(pos),end=list(target),feed=feed))
            pos=target;positions.append(pos)
        elif c.kind=='dwell':
            match=_DWELL.fullmatch(row)
            if not match or abs(float(match.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell mismatch')
        else:raise ValueError('unexpected pause or unresolved action')
    for c in commands:
        if c.action=='benchmark_station_visit':visits.append(c.message)
    if pos!=(800,800,35):raise ValueError('park mismatch')
    if name.startswith(('FRAME','LIP_')) and any(x[2]!=35 for x in positions):raise ValueError('frame/lip clearance program must stay at35')
    if name.startswith('ONE_WIPE'):
        if len(draws)!=40 or visits!=['ink:pigment_load','ink:same_color_reload','water:wash','sponge:absorbent_contact','A2:pigment_load','A2:same_color_reload']:
            raise ValueError('40-stroke/material visit preservation mismatch')
        if not air:
            ends=[(840,465,7.5),(840,465,7.5),(840,315,7.5)]
            if [tuple(w['end']) for w in wipes]!=ends or paper_links!=108:raise ValueError('one-pass contact or normalZ15 paper links changed')
            for w in wipes:
                if w['start']!=[w['end'][0],w['end'][1]-20,7.5]:raise ValueError('pressed Y+20mm required')
            for i,c in enumerate(commands):
                if c.travel_phase=='shallow_wipe':
                    after=[r for r in commands[i+1:] if r.kind=='move'][:2]
                    if [r.xyz for r in after]!=[(*c.xyz[:2],9),(*c.xyz[:2],35)]:raise ValueError('release and vertical35 lift must precede all lateral motion')
    return dict(readback_verified=True,source_strokes=len(draws),draw_sources=draws,station_visits=visits,
        start_work_xyz=p.data['machine']['start_work_xyz'],start_machine_xyz=[a+b for a,b in zip(p.data['machine']['start_work_xyz'],offset)],
        end_work_xyz=list(pos),end_machine_xyz=[a+b for a,b in zip(pos,offset)],G54_offset_xyz=offset,
        candidate_machine_bounds=p.data['machine']['machine_bounds_xyz'],maximum_projected_axis_feeds=rates,
        axis_feed_caps=p.data['machine']['axis_max_rate_mm_min'],complete_linear_axis_bounds_checked=True,
        physical_swept_clearance_verified=False,physical_frame_confirmed=p.data['machine']['coordinate_reconciliation_confirmed'],
        lip_contact_emitted=False,lip_Z20_descent_emitted=False,pressed_shallow_passes=0 if air else len(wipes),
        shallow_wipes=wipes,normal_Z15_paper_travel_segments=paper_links,M0_count=0,M2_verified=True,
        authorized=False,trajectory_sha256=digest([asdict(c) for c in commands]))


def spring_dependencies(root,profiles,machine,provenance):
    strokes,_=load_bound_spring(machine,provenance);base=next(iter(profiles.values()))
    order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    _,plan=make_plan(strokes,Layout('D'),order,palette_order=base.data['material']['color_order'])
    if digest(plan)!=PLAN_SHA:raise ValueError('canonical Spring plan changed')
    points=[(f['work_xy'],f['stroke']['stroke_id']) for units in plan['jobs'].values() for u in units for f in u['fragments']]
    out=dict(plan_sha256=PLAN_SHA,source_readback=verify_plan(plan,strokes,Layout('D')),artwork_or_pressure_modified=False,Spring_Gcode_exported=False,cases={})
    for key,p in profiles.items():
        off=p.data['machine']['g54_to_machine_xyz'];lo,hi=p.data['machine']['machine_bounds_xyz'];bad=[];minimum=1e9;maximum=-1e9
        for xy,_ in points:
            for x,y in xy:
                q=(x+off[0],y+off[1]);minimum=min(minimum,q[1]);maximum=max(maximum,q[1])
                if not all(a-1e-9<=v<=b+1e-9 for a,v,b in zip(lo[:2],q,hi[:2])):bad.append(q)
        out['cases'][key]=dict(profile_sha256=p.sha256,mapped_machine_Y_range=[minimum,maximum],
            vertices_outside_nominal_XY_bounds=len(bad),first_outside_vertices=bad[:5],
            frame_or_physical_execution_authorized=False,note='Axis-reference dependency check only; no swept clearance or controller installation inferred')
    return out


def export(root,output,record=None,machine=None,provenance=None):
    profiles={'UNCHANGED_Y0':frame_profile(root,record=record)}
    proposal=lip_candidates()
    def write(out):
        raw,diff,rec=yaml_candidate(root)
        (out/'config.X860.Y900.high_speed.candidate.yaml').write_bytes(raw)
        (out/'config.X860.Y900.high_speed.diff').write_text(diff)
        if record is not None:
            rec.update(installed=True,read_back=True,physical_range_verified=True,
                verification_source='operator-supplied record; no independent hardware activity by software')
            save_json(out/'reconciliation.OPERATOR_REPORTED.json',record)
        save_json(out/'controller.Y900.json',rec)
        save_json(out/'reconciliation.TO_COMPLETE.json',reconciliation_template());save_json(out/'lip_candidates.json',proposal)
        save_json(out/'LIP_CONTACT_NOT_EXPORTED.json',dict(
            reason='X815/Z20 and a Y region are proposals, not actual brush/edge contact or holder/release clearance.',
            low_speed_contact_Gcode_written=False,operator_requested_direction='X-negative',
            required_by_well={role:contact_blockers(next(iter(profiles.values())),role,q) for role,q in proposal.items()}))
        report=dict(schema='datascape.y900_one_wipe_lip_review.v01',base_commit=PIN,status=STATUS,
            Y_travel_candidate_mm=900,physical_Y0_unchanged_operator_reported=True,
            upper_assembly_extension_operator_reported=True,global_station_translation_applied=False,
            actual_reconciliation_record_supplied=record is not None,
            existing_two_pass_baseline_preserved=True,lip_contact_program_exported=False,authorized=False,cases={})
        for key,p in profiles.items():
            save_json(out/f'profile.{key}.wet12000.json',p.data)
            save_json(out/f'profile.{key}.wet15000.json',frame_profile(root,15000,record).data)
            plan,programs=jobs(root,p);save_json(out/'benchmark40.plan.json',plan)
            checked={}
            for name,commands in programs.items():
                filename=f'Y900_{key}_{name}_REVIEW'
                text=BANNER+'; UNCHANGED Y0 / EXPECTED HOME MPos=WPos0/900/35 - VERIFY NEW CONFIGURATION\n; NO LIP CONTACT OR DESCENT TO CANDIDATE Z20\n'+_serialize(commands,p,digest(plan),filename,'offline_review')
                (out/(filename+'.gcode')).write_text(text)
                result=readback((out/(filename+'.gcode')).read_text(),commands,p,name)
                save_json(out/(filename+'.readback.json'),result);checked[name]=result
            if xy_route(programs['ONE_WIPE_330_AIR'])!=xy_route(programs['ONE_WIPE_330_WATER_ONLY']):raise ValueError('paired one-wipe Air XY changed')
            report['cases'][key]=dict(profile_sha256=p.sha256,jobs=checked,lip_contact_blockers={role:contact_blockers(p,role,q) for role,q in proposal.items()})
        if machine is not None and provenance is not None:save_json(out/'spring_coordinate_dependencies.json',spring_dependencies(root,profiles,machine,provenance))
        save_json(out/'verification.json',report);(out/'README.md').write_text(README)
        return report
    return _atomic_output(output,write)


def verify(root,output):
    out=Path(output);hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(hashes)!={p.name for p in out.iterdir() if p.is_file() and p.name!='MANIFEST_SHA256.json'}:raise ValueError('manifest coverage mismatch')
    for name,h in hashes.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=h:raise ValueError('SHA256 mismatch: '+name)
    raw,diff,controller=yaml_candidate(root)
    if (out/'config.X860.Y900.high_speed.candidate.yaml').read_bytes()!=raw or (out/'config.X860.Y900.high_speed.diff').read_text()!=diff:
        raise ValueError('YAML/diff regeneration mismatch')
    record_path=out/'reconciliation.OPERATOR_REPORTED.json'
    record=json.loads(record_path.read_text()) if record_path.exists() else None
    report=json.loads((out/'verification.json').read_text());count=0
    for key,c in report['cases'].items():
        p=Profile.load(out/f'profile.{key}.wet12000.json');plan,programs=jobs(root,p)
        if p.sha256!=c['profile_sha256'] or p.sha256!=frame_profile(root,record=record).sha256:raise ValueError('profile hash/regeneration mismatch')
        if p.data['machine']['target_config_sha256']!=controller['candidate_sha256']:raise ValueError('YAML/profile binding mismatch')
        if Profile.load(out/f'profile.{key}.wet15000.json').sha256!=frame_profile(root,15000,record).sha256:raise ValueError('optional wet15000 profile mismatch')
        for name,commands in programs.items():
            filename=f'Y900_{key}_{name}_REVIEW';text=(out/(filename+'.gcode')).read_text()
            if text[text.index('; DATASCAPE'): ]!=_serialize(commands,p,digest(plan),filename,'offline_review'):raise ValueError('G-code regeneration mismatch')
            checked=readback(text,commands,p,name)
            if checked!=json.loads((out/(filename+'.readback.json')).read_text()) or checked!=c['jobs'][name]:raise ValueError('read-back regeneration mismatch')
            count+=1
    return dict(numeric_review_files_regenerated=count,all_SHA256_verified=True,lip_contact_exported=False,authorized=False)


README='''# Y900 reconciliation / one-wipe and lip-clearance review

No installed YAML is changed. Current two-pass/high-speed/Y898 files and Spring
v13/F2-C, artistic pressure, S3a, twelve colors and the Z-8 response stay intact.
New files are real numeric G1/G4/M2 REVIEW programs, not physical authorization.

The operator clarifies that PHYSICAL Y0 HAS NOT MOVED: the same mechanical
stopper establishes the lower reference; only the upper assembly was extended
from898 to900. Existing wells, palettes, purge and paper Y coordinates remain
unchanged. This supersedes a home-label-only/+2-offset scenario. NO+2 G54 offset,
station translation or retained898 new-frame alternative is proposed/exported.

The complete separate YAML changes ONLY Y homing mpos898->900 and max_travel
898->900, plus warning comments. X860, XY20000/1500, Z and all homing cycles,
directions/pins/steps/pull-offs/settings are preserved. Nominal Y bounds are
0..900. The physical upper modification is operator-reported; installation,
actual home/read-back and usable-range/end-margin tests remain unperformed.
Existing YAML name/comments are archival, not proof of active settings; do not
follow their obsolete G10 example. Installed YAML is never overwritten here.

Changing the assigned home label does not move fixed stations or automatically
set G54. In the same direction/scale, deltaM at a fixed physical point equals
delta home-label (2mm) minus physical post-home displacement. With G92/TLO0,
W=M-O54. In the reported upper-extension case the physical post-home point also
moves+2 while Y0 stays fixed, so fixed-reference deltaM is expected0 and old
G54 registration stays valid. Confirm with actual controller/home/reference
read-back; do not convert the geometry report into fabricated passing evidence.

| Verification | Expected result | If it disagrees |
|---|---|---|
| Existing mechanical Y0 | MPos/WPos Y0 | stop and inspect reference/config/offset |
| New post-home | MPos=WPos0/900/35 with existing zero offsets | inspect actual config/homing/pull-off/offsets |
| Fixed A2 center | X824.5/Y554.5 unchanged at safe Z35 | investigate; do not automatically translate |

G92 and tool offsets must be inspected, not assumed absent after reboot. If a
fixture moved independently, a common translation cannot fix it. Preserve
canonical artwork; registration correction belongs in measured G54/execution
mapping, never a rewrite of original artistic XY or pressure. A label-only+2
delta would be a different physical scenario; here it is a diagnostic mismatch,
not permission to set G54+2. No automatic coordinate correction is implemented.

One UNCHANGED_Y0 set is delivered. Expected post-home MPos AND WPos are0/900/35;
G54/G92/TLO remain the previously established zero values, subject to inspection.
All station/paper work coordinates and park800/800/35 remain unchanged. Complete
the actual read-back template after manual verification; --record rejects a+2
offset/reference mismatch rather than silently adopting it. Operator-reported
geometry is already recorded; only new installation/read-back/range evidence
remains blank. Record-derived profiles remain nominal, not contact-certified.

Programs: FRAME_AIR (A2 reference + paper outline entirely35), LIP_APPROACH_AIR
(both candidate regions, entirely35), and matched ONE_WIPE_330_AIR, WATER_ONLY,
INK_GOUACHE. All start0/900/35 and park800/800/35/M2. All M0=0; no homing, G10,
G92, probing or offset writes. FRAME_AIR avoids automatic end-limit/stopper tests;
the actual0 and900 margins are manually inspected, not claimed proved by it.

The same40 original depth strokes/order/feeds are preserved. The one-pass
material routine is deep immersion/agitation -> original Y+ withdrawal -> ONE
pressed20mm Y+ wipe at7.5 -> vertical controlled release9 -> vertical lift35.
Lip approach/contact steps are skipped until verified/authorized. This is a
replacement for two-pass wiping, not two passes plus a lip step. Matched Air
raises station motions to35 and paper drawing to15. Water/pigment numeric
commands are identical; prepare contents appropriately. Existing motion remains
dry15000/wet12000 (separate profile15000), draw6000, Z7000/contact2000, hover15,
localoff, transfer35; ink1200/color800 and material feeds/dwells unchanged.

Lip records keep the UNCHANGED Y0 coordinates: inkX815/Y458±10/Z20 and
waterX815/Y298±10/Z20. These are operator-proposed regions, not measured brush
contact. Z20 is NOT a contact measurement or a safe
approach boundary. No generated Air file descends there. Clearance-only X840
to815 is -25mm atZ35/F500, not a measured contact stroke or absolute negativeX.
The historical relative-20 proposal is recorded separately. Proposed first
contact feed300 and relative-1mm are adjustable unapproved suggestions only;
actual contact XYZ, X displacement, feed, release/retract and holder clearance
remain null/unconfirmed. The existing production lip-enable guard stays closed.
No unverified low-speed or high-speed lip-contact G-code is emitted.

Wipe inkY445..465 overlaps lipY448..468 by17mm; its end465 lies in that Y region.
WaterY295..315 overlaps288..308 by13mm, but its end315 lies7mm beyond the region.
Both require release/lift35 before any return toward the lip. X840/Z7.5 wiping
and X815/Z20 candidate lip geometry are distinct; Y overlap proves neither a
shared surface nor contact/holder clearance. Do not extrapolate slope or flatZ9.

Minimal operator sequence: back up actual config; manually select/install/reboot;
home; capture startup active YAML/actual scalar read-back, $I, $G, $# and ?.
Inspect MPos/WPos, G54/G92/TLO. Confirm unchanged mechanical Y0 with a slow
manual/no-contact check without driving into a hard stop. At verified Z35,
slowly approach the SAME fixed A2 reference and check Y554.5, plus existing
paper registration. Verify actual usable0..900/end clearances, then rehome and
capture MPos/WPos0/900/35. If offset/reference/range disagrees, stop and diagnose
the homing/configuration/offset source; do not set G54+2 or remap stations to
hide it. Confirm stopping and exact full-tool corridors
before running a selected review. Prior E-stop absence is not silently resolved.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.y900_lip --output NEW_DIR
Verify: append --verify with existing output. Optional --record
actual.json, --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json.
Record-derived profiles remain nominal reviews; operator read-back is not a
measured contact-volume certificate or stage authorization. Existing official
machine/evidence/collision/physical-export gates remain untouched.
'''


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--record',type=Path)
    ap.add_argument('--machine',type=Path);ap.add_argument('--provenance',type=Path);ap.add_argument('--verify',action='store_true')
    a=ap.parse_args();root=Path(__file__).resolve().parents[2]
    if a.verify:print(json.dumps(verify(root,a.output)))
    else:export(root,a.output,json.loads(a.record.read_text()) if a.record else None,a.machine,a.provenance)
