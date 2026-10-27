"""Spatially selective A brush roles; retain compositing, audit scheduler barriers."""
from pathlib import Path
from dataclasses import asdict
from copy import deepcopy
from collections import defaultdict,Counter
import argparse,gzip,json,subprocess,heapq
import numpy as np
from shapely.geometry import LineString
from shapely import STRtree
from . import spring_physical_ink as s
from . import spring_panels_contact20 as n
from . import spring_ink_v02 as v
from . import spring_fine_terrain as t
from .spring_physical_ink_review import render,sheet

PIN='172601cbe9e19d013d159b9dc9cd64b985c1ae1f'
BASE='docs/spring_fine_terrain_v01/review/'
POLICY=s.ROOT/'config/spring_a_hierarchy_v01/policy.json'

def frozen(name):
    rel=BASE+name;raw=subprocess.check_output(['git','show',PIN+':'+rel],cwd=s.ROOT)
    s.require(raw==(s.ROOT/rel).read_bytes(),'PR41 input changed '+name)
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

def dependency_review(rows,fs,ids,original_order):
    raw=set(map(tuple,n.frozen('protected_source_dependencies.json.gz')['edges']))
    A=[i for i in original_order if fs[i]['family']=='A'];chain=list(zip(A,A[1:]))
    lines={i:LineString(rows[i]['xy_mm']) for i in A}
    shapes={i:lines[i].buffer(max(rows[i].get('width_profile_mm',[rows[i]['width_mm']]))/2,quad_segs=6) for i in A}
    retained=set(raw);review=[]
    for a,b in chain:
        gap=shapes[a].distance(shapes[b]);same=fs[a]['parent_contour']==fs[b]['parent_contour']
        keep=(a,b) in raw or same or gap<=.5
        review.append(dict(from_index=a,to_index=b,from_id=fs[a]['source_id'],to_id=fs[b]['source_id'],
            authored_footprint_gap_mm=gap,same_parent_contour=same,in_original_protected_DAG=(a,b) in raw,
            disposition='retain' if keep else 'release_global_only',
            reason='Existing protected/parent/spatial relationship' if keep else 'Artificial consecutive-A execution barrier only; distinct source contours, disjoint footprints beyond0.5mm guard'))
        if keep:retained.add((a,b))
    return sorted(retained),sorted(raw|set(chain)),dict(original_protected_edges=len(raw),removed_original_protected_edges=0,
        global_A_chain_edges=len(chain),released_global_only_edges=sum(r['disposition']=='release_global_only' for r in review),
        chain_edges=review,evidence_limit='Authored widths and0.5mm guard, not measured wet-brush footprints. All original guard/occlusion/owner/parent edges retained. Release changes inter-contour time only; drying effects unmeasured.')

def diagnostics(rows,fs,ids,cfg):
    A=sorted(i for i in ids if fs[i]['family']=='A');lines=[LineString(rows[i]['xy_mm']) for i in A];tree=STRtree(lines)
    result=[]
    for k,i in enumerate(A):
        f=fs[i];line=lines[k]
        hits=[int(j) for j in tree.query(line,predicate='dwithin',distance=cfg['neighbor_search_mm']) if int(j)!=k
              and fs[A[int(j)]]['parent_contour']!=f['parent_contour'] and fs[A[int(j)]]['depth_band']==f['depth_band']
              and abs(fs[A[int(j)]]['depth_m']-f['depth_m'])/max(f['depth_m'],1)<=cfg['maximum_relative_depth_difference']]
        samples=[line.interpolate(x,normalized=True) for x in np.linspace(.1,.9,9)]
        spacing=[min((p.distance(lines[j]) for j in hits),default=999.) for p in samples]
        median=float(np.median(spacing));width=max(rows[i].get('width_profile_mm',[rows[i]['width_mm']]))
        result.append(dict(index=i,source_id=f['source_id'],depth_band=f['depth_band'],depth_m=f['depth_m'],length_mm=f['length_mm'],ink=f['ink'],
            center_xy=list(map(float,np.asarray(rows[i]['xy_mm']).mean(axis=0))),width_max_mm=width,
            neighbor_sources=[A[j] for j in hits],neighbor_count=len(hits),spacing_samples_mm=spacing,median_spacing_mm=median,
            gap_sensitivity_fraction={str(w):float(np.mean(np.asarray(spacing)<w)) for w in cfg['width_sensitivity_mm']},
            measured_physical_width_available=False))
    thresholds={}
    for band in ('near','middle'):
        values=[r['median_spacing_mm'] for r in result if r['depth_band']==band and r['median_spacing_mm']<999]
        thresholds[band]=min(cfg['maximum_median_spacing_mm'],float(np.quantile(values,cfg['crowded_band_quantile']))) if values else 0
    return result,thresholds

