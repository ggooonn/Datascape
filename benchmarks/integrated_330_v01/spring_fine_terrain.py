"""Selective terminal terrain reassignment, not an additional texture pass."""
from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
from dataclasses import asdict
import argparse,subprocess,gzip,json,base64
import numpy as np
from . import spring_ink_v02 as v
from . import spring_physical_ink as s
from . import spring_panels_contact20 as n
from .spring_physical_ink_review import render,sheet

PIN='38b32a68bb58c502c4e0fba60eccf9205ecbd4c5'
POLICY=s.ROOT/'config/spring_fine_terrain_v01/policy.json'
BASE='docs/spring_ink_v02/review/'

def frozen(name):
    rel=BASE+name;raw=subprocess.check_output(['git','show',PIN+':'+rel],cwd=s.ROOT)
    s.require(raw==(s.ROOT/rel).read_bytes(),'PR39 input changed '+name)
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

def graph_descendants(edges,ids):
    graph=defaultdict(list)
    for a,b in v.project_edges(edges,ids):graph[a].append(b)
    result={}
    for i in ids:
        seen=set();todo=list(graph[i])
        while todo:
            j=todo.pop()
            if j not in seen:seen.add(j);todo.extend(graph[j])
        result[i]=seen
    return result

def choose(records,edges,cfg):
    main={r['index'] for r in records if r['classification']=='main'}
    active={r['index'] for r in records if r['classification'] in ('main','fine')}
    descend=graph_descendants(edges,active);review=[];candidates=[]
    for r in records:
        i=r['index'];fam=r['family'];L=r['length_mm'];reason=None
        if i not in main or fam not in ('A','Soil','rock') or r['depth_band']=='far':continue
        if not cfg['minimum_length_mm']<=L<=cfg['maximum_length_mm']:continue
        if descend[i]&main:reason='Protected main successor prevents a main-then-fine reassignment'
        elif fam=='A':reason='A rhythm remains principal main-brush structure'
        elif fam=='rock' and r['role'] not in cfg['eligible_rock_roles']:reason='Preserve principal rock outlines/joints in main brush'
        elif fam=='Soil' and r['role'] not in cfg['eligible_soil_roles']:reason='Not a selected ground-support role'
        item=dict(index=i,source_id=r['source_id'],family=fam,role=r['role'],depth_band=r['depth_band'],length_mm=L,
                  decision='reject' if reason else 'eligible',reason=reason or 'Terminal localized ground/rock articulation')
        review.append(item)
        if not reason:candidates.append(r)
    selected=[];owners=Counter();centers=[]
    for r in sorted(candidates,key=lambda r:(0 if r['role']=='integration-contact-support' else 1 if r['family']=='Soil' else 2,r['length_mm'],r['index'])):
        center=np.mean(r['xy_mm'],axis=0);entry=next(x for x in review if x['index']==r['index'])
        if len(selected)>=cfg['maximum_terrain_support_sources'] or owners[r['owner']]>=cfg['maximum_per_owner'] or any(np.linalg.norm(center-c)<cfg['minimum_center_spacing_mm'] for c in centers):
            entry.update(decision='reject',reason='Selective count/owner/spacing cap');continue
        selected.append(r['index']);owners[r['owner']]+=1;centers.append(center);entry['decision']='select'
    return selected,review

def write_pair(out,label,groups,fragments,p,policy,fine):
    commands,material=n.build(groups,fragments,p,policy,20)
    prof=s.Profile.from_dict(frozen('profile.fine.PROVISIONAL.json')) if fine else p
    if fine:commands=v.fine_transform(commands,prof)
    n.audit_ir(commands,material,groups,fragments,prof)
    results={}
    for is_air,cmd in [(False,commands),(True,s.air_projection(commands,prof))]:
        name='SPRING_P2_'+('AIR' if is_air else 'INK')+'_'+label+'_REVIEW'
        results[name]=v.write(out,name,cmd,prof,groups,fragments,is_air,fine)
    s.save(out/(label+'.execution.json.gz'),dict(groups=groups))
    s.save(out/(label+'.IR.json.gz'),[asdict(c) for c in commands])
    s.save(out/(label+'.reload.json.gz'),material);s.save(out/(label+'.stations.json.gz'),n.station_records(commands,prof))
    return results,n.summary(commands,material,prof)

