"""Connected skeletons and vector transfer functions on unchanged F2 fields."""
from copy import deepcopy
import numpy as np
from scipy.ndimage import distance_transform_edt,gaussian_filter1d
from scipy.spatial import cKDTree
from datascape.projection.composition import smoothstep
from datascape.strokes.vector import resample,sample,split_at_gate,phase,finalize
from datascape.strokes.hierarchy import skeleton_candidates,path_length,total_length


def strength_envelope(t):
    """Weak entry, sustained center, weak exit, independent of terrain height."""
    t=np.clip(np.asarray(t),0,1)
    return (.06+.94*smoothstep(t/.26))*(.02+.98*(1-smoothstep((t-.62)/.38)))


def hard_clip(path,fixed,width,minimum):
    """Only fixed zero cores, nominal footprint and unconditional boundary."""
    p=resample(path,.35);safe=fixed['_grammar_safe']
    gate=np.minimum.reduce([sample(safe,p,order=0)-width/2-1.4,
        p[:,0]-width/2,600-width/2-p[:,0],p[:,1]-width/2,898-width/2-.002-p[:,1]])
    return split_at_gate(p,gate,minimum)


def compatible_bridge(a,b,fixed,config):
    """Do not join nearby unrelated axes or cross an omitted/hidden valley."""
    gap=np.linalg.norm(a[-1]-b[0])
    if gap>config['maximum_join_gap_mm']:return False
    ta=a[-1]-a[max(0,len(a)-5)];tb=b[min(len(b)-1,4)]-b[0]
    if ta@tb/(max(np.linalg.norm(ta)*np.linalg.norm(tb),1e-9))<np.cos(np.deg2rad(config['maximum_join_angle_deg'])):return False
    bridge=resample([a[-1],b[0]],.4);base=fixed['base']
    if np.min(sample(fixed['retention'],bridge))<=1e-8:return False
    q=sample(base['depth_m'],bridge)
    if np.ptp(q)>config['maximum_join_depth_change_m']:return False
    xyz=fixed['_grammar_xyz'];world=np.column_stack([sample(xyz[:,:,i],bridge) for i in range(3)])
    if np.linalg.norm(world[-1,:2]-world[0,:2])>config['maximum_join_source_gap_m']:return False
    return len(hard_clip(bridge,fixed,config['width_mm'],0))==1


def connect_candidates(candidates,fixed,config):
    """Endpoint graph with tangent/depth constraints and no branching shortcut."""
    chains=[{'kind':k,'path':resample(p,1),'events':[i]} for i,(k,p) in enumerate(candidates) if path_length(p)>=8]
    changed=True;joins=0
    while changed:
        changed=False;best=None
        for i,a in enumerate(chains):
            for j in range(i+1,len(chains)):
                b=chains[j]
                if a['kind']!=b['kind']:continue
                for ra in [False,True]:
                    pa=a['path'][::-1] if ra else a['path']
                    for rb in [False,True]:
                        pb=b['path'][::-1] if rb else b['path'];gap=np.linalg.norm(pa[-1]-pb[0])
                        if gap<config['maximum_join_gap_mm'] and (best is None or gap<best[0]) and compatible_bridge(pa,pb,fixed,config):best=(gap,i,j,pa,pb)
        if best:
            _,i,j,a,b=best;chains[i]['path']=np.concatenate([a,b]);chains[i]['events']+=chains[j]['events'];chains.pop(j);joins+=1;changed=True
    return chains,joins


