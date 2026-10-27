"""Execution-only source selection and dependency-safe dual-brush ink review."""
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict,replace
from collections import Counter,defaultdict
import argparse,gzip,json,hashlib,base64
import numpy as np
from scipy.spatial import cKDTree
from . import spring_physical_ink as s
from . import spring_panels_contact20 as n
from .spring_physical_ink_review import render,sheet

POLICY=s.ROOT/'config/spring_ink_v02/policy.json'
PIN='c2464d65e2b2203f2e4b5912377eb33097987dbc'

def classify(fs,rows,cfg):
    centers=np.array([np.asarray(r['xy_mm']).mean(axis=0) for r in rows]);tree=cKDTree(centers)
    density=[len(tree.query_ball_point(x,cfg['density_radius_mm']))-1 for x in centers]
    out=[]
    for i,f in enumerate(fs):
        family,role,band,L=f['family'],f['grammar'],f['depth_band'],f['length_mm']
        decision='main';reason='Preserved terrain or mass structure'
        foliage=role in ('foliage-field','twig') or family=='RSU'
        if foliage:
            if L<cfg['redundant_micro_mm'] and density[i]>=cfg['dense_neighbors']:
                decision='omit';reason='Dense sub2mm nonstructural repeated contact proxy'
            elif (role=='foliage-field' and (L<cfg['foliage_defer_mm'] or band=='far')) or (family=='RSU' and band=='far' and L<cfg['far_growth_defer_mm']):
                decision='color';reason='Nonstructural foliage/atmosphere better deferred to pigment'
            elif role=='twig' or (family=='RSU' and band!='far' and L>=3):
                decision='fine';reason='Selective identifiable growth structure'
        elif family=='tree' and role in ('branch-contour','trunk-contour') and cfg['fine_min_mm']<=L<=cfg['fine_max_mm']:
            decision='fine';reason='Necessary subordinate trunk/branch, fine-brush candidate'
        elif family=='rock' and role in ('small-structure','secondary-fracture','partial-spall-seam','feature-terminal') and L<10:
            decision='fine';reason='Subordinate structural rock detail'
        elif family=='Soil' and L<3 and density[i]>=cfg['dense_neighbors']:
            decision='omit';reason='Redundant dense ground contact proxy'
        out.append(dict(index=i,source_id=f['source_id'],family=family,role=role,depth_band=band,depth_m=f['depth_m'],
            owner=f['owner'],length_mm=L,local_neighbors_within2mm=density[i],classification=decision,reason=reason,
            original_ink=f['ink'],ink=f['ink'],source_record_sha256=s.digest(rows[i]),
            xy_mm=rows[i]['xy_mm'],width_reference=rows[i].get('width_profile_mm',rows[i]['width_mm'])))
    # Preserve all A allocation; soften nonstructural distant growth and minor B.
    for r in out:
        if r['family'] in ('tree','RSU') and (r['depth_band']=='far' or r['local_neighbors_within2mm']>=cfg['dense_neighbors']):r['ink']='LIGHT_INK'
        if r['family']=='rock' and r['depth_band']!='near':r['ink']='LIGHT_INK'
        if r['family']=='B' and r['depth_band']=='far' and r['length_mm']<15:r['ink']='LIGHT_INK'
    near=[r for r in out if r['family']=='rock' and r['depth_band']=='near']
    priority={'ink-contour':5,'primary-joint':4,'feature-shoulder':3,'bedding-band':2}
    dark={r['index'] for r in sorted(near,key=lambda r:(-priority.get(r['role'],0),-r['length_mm'],r['index']))[:round(len(near)*cfg['near_rock_dark_fraction'])]}
    for r in near:r['ink']='DARK_INK' if r['index'] in dark else 'LIGHT_INK'
    return out

