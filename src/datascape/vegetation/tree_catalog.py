"""Independent tree families, foliage fields and local object-to-object overlap.

No scene placement, geography, mist, pigment calibration or machine motion.
All drawing geometry is open centerline paths; wash regions are separate intent.
"""
from dataclasses import dataclass, field
from copy import deepcopy
import hashlib
import numpy as np
from scipy.interpolate import CubicSpline
from datascape.strokes.vector import resample, split_at_gate, finalize


@dataclass
class Mark:
    key: str
    xy: np.ndarray
    width: float
    part: str
    parent: str | None = None
    owner: str = ''


@dataclass
class Tree:
    identity: str
    family: str
    canopy: str
    season: str
    seed: int
    root: np.ndarray
    height: float
    marks: list = field(default_factory=list)
    lobes: list = field(default_factory=list)
    accent: str = 'none'


FAMILIES = ('hero-pine', 'broadleaf', 'understory')
CANOPIES = ('ribbons', 'fans', 'hybrid')
SEASONS = {
    'spring': {'density':.68, 'extent':.92, 'wash':.10, 'color':'#accb9d'},
    'summer': {'density':1.0, 'extent':1.11, 'wash':.18, 'color':'#6fa077'},
    'autumn': {'density':.55, 'extent':.90, 'wash':.13, 'color':'#c89666'},
    'winter': {'density':.055, 'extent':.73, 'wash':.025, 'color':'#adb4ac'},
}
ACCENTS = ('none', 'broken-top', 'bent', 'suppressed', 'dead-limb', 'damaged-crown')


def rng_for(seed, key):
    token = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'little')
    return np.random.default_rng(np.random.SeedSequence([int(seed), token]))


def length(p):
    return float(np.linalg.norm(np.diff(np.asarray(p), axis=0), axis=1).sum())


def curve(knots, step=.45):
    """Datascape's arclength spline construction, isolated from scene imports."""
    p=np.asarray(knots,float);u=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    keep=np.r_[True,np.diff(u)>1e-8];p=p[keep];u=u[keep]
    if len(p)<4:return resample(p,step)
    return CubicSpline(u,p,axis=0,bc_type='natural')(np.linspace(0,u[-1],max(3,int(u[-1]/step)+1)))


def path_part(p, a, b):
    q=resample(p,.3);u=np.r_[0,np.cumsum(np.linalg.norm(np.diff(q,axis=0),axis=1))];u/=max(u[-1],1e-9)
    return split_at_gate(q,np.minimum(u-a,b-u),0)[0]


def built_axis(center, radius, key, parent=None, mode='segmented', bark=True, seed=0):
    """Unequal paired contour tendencies, not filled trunk polygons."""
    p=resample(center,.45);u=np.linspace(0,1,len(p));tangent=np.gradient(p,axis=0)
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
    if mode=='single':return [Mark(key+'/single',p,.50,'trunk-control',parent)]
    out=[]
    rhythm=rng_for(seed,key+'/contour-rhythm')
    for side in [-1,1]:
        irregular=1+.16*np.sin(u*17+side*1.7)+.08*np.sin(u*43+side)
        offsets=radius*(1-.78*u)*irregular*(1.12 if side==1 else .88)
        border=p+side*normal*offsets[:,None]
        intervals=[(.0,.32),(.35,.69),(.73,1)] if side==1 else [(.0,.23),(.26,.57),(.61,.83),(.86,1)]
        if mode=='paired':intervals=[(0,1)]
        for j,(a,b) in enumerate(intervals):
            if mode=='segmented':
                a=a+rhythm.uniform(-.012,.012) if a>0 else a
                b=b+rhythm.uniform(-.012,.012) if b<1 else b
            q=path_part(border,a,b)
            if length(q)>=1.2:out.append(Mark(f'{key}/edge{side}/{j}',q,.42 if side==1 else .30,'trunk-contour' if parent is None else 'branch-contour',parent))
    if bark and radius>.6:
        for i,f in enumerate([.09,.18,.31,.47,.55,.69,.79]):
            a=int(f*(len(p)-1));b=min(len(p)-1,a+max(3,int(len(p)*(.05+.02*(i%2)))))
            q=p[a:b+1]+normal[a:b+1]*(radius*.30*(-1 if i%2 else 1))
            if length(q)>=1.4:out.append(Mark(f'{key}/grain/{i}',q,.18,'bark-grain',key))
    return out


