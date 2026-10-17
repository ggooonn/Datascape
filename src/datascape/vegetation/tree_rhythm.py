"""v06 catalog: coherent pad omissions, rigid units and articulated growth.

V02-derived v05 source candidates and growth axes remain immutable inputs.
Only independent catalog objects are constructed; no scene model is imported.
"""
from collections import defaultdict, Counter
from copy import deepcopy
import numpy as np
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_pattern as pattern
from datascape.vegetation import tree_growth as growth
from datascape.strokes.vector import resample

VERSIONS=('v05','density','articulated')
PAD_RETENTION={'dense':.98,'light':.82,'open':.62}


def pad_units(source,seed,force_remnant=False,rotation_limit_deg=8,pad_retention=None):
    """Keep coherent spatial subsets of whole 2–5-touch units.

    A nearest normalized pad owns each unit, including units originating in an
    overlapping pad. Thus a neighboring dense pad cannot refill an omitted
    sector. Ranking favors cores and avoids random independent dot thinning.
    """
    fractions=PAD_RETENTION if pad_retention is None else pad_retention
    lobes=source.lobes
    center=np.average([l['center'] for l in lobes],axis=0,weights=[l['weight'] for l in lobes])
    rng=old.rng_for(seed,source.family+'/pad-hierarchy')
    distances=np.linalg.norm(np.array([l['center'] for l in lobes])-center,axis=1)
    dense=int(np.argmin(distances))
    outboard=distances*rng.uniform(.75,1.25,len(lobes));outboard[dense]=-1
    opened=int(np.argmax(outboard))
    states=['light']*len(lobes);states[dense]='dense';states[opened]='open'
    if len(lobes)>3:
        choices=[i for i in range(len(lobes)) if i not in (dense,opened)]
        states[min(choices,key=lambda i:distances[i])]='dense'
    if force_remnant:
        choices=[i for i in range(len(lobes)) if i not in (dense,opened)] or [opened]
        remnant=max(choices,key=lambda i:distances[i]);states[remnant]='remnant'
    groups=defaultdict(list)
    for m in source.marks:
        if m.part=='foliage-field':groups[m.key.rsplit('-',1)[0]].append(m)
    owned=defaultdict(list)
    for key,marks in groups.items():
        pivot=np.mean([m.xy[0] for m in marks],axis=0)
        local=[old.rotate((pivot-l['center'])[None,:],-l['angle'])[0]/l['radii'] for l in lobes]
        radii=[np.linalg.norm(q) for q in local];owner=int(np.argmin(radii));q=local[owner];l=lobes[owner]
        external=old.rotate((l['center']-center)[None,:],-l['angle'])[0]/l['radii']
        external/=max(np.linalg.norm(external),1e-9)
        facing=float(q@external)
        # Smooth score fields select connected cores/shoulders; the open pad
        # has one deliberate outward omission rather than a peppered boundary.
        score=1-radii[owner]+.045*np.sin(q[0]*4+.7)+.035*np.cos(q[1]*5-.3)
        if states[owner]=='open':score-=.8*max(0,facing-.10)
        if states[owner]=='remnant':score-=.25*np.linalg.norm(q-np.array([-.08,.04]))
        owned[owner].append({'key':key,'marks':marks,'pivot':pivot,'q':q,'radius':float(radii[owner]),'score':float(score)})
    selected=set();pad_records=[]
    for i,l in enumerate(lobes):
        candidates=owned[i];state=states[i]
        count=min(4,len(candidates)) if state=='remnant' else int(np.ceil(len(candidates)*fractions[state]))
        chosen=sorted(candidates,key=lambda x:(-x['score'],x['key']))[:count]
        selected.update(u['key'] for u in chosen)
        def rate(items,which):
            subset=[u for u in items if (u['radius']<=.55 if which=='core' else u['radius']>.72)]
            return {'available':len(subset),'retained':sum(u['key'] in selected for u in subset)}
        pad_records.append({'key':l['key'],'state':state,'available_units':len(candidates),'retained_units':len(chosen),
                            'core':rate(candidates,'core'),'edge':rate(candidates,'edge')})
    marks=[];units=[]
    for owner,items in owned.items():
        for u in items:
            keep=u['key'] in selected
            angle=float(old.rng_for(seed,u['key']+'/unit-rotation').uniform(-rotation_limit_deg,rotation_limit_deg)) if keep else 0.
            if keep:
                for original in u['marks']:
                    m=deepcopy(original)
                    m.xy=u['pivot']+old.rotate(m.xy-u['pivot'],np.deg2rad(angle));marks.append(m)
            units.append({'key':u['key'],'owner_pad':lobes[owner]['key'],'state':states[owner],
                          'radius_fraction':u['radius'],'retained':keep,'touch_count':len(u['marks']),
                          'rotation_deg':angle,'pivot_mm':u['pivot'].tolist()})
    return marks,{'source_version':'v05 C1 / V02 fans / 2–5-touch units','source_foliage_paths':sum(len(g) for g in groups.values()),
                  'retained_foliage_paths':len(marks),'source_units':len(groups),'retained_units':len(selected),
                  'rotation_limit_deg':rotation_limit_deg,'rotation_mode':'One rigid rotation for the complete unit',
                  'pads':pad_records,'units':units,'pad_retention':dict(fractions),'remnant_operator':force_remnant,
                  'omission_model':'Pad ownership + core-first spatial ranking + one outward open sector'}