def previews(out,rows,fs,base_main,base_fine,newmain,newfine,support,cfg):
    """Provide actual authored geometry and a separately labeled unmeasured width proxy."""
    def events(g):return [e for group in g for e in group]
    for name,m,f in [('A',base_main,base_fine),('B',newmain,newfine)]:
        render(out/(name+'_authored.png'),rows,fs,events(m)+events(f),(300,0,600,900),2)
        proxy=deepcopy(rows)
        for e in events(f):
            r=proxy[e['source']];r['width_mm']*=cfg['fine_preview_width_factor_unmeasured']
            if 'width_profile_mm' in r:r['width_profile_mm']=[x*cfg['fine_preview_width_factor_unmeasured'] for x in r['width_profile_mm']]
        render(out/(name+'_proxy.png'),proxy,fs,events(m)+events(f),(300,0,600,900),2)
    sheet(out,[out/'A_proxy.png',out/'B_proxy.png'],['A PR39 / illustrative fine width','B selected terrain / illustrative width'],'full_comparison.png',(600,1800))
    render(out/'support_map.png',rows,fs,[e for e in events(newfine) if e['source'] in support],(300,0,600,900),2)
    centers=[np.mean(rows[i]['xy_mm'],axis=0) for i in support]
    regions=[]
    for c in centers:
        if all(np.linalg.norm(c-a)>65 for a in regions):regions.append(c)
    for k,c in enumerate(regions[:3]):
        x=float(np.clip(c[0]-55,300,490));y=float(np.clip(c[1]-65,0,770));bounds=(x,y,x+110,y+130)
        for name,m,f in [('A',base_main,base_fine),('B',newmain,newfine)]:
            proxy=deepcopy(rows)
            for e in events(f):
                r=proxy[e['source']];r['width_mm']*=.45
                if 'width_profile_mm' in r:r['width_profile_mm']=[w*.45 for w in r['width_profile_mm']]
            render(out/f'crop{k}_{name}.png',proxy,fs,events(m)+events(f),bounds,5)
        sheet(out,[out/f'crop{k}_A.png',out/f'crop{k}_B.png'],['A PR39','B terrain support'],f'crop{k}_comparison.png',(650,760))
    s.save(out/'subset_bounds.json',[dict(center=list(map(float,c))) for c in regions[:3]])

def svg_preview(path,rows,main,fine,support,cfg):
    from xml.sax.saxutils import escape
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="900mm" viewBox="300 0 300 900"><title>Authored geometry; fine width factor0.45 illustrative and unmeasured</title><rect x="300" y="0" width="300" height="900" fill="white"/>']
    for role,groups in [('main',main),('fine',fine)]:
        parts.append('<g id="'+role+'" fill="none" stroke-linecap="round" stroke-linejoin="round">')
        for group in groups:
            for e in group:
                i=e['source'];r=rows[i];width=r['width_mm']*(cfg['fine_preview_width_factor_unmeasured'] if role=='fine' else 1)
                color='#007f79' if i in support else '#4c5b61' if e['ink']=='LIGHT_INK' else '#111111'
                points=' '.join(f'{x:.12g},{y:.12g}' for x,y in r['xy_mm'])
                parts.append('<polyline id="s'+str(i)+'" data-source-id="'+escape(r['id'],{'"':'&quot;'})+'" data-role="'+('fine_terrain_support' if i in support else role)+'" points="'+points+'" stroke="'+color+'" stroke-width="'+str(width)+'"/>')
        parts.append('</g>')
    parts.append('</svg>');Path(path).write_text(''.join(parts))

