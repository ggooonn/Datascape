"""Three foliage construction families on shared, depth-aware growth graphs.

R delegates unchanged to v02's radial generator. S samples open arcs from
curved canopy surfaces. U builds jointed shoot axes and interior offshoots.
They share terrain evidence and structural ink, not a rotated fan generator.
"""
from copy import deepcopy
import math
import numpy as np
from scipy.ndimage import gaussian_filter
from shapely.geometry import LineString
from datascape.strokes.vector import sample,phase
from datascape.integration.visibility import clip_source,burn,signed_clearance
from datascape.vegetation.tree_growth import segment
from datascape.vegetation.structural_mid_far_v02 import (growth_graph,ink_from_graph,
    color_from_graph,record,apply_visibility)


def supported_root(evidence,x,target_q,y_hint,y_window):
    yy=np.arange(y_window[0]+.5,y_window[1]-.5,.20);p=np.c_[np.full(len(yy),x),yy]
    v=sample(evidence.depth,p)-target_q;occ=sample(evidence.occupied.astype(float),p,order=0)>.5
    ids=np.flatnonzero((v[:-1]*v[1:]<=0)&occ[:-1]&occ[1:])
    crossings=[yy[i]+.2*(-v[i])/(v[i+1]-v[i]) for i in ids if v[i]!=v[i+1]]
    if not crossings:raise ValueError('No measured terrain contact at requested x/q; never extrapolate')
    y=min(crossings,key=lambda value:abs(value-y_hint));return np.array([float(x),float(y)])


def measured_tangent(evidence,p,fallback):
    offsets=np.array([[.5,0],[-.5,0],[0,.5],[0,-.5]])
    q=sample(evidence.depth,p+offsets);dx=q[0]-q[1];dy=q[2]-q[3]
    if abs(dy)<1e-5:return fallback
    v=np.array([1.,-dx/dy]);v/=np.linalg.norm(v)
    return v.tolist()


def arrange(original,kind,region,evidence,config):
    """Authored support patches in canvas-x/source-q space; no y depth ranks."""
    sites=deepcopy(original)
    if kind=='linear':return sites
    offsets=config['depth_offsets_m'];mid_q=np.median([r['site']['source_forward_m'] for r in original])
    for i,r in enumerate(sites):
        q=r['site']['source_forward_m']+offsets[i%len(offsets)]*(.75 if region['mode'].startswith('F') else 1.)
        x=r['root_xy_mm'][0]+(i%3-1)*2.1
        p=supported_root(evidence,x,q,r['root_xy_mm'][1],region['y_search_mm'])
        r['root_xy_mm']=p.tolist();r['site']=evidence.point(p);r['placement_variant']=kind
        r['tangent_xy']=measured_tangent(evidence,p,r['tangent_xy'])
        r['source_v02_body_id']=r['id'];r['id']=r['id'].replace('v02/','v03/',1)
        r['stand_id']=r['stand_id'].replace('v02/','v03/',1)
        r['subcluster_id']=r['stand_id']+('/rear' if q>mid_q else '/front')
    if kind=='expanded':
        # Unequal neighboring lobes occupy different source-depth surfaces.
        # Extra roots are attached by measured crossings, never y offsets.
        parents=[r for r in sites if r['stand_role']=='dominant']
        for i in range(region['expanded_extra']):
            parent=parents[i%len(parents)];r=deepcopy(parent)
            side=-1 if i%3 else 1
            x=float(np.clip(parent['root_xy_mm'][0]+side*(9+3.5*(i%4)),*region['x_range_mm']))
            q=float(parent['site']['source_forward_m']+region['expanded_depth_m'][i%2]*(.62+.22*(i%3)))
            try:p=supported_root(evidence,x,q,parent['root_xy_mm'][1],region['y_search_mm'])
            except ValueError:continue
            r.update(id=parent['id']+f'/subcluster-{i}',root_xy_mm=p.tolist(),site=evidence.point(p),
                height_mm=parent['height_mm']*(.53+.10*(i%3)),member_index=i,
                stand_role='extension',subcluster_id=parent['stand_id']+f'/lobe-{i%3}',
                source_v02_body_id=parent['source_v02_body_id'])
            r['tangent_xy']=measured_tangent(evidence,p,r['tangent_xy'])
            sites.append(r)
    return sites


def larger_sites(sites,variant):
    result=deepcopy(sites)
    if variant=='small':return result
    candidates=sorted([r for r in result if r['stand_role']=='dominant'],key=lambda r:r['site']['source_forward_m'])
    candidates[0]['height_mm']=45. if variant=='one' else 55.
    candidates[0]['scale_role']='occasional structural focal'
    if variant=='varied':
        other=next(r for r in result if r['stand_index']==0 and r['member_index']==1)
        other['height_mm']=36.;other['scale_role']='secondary structural tree'
    return result


