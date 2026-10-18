"""Terrain patches, radial crowns, shared canopy carriers and jointed leaders.

All forms are derived experiments, separate from accepted catalogs. Canopy
carriers retain varying source-q profiles; visibility never assigns them one
invented object depth. Palette selection uses only existing material slots.
"""
from copy import deepcopy
import math
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter,distance_transform_edt
from shapely.geometry import LineString,Point,box
from shapely.ops import substring,unary_union
from datascape.strokes.vector import phase,sample,resample
from datascape.integration.visibility import clip_source,burn,signed_clearance
from datascape.vegetation.pictorial_families_v03 import supported_root,measured_tangent
from datascape.vegetation.structural_mid_far_v02 import growth_graph,record
from datascape.vegetation.tree_growth import segment
from datascape.vegetation.mid_far import root_visibility


def arc(xy):return np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]


def support_field(cid,kind,original,evidence,config):
    """Territorial extent and cluster concentration are independent controls."""
    if kind=='control':
        sites=deepcopy(original)
        for s in sites:s['patch_id']=s['stand_id'];s['density_variant']=kind
        return sites,[]
    region=config['regions'][cid];sites=[];rejected=[]
    for k,patch in enumerate(region['patches']):
        center=np.array(patch['center'],float);radii=np.array(patch['radii'],float);n=patch['count']
        for j in range(n):
            # A low-discrepancy disk avoids rows; first outer anchors keep the
            # same territorial extent when interior points become clustered.
            radius=math.sqrt((j+.5)/n);angle=j*math.pi*(3-math.sqrt(5))+k*.73
            if kind=='clustered' and j<n-4:radius*=.60
            x,q=center+radii*radius*np.array([math.cos(angle),math.sin(angle)])
            try:p=supported_root(evidence,x,q,np.mean(region['y_search_mm']),region['y_search_mm'])
            except ValueError:
                rejected.append(dict(patch=k,member=j,x_mm=float(x),q_m=float(q),reason='no-occupied-crossing'));continue
            if sample(evidence.protected_clearance,p.reshape(1,2),order=0)[0]<3.:
                rejected.append(dict(patch=k,member=j,x_mm=float(x),q_m=float(q),reason='locked-reserve-contact'));continue
            u=phase(f'v04/{cid}/{k}/{j}/height',config['seed']);scale=.69+.52*u
            if patch['role'] in ['relay','extension','isolated']:scale*=.70
            ident=f'v04/{cid}/patch-{k}/body-{j}'
            sites.append(dict(id=ident,stand_id=f'v04/{cid}/patch-{k}',patch_id=f'v04/{cid}/patch-{k}',
                stand_index=k,stand_role=patch['role'],member_index=j,member_count=n,root_xy_mm=p.tolist(),
                height_mm=region['base_height_mm']*scale,form=['B','P','U'][j%3],site=evidence.point(p),
                guide_u=float((x-region['bounds_mm'][0])/(region['bounds_mm'][2]-region['bounds_mm'][0])),
                guide_source_id='saved-F2-x-q-support-patch',tangent_xy=measured_tangent(evidence,p,[1.,0.]),density_variant=kind))
    return sites,rejected


def make_record(ident,xy,site,g,branch,channel,family,tier,config,**extra):
    xy=np.asarray(xy,float);r=record(ident,xy,site,g,branch,channel,config)
    r.update(pictorial_family=family,hierarchy_tier=tier,patch_id=site.get('patch_id',site['stand_id']),
        source_forward_profile_m=[site['site']['source_forward_m']]*len(xy),
        source_member_ids=[site['id']],generation_stage='v04-independent-foliage' if channel=='color' else 'v04-selected-structure')
    r.update(extra)
    if channel=='color':r.update(palette_slot='C2',color_kind='vegetation',width_mm=config['graphic_color_width_mm'],
        width_profile_mm=[config['graphic_color_width_mm']]*len(xy),preview_opacity=config['alpha'],local_role=extra.get('local_role','body'))
    return r


def structural_ink(site,g,family,config):
    # Representative structures establish a grove without rendering every axis.
    far=g['mode'].startswith('F');j=site['member_index'];out=[]
    if j%(5 if far else 3)!=0 and not(j==1 and site['stand_role']=='dominant'):return out
    axis=LineString(g['axis_xy_mm']);length=axis.length*(.74 if family=='U' else .58)
    if length>=config['minimum_ink_mm']:
        out.append(make_record(site['id']+f'/{family}/ink-axis',list(substring(axis,0,length).coords),site,g,None,'ink',family,'primary',config))
    if not far and family!='S':
        b=g['branches'][1];p=b['xy_mm']
        if LineString(p).length>=2.8:out.append(make_record(site['id']+f'/{family}/ink-branch',p,site,g,b,'ink',family,'secondary',config))
    return out


