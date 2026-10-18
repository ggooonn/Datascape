"""Open-vector spring wash supports, with no filled paint or background regions.

Carrier geometry is distinct from ink, pigment/pressure calibration and masks.
All palette hex values come from the unchanged 20-slot project definition.
"""
from copy import deepcopy
import hashlib
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import substring
from datascape.integration.visibility import clip_source,signed_clearance,burn
from datascape.integration.cluster_scene import object_gate_v02,terrain_gate_v02,intersects
from datascape.strokes.vector import sample
from datascape.vegetation.tree_occlusion_proof import line_parts
from datascape.rendering.spring_integration import geometry_mask


def quantile(key,seed):
    return int(hashlib.sha256(f'{seed}/{key}'.encode()).hexdigest()[:12],16)/16**12


def depth_parameters(q,config):
    d=config['depth_modulation'];lo,hi=d['source_forward_range_m']
    u=np.clip((np.asarray(q)-lo)/(hi-lo),0,1)
    return dict(u=u,density=1-.64*u,width=1.7-.85*u,alpha=.28-.16*u)


def palette_weights(kind,q,config):
    role=config['object_palette_weights'][kind];global_weights=config['spring_active_target_percent']
    role_total=sum(role.values());prior_total=sum(global_weights[k] for k in role)
    w={k:.75*v/role_total+.25*global_weights[k]/prior_total for k,v in role.items()}
    u=float(depth_parameters(q,config)['u'])
    for k in w:
        w[k]*={'A3':1+1.6*u,'A5':1+.55*u,'C1':1+.4*u,
               'C2':1-.5*u,'C3':1-.8*u,'C4':1-.6*u,
               'A4':1-.45*u,'D1':1-.45*u,'D4':1-.65*u,'D5':1-.65*u,
               'B2':1-.2*u,'B4':1-.7*u}.get(k,1.)
    total=sum(w.values());return {k:v/total for k,v in w.items()}


def choose_slot(kind,q,key,config):
    weights=palette_weights(kind,q,config);keys=list(weights)
    u=quantile(key+'/palette',config['seed'])
    return keys[min(int(np.searchsorted(np.cumsum(list(weights.values())),u)),len(keys)-1)]


def color_record(points,key,owner,kind,q_values,config,basis,pass_index=0):
    p=np.asarray(points,float);line=LineString(p)
    if line.length<3:return None
    # Accents are short episodes, never a large flat purple/earth crown.
    q=float(np.mean(q_values));slot=choose_slot(kind,q,basis,config)
    if slot in ('B4','B2','D4','D5') and line.length>16:
        part=substring(line,(line.length-16)/2,(line.length+16)/2);p=np.asarray(part.coords)
        q_values=np.full(len(p),q)
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    u=arc/max(arc[-1],1e-9);env=.50+.50*np.sin(np.pi*u)**.65
    d=depth_parameters(q_values,config)
    width=d['width']*env*(.82 if kind=='terrain' else 1.)
    alpha=d['alpha']*(.75+.25*np.sin(np.pi*u))
    return dict(id=key,source_stroke_id=key,source_arc_mm=[0.,float(arc[-1])],
        xy_mm=p.tolist(),layer='color-support',source_family='C-like',owner_id=owner,
        origin_kind='new-color-support',color_kind=kind,palette_slot=slot,
        width_mm=float(np.mean(width)),width_profile_mm=np.asarray(width).tolist(),
        opacity_profile=np.asarray(alpha).tolist(),preview_opacity=float(np.mean(alpha)),
        material_channel='vector-wash-support',source_forward_mean_m=q,
        depth_fraction=float(np.mean(d['u'])),carrier_basis=basis,cross_layer=pass_index,
        ink='pigment-display-intent',expression=dict(pressure_calibrated=False),
        calibrated_dilution=False,physical_plotting_validated=False)