def skeleton(family, height, seed, accent, trunk_mode):
    rng=rng_for(seed,f'{family}/structure')
    if family=='hero-pine':
        knots=np.array([[0,0],[-.06,-.18],[.015,-.36],[-.025,-.53],[.10,-.72],[.13,-.91]])
        levels=[.28,.48,.65,.83];sides=[-1,1,-1,1];spans=[.34,.39,.27,.22];rises=[.14,.15,.17,.13]
        radius=height*.021;main_count=1
    elif family=='broadleaf':
        knots=np.array([[0,0],[.015,-.18],[-.045,-.37],[.035,-.53],[.01,-.70]])
        levels=[.42,.62,.81];sides=[-1,1,-1];spans=[.28,.33,.19];rises=[.30,.26,.26]
        radius=height*.017;main_count=1
    else:
        knots=np.array([[0,0],[-.025,-.22],[.04,-.41],[-.015,-.61]])
        levels=[.30,.60,.85];sides=[1,-1,1];spans=[.27,.31,.23];rises=[.22,.23,.17]
        radius=height*.012;main_count=3
    knots[1:,0]+=rng.uniform(-.012,.012,len(knots)-1)
    if accent=='bent':knots[:,0]+=.20*(-knots[:,1])**1.5
    if accent=='suppressed':knots[:,0]*=.72;knots[:,1]*=.73
    center=curve(knots*height)
    if accent=='broken-top':center=path_part(center,0,.77)
    out=built_axis(center,radius,'axis',mode=trunk_mode,seed=seed)
    if accent=='broken-top':
        at=center[-1];out.append(Mark('fracture',curve([at+[-radius*.8,.7],at+[0,-.5],at+[radius*.7,.4]]),.38,'fracture','axis'))
    ends=[]
    for i,(level,side,span,rise) in enumerate(zip(levels,sides,spans,rises)):
        origin=center[int(level*(len(center)-1))]
        if accent=='suppressed':span*=.72;rise*=.70
        delta=height*np.array([side*span,-rise])
        end=origin+delta
        p=curve([origin,origin+delta*[.27,.10],end-delta*[.20,.30],end])
        key=f'arm-{i}'
        out+=built_axis(p,radius*.42,key,'axis',mode='segmented',bark=False,seed=seed)
        for j,f in enumerate([.52,.78]):
            start=p[int(f*(len(p)-1))];d=height*np.array([side*(.10 if j==0 else -.07),-.12])
            tip=start+d
            q=curve([start,start+d*.25+[side*height*.012,0],tip-d*.20,tip])
            out.append(Mark(f'{key}/twig-{j}',q,.23 if j==0 else .18,'twig',key))
        ends.append(end)
    if main_count>1:
        for j,(side,reach) in enumerate([(-1,.36),(1,.31)]):
            start=np.array([side*height*.045,0]);end=np.array([side*height*reach,-height*(.62+.12*j)])
            p=curve([start,start+[side*height*.04,-height*.2],end+[-side*height*.07,height*.15],end])
            out+=built_axis(p,radius*.65,f'basal-{j}',mode='segmented',bark=False,seed=seed)
            ends.append(end)
    if accent=='dead-limb':
        start=center[int(.55*(len(center)-1))];end=start+height*np.array([-.38,-.02])
        out.append(Mark('dead-limb',curve([start,start+[-height*.15,-height*.06],end+[height*.04,-height*.02],end]),.32,'dead-limb','axis'))
    return out,center,np.asarray(ends)


