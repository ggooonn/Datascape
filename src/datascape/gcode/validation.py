"""Full pressure/geometry lineage audit without changing any artistic input."""
from collections import Counter
from math import hypot,isclose
from .clipping import clip_stroke


def require(condition,message):
    if not condition: raise ValueError(message)


def validate_layout(strokes,layout):
    seen=set(); fragments=0; vertices=0; source_length=0.; clipped_length=0.; stats=Counter()
    for s in strokes:
        require(s.stroke_id not in seen,'duplicate source');seen.add(s.stroke_id)
        arcs=[0.]
        for a,b in zip(s.points,s.points[1:]): arcs.append(arcs[-1]+hypot(b.x-a.x,b.y-a.y))
        source_length+=arcs[-1]
        coverage=[[] for _ in s.points[1:]]
        for panel in layout.panels:
            for part in clip_stroke(s,panel):
                fragments+=1;vertices+=len(part.points);stats[f'{panel.name}_{s.medium}']+=1
                require(part.origin_id==s.stroke_id and part.sequence==s.sequence and part.order_group==s.order_group,'identity/order')
                require(part.medium==s.medium and part.color_slot==s.color_slot,'material binding')
                require(part.pressure_sidecar_sha256==s.pressure_sidecar_sha256,'pressure source SHA')
                require(part.reorderable==s.reorderable and part.reversible==s.reversible,'ordering locks')
                last_arc=-1
                for point,loc in zip(part.points,part.source_locations):
                    require(0<=loc.segment<len(s.points)-1 and 0<=loc.t<=1,'segment parameter bounds')
                    a,b=s.points[loc.segment:loc.segment+2]
                    for value,expected in ((point.x,a.x+loc.t*(b.x-a.x)),(point.y,a.y+loc.t*(b.y-a.y)),
                                           (point.pressure,a.pressure+loc.t*(b.pressure-a.pressure))):
                        require(isclose(value,expected,rel_tol=1e-12,abs_tol=1e-10),'interpolated source binding')
                    expected_arc=arcs[loc.segment]+loc.t*(arcs[loc.segment+1]-arcs[loc.segment])
                    require(isclose(loc.arc_mm,expected_arc,abs_tol=1e-9),'original arclength')
                    require(loc.arc_mm>=last_arc,'original direction');last_arc=loc.arc_mm
                for span in part.source_spans:
                    require(0<=span.t_start<span.t_end<=1,'positive parameter span')
                    coverage[span.segment].append((span.t_start,span.t_end))
                    clipped_length+=span.arc_end_mm-span.arc_start_mm
        # The complete panel partition must cover each source segment once, with
        # no duplicate boundary-only span or omitted expressive short interval.
        for spans in coverage:
            cursor=0.
            for start,end in sorted(spans):
                require(isclose(start,cursor,abs_tol=1e-12),'missing or duplicated source interval')
                cursor=end
            require(isclose(cursor,1.,abs_tol=1e-12),'incomplete original segment coverage')
    require(isclose(source_length,clipped_length,rel_tol=1e-10,abs_tol=1e-6),'length conservation')
    return {'sources_covered':len(seen),'fragments':fragments,'fragment_vertices':vertices,
            'stream_fragment_counts':dict(stats),'original_drawing_mm':source_length,
            'clipped_drawing_mm':clipped_length,'all_pressure_segment_bindings_valid':True,
            'complete_source_parameter_partition':True,'original_direction_preserved':True}


def verify_written_outputs(output,strokes):
    """Read actual compressed exports, not only in-memory planner results."""
    import gzip
    import hashlib
    import json
    from itertools import groupby
    from pathlib import Path
    from .binding import SIDECAR_SHA
    root=Path(output)
    manifest=json.loads((root/'MANIFEST_SHA256.json').read_text())
    for path,sha in manifest.items():
        require(hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,'output file hash: '+path)
    summary=json.loads((root/'summary.json').read_text())
    require(summary['offline_only'] and summary['full_scene'],'full offline output required')
    original={s.stroke_id:s for s in strokes}
    ids=set();seen_sources=set();count=0;pressure_count=0;comments=0
    for fragpath in root.glob('layout_*/*.fragments.jsonl.gz'):
        eventpath=fragpath.with_name(fragpath.name.replace('.fragments.','.events.'))
        previewpath=fragpath.with_name(fragpath.name.replace('.fragments.jsonl.','.preview.gcode.txt.'))
        with gzip.open(fragpath,'rt') as fh,gzip.open(eventpath,'rt') as eh:
            groups=groupby((json.loads(line) for line in eh),key=lambda e:e['fragment_id'])
            for line in fh:
                f=json.loads(line);piece=f['stroke'];ident=piece['stroke_id'];source=original[piece['source_id']]
                require(ident not in ids,'duplicate exported fragment');ids.add(ident);seen_sources.add(source.stroke_id)
                group_id,events=next(groups);events=list(events);count+=len(events)
                require(group_id==ident,'fragment/event export order')
                require(piece['pressure_sidecar_sha256']==SIDECAR_SHA,'export sidecar SHA')
                require(len(events)==len(piece['points'])+6,'missing/extra motion events')
                expected=['lift','travel','approach','initial_contact','pressure_variation']+['draw']*(len(piece['points'])-1)+['release','lift']
                require([e['action'] for e in events]==expected,'contact/release event order')
                samples=[e for e in events if e['artistic_pressure'] is not None]
                require(len(samples)==len(piece['points']),'missing exported pressure sample')
                for i,(point,loc,event,work_xy) in enumerate(zip(piece['points'],piece['source_locations'],samples,f['work_xy'])):
                    a,b=source.points[loc['segment']:loc['segment']+2];t=loc['t']
                    require(isclose(point['pressure'],a.pressure+t*(b.pressure-a.pressure),abs_tol=1e-12),'written pressure interpolation')
                    require(event['artistic_pressure']==point['pressure'] and event['source_vertex']==i,'written event pressure')
                    require(event['work_xy']==work_xy,'written event/work coordinate')
                    pressure_count+=1
                for e in events:
                    require(e['machine_xyz'] is None and e['calibrated_z_mm'] is None,'unexpected physical trajectory')
                    require(e['pressure_sidecar_sha256']==SIDECAR_SHA and e['source_id']==source.stroke_id,'event lineage')
            require(next(groups,None) is None,'orphan exported event group')
        with gzip.open(previewpath,'rt') as h:
            for line in h:
                require(line.startswith(';'),'executable/uncommented preview line');comments+=1
    require(len(seen_sources)==len(original),'source omitted in exports')
    with gzip.open(next(root.glob('layout_*/setup_order.jsonl.gz')),'rt') as h:
        references=[json.loads(line)['fragment_id'] for line in h]
        require(len(references)==len(ids) and set(references)==ids,'setup order manifest coverage')
    return {'output_manifest_entries_verified':len(manifest),'exported_fragments_verified':len(ids),
            'source_strokes_covered':len(seen_sources),'motion_events_verified':count,
            'fragment_artistic_pressure_samples_verified':pressure_count,
            'comment_only_lines_verified':comments,'all_physical_trajectory_fields_absent':True,
            'all_exported_pressure_matches_original_segment':True}


def main():
    import argparse,json
    from .binding import load_bound_spring
    p=argparse.ArgumentParser(description='Verify written full Spring v0.2 offline exports')
    p.add_argument('--output',required=True);p.add_argument('--machine',required=True);p.add_argument('--provenance',required=True)
    a=p.parse_args();strokes,_=load_bound_spring(a.machine,a.provenance)
    print(json.dumps(verify_written_outputs(a.output,strokes),indent=2))


if __name__=='__main__': main()