def safe_color_gate(fixed,obj,peers,corridor):
    other_gate=object_gate_v02(fixed,obj,peers) if obj else terrain_gate_v02(fixed,peers)
    if '_v02_global_safe' not in fixed:fixed['_v02_global_safe']=signed_clearance(fixed['refined']['global_retention']<=0)
    if '_v02_corridor_safe' not in fixed:fixed['_v02_corridor_safe']=signed_clearance(burn(corridor))
    global_safe=fixed['_v02_global_safe'];corridor_safe=fixed['_v02_corridor_safe']
    def gate(xy,arc,r):
        g,reasons=other_gate(xy,arc,r)
        width=max(r['width_profile_mm']);margin=width/2+.35+1.
        g=np.minimum.reduce([g,sample(global_safe,xy)-margin,sample(corridor_safe,xy)-margin,
            xy[:,0]-width/2,600-width/2-xy[:,0],898-width/2-xy[:,1]])
        return g,reasons+['color-footprint-reserves','bounded-open-passage']
    return gate


def build_wash(fixed,result,config,mode,corridor):
    spec=config['color_modes'][mode];seed=config['seed'];records=[];ledger=[];sources=[]
    objects=result['objects']
    # Existing canonical C is a carrier source. The main pass keeps its geometry;
    # the second cross-pass is explicitly derived and has independent lineage.
    for source in result['color_sources']:
        p=np.asarray(source['xy_mm']);mid=p[len(p)//2]
        q=float(sample(fixed['base']['depth_m'],[mid])[0]);d=depth_parameters(q,config)
        if quantile(source['source_stroke_id']+'/terrain-keep',seed)>float(d['density'])*spec['density_gain']*.83:continue
        for pass_index in range(spec['cross_layers']):
            if pass_index and quantile(source['id']+'/weave',seed)>.34:continue
            points=p.copy()
            if pass_index:
                tangent=np.gradient(points,axis=0);normal=np.c_[-tangent[:,1],tangent[:,0]]
                normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
                phase=np.linspace(0,np.pi,len(points))
                points+=normal*(1.6*np.sin(phase))[:,None]
            key=f'v02/color/terrain/{source["id"]}/pass-{pass_index}'
            qvals=sample(fixed['base']['depth_m'],points)
            r=color_record(points,key,'terrain-C','terrain',qvals,config,source['source_stroke_id'],pass_index)
            if r is None:continue
            r['source_family']='C';r['assumed_footprint_mm']=max(r['width_profile_mm'])
            r['ink_support_source_id']=source['source_stroke_id'];r['ink_support_arc_mm']=source['source_arc_mm']
            bb=LineString(points).bounds;peers=[o for o in objects if intersects(bb,o['bounds'])]
            sources.append(r);parts,a=clip_source(r,safe_color_gate(fixed,None,peers,corridor));records+=parts;ledger.append(a)
    for obj in objects:
        kind={'tree':'vegetation','rock':'rock','soil':'Soil'}[obj['kind']]
        q=obj['site']['source_forward_m'];d=depth_parameters(q,config)
        if kind=='vegetation':
            region=geometry_mask((obj['regions']['occupancy']>.025)&obj['visible'])
            region=region.buffer(1.3).buffer(-.5).intersection(geometry_mask(obj['visible']))
            angle=-17*(obj['flow'] or 1);spacing=3.6
        elif kind=='rock':
            region=obj['support'].intersection(geometry_mask(obj['visible']))
            orient=next((r.get('structural_orientation_deg',-12) for r in obj['records']),-12)
            angle=orient-24;spacing=4.2
        else:
            region=obj['support'].intersection(geometry_mask(obj['visible']))
            host=np.asarray(obj['host']['xy_mm']);delta=host[-1]-host[0]
            angle=np.degrees(np.arctan2(delta[1],delta[0]))-22;spacing=4.0
        region=region.difference(corridor)
        if region.is_empty:continue
        x0,y0,x1,y1=region.bounds;center=np.array([(x0+x1)/2,(y0+y1)/2]);diag=np.hypot(x1-x0,y1-y0)
        peers=[o for o in objects if intersects(obj['bounds'],o['bounds'])]
        gate=safe_color_gate(fixed,obj,peers,corridor)
        for pass_index in range(spec['cross_layers']):
            a=np.radians(angle+pass_index*37);along=np.array([np.cos(a),np.sin(a)])
            normal=np.array([-along[1],along[0]])
            rate=spec['density_gain']*float(d['density'])*(.46 if pass_index else 1.)
            phase=quantile(obj['id']+'/row-phase',seed)*spacing
            for row in range(-int(diag/spacing)-1,int(diag/spacing)+2):
                # Stable row-family quantiles concentrate actual vectors rather
                # than making an opaque ownership fill. Core rows get priority.
                offset=row*spacing+phase
                centrality=np.exp(-.5*(offset/max(diag*.27,3))**2)
                if quantile(obj['id']+f'/row-{row}/pass-{pass_index}',seed)>rate*(.50+.50*centrality):continue
                t=np.linspace(-diag*.72,diag*.72,max(18,int(diag*1.6)))
                bow=(1.2 if kind=='vegetation' else .8)*np.sin(t/max(diag*.25,1)+row*.23)
                points=center+t[:,None]*along+(offset+bow)[:,None]*normal
                line=LineString(points)
                for j,g in enumerate(line_parts(line.intersection(region))):
                    if g.length<3.2:continue
                    # Unequal entry/release lengths keep strokes from becoming
                    # one repeated perimeter-aligned hatch template.
                    start=.03*g.length*(.5+.5*np.sin(row*.7));end=g.length*(.91+.06*np.cos(row*.6))
                    if end-start<3:continue
                    part=substring(g,start,end);xy=np.asarray(part.coords)
                    qvals=sample(obj['q'],xy)
                    key=f'v02/color/{obj["id"]}/pass-{pass_index}/row-{row}/{j}'
                    band=row//3
                    basis=f'{obj["group"]}/{kind}/band-{band}/pass-{pass_index}'
                    r=color_record(xy,key,obj['id'],kind,qvals,config,basis,pass_index)
                    if r is None:continue
                    r['assumed_footprint_mm']=max(r['width_profile_mm']);r['group_id']=obj['group']
                    r['catalog_object_id']=obj['id'];sources.append(r)
                    parts,a=clip_source(r,gate);records+=parts;ledger.append(a)
    return records,sources,ledger


def wash_metrics(records):
    by_slot={};by_kind={};by_depth={k:dict(length_mm=0.,paths=0,weighted_width=0.,weighted_alpha=0.,palette_mm={}) for k in ['near','middle','far']}
    for r in records:
        length=LineString(r['xy_mm']).length;slot=r['palette_slot'];kind=r['color_kind']
        by_slot[slot]=by_slot.get(slot,0.)+length;by_kind[kind]=by_kind.get(kind,0.)+length
        q=r['source_forward_mean_m'];band='near' if q<1000 else 'middle' if q<2200 else 'far'
        b=by_depth[band];b['length_mm']+=length;b['paths']+=1
        b['weighted_width']+=length*np.mean(r['width_profile_mm']);b['weighted_alpha']+=length*np.mean(r['opacity_profile'])
        b['palette_mm'][slot]=b['palette_mm'].get(slot,0.)+length
    total=sum(by_slot.values())
    for b in by_depth.values():
        b['mean_width_mm']=b.pop('weighted_width')/max(b['length_mm'],1e-9)
        b['mean_display_alpha']=b.pop('weighted_alpha')/max(b['length_mm'],1e-9)
    return dict(paths=len(records),length_mm=total,palette_length_mm=by_slot,
        palette_length_percent={k:100*v/max(total,1e-9) for k,v in by_slot.items()},
        kind_length_mm=by_kind,depth=by_depth,
        ratio_basis='final centerline length; not pigment volume, wet area, saturation or measured opacity')
