"""Nested physical-density presets and screen-supported terminal accents."""
from copy import deepcopy
import numpy as np
from scipy.ndimage import distance_transform_edt,gaussian_filter,gaussian_filter1d,binary_dilation
from scipy.spatial import cKDTree
from scipy.signal import find_peaks
from datascape.projection.composition import smoothstep
from datascape.strokes.vector import sample,resample,split_at_gate,finalize,phase
from datascape.strokes.generators import taebaek_rows,structure_lines,valid_runs,contours
from datascape.strokes.hierarchy import select_c,path_length,total_length,breathe,trace_lattice_edges
from datascape.strokes.grammar import transfer_mist,hard_clip,connect_candidates,strength_envelope


def arc(path):
    p=np.asarray(path);return np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]


def profile_vertices(stroke,maximum_step=1.2):
    """Retain profile controls even when a straight path simplifies to two tips."""
    p=np.array(stroke['xy_mm']);points=[p[0]]
    for a,b in zip(p[:-1],p[1:]):
        n=max(1,int(np.ceil(np.linalg.norm(b-a)/maximum_step)))
        points.extend(a+(b-a)*t for t in np.linspace(0,1,n+1)[1:])
    stroke['xy_mm']=np.round(points,3).tolist()
    return np.array(stroke['xy_mm'])


def density_presets(current,fixed,root,config,parent_config,hierarchy_config):
    """Add interleaved A rows and select nested C sets; never copy-offset paths."""
    from datascape.strokes.vector import read_vectors
    import json
    c=config['density'];vc=json.loads((root/parent_config['vector_config']).read_text())
    tc={**vc['taebaek'],'first_depth_m':vc['taebaek']['first_depth_m']+vc['taebaek']['depth_pitch_m']/2}
    raw=taebaek_rows(fixed['base'],tc)
    # Omission and preset selection belong to the continuous parent. Panel
    # clipping happens inside transfer_mist after those path-space decisions.
    candidates=[{'id':f'A-half-depth-{i:06d}','xy_mm':p.tolist(),'width_mm':.32,'layer':'A','preview_opacity':.82,
                 'expression':{'intensity':.6,'pressure_calibrated':False}} for i,p in enumerate(raw)]
    extra=transfer_mist(candidates,fixed,'combined',parent_config)
    for s in extra:s['id']='interleaved-'+s['id'];s['density_origin']='Additional actual half-depth source rows'
    flow=read_vectors(root/hierarchy_config['source_vectors']['C'])['strokes'];flow=[s for s in flow if s.get('layer')=='terrain']
    layers={k:[s for s in current if s['layer']==k] for k in ['A','B','C','D','V']};sets={'current':layers};record={}
    for name,pc in c['presets'].items():
        added=[]
        probabilities={s['id']:sum(float(np.mean(sample(fixed['old']['depth_roles'][k],resample(s['xy_mm'],2))))*v for k,v in pc['A_interleaved_keep'].items()) for s in candidates}
        for s in extra:
            probability=probabilities[s['source_stroke_id']]
            if phase(s['source_stroke_id'],config['seed']+71)<probability:added.append(s)
        cc=select_c(flow,fixed['base'],hierarchy_config,pc['C_density'])
        # Explicit union preserves every current support path, even at saturation.
        by_id={s['id']:s for s in layers['C']}
        for s in cc:by_id.setdefault(s['id'],s)
        sets[name]={**layers,'A':layers['A']+added,'C':list(by_id.values())}
        record[name]={'additional_A_paths':len(added),'additional_A_length_mm':total_length(added),'C_paths':len(by_id)}
    return sets,record