def family_record(ident,p,site,g,b,family,config,**meta):
    r=record(ident,p,site,g,b,'color',config)
    r.update(pictorial_family=family,generation_rule=meta.pop('generation_rule'),
        palette_slot='C2',color_kind='vegetation',foliage_origin_xy_mm=b['crown_node_xy_mm'],
        ray_index=meta.pop('episode',0),**meta)
    return r


def surface_color(site,g,config):
    """Offset surface sections, with staggered open ends and coherent curvature.

    Their starts are spread across a canopy lens, not projected from one pivot.
    The measured terrain tangent and growth branch jointly orient the surface.
    """
    far=g['mode'].startswith('F');rows=[]
    tangent=np.array(site['tangent_xy'],float);tangent/=np.linalg.norm(tangent)
    if tangent[0]<0:tangent*=-1
    for j,b in enumerate(g['branches']):
        center=np.array(b['crown_node_xy_mm']);d=np.array(b['direction_xy'])
        if d[0]<0:d*=-1
        axis=.72*tangent+.28*d;axis/=np.linalg.norm(axis);normal=np.array([-axis[1],axis[0]])
        u=phase(b['id']+'/surface',config['seed'])
        span=(5.3 if far else 8.7)+(.9 if far else 3.0)*u
        n=(3 if u<.65 else 4) if far else 3+int(u*2)+(site['height_mm']>35)
        bend=(.4+.7*u)*(-.65 if phase(b['id']+'/surface-bend',config['seed'])<.26 else 1.)
        for k in range(n):
            level=(k-(n-1)/2)/(max(1,n-1)/2)
            level+=.12*math.sin(k*2.1+u*5)
            half=span*.5*math.sqrt(max(.38,1-.58*level**2))*(.86+.14*math.cos(k*1.8+u*4))
            shift=axis*(.6*math.sin(j+k*1.7+u*3))
            c=center+normal*(level*(1.4 if far else 2.7))+shift
            t=np.linspace(-1,1,19)
            p=c+t[:,None]*axis*half+normal[None,:]*(bend*(1-t*t)+.25*level*t)[:,None]
            # Unequal end releases are geometric; they do not add tiny dots.
            if (k+j)%4==0:p=p[2:]
            if LineString(p).length<config['minimum_color_mm']:continue
            rows.append(family_record(site['id']+f'/{g["mode"]}/S/surface-{j}/section-{k}',p,site,g,b,'S',config,
                generation_rule='open section of curved canopy surface',surface_id=b['id']+'/surface',
                surface_center_xy_mm=center.tolist(),surface_axis_xy=axis.tolist(),surface_level=float(level),
                local_role='core' if abs(level)<.6 else 'edge',episode=k))
    return rows


def shoot_color(site,g,config):
    """Bent shoot axes with interior offshoots; not an angularly rotated fan."""
    far=g['mode'].startswith('F');rows=[]
    for j,b in enumerate(g['branches']):
        source=np.asarray(b['xy_mm'])
        unit=phase(b['id']+'/shoot-count',config['seed'])
        n=(1+int(unit>.82)) if far else 1+int(unit*2.6)
        for k in range(n):
            u=phase(b['id']+f'/shoot-{k}',config['seed'])
            # Related but unequal origins spread along a supporting member.
            at=min(len(source)-1,max(0,int((.22+.43*(k+.5)/n)*(len(source)-1))))
            start=source[at]+np.array([(k-(n-1)/2)*.8,-.25])
            height=(4.8 if far else 6.)+(2.8 if far else 5.)*u
            drift=(-.48+.96*u)*height+site['tangent_xy'][1]*.6
            joint=start+[drift*.35,-height*(.35+.30*u)]
            tip=start+[drift,-height]
            p=np.vstack([segment(start,joint,.12),segment(joint,tip,-.10)[1:]])
            sid=b['id']+f'/shoot-{k}'
            rows.append(family_record(site['id']+f'/{g["mode"]}/U/{j}-{k}/axis',p,site,g,b,'U',config,
                generation_rule='jointed ascending shoot',shoot_id=sid,shoot_role='axis',
                joint_xy_mm=joint.tolist(),local_role='core' if k==1 else 'edge',episode=k))
            # Offshoot starts at the internal joint of its own axis. The
            # divided topology survives even at distant minimum length.
            side=-1 if phase(sid+'/side',config['seed'])<.5 else 1
            length=config['minimum_color_mm']+.2+(1.6 if far else 2.8)*u
            vec=np.array([side*(.85+.38*u),-(.20+.65*phase(sid+'/rise',config['seed']))]);vec/=np.linalg.norm(vec)
            q=segment(joint,joint+vec*length,side*.15)
            rows.append(family_record(site['id']+f'/{g["mode"]}/U/{j}-{k}/offshoot',q,site,g,b,'U',config,
                generation_rule='offshoot from interior shoot joint',shoot_id=sid,shoot_role='offshoot',
                joint_xy_mm=joint.tolist(),local_role='core',episode=k+n))
    return rows


