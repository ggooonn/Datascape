"""A body, B structure, C grain and sparse D skeleton on frozen F2 C."""
from collections import defaultdict
from copy import deepcopy
import numpy as np
from scipy.ndimage import gaussian_filter1d, distance_transform_edt
from scipy.spatial import cKDTree
from datascape.projection.composition import smoothstep
from datascape.strokes.vector import sample,resample,split_at_gate,phase,finalize,omit_path
from datascape.strokes.generators import contours,valid_runs


def path_length(path):
    return float(np.linalg.norm(np.diff(np.asarray(path),axis=0),axis=1).sum())


def total_length(strokes):
    return sum(path_length(s['xy_mm']) for s in strokes)


def style(strokes,layer,config):
    """Nominal widths/intensity stay separate from physical pressure or Z."""
    result=[];c=config['styles'][layer]
    for s in strokes:
        record=deepcopy(s);record.update(layer=layer,width_mm=c['width_mm'],opacity=1,
            preview_opacity=c['density_preview_opacity'],
            expression={'intensity':c['intensity'],'pressure_calibrated':False})
        record['id']=layer+'-'+record['id'];result.append(record)
    return result


def select_c(strokes,base,config,density):
    """Nested density sets with identical width, tone and surviving paths."""
    result=[]
    for s in strokes:
        p=resample(s['xy_mm'],2);q=sample(base['depth_m'],p)
        near=float(np.mean(1-smoothstep((q-600)/1000)))
        slope=float(np.mean(sample(np.nan_to_num(base['slope_deg']),p)))
        side=.18*float(np.clip((slope-12)/25,0,1))
        probability=density*max(near,side)
        if phase(s['id'],config['seed'])<probability:result.append(s)
    return style(result,'C',config)


def select_a(strokes,fixed,config):
    """Independent depth-density control; defaults preserve every A path."""
    weights=config['A']['depth_density_multipliers']
    if any(not 0<=value<=1 for value in weights.values()):
        raise ValueError('A keep multipliers must be between zero and one.')
    result=[]
    for s in strokes:
        p=resample(s['xy_mm'],2)
        probability=sum(weights[k]*float(np.mean(sample(v,p))) for k,v in fixed['old']['depth_roles'].items())
        if phase(s['id'],config['seed'])<min(1,probability+1e-12):result.append(s)
    return style(result,'A',config)


def select_b(strokes,fixed,derivatives,config,a_length):
    """Short local accents at valley/overlap and curvature changes."""
    b=fixed['base'];f=fixed['features'];d=derivatives
    curvature=np.sqrt(d['hxx']**2+2*d['hxy']**2+d['hyy']**2)
    strength=np.clip(curvature/config['B']['curvature_full_per_m'],0,1)
    valley=np.maximum(f['valley_small'],f['valley_medium'])
    score=.4*strength+.35*valley+.25*f['behind_edge']
    proposals=[]
    for s in strokes:
        p=resample(s['xy_mm'],.5)
        for part in split_at_gate(p,sample(score,p)-config['B']['minimum_score'],config['B']['minimum_mm']):
            for piece in breathe(part,config['B']['maximum_mm'],config['B']['gap_mm']):
                proposals.append((float(np.mean(sample(score,piece))),piece))
    selected=[];claimed=[];used=0.;budget=a_length*config['B']['maximum_length_fraction_of_A']
    for score,p in sorted(proposals,key=lambda x:x[0],reverse=True):
        length=path_length(p)
        if used+length>budget:continue
        dense=resample(p,1)
        if claimed and np.mean(cKDTree(np.concatenate(claimed)).query(dense)[0]<config['B']['spacing_mm'])>.15:continue
        selected.append(p);claimed.append(dense);used+=length
    return style(finalize(selected,'structure',config['styles']['B']['width_mm'],{'role':'selective structure accent'}),'B',config)


def breathe(path,maximum_mm,gap_mm):
    """Length-bounded runs with real gaps, never a renderer-only dash style."""
    p=resample(path,.5);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    for start in np.arange(0,max(arc[-1],.001),maximum_mm+gap_mm):
        ids=(arc>=start)&(arc<=start+maximum_mm)
        if ids.sum()>2:yield p[ids]


