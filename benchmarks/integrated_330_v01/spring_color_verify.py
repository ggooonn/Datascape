"""Delivered-byte readback against pinned original sources and numeric IR."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import argparse, json
from . import spring_color_execution as c


def command(data):
    data=dict(data)
    for k in ('xyz','axis_velocity_mm_min'):
        if data.get(k) is not None:data[k]=tuple(data[k])
    return c.Command(**data)


def decode_coupon(u):
    out=dict(u);out['original']=c.decode_stroke(u['original']);out['fragments']=[]
    for f in u['fragments']:
        s=f['stroke'];s=dict(s)
        s['points']=tuple(c.Point(**p) for p in s['points'])
        s['source_locations']=tuple(c.SourceLocation(**p) for p in s['source_locations'])
        s['source_spans']=tuple(c.SourceSpan(**p) for p in s['source_spans'])
        out['fragments'].append(c.Fragment(c.Stroke(**s),f['panel'],f['setup'],tuple(tuple(v) for v in f['work_xy'])))
    return out


def verify(output,context,independent=None):
    out=Path(output);policy=c.read(out/'policy.json')
    c.require(policy==c.read(c.POLICY),'Delivered policy differs from reproducible configuration')
    hashes=c.read(out/'MANIFEST_SHA256.json')
    for name,expected in hashes.items():c.require(c.sha(out/name)==expected,'Delivered bytes changed: '+name)
    context=c.recover(context,policy)
    plan,color,ink,units,palette=c.load_inputs(context,policy)
    c.overlap_audit(units,ink,policy);selected=c.select(units,policy)
    c.require(c.read(out/'source_selection.json.gz')==json.loads(json.dumps([c.unit_record(u) for u in units])),'Selection or original source/profiles changed')
    edges,shapes=c.layering(selected);flat,batches,wet=c.schedule(selected,edges,policy)
    graph=c.read(out/'layering_constraints.json.gz')
    c.require(graph['edges']==[list(e) for e in edges],'Layering graph changed or incomplete')
    profile=c.Profile.load(out/'profile.color.UNMEASURED.json');c.require(profile.data==c.make_profile(policy).data,'Color profile changed')
    selected_map={u['id']:i for i,u in enumerate(selected)};programs={};stage_ids=[]
    coupon=[decode_coupon(u) for u in c.read(out/'calibration_source_units.json.gz')]
    for path in sorted(out.glob('*.commands.json.gz')):
        name=path.name.removesuffix('.commands.json.gz');commands=[command(r) for r in c.read(path)]
        ids=[x.source_id for x in commands if x.action=='source_begin']
        if 'RESPONSE_COUPON' in name:us=coupon;index={u['id']:i for i,u in enumerate(us)}
        elif 'STATIONS_ONLY' in name:us=[];index={}
        else:us=selected;index=selected_map
        order=[index[i] for i in ids]
        if 'COMPLETE' in name:c.require(order==flat,'Complete order differs from protected schedule')
        elif us is selected:stage_ids.extend(ids)
        reports={}
        for air in (False,True):
            label=name.replace('COLOR','AIR',1) if air else name
            text=(out/(label+'.gcode')).read_text();compressed=c.gzip.decompress((out/(label+'.gcode.gz')).read_bytes()).decode()
            c.require(text==compressed,'Plain/gzip numerical programs differ')
            cs=c.air_projection(commands,profile) if air else commands
            report=c.verify_numeric(text,cs,profile,us,order,policy,air)
            c.require(report==c.read(out/(label+'.readback.json')),'Saved numeric readback differs')
            reports['air' if air else 'color']=report
        material=c.read(out/(name+'.material.json.gz'))
        c.require(sum(r['reason']=='pigment_change' for r in material['loads'])==material['pigment_changes'],'Actual change count')
        c.require(all(r['wash_performed']==(r['reason']=='pigment_change') for r in material['loads']),'Same-pigment reload unexpectedly washes')
        c.require(sum(r['action']=='terminal_wash' for r in material['station_operations'])==3,'Terminal water visits')
        if us is selected:
            c.require(len(order)==len(set(order)),'Source executed twice within program')
            for e in material['events']:
                c.require(e['distance_since_load_mm']<=policy['distance_limit_mm']+selected[selected_map[e['source_id']]]['length_mm']+1e-9,'Reload exceeded an atomic source boundary')
        programs[name]=reports
    expected_ids=[selected[i]['id'] for i in flat]
    c.require(stage_ids==expected_ids,'Separated programs do not reproduce complete source order exactly')
    comp=c.read(out/'future_dual_brush_compatibility.json.gz')
    c.require(len(comp['records'])==1851 and all(not r['geometry_in_primary_color'] for r in comp['records']),'PR35 deferral duplication')
    c.require(set(expected_ids).isdisjoint({r['source_id'] for r in comp['records']}),'Ink-deferred IDs were blindly added')
    independent_count=None
    if independent:
        other=Path(independent);independent_count=1
        c.require(c.sha(other/'MANIFEST_SHA256.json')==c.sha(out/'MANIFEST_SHA256.json'),'Independent manifest differs')
        for name,expected in hashes.items():
            c.require(c.sha(other/name)==expected,'Independent generation differs: '+name);independent_count+=1
    images=[]
    from PIL import Image
    for path in sorted(out.glob('*.png')):
        with Image.open(path) as im:im.verify()
        images.append(path.name)
    return dict(all_checks_passed=True,program_pairs_verified=len(programs),programs=programs,
        selected_source_count=len(selected),protected_edges_verified=len(edges),
        complete_and_stage_source_orders_identical=True,PR35_ink_deferred_duplicates=0,
        exact_pinned_reference_hashes=c.read(out/'summary.json')['pinned_reference_hashes'],
        original_source_arc_pressure_and_widths_verified=True,images_decoded=len(images),
        independent_files_compared=independent_count,measured_physical_clearance=False,machine_authorized=False)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--context',type=Path,required=True)
    ap.add_argument('--independent',type=Path);ap.add_argument('--report',type=Path)
    a=ap.parse_args();result=verify(a.output,a.context,a.independent)
    if a.report:c.save(a.report,result)
    print(json.dumps({k:v for k,v in result.items() if k!='programs'},indent=2))