def choose(diag,main,desc,thresholds,cfg):
    candidates=[]
    for d in diag:
        reasons=[]
        if d['index'] not in main:reasons.append('Not PR41 main')
        if d['depth_band']=='far':reasons.append('Far terrain preserved')
        if d['ink']!='LIGHT_INK':reasons.append('Preserve dark tonal concentration')
        if not cfg['minimum_A_length_mm']<=d['length_mm']<=cfg['maximum_A_length_mm']:reasons.append('Preserve long mass-defining stroke or fragile tiny endpoint')
        if d['neighbor_count']<2 or d['median_spacing_mm']>thresholds.get(d['depth_band'],0):reasons.append('Not a local crowded subordinate contour')
        if desc.get(d['index'],set())&main:reasons.append('Original protected main successor prevents final fine stage')
        d['reasons']=reasons;d['decision']='reject' if reasons else 'eligible'
        if not reasons:candidates.append(d)
    chosen=[];groups=[]
    for d in sorted(candidates,key=lambda r:(r['median_spacing_mm']/max(thresholds[r['depth_band']],.01),r['length_mm'],r['index'])):
        c=np.array(d['center_xy']);local=next((g for g in groups if g['band']==d['depth_band'] and np.linalg.norm(c-g['center'])<70),None)
        if local is None:
            if len(groups)>=cfg['maximum_local_groups']:d['decision']='reject';d['reasons']=['Local group cap, avoid distributed thinning'];continue
            local=dict(center=c,band=d['depth_band'],members=[]);groups.append(local)
        if len(chosen)>=cfg['maximum_A_reassignments'] or len(local['members'])>=cfg['maximum_per_local_group']:
            d['decision']='reject';d['reasons']=['Subordinate local/global count cap'];continue
        local['members'].append(d['index']);chosen.append(d['index']);d['decision']='select';d['local_group']=groups.index(local) if False else next(k for k,g in enumerate(groups) if g is local)
    return chosen,[dict(center_xy=list(map(float,g['center'])),depth_band=g['band'],members=g['members']) for g in groups]

def stage_lower_bound(ids,edges,fine):
    graph=defaultdict(list);degree=dict.fromkeys(ids,0);stage={};cause={}
    for a,b in v.project_edges(edges,set(ids)):graph[a].append(b);degree[b]+=1
    ready=[i for i,d in degree.items() if not d];heapq.heapify(ready);seen=[]
    while ready:
        i=heapq.heappop(ready);seen.append(i);required=stage.get(i,0);parity=int(i in fine)
        if required%2!=parity:required+=1
        stage[i]=required
        for j in graph[i]:
            if stage.get(j,0)<required:stage[j]=required;cause[j]=i
            degree[j]-=1
            if not degree[j]:heapq.heappush(ready,j)
    s.require(len(seen)==len(ids),'Stage DAG cycle')
    terminal=max(ids,key=lambda i:stage[i]);witness=[];cursor=terminal
    while cursor in cause:witness.append(cursor);cursor=cause[cursor]
    witness.append(cursor);witness.reverse()
    return dict(minimum_alternating_programs=max(stage.values())+1,three_stage_feasible=max(stage.values())<3,
                stage_assignment={str(i):k for i,k in stage.items()},witness_indices=witness,
                reason='Exact earliest feasible alternating brush-layer levels on retained DAG; starts main. This bound is achievable by level order.')