def canopy_lobes(family, height, center, ends, season, accent, seed):
    """Connected crown fields include bridge lobes, not tip-by-tip stickers."""
    e=SEASONS[season]['extent'];lobes=[]
    def add(key,at,rx,ry,angle=0,weight=1):
        lobes.append({'key':key,'center':np.asarray(at,float),'radii':height*e*np.array([rx,ry]),
                      'angle':angle,'weight':weight})
    if family=='hero-pine':
        for i,end in enumerate(ends):
            add(f'pad-{i}',end+[-.025*height,-.018*height],.22-.018*i,.075+.007*(i%2),(-.09 if i%2 else .16),1-.07*i)
        add('apex',center[-1]+[0,-height*.025],.19,.082,-.11,.8)
        add('bridge',np.mean(ends[1:3],axis=0)+[height*.025,-height*.045],.19,.095,.18,.62)
    elif family=='broadleaf':
        crown=np.array([0,-height*.71])
        for i,(dx,dy,rx,ry,angle) in enumerate([(-.20,.02,.23,.20,-.4),(.04,-.13,.25,.22,.15),(.25,.01,.24,.19,.35),(-.02,.11,.25,.16,-.15)]):
            add(f'crown-{i}',crown+height*np.array([dx,dy]),rx,ry,angle,1 if i!=3 else .70)
    else:
        for i,(dx,dy,rx,ry) in enumerate([(-.27,-.49,.25,.17),(.05,-.64,.27,.20),(.29,-.47,.25,.17),(-.02,-.33,.28,.16)]):
            add(f'mass-{i}',height*np.array([dx,dy]),rx,ry,(-.20 if i%2 else .18),.8 if i==3 else 1)
    shape=rng_for(seed,family+'/mass-shape')
    for l in lobes:
        l['center']+=shape.uniform(-.015,.015,2)*height
        l['radii']*=shape.uniform(.88,1.12,2)
        l['angle']+=shape.uniform(-.13,.13)
    if accent=='broken-top':
        cutoff=-height*(.68 if family=='hero-pine' else .75)
        lobes=[l for l in lobes if l['center'][1]>cutoff]
    if accent=='suppressed':
        for l in lobes:
            if family!='hero-pine':l['center']*=np.array([.75,.75])
            l['radii']*=.73
    if accent=='bent':
        if family!='hero-pine':
            for l in lobes:l['center'][0]+=.20*height*(-l['center'][1]/height)**1.5
    if accent=='damaged-crown':
        lobes=[l for i,l in enumerate(lobes) if i!=1]
        for i,l in enumerate(lobes):
            if i%2:l['weight']*=.45;l['radii']*=np.array([.85,.7])
    return lobes


def rotate(p,angle):
    co,si=np.cos(angle),np.sin(angle)
    return np.asarray(p)@np.array([[co,si],[-si,co]])


def union_score(points, lobes, scale=1):
    score=np.full(len(points),-np.inf)
    for l in lobes:
        q=rotate(np.asarray(points)-l['center'],-l['angle'])/(l['radii']*scale)
        theta=np.arctan2(q[:,1],q[:,0]);r=np.linalg.norm(q,axis=1)
        edge=1+.07*np.sin(3*theta+.4)+.045*np.sin(7*theta+1.1)
        score=np.maximum(score,edge-r)
    return score


