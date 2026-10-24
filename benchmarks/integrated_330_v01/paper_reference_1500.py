"""Corrected brush first-touch reference and one1500mm compression benchmark.

The reference applies ONLY to paper. Absolute station/controller coordinates and
canonical Spring pressure/geometry/order are unchanged. No hardware I/O.
"""
from copy import deepcopy
from dataclasses import asdict
from math import dist, hypot
from pathlib import Path
import csv
import hashlib
import io
import json

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import _atomic_output, _serialize, _MOVE, _DWELL, save_json
from . import final_ink_endurance as previous
from . import final_lip
from .high_speed import _draw, elevated_air
from .numeric_review import BANNER, STATUS, check_move, xy_route
from .spring_runtime import RuntimeBuilder, RuntimeMaterials
from .y900_lip import spring_dependencies

PIN='1c4007f79c16a004db6db423e347fa7d11e5a1ef'
STEM='INK_1500_PAPER_Z10_COMP1_15_'
PAPER_ACTIONS=('paper_hover','approach','initial_contact','calibration_compression','draw',
               'release','paper_release_clearance','retract')


def profile(root,first_touch=10):
    d=deepcopy(previous.profile(root).data)
    d['profile_id']='PAPER-FIRST-TOUCH10-COMPRESSION1-15-INK1500-REVIEW'
    for brush in d['brush_profiles'].values():
        brush['paper_first_touch_z_mm']=first_touch
        brush['notes']='First-touch approximately G54Z10 operator-reported for current brush. Existing signed Z-8 knots are HISTORICAL/PROVISIONAL COMPRESSION OFFSETS ONLY, not selected Spring physical calibration. Final pressure distribution awaits this1..15mm benchmark and brush selection; no3..15mm normalization chosen.'
    d['motion'].update(paper_approach_mm=15,paper_contact_z_range=[first_touch-15,first_touch])
    d['material'].update(ink_reload_mm=1500,spring_pressure_response_selected=False)
    d['notes']='Corrected paper-only formula: commanded Z=brush first-touch minus compression. Fast approach ends15; initial contact, compression and release use2000. Stations/YAML/G54 unchanged. One1500mm no-reload test: 15 depths x2 repetitions x50mm. Historical Spring Z-8 is NOT final; normalized artistic pressure remains immutable. Approximate first-touch and trial contact envelope are not measured clearance/brush-response evidence.'
    return Profile.from_dict(d)


def plan(p):
    first_touch=p.paper_first_touch_for('ink','INK');lines=[]
    for repeat in range(2):
        for n in range(15):
            compression=n+1;column,row=divmod(n,5);x=20+110*column;y=20+30*row+160*repeat
            lines.append(dict(id=f'INK-COMP-{compression:02}-'+('EARLY' if repeat==0 else 'LATE'),
                stage='early' if repeat==0 else 'late',compression_mm=compression,
                start_xy=[x,y],end_xy=[x+50,y],z_mm=first_touch-compression,
                feed_mm_min=6000,drawing_xy_mm=50,cumulative_xy_mm=(len(lines)+1)*50))
    return dict(schema='datascape.paper_reference_ink1500.v01',paper_region_xy=[[10,10],[320,320]],
        substrate_mm=[330,330],paper_first_touch_z_mm=first_touch,
        reference_status='operator-reported approximate first-touch; not precision metrology',
        formula='commanded_Z=paper_first_touch_Z-compression_mm',
        strokes=lines,drawing_xy_target_mm=1500,initial_ink_loads=1,reloads_during_test=0,
        compression_depths_mm=list(range(1,16)),repetitions_per_depth=2,
        start_work_xyz=[0,900,35],park_work_xyz=[800,800,35],
        comparison='50mm at each depth in early750mm and late750mm; paired marks have equal X/direction/feed and Y+160mm. Centerline layout only; actual broad wet-mark overlap is an observation, not a claimed measurement.')


def build(root,p):
    request=plan(p);b=RuntimeBuilder(p);m=RuntimeMaterials(b)
    b.marker('benchmark_station_visit','ink:pigment_load');m.station('ink','pigment_load')
    m.loaded='ink';m.distance=0
    for line in request['strokes']:
        _draw(b,p,line,line['id']);m.distance+=dist(line['start_xy'],line['end_xy'])
    b.marker('endurance_complete','1500mm drawing XY; all15 compressions repeated twice; reloads0')
    b.park(m.station_travel_state())
    return request,dict(AIR=elevated_air(b.commands,p),INK=b.commands)