def build_connected_d(fixed,derivative,azimuth,hierarchy_config,current,body,config):
    """Extend existing supported accents along raw axes before attenuation."""
    dc=config['D'];raw=skeleton_candidates(fixed,derivative,azimuth,hierarchy_config['D'])
    chains,joins=connect_candidates(raw,fixed,{**dc,'width_mm':hierarchy_config['styles']['D']['width_mm']})
    anchors={}
    for s in current:anchors.setdefault(s['support_type'],[]).append(resample(s['xy_mm'],1))
    trees={k:cKDTree(np.concatenate(v)) for k,v in anchors.items()}
    proposals=[];xyz=fixed['_grammar_xyz'];width=hierarchy_config['styles']['D']['width_mm']
    for chain_id,chain in enumerate(chains):
        p=resample(chain['path'],.6);kind=chain['kind']
        if kind not in trees:continue
        distance=trees[kind].query(p)[0]
        if distance.min()>dc['anchor_distance_mm']:continue
        # Windows grow around already selected support; no new global outline.
        candidates=np.flatnonzero(distance<dc['anchor_distance_mm'])
        centers=[candidates[0]]
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        for index in candidates:
            if arc[index]-arc[centers[-1]]>dc['maximum_path_mm']*.8:centers.append(index)
        for center in centers:
            half=dc['maximum_path_mm']/2;ids=np.abs(arc-arc[center])<=half
            section=p[ids]
            if len(section)<3:continue
            section=np.column_stack([gaussian_filter1d(section[:,i],.7) for i in range(2)])
            for part in hard_clip(section,fixed,width,dc['connected_minimum_mm']):
                z=sample(xyz[:,:,2],part)
                if z[0]<z[-1]:part=part[::-1]
                score=hierarchy_config['D']['type_priority'][kind]+float(np.mean(sample(fixed['features']['ridge'],part)))+.003*min(path_length(part),140)
                proposals.append({'path':part,'kind':kind,'chain':chain_id,'score':score,'events':chain['events']})
    budget=dc['maximum_length_fraction']/(1-dc['maximum_length_fraction'])*total_length(body)
    selected=[];points=[];used=0.;chain_count={}
    for item in sorted(proposals,key=lambda x:x['score'],reverse=True):
        p=item['path'];length=path_length(p)
        if used+length>budget or chain_count.get(item['chain'],0)>=dc['maximum_per_chain']:continue
        if points and cKDTree(np.concatenate(points)).query(resample(p,1))[0].min()<dc['minimum_spacing_mm']:continue
        selected.append(item);points.append(resample(p,.7));used+=length;chain_count[item['chain']]=chain_count.get(item['chain'],0)+1
    connected=finalize([x['path'] for x in selected],'D-connected',width,{'layer':'D','preview_opacity':1,'role':'continuous selected skeleton'})
    filtered_paths=[];parents=[]
    for item in selected:
        p=resample(item['path'],.5);foot=sample(fixed['features']['relative_foot'],p);q=sample(fixed['base']['depth_m'],p)
        far=smoothstep((q-1600)/1800)
        # Stop in a low-support foot; do not splice through it and resume below.
        retention=sample(fixed['retention'],p)
        release=(1-smoothstep((foot-.5)/.45)*far)*retention**.4
        bad=np.flatnonzero((release<dc['release_threshold'])&(np.arange(len(p))>len(p)*.28))
        if len(bad):p=p[:bad[0]+1]
        if len(p)>2 and path_length(p)>=dc['filtered_minimum_mm']:filtered_paths.append(p);parents.append(item)
    filtered=finalize(filtered_paths,'D-envelope',width,{'layer':'D','preview_opacity':1,'role':'connected skeleton with central strength envelope'})
    for collection,origins in [(connected,selected),(filtered,parents)]:
        for s in collection:
            parent=origins[s['parent_path']];s.update(support_type=parent['kind'],source_events=parent['events'],
                connected_chain=parent['chain'],expression={'intensity':1.,'pressure_calibrated':False})
    for s in filtered:
        parent=filtered_paths[s['parent_path']];dense=resample(parent,.2);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(dense,axis=0),axis=1))]
        _,indices=cKDTree(dense).query(s['xy_mm']);t=np.maximum.accumulate(arc[indices]/max(arc[-1],1e-9));p=np.array(s['xy_mm'])
        strength=strength_envelope(t)*sample(fixed['retention'],p)**.4
        s['width_profile_mm']=(width*strength).round(4).tolist()
        s['opacity_profile']=np.clip(.12+.88*strength,0,1).round(4).tolist()
        s['expression']['intensity_samples']=strength.round(4).tolist()
        s['profile_parent_range']=[float(t[0]),float(t[-1])]
    return connected,filtered,{'raw_support_paths':len(raw),'connected_chains':len(chains),'accepted_endpoint_joins':joins,
        'selected_continuous_parents':len(selected),'filtered_parents':len(filtered_paths),'length_budget_mm':budget}


def transfer_mist(candidates,fixed,mode,config):
    """Map the SAME retention field into actual paths and vertex profiles."""
    result=[];mc=config['mist'];roles=fixed['old']['depth_roles']
    for number,s in enumerate(candidates):
        width=s['width_mm'];p=resample(s['xy_mm'],.5)
        if len(p)<2:continue
        u=phase(s['id'],config['seed']);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        r=np.clip(sample(fixed['retention'],p),0,1)
        gamma=sum(sample(roles[k],p)*v for k,v in mc['density_exponent'].items())
        gate=np.ones(len(p))
        if mode!='binary':gate=np.minimum(gate,r**gamma-(.025+.95*u))
        if mode=='combined':
            period=mc['length_cycle_mm'];position=(arc+u*period)%period
            target=mc['minimum_window_mm']+(period-mc['minimum_window_mm'])*r
            length_gate=np.where(r>.82,1.,(target-position)/period)
            gate=np.minimum(gate,length_gate)
        safe=sample(fixed['_grammar_safe'],p,order=0)-width/2-1.4
        boundary=np.minimum.reduce([p[:,0]-width/2,600-width/2-p[:,0],p[:,1]-width/2,898-width/2-.002-p[:,1]])
        for run in split_at_gate(p,np.minimum.reduce([gate,safe,boundary]),mc['minimum_path_mm']):
            for final in finalize([run],f'{mode}-{number}-{len(result)}',width,{'layer':s['layer'],'preview_opacity':s['preview_opacity']}):
                xy=np.array(final['xy_mm']);rr=np.clip(sample(fixed['retention'],xy),0,1)
                final['source_stroke_id']=s['id'];final['mist_mode']=mode
                final['expression']={'intensity':s['expression']['intensity'],'pressure_calibrated':False}
                if mode=='combined':
                    opacity_gamma=sum(sample(roles[k],xy)*v for k,v in mc['opacity_exponent'].items())
                    final['opacity_profile']=(s['preview_opacity']*rr**opacity_gamma).round(4).tolist()
                    final['width_profile_mm']=(width*(mc['minimum_width_fraction']+(1-mc['minimum_width_fraction'])*rr**mc['width_exponent'])).round(4).tolist()
                    final['expression']['intensity_samples']=(s['expression']['intensity']*rr**.6).round(4).tolist()
                result.append(final)
    return result
