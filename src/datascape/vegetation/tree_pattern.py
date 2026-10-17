"""v05: preserved V02 directional fans with limited, traceable variation.

The crown footprint and every candidate touch come from the immutable V02
generator. A separately constructed body fits those existing crown supports.
No scene placement, terrain retention, mist or machine execution is imported.
"""
from collections import defaultdict, Counter
from copy import deepcopy
import numpy as np
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_growth as growth
from datascape.strokes.vector import resample

CANOPIES=('v02-control','count-2-5','count-angle')
POSTURES=('upright','stooped','redirected')


def body_contours(center,radius,key,seed,joints=(),part='trunk-contour',parent=None,depth='near',branch=False):
    """Two unequal tendencies span growth joints; gaps avoid the joints.

    Offset normals are blended locally, not by fitting a whole-axis spline.
    Swelling belongs to the body contour; scars are short open interior marks.
    """
    p=resample(center,.4);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    u=arc/max(arc[-1],1e-9)
    tangent=np.gradient(p,axis=0)
    for axis in range(2):tangent[:,axis]=np.convolve(np.pad(tangent[:,axis],(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
    rng=old.rng_for(seed,key+'/body')
    joint_u=[float(u[np.argmin(np.linalg.norm(p-q,axis=1))]) for q in joints]
    base=radius*(1-.78*u)
    out=[]
    for side in (-1,1):
        wave=1+.075*np.sin(18*u+side*1.3)+.035*np.sin(37*u+side)
        offset=base*wave*(1.13 if side==1 else .87)
        for j,f in enumerate(joint_u):
            offset*=1+(rng.uniform(.18,.38) if (j+side)%2 else rng.uniform(.06,.16))*np.exp(-((u-f)/.045)**2)
        if branch:
            offset*=1+(.55 if side==1 else .16)*np.exp(-((u-.065)/.11)**2)
        edge=p+normal*(side*offset)[:,None]
        if branch: intervals=[(.035,1)] if side==1 else [(.055,.64),(.68,1)]
        else:
            # Contour lifts are staggered and usually away from growth joints.
            cuts=np.array([.31,.71] if side==1 else [.23,.54,.83])+rng.uniform(-.025,.025,2 if side==1 else 3)
            for k,f in enumerate(cuts):
                if any(abs(f-j)<.045 for j in joint_u):cuts[k]+=.065
            cuts=np.clip(np.sort(cuts),.08,.93)
            starts=[0]+(cuts+.006).tolist();ends=(cuts-.006).tolist()+[1]
            intervals=list(zip(starts,ends))
        for j,(a,b) in enumerate(intervals):
            q=old.path_part(edge,a,b)
            if old.length(q)>=1.6:out.append(old.Mark(f'{key}/side{side}/{j}',q,.41 if side==1 else .29,part,parent))
    if depth=='near' and radius>.6:
        positions=joint_u if len(joints) else [.17,.48]
        for j,f in enumerate(positions):
            a=max(.02,f-.04);b=min(.96,f+.045)
            q=old.path_part(p+normal*(base*(.30 if j%2 else -.23))[:,None],a,b)
            if old.length(q)>=2:out.append(old.Mark(f'{key}/grain/{j}',q,.18,'bark-grain',key))
    return out


def constructed_structure(family,height,seed,accent,depth,posture='auto'):
    """Mix unequal local members while keeping the original crown endpoints.

    This is a crown-supported object scaffold, not a biological growth model.
    The main body changes posture; branch origins move with it and their
    terminals remain the exact V02 supports, keeping the canopy control honest.
    """
    original,axis,ends=old.skeleton(family,height,seed,accent,'segmented')
    rng=old.rng_for(seed,family+'/body-growth')
    if posture=='auto':posture=str(rng.choice(POSTURES,p=[.32,.34,.34]))
    n=int(rng.choice([2,3,4],p=[.12,.62,.26])) if family!='understory' else int(rng.choice([2,3],p=[.75,.25]))
    sign=int(rng.choice([-1,1]))
    fractions=rng.uniform(.7,1.2,n)*np.linspace(1.22,.76,n);fractions/=fractions.sum()
    f=np.r_[0,np.cumsum(fractions)];end=axis[-1]
    nodes=f[:,None]*end
    if posture=='upright':nodes[:,0]+=height*.018*sign*np.sin(np.pi*f)
    elif posture=='stooped':nodes[:,0]+=height*.15*sign*np.maximum(0,np.sin(np.pi*f))**1.5
    else:nodes[:,0]+=height*.17*sign*np.maximum(0,1-np.abs(f-.58)/.58)
    nodes[0]=[0,0];nodes[-1]=end
    members={};pieces=[];types=[]
    for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        if posture=='upright':bow=0 if i%2==0 else np.linalg.norm(b-a)*.022*sign;kind='straight' if i%2==0 else 'gentle'
        elif posture=='stooped':bow=np.linalg.norm(b-a)*(.11*sign if i==min(1,n-1) else 0);kind='bowed' if bow else 'straight'
        else:bow=np.linalg.norm(b-a)*(.025*sign if i==n-1 else 0);kind='redirected' if i else 'straight'
        p=growth.segment(a,b,bow,step=.4)
        members[f'axis/{i}']=p;pieces.append(p if i==0 else p[1:]);types.append(kind)
    center=np.vstack(pieces)
    radius=height*{'hero-pine':.022,'broadleaf':.018,'understory':.012}[family]
    marks=body_contours(center,radius,'axis',seed,nodes[1:-1],depth=depth)
    if family=='hero-pine':levels=[.28,.48,.65,.83]
    else:levels=[.42,.62,.81] if family=='broadleaf' else [.30,.60,.85]
    for i,level in enumerate(levels):
        origin=center[int(level*(len(center)-1))];tip=ends[i];d=tip-origin
        p=old.curve([origin,origin+d*[.27,.10],tip-d*[.20,.30],tip])
        key=f'arm-{i}';members[key]=p
        marks+=body_contours(p,radius*.46,key,seed,part='branch-contour',parent='axis',depth=depth,branch=True)
        if depth=='near':
            for j,at in enumerate([.52,.78]):
                start=p[int(at*(len(p)-1))];side=1 if d[0]>=0 else -1
                delta=height*np.array([side*(.10 if j==0 else -.07),-.12])
                q=old.curve([start,start+delta*.25+[side*height*.012,0],start+delta*.8,start+delta])
                marks.append(old.Mark(f'{key}/twig-{j}',q,.22 if j==0 else .18,'twig',key))
            # A small, one-sided support touch rather than a ring at every fork.
            if i%2==0 and radius>1:
                q=old.path_part(p,.025,.17)+np.array([radius*.12,0])
                if old.length(q)>=2:marks.append(old.Mark(key+'/collar',q,.19,'bark-grain',key))
    if family=='understory':
        marks += [deepcopy(m) for m in original if m.key.startswith('basal-')]
        for j,side in enumerate([-1,1]):
            start=np.array([side*height*.045,0]);tip=ends[3+j]
            members[f'basal-{j}']=old.curve([start,start+[side*height*.04,-height*.2],tip+[-side*height*.07,height*.15],tip])
    if accent=='dead-limb':
        at=center[int(.55*(len(center)-1))]
        q=old.curve([at,at+height*np.array([-.15,-.06]),at+height*np.array([-.34,-.02]),at+height*np.array([-.38,-.02])])
        marks.append(old.Mark('dead-limb',q,.32,'dead-limb','axis'))
    if accent=='broken-top':
        at=center[-1];q=np.array([at+[-radius*.8,.7],at+[0,-.5],at+[radius*.7,.4]])
        marks.append(old.Mark('fracture',q,.34,'fracture','axis'))
    if depth=='middle':marks=[m for m in marks if m.part not in ('twig','bark-grain')]
    structure={'posture':posture,'axis_nodes_mm':nodes.tolist(),'segment_types':types,
               'length_fractions':fractions.tolist(),'member_count':n,
               'members':{key:p.tolist() for key,p in members.items()},
               'branch_terminals_mm':ends.tolist(),'crown_supports':'Unchanged V02 terminal anchors',
               'ground_attachment':'unresolved','depth_role':depth}
    return marks,structure


def refine_foliage(family,lobes,season,seed,height,canopy,angle_limit_deg=10):
    """Subset exact V02 fan touches; a separate stream adds bounded rotations.

    No new packet positions, ray lengths, crown fields, or fill marks are made.
    Count-only is a literal subset. Angle-only changes rotate retained complete
    paths at their original start points, preserving their length and shape.
    """
    source=old.foliage(family,'fans',lobes,season,seed,height)
    groups=defaultdict(list)
    for m in source:groups[m.key.rsplit('-',1)[0]].append(m)
    kept=[];packets=[]
    for key,available in groups.items():
        m=len(available);rng=old.rng_for(seed,family+'/'+key+'/touch-count')
        requested=m if canopy=='v02-control' else int(rng.choice([2,3,4,5],p=[.06,.14,.30,.50]))
        count=m if canopy=='v02-control' else min(m,requested)
        if canopy!='v02-control' and count<2:count=0
        # Spread retained rays across the original fan instead of deleting one
        # entire side; the original direction and packet span remain visible.
        indices=np.round(np.linspace(0,m-1,count)).astype(int) if count else []
        retained=[]
        for idx in indices:
            mark=deepcopy(available[idx]);delta=0.
            if canopy=='count-angle':
                jitter=old.rng_for(seed,mark.key+'/small-angle')
                delta=float(jitter.choice([-1,1])*jitter.uniform(5,angle_limit_deg))
                mark.xy=mark.xy[0]+old.rotate(mark.xy-mark.xy[0],np.deg2rad(delta))
            # Retain exact component keys to trace every touch to V02.
            lobe_key=key.split('/fan/')[0]
            lobe=next(l for l in lobes if l['key']==lobe_key)
            mark.parent=lobe['source_branch'];kept.append(mark)
            retained.append({'key':mark.key,'rotation_deg':delta})
        packets.append({'key':key,'available_touches':m,'requested_touches':requested,
                        'retained_touches':count,'touches':retained})
    return kept,{'base_algorithm':'Immutable V02 directional-fan foliage',
                 'source_foliage_paths':len(source),'retained_foliage_paths':len(kept),
                 'retained_fraction':len(kept)/max(1,len(source)),
                 'angle_limit_deg':angle_limit_deg if canopy=='count-angle' else 0,
                 'packet_histogram':dict(Counter(p['retained_touches'] for p in packets)),
                 'packets':packets,'post_overlap_packet_counts_may_be_lower':True}


def make_tree(family='broadleaf',root=(90,155),height=95,season='spring',seed=20261017,
              accent='none',identity='tree-0',depth='near',canopy='count-2-5',posture='auto',angle_limit_deg=10):
    if family not in old.FAMILIES or season not in old.SEASONS or depth not in ('near','middle'):
        raise ValueError('unknown family, season or depth')
    if canopy not in CANOPIES or posture not in ('auto',)+POSTURES or accent not in old.ACCENTS:
        raise ValueError('unknown pattern, posture or operator')
    if not 5<=angle_limit_deg<=15:raise ValueError('small-angle limit must be 5–15 degrees')
    root=np.asarray(root,float);height=float(height);seed=int(seed)
    if root.shape!=(2,) or not np.isfinite(root).all() or not np.isfinite(height) or height<20:
        raise ValueError('finite root and height >=20 mm required')
    # Exact old geometry constructs the crown and its terminal scaffold.
    _,old_axis,ends=old.skeleton(family,height,seed,accent,'segmented')
    lobes=old.canopy_lobes(family,height,old_axis,ends,season,accent,seed)
    for l in lobes:
        idx=int(np.argmin(np.linalg.norm(ends-l['center'],axis=1)))
        l['source_branch']='axis' if l['key']=='apex' else f'basal-{idx-3}' if family=='understory' and idx>=3 else f'arm-{idx}'
    marks,structure=constructed_structure(family,height,seed,accent,depth,posture)
    foliage,diagnostics=refine_foliage(family,lobes,season,seed,height,canopy,angle_limit_deg)
    marks+=foliage
    for m in marks:m.xy+=root;m.owner=identity
    for l in lobes:l['center']+=root
    structure['axis_nodes_mm']=(np.array(structure['axis_nodes_mm'])+root).tolist()
    structure['members']={k:(np.array(p)+root).tolist() for k,p in structure['members'].items()}
    structure['branch_terminals_mm']=(np.array(structure['branch_terminals_mm'])+root).tolist()
    return growth.GrowthTree(identity,family,canopy,season,seed,root,height,marks,lobes,accent,structure,diagnostics)


def vector_records(marks,trees):
    result=old.vector_records(marks,trees)
    by_id={t.identity:t for t in trees}
    for s in result:
        s['id']=s['id'].replace('catalog-v02/','catalog-v05/',1)
        s['catalog_version']='0.5'
        t=by_id[s['source_root_id']]
        s['trunk_grammar']='constructed-body';s['growth_posture']=t.structure['posture']
    return result
