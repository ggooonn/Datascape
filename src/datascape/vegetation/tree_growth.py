"""Compact v03 growth graphs and branch-directed stroke fields.

The immutable v02 vocabulary supplies vector records, local overlap and wash
intent. This module replaces global growth splines and repeated fan packets.
It never imports scene placement, terrain retention, hardware or material plans.
"""
from dataclasses import dataclass, field
import numpy as np
from datascape.vegetation import tree_catalog as old
from datascape.strokes.vector import resample


@dataclass
class GrowthTree(old.Tree):
    structure: dict = field(default_factory=dict)
    canopy_diagnostics: dict = field(default_factory=dict)


def segment(a,b,bow=0,step=.5):
    """A mildly bowed local growth segment; no interpolation across joints."""
    a=np.asarray(a,float);b=np.asarray(b,float);d=b-a
    normal=np.array([-d[1],d[0]])/max(np.linalg.norm(d),1e-9)
    u=np.linspace(0,1,max(3,int(np.linalg.norm(d)/step)+1))[:,None]
    return a+u*d+np.sin(np.pi*u)*normal*bow


def normal_offsets(p,r0,r1):
    tangent=np.gradient(p,axis=0);normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
    r=np.linspace(r0,r1,len(p))
    return normal,r


def contours(p,r0,r1,key,part,parent,seed,broken=True):
    """Unequal side tendencies follow a single growth member, not a whole axis."""
    normal,r=normal_offsets(p,r0,r1);rng=old.rng_for(seed,key+'/edges');out=[]
    for side in [-1,1]:
        edge=p+normal*(side*r*(1.12 if side==1 else .86))[:,None]
        if broken and side==-1 and old.length(p)>12:
            at=rng.uniform(.45,.68);intervals=[(0,at-.045),(at+.035,1)]
        else:intervals=[(0,1)]
        for j,(a,b) in enumerate(intervals):
            q=old.path_part(edge,a,b)
            if old.length(q)>=1.8:out.append(old.Mark(f'{key}/edge{side}/{j}',q,.40 if side==1 else .28,part,parent))
    if r0>.8 and old.length(p)>9:
        a=int(.17*(len(p)-1));b=int(.60*(len(p)-1))
        q=p[a:b+1]+normal[a:b+1]*(r0*.22)
        if old.length(q)>=2:out.append(old.Mark(key+'/grain',q,.17,'bark-grain',key))
    return out


def axis_nodes(family,height,seed,accent):
    rng=old.rng_for(seed,family+'/growth')
    n=int(rng.choice([2,3,4],p=([.05,.65,.30] if family=='hero-pine' else [.20,.65,.15])))
    if family=='understory':n=2
    sign=int(rng.choice([-1,1]));lean=float(rng.uniform(-11,11))
    base=np.array([-12,22,-9,19])[:n]*sign+lean+rng.uniform(-6,6,n)
    if accent=='bent':base+=18*sign
    fractions=rng.uniform(.7,1.25,n)*np.linspace(1.25,.75,n);fractions/=fractions.sum()
    total=height*{'hero-pine':.92,'broadleaf':.75,'understory':.64}[family]
    if accent=='suppressed':total*=.73
    nodes=[np.zeros(2)]
    for angle,f in zip(base,fractions):
        rad=np.deg2rad(angle);nodes.append(nodes[-1]+total*f*np.array([np.sin(rad),-np.cos(rad)]))
    nodes=np.asarray(nodes)
    if accent=='broken-top':nodes[-1]=nodes[-2]+(nodes[-1]-nodes[-2])*.46
    return nodes,{'segment_count':n,'angles_from_vertical_deg':base.tolist(),
                  'length_fractions':fractions.tolist(),'dominant_direction':sign,'lean_deg':lean}


