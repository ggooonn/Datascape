"""Growth-first small vegetation, independent of the accepted foreground catalog.

Reuses the accepted tree_growth.segment primitive and P/B/U structural roles,
not completed foreground specimens. A common terrain-attached growth graph
generates restrained structural ink and independent outward foliage color.
All coordinates are actual canvas mm. No camera, terrain or catalog is changed.
"""
from copy import deepcopy
import math
import numpy as np
from shapely.geometry import LineString
from shapely.ops import substring
from datascape.vegetation.tree_growth import segment
from datascape.vegetation.mid_far import root_visibility, sha_file, digest
from datascape.strokes.vector import sample, resample, phase
from datascape.integration.visibility import clip_source


def seed_value(identity,config):
    return phase(identity,config['seed'])


def terrain_guide(scene,evidence):
    """Follow an actual saved q contour; do not extrapolate unsupported arcs.

    The previous y is used only to choose among multiple measured crossings.
    A missing or discontinuous crossing rejects the guide, rather than joining
    unrelated terrain. This is reduced-precision raster evidence, not a mesh.
    """
    xmin,xmax=scene['guide_x_mm'];ymin,ymax=scene['guide_y_window_mm']
    xx=np.linspace(xmin,xmax,int((xmax-xmin)/.5)+1)
    points=[];last=None
    for x in xx:
        yy=np.arange(ymin+.5,ymax-.5,.25);probe=np.c_[np.full(len(yy),x),yy]
        value=sample(evidence.depth,probe)-scene['source_q_m']
        occupied=sample(evidence.occupied.astype(float),probe,order=0)>.5
        ids=np.flatnonzero((value[:-1]*value[1:]<=0)&occupied[:-1]&occupied[1:])
        if not len(ids):raise ValueError(f'Unsupported guide crossing at {scene["id"]}/{x}')
        choices=[yy[i]+.25*(-value[i])/(value[i+1]-value[i]) for i in ids if value[i]!=value[i+1]]
        y=min(choices,key=lambda y:abs(y-(last if last is not None else (ymin+ymax)/2)))
        if last is not None and abs(y-last)>5:
            raise ValueError('Discontinuous terrain guide; split the scene instead')
        points.append([float(x),float(y)]);last=y
    return dict(id='v02/nonplotting/q-guide/'+scene['id'],xy_mm=points,
                source_forward_m=scene['source_q_m'],evidence='actual saved F2 raster q crossing',
                nonplotting=True,exact_mesh_contact=False)


def body_sites(scene,guide,evidence,config):
    """Unequal related stands along one supported terrain sequence.

    Three authored growth episodes have differing size, density and gaps.
    Roots sit on the measured contour; no random screen scatter is used.
    """
    line=LineString(guide['xy_mm']);roots=[]
    for gi,g in enumerate(scene['groups']):
        a,b=g['u'];count=g['count']
        for j in range(count):
            ident=f'v02/{scene["id"]}/stand-{gi}/body-{j}'
            t=(j+.5)/count
            # Correlated crowding toward an unequal stand core; stable across
            # modes and seeds. Small variation is subsidiary to the scaffold.
            t=.5+.5*np.sign(t-.5)*abs(2*t-1)**1.2
            u=a+(b-a)*t
            p=np.asarray(line.interpolate(line.length*u).coords[0])
            at=line.length*u;lo=max(0,at-1.2);hi=min(line.length,at+1.2)
            tangent=np.array(line.interpolate(hi).coords[0])-np.array(line.interpolate(lo).coords[0]);tangent/=np.linalg.norm(tangent)
            q=seed_value(ident,config)
            core=math.sin(math.pi*(j+.7)/(count+.4))
            h=g['height_mm']*(.52+.58*max(0,core))*(.88+.24*q)
            roots.append(dict(id=ident,stand_id=f'v02/{scene["id"]}/stand-{gi}',
                stand_index=gi,stand_role=g['role'],member_index=j,member_count=count,
                root_xy_mm=p.tolist(),guide_u=float(u),guide_source_id=guide['id'],
                tangent_xy=tangent.tolist(),height_mm=float(h),
                form=['B','U','B','P','B'][j%5],site=evidence.point(p)))
    for k,spec in enumerate(scene.get('relays',[])):
        u=spec['u'];p=np.asarray(line.interpolate(line.length*u).coords[0]);at=line.length*u
        tangent=np.array(line.interpolate(min(line.length,at+1)).coords[0])-np.array(line.interpolate(max(0,at-1)).coords[0]);tangent/=np.linalg.norm(tangent)
        roots.append(dict(id=f'v02/{scene["id"]}/relay-{k}',stand_id=f'v02/{scene["id"]}/relay-{k}',stand_index=3+k,
            stand_role='relay',member_index=k,member_count=1,root_xy_mm=p.tolist(),guide_u=u,
            guide_source_id=guide['id'],tangent_xy=tangent.tolist(),height_mm=spec['height_mm'],form='U',site=evidence.point(p)))
    return sorted(roots,key=lambda r:r['guide_u'])


