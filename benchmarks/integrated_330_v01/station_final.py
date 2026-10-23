"""Final station correction: paired physical-material reviews and revised dry Air.

Prior successful motion is recorded as operator observation. New material,
purge and station candidates do not become authorized physical evidence.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from math import dist
import hashlib
import json

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile, vector
from datascape.gcode.production.trajectory import _station_geometry, emit_station_operation, palette_pattern_xy
from datascape.gcode.production.integrated_benchmark import validate, render_continuous
from datascape.gcode.production.exporter import _atomic_output, _serialize, save_json
from studies.local_hover_v01.config import historical_xy
from .handoff import execution_request
from .numeric_review import nominal_profile, NumericReviewBuilder, readback_review, xy_route, BANNER, STATUS

PIN = '42bff2398f9394e9840a291b5a1c48567f575a95'
SLOTS = ('A2','A3','A4','A5','C1','C2','C3','C4','D1','D2','D4','D5')
NAMES = {'air':'BENCHMARK_330_STATION_AIR_REVIEW',
         'water':'BENCHMARK_330_WATER_ONLY_REVIEW', 'pigment':'BENCHMARK_330_INK_GOUACHE_REVIEW'}


def final_inputs(root):
    request = execution_request(root)
    request.update(station_policy='final_station_v01', include_cloth=True,
                   air_station_roles=['ink','water','sponge','A2'])
    request['notes'] = 'Unchanged forty strokes at F5000; final Z35 access, phase feeds, one centered purge; Air then water-only then ink/gouache.'
    base, assumptions = nominal_profile(root); d = deepcopy(base.data)
    v = d['motion']
    v.update(station_clearance_mm=35, park_xyz=[800,800,35], air_station_top_mm=35, contact_mm_min=1000,
             air_station_simulation_z_mm=32, air_station_roles=request['air_station_roles'],
             benchmark_plan_sha256=digest(request),
             station_phase_limits_mm_min={'immersion':1000,'agitation':1000,'withdrawal':1000,'purge_contact':500})
    feeds = {'immersion':750,'agitation':500,'withdrawal':1000,'purge_contact':500}
    for role in ('ink','water'):
        d['stations'][role].update(feed_mm_min=750, phase_feeds_mm_min=deepcopy(feeds), approach_z=12,
            agitation_cycles=1, agitation_bidirectional=True, agitation_xy_mm=[0.5,0],
            agitation_floor_max_z=4, dwell_seconds=1.5 if role=='ink' else 3)
    d['stations']['ink']['immersion_mm'] = 1  # selected nominal liquid9 -> tip8
    cloth = d['stations']['sponge']
    cloth.update(status='nominal_review', coordinate_frame='G54', center_xy=[840,137.5],
                 surface_z=1.5, compression_mm=1, approach_z=3.5, dwell_seconds=.75,
                 feed_mm_min=500, phase_feeds_mm_min=deepcopy(feeds), wipe_xy_mm=[0,0],
                 repetitions=1, contact_box_xyz=None)
    a2 = d['stations']['A2']
    a2.update(feed_mm_min=750, phase_feeds_mm_min=deepcopy(feeds), approach_z=8, dwell_seconds=1)
    xy = historical_xy(root/'hardware/fluidnc/tool_coordinates.yaml')
    palettes = {key:value for key,value in xy.items() if 'y' in value and key not in ('PURGE',)}
    mapping = {'source':'hardware/fluidnc/tool_coordinates.yaml',
               'source_sha256':hashlib.sha256((root/'hardware/fluidnc/tool_coordinates.yaml').read_bytes()).hexdigest(),
               'all_registered_centers':{slot:[ref['x'],ref['y']] for slot,ref in palettes.items()},
               'spring_12_slots':list(SLOTS), 'slot_assessments':{},
               'common_model':'A2 nominal floor1/liquid6/dip4, not per-slot measured equivalence',
               'physical_brush_holder_footprint_verified':False}
    for slot, ref in palettes.items():
        st = deepcopy(a2)
        st.update(hardware_id=slot, center_xy=[ref['x'],ref['y']],
                  common_geometry_status='shared nominal candidate; confirm physical equivalence before production')
        d['stations'][slot] = st
        points = [tuple(st['center_xy']), *palette_pattern_xy(st)]
        xmax = max(p[0] for p in points)
        mapping['slot_assessments'][slot] = {
            'center_xy':st['center_xy'], 'path_x_range':[min(p[0] for p in points),xmax],
            'axis_X850_headroom_mm':850-xmax,
            'full_brush_holder_clearance_verified':False,
            'note':'axis-reference path fits; headroom is NOT a measured physical brush/holder gap'}
    if set(d['material']['color_order']) != set(SLOTS): raise ValueError('Spring palette set changed')
    mapping['preserved_Spring_color_order'] = d['material']['color_order']
    assumptions.update(station_contact_feed_mm_min=None, station_dwell_seconds=None,
        station_phase_feeds_mm_min=feeds, station_clearance_mm=35, final_park_xyz=[800,800,35],
        noncontact_station_approach_mm_min=3000,
        approach_z={'ink':12,'water':12,'palettes':8,'purge':3.5},
        dwell_seconds={'ink':1.5,'water':3,'A2':1,'purge':.75},
        ink_dip_G54_z=8, alternate_ink_dip_G54_z=9,
        ink_dip_note='Z8 gives 1..2mm nominal immersion for actual level9..10; Z9 is not the default',
        agitation={'cycles':1,'x_offset_mm':.5,'sequence':'center -> X-0.5 -> X+0.5 -> center',
                   'actual_stone_interior_and_brush_fit_verified':False},
        purge={'surface_bed_z_range':[2,3],'surface_G54_z_range':[1,2],
               'selected_surface_G54_z':1.5,'target_G54_z':.5,'compression_mm':1,
               'single_vertical_dab':True,'lateral_rubbing':False,'precision_measurement':False})
    assumptions['calculated_review_coordinates_G54']['ink']['dip'] = [840,380,8]
    assumptions['well_initial_immersion_mm'] = {'ink':1,'water':2}
    prior = {'status':'operator_reported_success','source_pin':PIN,'transport':'UGS TCP',
             'existing_Air_and_water_only_Paint_completed':True,'XYZ_stable_reported':True,
             'large_baegunmo_strokes_to_G54_minus10_successful':True,
             'new_Z35_station_phase_agitation_purge_pigment_policy_verified':False,
             'streamed_byte_hash_and_timing_not_supplied':True,
             'not_a_new_profile_scoped_passed_authorization':True}
    d['notes'] = ('Prior Air/water-only benchmark successful via UGS TCP, stable XYZ and -10 strokes reported. '
                  'New Z35 station access, immersion/agitation/withdrawal feeds and purge are candidates. '
                  'No invented contact/free-space volume or passed evidence. Full Spring palette centers reused; '
                  'A2 shared nominal model and X847 full-tool clearance remain separately unverified.')
    return request, Profile.from_dict(d), assumptions, prior, mapping


def build_final(request, profile, kind):
    validate(request, profile, kind, physical=False)
    if profile.data['status'] != 'nominal_review': raise ValueError('review status required')
    v = profile.data['motion']
    if (v['draw_mm_min'],v['ordinary_travel_mm_min'],v['wet_loaded_mm_min'],v['z_travel_mm_min'],
        v['pressure_z_mm_min'],v['station_clearance_mm']) != (5000,8000,8000,3000,2000,35):
        raise ValueError('final benchmark baseline changed')
    b = NumericReviewBuilder(profile, kind); loaded = None
    def contact(role, action):
        nonlocal loaded
        def geometry(st):
            def point(p):
                if not vector(p): raise ValueError('incomplete nominal station geometry')
                return tuple(p)
            return _station_geometry(st, point)
        emit_station_operation(b, profile.data['stations'][role], action,
                               'ordinary_travel' if loaded is None else 'wet_loaded', geometry)
        b.marker(action, role); loaded = role
    render_continuous(request, profile, b, kind, contact if kind=='paint' else None)
    if any(c.kind not in ('move','dwell','marker') for c in b.commands): raise ValueError('unexpected pause/unresolved action')
    return b.commands


def export_final(root, output):
    request, p, assumptions, prior, mapping = final_inputs(root)
    paths = {kind:build_final(request,p,kind) for kind in ('air','paint')}
    if xy_route(paths['air']) != xy_route(paths['paint']): raise ValueError('paired Air route changed')
    def write(out):
        for name,data in [('plan.json',request),('profile.nominal.json',p.data),('nominal_assumptions.json',assumptions),
                          ('prior_observations.json',prior),('spring_palette_mapping.json',mapping)]: save_json(out/name,data)
        report = {'schema':'datascape.station_final_review.v0.3','status':STATUS,'source_pin':PIN,
                  'plan_sha256':digest(request),'profile_sha256':p.sha256,
                  'unchanged_40_stroke_source_sha256':digest(request['benchmark_columns']),
                  'water_pigment_executable_commands_identical':True,'paired_Air_XY_identical':True,
                  'prior_observations':prior,'authorized':False,'jobs':{}}
        text_rows = []
        for variant,name in NAMES.items():
            kind = 'air' if variant=='air' else 'paint'; commands=paths[kind]
            text = (BANNER+'; PRIOR XYZ/-10 SUCCESS OPERATOR-REPORTED; REVISED STATIONS/PURGE ARE CANDIDATES\n'+
                    '; FILL: '+('WATER in WELL_2 and A2; clean water WELL_1' if variant=='water' else
                    'INK WELL_2 / GOUACHE A2 / clean water WELL_1' if variant=='pigment' else 'DRY AIR ONLY')+'\n'+
                    _serialize(commands,p,digest(request),name,'offline_review'))
            (out/(name+'.gcode')).write_text(text)
            checked=readback_review(text,commands,p,kind)
            checked['commanded_feed_seconds_not_physical_runtime']=commanded_seconds(commands,p)
            checked['phase_feeds_present_mm_min']=sorted({c.feed_mm_min for c in commands if c.action.startswith('station_') and c.kind=='move'})
            save_json(out/(name+'.readback.json'),checked); report['jobs'][name]=checked
            if variant!='air': text_rows.append('\n'.join(r for r in text.splitlines() if not r.startswith(';')))
        if text_rows[0]!=text_rows[1]: raise ValueError('water/pigment executable commands differ')
        report['water_pigment_executable_sha256']=hashlib.sha256(text_rows[0].encode()).hexdigest()
        for kind,commands in paths.items(): save_json(out/(kind+'.trajectory.json'),[asdict(c) for c in commands])
        save_json(out/'verification.json',report)
        (out/'README.md').write_text('''# Final station benchmark review

Real numeric G-code, not physically authorized. Prior Air/water-only motion and
-10 strokes succeeded via UGS TCP according to the operator. New station feeds,
agitation, purge and pigment response remain candidates. No repeated hardware
questions or new palette mapping study: all 20 centers are read from the existing
YAML; the existing 12 Spring slots/order are preserved.

Start X0 Y898 Z35 after homing; final X800 Y800 Z35/M2. Same forty strokes,
F5000 drawing, F8000 dry/wet-main XY, F3000 noncontact Z, F2000 pressure-Z cap,
hover10/local disabled, zero M0. Station access always retracts vertically to35
before XY, then approaches vertically. Air uses a noncontact Z32 simulation
plane after Z35 travel. WATER_ONLY and INK_GOUACHE executable commands match.

Approach F3000 to wellZ12/paletteZ8/clothZ3.5, immersion750, agitation500,
withdrawal1000, cloth500. Explicit phase caps replace the legacy F60 clamp for
these profiles; legacy profiles retain their old clamp. Ink dipZ8/dwell1.5s,
water dipZ7/dwell3s, one +/-0.5mm X agitation cycle, Y+ rising withdrawal. A2
dipZ4, radius1 circle, dwell1s. Purge one centered X840/Y137.5 dab toZ0.5,
dwell0.75s, controlled release; no rubbing. All new dimensions/feeds are explicit
nominal candidates, not precision measurements or certified stone interior fit.

X847 palette radius1 reachesX848, leaving2mm of axis-reference travel. That
number is NOT actual brush/holder clearance; full-tool fit and common A2 model
equivalence must be checked before production. No new collision-free volumes
or measured pressure curve are invented. See spring_palette_mapping.json.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.station_final --output NEW_DIR
Verify: same command with --verify. Checks: configured axis bounds, per-axis/Z
feeds, regenerated sequence/read-back/SHA256, forty strokes, M0=0, park/M2.
After water then pigment results, apply only necessary parameter refinements
to existing profiles; full Spring Air -> SHARED_INK / SHARED_COLOR, preserving
v13/F2-C/Pressure Intent/S3a. Official physical authorization gates stay intact.
''')
        return report
    return _atomic_output(output,write)


def commanded_seconds(commands,profile):
    position=profile.data['machine']['start_work_xyz']; total=0
    for c in commands:
        if c.kind=='move': total+=dist(position,c.xyz)/c.feed_mm_min*60; position=c.xyz
        elif c.kind=='dwell': total+=c.seconds
    return total


def verify_final(output):
    out=Path(output); hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(hashes)!={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}:
        raise ValueError('manifest coverage mismatch')
    for name,sha in hashes.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha: raise ValueError('SHA256 mismatch')
    request=json.loads((out/'plan.json').read_text()); profile=Profile.load(out/'profile.nominal.json')
    report=json.loads((out/'verification.json').read_text())
    if report.get('status')!=STATUS or report.get('authorized') is not False: raise ValueError('not an authorized machine package')
    if report['plan_sha256']!=digest(request) or report['profile_sha256']!=profile.sha256: raise ValueError('binding mismatch')
    paths={kind:build_final(request,profile,kind) for kind in ('air','paint')}
    if xy_route(paths['air'])!=xy_route(paths['paint']): raise ValueError('Air route mismatch')
    for kind,commands in paths.items():
        if digest(json.loads((out/(kind+'.trajectory.json')).read_text()))!=digest([asdict(c) for c in commands]):
            raise ValueError('trajectory regeneration mismatch')
    executable=[]
    for variant,name in NAMES.items():
        kind='air' if variant=='air' else 'paint'; commands=paths[kind]
        text=(out/(name+'.gcode')).read_text(); checked=readback_review(text,commands,profile,kind)
        checked['commanded_feed_seconds_not_physical_runtime']=commanded_seconds(commands,profile)
        checked['phase_feeds_present_mm_min']=sorted({c.feed_mm_min for c in commands if c.action.startswith('station_') and c.kind=='move'})
        if checked!=report['jobs'][name] or checked!=json.loads((out/(name+'.readback.json')).read_text()): raise ValueError('readback report mismatch')
        if variant!='air': executable.append('\n'.join(r for r in text.splitlines() if not r.startswith(';')))
    if executable[0]!=executable[1] or hashlib.sha256(executable[0].encode()).hexdigest()!=report['water_pigment_executable_sha256']:
        raise ValueError('material variants changed executable commands')
    return {'SHA256_files_verified':len(hashes),'regenerated':True,'water_pigment_commands_identical':True,'authorized':False}


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',required=True); ap.add_argument('--verify',action='store_true')
    a=ap.parse_args(); result=verify_final(a.output) if a.verify else export_final(Path(__file__).resolve().parents[2],a.output)
    print(json.dumps(result,indent=2))