def build_structure(family,height,seed,accent,depth):
    nodes,morph=axis_nodes(family,height,seed,accent)
    marks=[];members={};supports=[];rng=old.rng_for(seed,family+'/branches')
    radius=height*{'hero-pine':.021,'broadleaf':.017,'understory':.013}[family]
    for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        f0=i/(len(nodes)-1);f1=(i+1)/(len(nodes)-1)
        p=segment(a,b,np.linalg.norm(b-a)*(.045 if i%2 else -.055))
        key=f'axis/{i}';members[key]=p
        marks+=contours(p,radius*(1-.76*f0),radius*(1-.76*f1),key,'trunk-contour',None,seed)
        if i and depth=='near':
            d=(b-a)/np.linalg.norm(b-a);normal=np.array([-d[1],d[0]])
            q=np.array([a-normal*radius*.7,a+d*radius*.45,a+normal*radius*.4])
            if old.length(q)>=1.8:marks.append(old.Mark(key+'/joint',q,.30,'joint-accent',f'axis/{i-1}'))
    if accent=='broken-top':
        top=nodes[-1];q=np.array([top+[-radius*.6,.5],top+[0,-.3],top+[radius*.5,.3]])
        if old.length(q)>=1.8:marks.append(old.Mark('top-fracture',q,.34,'fracture','axis'))
    branch_count=4 if family=='hero-pine' else 3
    if depth=='middle':branch_count-=1
    n=len(nodes)-1
    # Supports prefer growth joints but include one off-joint dominant arm.
    last_side=-morph['dominant_direction']
    for i in range(branch_count):
        idx=min(n-1,1+int(i*max(n-2,1)/max(branch_count-1,1)))
        if i==0:
            idx=0;t=.68
        else:t=rng.uniform(.07,.28)
        key=f'axis/{idx}';parent=members[key]
        origin=parent[int(t*(len(parent)-1))].copy()
        side=-last_side if rng.random()<.66 else last_side;last_side=side
        reach=height*rng.uniform(.23,.38)*(1-.10*i)
        if family=='understory':reach*=.88
        if accent=='suppressed':reach*=.70
        rise=reach*rng.uniform(.30,.90)
        elbow=origin+np.array([side*reach*rng.uniform(.40,.64),-rise*rng.uniform(.28,.55)])
        end=origin+np.array([side*reach,-rise])
        p=np.vstack([segment(origin,elbow,-height*.014),segment(elbow,end,height*.012)[1:]])
        bkey=f'arm/{i}';members[bkey]=p
        if depth=='near':marks+=contours(p,radius*.43,radius*.10,bkey,'branch-contour',key,seed,broken=False)
        else:marks.append(old.Mark(bkey,p,.27,'branch-contour',key))
        # A small number of unequal forks; no repeated paired terminal tufts.
        if depth=='near' or i%2==0:
            a=p[int(rng.uniform(.45,.75)*(len(p)-1))]
            d=height*np.array([side*rng.uniform(-.07,.11),-rng.uniform(.09,.17)])
            q=segment(a,a+d,height*.006)
            if old.length(q)>=2:marks.append(old.Mark(bkey+'/fork',q,.19,'twig',bkey))
        vector=end-elbow;angle=float(np.arctan2(vector[1],vector[0]))
        supports.append({'key':bkey,'center':end,'flow_angle':angle,'weight':1-.11*i,
                         'source_branch':bkey,'role':'terminal' if i%2 else 'body'})
    supports.append({'key':'apex','center':nodes[-1],
                     'flow_angle':float(np.arctan2(*(nodes[-1]-nodes[-2])[::-1])),
                     'weight':.7,'source_branch':f'axis/{n-1}','role':'terminal'})
    if family=='understory':
        for j,side in enumerate([-1,1]):
            a=np.array([side*height*.05,0]);b=a+height*np.array([side*.12,-.28]);end=b+height*np.array([side*.19,-.26])
            p=np.vstack([segment(a,b,0),segment(b,end,height*.008)[1:]])
            key=f'basal/{j}';members[key]=p
            marks+=contours(p,radius*.7,radius*.10,key,'trunk-contour',None,seed,broken=False)
            supports.append({'key':key,'center':end,'flow_angle':float(np.arctan2(*(end-b)[::-1])),
                             'weight':.72,'source_branch':key,'role':'body'})
    if accent=='dead-limb':
        at=nodes[1];end=at+height*np.array([-morph['dominant_direction']*.32,-.045])
        p=np.vstack([segment(at,at+(end-at)*.6,0),segment(at+(end-at)*.6,end,0)[1:]])
        marks.append(old.Mark('dead-limb',p,.30,'dead-limb','axis/0'))
    if depth=='middle':marks=[m for m in marks if m.part not in ('bark-grain','joint-accent','twig')]
    return marks,nodes,members,supports,morph


