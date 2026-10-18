"""Three scale tiers: terrain-supported forest ribbons, groves and micro marks.

Macro fields are generated directly in terrain x/q space, not by repeating
small trees. Taps are typed experimental contacts, never zero-length lines
silently passed through continuous-stroke length validation.
"""
from copy import deepcopy
import math
import numpy as np
from shapely.geometry import LineString
from datascape.strokes.vector import sample,phase,resample
from datascape.vegetation.mid_far import root_visibility
from datascape.vegetation.tree_growth import segment
from datascape.vegetation.territorial_mid_far_v04 import (
    generate as medium_generate,visibility,colorize,arc)


def density(u,v):
    lobes=max(math.exp(-((u-.19)/.22)**2-((v+.12)/.82)**2),
        .98*math.exp(-((u-.57)/.23)**2-((v-.12)/.86)**2),
        .81*math.exp(-((u-.86)/.19)**2-((v+.18)/.70)**2))
    neck=.19*math.exp(-(v/.75)**2)
    opening=1-.97*math.exp(-((u-.405)/.043)**2-((v-.30)/.35)**2)
    return float(np.clip((lobes+neck)*opening,0,1))


class Ground:
    """Cache occupied vertical samples; solve measured crossings, not screen-y depth."""
    def __init__(self,evidence,region):
        self.e=evidence;self.region=region;self.cache={};self.occ=evidence.occupied.astype(float)
        self.yy=np.arange(region['y_search_mm'][0]+.5,region['y_search_mm'][1]-.5,.25)

    def point(self,x,q,hint=None):
        key=round(float(x),7)
        if key not in self.cache:
            p=np.c_[np.full(len(self.yy),x),self.yy];self.cache[key]=(sample(self.e.depth,p),sample(self.occ,p,order=0)>.5)
        values,occ=self.cache[key];v=values-q
        ids=np.flatnonzero((v[:-1]*v[1:]<=0)&occ[:-1]&occ[1:])
        ys=[self.yy[i]+.25*(-v[i])/(v[i+1]-v[i]) for i in ids if v[i]!=v[i+1]]
        if not ys:return None
        y=min(ys,key=lambda a:abs(a-(hint if hint is not None else np.mean(self.yy))))
        return np.array([float(x),float(y)])

    def uv(self,u,v,hint=None):
        r=self.region;x=r['knots_x_mm'][0]+u*(r['knots_x_mm'][-1]-r['knots_x_mm'][0])
        q=np.interp(x,r['knots_x_mm'],r['knots_q_m'])+v*r['half_depth_m']
        return self.point(x,q,hint)


def record(ident,xy,q,tier,region,config,**extra):
    p=np.asarray(xy,float);qq=np.broadcast_to(np.asarray(q,float),len(p));length=float(LineString(p).length) if len(p)>1 else 0.
    r=dict(id=ident,source_stroke_id=ident,source_arc_mm=[0.,length],xy_mm=p.tolist(),
        source_forward_profile_m=qq.tolist(),source_forward_m=float(np.median(qq)),
        owner_id=f'v05/{region}/{tier}',group_id=f'v05/{region}',growth_branch_id=ident,
        scale_tier=tier,region=region,primitive='stroke',hierarchy_tier='field' if tier=='macro' else 'micro',
        layer='vegetation-color',material_channel='vegetation-foliage',palette_slot='C2',pictorial_family='S',
        local_role='body',stand_role='dominant',assumed_footprint_mm=config['color_footprint_mm'],
        width_mm=1.1 if tier=='macro' else .65,preview_opacity=config['field_alpha'],
        physical_plotting_validated=False,source_ancestry='derived x/source-q terrain field; no repeated tree specimens',
        contact_precision='1-mm float32 raster interpolation; no exact triangle or observed vegetation claim')
    r.update(extra);return r