def radial(site,g,config):
    far=g['mode'].startswith('F');out=[];h=site['height_mm'];branches=[g['branches'][1],g['branches'][-1]]
    # Nine strokes per supported unit: the density test never adds fan rays.
    tiers=['short','medium','long','medium','short','short','medium','long','medium']
    for j,tier in enumerate(tiers):
        b=branches[0 if j<5 else 1];node=np.array(b['crown_node_xy_mm']);d=np.array(b['direction_xy'])
        u=phase(site['id']+f'/radial-{j}',config['seed']);theta=math.atan2(d[1],d[0])+([-1.,-.46,0.,.55,1.1][j] if j<5 else (j-6.5)*.55)
        length={'short':3.4+.7*u,'medium':(4.8 if far else 5.7)+1.4*u,
            'long':(7.6 if far else 10.)+(1.3 if far else 4.)*min(1.,h/(10 if far else 26))}[tier]
        v=np.array([math.cos(theta),math.sin(theta)]);normal=np.array([-d[1],d[0]])
        start=node+normal*(j%5-2)*.47+d*.35;p=segment(start,start+v*length,(.22 if far else .45)*(u-.3))
        out.append(make_record(site['id']+f'/R/ray-{j}',p,site,g,b,'color','R',tier,config,
            growth_direction_xy=v.tolist(),foliage_origin_xy_mm=node.tolist(),local_role='tip' if tier=='short' else 'body',
            generation_rule='two related crown nodes; selected long primary outward ray'))
    return out


def jointed(site,g,config):
    far=g['mode'].startswith('F');h=site['height_mm'];root=np.array(site['root_xy_mm'])
    u=phase(site['id']+'/jointed-leader',config['seed']);lean=(u-.5)*h*.75
    points=np.array([root+[0,-h*.18],root+[lean*.18,-h*.48],root+[lean*.74,-h*.79],root+[lean,-h*1.10]])
    # This colored leader is constructed independently of selected ink axes.
    pieces=[np.vstack([segment(points[0],points[1],.2),segment(points[1],points[2],-.25)[1:]]),segment(points[2],points[3],.22)]
    if far:pieces=[np.vstack([pieces[0],pieces[1][1:]])]
    out=[];b=g['branches'][1]
    for j,p in enumerate(pieces):
        tier='long' if j==0 else 'medium'
        if LineString(p).length>=3.2:out.append(make_record(site['id']+f'/U/leader-{j}',p,site,g,b,'color','U',tier,config,
            joint_chain_xy_mm=points.tolist(),local_role='shadow',generation_rule='multi-joint colored leader; unequal internodes'))
    for j in [1,2]:
        side=(-1 if (site['member_index']+j)%2 else 1);joint=points[j]
        length=(3.5+.9*u) if j==2 else (5.2+2.*u if far else 7.2+3.8*u)
        elbow=joint+[side*length*.58,-length*.19];tip=joint+[side*length,-length*(.35+.3*u)]
        p=np.vstack([segment(joint,elbow,.14*side),segment(elbow,tip,-.12*side)[1:]])
        out.append(make_record(site['id']+f'/U/lateral-{j}',p,site,g,b,'color','U','short' if j==2 else 'medium',config,
            joint_xy_mm=joint.tolist(),joint_chain_xy_mm=points.tolist(),local_role='body',
            generation_rule='lateral continuation attached at a distinct leader joint'))
        if not far:
            start=tip;end=tip+[side*(3.4+.6*u),-(1.+u)]
            out.append(make_record(site['id']+f'/U/terminal-{j}',segment(start,end,.15),site,g,b,'color','U','short',config,
                local_role='tip',generation_rule='terminal extension of an existing jointed side branch'))
    return out


