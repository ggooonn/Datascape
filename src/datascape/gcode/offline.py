"""Reproducible Spring v13 Level-1 integration; use --help for exact inputs.

Run PR25's accepted adapter FIRST, then pass its bound machine and provenance.
No artistic generation, machine connection, production G-code or station moves.
"""
import argparse
from collections import Counter,defaultdict
from contextlib import ExitStack,contextmanager
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import time
from .binding import load_bound_spring,PRESSURE_COMMIT,SPRING_COMMIT,SIDECAR_SHA
from .calibration import synthetic_profile,BrushCalibration,CalibrationObservation
from .layout import Layout,Registration
from .motion import fragments,stroke_events,MotionSettings,commented_preview,require_output_level
from .estimation import Estimator
from .stations import StationSimulator
from .validation import validate_layout
from .review import work_svg,trajectory_html,write_benchmarks



@contextmanager
def gzip_text(path):
    # Stable payload bytes independent of output basename and wall-clock time.
    with open(path,'wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='\n') as text:
                yield text


def write_json(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def jsonline(handle,obj):
    handle.write(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n')


def run_layout(strokes,layout,settings,destination=None):
    start=time.perf_counter()
    audit=validate_layout(strokes,layout)
    estimator=Estimator(); sim=StationSimulator(); operation_counts=Counter()
    operation_seconds=0.; stream_stats=defaultdict(lambda: {'fragments':0,'vertices':0,'drawing_mm':0.})
    representative=[]; represented=set(); last_sequence={}; last_source_arc={}; total_events=0
    with ExitStack() as stack:
        handles={}; svg_parts=defaultdict(list)
        if destination:
            destination.mkdir(parents=True,exist_ok=True)
            order=stack.enter_context(gzip_text(destination/'setup_order.jsonl.gz'))
            stationfile=stack.enter_context(gzip_text(destination/'station_operations.jsonl.gz'))
        for f in fragments(strokes,layout):
            s=f.stroke
            if s.sequence<last_sequence.get(f.setup,-1): raise ValueError('source sequence changed within physical setup')
            last_sequence[f.setup]=s.sequence
            key=(f.setup,s.origin_id)
            if s.source_locations[0].arc_mm<last_source_arc.get(key,-1)-1e-10:
                raise ValueError('original fragment traversal changed')
            last_source_arc[key]=s.source_locations[-1].arc_mm
            state=stream_stats[f.stream];state['fragments']+=1;state['vertices']+=len(s.points)
            state['drawing_mm']+=s.source_spans[-1].arc_end_mm-s.source_spans[0].arc_start_mm
            operations=sim.before(f)
            for op in operations:
                operation_counts[op.action]+=1
                if op.assumed_seconds is not None: operation_seconds+=op.assumed_seconds
                if destination: jsonline(stationfile,asdict(op))
            if destination:
                if f.stream not in handles:
                    handles[f.stream]=tuple(stack.enter_context(gzip_text(destination/f'{f.stream}.{suffix}.gz'))
                                            for suffix in ('events.jsonl','fragments.jsonl','preview.gcode.txt'))
                eventsfile,fragmentfile,commentsfile=handles[f.stream]
                if state['fragments']==1: commentsfile.write('; DATASCAPE v0.2 OFFLINE ONLY; SYNTHETIC/UNRESOLVED Z; NO MACHINE TRAJECTORY\n')
                jsonline(order,{'setup':f.setup,'stream':f.stream,'fragment_id':s.stroke_id,
                                'source_id':s.origin_id,'source_sequence':s.sequence})
                jsonline(fragmentfile,asdict(f))
                svg_parts[f.stream].append(f)
            events=stroke_events(f,settings)
            for e in events:
                estimator.add(e);total_events+=1
                if destination:
                    jsonline(eventsfile,asdict(e))
                    commentsfile.writelines(list(commented_preview((e,)))[1:])
            sim.after(f)
            # Pick actual short/long/variable/cross-seam examples across layers.
            key=(s.medium,s.layer, 'crossing' if any(0<loc.t<1 for loc in s.source_locations) else 'ordinary')
            if key not in represented and len(representative)<32:
                represented.add(key);representative.append(f)
        if destination:
            for stream,parts in svg_parts.items():
                svg=work_svg(parts,layout)
                with gzip_text(destination/f'{stream}.work.svg.gz') as h: h.write(svg)
            (destination/'spring_3d_review.html').write_text(trajectory_html(representative,settings),encoding='utf-8')
    result={'layout':asdict(layout),'artwork_frame':'top-left X-right Y-down mm',
            'work_frame':'G54 front-left X-right Y-rear Z-up, registration unverified',
            'setup_footprints':{p.name:layout.footprint(p) for p in layout.panels},
            'audit':audit,'streams':dict(stream_stats),'motion_events':total_events,
            'estimates':estimator.result(),'station_simulation':{'counts':dict(operation_counts),
                'assumed_operation_seconds_excluding_travel_and_manual':operation_seconds,
                'coordinates_used':False,'thresholds_deferred_to_next_fragment':True},
            'runtime_seconds':time.perf_counter()-start}
    if destination: write_json(destination/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--machine',type=Path,required=True)
    p.add_argument('--provenance',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--layout',choices=list('ABCD'),default='A')
    p.add_argument('--gap-mm',type=float,default=0)
    p.add_argument('--layout-config',type=Path,help='JSON mode/gap_mm/registrations; replaces layout flags')
    p.add_argument('--calibration-profile',type=Path,help='external BrushCalibration JSON, offline interpretation only')
    p.add_argument('--constant-z-preview',type=float,help='explicit constant illustrative contact depth')
    p.add_argument('--synthetic-z-preview',action='store_true',help='invented nonlinear Z scale, never a safe physical mapping')
    p.add_argument('--compare-layouts',action='store_true')
    p.add_argument('--output-level',type=int,default=1)
    p.add_argument('--limit',type=int,help='deterministic development subset; final full verification omits this')
    args=p.parse_args();require_output_level(args.output_level)
    layout=Layout(args.layout,args.gap_mm)
    if args.layout_config:
        config=json.loads(args.layout_config.read_text())
        config['registrations']=tuple(Registration(**r) for r in config.get('registrations',[]))
        layout=Layout(**config)
    if args.output.exists() and any(args.output.iterdir()): raise ValueError('output must be new or empty')
    args.output.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();strokes,provenance=load_bound_spring(args.machine,args.provenance)
    load_seconds=time.perf_counter()-start
    if args.limit is not None:
        if args.limit<1: raise ValueError('positive limit required')
        strokes=strokes[:args.limit]
    if args.calibration_profile and args.synthetic_z_preview: raise ValueError('choose one Z profile')
    profile=synthetic_profile() if args.synthetic_z_preview else None
    if args.calibration_profile:
        record=json.loads(args.calibration_profile.read_text())
        record['knots']=tuple(tuple(k) for k in record['knots'])
        record['observations']=tuple(CalibrationObservation(**r) for r in record.get('observations',[]))
        profile=BrushCalibration(**record)
    settings=MotionSettings(profile,'constant' if args.constant_z_preview is not None else 'variable',args.constant_z_preview)
    results=[run_layout(strokes,layout,settings,args.output/f'layout_{layout.mode}')]
    if args.compare_layouts:
        for candidate in (Layout('A'),Layout('B'),Layout('C',50),Layout('D')):
            if candidate!=layout: results.append(run_layout(strokes,candidate,settings))
    write_benchmarks(args.output/'calibration')
    summary={'schema':'datascape.backend_offline_report.v0.2','offline_only':True,'output_level':1,
             'pressure_commit':PRESSURE_COMMIT,'spring_commit':SPRING_COMMIT,
             'pressure_sidecar_sha256':SIDECAR_SHA,'bound_machine_payload_sha256':provenance['derived_machine_payload_sha256'],
             'provenance_core_sha256':'c8baa3e46ce773a8752f488c889dc422e34d2ab9ba0ee87582efd9126c7e88d4',
             'source_strokes':len(strokes),'source_pressure_samples':sum(len(s.points) for s in strokes),
             'source_files_modified':False,'artistic_pressure_regenerated':False,'fallback_used':False,
             'machine_trajectory_available':False,'executable_output_available':False,
             'z_interpretation':('constant_synthetic_preview' if settings.mode=='constant' else settings.profile.status if settings.profile else 'unresolved'),
             'synthetic_profile':asdict(settings.profile) if settings.profile else None,
             'bound_load_seconds':load_seconds,'layouts':results,
             'runtime_seconds':time.perf_counter()-start,
             'peak_process_rss_mib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
             'memory_scope':'peak Python process including parsed input and output construction',
             'full_scene':args.limit is None}
    write_json(args.output/'summary.json',summary)
    manifest={str(f.relative_to(args.output)):hashlib.sha256(f.read_bytes()).hexdigest()
              for f in args.output.rglob('*') if f.is_file()}
    write_json(args.output/'MANIFEST_SHA256.json',manifest)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('layouts','synthetic_profile')},indent=2))


if __name__=='__main__': main()
