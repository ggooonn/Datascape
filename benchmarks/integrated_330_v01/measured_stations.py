"""Measured XY and explicit operator-selected shallow-wiping test parameters.

Produces numeric offline reviews, not a bypass of machine authorization.
Paint emits the intended contact; Air lifts the same XY to a noncontact plane.
The extended flat Z9 is an operator-selected assumption, NOT a new measurement.
Original artwork, pressure and S3a are untouched; official gates remain intact.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import re
import difflib

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import emit_station_operation, _station_geometry, shallow_wipe_points, palette_pattern_xy
from datascape.gcode.production.integrated_benchmark import validate, render_continuous, benchmark_columns
from datascape.gcode.production.exporter import _serialize, _atomic_output, save_json
from .numeric_review import NumericReviewBuilder, BANNER, STATUS, readback_review, xy_route
from .station_final import final_inputs, commanded_seconds

PIN = 'f6aca60a24499036c4e17de994abde63c9189839'
NAMES = {'air':'BENCHMARK_330_MEASURED_AIR_REVIEW',
         'water':'BENCHMARK_330_MEASURED_WATER_ONLY_REVIEW',
         'pigment':'BENCHMARK_330_MEASURED_INK_GOUACHE_REVIEW'}
PHASE_FEEDS = dict(immersion=1000, agitation=1000, withdrawal=1000,
                   shallow_contact=750, shallow_wipe=1000, reentry=3000,
                   purge_contact=750, palette_loading=1000)


def controller_candidate(root):
    original = (root/'benchmarks/integrated_330_v01/config.installed.yaml').read_bytes()
    old, new = b'    max_travel_mm: 850.0', b'    max_travel_mm: 860.0'
    if original.count(old) != 1: raise ValueError('installed X850 source changed; inspect before editing')
    candidate = original.replace(old,new,1)
    # Exact byte replacement preserves homing, pull-offs, all other settings,
    # comments and any absent soft_limits field. Source file is never modified.
    report = dict(installed_sha256=hashlib.sha256(original).hexdigest(),
        candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        sole_configuration_change={'axes.x.max_travel_mm':{'from':850,'to':860}},
        installed_recorded_X_max=850, operator_measured_physical_X_max=860,
        candidate_X_max=860, candidate_installed_or_read_back=False,
        operator_confirmed_intended_X_max=860,
        homing_offsets_rates_acceleration_pulloff_unchanged=True,
        soft_limits_key_present=bool(re.search(rb'^\s*soft_limits:',original,re.M)),
        soft_limits_setting_changed=False,
        soft_limits_note='No soft_limits key in recorded YAML; v4.1.1 Axis.h initializes it false. No assertion of runtime enforcement.',
        upstream_source='https://github.com/bdring/FluidNC/blob/v4.1.1/FluidNC/src/Machine/Axis.h',
        remaining_controller_action='Operator installs candidate, restarts/reloads as appropriate, inspects actual X max860, then rehomes and verifies original zero offsets/start. No device I/O here.',
        obsolete_source_comments='Preserved byte-for-byte as historical comments; X850/USB caveats are archival, not new observations.')
    return candidate,report


def inputs(root):
    request, base, assumptions, prior, mapping = final_inputs(root)
    request.update(station_policy='physical_feedback_v01',air_hover_mm=15,benchmark_columns=benchmark_columns(6000),
                   notes='Same forty paths/depths/order. Feedback: hover15/Z7000, pressed wipe20mm, purge1.5 and palette5. Flat9 remains an assumption.')
    d=deepcopy(base.data); v=d['motion']; candidate,reconciliation=controller_candidate(root)
    d['profile_id']='MEASURED-XY-OPERATOR-SHALLOW-TEST-SPRING-MOTION-REVIEW'
    d['machine']['machine_bounds_xyz'][1][0]=860
    d['machine']['target_config_sha256']=reconciliation['candidate_sha256']
    d['machine']['target_config_installed']=False
    v.update(ordinary_travel_mm_min=12000, wet_loaded_mm_min=9000, draw_mm_min=6000,
             air_xy_mm_min=6000, z_travel_mm_min=7000, station_approach_mm_min=7000,
             paper_approach_mm_min=7000, paper_contact_mm_min=2000, paper_release_mm_min=2000,
             pressure_z_mm_min=2000, paper_hover_mm=15, station_clearance_mm=35,
             park_xyz=[800,800,35], air_station_top_mm=35, air_station_simulation_z_mm=35,
             benchmark_plan_sha256=digest(request),
             station_phase_limits_mm_min={key:(6000 if key=='reentry' else 1000) for key in PHASE_FEEDS})
    for role in ('ink','water'):
        st=d['stations'][role]; shallow=st['shallow_surface_xyz']; deep=st['deep_surface_xyz']
        y=445 if role=='ink' else 295
        st.update(phase_feeds_mm_min=deepcopy(PHASE_FEEDS), agitation_xy_mm=[15,0],
                  dwell_seconds=2 if role=='ink' else 5,
                  shallow_wipe=dict(enabled=True,start_xy=[840,y],end_xy=[840,y+20],
                    optional_end_y=y+30,previous_tested_end_y=y+10,
                    new_end_status='operator-requested final trial extension, not yet physically tested',
                    return_xy=[830,(deep[1]+shallow[1])/2],second_pass_x_offset_mm=-10,
                    passes=2,surface_z=9.0,compression_mm=1.5,reentry_lift_mm=10.0,
                    reentry_lift_reference='compressed_contact_target',
                    xy_status='operator physically inspected/tested',
                    contact_status='operator-selected trial; extended flat surface9 assumed from existing shallow endpoint, NOT newly measured'))
    d['stations']['sponge'].update(dwell_seconds=4,compression_mm=0,
        alternate_contact_target_z=1.0,phase_feeds_mm_min=deepcopy(PHASE_FEEDS),
        notes='Operator feedback: prior0.5 too deep; target1.5 equals nominal surface1.5 (zero nominal compression). Optional target1.0 needs separate review.')
    for slot in mapping['all_registered_centers']:
        st=d['stations'][slot]
        st.update(radius_mm=5,immersion_mm=1,phase_feeds_mm_min=deepcopy(PHASE_FEEDS),dwell_seconds=1,
                  common_geometry_status='nominal common floor/liquid; XY radius/holder space operator-confirmed')
        points=palette_pattern_xy(st); low=min(p[0] for p in points); high=max(p[0] for p in points)
        mapping['slot_assessments'][slot]=dict(center_xy=st['center_xy'],path_x_range=[low,high],
            axis_X860_headroom_mm=860-high, recorded_X850_exceeded=high>850,
            brush_holder_XY_space_operator_confirmed=True, per_slot_liquid_height_measured=False)
    mapping.update(physical_brush_holder_footprint_verified='operator-confirmed relevant XY space; no numeric swept-volume certificate',
        common_model='Common nominal floor1/liquid6, corrected dip5/immersion1; equivalent geometry only, NOT per-slot measured liquid heights',
        palette_radius_mm=5, controller_target_X_max=860)
    prior.update(source_pin=PIN, X860_physically_measured_reported=True,
        agitation_plus_minus15_XY_and_holder_space_confirmed=True,
        palette_radius5_XY_space_confirmed=True, extended_shallow_XY_space_confirmed=True,
        previous_revision_both_Paint_completed_UGS_TCP=True,
        previous_revision_higher_feeds_Z35_palette_visits_successful=True,
        previous_revision_vibration_noise_acceptable=True,
        previous_revision_wiping_mechanical_success_but_water_removal_weak=True,
        previous_revision_purge_too_deep=True,
        new_hover15_Z7000_and_other_feedback_refinements_physically_verified=False,
        shallow_wiping_test_parameters_operator_selected=True,
        extended_solid_surface_Z_compression_reentry_measured=False)
    assumptions.update(station_phase_feeds_mm_min=PHASE_FEEDS, noncontact_station_approach_mm_min=7000,
        dwell_seconds={'ink':2,'water':5,'A2':1,'purge':4},
        agitation={'cycles':1,'x_offset_mm':15,'sequence':'840 -> 825 -> 855 -> 840',
                   'XY_space_operator_confirmed':True,'floor_z_still_nominal':True},
        a2_pattern='operator-confirmed radius5, one circle, 24 segments',
        high_speed_and_minus9_minus10='Both pinned Paint jobs and higher feeds operated successfully per operator; new Z7000/hover15 refinements remain candidates',
        shallow_contact_test_settings={role:d['stations'][role]['shallow_wipe'] for role in ('ink','water')},
        calculated_shallow_contact_Z=7.5,calculated_reentry_Z=17.5,
        review_substitution='None in Paint: actual intended two-pass contact is emitted. Air alone elevates station XY to35.',
        extended_shallow_surface_status='operator-assumed constant G54Z9 from existing shallow reference; NOT a newly measured extended surface')
    assumptions['calculated_review_coordinates_G54']['A2']['dip_z']=5
    assumptions['purge'].update(target_G54_z=1.5,compression_mm=0,alternate_target_G54_z=1.0)
    assumptions['a2_initial_immersion_mm']=1
    prior['new_Z35_station_phase_agitation_purge_pigment_policy_verified']=False
    prior['previous_revision_success_is_operator_report_not_current_scoped_authorization']=True
    assumptions['pressed_wiping_length_mm']=20
    assumptions['weak_wiping_diagnosis']='Prior pressed passes were10mm. New passes20mm; actual contact force/surface mismatch remains separate and is NOT solved by increasing compression.'
    d['notes']='Both pinned Paint trials successful per operator, with saturated-brush Z10 trails, weak wiping and deep purge. Final corrections: hover15/Z7000, wipe20 at unchanged7.5, purge1.5, palettes5. X860 installation/readback still unreported; no passing authorization or measured volumes invented.'
    return request,Profile.from_dict(d),assumptions,prior,mapping,reconciliation,candidate


def build(request,profile,kind):
    validate(request,profile,kind,physical=False)
    v=profile.data['motion']
    if profile.data['status']!='nominal_review' or (
        v['ordinary_travel_mm_min'],v['wet_loaded_mm_min'],v['draw_mm_min'],v['z_travel_mm_min'],
        v['paper_contact_mm_min'],v['pressure_z_mm_min'],v['paper_hover_mm'],v['park_xyz']) != (
            12000,9000,6000,7000,2000,2000,15,[800,800,35]):
        raise ValueError('unified candidate motion policy changed')
    b=NumericReviewBuilder(profile,kind); loaded=None
    def contact(role,action):
        nonlocal loaded
        st=profile.data['stations'][role]
        # The shared production grammar emits every intended contact/re-entry.
        # This numeric REVIEW sink adds axis/rate checks, not invented calibrated
        # contact boxes. Official emitter defaults still require actual volumes.
        emit_station_operation(b,st,action,'ordinary_travel' if loaded is None else 'wet_loaded',
                               lambda s:_station_geometry(s,tuple),
                               lambda s:shallow_wipe_points(s,tuple))
        b.marker(action,role); loaded=role
    render_continuous(request,profile,b,kind,contact if kind=='paint' else None)
    if any(c.kind not in ('move','dwell','marker') for c in b.commands): raise ValueError('unresolved numeric command or pause')
    return b.commands


def check_controller(commands,profile,reconciliation):
    positions=[profile.data['machine']['start_work_xyz']]+[c.xyz for c in commands if c.kind=='move']
    maximum=max(p[0] for p in positions)
    return dict(candidate_X860_axis_bounds_pass=True, maximum_commanded_X=maximum,
        candidate_X860_axis_reference_margin_mm=860-maximum,
        recorded_installed_X850_bounds_pass=maximum<=850,
        endpoints_exceeding_recorded_X850=sum(p[0]>850 for p in positions),
        actual_controller_configuration_reconciled=False,
        required_candidate_sha256=reconciliation['candidate_sha256'],
        note='Checks against proposed860 do not prove installation, soft-limit enforcement or collision clearance.')


def job_check(text,commands,p,kind,reconciliation):
    checked=readback_review(text,commands,p,kind)
    wiping=[(i,c) for i,c in enumerate(commands) if c.kind=='move' and c.travel_phase=='shallow_wipe']
    lengths=[]
    if kind=='paint':
        expected=[];planes=[]
        for role in ('ink','ink','water'):
            w=p.data['stations'][role]['shallow_wipe'];contact=w['surface_z']-w['compression_mm']
            clear=contact+w['reentry_lift_mm'];x=w['start_xy'][0]
            expected += [(x,w['end_xy'][1],contact),(x+w['second_pass_x_offset_mm'],w['end_xy'][1],contact)]
            planes += [(w['surface_z'],clear)]*2
            lengths += [w['end_xy'][1]-w['start_xy'][1]]*2
        if [c.xyz for _,c in wiping]!=expected:raise ValueError('two-pass wiping contact sequence mismatch')
        for n,(i,c) in enumerate(wiping):
            surface,clear=planes[n];after=[row for row in commands[i+1:] if row.kind=='move']
            if after[0].xyz!=(*c.xyz[:2],surface) or after[0].travel_phase!='shallow_contact':
                raise ValueError('wipe must release vertically at controlled contact feed')
            lifted=clear if n%2==0 else p.data['motion']['station_clearance_mm']
            if after[1].xyz!=(*c.xyz[:2],lifted):raise ValueError('vertical lift must precede lateral re-entry/transfer')
            if n%2==0 and after[2].xyz!=expected[n+1][:2]+(clear,):raise ValueError('X offset must follow complete vertical lift')
            before=next(row for row in reversed(commands[:i]) if row.kind=='move')
            if before.xyz!=(c.xyz[0],c.xyz[1]-lengths[n],c.xyz[2]):raise ValueError('pressed Y+ wiping length/height mismatch')
        previous=p.data['machine']['start_work_xyz'];active_role=None
        for c in commands:
            if c.kind=='marker' and c.action=='benchmark_station_visit':active_role=c.message.split(':')[0]
            if c.kind=='move':
                if c.travel_phase=='reentry' and tuple(previous[:2])!=c.xyz[:2]:
                    w=p.data['stations'][active_role]['shallow_wipe']
                    clear=w['surface_z']-w['compression_mm']+w['reentry_lift_mm']
                    if min(previous[2],c.xyz[2])<clear:
                        raise ValueError('lateral re-entry below lifted plane')
                previous=c.xyz
    elif wiping:raise ValueError('Air contains solid wiping contact')
    v=p.data['motion']
    paper_hover=[c for c in commands if c.kind=='move' and c.action=='paper_hover' and c.xyz[0]<=330 and c.xyz[1]<=330]
    if not paper_hover or any(c.xyz[2]!=v['paper_hover_mm'] for c in paper_hover):raise ValueError('paper hover height mismatch')
    if any(c.kind=='move' and c.action in ('lift','retract','approach','paper_hover','park','station_approach') and
           c.feed_mm_min!=v['z_travel_mm_min'] for c in commands):raise ValueError('noncontact Z feed mismatch')
    checked.update(controller_bounds=check_controller(commands,p,reconciliation),
        commanded_feed_seconds_not_physical_runtime=commanded_seconds(commands,p),
        solid_wipe_contact_emitted=kind=='paint',contact_benchmark_complete=kind=='paint',
        shallow_wiping_passes=len(wiping),pressed_wiping_lengths_mm=lengths,vertical_lift_before_X_offset_verified=kind=='paint',
        paper_hover_mm=v['paper_hover_mm'],noncontact_Z_feed_mm_min=v['z_travel_mm_min'],
        purge_target_z=p.data['stations']['sponge']['surface_z']-p.data['stations']['sponge']['compression_mm'],
        palette_dip_z=p.data['stations']['A2']['liquid_reference_z']-p.data['stations']['A2']['immersion_mm'],
        wiping_parameters={role:dict(surface_z=p.data['stations'][role]['shallow_wipe']['surface_z'],
            contact_z=p.data['stations'][role]['shallow_wipe']['surface_z']-p.data['stations'][role]['shallow_wipe']['compression_mm'],
            reentry_z=p.data['stations'][role]['shallow_wipe']['surface_z']-p.data['stations'][role]['shallow_wipe']['compression_mm']+p.data['stations'][role]['shallow_wipe']['reentry_lift_mm']) for role in ('ink','water')},
        extended_surface_newly_measured=False,
        station_feeds_by_phase={phase:sorted({c.feed_mm_min for c in commands if c.kind=='move' and c.travel_phase==phase})
                               for phase in PHASE_FEEDS})
    return checked


def export(root,output):
    request,p,assumptions,prior,mapping,reconciliation,candidate=inputs(root)
    paths={kind:build(request,p,kind) for kind in ('air','paint')}
    if xy_route(paths['air'])!=xy_route(paths['paint']): raise ValueError('Air/Paint XY mismatch')
    def write(out):
        for name,obj in [('plan.json',request),('profile.review.json',p.data),('nominal_assumptions.json',assumptions),
            ('operator_observations.json',prior),('spring_palette_mapping.json',mapping),('controller_reconciliation.json',reconciliation)]:
            save_json(out/name,obj)
        (out/'config.X860.candidate.yaml').write_bytes(candidate)
        original=(root/'benchmarks/integrated_330_v01/config.installed.yaml').read_text()
        (out/'config.X860.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),candidate.decode().splitlines(True),
            fromfile='config.installed.yaml',tofile='config.X860.candidate.yaml')))
        report=dict(schema='datascape.measured_station_review.v0.3',status=STATUS,source_pin=PIN,
            plan_sha256=digest(request),profile_sha256=p.sha256,paired_XY_identical=True,
            original_40_geometry_depth_order_preserved=True, drawing_feed_intentionally_changed_to6000=True,
            complete_solid_contact_benchmark=True,extended_surface_newly_measured=False,authorized=False,jobs={})
        executables=[]
        for variant,name in NAMES.items():
            kind='air' if variant=='air' else 'paint'; commands=paths[kind]
            text=(BANNER+'; REQUIRES X860 CONTROLLER CANDIDATE INSTALLATION/READBACK; RECORDED CONFIG STILL X850\n'+
                ('; AIR ONLY: STATION XY AT Z35; NO CONTACT\n' if kind=='air' else
                 '; OPERATOR TEST ASSUMPTION: FLAT SURFACE Z9 / COMPRESSION1.5 / CONTACT7.5 / LIFT10 TO17.5\n')+
                '; FILL: '+('NO CONTACT - AIR ONLY' if variant=='air' else
                    'WATER IN WELL_2 AND A2, CLEAN WATER WELL_1' if variant=='water' else 'INK WELL_2, GOUACHE A2, CLEAN WATER WELL_1')+'\n'+
                _serialize(commands,p,digest(request),name,'offline_review'))
            (out/(name+'.gcode')).write_text(text)
            checked=job_check(text,commands,p,kind,reconciliation)
            save_json(out/(name+'.readback.json'),checked); report['jobs'][name]=checked
            if variant!='air':executables.append('\n'.join(r for r in text.splitlines() if not r.startswith(';')))
        if executables[0]!=executables[1]:raise ValueError('Water/pigment numeric commands differ')
        report['water_pigment_executable_sha256']=hashlib.sha256(executables[0].encode()).hexdigest()
        for kind,commands in paths.items():save_json(out/(kind+'.trajectory.json'),[asdict(c) for c in commands])
        save_json(out/'verification.json',report)
        (out/'README.md').write_text(README)
        return report
    return _atomic_output(output,write)


def verify(output):
    out=Path(output); hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(hashes)!={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}:
        raise ValueError('manifest coverage mismatch')
    for name,sha in hashes.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha:raise ValueError('SHA256 mismatch')
    request=json.loads((out/'plan.json').read_text()); p=Profile.load(out/'profile.review.json')
    report=json.loads((out/'verification.json').read_text()); reconciliation=json.loads((out/'controller_reconciliation.json').read_text())
    if (report['plan_sha256']!=digest(request) or report['profile_sha256']!=p.sha256 or
        report['authorized'] is not False or report['status']!=STATUS or report['complete_solid_contact_benchmark'] is not True or
        report['extended_surface_newly_measured'] is not False):
        raise ValueError('review binding mismatch')
    candidate_sha=hashlib.sha256((out/'config.X860.candidate.yaml').read_bytes()).hexdigest()
    if candidate_sha!=reconciliation['candidate_sha256'] or candidate_sha!=p.data['machine']['target_config_sha256']:
        raise ValueError('controller candidate binding mismatch')
    paths={k:build(request,p,k) for k in ('air','paint')}
    if xy_route(paths['air'])!=xy_route(paths['paint']):raise ValueError('paired route mismatch')
    for k,commands in paths.items():
        if digest(json.loads((out/(k+'.trajectory.json')).read_text()))!=digest([asdict(c) for c in commands]):
            raise ValueError('trajectory regeneration mismatch')
    executable=[]
    for variant,name in NAMES.items():
        kind='air' if variant=='air' else 'paint'; commands=paths[kind]
        text=(out/(name+'.gcode')).read_text()
        checked=job_check(text,commands,p,kind,reconciliation)
        saved=json.loads((out/(name+'.readback.json')).read_text())
        if saved!=checked or saved!=report['jobs'][name]:raise ValueError('readback mismatch')
        if variant!='air':executable.append('\n'.join(r for r in text.splitlines() if not r.startswith(';')))
    if executable[0]!=executable[1] or hashlib.sha256(executable[0].encode()).hexdigest()!=report['water_pigment_executable_sha256']:
        raise ValueError('water/pigment executable hash mismatch')
    return dict(SHA256_files_verified=len(hashes),trajectories_regenerated=True,M0_count=0,
                actual_installed_X850_conflict_reported=True,solid_contact_Z_pending=False,
                Paint_two_pass_contact_verified=True,operator_assumed_surface_not_newly_measured=True,authorized=False)


README="# Final physical-feedback benchmark and Spring handoff\n\nActual numeric REVIEW commands, not authorized physical exports. Both previous\nPaint variants at pinned f6aca60a were successfully run over UGS TCP according\nto the operator: higher feeds, station visits, Z35 and palette loading worked;\nvibration/noise acceptable. New refinements below remain awaiting confirmation.\nNo controller configuration readback or exact attained speed is inferred.\n\nSame original40 strokes/depth order/visits. Ordinary12000, wet-main9000,\ndrawing6000, noncontact Z/approach7000, paper contact/release/pressureZ2000.\nNormal paper hover15, local disabled; no per-strokeZ35 round trips. Station and\ncross-region clearance35. Home start0/898/35; park800/800/35/M2; M0=0.\nExisting wet departure/arrival3000 over5mm and separate station feeds retained.\n\nBoth shallow passes are now PRESSED20mm atZ7.5: ink445->465, water295->315.\nOptional endpoints475/325 are configurable candidates, not defaults. Surface9\nand compression1.5 stay operator assumptions; no blind slope extrapolation.\nFirst pass X840, controlled release to9, vertical lift to17.5 BEFORE X-10,\nlifted return via middleY402.5/252.5, second passX830, release and retract35.\nPrior pressed passes were only10mm. Doubling distance does not prove actual\nsurface contact; insufficient contact/force remains a separate possible cause\nof weak removal. Compression is not increased automatically.\n\nPurge840/137.5, target1.5, dwell4s, one vertical dab, no rubbing. Nominal\nsurface1.5 implies ZERO nominal compression; target1.0 is an explicit alternate\nif later selected, not automatic fallback. Negative compression is rejected.\nAll registered palettes keep radius5/feeds/centers; common equivalent geometry\nuses liquid6 minus immersion1 -> dip5, instead of prior dip4. No new per-slot\nmeasured liquid height is invented. Ink dwell2s, water5s unchanged.\n\nX860 candidate YAML is byte-identical to pinned PR31 and changes only X max\ntravel versus recorded installed850. The operator's intended860 and physical\nreach are retained; installation/readback/homing verification are STILL\nunreported. Reviews reach855, pass candidate860 bounds and explicitly fail the\nrecorded850 bound. Formal profile/evidence/authorization gates stay intact.\n\nMatched Air: paper strokes15 and station XY35, no paper/liquid/stone/cloth\ncontact. WATER_ONLY and INK_GOUACHE numeric commands match and include actual\nwiping, purge and loading, not Z35-only Paint substitutes. Verification covers\nregeneration, bounds/feeds, actual15/7000, pressed length/height, lift-before-X,\n40 strokes, M0=0, finalpark/M2, read-back and SHA256.\n\nReproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR\nVerify: same command with --verify. Original source-plan hover10/5 metadata is\nretained provenance, not this version's execution height.\n\nCanonical Spring inputs have now been recovered with the byte-verified PR25\nadapter and exact existing machine/provenance SHA256s. Full LayoutD plan readback\npreserves14951 unsplit sources/240974 pressure samples/50 continuous X300\ncrossings and S3a. spring_runtime.py compares hover10/Z6000, hover15/Z6000 and\nhover15/Z7000 on FULL synchronized trajectories with existing material visits,\nreloads and separate jobs. Estimates are not measured runtimes or safety tests.\nAfter final refinement feedback, the same-profile spring_pipeline exports Air,\nSHARED_INK and SHARED_COLOR through the official gates and verifier. No preview\nfiles are substituted for requested authorized Spring executions.\n"


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True);ap.add_argument('--verify',action='store_true')
    a=ap.parse_args();print(json.dumps(verify(a.output) if a.verify else export(Path(__file__).resolve().parents[2],a.output),indent=2))