def visible_supports(fixed,derivative,projection,config):
    """Skyline/depth edges first; physical ridge and cliff proxies are gated."""
    c=config['D'];b=fixed['base'];occ=b['occupied'];q=b['depth_m'];xyz=fixed['_grammar_xyz'];h,w=occ.shape
    edges=[];jump=np.zeros_like(q);pair_count=0
    for axis in [0,1]:
        aa=(slice(None),slice(None,-1)) if axis==1 else (slice(None,-1),slice(None))
        bb=(slice(None),slice(1,None)) if axis==1 else (slice(1,None),slice(None))
        depth=np.abs(q[aa]-q[bb]);source=np.linalg.norm(xyz[aa][:,:,:2]-xyz[bb][:,:,:2],axis=2)
        # Both a real source separation and a depth step are required.
        hit=occ[aa]&occ[bb]&(depth>c['depth_jump_m'])&(source>c['minimum_source_jump_m'])
        jump[aa]=np.maximum(jump[aa],np.where(hit,depth,0));jump[bb]=np.maximum(jump[bb],np.where(hit,depth,0));pair_count+=int(hit.sum())
        for y,x in zip(*np.where(hit)):
            edges.append(((int(x+1),int(y)),(int(x+1),int(y+1))) if axis==1 else ((int(x),int(y+1)),(int(x+1),int(y+1))))
    raw=[];first=np.argmax(occ,axis=0);valid=occ.any(axis=0)
    sky=np.column_stack([np.arange(w)+.5,gaussian_filter1d(first.astype(float)+.5,1.0)])
    tangent=np.gradient(sky,axis=0);normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
    sky+=normal*c['inset_mm']
    for p in split_at_gate(sky,np.where(valid,1.,-1.),8):
        # Peak-centered shoulder windows avoid outlining the whole skyline.
        at=arc(p);peaks,_=find_peaks(-p[:,1],prominence=c['skyline_prominence_mm'],distance=c['skyline_peak_spacing_mm'])
        if not len(peaks):peaks=[int(np.argmin(p[:,1]))]
        for peak in peaks:
            ids=(at>=at[peak]-c['skyline_left_breath_mm'])&(at<=at[peak]+c['skyline_right_breath_mm'])
            if ids.sum()>2:raw.append(('skyline',p[ids]))
    for p in trace_lattice_edges(edges):
        p=resample(p,.7);p=np.column_stack([gaussian_filter1d(p[:,i],1.) for i in range(2)])
        t=np.gradient(p,axis=0);normal=np.column_stack([-t[:,1],t[:,0]]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
        a=p+normal*c['inset_mm'];bb=p-normal*c['inset_mm'];qa=sample(q,a);qb=sample(q,bb)
        qa=np.where(sample(occ,a,order=0)>.5,qa,np.inf);qb=np.where(sample(occ,bb,order=0)>.5,qb,np.inf)
        # Trace the nearer surviving surface, never both sides of one boundary.
        p=np.where((qa<=qb)[:,None],a,bb)
        for run in valid_runs(p,b,jump_m=c['maximum_local_source_step_m']):raw.append(('occlusion',run))
    # Differentiate the actual smooth F2 mapping on the raw terrain tangents.
    flat=xyz.reshape(-1,3);p0,_=projection.project(flat,600,900);d=derivative
    de=np.column_stack([np.ones(h*w)*5,np.zeros(h*w),d['gx'].ravel()*5])
    dn=np.column_stack([np.zeros(h*w),np.ones(h*w)*5,d['gy'].ravel()*5])
    pe,_=projection.project(flat+de,600,900);pn,_=projection.project(flat+dn,600,900)
    a=pe-p0;bb=pn-p0;det=(a[:,0]*bb[:,1]-a[:,1]*bb[:,0]).reshape(h,w)
    denom=(np.linalg.norm(a,axis=1)*np.linalg.norm(bb,axis=1)).reshape(h,w)
    tangency=1-np.clip(np.abs(det)/np.maximum(denom,1e-8),0,1);tangency[~occ]=0
    edge_mask=(jump>0)|fixed['features']['silhouette'].astype(bool)
    edge_distance=distance_transform_edt(~edge_mask)
    # Ridge/rock proxies are secondary and must approach a visible terminal edge.
    az=np.deg2rad(projection.camera.azimuth_deg);rx,ry=np.cos(az),-np.sin(az)
    lateral=d['gx']*rx+d['gy']*ry;bend=d['hxx']*rx*rx+2*d['hxy']*rx*ry+d['hyy']*ry*ry
    for _,p in contours(lateral,occ,[0]):
        gate=np.minimum.reduce([-sample(bend,p)/c['crest_curvature_per_m']-1,
            sample(tangency,p)-c['minimum_tangency'],c['maximum_secondary_edge_distance_mm']-sample(edge_distance,p)])
        for part in split_at_gate(p,gate,12):
            for run in valid_runs(part,b):raw.append(('visible_crest',run))
    slope=np.nan_to_num(b['slope_deg'])
    for _,p in contours(slope,occ,c['cliff_levels_deg']):
        gate=np.minimum(sample(tangency,p)-c['minimum_tangency'],c['maximum_secondary_edge_distance_mm']-sample(edge_distance,p))
        for part in split_at_gate(p,gate,12):
            z=sample(xyz[:,:,2],part)
            for run in split_at_gate(part,z-np.percentile(z,55),10):
                for v in valid_runs(run,b):raw.append(('rock_edge_proxy',v))
    volume=projection.volume_determinant(flat[occ.ravel()],600,900)
    return raw,{'depth_jump':jump,'tangency':tangency,'edge_distance':edge_distance,'projected_surface_det':det}, {'adjacent_depth_source_edges':pair_count,'raw_paths':len(raw),'raw_by_kind':{k:sum(kind==k for kind,_ in raw) for k in c['type_priority']},'positive_volume_mapping':bool(np.all(volume>0)),'minimum_volume_jacobian':float(np.min(volume))}


def make_profiled(paths,items,name,width,fixed,envelope):
    result=finalize(paths,name,width,{'layer':'D','preview_opacity':1,'expression':{'intensity':1,'pressure_calibrated':False}})
    for s in result:
        profile_vertices(s)
        parent=paths[s['parent_path']];dense=resample(parent,.18);at=arc(dense);_,ix=cKDTree(dense).query(s['xy_mm']);t=at[ix]/max(at[-1],1e-9)
        strength=strength_envelope(t)*sample(fixed['retention'],s['xy_mm'])**.25 if envelope else np.ones(len(t))
        s.update(width_profile_mm=(width*strength).round(4).tolist(),opacity_profile=(.08+.92*strength).round(4).tolist(),
                 support_type=items[s['parent_path']]['kind'],source_event=items[s['parent_path']]['events'],profile_parent_range=[float(t[0]),float(t[-1])])
        s['expression']={**s['expression'],'intensity_samples':strength.round(4).tolist()}
    return result


def terminal_d(raw,fields,fixed,a_strokes,body,config,connected=False):
    c=config['D'];width=c['width_mm']
    if connected:
        chains,joins=connect_candidates(raw,fixed,{**c,'width_mm':width})
    else:chains=[{'kind':k,'path':p,'events':[i]} for i,(k,p) in enumerate(raw)];joins=0
    tips=np.concatenate([np.asarray(s['xy_mm'])[[0,-1]] for s in a_strokes]);tip_tree=cKDTree(tips)
    proposals=[]
    for event,item in enumerate(chains):
        p=resample(item['path'],.6)
        for piece in breathe(p,c['maximum_path_mm'],c['breath_gap_mm']):
            for run in hard_clip(piece,fixed,width,c['minimum_path_mm']):
                if connected:
                    # Terminal edges release into soft mist before a low foothill.
                    z=sample(fixed['_grammar_xyz'][:,:,2],run)
                    if z[0]<z[-1]:run=run[::-1]
                    rr=sample(fixed['retention'],run);foot=sample(fixed['features']['relative_foot'],run)
                    low=(rr<c['release_retention'])&((foot>.45)|(rr<.15))
                    bad=np.flatnonzero(low&(arc(run)>path_length(run)*.3))
                    if len(bad):run=run[:bad[0]+1]
                    if path_length(run)<c['filtered_minimum_mm']:continue
                distance=tip_tree.query(run)[0]
                score=c['type_priority'][item['kind']]+.15*float(np.mean(sample(fixed['features']['ridge'],run)))+.10*float(np.mean(np.exp(-distance/4)))+.003*min(path_length(run),160)
                proposals.append({**item,'path':run,'score':score,'event':event})
    chosen=[];points=[];used=0;counts={};type_counts={};budget=min(c['maximum_total_length_mm'],c['maximum_length_fraction']/(1-c['maximum_length_fraction'])*total_length(body))
    for it in sorted(proposals,key=lambda x:(-x['score'],x['event'])):
        p=it['path'];length=path_length(p)
        if used+length>budget or len(chosen)>=c['maximum_paths'] or counts.get(it['event'],0)>=c['maximum_per_event'] or type_counts.get(it['kind'],0)>=c['maximum_type_paths'][it['kind']]:continue
        if points and cKDTree(np.concatenate(points)).query(resample(p,.7))[0].min()<c['minimum_spacing_mm']:continue
        chosen.append(it);points.append(resample(p,.5));used+=length;counts[it['event']]=counts.get(it['event'],0)+1;type_counts[it['kind']]=type_counts.get(it['kind'],0)+1
    paths=[it['path'] for it in chosen];strokes=make_profiled(paths,chosen,'D-terminal' if connected else 'D-screen',width,fixed,connected)
    return strokes,{'selected_parents':len(paths),'endpoint_joins':joins,'length_budget_mm':budget,'selected_length_mm':total_length(strokes),'types':{k:sum(x['kind']==k for x in chosen) for k in c['type_priority']}}


def mist_context(fixed,a_strokes,config):
    """Read-only transition diagnostics, not new painterly omission fields."""
    c=config['B'];r=fixed['retention'];gy,gx=np.gradient(gaussian_filter(r,.8));strength=np.hypot(gx,gy)
    transition=(strength>c['transition_gradient_per_mm'])&(r>.08)&(r<.92)&fixed['base']['occupied']
    distance=distance_transform_edt(~transition);ink=np.zeros_like(r)
    for s in a_strokes:
        ij=np.floor(resample(s['xy_mm'],.5)).astype(int);x=np.clip(ij[:,0],0,599);y=np.clip(ij[:,1],0,899);ink[y,x]=1
    support=gaussian_filter(ink,c['A_support_sigma_mm']);support/=max(float(support.max()),1e-9)
    return {'gx':gx,'gy':gy,'strength':strength,'transition_distance':distance,'A_support':support}


def internal_b(raw,fixed,derivative,a_strokes,config,context):
    """Intrinsic terrain candidates first; continuous inward/orientation retreat."""
    c=config['B'];d=derivative;f=fixed['features'];r=fixed['retention'];width=c['width_mm']
    curvature=np.clip(np.sqrt(d['hxx']**2+2*d['hxy']**2+d['hyy']**2)/c['curvature_full_per_m'],0,1)
    score=.65*curvature+.35*np.maximum(f['valley_small'],f['valley_medium'])
    proposals=[]
    for event,line in enumerate(raw):
        p=resample(line,.5);t=np.gradient(p,axis=0);t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9)
        normal=np.column_stack([sample(context['gx'],p),sample(context['gy'],p)]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
        parallel=1-np.abs(np.sum(t*normal,axis=1));dist=sample(context['transition_distance'],p)
        proximity=1-smoothstep(dist/c['inward_retreat_mm']) if c['inward_retreat_mm']>0 else np.zeros_like(dist)
        retreat=proximity*parallel*c['orientation_penalty']
        gate=np.minimum.reduce([sample(score,p)-c['minimum_score'],sample(r,p)-c['minimum_retention'],
            sample(context['A_support'],p)-c['minimum_A_support'],c['maximum_parallel_penalty']-retreat])
        for part in split_at_gate(p,gate,c['minimum_path_mm']):
            for breath in breathe(part,c['maximum_path_mm'],c['breath_gap_mm']):
                for run in hard_clip(breath,fixed,width,c['minimum_path_mm']):
                    proposals.append((float(np.mean(sample(score,run))),event,run))
    chosen=[];claimed=[];used=0.;budget=total_length(a_strokes)*c['maximum_A_length_fraction']
    for score,event,p in sorted(proposals,key=lambda x:(-x[0],x[1])):
        length=path_length(p)
        if used+length>budget:continue
        if claimed and np.mean(cKDTree(np.concatenate(claimed)).query(resample(p,1))[0]<c['minimum_spacing_mm'])>.1:continue
        chosen.append(p);claimed.append(resample(p,.6));used+=length
    strokes=finalize(chosen,'B-internal',width,{'layer':'B','preview_opacity':.94,'expression':{'intensity':.8,'pressure_calibrated':False}})
    for s in strokes:
        p=profile_vertices(s);parent=resample(chosen[s['parent_path']],.18);at=arc(parent);_,ix=cKDTree(parent).query(p);t=at[ix]/max(at[-1],1e-9)
        strength=np.sin(np.pi*t)**.4*sample(r,p)**.2
        s['width_profile_mm']=(width*(.2+.8*strength)).round(4).tolist();s['opacity_profile']=(.94*(.25+.75*strength)).round(4).tolist()
        s['expression']={**s['expression'],'intensity_samples':(.8*strength).round(4).tolist()};s['source']='Unmasked intrinsic DEM curvature/valley and source-continuous structure paths'
    return strokes,{'intrinsic_candidates':len(raw),'ranked_surviving_pieces':len(proposals),'length_budget_mm':budget,'selected_parents':len(chosen),'mask_derived_candidates':0}


def boundary_relation(strokes,context,fixed,config):
    near=parallel=length=inside=0.
    for s in strokes:
        p=resample(s['xy_mm'],.6);dl=np.linalg.norm(np.diff(p,axis=0),axis=1);t=np.diff(p,axis=0);t/=np.maximum(dl[:,None],1e-9)
        n=np.column_stack([sample(context['gx'],p[:-1]),sample(context['gy'],p[:-1])]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-9)
        close=sample(context['transition_distance'],p[:-1])<config['B']['inward_retreat_mm'];pa=np.abs(np.sum(t*n,axis=1))<.35
        near+=float(dl[close].sum());parallel+=float(dl[close&pa].sum());inside+=float(dl[sample(context['A_support'],p[:-1])>config['B']['minimum_A_support']].sum());length+=float(dl.sum())
    return {'length_mm':length,'near_transition_length_fraction':near/max(length,1),'parallel_near_transition_fraction':parallel/max(length,1),'inside_A_support_fraction':inside/max(length,1)}