def articulated_contours(center,radius,key,seed,growth_joints=(),branch_joints=(),branch=False,depth='near',parent=None):
    """Local narrowing and widening, plus actual fork collars on both sides."""
    p=resample(center,.4);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];u=arc/max(arc[-1],1e-9)
    tangent=np.gradient(p,axis=0)
    for j in range(2):tangent[:,j]=np.convolve(np.pad(tangent[:,j],(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-9)
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    fraction=lambda point:float(u[np.argmin(np.linalg.norm(p-point,axis=1))])
    gj=[fraction(q) for q in growth_joints];bj=[fraction(q) for q in branch_joints]
    rng=old.rng_for(seed,key+'/articulation')
    neck=float(rng.uniform(.25,.43));shoulder=float(rng.uniform(.56,.73))
    # Pinch is offset from physical branch collars, which reopen the outline.
    profile=1-.77*np.exp(-((u-neck)/.065)**2)+.24*np.exp(-((u-shoulder)/.10)**2)
    if branch:profile=1-.30*np.exp(-((u-.58)/.09)**2)
    base=radius*(1-.78*u)*profile
    sides=[];out=[]
    for side in (-1,1):
        offset=base*(1.12 if side==1 else .85)*(1+.045*np.sin(21*u+side))
        for j,f in enumerate(gj):offset*=1+(.27 if (j+side)%2 else .12)*np.exp(-((u-f)/.045)**2)
        for j,f in enumerate(bj):offset+=radius*(.35 if (j+side)%2 else .15)*np.exp(-((u-f)/.035)**2)
        if branch:offset*=1+(.75 if side==1 else .22)*np.exp(-((u-.065)/.10)**2)
        sides.append(offset)
        edge=p+normal*(side*offset)[:,None]
        if branch:intervals=[(.03,.68),(.70,1)] if side==-1 else [(.025,1)]
        else:
            cuts=[.28,.69] if side==1 else [.21,.54,.84]
            for k,f in enumerate(cuts):
                if any(abs(f-j)<.035 for j in gj+bj):cuts[k]+=.055
            starts=[0]+[f+.005 for f in cuts];ends=[f-.005 for f in cuts]+[1]
            intervals=list(zip(starts,ends))
        for i,(a,b) in enumerate(intervals):
            q=old.path_part(edge,a,b)
            if old.length(q)>=1.6:out.append(old.Mark(f'{key}/side{side}/{i}',q,.41 if side==1 else .29,
                                                       'branch-contour' if branch else 'trunk-contour',parent))
    if depth=='near':
        candidates=(bj[::2]+gj[:1]) if not branch else [.07]
        for i,f in enumerate(candidates):
            at=int(f*(len(p)-1));r=base[at];sign=1 if i%2 else -1
            length=max(2.1,min(4.2,radius*1.8))
            # One broken grain tendency at selected joints; no rings or bark fill.
            q=np.array([p[at]+normal[at]*r*.30*sign-tangent[at]*length*.45,
                        p[at]+normal[at]*r*.10*sign,
                        p[at]+normal[at]*r*.34*sign+tangent[at]*length*.55])
            if old.length(q)>=2:out.append(old.Mark(f'{key}/joint-grain/{i}',q,.20,'bark-grain',key))
    return out,{'minimum_side_spacing_mm':float(np.min(sides[0]+sides[1])),
                'maximum_side_spacing_mm':float(np.max(sides[0]+sides[1])),
                'neck_fraction':neck,'shoulder_fraction':shoulder,'fork_fractions':bj,
                'spacing_profile_mm':np.column_stack([u,sides[0]+sides[1]])[::max(1,len(p)//30)].tolist()}


def bezier(points,step=.35):
    p=np.asarray(points,float);t=np.linspace(0,1,max(8,int(old.length(p)/step)))[:,None]
    return (1-t)**3*p[0]+3*(1-t)**2*t*p[1]+3*(1-t)*t*t*p[2]+t**3*p[3]


def growth_details(source):
    structure=deepcopy(source.structure);members={k:np.array(p) for k,p in structure['members'].items()}
    nodes=np.array(structure['axis_nodes_mm']);height=source.height;seed=source.seed;depth=structure['depth_role']
    axis=np.vstack([p if i==0 else p[1:] for i,(k,p) in enumerate((x for x in members.items() if x[0].startswith('axis/')))])
    arms=[k for k in members if k.startswith('arm-')]
    radius=height*{'hero-pine':.022,'broadleaf':.018,'understory':.012}[source.family]
    origins=[members[k][0] for k in arms]
    marks,width_info=articulated_contours(axis,radius,'axis',seed,nodes[1:-1],origins,depth=depth)
    terminal=[];rng=old.rng_for(seed,source.family+'/terminal-behavior')
    for i,key in enumerate(arms):
        origin=members[key][0];tip=members[key][-1];d=tip-origin;side=1 if d[0]>=0 else -1
        state=str(rng.choice(['rise','level','droop'],p=([.38,.27,.35] if source.family=='hero-pine' else [.42,.25,.33])))
        elbow=origin+d*np.array([.58,.67])+[0,-height*.012]
        bend=float(rng.uniform(.80,1.10))
        shoulder=tip+np.array([-side*max(abs(d[0])*.17,height*.035),height*bend*({'rise':.045,'level':0,'droop':-.032}[state])])
        a=growth.segment(origin,elbow,height*.006*side,step=.4)
        b=bezier([elbow,elbow+(tip-elbow)*.32,shoulder,tip])
        p=np.vstack([a,b[1:]]);members[key]=p
        mm,_=articulated_contours(p,radius*.46,key,seed,[elbow],branch=True,depth=depth,parent='axis');marks+=mm
        vector=tip-shoulder
        terminal.append({'key':key,'state':state,'tip_mm':tip.tolist(),
                         'end_tangent_xy':vector.tolist(),'downward_tangent':bool(vector[1]>1e-8)})
        if depth=='near':
            for j,f in enumerate([.50,.77]):
                at=p[int(f*(len(p)-1))]
                # The second twig follows the terminal state; not all forks rise.
                dy=height*(.06 if state=='droop' and j==1 else 0 if state=='level' and j==1 else -.11)
                delta=np.array([side*height*(.085 if j==0 else -.055),dy])
                q=growth.segment(at,at+delta,height*.006*(1 if j else -1))
                if old.length(q)>=2:marks.append(old.Mark(f'{key}/twig-{j}',q,.22 if j==0 else .18,'twig',key))
    # Preserve basal supports and limited fracture/dead-limb operators.
    marks += [deepcopy(m) for m in source.marks if m.key.startswith('basal-') or m.part in ('fracture','dead-limb')]
    structure.update(members={k:p.tolist() for k,p in members.items()},terminal_behavior=terminal,
                     contour_spacing=width_info,body_grammar='variable-width body with physical fork collars')
    return marks,structure


def make_tree(family='broadleaf',root=(90,155),height=95,season='spring',seed=20261017,
              accent='none',identity='tree-0',depth='near',posture='auto',version='articulated',rotation_limit_deg=8,remnant_pad=False,pad_retention=None):
    if version not in VERSIONS:raise ValueError('unknown refinement control')
    if not np.isfinite(rotation_limit_deg) or not 0<=rotation_limit_deg<=10:raise ValueError('unit rotation must be within 10 degrees')
    keep=PAD_RETENTION if pad_retention is None else pad_retention
    if set(keep)!=set(PAD_RETENTION) or not 0<keep['open']<=keep['light']<=keep['dense']<=1:
        raise ValueError('pad retention must satisfy 0 < open <= light <= dense <= 1')
    legacy_accent='none' if accent=='reduced-canopy' else accent
    source=pattern.make_tree(family,root,height,season,seed,legacy_accent,identity,depth,canopy='count-2-5',posture=posture)
    if version=='v05':return source
    foliage,diagnostics=pad_units(source,int(seed),accent=='reduced-canopy' or remnant_pad,rotation_limit_deg,keep)
    if version=='density':marks=[deepcopy(m) for m in source.marks if m.part!='foliage-field'];structure=deepcopy(source.structure)
    else:marks,structure=growth_details(source)
    marks+=foliage
    for m in marks:m.owner=identity
    structure['refinement_version']=version
    return growth.GrowthTree(identity,family,'pad-rhythm',season,int(seed),np.asarray(root,float),float(height),
                             marks,deepcopy(source.lobes),accent,structure,diagnostics)


def vector_records(marks,trees):
    records=pattern.vector_records(marks,trees)
    by_id={t.identity:t for t in trees}
    for r in records:
        t=by_id[r['source_root_id']]
        if t.canopy=='pad-rhythm':
            r['id']=r['id'].replace('catalog-v05/','catalog-v06/',1);r['catalog_version']='0.6'
            r['refinement_version']=t.structure['refinement_version']
            r['trunk_grammar']=t.structure.get('body_grammar','v05 constructed body')
            r['canopy_pad_reduction']=t.canopy_diagnostics['remnant_operator']
    return records