def trace_lattice_edges(edges):
    """Join visible-depth discontinuity segments and split at junctions."""
    graph=defaultdict(set)
    for a,b in edges:graph[a].add(b);graph[b].add(a)
    visited=set();paths=[]
    for start in sorted(graph,key=lambda n:(len(graph[n])==2,n)):
        for neighbor in sorted(graph[start]):
            key=tuple(sorted([start,neighbor]))
            if key in visited:continue
            line=[start];previous,current=start,neighbor;visited.add(key)
            while True:
                line.append(current)
                if len(graph[current])!=2:break
                choices=sorted(graph[current]-{previous})
                if not choices:break
                nxt=choices[0];key=tuple(sorted([current,nxt]))
                if key in visited:break
                visited.add(key);previous,current=current,nxt
            if len(line)>=5:paths.append(np.array(line,dtype=float))
    return paths


def occlusion_candidates(base,config):
    """Skyline and actual front/back depth jumps, never all terrain contours."""
    occ=base['occupied'];q=base['depth_m'];h,w=occ.shape;paths=[];edges=[]
    first=np.argmax(occ,axis=0);valid=occ.any(axis=0)
    skyline=np.column_stack([np.arange(w)+.5,gaussian_filter1d(first.astype(float),1.2)+config['inset_mm']])
    for p in split_at_gate(skyline,np.where(valid,1.,-1.),8):paths.append(('skyline',p))
    for y,x in zip(*np.where(occ[:,:-1]&occ[:,1:]&(np.abs(np.diff(q,axis=1))>config['depth_jump_m']))):
        edges.append(((int(x+1),int(y)),(int(x+1),int(y+1))))
    for y,x in zip(*np.where(occ[:-1]&occ[1:]&(np.abs(np.diff(q,axis=0))>config['depth_jump_m']))):
        edges.append(((int(x),int(y+1)),(int(x+1),int(y+1))))
    for p in trace_lattice_edges(edges):
        p=resample(p,.7);p=np.column_stack([gaussian_filter1d(p[:,i],1.5) for i in range(2)])
        tangent=np.gradient(p,axis=0);normal=np.column_stack([-tangent[:,1],tangent[:,0]])
        normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
        a=p+normal*config['inset_mm'];b=p-normal*config['inset_mm']
        # Choose one foreground side; do not darken both flanks of a ridge.
        qa=sample(q,a);qb=sample(q,b)
        qa=np.where(sample(occ,a,order=0)>.5,qa,np.inf)
        qb=np.where(sample(occ,b,order=0)>.5,qb,np.inf)
        shifted=np.where((qa<=qb)[:,None],a,b)
        paths.append(('occlusion',shifted))
    return paths


def skeleton_candidates(fixed,derivatives,azimuth_deg,config):
    """Measured-surface support proxies, not confirmed rock/geology edges."""
    b=fixed['base'];f=fixed['features'];d=derivatives;occ=b['occupied']
    az=np.deg2rad(azimuth_deg);rx,ry=np.cos(az),-np.sin(az)
    lateral=d['gx']*rx+d['gy']*ry
    bend=d['hxx']*rx*rx+2*d['hxy']*rx*ry+d['hyy']*ry*ry
    result=occlusion_candidates(b,config)
    for _,p in contours(lateral,occ,[0]):
        # Negative cross curvature selects one convex crest, not two edges.
        score=np.minimum(-sample(bend,p)/config['crest_curvature_per_m'],sample(f['ridge'],p)/config['crest_ridge_minimum'])-1
        for part in split_at_gate(p,score,8):
            result.extend(('crest',run) for run in valid_runs(part,b))
    slope=np.nan_to_num(b['slope_deg'])
    for level,p in contours(slope,occ,config['slope_break_levels_deg']):
        z=sample(np.nan_to_num(b['xyz'][:,:,2]),p)
        # Keep only the upper shoulder of a slope boundary, never its loop.
        high=z-np.percentile(z,config['upper_rim_percentile'])
        for part in split_at_gate(p,high,8):result.extend(('slope_break_proxy',run) for run in valid_runs(part,b))
    near=fixed['old']['depth_roles']['near']
    for _,p in contours(f['mound'],occ,[config['mound_level']]):
        score=sample(near,p)*sample(np.maximum(fixed['refined']['root_support'],fixed['refined']['positive_forms']),p)
        z=sample(np.nan_to_num(b['xyz'][:,:,2]),p)
        for part in split_at_gate(p,np.minimum(score-.1,(z-np.percentile(z,60))/10),6):
            result.extend(('foothold_rim_proxy',run) for run in valid_runs(part,b))
    return result