def render(commands,p,request,kind):
    return BANNER+'; CORRECTED PAPER FIRST TOUCH ~Z10; STATION ABSOLUTE Z UNCHANGED\n; SPRING FINAL PRESSURE DISTRIBUTION NOT SELECTED\n'+_serialize(commands,p,digest(request),STEM+kind+'_REVIEW','offline_review')


def readback(text,commands,p,request,kind):
    if not text.startswith(BANNER):raise ValueError('missing review identity')
    rows=[r for r in text.splitlines() if r and not r.startswith(';')]
    expected=[c for c in commands if c.kind!='marker']
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or len(rows)!=len(expected)+2:raise ValueError('modal/M2/coverage mismatch')
    pos=tuple(p.data['machine']['start_work_xyz']);touch,hover,approach=p.paper_heights_for('ink','INK')
    total=0.;draw=[];moves=[];paper=[];rates=[0.,0.,0.];departures={};arrivals={};wet=[]
    for row,c in zip(rows[1:-1],expected):
        if c.kind=='move':
            m=_MOVE.fullmatch(row)
            if not m:raise ValueError('unsupported move')
            x,y,z,f=map(float,m.groups());target=(x,y,z)
            if any(abs(a-b)>5.1e-10 for a,b in zip((x,y,z,f),(*c.xyz,c.feed_mm_min))):raise ValueError('numeric read-back differs from IR')
            check_move(pos,target,f,c.action,p,'air' if kind=='AIR' else 'paint')
            length=dist(pos,target)
            projected_z=0 if not length else abs(z-pos[2])/length*f
            if length:
                for axis in range(3):rates[axis]=max(rates[axis],abs(target[axis]-pos[axis])/length*f)
            if c.time_category=='station_transfer' and pos[:2]!=target[:2] and (pos[2]!=35 or z!=35):raise ValueError('global station transfer below35')
            if c.time_category=='station_handling' and kind=='AIR' and (pos[2]!=35 or z!=35):raise ValueError('Air station handling below35')
            if c.action in PAPER_ACTIONS:
                paper.append(dict(action=c.action,start=list(pos),end=list(target),feed_mm_min=f,projected_z_mm_min=projected_z))
                if kind=='INK':
                    if c.action in ('paper_hover','approach','retract') and min(pos[2],z)<approach:
                        raise ValueError('fast noncontact paper path enters approach/contact region')
                    if c.action in ('initial_contact','calibration_compression','release','paper_release_clearance'):
                        if f>2000 or projected_z>2000+1e-8:raise ValueError('contact/compression/release exceeds2000')
                    if z!=pos[2] and min(pos[2],z)<=touch and projected_z>2000+1e-8:
                        raise ValueError('fast Z motion crosses/occupies actual paper-contact plane')
            if c.action=='travel' and length:
                if c.travel_phase=='departure':departures.setdefault(c.travel_state,[]).append(f)
                if c.travel_phase=='arrival':arrivals.setdefault(c.travel_state,[]).append(f)
                if c.travel_state=='wet_loaded' and c.travel_phase=='main':wet.append(f)
            if c.action=='draw':
                line=request['strokes'][len(draw)];xy_length=hypot(x-pos[0],y-pos[1]);total+=xy_length
                intended=touch-line['compression_mm'];actual=hover if kind=='AIR' else intended
                if (line['z_mm']!=intended or c.source_id!=line['id'] or pos[:2]!=tuple(line['start_xy']) or target[:2]!=tuple(line['end_xy']) or
                    xy_length!=50 or pos[2]!=z or z!=actual or f!=6000):raise ValueError('source/XY/depth conversion/length/feed mismatch')
                draw.append(dict(id=line['id'],stage=line['stage'],compression_mm=line['compression_mm'],
                    commanded_paper_z=intended,actual_path_z=z,start=list(pos),end=list(target),drawing_xy_mm=xy_length,cumulative_xy_mm=total))
            pos=target;moves.append(c)
        elif c.kind=='dwell':
            m=_DWELL.fullmatch(row)
            if not m or abs(float(m.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell mismatch')
        else:raise ValueError('pause or unresolved command')
    if len(draw)!=30 or total!=1500 or [s['compression_mm'] for s in draw]!=list(range(1,16))*2:raise ValueError('all15 depths twice / exactly1500mm required')
    if [r['action'] for r in paper]!=list(PAPER_ACTIONS)*30:raise ValueError('paper approach/contact/compression/release ordering mismatch')
    for i in range(30):
        group=paper[i*8:(i+1)*8];line=request['strokes'][i]
        targets=[hover,approach,touch,line['z_mm'],line['z_mm'],touch,approach,hover] if kind=='INK' else [hover]*8
        feeds=[7000,7000,2000,2000,6000,2000,2000,7000]
        if [r['end'][2] for r in group]!=targets or [r['feed_mm_min'] for r in group]!=feeds:
            raise ValueError('paper first-touch/approach/release coordinates or feed mismatch')
    visits=[c.message for c in commands if c.action=='benchmark_station_visit']
    if visits!=['ink:pigment_load'] or any(c.action=='same_color_reload' for c in commands):raise ValueError('one ink load / no reload required')
    if pos!=(800,800,35):raise ValueError('park mismatch')
    for state in ('ordinary_travel','partially_depleted'):
        if not departures.get(state) or set(departures[state])!={15000} or not arrivals.get(state) or set(arrivals[state])!={3000}:raise ValueError('dry/return speed policy mismatch')
    if not wet or set(wet)!={12000}:raise ValueError('wet main feed mismatch')
    lip=previous.check_lip(moves,kind,p)
    return dict(readback_verified=True,status=STATUS,kind=kind,profile_sha256=p.sha256,plan_sha256=digest(request),
        start_work_xyz=p.data['machine']['start_work_xyz'],end_work_xyz=list(pos),G54_offset_xyz=p.data['machine']['g54_to_machine_xyz'],
        paper_first_touch_z_mm=touch,physical_compression_depths_mm=list(range(1,16)),repetitions_per_depth=2,
        compression_conversion_verified=True,drawing_xy_mm=total,drawing_strokes=draw,source_strokes=30,
        paper_moves=paper,no_fast_Z_crossing_actual_contact_plane_verified=True,
        paper_approach_boundary_z=approach,contact_compression_release_cap_mm_min=2000,
        minimum_commanded_paper_z=touch-15 if kind=='INK' else hover,
        maximum_projected_axis_feeds=rates,controller_axis_feed_caps=p.data['machine']['axis_max_rate_mm_min'],
        candidate_machine_bounds=p.data['machine']['machine_bounds_xyz'],full_axis_segment_bounds_checked=True,
        station_visits=visits,initial_ink_loads=1,reloads_during_test=0,lip_sequence=lip,
        M0_count=0,M2_verified=True,Spring_pressure_finalized=False,physically_passed=False,authorized=False,
        trajectory_sha256=digest([asdict(c) for c in commands]))


def schedule(request):
    s=io.StringIO(newline='');w=csv.writer(s,lineterminator='\n')
    w.writerow(['stroke','stage','compression_mm','paper_first_touch_Z','commanded_paper_Z','start_x','start_y','end_x','end_y','drawing_mm','cumulative_mm'])
    for line in request['strokes']:
        w.writerow([line['id'],line['stage'],line['compression_mm'],request['paper_first_touch_z_mm'],line['z_mm'],*line['start_xy'],*line['end_xy'],50,line['cumulative_xy_mm']])
    return s.getvalue()


def handoff(root,p):
    old=previous.profile(root)
    return dict(status='AWAITING_OPERATOR_PHYSICAL_BENCHMARK_RESULTS_AND_BRUSH_SELECTION',
        preferred_ink_reload_mm=1500,color_reload_mm=800,
        final_Spring_pressure_response_selected=False,selected_pressure_to_compression_knots=None,
        possible_3_to_15mm_range_selected=False,source_pressure_or_geometry_changed=False,
        first_touch_is_brush_specific=True,formula='G54_paper_Z=brush_first_touch_Z+relative_compression_offset',
        absolute_station_Z_shift_applied=False,global_G54_shift_applied=False,
        historical_only={role:dict(relative_knots=b['knots'],relative_knots_sha256=digest(b['knots']),
            paper_first_touch_z_mm=p.data['brush_profiles'][role]['paper_first_touch_z_mm'],
            status='HISTORICAL / PROVISIONAL ONLY; NOT FINAL PHYSICAL NORMALIZATION') for role,b in old.data['brush_profiles'].items()},
        next='Operator evaluates width/continuity/depletion/recovery at physical1..15mm; select brush and physical pressure curve, then existing full Spring AIR/SHARED_INK/SHARED_COLOR workflow. No final Spring files now.')


def export(root,output,machine=None,provenance=None):
    p=profile(root);request,programs=build(root,p)
    def write(out):
        raw,_,controller=final_lip.yaml_candidate(root)
        (out/'config.X860.Y900.final_lip.candidate.yaml').write_bytes(raw)
        save_json(out/'controller.json',controller);save_json(out/'profile.paper_touch10.ink1500.json',p.data)
        save_json(out/'benchmark1500.plan.json',request);(out/'stroke_schedule.csv').write_text(schedule(request))
        save_json(out/'spring_pressure_handoff.json',handoff(root,p))
        report=dict(schema='datascape.paper_first_touch_corrected_ink1500.v01',base_commit=PIN,
            status=STATUS,authorized=False,hardware_operated=False,station_absolute_coordinates_unchanged=True,
            global_G54_shift_applied=False,Spring_final_pressure_curve_selected=False,jobs={})
        for kind,commands in programs.items():
            name=STEM+kind+'_REVIEW';text=render(commands,p,request,kind)
            (out/(name+'.gcode')).write_text(text);result=readback((out/(name+'.gcode')).read_text(),commands,p,request,kind)
            save_json(out/(name+'.readback.json'),result);report['jobs'][kind]=result
        if xy_route(programs['AIR'])!=xy_route(programs['INK']):raise ValueError('matched Air XY differs')
        if machine is not None and provenance is not None:save_json(out/'spring_coordinate_dependencies.json',spring_dependencies(root,{'PAPER_TOUCH_CORRECTED':p},machine,provenance))
        save_json(out/'verification.json',report);(out/'README.md').write_text(README);(out/'RUN_SHEET.md').write_text(RUN_SHEET)
        return report
    return _atomic_output(output,write)


def verify(root,output):
    out=Path(output);manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(manifest)!={f.name for f in out.iterdir() if f.is_file() and f.name!='MANIFEST_SHA256.json'}:raise ValueError('manifest coverage')
    for name,sha in manifest.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha:raise ValueError('SHA256 mismatch '+name)
    p=profile(root);request,programs=build(root,p)
    if p.data!=Profile.load(out/'profile.paper_touch10.ink1500.json').data:raise ValueError('profile regeneration')
    if request!=json.loads((out/'benchmark1500.plan.json').read_text()) or schedule(request)!=(out/'stroke_schedule.csv').read_text():raise ValueError('plan/schedule mismatch')
    raw,_,controller=final_lip.yaml_candidate(root)
    if raw!=(out/'config.X860.Y900.final_lip.candidate.yaml').read_bytes() or controller!=json.loads((out/'controller.json').read_text()):raise ValueError('unchanged YAML/controller mismatch')
    if handoff(root,p)!=json.loads((out/'spring_pressure_handoff.json').read_text()):raise ValueError('pending pressure handoff mismatch')
    report=json.loads((out/'verification.json').read_text())
    for kind,commands in programs.items():
        name=STEM+kind+'_REVIEW';text=(out/(name+'.gcode')).read_text()
        if text!=render(commands,p,request,kind):raise ValueError('G-code regeneration')
        result=readback(text,commands,p,request,kind)
        if result!=json.loads((out/(name+'.readback.json')).read_text()) or result!=report['jobs'][kind]:raise ValueError('readback regeneration')
    return dict(numeric_review_files_regenerated=2,all_SHA256_verified=True,readback_verified=True,
        drawing_xy_mm=1500,physical_compression_range_mm=[1,15],paper_first_touch_z_mm=10,
        M0_count=0,Spring_final_pressure_selected=False,authorized=False)


README='''# Corrected paper first-touch and final1500mm ink test

IMPORTANT: the operator now reports actual first-touch at approximately G54Z+10,
not0. Old negative-Z benchmark files are historical/superseded for this mounting:
Z-1..-7 meant approximately11..17mm compression. Do not reuse those old files as
1..7mm tests under the corrected reference. They remain reproducible for audit.

Paper formula: commanded_Z=brush_first_touch_Z-compression_mm.
At first-touch10: compression1->Z9,7->Z3,15->Z-5.
The reusable brush field paper_first_touch_z_mm is independent for ink/color/slot.
Existing pressure knots remain SIGNED COMPRESSION OFFSETS: z_for returns that
historical relative value; work_z_for adds only the brush's paper reference.
Paper contact/release use that reference. Absolute stations, machine bounds,
YAML, G54, bed/substrate registration and station/lip/palette/washing Z NEVER
receive this paper-only offset.

Fast noncontact paper approach stops at the existing hoverZ15 (5mm above the
reported first-touch); no new lower fast-approach boundary is assumed measured.
Z15->10 initial contact, compression, return to10 and release10->15 all useF2000.
F7000 is restricted to the noncontact region15 and above. Readback separately
checks every paper segment and prevents fast Z crossing/occupying the actual
contact plane. Station motions crossing the numericZ10 elsewhere are not paper
contact and keep their existing independent feeds/absolute coordinates.

One final test:30 straight50mm strokes=1500mm drawing-onlyXY. Depths1..15mm
repeat in early750mm and late750mm; every depth appears twice at equal length,
direction and F6000. Three columns X20->70,130->180,240->290. Early rowY20..140,
lateY180..300,30mm spacing. Paired depths shareX and differY+160. The centerlines
fit the existing paper region10..320; wet-mark width/overlap is not certified.
One automatic WELL_2 load with accepted immersion/agitation/slope/single20mm
wipe/local20 lip connection/X815->795 atF1500/retract35. No reload within the
test, wash, purge or color visit. Every file independently starts after home at
X0Y900Z35 and finishes800/800/35/M2. M0=0. No homing/offset commands embedded.
Matched AIR retains all XY/source/visits, paper15/stations35, with no contact.

Preferred subsequent Spring ink reload is now1500mm; color remains800mm.
All other accepted motion/station/controller settings are unchanged. Complete
Y900 YAML bytes equal the previous candidate; installation/readback is not
claimed. Files are real numeric review G-code, not manufactured execution
authorization, brush-response measurement or swept-tool clearance evidence.

SPRING PRESSURE IS NOT FINAL: the relative Z-8 curve is kept ONLY as a historical/
provisional reference. The profile explicitly marks final Spring response NOT
selected; the official painting gate rejects that pending state. No3..15mm or
other new normalization is chosen. After results, select brush/usable compression
and knot response from physical width/continuity/recovery/loading observations,
then apply first-touch to its absolute paper G-code. Every artistic pressure,
source XY/direction/S3a/color and canonical plan binding stays immutable.
No final Spring production files are generated in this update.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.paper_reference_1500 --output NEW_DIR
Verify: append --verify for an existing package. Optional --machine/--provenance
perform canonical Spring dependency readback without producing Spring G-code.
'''

RUN_SHEET='''# Final1500mm ink test: corrected paper first-touch

Use ONLY the new PAPER_Z10_COMP1_15 files for this reference. Prior negative-Z
files were based on first-touch0 and no longer describe their labeled physical
compressions. Reference10 is operator-reported approximate, brush-specific.

1. Each separate AIR or INK file requires manual rehome/start G54X0Y900Z35,
   established zero G54/G92/TLO; endX800Y800Z35/M2. Do not shift G54 or stations.
   Preserve existing controller/configuration/clearance/stopping checks. No
   installation or new physical pass is asserted by these review files.
2. Run matched AIR as appropriate: paper15/stations35. It has no contact and
   cannot establish physical compression, brush response or the local lip fit.
3. Prepare WELL_2 ink at its established reference. INK loads once automatically
   with the accepted local20/F1500 lip routine, then draws without reloading.
4. Follow stroke_schedule.csv: early15 lines at1..15mm compression/750mm, then
   late15 equivalent lines/750mm. Each50mm/F6000; physical1->Z9,7->Z3,15->Z-5.
   Paper fast motion stops15; initial contact10, compression and release use2000.
5. Record widths, density, continuity, depletion, pooling/paper condition and
   brush recovery for each paired early/late depth. Compare equivalent depths,
   not a shallow early mark against a deep late mark. M0=0: use the established
   stop control if contact, communication or mechanics is abnormal; inspect
   actual position before resuming. No automatic mid-test reload or inspection.
6. Send results and brush selection. Final Spring pressure distribution remains
   undecided; Z-8 is history only. Select the physical curve from these results,
   then existing Spring AIR -> SHARED_INK -> SHARED_COLOR export. No new hardware
   commissioning or artwork/composition study is planned.
'''

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--machine',type=Path);ap.add_argument('--provenance',type=Path)
    a=ap.parse_args();root=Path(__file__).resolve().parents[2]
    if a.verify:print(json.dumps(verify(root,a.output)))
    else:export(root,a.output,a.machine,a.provenance)