def generate(output,context):
    out=Path(output);s.require(not out.exists(),'New output required');out.mkdir(parents=True)
    cfg=s.read(POLICY);_,rows,fragments=s.load_inputs(s.recover_context(Path(context)))
    records=frozen('source_roles.json.gz');indexed={r['index']:r for r in records}
    oldmain=frozen('BAEGUNMO_MAIN.execution.json.gz')['groups'];oldfine=frozen('FINE_DETAIL.execution.json.gz')['groups']
    orig=n.frozen('SINGLE_PASS.execution_manifest.json.gz')['events'];ids=set(indexed);rank={e['source']:k for k,e in enumerate(orig) if e['source'] in ids}
    edges=list(map(tuple,n.frozen('protected_source_dependencies.json.gz')['edges']));A=[e['source'] for e in orig if e['source'] in ids and indexed[e['source']]['family']=='A']
    edges=sorted(set(edges)|set(zip(A,A[1:])))
    support,review=choose(records,edges,cfg);s.require(support,'No justified terrain candidates')
    main=[[e for e in group if e['source'] not in support] for group in oldmain];main=[g for g in main if g]
    fineids=[e['source'] for g in oldfine for e in g]+support
    fullrecords=[{} for _ in fragments]
    for r in records:fullrecords[r['index']]=r
    fine,diag=v.schedule(fineids,fullrecords,edges,rank,10)
    order=[e['source'] for g in main+fine for e in g];position={i:k for k,i in enumerate(order)}
    protected=v.project_edges(edges,set(order));s.require(all(position[a]<position[b] for a,b in protected),'Two-stage precedence violation')
    s.require(len(order)==len(set(order))==1209,'Duplicated or lost intended ink source')
    s.require({e['source'] for g in main for e in g}.isdisjoint(fineids),'Brush duplication')
    p=s.Profile.from_dict(frozen('profile.small.json'));policy=n.frozen('policy.json');policy['contact_limit']=20
    s.save(out/'profile.small.json',p.data);s.save(out/'profile.fine.PROVISIONAL.json',frozen('profile.fine.PROVISIONAL.json'));s.save(out/'policy.json',cfg)
    jobs={};timings={}
    for label,g,isfine in [('TERRAIN_MAIN',main,False),('VEGETATION_TERRAIN_FINE',fine,True)]:
        j,t=write_pair(out,label,g,fragments,p,policy,isfine);jobs.update(j);timings[label]=t
    # Exact PR39 numerical control, without regenerating or approximating its output.
    for role in ('BAEGUNMO_MAIN','FINE_DETAIL'):
        for mode in ('INK','AIR'):
            name=f'SPRING_P2_{mode}_{role}_REVIEW';rel=BASE+name+'.gcode.gz'
            raw=subprocess.check_output(['git','show',PIN+':'+rel],cwd=s.ROOT)
            (out/(name+'.gcode.gz')).write_bytes(raw);(out/(name+'.gcode')).write_bytes(gzip.decompress(raw))
    for r in records:
        i=r['index'];r['PR39_role']=r['classification'];r['review_role']='fine_terrain_support' if i in support else 'fine_vegetation_detail' if r['classification']=='fine' else 'baegunmo_main' if r['classification']=='main' else r['classification']
        r['source_geometry_or_pressure_changed']=False
    s.save(out/'source_roles.json.gz',records);s.save(out/'terrain_selection_review.json',review)
    s.save(out/'color_handoff.json.gz',dict(records=[r for r in records if r['classification']=='color'],color_source_count=642,
        fine_terrain_support_not_color=support,no_color_Gcode=True,palette_finalized=False,
        next_inputs=['this reviewed ink candidate','PR40 seasonal color framework (not imported here)'],avoid_strong_D4_spring_summer=True))
    fs=n.frozen('source_features.json.gz');previews(out,rows,fs,oldmain,oldfine,main,fine,support,cfg)
    svg_preview(out/'A_PR39_layers.svg',rows,oldmain,oldfine,[],cfg)
    svg_preview(out/'B_terrain_layers.svg',rows,main,fine,support,cfg)
    # Identical authored-width composites prove this is a brush reassignment, not extra lines.
    # Compare source sets/hashes rather than order-dependent alpha raster compositing.
    s.save(out/'verification.json',dict(baseline=PIN,jobs=jobs,terrain_support_ids=support,terrain_support_source_ids=[indexed[i]['source_id'] for i in support],
        terrain_support_by_family=dict(Counter(indexed[i]['family'] for i in support)),terrain_support_by_depth=dict(Counter(indexed[i]['depth_band'] for i in support)),
        canonical_source_count=1851,intended_ink_sources=1209,color_sources=642,omitted_sources=0,main_sources=len(order)-len(fineids),fine_sources=len(fineids),
        fine_original_sources=202,additional_drawing_passes=0,no_geometry_duplication=True,
        protected_edges_checked=len(protected),violations=0,main_is_exact_PR39_subsequence=True,allocation_and_pressure_unchanged=True,
        A_support_rejected_to_preserve_A_order=True,fine_scheduler=diag,timings=timings,machine_authorized=False))
    lines=['# Fine terrain support / modeled minutes','','No physical width/runtime certification. PR39 motion/pressure/stations unchanged; fine profile provisional.','','| Stage | Sources | Loads | Switches | Modeled minutes |','| --- | ---: | ---: | ---: | ---: |']
    for name,t in timings.items():lines.append(f"| {name} | {t['actual_paper_engagements']} | {t['total_loads']} | {t['concentration_switches']} | {t['modeled_seconds']/60:.3f} |")
    (out/'RUNTIME.md').write_text('\n'.join(lines)+'\n')
    s.save(out/'MANIFEST_SHA256.json',{f.name:s.sha(f) for f in sorted(out.iterdir()) if f.name!='MANIFEST_SHA256.json'})
    return audit(out,context)