def generate(sites,mode,family,config):
    graphs=[];ink=[];color=[]
    for site in sites:
        g=growth_graph(site,mode,config);graphs.append(g);ink.extend(ink_from_graph(site,g,config))
        if family=='R':
            cc=color_from_graph(site,g,config)
            for r in cc:r.update(pictorial_family='R',local_role=r.get('foliage_state','edge'))
        elif family=='S':cc=surface_color(site,g,config)
        elif family=='U':cc=shoot_color(site,g,config)
        else:raise ValueError('Unknown pictorial family')
        color.extend(cc)
    for r in ink:r['pictorial_family']=family
    return graphs,ink,color


def depth_overlap(ink,color,config):
    """New-object overlap only; canonical terrain is never an occlusion receiver.

    Near objects supply dense cores from actual already-visible foliage passes,
    not convex crown silhouettes. Order is source q, with a 25-m uncertainty
    band; no screen-y rank or invented depth offset is introduced.
    """
    owners=sorted({r['owner_id'] for r in ink+color},key=lambda owner:min(r['source_forward_m'] for r in ink+color if r['owner_id']==owner))
    outi=[];outc=[];cores=[];ledger=[]
    for owner in owners:
        rows=[r for r in ink+color if r['owner_id']==owner];q=rows[0]['source_forward_m'];near=[m for depth,m in cores if depth<q-25]
        if near:clear=signed_clearance(np.logical_or.reduce(near))
        retained=[]
        for r in rows:
            if near:
                def gate(xy,arc,rec):
                    return sample(clear,xy,order=0)-rec['assumed_footprint_mm']/2-.25,['nearer-visible-vegetation-core']
                offset=r['source_arc_mm'][0]
                local={**r,'source_arc_mm':[0.,LineString(r['xy_mm']).length]}
                pieces,decision=clip_source(local,gate,minimum_mm=config['minimum_color_mm'] if 'palette_slot' in r else config['minimum_ink_mm'],step_mm=.15)
                for p in pieces:
                    p['source_arc_mm']=[a+offset for a in p['source_arc_mm']];p['source_stroke_id']=r['source_stroke_id']
                    p['source_forward_profile_m']=[q]*len(p['xy_mm'])
                ledger.append(dict(owner_id=owner,source_id=r['id'],source_forward_m=q,
                    removed_mm=decision['removed_mm'],nearer_cores=len(near)))
            else:pieces=[r]
            retained.extend(pieces)
        owner_colors=[r for r in retained if 'palette_slot' in r]
        count=np.zeros((900,600),np.float32)
        for r in owner_colors:count+=burn(LineString(r['xy_mm']).buffer(config['color_footprint_mm']/2))
        # Two or more locally overlapping real strokes, smoothed below 1 mm.
        core=gaussian_filter(count,.65)>=1.7
        if core.any():cores.append((q,core))
        outi.extend(r for r in retained if 'palette_slot' not in r);outc.extend(owner_colors)
    outc.sort(key=lambda r:-r['source_forward_m']);outi.sort(key=lambda r:-r['source_forward_m'])
    return outi,outc,ledger


def palette_treatment(rows,treatment,config):
    """Perceived gradients from slot frequencies; no RGB or HEX interpolation."""
    slots=config['global_slots'];lo,hi=config['depth_range_m'];out=[]
    for old in rows:
        r=deepcopy(old);f=np.clip((r['source_forward_m']-lo)/(hi-lo),0,1)
        near=np.array(config['global_near_weights'],float);far=np.array(config['global_far_weights'],float)
        global_w=(1-f)*near+f*far
        # A selected dominant visible stand retains distant chromatic emphasis.
        if r.get('stand_role')=='dominant' and f>.7:
            global_w[3:5]*=2.0
        role=r.get('local_role',r.get('foliage_state','edge'));recipe=r.get('stand_index',0)%3
        local=np.ones(len(slots))
        if role=='core':local=np.array([.35,1.5,1.5,1.6,1.2,.35])
        else:local=np.array([1.7,1.0,.7,.4,.4,1.15])
        local[(recipe+1)%len(slots)]*=1.35
        if treatment=='local':weights=(near+far)/2*local
        elif treatment=='global':weights=global_w
        elif treatment=='combined':weights=global_w*local
        else:raise ValueError('Unknown color treatment')
        key=r['growth_branch_id']+'/'+str(r.get('ray_index',0))
        u=phase(key+'/slot-v03',config['seed']);cdf=np.cumsum(weights)/weights.sum()
        r.update(palette_slot=slots[min(len(slots)-1,int(np.searchsorted(cdf,u)))],color_treatment=treatment)
        out.append(r)
    return out


def preview(rows,alpha):
    return [{**r,'preview_opacity':alpha,'opacity_profile':[alpha]*len(r['xy_mm'])} for r in rows]