def project_edges(edges,selected):
    graph=defaultdict(list)
    for a,b in edges:graph[a].append(b)
    result=set()
    for a in selected:
        todo=list(graph[a]);seen=set()
        while todo:
            b=todo.pop()
            if b in seen:continue
            seen.add(b)
            if b in selected:result.add((a,b))
            else:todo.extend(graph[b])
    return sorted(result)

def resolve_fine(records,edges):
    """Keep a genuine two-stage plan by reporting blocked fine candidates explicitly."""
    selected={r['index'] for r in records if r['classification'] in ('main','fine')}
    graph=project_edges(edges,selected);blocked=[]
    while True:
        bad={a for a,b in graph if records[a]['classification']=='fine' and records[b]['classification']=='main'}
        if not bad:break
        for a in sorted(bad):
            r=records[a];blocked.append(a)
            if r['role']=='trunk-contour':r['classification']='main';r['reason']+='; retained main to protect a later structural successor'
            else:r['classification']='color';r['reason']+='; deferred because main-after-fine precedence prevents a two-stage manual workflow'
        selected={r['index'] for r in records if r['classification'] in ('main','fine')};graph=project_edges(edges,selected)
    return blocked

def schedule(ids,records,edges,rank,soft=10):
    selected=set(ids);edges=project_edges(edges,selected);adj=defaultdict(list);degree=dict.fromkeys(ids,0)
    for a,b in edges:adj[a].append(b);degree[b]+=1
    ready={i for i,d in degree.items() if not d};order=[];ink='LIGHT_INK';batch=0;switch=[]
    while ready:
        same=[i for i in ready if records[i]['ink']==ink]
        pool=same or list(ready)
        i=min(pool,key=lambda j:rank[j]);new=records[i]['ink']
        if new!=ink:
            if order:switch.append(dict(after=order[-1],contacts=batch,below_soft_target=batch<soft,reason='No dependency-ready source of current concentration'))
            ink=new;batch=0
        ready.remove(i);order.append(i);batch+=1
        for j in adj[i]:
            degree[j]-=1
            if not degree[j]:ready.add(j)
    s.require(len(order)==len(ids),'Cyclic schedule')
    position={i:k for k,i in enumerate(order)};s.require(all(position[a]<position[b] for a,b in edges),'Protected order violated')
    return [[dict(source=i,pass_index=0,ink=records[i]['ink'],id=f'{i}:pass0')] for i in order],dict(edges=len(edges),violations=0,batches_ended=switch,final_batch_contacts=batch)

def fine_profile(p,cfg):
    d=deepcopy(p.data);v=cfg['fine_provisional'];d['profile_id']='FINE-BRUSH-EXPLICITLY-PROVISIONAL-REVIEW'
    d['brush_profiles']['ink'].update(brush_id='fine-uncalibrated',brush_type='fine_provisional',paper_first_touch_z_mm=v['first_touch_z'],knots=[[x,-y] for x,y in v['compression_knots']],observations=[],status='unverified')
    d['motion'].update(paper_hover_mm=v['paper_hover_z'],paper_approach_mm=v['paper_approach_z'])
    return s.Profile.from_dict(d)

def fine_transform(commands,p):
    b=s.RuntimeBuilder(p)
    for c in commands:
        if c.kind!='move':
            if c.kind=='pause':c=replace(c,message='FINE BRUSH UNCALIBRATED: provisional touch12 and max1mm compression, station contacts unverified. Manually condition and verify profile before any contact; M0 is not a safety interlock.')
            b.commands.append(c);continue
        xyz=c.xyz
        if c.artistic_pressure is not None:xyz=(*xyz[:2],p.brush_for('ink','INK').work_z_for(c.artistic_pressure))
        elif c.action in ('initial_contact','release'):xyz=(*xyz[:2],12)
        elif c.action in ('approach','paper_release_clearance'):xyz=(*xyz[:2],17)
        elif c.action in ('paper_hover','retract') or (c.action=='travel' and xyz[2]==20):xyz=(*xyz[:2],22)
        b.time_context=c.time_category
        b.move(xyz,c.feed_mm_min,c.action,c.travel_state,source_id=c.source_id,fragment_id=c.fragment_id,
            source_vertex=c.source_vertex,artistic_pressure=c.artistic_pressure,travel_phase=c.travel_phase)
    return b.commands