def split_saddles(path,base,maximum_mm,gap_mm):
    """Release at source-height reversals and strong projected bends."""
    p=resample(path,1);z=sample(np.nan_to_num(base['xyz'][:,:,2]),p)
    if z[0]<z[-1]:p=p[::-1];z=z[::-1]
    z=gaussian_filter1d(z,2);dz=np.gradient(z)
    direction=np.gradient(p,axis=0);direction/=np.maximum(np.linalg.norm(direction,axis=1)[:,None],1e-9)
    turn=np.zeros(len(p));turn[3:-3]=np.arccos(np.clip(np.sum(direction[:-6]*direction[6:],axis=1),-1,1))
    cut=np.zeros(len(p),bool)
    if len(p)>10:
        cut[3:-3]=((dz[3:-3]*dz[2:-4]<0)&(np.abs(dz[3:-3]-dz[2:-4])>.1))|(turn[3:-3]>.55)
    for part in split_at_gate(p,np.where(cut,-1.,1.),7):yield from breathe(part,maximum_mm,gap_mm)


def select_d(fixed,derivatives,azimuth_deg,config,base_strokes,context):
    """Score + one-sided selection + NMS + strict measured length budget."""
    dc=config['D'];b=fixed['base'];f=fixed['features'];width=config['styles']['D']['width_mm']
    raw=skeleton_candidates(fixed,derivatives,azimuth_deg,dc)
    safe=distance_transform_edt((fixed['retention']>1e-8)&b['occupied'])
    proposals=[]
    for event,(kind,path) in enumerate(raw):
        for piece in split_saddles(path,b,dc['maximum_stroke_mm'],dc['breath_gap_mm']):
            if path_length(piece)<dc['minimum_stroke_mm']:continue
            z=sample(np.nan_to_num(b['xyz'][:,:,2]),piece)
            if z[0]<z[-1]:piece=piece[::-1]
            q=sample(b['depth_m'],piece);height=sample(f['relative_foot'],piece)
            # Existing omission/global gates still dominate the new accents.
            probability=fixed['retention']
            for part in omit_path(piece,probability,safe,f'D:{event}',config['seed'],width,dc['minimum_stroke_mm']):
                score=float(np.mean(.5*sample(f['ridge'],part)+.3*sample(f['silhouette'],part)+.2*(1-sample(f['relative_foot'],part))))
                score+=dc['type_priority'][kind]
                proposals.append({'kind':kind,'path':part,'score':score,'event':event})
    terrain_length=total_length(base_strokes);all_length=terrain_length+total_length(context)
    budget=min(dc['target_all_length_fraction']/(1-dc['target_all_length_fraction'])*all_length,
               dc['maximum_terrain_length_fraction']/(1-dc['maximum_terrain_length_fraction'])*terrain_length)
    selected=[];claimed=[];used=0.;type_length=defaultdict(float);event_counts=defaultdict(int)
    for candidate in sorted(proposals,key=lambda x:(-x['score'],x['event'])):
        p=candidate['path'];length=path_length(p);kind=candidate['kind']
        if used+length>budget or event_counts[candidate['event']]>=dc['maximum_per_event']:continue
        if type_length[kind]+length>budget*dc['type_maximum_fraction'][kind]:continue
        dense=resample(p,.5)
        if claimed and cKDTree(np.concatenate(claimed)).query(dense)[0].min()<dc['minimum_spacing_mm']:continue
        selected.append(candidate);claimed.append(dense);used+=length;type_length[kind]+=length;event_counts[candidate['event']]+=1
    paths=[c['path'] for c in selected];strokes=style(finalize(paths,'skeleton',width,{'role':'sparse final skeleton'}),'D',config)
    for s in strokes:
        parent=selected[s['parent_path']];dense=resample(parent['path'],.25)
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(dense,axis=0),axis=1))]
        _,idx=cKDTree(dense).query(np.asarray(s['xy_mm']))
        t=arc[idx]/max(arc[-1],1e-9);taper=1-smoothstep((t-.4)/.6)
        s['width_profile_mm']=(width*taper).round(4).tolist()
        s['expression']['intensity_samples']=(config['styles']['D']['intensity']*taper).round(4).tolist()
        s.update(support_type=parent['kind'],support_event=parent['event'],selection_score=parent['score'],
                 side_rule='Single visible front/convex axis or upper shoulder; no paired flanks',
                 release_rule='Source-height reversal, strong bend, omission, or bounded breath')
        xyz=b['xyz'];p=np.asarray(s['xy_mm'])
        s['source_endpoints_xyz_m']=[[float(sample(np.nan_to_num(xyz[:,:,i]),p[[j]])[0]) for i in range(3)] for j in [0,-1]]
    return strokes,{'raw_candidates':len(raw),'ranked_pieces':len(proposals),'selected_events':len(selected),
        'length_budget_mm':budget,'selected_length_mm':total_length(strokes),'type_length_mm':dict(type_length),
        'minimum_spacing_mm':dc['minimum_spacing_mm'],'target_all_length_fraction':dc['target_all_length_fraction']}
