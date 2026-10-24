"""Independent exact-distance ink endurance jobs using the accepted backend.

No hardware I/O, artwork modification, reload during a test, or invented passed
physical evidence. Earlier 40-stroke and endurance baselines remain reproducible.
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
from . import final_lip as baseline
from .high_speed import _draw, elevated_air
from .numeric_review import BANNER, STATUS, check_move, xy_route
from .spring_runtime import RuntimeBuilder, RuntimeMaterials
from .y900_lip import spring_dependencies

PIN='1f20984885176291925d97bbcb070ea2c53396d9'
CASES={'A1200':1200,'B1500':1500}
STEM='INK_ENDURANCE_'


def profile(root):
    d=deepcopy(baseline.profile(root).data)
    d['profile_id']='FINAL-INK-ENDURANCE-LIP1500-LOCAL20-IMMEDIATE-DRY15000-REVIEW'
    for role in ('ink','water'):
        lip=d['stations'][role]['lip_stripping']
        lip.update(contact_feed_mm_min=1500,contact_feed_cap_mm_min=1500,
            approach_clearance_z=20,approach_xy_mm_min=1500)
    for state in ('ordinary_travel','partially_depleted'):
        # Same straight path/arrival zone: request the main feed from the FIRST
        # departure block. No controller acceleration/lookahead setting changes.
        d['motion']['segmented_travel'][state]['departure_mm_min']=15000
    d['notes']='Latest operator-requested physical-feedback revision: release shallow wipe vertically to20, controlled XY at20/F1500 to confirmed lip, X815->795/F1500, then vertical35. Dry/used departure commands15000 with existing controlled arrival; wet12000 unchanged. Two independent no-reload endurance jobs, not changes to Spring reload thresholds or pressure. Review generation only; no installation, full-tool clearance or new physical pass fabricated.'
    return Profile.from_dict(d)


def plan(case):
    if case not in CASES:raise ValueError('unknown endurance case')
    count=CASES[case]//100;lines=[]
    for i in range(count):
        column,row=divmod(i,8);x=20+170*column;y=20+40*row
        lines.append(dict(id=f'INK-ENDURANCE-{i+1:02}',start_xy=[x,y],end_xy=[x+100,y],
            z_mm=-(1+i%7),feed_mm_min=6000,drawing_xy_mm=100,
            cumulative_xy_mm=(i+1)*100,depth_cycle=1+i//7))
    return dict(schema='datascape.final_ink_endurance.v01',case=case,paper_region_xy=[[10,10],[320,320]],
        substrate_mm=[330,330],start_work_xyz=[0,900,35],park_work_xyz=[800,800,35],
        drawing_xy_target_mm=CASES[case],drawing_xy_only=True,
        strokes=lines,repeated_depths_mm=[-1,-2,-3,-4,-5,-6,-7],
        fresh_load_count=1,reloads_during_test=0,
        no_reload_override_scope='this isolated endurance test only; Spring ink1200/color800 thresholds unchanged',
        comparison='Same100mm lines and repeated depth sequence; B first12 strokes exactly equal A. Separate files each require post-home start and fresh automatic ink load. Centerline paths fit paper; no physical mark-width/clearance certificate inferred.')


def build(root,p,case):
    request=plan(case);b=RuntimeBuilder(p);m=RuntimeMaterials(b)
    b.marker('benchmark_station_visit','ink:pigment_load')
    m.station('ink','pigment_load');m.loaded='ink';m.distance=0
    for line in request['strokes']:
        _draw(b,p,line,line['id'])
        m.distance+=dist(line['start_xy'],line['end_xy'])
        # Deliberately no material reload dispatch: this is an uninterrupted
        # depletion test, INCLUDING at/after the normal1200mm boundary.
    b.marker('endurance_complete',f'drawingXY={m.distance}; reloads=0')
    b.park(m.station_travel_state())
    return request,dict(AIR=elevated_air(b.commands,p),INK=b.commands)


def render(commands,p,request,kind):
    name=STEM+request['case']+'_'+kind+'_REVIEW'
    return BANNER+'; INDEPENDENT POST-HOME START; ONE FRESH INK LOAD; ZERO RELOADS DURING TEST\n'+_serialize(commands,p,digest(request),name,'offline_review')


def check_lip(moves,kind,p,role='ink'):
    """Exact local release/strip ordering, also used for isolated water tests."""
    y=458 if role=='ink' else 298;end_y=465 if role=='ink' else 315
    wipes=[i for i,c in enumerate(moves) if c.travel_phase=='shallow_wipe']
    strips=[i for i,c in enumerate(moves) if c.travel_phase=='lip_strip']
    if len(wipes)!=1 or len(strips)!=1:raise ValueError('one shallow wipe and one lip strip required')
    i=wipes[0];tail=moves[i:i+6];air=kind=='AIR';contact_z=35 if air else 7.5
    release_z=35 if air else 9;lip_z=35 if air else 20
    if len(tail)!=6:raise ValueError('incomplete local lip sequence')
    expected=[((840,end_y,contact_z),1000,'shallow_wipe'),
        ((840,end_y,release_z),750,'shallow_contact'),
        ((840,end_y,lip_z),7000,''),
        ((815,y,lip_z),1500,'lip_approach'),
        ((795,y,lip_z),1500,'lip_strip'),
        ((795,y,35),7000,'lip_retract')]
    if [(c.xyz,c.feed_mm_min,c.travel_phase) for c in tail]!=expected:
        raise ValueError('wipe/release/local20/XY/strip/global35 order or feed mismatch')
    if not air and any(c.xyz[2]==35 for c in tail[:-1]):raise ValueError('unnecessary global35 before lip strip')
    if any(c.travel_phase=='lip_contact' for c in moves):raise ValueError('redundant lip descent remains')
    return dict(role=role,shallow_wipe_start=[840,end_y-20,contact_z],
        shallow_wipe_end=[840,end_y,contact_z],vertical_release_z=release_z,
        local_connection_z=lip_z,lip_start=[815,y,lip_z],lip_end=[795,y,lip_z],
        approach_and_strip_feed_mm_min=1500,global_retract_z=35,
        Z35_to_Z20_round_trip_removed=True,
        actual_lip_contact_emitted=not air,physical_new_connection_verified=False)


def readback(text,commands,p,request,kind):
    if not text.startswith(BANNER):raise ValueError('missing review identity')
    rows=[r for r in text.splitlines() if r and not r.startswith(';')]
    expected=[c for c in commands if c.kind!='marker']
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2' or len(rows)!=len(expected)+2:
        raise ValueError('modal/command/M2 coverage mismatch')
    pos=tuple(p.data['machine']['start_work_xyz']);rates=[0.,0.,0.];draw=[];total=0.;moves=[]
    departures={};arrivals={};wet=[];positions=[pos]
    for row,c in zip(rows[1:-1],expected):
        if c.kind=='move':
            match=_MOVE.fullmatch(row)
            if not match:raise ValueError('unsupported numeric move')
            x,y,z,feed=map(float,match.groups());target=(x,y,z)
            if any(abs(a-b)>5.1e-10 for a,b in zip((x,y,z,feed),(*c.xyz,c.feed_mm_min))):
                raise ValueError('numeric read-back differs from trajectory')
            check_move(pos,target,feed,c.action,p,'air' if kind=='AIR' else 'paint')
            length=dist(pos,target)
            if length:
                for axis in range(3):rates[axis]=max(rates[axis],abs(target[axis]-pos[axis])/length*feed)
            if c.time_category=='station_transfer' and pos[:2]!=target[:2] and (pos[2]!=35 or z!=35):
                raise ValueError('cross-region transfer below35')
            if kind=='AIR' and c.time_category=='station_handling' and (pos[2]!=35 or z!=35):
                raise ValueError('Air station handling below35')
            if c.action=='travel' and length:
                if c.travel_phase=='departure':departures.setdefault(c.travel_state,[]).append(feed)
                if c.travel_phase=='arrival':arrivals.setdefault(c.travel_state,[]).append(feed)
                if c.travel_state=='wet_loaded' and c.travel_phase=='main':wet.append(feed)
            if c.action=='draw':
                i=len(draw);line=request['strokes'][i];xy_length=hypot(x-pos[0],y-pos[1]);total+=xy_length
                if (c.source_id!=line['id'] or pos[:2]!=tuple(line['start_xy']) or target[:2]!=tuple(line['end_xy']) or
                    xy_length!=100 or feed!=6000 or pos[2]!=z or z!=(15 if kind=='AIR' else line['z_mm'])):
                    raise ValueError('stroke source/XY/direction/depth/feed/distance mismatch')
                draw.append(dict(id=line['id'],start=list(pos),end=list(target),
                    intended_contact_z=line['z_mm'],drawing_xy_mm=xy_length,cumulative_drawing_xy_mm=total))
            pos=target;positions.append(pos);moves.append(c)
        elif c.kind=='dwell':
            match=_DWELL.fullmatch(row)
            if not match or abs(float(match.group(1))-c.seconds)>5.1e-10:raise ValueError('dwell mismatch')
        else:raise ValueError('unexpected pause or unresolved command')
    visits=[c.message for c in commands if c.action=='benchmark_station_visit']
    if visits!=['ink:pigment_load']:raise ValueError('exactly one initial ink load; no reload/wash/color allowed')
    if any(c.action=='same_color_reload' for c in commands):raise ValueError('reload inside endurance test')
    if len(draw)!=len(request['strokes']) or total!=request['drawing_xy_target_mm']:
        raise ValueError('exact drawing-only XY distance or stroke count mismatch')
    if pos!=(800,800,35):raise ValueError('park mismatch')
    for state in ('ordinary_travel','partially_depleted'):
        if not departures.get(state) or set(departures[state])!={15000}:
            raise ValueError('dry/used return must request15000 from first departure')
        if not arrivals.get(state) or set(arrivals[state])!={3000}:raise ValueError('controlled slow arrival lost')
    if not wet or set(wet)!={12000}:raise ValueError('wet main travel must remain12000')
    if not departures.get('wet_loaded') or set(departures['wet_loaded'])!={3000}:
        raise ValueError('wet departure behavior changed')
    lip=check_lip(moves,kind,p)
    off=p.data['machine']['g54_to_machine_xyz']
    return dict(readback_verified=True,case=request['case'],kind=kind,status=STATUS,
        plan_sha256=digest(request),profile_sha256=p.sha256,
        start_work_xyz=list(positions[0]),start_machine_xyz=[a+b for a,b in zip(positions[0],off)],
        end_work_xyz=list(pos),end_machine_xyz=[a+b for a,b in zip(pos,off)],
        source_strokes=len(draw),drawing_xy_mm=total,drawing_only_distance_verified=True,
        drawing_strokes=draw,station_visits=visits,initial_ink_loads=1,reloads_during_test=0,
        pressed_shallow_passes=0 if kind=='AIR' else 1,lip_sequence=lip,
        maximum_projected_axis_feeds=rates,controller_axis_feed_caps=p.data['machine']['axis_max_rate_mm_min'],
        axis_reference_bounds=p.data['machine']['machine_bounds_xyz'],
        complete_linear_axis_bounds_checked=True,departure_feeds=departures,arrival_feeds=arrivals,
        wet_main_feeds=sorted(set(wet)),M0_count=0,M2_verified=True,
        physical_swept_clearance_verified=False,physically_passed=False,authorized=False,
        trajectory_sha256=digest([asdict(c) for c in commands]))


def schedule(request):
    buffer=io.StringIO(newline='');w=csv.writer(buffer,lineterminator='\n')
    w.writerow(['stroke','start_x','start_y','end_x','end_y','Z','drawing_mm','cumulative_mm'])
    for line in request['strokes']:
        w.writerow([line['id'],*line['start_xy'],*line['end_xy'],line['z_mm'],100,line['cumulative_xy_mm']])
    return buffer.getvalue()


def export(root,output,machine=None,provenance=None):
    p=profile(root)
    def write(out):
        raw,diff,controller=baseline.yaml_candidate(root)
        (out/'config.X860.Y900.final_lip.candidate.yaml').write_bytes(raw)
        save_json(out/'controller.json',controller);save_json(out/'profile.final_ink_endurance.json',p.data)
        report=dict(schema='datascape.final_ink_endurance_review.v01',base_commit=PIN,
            status=STATUS,authorized=False,hardware_operated=False,
            Spring_artwork_pressure_order_modified=False,cases={})
        for case in CASES:
            request,programs=build(root,p,case);save_json(out/(case+'.plan.json'),request)
            (out/(case+'.stroke_schedule.csv')).write_text(schedule(request))
            results={}
            for kind,commands in programs.items():
                name=STEM+case+'_'+kind+'_REVIEW';text=render(commands,p,request,kind)
                (out/(name+'.gcode')).write_text(text)
                checked=readback((out/(name+'.gcode')).read_text(),commands,p,request,kind)
                save_json(out/(name+'.readback.json'),checked);results[kind]=checked
            if xy_route(programs['AIR'])!=xy_route(programs['INK']):raise ValueError('matched Air XY route mismatch')
            report['cases'][case]=results
        if machine is not None and provenance is not None:
            save_json(out/'spring_coordinate_dependencies.json',spring_dependencies(root,{'FINAL_INK_ENDURANCE':p},machine,provenance))
        save_json(out/'verification.json',report)
        (out/'README.md').write_text(README);(out/'RUN_SHEET.md').write_text(RUN_SHEET)
        return report
    return _atomic_output(output,write)


def verify(root,output):
    out=Path(output);manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(manifest)!={f.name for f in out.iterdir() if f.is_file() and f.name!='MANIFEST_SHA256.json'}:raise ValueError('manifest coverage mismatch')
    for name,sha in manifest.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha:raise ValueError('SHA256 mismatch '+name)
    p=profile(root)
    if p.data!=Profile.load(out/'profile.final_ink_endurance.json').data:raise ValueError('profile regeneration mismatch')
    raw,_,controller=baseline.yaml_candidate(root)
    if (out/'config.X860.Y900.final_lip.candidate.yaml').read_bytes()!=raw or json.loads((out/'controller.json').read_text())!=controller:
        raise ValueError('unchanged Y900 YAML/controller mismatch')
    report=json.loads((out/'verification.json').read_text());count=0
    for case in CASES:
        request,programs=build(root,p,case)
        if request!=json.loads((out/(case+'.plan.json')).read_text()) or schedule(request)!=(out/(case+'.stroke_schedule.csv')).read_text():
            raise ValueError('plan/schedule mismatch')
        for kind,commands in programs.items():
            name=STEM+case+'_'+kind+'_REVIEW';text=(out/(name+'.gcode')).read_text()
            if text!=render(commands,p,request,kind):raise ValueError('G-code regeneration mismatch')
            checked=readback(text,commands,p,request,kind)
            if checked!=json.loads((out/(name+'.readback.json')).read_text()) or checked!=report['cases'][case][kind]:
                raise ValueError('readback regeneration mismatch')
            count+=1
    return dict(numeric_review_files_regenerated=count,all_SHA256_verified=True,readback_verified=True,
        drawing_distances_mm=CASES,M0_count=0,authorized=False)


README='''# Final ink endurance: independent 1200mm and1500mm tests

Each complete AIR/INK job starts independently immediately after manual homing,
G54 X0 Y900 Z35, and ends X800 Y800 Z35/M2, M0=0. No homing/offset write is
embedded. Each has ONE automatic fresh WELL_2 load, NO in-test reload, washing,
purge or palette visit. This intentional depletion-test override does not change
Spring ink1200/color800 reload thresholds. Old40-stroke and endurance baselines
are retained unchanged.

A1200:12 straight100mm strokes, drawing-only XY=1200mm.
B1500:15 straight100mm strokes, drawing-only XY=1500mm.
Depths repeat[-1,-2,-3,-4,-5,-6,-7] in the same order. B first12 source IDs,
XY, direction, depth, speed and sequence equal A; the last three extend the test.
Stroke centers: X20->120 for rows1..8 atY20,60,...300; X190->290 for later rows.
All paths fit the existing paper region10..320.40mm row spacing/70mm column gap
are layout choices, not measured wet-mark-width certificates. CSV schedules give
exact numbering/depth/cumulative distance. No non-drawing XY/Z travel is counted.
No Spring artwork/Pressure Intent or brush-response curve is regenerated.

Updated BOTH stone profiles: original immersion/agitation/slope -> ONE pressed
20mm Y+ wipe at7.5 -> vertical controlled release9 -> vertical lift20 -> controlled
XY to measured lip815/458 (ink) or815/298 (water) at20/F1500 -> X795/F1500 ->
vertical35/F7000. No Z35->20 round trip or redundant lip descent. The local
connection is distinct from cross-region travel at35. Lip displacement/feed,
local connection height/feed and final retract remain separately configurable.
The new connection/feed is operator-requested, not a fabricated physical pass.
Water uses the same grammar/configuration, but these INK-only tests visit only
WELL_2. Official station contact-volume and full-tool path/authorization checks
still apply; nominal review records do not certify the local XY corridor.

Dry/used-brush travel requests15000 from the FIRST departure block, keeping the
existing controlled F3000 arrival zone (nominal35mm for station/park arrival,
scaled for short routes). No initial F3000 departure segment for these states.
Collinear departure/main blocks can share F15000; no dwell or exact-stop mode
is introduced. Actual acceleration/attained speed remain governed by FluidNC
lookahead and unchanged axis limits. Short moves need not attain full speed.
Wet main12000 with its existing slow departure/arrival remains unchanged.
Drawing6000, noncontactZ7000, pressure/contact/release limit2000, paper hover15,
local hover off, transfer35, Y900/X860 YAML and Spring Z-8 candidate preserved.
The complete YAML is byte-identical to the prior final-lip candidate, never
installed/read back by this software. Existing fixedY0/stations remain unchanged.

AIR projects exactly the same XY/source/visit route: paper simulation15 and all
station handling35. It does not test actual liquid/stone/lip contact. INK uses
real commanded contact depths. All files contain real numeric G-code for review;
file generation, offline checks and physical execution authorization stay distinct.
No installed configuration, stopping, full-tool clearance or new physical pass
is invented. No hardware I/O, PR merge or final Spring production export occurs.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.final_ink_endurance --output NEW_DIR
Verify: append --verify using an existing package. Optional --machine and
--provenance bind/check recovered canonical Spring inputs without exporting it.
Next after operator results: select/calibrate brush, then existing full Spring
AIR and separate SHARED_INK/SHARED_COLOR export workflow. No further benchmark
study is planned.
'''

RUN_SHEET='''# Final ink endurance run sheet

These are complete numeric review programs, not a fabricated machine-authorized
export. Preserve established machine checks/stopping procedure. Confirm actual
active Y900 configuration/home/offsets and mounted-tool local lip corridor before
physical execution; no hardware settings are changed by the files.

1. Select A1200 or B1500. Rehome BEFORE EACH separate AIR or INK program: expected
   MPos=G54 WPos X0 Y900 Z35 with established zero G54/G92/TLO. The prior park is
   not a valid substitute for the documented start. Finish is X800 Y800 Z35/M2.
2. Use the matching AIR file first. Paper XY simulation stays at15; all station
   handling stays35. AIR cannot establish contact or material-delivery quality.
3. Prepare WELL_2 ink at its established reference level. INK automatically loads
   once, including the local20/F1500 lip routine; it does not reload even when
   crossing1200mm. Each test starts with a fresh load. No manual mid-test refill
   of the brush or routine M0. Keep substrate/media comparable between A and B.
4. Follow the CSV: every line is100mm, depths repeat1..7mm compression. A ends
   after stroke12/1200mm; B after stroke15/1500mm. B first12 match A exactly.
   Record width, density, continuity/gaps, fading/depletion, puddling and brush
   recovery by stroke/depth/cumulative distance, plus lip droplet removal.
5. Dry/used travel commands15000 immediately then controlled3000 arrival; wet
   main12000, drawing6000, noncontactZ7000, paper contact/release cap2000.
   Stop by the established available control if motion/contact/streaming is
   abnormal; inspect position before resuming. M0=0 means no automatic pauses.
6. Send both results and brush selection/calibration. This completes benchmarks;
   next is full Spring AIR -> SHARED_INK -> SHARED_COLOR using validated settings.
'''

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--machine',type=Path);ap.add_argument('--provenance',type=Path)
    a=ap.parse_args();root=Path(__file__).resolve().parents[2]
    if a.verify:print(json.dumps(verify(root,a.output)))
    else:export(root,a.output,a.machine,a.provenance)