def canopy_carriers(sites,graphs,config):
    """Canopy surfaces span adjacent bodies, with actual varying source depths."""
    lookup={g['body_id']:g for g in graphs};rows=[];links=[]
    for patch in sorted({s.get('patch_id',s['stand_id']) for s in sites}):
        members=[s for s in sites if s.get('patch_id',s['stand_id'])==patch]
        # Separate source-depth strata before lateral chaining; not screen-y bands.
        for band in sorted({int(s['site']['source_forward_m']//115) for s in members}):
            group=sorted([s for s in members if int(s['site']['source_forward_m']//115)==band],key=lambda s:s['root_xy_mm'][0])
            chains=[];current=[]
            for s in group:
                if current:
                    delta=np.array(s['root_xy_mm'])-current[-1]['root_xy_mm']
                    if delta[0]>13. or abs(delta[1])>6. or np.linalg.norm(delta)>15.:
                        chains.append(current);current=[]
                current.append(s)
            if current:chains.append(current)
            for ci,chain in enumerate(chains):
                # Limit carriers to four bodies. Neighbor chains may share an
                # end body, creating related layers without a single giant fill.
                for chunk in range(0,len(chain),3):
                    unit=chain[max(0,chunk-1):min(len(chain),chunk+3)];site=unit[len(unit)//2];g=lookup[site['id']];far=g['mode'].startswith('F')
                    common_height=np.median([s['height_mm'] for s in unit])*.65
                    centers=np.array([np.array(s['root_xy_mm'])+[0,-common_height] for s in unit]);qq=np.array([s['site']['source_forward_m'] for s in unit])
                    ident=f'{patch}/S/band-{band}/chain-{ci}/span-{chunk}'
                    if len(centers)==1:
                        width=(6.5 if far else 11.)
                        centers=np.array([centers[0]+[-width/2,0],centers[0]+[width/2,site['tangent_xy'][1]*width*.4]])
                        qq=np.repeat(qq,2)
                    x=centers[:,0];keep=np.r_[True,np.diff(x)>.1];centers=centers[keep];qq=qq[keep];x=centers[:,0]
                    if len(x)<2:continue
                    yy=PchipInterpolator(x,centers[:,1]);qfun=PchipInterpolator(x,qq)
                    # Three broad layers interleave two subordinate releases.
                    # Close core passes form a surface mass; outer edges stay
                    # irregular. This density budget is distinct from family R.
                    for layer,(a,b,offset,tier) in enumerate([(x[0],x[-1],-2.2,'long'),
                        (x[0]+.10*np.ptp(x),x[0]+.77*np.ptp(x),-1.15,'medium'),
                        (x[0],x[-1],0.,'long'),
                        (x[0]+.23*np.ptp(x),x[-1],1.0,'medium'),(x[0],x[-1],2.2,'long')]):
                        xx=np.linspace(a,b,max(15,int((b-a)/.4)+1));t=(xx-a)/max(b-a,1e-9)
                        chord=np.interp(xx,[x[0],x[-1]],[centers[0,1],centers[-1,1]])
                        surface=chord+np.clip(yy(xx)-chord,-1.4,1.4)
                        p=np.c_[xx,surface+offset+(.35 if far else .6)*np.sin(t*math.pi*1.5+ci*.6)]
                        if LineString(p).length<3.2:continue
                        r=make_record(ident+f'/layer-{layer}',p,site,g,g['branches'][1],'color','S',tier,config,
                            owner_id=ident,source_member_ids=[s['id'] for s in unit],local_role='shadow' if layer==0 else 'body',
                            generation_rule='shared canopy carrier across terrain-supported bodies',carrier_id=ident)
                        r['source_forward_profile_m']=qfun(xx).tolist();r['source_forward_m']=float(np.median(qfun(xx)));rows.append(r)
                    for k,s in enumerate(unit):
                        center=np.array(s['root_xy_mm'])+[0,-s['height_mm']*.83];length=3.5+1.1*phase(s['id']+'/edge',config['seed'])
                        tangent=np.array(s['tangent_xy']);p=segment(center-tangent*length*.5,center+tangent*length*.5,.22)
                        rows.append(make_record(ident+f'/edge-{k}',p,s,lookup[s['id']],lookup[s['id']]['branches'][1],'color','S','short',config,
                            owner_id=ident,local_role='tip',source_member_ids=[s['id']],generation_rule='local edge release of shared canopy'))
                    links.append(dict(id=ident,member_ids=[s['id'] for s in unit],source_q_range_m=[float(qq.min()),float(qq.max())],
                        nonplotting=True,center_xy_mm=centers.tolist()))
    return rows,links


def generate(sites,mode,family,config):
    graphs=[growth_graph(s,mode,config) for s in sites];ink=[];color=[];links=[]
    for s,g in zip(sites,graphs):
        ink+=structural_ink(s,g,family,config)
        if family=='R':color+=radial(s,g,config)
        elif family=='U':color+=jointed(s,g,config)
        elif family!='S':raise ValueError('Unknown family')
    if family=='S':color,links=canopy_carriers(sites,graphs,config)
    return graphs,ink,color,links


def q_at(r,arcs):return np.interp(arcs,arc(r['xy_mm']),r['source_forward_profile_m'])


def clip_profiled(r,gate,config):
    """Keep all source depth/width/opacity profiles aligned with raw arc space."""
    minimum=config['minimum_color_mm'] if 'palette_slot' in r else config['minimum_ink_mm']
    offset=r['source_arc_mm'][0];local={**r,'source_arc_mm':[0.,LineString(r['xy_mm']).length]}
    pieces,decision=clip_source(local,gate,minimum_mm=minimum,step_mm=.15)
    for p in pieces:
        a,b=p['source_arc_mm'];at=a+arc(p['xy_mm']);p['source_forward_profile_m']=q_at(r,at).tolist()
        p['source_forward_m']=float(np.median(p['source_forward_profile_m']));p['source_stroke_id']=r['source_stroke_id'];p['source_arc_mm']=[a+offset,b+offset]
    return pieces,decision


def visibility(rows,evidence,config):
    out=[];ledger=[]
    for r in rows:
        line=LineString(r['xy_mm']);aa=np.linspace(0,line.length,max(2,int(line.length/.4)+1));pp=np.array([line.interpolate(a).coords[0] for a in aa])
        retain,_=root_visibility(evidence,{'source_forward_m':q_at(r,aa)},pp);mean=float(np.mean(retain));strength=float(np.clip((mean-.08)/.68,0,1))
        key=r.get('carrier_id',r['owner_id'])+'/'+r['hierarchy_tier']
        probability=.23+.77*strength**.72
        if 'palette_slot' in r and phase(key+'/mist-v04',config['seed'])>probability:
            ledger.append(dict(source_id=r['id'],removed_mm=line.length,reason='locked-mist-coherent-occurrence'));continue
        def gate(xy,arcs,rec):
            ret,vis=root_visibility(evidence,{'source_forward_m':q_at(rec,arcs)},xy)
            safe=sample(evidence.protected_clearance,xy,order=0)-rec['assumed_footprint_mm']/2-1.4
            return np.minimum.reduce([safe,ret-.08,np.where(vis,1.,-1.)]),['locked-depth-matched-mist','protected-footprint','source-terrain-visibility']
        pieces,d=clip_profiled(r,gate,config)
        for p in pieces:p['mean_retention']=mean
        out+=pieces;ledger.append(d)
    return out,ledger


def vegetation_overlap(ink,color,config):
    """Only dense visible front vegetation can clip new rear vegetation."""
    owners=sorted({r['owner_id'] for r in ink+color},key=lambda own:min(min(r['source_forward_profile_m']) for r in ink+color if r['owner_id']==own))
    nearq=np.full((900,600),np.inf);out=[];ledger=[]
    for owner in owners:
        rows=[r for r in ink+color if r['owner_id']==owner];mask=np.isfinite(nearq)
        if mask.any():
            clearance=signed_clearance(mask);idx=distance_transform_edt(~mask,return_distances=False,return_indices=True);nearest_q=nearq[tuple(idx)]
        kept=[]
        for r in rows:
            if mask.any():
                def gate(xy,aa,rec):
                    behind=q_at(rec,aa)>sample(nearest_q,xy,order=0)+25.
                    return np.where(behind,sample(clearance,xy,order=0)-rec['assumed_footprint_mm']/2-.25,1.),['nearer-dense-new-vegetation']
                pieces,d=clip_profiled(r,gate,config);ledger.append(d)
            else:pieces=[r]
            kept+=pieces
        count=np.zeros((900,600),np.float32)
        for r in kept:
            if 'palette_slot' in r:count+=burn(LineString(r['xy_mm']).buffer(.6))
        core=gaussian_filter(count,.65)>=1.7
        # Conservative maximum depth ensures a mixed-depth carrier cannot hide
        # a path that may actually be in front of part of that same carrier.
        depth=max(max(r['source_forward_profile_m']) for r in rows)
        nearq[core]=np.minimum(nearq[core],depth);out+=kept
    out.sort(key=lambda r:-r['source_forward_m'])
    return [r for r in out if 'palette_slot' not in r],[r for r in out if 'palette_slot' in r],ledger


def colorize(rows,config,kind='vegetation',depth_override=None):
    out=[];knots=config['depth_knots_m'];weights=np.array(config['depth_slot_weights'],float)
    for old in rows:
        r=deepcopy(old);q=float(depth_override if depth_override is not None else r['source_forward_m'])
        if kind=='general':
            from datascape.vegetation.pictorial_families_v03 import palette_treatment
            # Exact v03 assignment policy, on the same new v04 geometry.
            v03=dict(seed=config['seed'],global_slots=['C1','C2','A5','C3','C4','D1'],depth_range_m=[800,3400],
                global_near_weights=[18,40,18,13,8,3],global_far_weights=[42,20,23,6,5,4])
            rr=palette_treatment([r],'combined',v03)[0];out.append(rr);continue
        w=np.array([np.interp(q,knots,weights[:,j]) for j in range(weights.shape[1])]);role=r.get('local_role','body');fam=r['pictorial_family']
        if role=='tip':w*=np.array([1.55,1.2,.6,.5,.1,.8,.7,1.35])
        elif role=='shadow':w*=np.array([.65,.65,1.,1.5,1.35,1.2,1.2,.2])
        if fam=='S':w[5]*=1.35
        if fam=='U':w[3]*=1.25
        atmosphere=float(np.clip(1-r.get('mean_retention',1.),0,.65));w=(1-atmosphere)*w+atmosphere*weights[2]
        # Far green mass can retain jade emphasis while excluding dark ink green.
        if q>2600 and r.get('stand_role')=='dominant':w[2]*=1.6
        w[4]=0 if q>=2600 else w[4]
        u=phase(r['source_stroke_id']+'/vegetation-slot-v04',config['seed']);j=min(len(w)-1,int(np.searchsorted(np.cumsum(w)/w.sum(),u)))
        r.update(palette_slot=config['vegetation_slots'][j],color_logic='vegetation-v04',palette_depth_m=q)
        if depth_override is not None:r['palette_depth_override_m']=depth_override
        out.append(r)
    return out


def terrain_treatment(context,color,evidence,kind,config,bounds=None):
    """Diagnostic copies only; no canonical source geometry is mutated."""
    if kind=='overlay':return deepcopy(context),dict(kind=kind,removed_mm=0.,source_records_modified=0)
    count=np.zeros((900,600),np.float32);nearq=np.full((900,600),np.inf)
    for r in color:
        mask=burn(LineString(r['xy_mm']).buffer(.6));count+=mask;nearq[mask]=np.minimum(nearq[mask],max(r['source_forward_profile_m']))
    if kind=='limited':mask=gaussian_filter(count,.7)>=3.2
    elif kind=='strong':
        shapes=[]
        for group in sorted({r['group_id'] for r in color}):
            shapes.append(unary_union([LineString(r['xy_mm']) for r in color if r['group_id']==group]).convex_hull.buffer(1.5))
        mask=burn(unary_union(shapes))
    else:raise ValueError('Unknown terrain diagnostic')
    region=box(*bounds) if bounds is not None else box(0,0,600,900)
    mask&=burn(region)
    clear=signed_clearance(mask);idx=distance_transform_edt(~np.isfinite(nearq),return_distances=False,return_indices=True);nearest_q=nearq[tuple(idx)]
    total=sum(LineString(r['xy_mm']).intersection(region).length for r in context);removed=0.;out=[]
    for r in context:
        if r['layer']=='D':out.append(deepcopy(r));continue
        def gate(xy,aa,rec):
            behind=sample(evidence.depth,xy)>=sample(nearest_q,xy,order=0)-25.
            return np.where(behind,sample(clear,xy,order=0)-.4,1.),['diagnostic-'+kind+'-core-copy']
        pieces,d=clip_source(r,gate,minimum_mm=2.8,step_mm=.25)
        lost=LineString(r['xy_mm']).intersection(region).length-sum(LineString(p['xy_mm']).intersection(region).length for p in pieces)
        if kind=='limited' and removed+lost>total*.08:pieces=[deepcopy(r)];lost=0.
        out+=pieces;removed+=max(0.,lost)
    return out,dict(kind=kind,removed_mm=removed,fraction_removed=removed/max(1.,total),source_records_modified=0,
        diagnostic_copies_only=True,accepted_default=False,measurement_bounds_mm=list(region.bounds))