def macro_field(cid,ground,evidence,config):
    region=ground.region;rows=[];supports=[];seed=config['seed'];n=config['field_rows']
    xx=np.arange(region['knots_x_mm'][0],region['knots_x_mm'][-1]+.01,1.1)
    for j in range(n):
        v=-.94+1.88*j/(n-1)+.012*math.sin(j*2.3);points=[];qs=[];weights=[];last=None
        for x in xx:
            u=(x-xx[0])/(xx[-1]-xx[0])
            flow_v=v+.14*math.sin(u*17+j*.67)*max(0.,1-abs(v))
            q=np.interp(x,region['knots_x_mm'],region['knots_q_m'])+flow_v*region['half_depth_m']
            p=ground.point(x,q,last)
            d=density(u,v)
            # Dense interiors form long related runs; sparse margins dissolve
            # in coherent openings, not independent per-pixel speckle.
            keep=d>.24+.09*phase(f'v05/{cid}/row-{j}',seed)
            keep&=d>.65 or math.sin(u*28+v*4+math.sin(u*9)*.8)>-.35
            if p is not None and last is not None and abs(p[1]-last)>7.:keep=False
            if p is None:points.append(None);qs.append(q);weights.append(d);last=None;continue
            last=p[1];height=region['height_mm']*(.62+.18*math.sin(u*8+.5)+.10*d)
            crown=p+[.3*math.sin(j+u*10),-height+.30*math.sin(u*24+j*.6)]
            points.append(crown if keep else None);qs.append(float(sample(evidence.depth,p.reshape(1,2))[0]));weights.append(d)
        starts=[];run=[]
        for k,p in enumerate(points+[None]):
            if p is not None:run.append(k)
            elif run:starts.append(run);run=[]
        for run_index,run in enumerate(starts):
            # Long carriers are bounded for brush travel. Shared continuation
            # is intentional; no broad polygon fill is exported.
            primary=j%4==0;span=29 if primary else [8,12,16][j%3]
            for part,start in enumerate(range(0,len(run)-1,span)):
                idx=run[start:min(len(run),start+span+(1 if primary else 0))]
                if len(idx)<4:continue
                p=np.array([points[k] for k in idx])
                if not primary:
                    # Meso foliage plates rise out of the terrain flow. Their
                    # different reach and bow interrupt parallel ground hatching
                    # while the same low-frequency field still binds the mass.
                    t=np.linspace(0,1,len(p));direction=p[-1]-p[0];direction/=max(np.linalg.norm(direction),1e-9)
                    normal=np.array([-direction[1],direction[0]])
                    rise=(2.2 if cid=='M' else 1.4)*(1+.45*math.sin(j*.7+u*8))
                    p-=normal[None,:]*(rise*np.sin(np.pi*t)+rise*.55*(t-.5))[:,None]
                length=LineString(p).length
                if length<config['minimum_color_mm']:continue
                d=float(np.mean([weights[k] for k in idx]));q=[qs[k] for k in idx]
                ident=f'v05/{cid}/field/row-{j}/run-{run_index}/part-{part}'
                rows.append(record(ident,p,q,'macro',cid,config,carrier_id=f'v05/{cid}/field/row-{j}',
                    field_density=d,field_v=float(v),local_role='shadow' if d>.68 else 'body',
                    generation_rule='long field connection' if primary else 'rising meso foliage plate within shared forest field'))
                supports.append(dict(id=ident,source_q_range_m=[min(q),max(q)],field_density=d,nonplotting=True))
    # Sparse outward edge releases give the continuous field a crown boundary;
    # they are field accents, not a tree repeated at every sample.
    for j,u in enumerate(np.linspace(.07,.95,22)):
        v=-.60+.12*math.sin(u*11);p=ground.uv(u,v)
        if p is None or density(u,v)<.45:continue
        center=p+[0,-region['height_mm']*.84];q=float(sample(evidence.depth,p.reshape(1,2))[0]);length=4.3+(2.4 if cid=='M' else .9)*phase(f'v05/{cid}/edge-{j}',seed)
        for side in [-1,1]:
            end=center+[side*length*.65,-length*.65]
            rows.append(record(f'v05/{cid}/field-edge-{j}/{side}',segment(center,end,side*.3),q,'macro',cid,config,
                local_role='tip',field_density=density(u,v),generation_rule='selective outward forest-edge release'))
    visible,ledger=visibility(rows,evidence,config);visible=colorize(visible,config)
    for r in visible:
        r['preview_opacity']=config['field_alpha'];r['opacity_profile']=[config['field_alpha']]*len(r['xy_mm'])
        if r['field_density']>.68:
            u=phase(r['source_stroke_id']+'/core-material',seed)
            r['palette_slot']=('C4' if u<.55 else 'C2') if r['source_forward_m']<2200 else ('A5' if u<.68 else 'C3' if u<.82 else 'C1')
            r['color_logic']='v05-coherent-forest-core, existing palette slots'
    return rows,visible,ledger,supports