def verify(text,commands,p,groups,fragments,air=False,fine=False):
    lines=[l for l in text.splitlines() if l and not l.startswith(';')]
    s.require(lines[0]=='G21 G90 G94 G54' and lines[-1]=='M2','Dialect/end')
    expected=[c for c in commands if c.kind!='marker'];s.require(len(lines)==len(expected)+2,'Command count')
    pos=tuple(p.data['machine']['start_work_xyz']);active=None;values=defaultdict(list);seen=[];cursor=iter(lines[1:-1])
    for c in commands:
        if c.action=='source_begin':s.require(active is None,'Nested source');active=c.message;seen.append(active)
        if c.action=='source_complete':s.require(active==c.message,'Unclosed source');active=None
        if active:s.require(c.time_category not in ('station_handling','station_transfer'),'Station inside source')
        if c.kind=='marker':continue
        line=next(cursor)
        if c.kind=='move':
            match=s._MOVE.fullmatch(line);s.require(match is not None,'Motion dialect');x,y,z,f=map(float,match.groups())
            s.require(all(abs(a-b)<5.1e-10 for a,b in zip((x,y,z,f),(*c.xyz,c.feed_mm_min))),'Numeric IR mismatch')
            s.check_move(pos,(x,y,z),f,c.action,p,'air' if air else 'paint',exact_benchmark_draw=False)
            if air:s.require(z==35,'AIR contact')
            elif c.action in ('initial_contact','release','approach','paper_release_clearance','paper_hover','retract'):
                touch,hover,approach=(12,22,17) if fine else (10,20,15)
                expected_z=touch if c.action in ('initial_contact','release') else approach if c.action in ('approach','paper_release_clearance') else hover
                s.require(z==expected_z,'Paper height mismatch')
            if c.time_category=='station_transfer' and pos[:2]!=(x,y):s.require(pos[2]==z==35,'Station transfer below35')
            if c.artistic_pressure is not None:
                s.require(active is not None,'Pressure outside source');values[active].append((c.source_vertex,c.artistic_pressure,(x,y)))
                if not air:s.require(abs(z-p.brush_for('ink','INK').work_z_for(c.artistic_pressure))<5.1e-10,'Pressure mapping changed')
            pos=(x,y,z)
        elif c.kind=='dwell':
            m=s._DWELL.fullmatch(line);s.require(m and abs(float(m.group(1))-c.seconds)<5.1e-10,'Dwell mismatch')
        elif c.kind=='pause':s.require(line=='M0','Gate missing')
        else:raise ValueError('Unsupported command')
    events=[e for g in groups for e in g];s.require(seen==[e['id'] for e in events],'Source order')
    for e in events:
        f=fragments[e['source']];v=values[e['id']];s.require(len(v)==len(f.stroke.points),'Vertex count')
        for k,(index,pressure,xy) in enumerate(v):s.require(index==k and pressure==f.stroke.points[k].pressure and all(abs(a-b)<5.1e-10 for a,b in zip(xy,f.work_xy[k])),'Canonical lineage changed')
    s.require(pos==(800,800,35),'Terminal park');s.require(lines.count('M0')==(0 if air else 1),'Unexpected repeated pauses')
    return dict(sources=len(events),pressure_samples=sum(map(len,values.values())),all_XY_pressure_vertices_verified=True,
        AIR_Z35=air,all_numeric_IR_values_verified=True,machine_authorized=False,fine_profile_provisional=fine)

