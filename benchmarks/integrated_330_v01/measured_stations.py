"""Measured XY revision; missing solid-contact Z never becomes guessed contact.

Produces numeric offline reviews, not a bypass of machine authorization.
Unknown shallow-solid contact is explicitly replaced by a Z35 XY rehearsal.
The real production primitive fails closed until its three Z/compliance inputs
are supplied for each well. Original artwork, pressure and S3a are untouched.
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
from datascape.gcode.production.trajectory import emit_station_operation, _station_geometry, shallow_wipe_xy, palette_pattern_xy
from datascape.gcode.production.integrated_benchmark import validate, render_continuous, benchmark_columns
from datascape.gcode.production.exporter import _serialize, _atomic_output, save_json
from .numeric_review import NumericReviewBuilder, BANNER, STATUS, readback_review, xy_route
from .station_final import final_inputs, commanded_seconds

PIN = '20a8070f66bcaea5adc38c67d2ef9dbb64ee9544'
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
    request.update(station_policy='measured_station_v01', benchmark_columns=benchmark_columns(6000),
                   notes='Same forty XY paths/depths/order, Spring-equivalent feeds; unknown shallow-solid Z is NOT extrapolated.')
    d=deepcopy(base.data); v=d['motion']; candidate,reconciliation=controller_candidate(root)
    d['profile_id']='MEASURED-XY-SPRING-MOTION-REVIEW-Z-PENDING'
    d['machine']['machine_bounds_xyz'][1][0]=860
    d['machine']['target_config_sha256']=reconciliation['candidate_sha256']
    d['machine']['target_config_installed']=False
    v.update(ordinary_travel_mm_min=12000, wet_loaded_mm_min=9000, draw_mm_min=6000,
             air_xy_mm_min=6000, z_travel_mm_min=6000, station_approach_mm_min=6000,
             paper_approach_mm_min=6000, paper_contact_mm_min=2000, paper_release_mm_min=2000,
             pressure_z_mm_min=2000, paper_hover_mm=10, station_clearance_mm=35,
             park_xyz=[800,800,35], air_station_top_mm=35, air_station_simulation_z_mm=35,
             benchmark_plan_sha256=digest(request),
             station_phase_limits_mm_min={key:(6000 if key=='reentry' else 1000) for key in PHASE_FEEDS})
    for role in ('ink','water'):
        st=d['stations'][role]; shallow=st['shallow_surface_xyz']; deep=st['deep_surface_xyz']
        y=445 if role=='ink' else 295
        st.update(phase_feeds_mm_min=deepcopy(PHASE_FEEDS), agitation_xy_mm=[15,0],
                  dwell_seconds=2 if role=='ink' else 5,
                  shallow_wipe=dict(enabled=True,start_xy=[840,y],end_xy=[840,y+10],
                    return_xy=[830,(deep[1]+shallow[1])/2],second_pass_x_offset_mm=-10,
                    passes=2,surface_z=None,compression_mm=None,reentry_lift_mm=None,
                    xy_status='operator physically inspected/tested',
                    contact_status='missing actual solid surface/compliance; NOT derived from slope'))
    d['stations']['sponge'].update(dwell_seconds=4,phase_feeds_mm_min=deepcopy(PHASE_FEEDS))
    for slot in mapping['all_registered_centers']:
        st=d['stations'][slot]
        st.update(radius_mm=5,phase_feeds_mm_min=deepcopy(PHASE_FEEDS),dwell_seconds=1,
                  common_geometry_status='nominal common floor/liquid; XY radius/holder space operator-confirmed')
        points=palette_pattern_xy(st); low=min(p[0] for p in points); high=max(p[0] for p in points)
        mapping['slot_assessments'][slot]=dict(center_xy=st['center_xy'],path_x_range=[low,high],
            axis_X860_headroom_mm=860-high, recorded_X850_exceeded=high>850,
            brush_holder_XY_space_operator_confirmed=True, per_slot_liquid_height_measured=False)
    mapping.update(physical_brush_holder_footprint_verified='operator-confirmed relevant XY space; no numeric swept-volume certificate',
        common_model='Existing nominal floor1/liquid6/dip4; NOT newly measured per-slot liquid heights',
        palette_radius_mm=5, controller_target_X_max=860)
    prior.update(source_pin=PIN, X860_physically_measured_reported=True,
        agitation_plus_minus15_XY_and_holder_space_confirmed=True,
        palette_radius5_XY_space_confirmed=True, extended_shallow_XY_space_confirmed=True,
        new_unified_speeds_physically_verified=False,
        extended_solid_surface_Z_compression_reentry_measured=False)
    assumptions.update(station_phase_feeds_mm_min=PHASE_FEEDS, noncontact_station_approach_mm_min=6000,
        dwell_seconds={'ink':2,'water':5,'A2':1,'purge':4},
        agitation={'cycles':1,'x_offset_mm':15,'sequence':'840 -> 825 -> 855 -> 840',
                   'XY_space_operator_confirmed':True,'floor_z_still_nominal':True},
        a2_pattern='operator-confirmed radius5, one circle, 24 segments',
        high_speed_and_minus9_minus10='prior -10 water-only success reported; new unified feeds are candidates',
        unresolved_shallow_contact={role:d['stations'][role]['shallow_wipe'] for role in ('ink','water')},
        review_substitution='Both Paint reviews rehearse unknown solid-wipe XY at Z35; no solid contact is emitted. They are INCOMPLETE contact benchmarks, not run-ready.')
    d['notes']='User-measured XY accepted, actual installed YAML850 retained, X860 candidate pending installation. Separate solid wipe surface/compression/reentry remain null. No passed evidence, calibrated volumes or authorization invented.'
    return request,Profile.from_dict(d),assumptions,prior,mapping,reconciliation,candidate


def build(request,profile,kind):
    validate(request,profile,kind,physical=False)
    v=profile.data['motion']
    if profile.data['status']!='nominal_review' or (
        v['ordinary_travel_mm_min'],v['wet_loaded_mm_min'],v['draw_mm_min'],v['z_travel_mm_min'],
        v['paper_contact_mm_min'],v['pressure_z_mm_min'],v['paper_hover_mm'],v['park_xyz']) != (
            12000,9000,6000,6000,2000,2000,10,[800,800,35]):
        raise ValueError('unified candidate motion policy changed')
    b=NumericReviewBuilder(profile,kind); loaded=None
    def contact(role,action):
        nonlocal loaded
        st=deepcopy(profile.data['stations'][role]); wipe=shallow_wipe_xy(st)
        # Explicit noncontact substitution, ONLY in this offline-review sink.
        # Real production emit_station_operation still rejects missing wipe Z.
        if wipe: st['shallow_wipe']['enabled']=False
        emit_station_operation(b,st,action,'ordinary_travel' if loaded is None else 'wet_loaded',
                               lambda s:_station_geometry(s,tuple))
        for xy in wipe:
            b.move((*xy,35),v['air_xy_mm_min'],'station_wipe_Z_PENDING_NONCONTACT',
                   travel_phase='NONCONTACT_SUBSTITUTION',source_id='station-'+role)
        if wipe: b.marker('solid_wipe_contact_NOT_EMITTED',role+': surface_z/compression_mm/reentry_lift_mm missing; XY at35 only')
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
    checked.update(controller_bounds=check_controller(commands,p,reconciliation),
        commanded_feed_seconds_not_physical_runtime=commanded_seconds(commands,p),
        solid_wipe_contact_emitted=False,contact_benchmark_complete=False,
        station_feeds_by_phase={phase:sorted({c.feed_mm_min for c in commands if c.kind=='move' and c.travel_phase==phase})
                               for phase in (*PHASE_FEEDS,'NONCONTACT_SUBSTITUTION')})
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
            complete_solid_contact_benchmark=False,authorized=False,jobs={})
        executables=[]
        for variant,name in NAMES.items():
            kind='air' if variant=='air' else 'paint'; commands=paths[kind]
            text=(BANNER+'; REQUIRES X860 CONTROLLER CANDIDATE INSTALLATION/READBACK; RECORDED CONFIG STILL X850\n'+
                '; SOLID WIPE CONTACT Z UNKNOWN: XY REHEARSAL AT Z35 ONLY; PAINT CONTACT BENCHMARK INCOMPLETE\n'+
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
        report['authorized'] is not False or report['status']!=STATUS or report['complete_solid_contact_benchmark'] is not False):
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
                actual_installed_X850_conflict_reported=True,solid_contact_Z_pending=True,authorized=False)


README='''# Measured XY benchmark / Spring motion handoff

Numeric G1/G4/M2 offline reviews, not machine authorization. Same forty original
45mm strokes, four columns, original depth order and visits. Drawing6000,
dry12000, wet-main9000 (departure/arrival3000 over5mm retained), noncontactZ6000,
contact/release/pressureZ2000. Paper hover10/local disabled. Consecutive paper
strokes remain at10; station/cross-region access35. Home start0/898/35,
park800/800/35/M2, M0=0. No artwork, pressure or S3a changes.

The operator reports prior stable Air/water-only streaming via UGS TCP and
large-brush strokes to -10. X860, X840+/-15 agitation, radius5 palette/holder
space and extended shallow XY sections are now operator-confirmed, not treated
as arbitrary unmeasured XY expansion. New feeds/material response remain candidates.

Installed YAML still records X850. config.X860.candidate.yaml changes ONLY
axes.x.max_travel_mm to860; original installed bytes/hash and homing/pull-offs
remain unchanged. Runtime installation/readback is pending. Reviews reach855;
they FAIL the recorded850 bound and pass the proposed860 bound with5mm axis
headroom. Right palette radius5 reaches852, with8mm axis headroom. These margins
are axis-reference distances, not invented measured tool-volume certificates.
soft_limits is absent in the original YAML (v4.1.1 source default false); this
patch does not change its state or claim runtime enforcement.

Ink dip8/dwell2s, water dip7/dwell5s, agitation825->855->840, then Y+ slope
withdrawal to the existing shallow reference. Immersion/agitation/withdrawal1000,
palette1000, purge750, approach6000; separately capped, no legacyF60 clamp.
Palette floor1/liquid6/dip4 still nominal, radius5/one24-segment circle/dwell1s.
Purge840/137.5 to0.5, single vertical dab/dwell4s/no rubbing.

Solid wiping is modeled SEPARATELY: ink445->455, water295->305; two passes,
second X830, lifted return toward slope middle402.5/252.5. Actual surface_z,
gentle compression_mm and reentry_lift_mm are missing for EACH well. No old
slope line is extrapolated. Production rejects these nulls before motion.
ALL three review files include this XY at Z35 ONLY. The two Paint files have
real loading/washing/purge/palette and forty paper strokes, but DO NOT perform
the requested solid squeezing/wiping yet: incomplete contact benchmarks, NOT
run-ready final Paint files. WATER_ONLY and INK_GOUACHE numeric commands match.
Once those inputs are supplied, regenerate actual contact through the shared
production primitive and obtain scoped physical authorization; do not edit G-code.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR
Verify: same command with --verify. Checks include regenerated IR, actual numeric
read-back, both controller bounds, axis/Z feeds, 40 strokes, paired XY, dwell,
M0=0/M2 and SHA256. No physical sweep, stopping or speed test is manufactured.
See spring_pipeline.py for the same-profile, canonical-input, gated Spring
Air/SHARED_INK/SHARED_COLOR path; normal paper links10, global transfers35.
'''


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True);ap.add_argument('--verify',action='store_true')
    a=ap.parse_args();print(json.dumps(verify(a.output) if a.verify else export(Path(__file__).resolve().parents[2],a.output),indent=2))