def crown_fields(family,height,supports,season,seed,accent):
    rng=old.rng_for(seed,family+'/fields');extent=old.SEASONS[season]['extent']/.92
    lobes=[]
    # Branch-supported masses overlap with one bridge, rather than one icon per tip.
    for i,s in enumerate(supports):
        if family=='hero-pine':rx,ry=height*rng.uniform(.17,.24),height*rng.uniform(.075,.115)
        elif family=='broadleaf':rx,ry=height*rng.uniform(.20,.29),height*rng.uniform(.13,.21)
        else:rx,ry=height*rng.uniform(.23,.32),height*rng.uniform(.13,.20)
        if accent=='suppressed':rx*=.72;ry*=.72
        at=s['center']+np.array([0,-height*.025])
        # Keep a transverse field bias while allowing the branch to steer it.
        flow=s['flow_angle'];undirected=(flow+np.pi/2)%np.pi-np.pi/2
        angle=float(.32*undirected+rng.uniform(-.18,.18))
        lobes.append({'key':s['key'],'center':at,'radii':np.array([rx,ry])*extent,
                      'angle':angle,'weight':s['weight'],'flow_angle':flow,
                      'source_branch':s['source_branch'],'role':s['role']})
    if len(supports)>2:
        pair=sorted(supports,key=lambda s:s['center'][1])[:3]
        at=np.mean([s['center'] for s in pair],axis=0)
        lobes.append({'key':'bridge','center':at,'radii':height*np.array([.22,.13])*extent,
                      'angle':float(rng.uniform(-.16,.16)),'weight':.65,
                      'flow_angle':pair[0]['flow_angle'],'source_branch':pair[0]['source_branch'],'role':'bridge'})
    if accent=='broken-top':lobes=[l for l in lobes if l['key']!='apex']
    if accent=='reduced-canopy':
        keep=[l for i,l in enumerate(lobes) if i!=1]
        for l in keep:l['weight']*=.65
        lobes=keep
    return lobes