def pair(out,label,groups,fragments,small,fine_profile,cfg,isfine,distance=None,write=True):
    policy=n.frozen('policy.json');policy['distance_limit_mm']=(distance or cfg['fine_reload_mm']) if isfine else cfg['small_reload_mm']
    limit=cfg['fine_contacts'] if isfine else cfg['small_contacts'];commands,mat=n.build(groups,fragments,small,policy,limit)
    profile=fine_profile if isfine else small
    if isfine:commands=v.fine_transform(commands,profile)
    n.audit_ir(commands,mat,groups,fragments,profile)
    s.require(mat['maximum_contacts_before_reload']<=limit,'Contact cap exceeded')
    stats=n.summary(commands,mat,profile);stats.update(station_operation_visits=len(mat['station_operations']),station_operation_visits_by_location=dict(Counter(x['station'] for x in mat['station_operations'])),terminal_PURGE_contacts=2,distance_limit_mm=policy['distance_limit_mm'],contact_limit=limit,
        same_concentration_reloads=mat['same_concentration_reloads'],drawing_mm=sum(x['drawn_mm'] for x in mat['gestures']))
    if not write:return stats
    reports={}
    for air,cmd in [(False,commands),(True,s.air_projection(commands,profile))]:
        name=f'SPRING_P2_{"AIR" if air else "INK"}_{label}_REVIEW';reports[name]=v.write(out,name,cmd,profile,groups,fragments,air,isfine)
    s.save(out/(label+'.execution.json.gz'),dict(groups=groups));s.save(out/(label+'.reload.json.gz'),mat)
    s.save(out/(label+'.stations.json.gz'),n.station_records(commands,profile));s.save(out/(label+'.IR.json.gz'),[asdict(c) for c in commands])
    return reports,stats