def write(out,name,commands,p,groups,fragments,air=False,fine=False):
    text=s.BANNER+'; INITIAL CONDITIONING REQUIRED / NUMERICAL REVIEW ONLY\n'+s._serialize(commands,p,s.PLAN_SHA,name,'offline_review')
    check=verify(text,commands,p,groups,fragments,air,fine)
    (out/(name+'.gcode')).write_text(text);(out/(name+'.gcode.gz')).write_bytes(gzip.compress(text.encode(),mtime=0))
    s.save(out/(name+'.readback.json'),check)
    return dict(**check,sha256=s.sha(out/(name+'.gcode')),runtime=s.runtime(commands,p))

def generate(output,context,panel='P2'):
    out=Path(output);s.require(not out.exists(),'Fresh directory required');out.mkdir(parents=True)
    cfg=s.read(POLICY);context=s.recover_context(Path(context));plan,rows,fragments=s.load_inputs(context)
    fs=n.frozen('source_features.json.gz');owners,_=n.partition(fragments,rows)
    original=n.frozen('SINGLE_PASS.execution_manifest.json.gz');base=n.panel_groups(original['groups'],owners,panel)
    ids=[e['source'] for g in base for e in g];rank={i:k for k,i in enumerate(ids)}
    edges=n.frozen('protected_source_dependencies.json.gz')['edges']
    # Preserve the accepted A execution rhythm as a source-order barrier.
    A=[i for i in ids if fs[i]['family']=='A'];edges=sorted(set(map(tuple,edges))|set(zip(A,A[1:])))
    records=classify(fs,rows,cfg);blocked=resolve_fine(records,edges)
    selected={i for i in ids if records[i]['classification'] in ('main','fine')}
    graphs=project_edges(edges,selected)
    s.require(not any(records[a]['classification']=='fine' and records[b]['classification']=='main' for a,b in graphs),'Invalid two-stage brush order')
    p=s.Profile.from_dict(n.frozen('profile.small_baegunmo.json'));fine=fine_profile(p,cfg);policy=n.frozen('policy.json');policy['contact_limit']=20
    s.save(out/'policy.json',cfg);s.save(out/'profile.small.json',p.data);s.save(out/'profile.fine.PROVISIONAL.json',fine.data)
    report=dict(baseline=PIN,panel=panel,jobs={},selection_counts=dict(Counter(records[i]['classification'] for i in ids)),
        fine_candidates_blocked_by_main_successors=[i for i in blocked if i in ids],original_sources=len(ids),
        original_pressure_reference=s.SIDECAR_SHA,canonical_plan_sha256=s.PLAN_SHA,
        physical_feedback='Operator reports better P2 small-brush result and stable800/20 after initial wetting; no measured runtime or widths supplied',
        manual_exchange_assumed_seconds=cfg['manual_exchange_seconds_assumed'],machine_authorized=False)
    roles={
        'SMALL_ONLY':[i for i in ids if records[i]['classification']=='main'],
        'BAEGUNMO_MAIN':[i for i in ids if records[i]['classification']=='main'],
        'FINE_DETAIL':[i for i in ids if records[i]['classification']=='fine']}
    schedules={};timings={}
    for role,chosen in roles.items():
        groups,diag=schedule(chosen,records,edges,rank,cfg['soft_batch_contacts']);schedules[role]=groups
        cmd,mat=n.build(groups,fragments,p,policy,20);is_fine=role=='FINE_DETAIL';prof=fine if is_fine else p
        if is_fine:cmd=fine_transform(cmd,prof)
        n.audit_ir(cmd,mat,groups,fragments,prof)
        name=f'SPRING_{panel}_INK_{role}_REVIEW';report['jobs'][name]=write(out,name,cmd,prof,groups,fragments,fine=is_fine)
        air=s.air_projection(cmd,prof);report['jobs'][name.replace('_INK_','_AIR_')]=write(out,name.replace('_INK_','_AIR_'),air,prof,groups,fragments,True,is_fine)
        s.save(out/(role+'.execution.json.gz'),dict(groups=groups,ordering=diag))
        s.save(out/(role+'.reload.json.gz'),mat);s.save(out/(role+'.stations.json.gz'),n.station_records(cmd,prof))
        s.save(out/(role+'.IR.json.gz'),[asdict(c) for c in cmd])
        timings[role]=n.summary(cmd,mat,prof)
        timings[role]['drawing_mm']=sum(fs[i]['length_mm'] for i in chosen)
        print(role,len(chosen),'switches',mat['concentration_changes'],'loads',mat['total_loads'],flush=True)
    baseline_cmd,baseline_mat=n.build(base,fragments,p,policy,20);timings['PR35']=n.summary(baseline_cmd,baseline_mat,p)
    # Same selection/allocation in original order isolates scheduling savings.
    control=[[dict(source=i,pass_index=0,ink=records[i]['ink'],id=f'{i}:pass0')] for i in ids if i in roles['SMALL_ONLY']]
    cc,cm=n.build(control,fragments,p,policy,20);timings['same_selection_source_order']=n.summary(cc,cm,p)
    s.save(out/'runtime_switch_comparison.json',timings)
    for i in ids:
        r=records[i];r['variant_A']='main' if r['classification']=='main' else 'defer_color' if r['classification']=='fine' else r['classification']
        r['variant_B']=r['classification'];r['pressure_samples']=len(fragments[i].stroke.points)
        r['canonical_stroke_sha256']=s.digest(asdict(fragments[i].stroke))
    s.save(out/'source_roles.json.gz',[records[i] for i in ids])
    s.save(out/'color_handoff.json.gz',dict(palette_finalized=False,no_color_Gcode=True,avoid_strong_D4_spring_summer=True,
        future_color_layers=['base','structure_grouping','foreground_accent'],
        records=[records[i] for i in ids if records[i]['classification'] in ('fine','color')],
        fine_details_deferred_only_in_variant_A=True))
    s.save(out/'ordering_conflicts.json',dict(initial_fine_to_main_blocked=[i for i in blocked if i in ids],remaining_fine_to_main_edges=0,manual_brush_exchanges=1,
        policy='Blocked subordinate fine details deferred to color; blocked main trunks retained main. No dependency is overridden to force two stages.'))
    allocation={}
    for label,chosen in [('PR35',ids),('A',roles['SMALL_ONLY']),('B',roles['BAEGUNMO_MAIN']+roles['FINE_DETAIL'])]:
        stats=defaultdict(lambda:dict(sources=0,dark_sources=0,drawing_mm=0.,dark_mm=0.))
        for i in chosen:
            r=records[i];ink=r['original_ink'] if label=='PR35' else r['ink']
            for key in ('all','family/'+r['family'],'depth/'+r['depth_band'],'family_depth/'+r['family']+'/'+r['depth_band']):
                v=stats[key];v['sources']+=1;v['dark_sources']+=ink=='DARK_INK';v['drawing_mm']+=r['length_mm'];v['dark_mm']+=r['length_mm']*(ink=='DARK_INK')
        allocation[label]=dict(stats)
    s.save(out/'allocation_by_depth_family.json',allocation)
    preview_fs=deepcopy(fs)
    for i in ids:preview_fs[i]['ink']=records[i]['ink']
    bounds=(300,0,600,900) if panel=='P2' else (0,0,300,900) if panel=='P1' else (0,0,600,900)
    render(out/'PR35.png',rows,fs,[e for g in base for e in g],bounds,2)
    for label,chosen in [('A',roles['SMALL_ONLY']),('B',roles['BAEGUNMO_MAIN']+roles['FINE_DETAIL']),('deferred',[i for i in ids if records[i]['classification'] in ('color','fine')])]:
        render(out/(label+'.png'),rows,preview_fs,[dict(source=i,ink=records[i]['ink']) for i in chosen],bounds,2)
    sheet(out,[out/'PR35.png',out/'A.png',out/'B.png',out/'deferred.png'],['PR35 control','A small brush','B small + fine','Color handoff (A superset)'],'comparison.png',(450,1350))
    report['variant_B_modeled_seconds']=timings['BAEGUNMO_MAIN']['modeled_seconds']+timings['FINE_DETAIL']['modeled_seconds']
    report['variant_B_plus_assumed_exchange_seconds']=report['variant_B_modeled_seconds']+cfg['manual_exchange_seconds_assumed']
    s.save(out/'verification.json',report)
    s.save(out/'MANIFEST_SHA256.json',{f.name:s.sha(f) for f in sorted(out.iterdir()) if f.name!='MANIFEST_SHA256.json'})
    return report