def stroke_field(family,lobes,height,season,seed,depth):
    """Role/direction-driven packets: 1/2/3/5 strokes, not a repeated fan symbol."""
    density=old.SEASONS[season]['density']/.68
    if season=='winter':density=.26 if family=='hero-pine' else 0
    base={'hero-pine':150,'broadleaf':180,'understory':78}[family]
    reference=55 if family=='understory' else 85
    budget=max(0,int(base*(height/reference)**1.20*density*(.70 if depth=='middle' else 1)))
    weights=np.array([np.prod(l['radii'])*l['weight'] for l in lobes]);weights/=max(weights.sum(),1e-9)
    marks=[];packets=[];claimed={}
    for l,weight in zip(lobes,weights):
        rng=old.rng_for(seed,family+'/'+l['key']+'/field')
        target=int(budget*weight);count=0;packet=0
        while count<target and packet<target*3+1:
            k=packet;packet+=1
            # An ordered coverage sequence, compressed unevenly into local masses.
            theta=k*2.399963229728653+rng.uniform(-.16,.16)
            phase=((k*.61803398875+.17)%1)
            rr=(.55*np.sqrt(phase/.60) if phase<.60 else
                .55+.18*(phase-.60)/.30 if phase<.90 else .73+.15*(phase-.90)/.10)
            local=np.array([np.cos(theta),np.sin(theta)])*l['radii']*rr
            at=l['center']+old.rotate(local[None,:],l['angle'])[0]
            role='edge' if rr>.68 else l['role']
            kind=rng.choice(['strand','fork','sweep'],p=([.45,.15,.40] if role=='bridge' else [.52,.35,.13]))
            n=int(rng.choice([1,2,3,5],p=([.66,.25,.08,.01] if role=='edge' else [.30,.38,.27,.05])))
            if kind=='sweep':n=min(n,2)
            if depth=='middle':n=min(n,3)
            if count+n>target:n=target-count
            if n<=0:break
            branch=(l['flow_angle']+np.pi/2)%np.pi-np.pi/2
            radial=np.arctan2(local[1]/l['radii'][1],local[0]/l['radii'][0])
            direction=l['angle']+.28*branch+.20*radial+rng.uniform(-.48,.48)
            span=height*rng.uniform(.034,.082)*(1.35 if kind=='sweep' else 1)
            if depth=='middle':span=max(2.1,span)
            span=max(2.0,span)
            curvature=rng.uniform(-.14,.18)
            actual=0
            for j in range(n):
                t=np.linspace(-.5,.5,9)
                if kind=='fork':
                    angle=direction+(j-(n-1)/2)*rng.uniform(.18,.44)
                    shape=np.sin(np.pi*(t+.5)**rng.uniform(.65,1.65))
                    p=np.column_stack([t*span,shape*span*curvature*rng.uniform(.30,1.10)])
                    p[:,0]+=span*.18*j/max(n,1)
                else:
                    angle=direction+rng.uniform(-.24,.24)
                    shape=np.sin(np.pi*(t+.5)**rng.uniform(.65,1.65))
                    bend=curvature*rng.uniform(-.55,1.15)
                    p=np.column_stack([t*span*rng.uniform(.80,1.12),
                         shape*span*bend+(j-(n-1)/2)*rng.uniform(.55,1.0)])
                p=at+old.rotate(p,angle)
                cells={tuple(np.floor(q/.9).astype(int)) for q in resample(p,.6)}
                if cells and sum(c in claimed for c in cells)/len(cells)>.70:continue
                if old.length(p)<1.9:continue
                for c in cells:claimed[c]=True
                key=f'field/{l["key"]}/{k}/{j}'
                marks.append(old.Mark(key,p,float(rng.uniform(.19,.28)), 'foliage-field',l['source_branch']))
                actual+=1;count+=1
            if actual:packets.append({'lobe':l['key'],'role':role,'kind':kind,'strokes':actual,
                                      'angle_deg':float(np.rad2deg(direction)),'span_mm':span,'radius_fraction':rr})
    return marks,{'requested_path_budget':budget,'retained_foliage_paths':len(marks),'packets':packets,
                  'packet_stroke_counts':{str(n):sum(p['strokes']==n for p in packets) for n in [1,2,3,4,5]},
                  'spacing_note':'Local one-mm near-coincidence suppression; crossings remain possible'}


def make_tree(family='broadleaf',root=(90,150),height=85,season='spring',seed=20261017,
              accent='none',identity='tree-0',depth='near'):
    if family not in old.FAMILIES or season not in old.SEASONS or depth not in ('near','middle'):
        raise ValueError('unknown family, season or depth')
    if accent not in ('none','bent','broken-top','reduced-canopy','suppressed','dead-limb'):
        raise ValueError('unknown compact variation operator')
    root=np.asarray(root,float)
    if root.shape!=(2,) or not np.isfinite(root).all() or not np.isfinite(height) or height<20:
        raise ValueError('finite root and height >=20 mm required')
    height=float(height);seed=int(seed)
    marks,nodes,members,supports,morph=build_structure(family,height,seed,accent,depth)
    lobes=crown_fields(family,height,supports,season,seed,accent)
    foliage,diagnostics=stroke_field(family,lobes,height,season,seed,depth)
    marks+=foliage
    for m in marks:m.xy+=root;m.owner=identity
    for l in lobes:l['center']+=root
    structure={'axis_nodes_mm':(nodes+root).tolist(),'morphology':morph,'depth_role':depth,
               'members':{key:(p+root).tolist() for key,p in members.items()},
               'source_claim':'Synthetic growth graph; no observed tree or terrain claim'}
    return GrowthTree(identity,family,'directed-field',season,seed,root,height,marks,lobes,accent,structure,diagnostics)


def vector_records(marks,trees):
    records=old.vector_records(marks,trees)
    for s in records:
        if s['canopy_grammar']=='directed-field':
            s['id']=s['id'].replace('catalog-v02/','catalog-v03/',1)
            s['catalog_version']='0.3'
    return records