def render_sensitivity(path,rows,main,fine,bounds):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    x0,y0,x1,y1=bounds;scale=5;lines=[];widths=[];colors=[]
    for role,groups in [('main',main),('fine',fine)]:
        for group in groups:
            for e in group:
                r=rows[e['source']];xy=np.asarray(r['xy_mm'])
                if xy[:,0].max()<x0 or xy[:,0].min()>x1 or xy[:,1].max()<y0 or xy[:,1].min()>y1:continue
                lines.append(xy)
                width=(2. if role=='main' else .5) if r['source_family']=='A' else float(np.median(r.get('width_profile_mm',[r['width_mm']])))
                widths.append(width*scale*72/150)
                colors.append((.14,.19,.21,.42) if e['ink']=='LIGHT_INK' else (0,0,0,.86))
    fig=plt.figure(figsize=((x1-x0)*scale/150,(y1-y0)*scale/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    ax.add_collection(LineCollection(lines,linewidths=widths,colors=colors,capstyle='round',joinstyle='round'))
    fig.savefig(path,dpi=150,facecolor='white');plt.close(fig)

def visuals(out,rows,fs,variants,selected,groups,diag,cfg):
    def flat(g):return [e for part in g for e in part]
    paths=[]
    for name,(main,fine) in variants.items():
        proxy=deepcopy(rows)
        for e in flat(fine):
            r=proxy[e['source']];r['width_mm']*=cfg['fine_preview_factor_unmeasured']
            if 'width_profile_mm' in r:r['width_profile_mm']=[w*cfg['fine_preview_factor_unmeasured'] for w in r['width_profile_mm']]
        render(out/(name+'_full.png'),proxy,fs,flat(main)+flat(fine),(300,0,600,900),2);paths.append(out/(name+'_full.png'))
        t.svg_preview(out/(name+'_roles.svg'),rows,main,fine,selected if name!='A' else [],dict(fine_preview_width_factor_unmeasured=cfg['fine_preview_factor_unmeasured']))
    sheet(out,paths,['A PR41','B selective A / 2 stages','C extra near A / 3 stages'],'full_comparison.png',(500,1550))
    bounds=[]
    for k,g in enumerate(groups):
        xy=np.concatenate([np.array(rows[i]['xy_mm']) for i in g['members']]);lo=xy.min(axis=0)-10;hi=xy.max(axis=0)+10
        x=float(np.clip((lo[0]+hi[0])/2-65,300,470));y=float(np.clip((lo[1]+hi[1])/2-65,0,770));roi=(x,y,x+130,y+130);bounds.append(roi)
        crops=[]
        for name,(main,fine) in variants.items():
            proxy=deepcopy(rows)
            for e in flat(fine):
                r=proxy[e['source']];r['width_mm']*=.45
                if 'width_profile_mm' in r:r['width_profile_mm']=[w*.45 for w in r['width_profile_mm']]
            file=out/f'crop{k}_{name}.png';render(file,proxy,fs,flat(main)+flat(fine),roi,5);crops.append(file)
        sheet(out,crops,['A PR41','B selective A','C extra near A / extra exchange'],f'crop{k}_comparison.png',(650,760))
        sensitivity=[]
        for name,(main,fine) in variants.items():
            proxy=deepcopy(rows)
            for role,parts in [('main',main),('fine',fine)]:
                for e in flat(parts):
                    i=e['source']
                    if fs[i]['family']=='A':
                        width=2.0 if role=='main' else .5
                        proxy[i]['width_mm']=width;proxy[i]['width_profile_mm']=[width]*len(proxy[i]['xy_mm'])
            file=out/f'crop{k}_{name}_2mm_UNMEASURED.png';render_sensitivity(file,rows,main,fine,roi);sensitivity.append(file)
        filename=f'crop{k}_2mm_sensitivity_comparison.png'
        sheet(out,sensitivity,['A PR41','B selective A','C extra near A'],filename,(650,760))
        from PIL import Image,ImageDraw,ImageFont
        with Image.open(out/filename) as im:
            im=im.convert('RGB');d=ImageDraw.Draw(im);d.rectangle((0,0,im.width,44),fill='#f4f4ed')
            d.text((15,10),'UNMEASURED A-width sensitivity: main2mm / fine0.5mm. NOT a calibrated prediction.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19),fill='#17382e');im.save(out/filename)

    s.save(out/'crop_bounds.json',bounds)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    for band,color in [('near','#a57f42'),('middle','#427e83')]:
        vals=[d['median_spacing_mm'] for d in diag if d['depth_band']==band and d['median_spacing_mm']<20]
        axes[0].hist(vals,bins=np.linspace(0,12,25),histtype='step',label=band,color=color)
    chosen=[d for d in diag if d['index'] in selected];axes[1].bar(range(len(chosen)),[d['median_spacing_mm'] for d in chosen],color='#427e83')
    axes[0].set(xlabel='Median nearest contour spacing (mm)',ylabel='A sources',title='Geometry unchanged in A/B/C');axes[0].legend()
    axes[1].set(xlabel='Selected source (see source IDs)',ylabel='Median local spacing (mm)',title='Measured XY spacing; brush width UNMEASURED')
    fig.savefig(out/'spacing_diagnostics.png',dpi=150);plt.close(fig)

def generate(output,context):
    out=Path(output);s.require(not out.exists(),'Fresh directory required');out.mkdir(parents=True)
    cfg=s.read(POLICY);_,rows,fragments=s.load_inputs(s.recover_context(Path(context)));fs=n.frozen('source_features.json.gz')
    records=frozen('source_roles.json.gz');rs={r['index']:r for r in records};ids=set(rs)
    base_main=frozen('TERRAIN_MAIN.execution.json.gz')['groups'];base_fine=frozen('VEGETATION_TERRAIN_FINE.execution.json.gz')['groups']
    mainids={e['source'] for g in base_main for e in g};fineids={e['source'] for g in base_fine for e in g};active=mainids|fineids
    original=[e['source'] for e in n.frozen('SINGLE_PASS.execution_manifest.json.gz')['events'] if e['source'] in ids];rank={i:k for k,i in enumerate(original)}
    retained,strict,dependencies=dependency_review(rows,fs,ids,original)
    desc=t.graph_descendants(retained,active);diag,threshold=diagnostics(rows,fs,ids,cfg)
    selected,localgroups=choose(diag,mainids,desc,threshold,cfg);s.require(selected,'No defensible selective A reassignment')
    fullrecords=[{} for _ in fragments]
    for r in records:fullrecords[r['index']]=r
    newmain=[[e for e in g if e['source'] not in selected] for g in base_main];newmain=[g for g in newmain if g]
    fine,ordering=v.schedule(sorted(fineids|set(selected)),fullrecords,retained,rank,10)
    sequence=[e['source'] for g in newmain+fine for e in g];pos={i:k for k,i in enumerate(sequence)}
    protected=v.project_edges(retained,active);s.require(all(pos[a]<pos[b] for a,b in protected),'Essential precedence changed')
    s.require(set(sequence)==active and len(sequence)==len(active)==1209,'Duplicated/lost ink source')
    strict_case=stage_lower_bound(sorted(active),strict,fineids|set(selected))
    near_candidates=[d for d in diag if d['depth_band']=='near' and d['reasons']==['Original protected main successor prevents final fine stage']]
    near_choice=min(near_candidates,key=lambda d:(d['median_spacing_mm'],d['index']))['index'] if near_candidates else None
    Cfine=fineids|set(selected)|({near_choice} if near_choice is not None else set())
    C=stage_lower_bound(sorted(active),retained,Cfine)
    C['additional_near_A_index']=near_choice
    C['additional_near_A_source_id']=rs[near_choice]['source_id'] if near_choice is not None else None
    C['strict_global_chain_counterfactual_programs']=strict_case['minimum_alternating_programs']
    s.save(out/'strict_global_chain_counterfactual.json',strict_case)
    s.require(stage_lower_bound(sorted(active),retained,fineids|set(selected))['minimum_alternating_programs']==2,'B not two-stage feasible')
    small=s.Profile.from_dict(frozen('profile.small.json'));fineprofile=s.Profile.from_dict(frozen('profile.fine.PROVISIONAL.json'))
    fineprofile.data['material']['ink_reload_mm']=cfg['fine_reload_mm']
    s.save(out/'policy.json',cfg);s.save(out/'profile.small.json',small.data);s.save(out/'profile.fine.PROVISIONAL.json',fineprofile.data)
    old_review=frozen('terrain_selection_review.json');oldA=[x for x in old_review if x['family']=='A']
    s.save(out/'historical_A_rejection_audit.json',dict(PR41_reviewed_A=len(oldA),reasons=dict(Counter(x['reason'] for x in oldA)),code_evidence=['spring_fine_terrain.generate adds global consecutive-A chain','spring_fine_terrain.choose also contains unconditional A-family retention after the descendant check'],new_policy='Keep original protected DAG plus spatial/parent A barriers; replace blanket A retention with density/role evidence.'))
    s.save(out/'dependency_analysis.json.gz',dependencies);s.save(out/'retained_edges.json.gz',retained)
    s.save(out/'A_candidates.json.gz',diag);s.save(out/'local_groups.json',localgroups);s.save(out/'C_strict_chain_feasibility.json',C)
    jobs={};timings={}
    for label,g,isfine in [('A_PR41_MAIN',base_main,False),('A_PR41_FINE',base_fine,True),('B_SELECTIVE_A_MAIN',newmain,False),('B_SELECTIVE_A_FINE',fine,True)]:
        j,st=pair(out,label,g,fragments,small,fineprofile,cfg,isfine);jobs.update(j);timings[label]=st
        print(label,len([e for x in g for e in x]),st['total_loads'],round(st['modeled_seconds']/60,3),flush=True)
    sensitivity={str(mm):pair(out,'sensitivity',fine,fragments,small,fineprofile,cfg,True,mm,False) for mm in cfg['fine_sensitivity_mm']}
    # Model the exact stricter-chain stage count only when a bounded review remains practical.
    Ctime=[];Cgroups=[]
    if C['minimum_alternating_programs']<=12:
        for stage in range(C['minimum_alternating_programs']):
            stageids=[i for i in active if C['stage_assignment'][str(i)]==stage]
            group,_=v.schedule(stageids,fullrecords,retained,rank,10);Cgroups.append(group)
            label=f'C_STAGE{stage+1}_'+('FINE' if stage%2 else 'MAIN')
            jj,st=pair(out,label,group,fragments,small,fineprofile,cfg,stage%2==1)
            jobs.update(jj);Ctime.append(st)
    else:C['runtime_not_materialized_reason']='More than12 alternating programs; lower-bound complexity alone rejects limited-three-stage workflow'
    s.save(out/'C_strict_chain_feasibility.json',C);s.save(out/'runtime.json',dict(stages=timings,fine_distance_sensitivity=sensitivity,C_stage_models=Ctime,
        C_minimum_manual_exchanges=C['minimum_alternating_programs']-1,manual_exchange_seconds_assumed=cfg['manual_exchange_seconds_assumed'],
        historical_PR41=frozen('verification.json')['timings']))
    for r in records:
        r['PR41_review_role']=r['review_role']
        if r['index'] in selected:r['review_role']='fine_A_terrain';r['reason_A_hierarchy']='Local crowded light subordinate A; no protected main successor after releasing only evidenced global barrier'
    
    for r in records:r['C_review_role']='fine_A_terrain' if r['index']==near_choice else r['review_role']
    s.save(out/'source_roles.json.gz',records);s.save(out/'selected_source_ids.json',[rs[i]['source_id'] for i in selected])
    s.save(out/'color_handoff.json.gz',dict(records=[r for r in records if r['review_role']=='color'],source_count=642,no_color_Gcode=True,
        ink_A_reassignments_not_color=selected,next_step='Reviewed ink plus PR40 seasonal framework; no palette finalized'))
    Cmain=[g for k,part in enumerate(Cgroups) if k%2==0 for g in part];Cdetail=[g for k,part in enumerate(Cgroups) if k%2==1 for g in part]
    Cseq=[e['source'] for part in Cgroups for g in part for e in g];cpos={i:k for k,i in enumerate(Cseq)}
    s.require(set(Cseq)==active and len(Cseq)==len(active) and all(cpos[a]<cpos[b] for a,b in protected),'C sequence violates retained order')
    near_groups=localgroups+([dict(center_xy=list(map(float,np.asarray(rows[near_choice]['xy_mm']).mean(axis=0))),depth_band='near',members=[near_choice])] if near_choice is not None else [])
    visuals(out,rows,fs,{'A':(base_main,base_fine),'B':(newmain,fine),'C':(Cmain,Cdetail)},selected,near_groups,diag,cfg)
    report=dict(baseline=PIN,jobs=jobs,total_ink_sources=1209,color_sources=642,original_P2_sources=1851,
        selected_A_count=len(selected),selected_A_indices=selected,selected_A_by_depth=dict(Counter(rs[i]['depth_band'] for i in selected)),
        selection_decisions=dict(Counter(d['decision'] for d in diag)),rejection_reasons=dict(Counter(reason for d in diag if d['decision']=='reject' for reason in d['reasons'])),
        spacing_thresholds_mm=threshold,measured_physical_width_mm=None,original_protected_edges_removed=0,
        original_A_geometry_density_pressure_and_ink_unchanged=True,protected_projected_edges=len(protected),violations=0,
        B_main_sources=len(mainids)-len(selected),B_fine_sources=len(fineids)+len(selected),B_programs=2,C_programs=C['minimum_alternating_programs'],C_near_A_index=near_choice,strict_global_chain_programs=strict_case['minimum_alternating_programs'],
        C_three_stage_feasible=C['three_stage_feasible'],fine_reload=dict(mm=450,contacts=10),small_reload=dict(mm=800,contacts=20),
        machine_authorized=False)
    s.save(out/'verification.json',report)
    lines=['# A-layer hierarchy / modeled timing','','All comparisons use small800/20 and fine450/10. Physical width, retention and fine Z uncalibrated.','','| Stage | Sources | Loads | Same-ink reloads | Switch washes | Station visits | Minutes |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,st in timings.items():lines.append(f"| {name} | {st['actual_paper_engagements']} | {st['total_loads']} | {st['same_concentration_reloads']} | {st['concentration_switches']} | {st['station_operation_visits']} | {st['modeled_seconds']/60:.3f} |")
    lines+=['',f"Near-A candidate C needs {C['minimum_alternating_programs']} alternating programs; three-stage feasible: {C['three_stage_feasible']}. C adds one near A transfer and retains essential ordering. The old global-chain counterfactual is recorded separately. Full C stage models (if <=12 stages) and400/500mm sensitivities are in runtime.json."]
    (out/'RUNTIME.md').write_text('\n'.join(lines)+'\n')
    s.save(out/'MANIFEST_SHA256.json',{f.name:s.sha(f) for f in sorted(out.iterdir()) if f.name!='MANIFEST_SHA256.json'})
    return audit(out,context)

def audit(output,context,independent=None):
    out=Path(output);_,rows,fragments=s.load_inputs(Path(context));report=s.read(out/'verification.json');records=s.read(out/'source_roles.json.gz')
    for r in records:s.require(r['source_record_sha256']==s.digest(rows[r['index']]) and r['canonical_stroke_sha256']==s.digest(asdict(fragments[r['index']].stroke)),'Source/width/pressure changed')
    sets={};checks={}
    labels=['A_PR41_MAIN','A_PR41_FINE','B_SELECTIVE_A_MAIN','B_SELECTIVE_A_FINE']+sorted({name[len('SPRING_P2_INK_'):-len('_REVIEW')] for name in report['jobs'] if name.startswith('SPRING_P2_INK_C_STAGE')})
    for label in labels:
        fine=label.endswith('FINE');p=s.Profile.load(out/('profile.fine.PROVISIONAL.json' if fine else 'profile.small.json'))
        groups=s.read(out/(label+'.execution.json.gz'))['groups'];sets[label]=[e['source'] for g in groups for e in g]
        cmd=[s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None}) for c in s.read(out/(label+'.IR.json.gz'))]
        mat=s.read(out/(label+'.reload.json.gz'));n.audit_ir(cmd,mat,groups,fragments,p)
        s.require(mat['maximum_contacts_before_reload']<=(10 if fine else 20),'Contact limit')
        s.require(all(x['distance_limit_mm']==(450 if fine else 800) and x['contact_limit']==(10 if fine else 20) for x in mat['loads']),'Reload policy mismatch')
        for air,commands in [(False,cmd),(True,s.air_projection(cmd,p))]:
            name=f'SPRING_P2_{"AIR" if air else "INK"}_{label}_REVIEW';raw=(out/(name+'.gcode')).read_bytes()
            s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes())==raw,'Gzip bytes')
            checks[name]=v.verify(raw.decode(),commands,p,groups,fragments,air,fine)
    A=sets['A_PR41_MAIN']+sets['A_PR41_FINE'];B=sets['B_SELECTIVE_A_MAIN']+sets['B_SELECTIVE_A_FINE']
    s.require(set(A)==set(B) and len(set(A))==len(A)==len(B)==1209,'Lost/duplicate source')
    pos={i:k for k,i in enumerate(B)};edges=s.read(out/'retained_edges.json.gz')
    C=[i for label in labels if label.startswith('C_STAGE') for i in sets[label]];cpos={i:k for k,i in enumerate(C)}
    s.require(set(C)==set(A) and len(C)==1209 and all(cpos[a]<cpos[b] for a,b in v.project_edges(edges,set(C))),'C stage source/order mismatch')
    s.require(all(pos[a]<pos[b] for a,b in v.project_edges(edges,set(B))),'Delivered protected order')
    s.require(sets['B_SELECTIVE_A_MAIN']==[i for i in sets['A_PR41_MAIN'] if i not in report['selected_A_indices']],'Main subsequence')
    manifest=s.read(out/'MANIFEST_SHA256.json');s.require(all(s.sha(out/name)==sha for name,sha in manifest.items()),'SHA mismatch')
    equal={}
    if independent:
        for name in manifest:equal[name]=(out/name).read_bytes()==(Path(independent)/name).read_bytes()
        s.require(all(equal.values()),'Nondeterministic output')
    result=dict(programs=checks,source_set_and_width_XY_pressure_integrity=True,all_original_protected_edges_retained=True,
        fine450mm_10contacts_verified=True,small800mm_20contacts_verified=True,independent_byte_equality=equal,machine_authorized=False)
    s.save(out/'delivered_audit.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--output',required=True);p.add_argument('--context',required=True);p.add_argument('--verify',action='store_true');p.add_argument('--independent');a=p.parse_args()
    r=audit(a.output,a.context,a.independent) if a.verify else generate(a.output,a.context)
    print(json.dumps(r))