def micro_field(cid,ground,evidence,config):
    raw=[];visible=[];ledger=[];seed=config['seed'];region=ground.region
    for j in range(config['micro_groups']):
        u=(j*.61803398875+.07)%1;v=(((j*.41421356237+.31)%1)*2-1)*1.03
        d=density(u,v)
        if d<.16 or phase(f'v05/{cid}/micro-{j}/occ',seed)>.21+.74*d:continue
        p=ground.uv(u,v)
        if p is None:continue
        dx=.5;px=ground.point(p[0]+dx,np.interp(p[0],region['knots_x_mm'],region['knots_q_m'])+v*region['half_depth_m'],p[1])
        tangent=np.array([1.,0.]) if px is None else px-p;tangent/=max(np.linalg.norm(tangent),1e-9);normal=np.array([-tangent[1],tangent[0]])
        group=f'v05/{cid}/micro-{j}';kind='compact-stroke' if j%4==0 else 'tap'
        if kind=='tap':
            for k in range(2+j%3):
                point=p+tangent*(k-1)*1.12+normal*(.30*math.sin(k*2+j))
                q=float(sample(evidence.depth,point.reshape(1,2))[0])
                r=record(group+f'/tap-{k}',[point],q,'micro',cid,config,primitive='tap',diameter_mm=config['tap_diameter_mm'],
                    contact_group=group,field_density=d,local_role='shadow' if d>.65 else 'body',
                    assumed_footprint_mm=1.2,requires_contact_calibration=True,generation_rule='clustered experimental pigment contacts')
                raw.append(r)
                ret,vis=root_visibility(evidence,r,point.reshape(1,2));safe=sample(evidence.protected_clearance,point.reshape(1,2),order=0)[0]>2.0
                keep=safe and vis[0] and ret[0]>.08 and phase(group+'/mist',seed)<.2+.8*ret[0]
                if keep:r=deepcopy(r);r['mean_retention']=float(ret[0]);visible.append(r)
                ledger.append(dict(source_id=r['id'],kept=bool(keep),primitive='tap'))
        else:
            # A compact connected tuft retains the 3.2-mm continuous path floor.
            # Its tiny envelope will merge under a wider brush, intentionally.
            local=np.array([[0,0],[1.2,.45],[.25,.85],[1.55,1.05]])
            points=p+local[:,0,None]*tangent+local[:,1,None]*normal
            q=sample(evidence.depth,points);r=record(group+'/tuft',points,q,'micro',cid,config,
                carrier_id=group,field_density=d,local_role='tip',requires_contact_calibration=False,
                generation_rule='compact connected ground tuft, not a sub-floor dash')
            raw.append(r);vv,ll=visibility([r],evidence,config);visible+=vv;ledger+=ll
    visible=colorize(visible,config)
    for r in visible:
        alpha=config['tap_alpha'] if r['primitive']=='tap' else config['field_alpha']
        r['preview_opacity']=alpha;r['opacity_profile']=[alpha]*len(r['xy_mm'])
        if r['field_density']>.6:r['palette_slot']='C4' if r['source_forward_m']<2200 else 'A5'
    return raw,visible,ledger


def medium_grove(cid,sites,evidence,config):
    chosen=[deepcopy(s) for s in sites if s['member_index']%8==1 and s['stand_index']<4]
    graphs,ri,rc,links=medium_generate(chosen,'M2' if cid=='M' else 'F2','U',config)
    i,li=visibility(ri,evidence,config);c,lc=visibility(rc,evidence,config);c=colorize(c,config)
    for r in i+c:r.update(scale_tier='medium',region=cid,primitive='stroke')
    for r in c:r.update(preview_opacity=config['field_alpha'],opacity_profile=[config['field_alpha']]*len(r['xy_mm']))
    return chosen,ri,rc,i,c,li+lc


def assemble(macro,micro,medium,variant):
    # Medium geometry is identical in A/B/C. C retains all of A's field, adding
    # a strict subset of B's fringe texture rather than filling every gap.
    out=deepcopy(medium)
    if variant in ['A','C']:out+=deepcopy(macro)
    if variant=='B':out+=deepcopy(micro)
    if variant=='C':out+=deepcopy([r for r in micro if r['field_density']<.54])
    return out
