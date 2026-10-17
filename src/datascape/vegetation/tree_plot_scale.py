"""v07: physical-size foliage budgets and noncrossing contour tendencies.

Geometric design assumptions are explicit, never hardware calibration. V06
growth/terminal scaffolds remain inputs; the scene pipeline is not imported.
"""
from collections import defaultdict,Counter
from copy import deepcopy
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_rhythm as prior
from datascape.vegetation import tree_growth as growth
from datascape.strokes.vector import resample,split_at_gate

PROFILES=('v06','light','spare')
UNIT_CAPS={
    'light':{'large':{'dense':9,'light':5,'open':1,'remnant':1},
             'medium':{'dense':4,'light':2,'open':1,'remnant':1},
             'small':{'dense':2,'light':1,'open':0,'remnant':0}},
    'spare':{'large':{'dense':6,'light':3,'open':1,'remnant':1},
             'medium':{'dense':3,'light':1,'open':0,'remnant':0},
             'small':{'dense':1,'light':1,'open':0,'remnant':0}}}


def size_class(height):return 'large' if height>=70 else 'medium' if height>=35 else 'small'


def thin_units(source,profile,design_width_mm=.8,clear_gap_mm=.5):
    """Reduce both unit touch count and unit count, then enforce an mm gap.

    Candidate locations and directional fans remain V02/v06-derived. Minimum
    leaf length is held physically, rather than shrinking into sub-mm detail.
    """
    cls=size_class(source.height);caps=UNIT_CAPS[profile][cls]
    by_unit=defaultdict(list)
    for m in source.marks:
        if m.part=='foliage-field':by_unit[m.key.rsplit('-',1)[0]].append(m)
    info={u['key']:u for u in source.canopy_diagnostics['units'] if u['retained']}
    pads=source.lobes;groups=defaultdict(list)
    for key,marks in by_unit.items():groups[info[key]['owner_pad']].append((key,marks))
    probabilities=({'large':[.45,.47,.08],'medium':[.60,.35,.05],'small':[.85,.15,0]}
                   if profile=='light' else {'large':[.65,.32,.03],'medium':[.85,.15,0],'small':[1,0,0]})[cls]
    minimum_length=max(2.8,3.5*design_width_mm)
    minimum_centerline_gap=design_width_mm+clear_gap_mm
    accepted=[];unit_records=[];pad_records=[];sampled=[];tree=None
    # Dense pads get first use of limited space; no extra units fill an open pad.
    order=sorted(source.canopy_diagnostics['pads'],key=lambda p:({'dense':0,'light':1,'open':2,'remnant':3}[p['state']],p['key']))
    for pad in order:
        candidates=groups[pad['key']];count=0;target=caps[pad['state']]
        for key,available in sorted(candidates,key=lambda x:(info[x[0]]['radius_fraction'],x[0])):
            rng=old.rng_for(source.seed,key+'/physical-unit')
            wanted=int(rng.choice([1,2,3],p=probabilities));n=min(wanted,len(available))
            slots=np.array([len(available)//2]) if n==1 else np.round(np.linspace(0,len(available)-1,n)).astype(int)
            candidate=[]
            for i in slots:
                m=deepcopy(available[i]);length=old.length(m.xy)
                goal=max(minimum_length,min(6.2,length))
                m.xy=m.xy[0]+(m.xy-m.xy[0])*(goal/max(length,1e-9));candidate.append(m)
            dense=np.concatenate([resample(m.xy,.2) for m in candidate])
            gap=float(tree.query(dense)[0].min()) if tree is not None else None
            reason='pad-budget' if count>=target else 'physical-gap' if gap is not None and gap<minimum_centerline_gap+.2 else 'kept'
            unit_records.append({'key':key,'pad':pad['key'],'state':pad['state'],'source_touches':len(available),
                                 'touches':n,'retained':reason=='kept','reason':reason,
                                 'sampled_gap_to_previous_mm':gap,'rotation_deg':info[key]['rotation_deg']})
            if reason!='kept':continue
            accepted+=candidate;count+=1;sampled.append(dense)
            tree=cKDTree(np.concatenate(sampled))
        pad_records.append({'key':pad['key'],'state':pad['state'],'available_units':len(candidates),'unit_cap':target,'retained_units':count})
    kept=[u for u in unit_records if u['retained']]
    return accepted,{'source_version':'v06 R2','size_class':cls,'source_units':len(by_unit),
                     'source_foliage_paths':sum(len(v) for v in by_unit.values()),'retained_units':len(kept),
                     'retained_foliage_paths':len(accepted),'unit_touch_histogram':dict(Counter(u['touches'] for u in kept)),
                     'minimum_leaf_length_mm':minimum_length,'design_width_mm':design_width_mm,
                     'clear_gap_mm':clear_gap_mm,'minimum_between_unit_centerline_gap_mm':minimum_centerline_gap,
                     'sampling_guard_mm':.2,'pads':pad_records,'units':unit_records,
                     'within_unit_merging':'Intentional calligraphic glyph; individual touch impressions are not guaranteed separate',
                     'across_tree_spacing':'Not guaranteed; only one object is checked at a time',
                     'physical_plotting_validated':False}


def segment_crossings(a,b):
    """Strict transverse intersections, excluding legitimate shared endpoints."""
    def cross(x,y):return x[...,0]*y[...,1]-x[...,1]*y[...,0]
    p=np.asarray(a)[:-1,None,:];q=np.asarray(b)[None,:-1,:]
    r=np.diff(a,axis=0)[:,None,:];s=np.diff(b,axis=0)[None,:,:]
    den=cross(r,s);ok=abs(den)>1e-10;den=np.where(ok,den,1)
    t=cross(q-p,s)/den;u=cross(q-p,r)/den
    return int(np.sum(ok&(t>1e-7)&(t<1-1e-7)&(u>1e-7)&(u<1-1e-7)))


def safe_contours(center,radius,key,seed,design_width_mm=.8,joints=(),branch=False):
    """Use monotone coordinate sections, a gradual taper and a single tail.

    Opposite sides are ordered functions of the same monotone coordinate.
    They cannot cross. If a member has no monotone coordinate, use its single
    structural centerline instead of forcing an invalid paired outline.
    """
    p=resample(center,.3);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];u=arc/max(arc[-1],1e-9)
    choices=[j for j in (1,0) if np.all(np.diff(p[:,j])>=-1e-9) or np.all(np.diff(p[:,j])<=1e-9)]
    part='branch-contour' if branch else 'trunk-contour';parent='axis' if branch else None
    if not choices:
        return [old.Mark(key+'/single',p,.30,part,parent)],{'mode':'single nonmonotone fallback','opposite_side_crossings':0},None
    along=max(choices,key=lambda j:np.ptp(p[:,j]));across=1-along
    base=radius*(1-.72*u)
    for j,point in enumerate(joints):
        f=u[np.argmin(np.linalg.norm(p-point,axis=1))]
        base*=1+(.12 if j%2 else .18)*np.exp(-((u-f)/.065)**2)
    left=base*.88;right=base*1.10;spacing=left+right
    # At small physical widths, merge to one structural stroke over several mm.
    threshold=design_width_mm+.3
    below=np.flatnonzero(spacing<threshold)
    start=float(u[below[0]]) if len(below) else 1.
    if start<=.06:
        return [old.Mark(key+'/single',p,.30,part,parent)],{'mode':'single physical LOD','opposite_side_crossings':0},None
    end=min(1.,start+max(.05,2.5/max(arc[-1],1))) if len(below) else 1.
    if len(below):
        t=np.clip((u-start)/max(end-start,1e-9),0,1);fade=1-t*t*(3-2*t);left*=fade;right*=fade
    a=p.copy();b=p.copy();a[:,across]-=left;b[:,across]+=right
    stop=max(2,int(np.searchsorted(u,end,side='right')))
    a=a[:stop];b=b[:stop];out=[]
    for side,edge in [(-1,a),(1,b)]:
        intervals=[(0,.43),(.445,1)] if old.length(edge)>20 and side==-1 else [(0,1)]
        for i,(f,g) in enumerate(intervals):
            q=old.path_part(edge,f,g)
            if old.length(q)>=2:out.append(old.Mark(f'{key}/side{side}/{i}',q,.40 if side==1 else .28,part,parent))
    if end<1 and len(p[stop-1:])>1 and old.length(p[stop-1:])>=2:
        out.append(old.Mark(key+'/single-tail',p[stop-1:],.30,part,parent))
    crossings=segment_crossings(a,b);assert crossings==0
    envelope={'center':p,'left':p.copy(),'right':p.copy(),'along':along,'across':across}
    envelope['left'][:,across]-=base*.88;envelope['right'][:,across]+=base*1.1
    return out,{'mode':'ordered sections with gradual physical collapse','along_coordinate':along,
                'paired_until_fraction':start,'single_after_fraction':end,
                'minimum_uncollapsed_spacing_mm':float(spacing.min()),'opposite_side_crossings':crossings},envelope


def outside_stem(points,envelope):
    if envelope is None:return np.ones(len(points))
    a=envelope['along'];b=envelope['across'];order=np.argsort(envelope['center'][:,a])
    s=envelope['center'][order,a];lo=np.interp(points[:,a],s,envelope['left'][order,b]);hi=np.interp(points[:,a],s,envelope['right'][order,b])
    inside_extent=(points[:,a]>=s[0])&(points[:,a]<=s[-1])
    gate=np.maximum(lo-points[:,b],points[:,b]-hi)
    return np.where(inside_extent,gate,np.maximum(1,abs(gate)))


def safe_body(source,design_width_mm=.8):
    structure=deepcopy(source.structure);members={k:np.array(p) for k,p in structure['members'].items()}
    axis=np.vstack([p if i==0 else p[1:] for i,(k,p) in enumerate((x for x in members.items() if x[0].startswith('axis/')))])
    radius=source.height*{'hero-pine':.022,'broadleaf':.018,'understory':.012}[source.family]
    origins=[p[0] for k,p in members.items() if k.startswith('arm-')]
    marks,audit,envelope=safe_contours(axis,radius,'axis',source.seed,design_width_mm,origins)
    audits={'axis':audit}
    for key,p in members.items():
        if not key.startswith('arm-'):continue
        mm,info,_=safe_contours(p,radius*.46,key,source.seed,design_width_mm,branch=True)
        for m in mm:
            # Do not draw branch contour continuations through the stem interior.
            gate=outside_stem(m.xy,envelope)
            for j,q in enumerate(split_at_gate(m.xy,gate,minimum_length=2)):
                marks.append(old.Mark(m.key+f'/outside-{j}',q,m.width,m.part,m.parent))
        audits[key]=info
    # Keep limited terminal twigs only at the large physical size.
    if size_class(source.height)=='large':
        marks += [deepcopy(m) for m in source.marks if m.part=='twig' and old.length(m.xy)>=2.8]
        # Two short centerline grains, confined to the body instead of long X accents.
        for i,f in enumerate([.28,.60]):
            a=max(0,f-1.4/max(old.length(axis),1));b=min(1,f+1.4/max(old.length(axis),1))
            q=old.path_part(axis,a,b)
            if envelope is not None and np.all(outside_stem(q,envelope)<0):
                marks.append(old.Mark(f'axis/grain/{i}',q,.17,'bark-grain','axis'))
    marks += [deepcopy(m) for m in source.marks if m.key.startswith('basal-') or m.part in ('fracture','dead-limb')]
    for m in marks:m.owner=source.identity
    structure.update(body_grammar='ordered contour sections; no hourglass pinch',contour_audit=audits,
                     contour_spacing={'design_width_mm':design_width_mm,'paired_to_single':'gradual physical LOD'},
                     joint_detail='Mild fork swelling and contained short grain; interior arm continuations clipped')
    return marks,structure


def make_tree(family='hero-pine',root=(90,155),height=95,season='spring',seed=20261017,
              accent='none',identity='tree-0',posture='auto',profile='light',design_width_mm=.8,clear_gap_mm=.5):
    if profile not in PROFILES:raise ValueError('unknown physical density profile')
    if not np.isfinite(design_width_mm) or not .2<=design_width_mm<=2:raise ValueError('design width must be 0.2–2 mm')
    if not np.isfinite(clear_gap_mm) or clear_gap_mm<.2:raise ValueError('clear gap must be >=0.2 mm')
    depth='near' if height>=70 else 'middle'
    source=prior.make_tree(family,root,height,season,seed,accent,identity,depth,posture=posture)
    if profile=='v06':return source
    foliage,diagnostics=thin_units(source,profile,design_width_mm,clear_gap_mm)
    marks,structure=safe_body(source,design_width_mm);marks+=foliage
    structure['density_profile']=profile
    return growth.GrowthTree(identity,family,'physical-units',season,int(seed),np.asarray(root,float),float(height),
                             marks,deepcopy(source.lobes),accent,structure,diagnostics)


def vector_records(marks,trees):
    if all(t.canopy!='physical-units' for t in trees):return prior.vector_records(marks,trees)
    rr=old.vector_records(marks,trees);by_id={t.identity:t for t in trees}
    for r in rr:
        t=by_id[r['source_root_id']]
        version='0.7' if t.canopy=='physical-units' else '0.6'
        r['id']=r['id'].replace('catalog-v02/',f'catalog-v{version.replace(".","")}/',1);r['catalog_version']=version
        if version=='0.7':
            r['density_profile']=t.structure['density_profile']
            r['physical_design_assumption_mm']=t.canopy_diagnostics['design_width_mm']
            r['physical_plotting_validated']=False
    return rr