def audit(output,context,independent=None):
    out=Path(output);_,rows,fragments=s.load_inputs(Path(context));report=s.read(out/'verification.json')
    refs=s.read(out/'source_roles.json.gz');s.require(len(refs)==1851 and len({r['source_id'] for r in refs})==1851,'Source accounting')
    for r in refs:s.require(r['canonical_stroke_sha256']==s.digest(asdict(fragments[r['index']].stroke)) and r['source_record_sha256']==s.digest(rows[r['index']]),'Source or width hash')
    used={};checks={}
    for role in ('SMALL_ONLY','BAEGUNMO_MAIN','FINE_DETAIL'):
        groups=s.read(out/(role+'.execution.json.gz'))['groups'];p=s.Profile.load(out/('profile.fine.PROVISIONAL.json' if role=='FINE_DETAIL' else 'profile.small.json'))
        cmd=[s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None}) for c in s.read(out/(role+'.IR.json.gz'))]
        mat=s.read(out/(role+'.reload.json.gz'));n.audit_ir(cmd,mat,groups,fragments,p)
        used[role]={e['source'] for g in groups for e in g}
        for air,commands in [(False,cmd),(True,s.air_projection(cmd,p))]:
            name=f'SPRING_P2_{"AIR" if air else "INK"}_{role}_REVIEW'
            raw=(out/(name+'.gcode')).read_bytes();s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes())==raw,'Gzip mismatch')
            checks[name]=verify(raw.decode(),commands,p,groups,fragments,air,role=='FINE_DETAIL')
    s.require(not used['BAEGUNMO_MAIN']&used['FINE_DETAIL'],'Duplicated brush stage source')
    s.require(used['SMALL_ONLY']==used['BAEGUNMO_MAIN'],'Shared content policy differs')
    manifest=s.read(out/'MANIFEST_SHA256.json');s.require(all(s.sha(out/name)==h for name,h in manifest.items()),'Delivered SHA mismatch')
    equal={}
    if independent:
        for name in manifest:
            other=Path(independent)/name
            if other.exists():equal[name]=(out/name).read_bytes()==other.read_bytes()
        s.require(len(equal)>=30 and all(equal.values()),'Independent regeneration mismatch')
    result=dict(programs=checks,source_accounting_verified=True,original_width_XY_pressure_hashes_verified=True,independent_byte_equality=equal,machine_authorized=False)
    s.save(out/'delivered_audit.json',result);return result

if __name__=='__main__':
    a=argparse.ArgumentParser(__doc__);a.add_argument('--output',required=True);a.add_argument('--context',required=True);a.add_argument('--panel',choices=['P1','P2','P1P2'],default='P2');a.add_argument('--verify',action='store_true');a.add_argument('--independent');v=a.parse_args()
    if v.verify:
        print(json.dumps(audit(v.output,v.context,v.independent)));raise SystemExit
    r=generate(v.output,v.context,v.panel);print(json.dumps({'selection':r['selection_counts'],'blocked_fine':len(r['fine_candidates_blocked_by_main_successors']),'B_seconds':r['variant_B_modeled_seconds']}))