def audit(output,context,independent=None):
    out=Path(output);_,rows,fragments=s.load_inputs(Path(context));r=s.read(out/'verification.json');records=s.read(out/'source_roles.json.gz')
    s.require(len(records)==1851 and len({x['source_id'] for x in records})==1851,'Source accounting')
    for item in records:s.require(item['source_record_sha256']==s.digest(rows[item['index']]) and item['canonical_stroke_sha256']==s.digest(asdict(fragments[item['index']].stroke)),'Canonical geometry/width/pressure hash')
    used=[];checks={}
    for label,isfine in [('TERRAIN_MAIN',False),('VEGETATION_TERRAIN_FINE',True)]:
        p=s.Profile.load(out/('profile.fine.PROVISIONAL.json' if isfine else 'profile.small.json'))
        groups=s.read(out/(label+'.execution.json.gz'))['groups'];used.extend(e['source'] for g in groups for e in g)
        cmd=[s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None}) for c in s.read(out/(label+'.IR.json.gz'))]
        n.audit_ir(cmd,s.read(out/(label+'.reload.json.gz')),groups,fragments,p)
        for air,commands in [(False,cmd),(True,s.air_projection(cmd,p))]:
            name=f'SPRING_P2_{"AIR" if air else "INK"}_{label}_REVIEW';raw=(out/(name+'.gcode')).read_bytes()
            s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes())==raw,'Gzip differs')
            checks[name]=v.verify(raw.decode(),commands,p,groups,fragments,air,isfine)
    s.require(len(used)==len(set(used))==1209,'Stage duplication')
    s.require(set(used)=={x['index'] for x in records if x['classification'] in ('main','fine')},'Intended source set changed')
    edge=n.frozen('protected_source_dependencies.json.gz')['edges'];orig=n.frozen('SINGLE_PASS.execution_manifest.json.gz')['events'];idx={x['index']:x for x in records};A=[e['source'] for e in orig if e['source'] in idx and idx[e['source']]['family']=='A'];edge=list(map(tuple,edge))+list(zip(A,A[1:]));pos={i:k for k,i in enumerate(used)}
    s.require(all(pos[a]<pos[b] for a,b in v.project_edges(edge,set(used))),'Delivered protected order changed')
    manifest=s.read(out/'MANIFEST_SHA256.json');s.require(all(s.sha(out/name)==h for name,h in manifest.items()),'Delivered SHA differs')
    equality={}
    if independent:
        for name in manifest:equality[name]=(out/name).read_bytes()==(Path(independent)/name).read_bytes()
        s.require(all(equality.values()),'Non-deterministic output')
    result=dict(programs=checks,all_source_width_XY_pressure_hashes_verified=True,disjoint_complete_intended_ink=True,independent_bytes=equality,machine_authorized=False)
    s.save(out/'delivered_audit.json',result);return result

if __name__=='__main__':
    a=argparse.ArgumentParser(__doc__);a.add_argument('--output',required=True);a.add_argument('--context',required=True);a.add_argument('--verify',action='store_true');a.add_argument('--independent');args=a.parse_args()
    result=audit(args.output,args.context,args.independent) if args.verify else generate(args.output,args.context)
    print(json.dumps(result))