def foliage(family, grammar, lobes, season, seed, height):
    c=SEASONS[season];density=c['density']
    if family=='hero-pine' and season=='winter':density=.27
    out=[];occupied={}
    # Field coalescence suppresses parallel duplicates where lobes overlap.
    def accept(p,key,width=.23):
        if length(p)<1.35:return
        tangent=p[-1]-p[0];angle=np.arctan2(tangent[1],tangent[0])
        bins={tuple(np.r_[np.floor(q/1.0).astype(int),int((angle%np.pi)/.42)]) for q in resample(p,.7)}
        if bins and sum(b in occupied for b in bins)/len(bins)>.58:return
        for b in bins:occupied[b]=True
        out.append(Mark(key,p,width,'foliage-field'))
    for l in lobes:
        key=l['key'];rng=rng_for(seed,f'{family}/{key}/foliage')
        rx,ry=l['radii'];rows=max(1,int((15 if family=='hero-pine' else 21)*density*l['weight']*height/85))
        if season=='winter' and family!='hero-pine':rows=0
        for j in range(rows):
            v=(j+.5)/max(rows,1);vertical=ry*(2*v-1)*.90
            span=rx*np.sqrt(max(.03,1-(vertical/ry)**2))*rng.uniform(.72,1.04)
            mode=grammar
            if grammar=='hybrid':mode='ribbons' if (j%3!=0 and v>.25) else 'fans'
            if mode=='ribbons':
                shift=0
                if grammar=='hybrid':
                    span*=rng.uniform(.45,.70)
                    shift=rng.uniform(-.34,.34)*rx
                pieces=1+(j%4==0)
                for part in range(pieces):
                    a=(-1 if part==0 else .12)*span;b=(1 if pieces==1 or part==1 else -.12)*span
                    x=np.linspace(a,b,14)+shift;tilt=rng.uniform(-.24,.24)+l['angle']*.45
                    y=vertical+tilt*x+ry*rng.uniform(.05,.22)*np.sin(np.linspace(rng.uniform(0,.8),np.pi+rng.uniform(-.2,.3),len(x)))
                    p=l['center']+rotate(np.column_stack([x,y]),l['angle'])
                    # Do not force a common smooth envelope around the crown.
                    accept(p,f'{key}/ribbon/{j}-{part}',rng.uniform(.19,.29))
            else:
                # Many short, uneven, overlapping sprays merge into a field.
                groups=max(2,int(2.8*span/max(height*.09,2)))
                for group in range(groups):
                    x=(-.82+1.64*(group+.5)/groups)*span+rng.uniform(-.06,.06)*rx
                    origin=np.array([x,vertical]);sweep=rng.uniform(.65,1.15);bias=rng.uniform(-.65,.65)
                    for ray in range(4+(j+group)%3):
                        a=-np.pi/2+bias+sweep*(ray/5-.5)
                        dist=max(1.6,height*rng.uniform(.035,.065)*(1-.2*abs(v-.5)))
                        end=origin+dist*np.array([np.cos(a),np.sin(a)])
                        # Stagger starts instead of an ornamental common fan hub.
                        start=origin+rng.uniform(-.9,.9,2)
                        p=curve([start,start+(end-start)*.25+[.25,.1],end-(end-start)*.20,end],.4)
                        accept(l['center']+rotate(p,l['angle']),f'{key}/fan/{j}-{group}-{ray}',rng.uniform(.17,.25))
    return out


def make_tree(family='broadleaf', canopy='hybrid', root=(90,155), height=95,
              season='spring', seed=20261017, accent='none', identity='tree-0', trunk_mode='segmented'):
    if family not in FAMILIES or canopy not in CANOPIES or season not in SEASONS or accent not in ACCENTS:
        raise ValueError('unknown family, canopy, season or accent')
    root=np.asarray(root,float)
    if root.shape!=(2,) or not np.isfinite(root).all() or not np.isfinite(height) or height<15:
        raise ValueError('finite root and height >=15 mm required')
    if trunk_mode not in ('single','paired','segmented'):raise ValueError('unknown trunk construction')
    marks,axis,ends=skeleton(family,height,seed,accent,trunk_mode)
    lobes=canopy_lobes(family,height,axis,ends,season,accent,seed)
    marks+=foliage(family,canopy,lobes,season,seed,height)
    for m in marks:m.xy=m.xy+root;m.owner=identity
    for l in lobes:l['center']=l['center']+root
    return Tree(identity,family,canopy,season,seed,root,height,marks,lobes,accent)


def foreground_gate(points, tree, trunk_index=None):
    """Local pictorial overlap only: sparse canopy has smaller occluding cores."""
    density=SEASONS[tree.season]['density']
    if tree.family=='hero-pine' and tree.season=='winter':density=.27
    core=.34+.27*density
    gate=-union_score(points,tree.lobes,core) if density>.08 else np.ones(len(points))*1e3
    # A narrow physical trunk ribbon also occludes farther strokes.
    trunk=[m for m in tree.marks if m.part=='trunk-contour']
    if trunk:
        if trunk_index is None:
            dense=np.concatenate([resample(m.xy,.65) for m in trunk])
            from scipy.spatial import cKDTree
            trunk_index=cKDTree(dense)
        distance=trunk_index.query(points)[0]-.40
        gate=np.minimum(gate,distance)
    return gate