def growth_graph(site,mode,config):
    """Reduced branching hierarchy built natively at its requested mm size."""
    far=mode.startswith('F');shrub=mode=='M3'
    base=np.array(site['root_xy_mm']);h=site['height_mm']
    if shrub:h*=.52
    if mode=='F3':h*=.62
    elif mode=='F2':h*=.78
    ident=site['id'];u=seed_value(ident+'/posture',config)
    slope=np.clip(site['tangent_xy'][1],-.6,.6)
    lean=(-.33+.66*u)+slope*.18
    apex=base+[h*lean,-h*(.68 if shrub else .83)]
    elbow=base+[h*lean*.24,-h*.39]
    axis=np.vstack([segment(base,elbow,h*.018),segment(elbow,apex,-h*.014)[1:]])
    branches=[];n=3 if not far else 2
    if mode in ('M2','M3','F2','F3') and site['member_index']%3==1:n+=1
    if site['stand_role']=='relay':n=2
    for j in range(n):
        side=(-1 if (j+site['member_index'])%2 else 1)
        f=.38+.43*j/max(n-1,1)
        source=axis[int(f*(len(axis)-1))]
        r=seed_value(ident+f'/branch-{j}',config)
        reach=h*(.24+.14*r)*(1.25 if shrub else 1.)
        rise=reach*(.35+.70*seed_value(ident+f'/rise-{j}',config))
        if site['form']=='P':rise*=.55;reach*=1.12
        elif site['form']=='U':rise*=.75
        end=source+[side*reach,-rise]
        bend=source+(end-source)*[.55,.40]
        path=np.vstack([segment(source,bend,side*.13),segment(bend,end,-side*.13)[1:]])
        direction=(end-bend)/np.linalg.norm(end-bend)
        branches.append(dict(id=ident+f'/branch-{j}',parent_axis_id=ident+'/axis',
            origin_xy_mm=source.tolist(),crown_node_xy_mm=end.tolist(),
            direction_xy=direction.tolist(),xy_mm=path.tolist(),
            role='dominant' if j==1 else 'subordinate',order=j,side=side))
    direction=(axis[-1]-axis[-2]);direction/=np.linalg.norm(direction)
    branches.append(dict(id=ident+'/apex',parent_axis_id=ident+'/axis',
        origin_xy_mm=axis[-max(2,len(axis)//3)].tolist(),crown_node_xy_mm=apex.tolist(),
        direction_xy=direction.tolist(),xy_mm=axis[-max(2,len(axis)//3):].tolist(),
        role='terminal',order=n,side=1))
    return dict(id=ident+'/growth/'+mode,body_id=ident,stand_id=site['stand_id'],mode=mode,
        root_xy_mm=base.tolist(),axis_id=ident+'/axis',axis_xy_mm=axis.tolist(),branches=branches,
        nominal_height_mm=site['height_mm'],scaffold_height_mm=h,
        form_role=site['form'],site=site['site'],root_guide_u=site['guide_u'],
        origin='new reduced branching graph using accepted segment primitive; no scaled finished tree')


def record(identity,points,site,graph,branch,channel,config):
    color=channel=='color';p=np.asarray(points,float)
    return dict(id=identity,xy_mm=p.tolist(),layer='vegetation-color' if color else 'derived-vegetation',
        material_channel='growth-foliage-color' if color else 'growth-structure-ink',
        source_stroke_id=identity,source_arc_mm=[0.,float(LineString(p).length)],
        owner_id=site['id'],group_id=site['stand_id'],growth_graph_id=graph['id'],
        growth_branch_id=branch['id'] if branch else graph['axis_id'],
        unit_id=(branch['id'] if branch else graph['axis_id']),
        grammar_part='outward-foliage' if color else 'growth-origin',
        representation=graph['mode'],source_forward_m=site['site']['source_forward_m'],
        source_site=site['site'],root_xy_mm=site['root_xy_mm'],
        depth_provider='saved-F2-1mm-raster-float32',guide_source_id=site['guide_source_id'],
        physical_plotting_validated=False,pressure_calibrated=False,
        assumed_footprint_mm=config['color_footprint_mm'] if color else config['ink_footprint_mm'],
        width_mm=1.05 if color else .30,preview_opacity=(.46 if graph['mode'].startswith('F') else .58) if color else .88,
        opacity=1.,origin_kind='new-derived-vegetation',
        stand_role=site['stand_role'],stand_index=site['stand_index'],guide_u=site['guide_u'],
        source_ancestry='v10 tree_growth.segment primitive and P/B/U structural tendencies; new v02 reduced graph')


def ink_from_graph(site,graph,config):
    mode=graph['mode'];ident=site['id'];axis=LineString(graph['axis_xy_mm']);out=[]
    if mode=='M1':fraction=1.
    elif mode=='M2':fraction=.95 if site['member_index']%3==1 else .54
    elif mode=='M3':fraction=.67 if site['member_index']%3==1 else .40
    elif mode=='F1':fraction=.78
    elif mode=='F2':
        fraction=.85 if site['member_index']%3==1 else .60 if site['stand_role']=='dominant' and site['member_index']%2==0 else 0.
    else:
        # Keep a longer existing section of selected tiny axes so the physical
        # floor does not accidentally erase every intended growth origin.
        # Never lengthen a graph or emit a sub-floor decorative tick.
        fraction=.95 if site['member_index']%3==1 and site['stand_role']!='relay' else 0.
    if axis.length*fraction>=config['minimum_ink_mm']:
        points=np.asarray(substring(axis,0,axis.length*fraction).coords)
        out.append(record(ident+'/'+mode+'/ink/axis',points,site,graph,None,'ink',config))
    for j,branch in enumerate(graph['branches']):
        line=LineString(branch['xy_mm'])
        if mode=='M1':fraction=.92
        elif mode=='M2':fraction=.78 if j in (0,1) else .58
        elif mode=='M3':fraction=.65 if j<2 else 0
        elif mode=='F1':fraction=1. if j==0 else 0
        elif mode=='F2':fraction=.90 if j==1 and site['member_index']%2 else 0
        else:fraction=.90 if j==0 and site['member_index']%3==1 else 0
        amount=line.length*fraction
        if amount<config['minimum_ink_mm']:continue
        out.append(record(ident+f'/{mode}/ink/branch-{j}',np.asarray(substring(line,0,amount).coords),site,graph,branch,'ink',config))
    return out


def color_from_graph(site,graph,config):
    """Foliage propagates outward from nodes, never from an ink-stroke offset.

    Inward core and lateral/apical reaches have separate roles. Fan groups share
    branch ancestry, but have unequal ray counts, spread and length hierarchy.
    Intentional within-crown overlap creates mass rather than isolated hairs.
    """
    mode=graph['mode'];ident=site['id'];out=[];far=mode.startswith('F')
    count={'M1':4,'M2':6,'M3':7,'F1':3,'F2':5,'F3':7}[mode]
    for j,branch in enumerate(graph['branches']):
        if mode=='F1' and j>1:continue
        node=np.asarray(branch['crown_node_xy_mm']);direction=np.asarray(branch['direction_xy'])
        theta=math.atan2(direction[1],direction[0]);u=seed_value(branch['id']+'/fan',config)
        n=max(2,count+(1 if branch['role']=='dominant' else -2 if branch['role']=='terminal' else 0))
        n=max(2,n-int(seed_value(branch['id']+'/crown-open',config)*3))
        if site['stand_role']=='relay':n=max(2,n-2)
        # A whole branch's growth is correlated; rays do not receive arbitrary
        # per-screen-point directions. No seed controls the stand geometry.
        for k in range(n):
            t=(k+.45)/(n+.1)
            spread=(.85+1.05*u) if site['form']!='P' else (.75+.5*u)
            angle=theta+(t-.5)*spread
            angle+=.27*math.sin(u*math.pi*2+j)
            d=np.array([math.cos(angle),math.sin(angle)]);normal=np.array([-d[1],d[0]])
            minimum=config['minimum_color_mm']
            length=minimum+(1.2 if far else 3.9)*(.25+.70*math.sin(math.pi*t)+.05*u)
            if mode=='M3':length*=1.12
            if mode=='F3':length*=1.10
            # Outer spread is a shared scaffold zone; its geometry is not
            # constrained to whichever internal ink fragment remains visible.
            offset=(k-(n-1)/2)*(.48 if far else .65)
            start=node+normal*offset+direction*(.45+.65*math.sin(math.pi*t))
            end=start+d*length
            points=segment(start,end,(.22 if far else .42)*math.sin(math.pi*(t-.3)))
            r=record(ident+f'/{mode}/color/branch-{j}/ray-{k}',points,site,graph,branch,'color',config)
            slot_roll=seed_value(site['stand_id']+f'/slot/{j}',config)
            core=['C2','A5','C2','C3'][min(3,int(slot_roll*4))]
            slot=core if .18<t<.82 else ('C1' if k%2 else 'C2')
            # Palette slots are existing Spring materials. These preview widths
            # and opacities are graphic intent, not calibrated wet ink/pigment.
            r.update(palette_slot=slot,color_kind='vegetation',
                foliage_origin_xy_mm=node.tolist(),growth_direction_xy=d.tolist(),
                foliage_state='core' if .18<t<.82 else 'edge',ray_index=k,
                generation_rule='outward growth from shared branch node; no paired ink stroke',
                width_profile_mm=(1.05*(.55+.45*np.sin(np.linspace(0,math.pi,len(points))))).tolist(),
                calibrated_dilution=False)
            out.append(r)
    return out


def build_representation(sites,mode,config):
    graphs=[growth_graph(site,mode,config) for site in sites]
    ink=[];color=[]
    for site,g in zip(sites,graphs):
        ink.extend(ink_from_graph(site,g,config));color.extend(color_from_graph(site,g,config))
    return graphs,ink,color


def apply_visibility(records,evidence,config,mist=True):
    """Keep existing source-depth/global/local semantics; simplify by hierarchy.

    Structural ink is retained more selectively at major growth origins.
    Color has its own branch/ray occurrence and unequal retreat; it does not
    depend on emitted ink IDs. Constant preview alpha is never used as mist.
    """
    result=[];ledger=[]
    for original in records:
        r=deepcopy(original);line=LineString(r['xy_mm']);length=line.length;color='palette_slot' in r
        minimum=config['minimum_color_mm'] if color else config['minimum_ink_mm']
        p=resample(r['xy_mm'],.3);ret,_=root_visibility(evidence,r,p)
        mean=float(np.mean(ret));strength=float(np.clip((mean-.08)/.68,0,1))
        # Dominant internal growth starts remain readable at partial mist;
        # outward minor foliage disappears before the structure.
        occurrence=.18+.82*strength**.72 if color else .72+.28*strength
        unit=r['growth_branch_id']+('/foliage/'+str(r.get('ray_index',0)) if color else '/structure')
        if mist and seed_value(unit+'/mist',config)>occurrence:
            ledger.append(dict(source_id=r['id'],channel='color' if color else 'ink',reason='hierarchical-mist-occurrence',
                mean_retention=mean,source_length_mm=length,removed_mm=length,kept_intervals_mm=[]));continue
        offset=0.
        if mist and color and strength<.85 and seed_value(r['id']+'/retreat',config)<.6:
            a=length*(1-strength)*.22*seed_value(r['id']+'/head',config)
            b=length*(1-(1-strength)*.3*seed_value(r['id']+'/tip',config))
            if b-a<minimum:
                ledger.append(dict(source_id=r['id'],channel='color',reason='retreat-below-physical-floor',mean_retention=mean,
                    source_length_mm=length,removed_mm=length,kept_intervals_mm=[]));continue
            points=np.asarray(substring(line,a,b).coords);oldarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
            at=a+np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
            if 'width_profile_mm' in r:r['width_profile_mm']=np.interp(at,oldarc,r['width_profile_mm']).tolist()
            r['xy_mm']=points.tolist();offset=a
        def gate(xy,arc,rec):
            retain,vis=root_visibility(evidence,rec,xy)
            margin=rec['assumed_footprint_mm']/2+1.4
            safe=sample(evidence.protected_clearance,xy,order=0)-margin
            # Even the no-soft-mist control preserves fully omitted cores,
            # global reserves and nearer-terrain occlusion.
            threshold=.08 if mist else 0.
            g=np.minimum.reduce([safe,retain-threshold,np.where(vis,1.,-1.)])
            return g,['locked-depth-matched-fields','protected-footprint','source-terrain-visibility']
        r['source_arc_mm']=[0.,LineString(r['xy_mm']).length]
        parts,decision=clip_source(r,gate,minimum_mm=minimum,step_mm=.15)
        for p in parts:
            p['source_stroke_id']=original['id'];p['source_arc_mm']=[v+offset for v in p['source_arc_mm']]
            p['mean_retention']=mean;p['mist_geometry_applied']=mist
            p['source_forward_profile_m']=[r['source_forward_m']]*len(p['xy_mm'])
        decision.update(channel='color' if color else 'ink',source_length_mm=length,mean_retention=mean,
            endpoint_retreat_mm=offset,removed_mm=length-sum(LineString(p['xy_mm']).length for p in parts),
            kept_intervals_mm=[p['source_arc_mm'] for p in parts])
        result.extend(parts);ledger.append(decision)
    return result,ledger
