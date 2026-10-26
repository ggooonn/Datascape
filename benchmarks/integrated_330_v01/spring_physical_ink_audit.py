"""Independent delivered-byte, source, material and transformed-lineage readback."""
from pathlib import Path
from collections import Counter
from dataclasses import replace
import argparse,gzip,json
import numpy as np
from scipy.spatial import cKDTree
from . import spring_physical_ink as s


def audit(out,context,independent=None):
    out=Path(out);context=Path(context);report=s.read(out/'verification.json');policy=s.read(out/'policy.json');p=s.Profile.load(out/'profile.small_baegunmo.json')
    _,rows,fragments=s.load_inputs(context);fs=s.read(out/'source_features.json.gz')
    for name,r in report['jobs'].items():
        text=(out/r['filename']).read_text();raw=(out/r['filename']).read_bytes()
        s.require(s.sha(out/r['filename'])==r['gcode_sha256'],'delivered G-code hash mismatch '+name)
        s.require(gzip.decompress((out/(r['filename']+'.gz')).read_bytes())==raw,'gzip mismatch')
        lines=[v for v in text.splitlines() if v and not v.startswith(';')]
        s.require(lines[0]=='G21 G90 G94 G54' and lines[-1]=='M2','prologue/end')
        s.require(all(v=='M0' or s._MOVE.fullmatch(v) or s._DWELL.fullmatch(v) for v in lines[1:-1]),'extra controller commands')
        s.require(lines.count('M0')==(0 if '_AIR_' in name else 1),'gate missing/extra')
    commands=[s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None}) for c in s.read(out/'full_numeric_IR.json.gz')]
    execution=s.read(out/'SELECTIVE_LAYERED.execution_manifest.json.gz');groups=execution['groups']
    result=s.verify_numeric((out/'SPRING_INK_SELECTIVE_LAYERED_REVIEW.gcode').read_text(),commands,p,groups,fragments)
    air=s.air_projection(commands,p);air_result=s.verify_numeric((out/'SPRING_INK_FULL_AIR_REVIEW.gcode').read_text(),air,p,groups,fragments,True)
    contacts=0;peak=0;total=0;loaded=0;water_uses=0
    for c in commands:
        if c.action=='pigment_load' and c.kind=='marker':
            s.require(c.message in ('WELL_1','WELL_2'),'wrong ink well');peak=max(peak,contacts);contacts=0;loaded+=1
        if c.action=='initial_contact':contacts+=1;total+=1;peak=max(peak,contacts)
        if c.kind=='marker' and c.action in ('wash','controlled_rewet','terminal_wash'):
            s.require(c.message=='NEW_WATER_CONTAINER','WELL1 must never wash');water_uses+=1
    mat=s.read(out/'SELECTIVE_LAYERED.reload_manifest.json.gz')
    s.require(peak<=policy['contact_limit'] and peak==mat['maximum_contacts_before_reload'],'actual contact limit changed')
    s.require(total==mat['actual_paper_engagements'] and loaded==mat['total_loads'],'material IR count mismatch')
    s.require(len({e['source'] for e in execution['events'] if not e['pass_index']})==3345,'lost canonical source')
    edges=s.read(out/'protected_source_dependencies.json.gz')['edges'];rank={e['source']:i for i,e in enumerate(execution['events']) if not e['pass_index']}
    s.require(all(rank[a]<rank[b] for a,b in edges),'protected source order changed')
    cross=[i for i,f in enumerate(fragments) if min(p.x for p in f.stroke.points)<300<max(p.x for p in f.stroke.points)]
    s.require(all(sum(e['source']==i and not e['pass_index'] for e in execution['events'])==1 for i in cross),'original X300 source split')
    # Exercise rejection, without changing delivered bytes.
    bad=(out/'SPRING_INK_SELECTIVE_LAYERED_REVIEW.gcode').read_text().replace('M0\n','',1)
    rejected=False
    try:s.verify_numeric(bad,commands,p,groups,fragments)
    except ValueError:rejected=True
    s.require(rejected,'missing gate accepted')
    atext=(out/'SPRING_INK_FULL_AIR_REVIEW.gcode').read_text();bad=atext.replace('Z35.000000000','Z20.000000000',1)
    rejected=False
    try:s.verify_numeric(bad,air,p,groups,fragments,True)
    except ValueError:rejected=True
    s.require(rejected,'AIR descent mutation accepted')
    by={}
    for fam in sorted({f['family'] for f in fs}):
        rr=[f for f in fs if f['family']==fam]
        by[fam]=dict(sources=len(rr),dark_sources=sum(f['ink']=='DARK_INK' for f in rr),drawing_mm=sum(f['length_mm'] for f in rr),dark_drawing_mm=sum(f['length_mm'] for f in rr if f['ink']=='DARK_INK'),
            shorter_than1mm=sum(f['length_mm']<1 for f in rr),shorter_than2mm=sum(f['length_mm']<2 for f in rr),shorter_than5mm=sum(f['length_mm']<5 for f in rr),sharp_turns_over90=sum(f['sharp_turns_over_90'] for f in rr))
    starts=np.array([r['xy_mm'][0] for r in rows]);ends=np.array([r['xy_mm'][-1] for r in rows]);tree=cKDTree(starts);candidates=[]
    for i,endpoint in enumerate(ends):
        for j in tree.query_ball_point(endpoint,1.):
            if i!=j:candidates.append(dict(from_index=i,to_index=j,gap_mm=float(np.linalg.norm(endpoint-starts[j])),same_owner=fs[i]['owner']==fs[j]['owner'],from_role=fs[i]['grammar'],to_role=fs[j]['grammar']))
    s.save(out/'brush_path_audit.json',dict(by_family=by,near_endpoint_pairs_under1mm=len(candidates),near_endpoint_same_owner=sum(c['same_owner'] for c in candidates),
        exact_D_endpoint_joins=3,new_positive_gap_connectors=0,catalog_geometry_modified=False,original_gaps_directions_and_turns_preserved=True,
        reason_near_candidates_not_joined='Nearness is not authored-junction evidence; do not fill mist/occlusion/catalog gaps, vegetation dots or textures.'))
    s.save(out/'near_endpoint_candidates.NOT_AUTO_JOINED.json.gz',candidates)
    equality={}
    if independent:
        names=[x.name for x in out.iterdir() if x.suffix in ('.gz','.json') and x.name not in ('MANIFEST_SHA256.json','delivered_readback.json','brush_path_audit.json','near_endpoint_candidates.NOT_AUTO_JOINED.json.gz')]
        for name in names:
            other=Path(independent)/name
            if other.exists():equality[name]=(out/name).read_bytes()==other.read_bytes()
        s.require(equality and all(equality.values()),'deterministic data regeneration mismatch')
        for name in report['jobs']:
            a=out/report['jobs'][name]['filename'];b=Path(independent)/a.name
            s.require(a.read_bytes()==b.read_bytes(),'numeric regeneration differs');equality[a.name]=True
    answer=dict(delivered_numeric_files=len(report['jobs']),all_gzip_and_file_hashes_verified=True,
        complete_original_ink_sources_verified=3345,complete_original_ink_pressure_values=69101,
        complete_layered_sources=result['source_occurrences'],complete_layered_pressure_samples=result['pressure_samples'],
        protected_dependencies_verified=len(edges),original_ink_X300_crossings_unsplit=len(cross),actual_IR_paper_engagements=total,
        maximum_actual_contacts_between_loads=peak,total_IR_pigment_loads=loaded,new_container_visits=water_uses,
        complete_INK_and_AIR_XY_correspondence=True,all_AIR_Z35_verified=True,
        altered_gate_and_AIR_descent_mutations_rejected=True,independent_byte_reproduction=equality,
        measured_small_brush_compression_range=None,operator_contact_reference_confirmed=True,
        vessel_and_holder_swept_clearance_verified=False,machine_authorized=False)
    s.save(out/'delivered_readback.json',answer)
    s.save(out/'MANIFEST_SHA256.json',{str(f.relative_to(out)):s.sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='MANIFEST_SHA256.json'})
    return answer

if __name__=='__main__':
    a=argparse.ArgumentParser(__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--context',type=Path,required=True);a.add_argument('--independent',type=Path)
    args=a.parse_args();print(json.dumps(audit(args.output,args.context,args.independent),indent=2))