def overlap(trees, apply=True):
    """Input order is far to near; clip real paths without white cover polygons."""
    if len({t.identity for t in trees})!=len(trees):
        raise ValueError('overlap requires unique object identities')
    result=[];before=0;after=0;cut=0;owners=[]
    from scipy.spatial import cKDTree
    indexes={t.identity:cKDTree(np.concatenate([resample(m.xy,.65) for m in t.marks if m.part=='trunk-contour']))
             for t in trees if any(m.part=='trunk-contour' for m in t.marks)}
    for i,tree in enumerate(trees):
        for mark in tree.marks:
            before+=length(mark.xy);runs=[mark.xy]
            for front in trees[i+1:] if apply else []:
                new=[]
                for run in runs:
                    p=resample(run,.35);gate=foreground_gate(p,front,indexes.get(front.identity))
                    new+=split_at_gate(p,gate,1.2)
                runs=new
            retained=sum(length(p) for p in runs);after+=retained
            if retained<length(mark.xy)-.1:cut+=1
            for j,p in enumerate(runs):
                m=deepcopy(mark);m.key+=f'/visible-{j}';m.xy=p;result.append(m)
        owners.append(tree.identity)
    return result,{'before_mm':before,'retained_mm':after,'removed_mm':before-after,
                   'affected_source_paths':cut,'far_to_near':owners,
                   'model':'Procedural dense-core and trunk-ribbon occlusion; not physical 3D foliage or scene mist'}


def halo_outline(lobe, season, scale=1.13):
    angle=np.linspace(0,2*np.pi,81)
    radius=1+.075*np.sin(3*angle+.4)+.04*np.sin(7*angle+1.1)
    p=np.column_stack([np.cos(angle),np.sin(angle)])*lobe['radii']*radius[:,None]*scale
    return lobe['center']+rotate(p,lobe['angle'])


def vector_records(marks, trees):
    by_id={t.identity:t for t in trees};out=[]
    for m in marks:
        tree=by_id[m.owner]
        for s in finalize([m.xy],f'catalog-v02/{m.owner}/{m.key}',m.width,{
                'layer':'V','catalog_family':tree.family,'canopy_grammar':tree.canopy,
                'grammar_part':m.part,'component_key':m.key,'parent_component_key':m.parent,
                'source_root_id':tree.identity,'source_root_xy_mm':tree.root.tolist(),
                'source_height_mm':tree.height,'season':tree.season,'seed':tree.seed,
                'accent':tree.accent,'placement_basis':'synthetic independent fixture',
                'scene_integration_status':'not_evaluated','ground_visibility_status':'unresolved',
                'material_intent':'unassigned'}):
            p=np.asarray(s['xy_mm']);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];u=arc/max(arc[-1],1e-9)
            profile=.30+.70*np.sin(np.pi*(.08+.84*u))
            s['width_profile_mm']=(m.width*profile).round(4).tolist()
            s['expression']={'intensity':.65,'intensity_samples':(.65*profile).round(4).tolist(),'pressure_calibrated':False}
            s['draw_order']=len(out);out.append(s)
    return out


def wash_metadata(trees):
    return {'schema':'datascape.canopy-wash-intent/0.1','not_plotter_paths':True,
            'calibrated_pigment':False,'regions':[{
                'owner':t.identity,'family':t.family,'season':t.season,
                'source_root_xy_mm':t.root.tolist(),'lobe_key':l['key'],
                'outline_xy_mm':halo_outline(l,t.season).round(3).tolist(),
                'display_color':SEASONS[t.season]['color'],
                'preview_weight':SEASONS[t.season]['wash']*l['weight'],
                'basis':'Procedural canopy support; not observed vegetation extent'}
                for t in trees for l in t.lobes]}
