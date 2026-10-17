"""v09 catalog: bounded scale calibration and an experimental hanging form.

No terrain, scene or hardware system is imported. P/B/U controls delegate to
the immutable v08 objects. W is a structural architecture on the B carrier,
not a botanical species or a change to the production family registry.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import dataclass
import math
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_growth as growth
from datascape.vegetation import tree_rhythm as rhythm
from datascape.vegetation import tree_plot_scale as physical
from datascape.vegetation import tree_group_review as previous
from datascape.strokes.vector import resample,split_at_gate

FORMS={'P':'hero-pine','B':'broadleaf','U':'understory','W':'broadleaf'}
SCALE_KNOTS=(22,45,95,130)
GAINS={'P':(1,1.5,2,2.4),'B':(1,1.3,1.5,1.9),'U':(1,1.15,1.25,1.4),'W':(1,1.1,1.2,1.5)}
W_CAPS={'large':(12,8,2,1),'medium':(6,4,1,1),'small':(2,1,0,0)}


@dataclass(frozen=True)
class GrowthControls:
    """One anatomy control and one fullness modifier, separate from posture.

    stem_ratio changes the lower 30% vertical carrier while translating the
    crown above that join. It is an explicit layout operator, not simulated
    growth. Vigor modifies foliage budget only, not trunk size or damage.
    """
    stem_ratio:float=1.0
    vigor:float=1.0

    def validate(self):
        if not np.isfinite(self.stem_ratio) or not .7<=self.stem_ratio<=1.3:raise ValueError('stem ratio must be 0.7–1.3')
        if not np.isfinite(self.vigor) or not 0<=self.vigor<=1.5:raise ValueError('vigor must be 0–1.5')


def density_gain(form,height):return float(np.interp(height,SCALE_KNOTS,GAINS[form]))


def stem_layout(source,ratio):
    if ratio==1:return source
    t=deepcopy(source);root=t.root;join=-.30*t.height
    def warp(xy):
        p=np.asarray(xy,float).copy();y=p[...,1]-root[1]
        p[...,1]=root[1]+np.where(y>=join,y*ratio,y+join*(ratio-1));return p
    for m in t.marks:m.xy=warp(m.xy)
    for l in t.lobes:l['center']=warp(l['center'])
    s=t.structure
    for key in ['axis_nodes_mm','branch_terminals_mm']:
        if key in s:s[key]=warp(s[key]).tolist()
    s['members']={k:warp(p).tolist() for k,p in s['members'].items()}
    for item in s['terminal_behavior']:
        p=np.array(s['members'][item['key']]);item['tip_mm']=p[-1].tolist()
        item['end_tangent_xy']=(p[-1]-p[-2]).tolist();item['downward_tangent']=bool(p[-1,1]>p[-2,1])
    s['stem_layout']={'ratio':ratio,'join_fraction':.30,'model':'Lower carrier scale plus upper crown translation'}
    return t


def terminal_droop(source):
    """All arm end tangents droop, but the existing crown anchors stay fixed."""
    t=deepcopy(source)
    for key,points in t.structure['members'].items():
        if not key.startswith('arm-'):continue
        p=np.asarray(points);start=p[int(.58*(len(p)-1))];tip=p[-1];side=1 if tip[0]>start[0] else -1
        shoulder=tip+[-side*t.height*.035,-t.height*.045]
        q=rhythm.bezier([start,start+(tip-start)*.35,shoulder,tip]);p=np.vstack([p[:int(.58*(len(p)-1))],q])
        t.structure['members'][key]=p.tolist()
        for item in t.structure['terminal_behavior']:
            if item['key']==key:item.update(state='droop',tip_mm=tip.tolist(),end_tangent_xy=(tip-shoulder).tolist(),downward_tangent=True)
    t.structure['architecture']='B with terminal droop only; original crown supports retained'
    return t


def hanging_source(source):
    """Arch-bearing arms and actual descending secondary members, not leaf jitter."""
    t=deepcopy(source);h=t.height;r=t.root;s=t.structure
    members={k:np.asarray(p) for k,p in s['members'].items() if k.startswith('axis/')}
    axis=np.vstack([p if i==0 else p[1:] for i,p in enumerate(members.values())])
    marks=[];lobes=[];unit_info=[];pad_info=[];terminal=[];ends=[]
    cls=physical.size_class(h);per_arm=3 if cls=='large' else 2 if cls=='medium' else 1
    for i,(f,side,reach) in enumerate([(1.,-1,.30),(.82,1,.38),(.50,-1,.16)]):
        origin=axis[min(len(axis)-1,int(f*(len(axis)-1)))];tip=origin+[side*reach*h,h*(.055 if i==0 else .025 if i==1 else -.005)]
        elbow=origin+[side*h*(.12 if i==0 else .21 if i==1 else .075),-h*(.09 if i==0 else .07 if i==1 else .035)]
        # Unequal growth episodes avoid three repeated smooth umbrella arcs.
        first=growth.segment(origin,elbow,side*h*(.012 if i==1 else .003))
        second=growth.segment(elbow,tip,-side*h*(.020 if i==0 else .008))
        arm=np.vstack([first,second[1:]]);key=f'arm-{i}';members[key]=arm;ends.append(tip)
        terminal.append({'key':key,'state':'droop','tip_mm':tip.tolist(),'end_tangent_xy':(tip-arm[-2]).tolist(),'downward_tangent':bool(tip[1]>arm[-2,1])})
        pad_key=f'hanging-pad-{i}';pendants=[]
        fractions=[.32,.61,.88] if per_arm==3 else [.38,.84] if per_arm==2 else [.63]
        for j,fraction in enumerate(fractions):
            start=arm[int(fraction*(len(arm)-1))]
            rng=old.rng_for(t.seed,f'W/pendant/{i}/{j}')
            drop=h*float(rng.uniform(.17,.27));drift=side*h*float(rng.uniform(.02,.07))
            elbow=start+[drift*.35+(-1 if j%2 else 1)*h*.018,drop*.36];end=start+[drift,drop]
            p=np.vstack([growth.segment(start,elbow,side*h*.007),growth.segment(elbow,end,-side*h*.006)[1:]])
            pkey=f'pendant-{i}-{j}';members[pkey]=p;pendants.append(p)
            count=max(1,int(old.length(p)/3.9))
            for k,at in enumerate(np.linspace(.22,.88,count)):
                ix=min(len(p)-2,max(1,int(at*(len(p)-1))));pivot=p[ix]+[(-1 if k%2 else 1)*1.6,0]
                direction=p[ix+1]-p[ix-1];angle=math.atan2(direction[1],direction[0])
                unit=f'{pad_key}/fan/{j}-{k}'
                rotation=float(old.rng_for(t.seed,unit+'/unit-rotation').uniform(-8,8))
                for ray in range(3):
                    d=2.8+h*float(rng.uniform(.006,.018));a=angle+(ray-1)*.22+np.deg2rad(rotation)
                    begin=pivot+[(ray-1)*.35,0];end_leaf=begin+d*np.array([np.cos(a),np.sin(a)])
                    q=growth.segment(begin,end_leaf,.12*(ray-1))
                    marks.append(old.Mark(f'{unit}-{ray}',q,.22,'foliage-field',pkey,t.identity))
                unit_info.append({'key':unit,'owner_pad':pad_key,'state':['light','dense','open'][i],
                                  'radius_fraction':abs(at-.5)*1.5,'retained':True,'touch_count':3,
                                  'rotation_deg':rotation,'pivot_mm':pivot.tolist()})
        cloud=np.concatenate(pendants);center=(cloud.min(axis=0)+cloud.max(axis=0))/2
        radii=np.maximum((cloud.max(axis=0)-cloud.min(axis=0))/2+[h*.035,h*.025],[2,3])
        lobes.append({'key':pad_key,'center':center,'radii':radii,'angle':0.,'weight':1 if i==1 else .65,'source_branch':key})
        pad_info.append({'key':pad_key,'state':['light','dense','open'][i]})
    s.update(members={k:p.tolist() for k,p in members.items()},terminal_behavior=terminal,
             branch_terminals_mm=np.asarray(ends).tolist(),architecture='W / arch-bearing arms + descending secondaries',
             inherited_family='broadleaf',experimental_form=True)
    t.lobes=lobes;t.marks=marks;t.canopy_diagnostics={'units':unit_info,'pads':pad_info}
    return t


def thin(source,form,gain,width=.8,gap=.5):
    cls=physical.size_class(source.height)
    caps=dict(zip(previous.STATES,W_CAPS[cls] if form=='W' else previous.FAMILY_CAPS[source.family][cls])) if form!='P' else physical.UNIT_CAPS['light'][cls]
    probs=({'large':(.45,.47,.08),'medium':(.60,.35,.05),'small':(.85,.15,0)}[cls] if form=='P' else
           {'large':(.58,.38,.04),'medium':(.72,.26,.02),'small':(.90,.10,0)}[cls] if form=='W' else previous.TOUCH_PROBABILITIES[source.family][cls])
    by_unit=defaultdict(list);grouped=defaultdict(list)
    for m in source.marks:
        if m.part=='foliage-field':by_unit[m.key.rsplit('-',1)[0]].append(m)
    info={u['key']:u for u in source.canopy_diagnostics['units'] if u['retained']}
    for key,marks in by_unit.items():grouped[info[key]['owner_pad']].append((key,marks))
    accepted=[];sampled=[];index=None;minimum=max(2.8,3.5*width)
    ordered=sorted(source.canopy_diagnostics['pads'],key=lambda p:(previous.STATES.index(p['state']),p['key']))
    cached={};counts={p['key']:0 for p in ordered};targets={};records={};selected=set()
    for pad in ordered:
        state=pad['state']
        local_gain=gain if gain<=1 or state=='dense' else 1+.70*(gain-1) if state=='light' else 1
        targets[pad['key']]=int(math.floor(caps[state]*max(0,local_gain)+.5))
        candidates=[]
        for key,available in sorted(grouped[pad['key']],key=lambda x:(info[x[0]]['radius_fraction'],x[0])):
            rng=old.rng_for(source.seed,key+'/physical-unit');n=min(int(rng.choice([1,2,3],p=probs)),len(available))
            slots=[len(available)//2] if n==1 else np.round(np.linspace(0,len(available)-1,n)).astype(int)
            marks=[]
            for slot in slots:
                m=deepcopy(available[slot]);length=old.length(m.xy);target=max(minimum,min(6.2,length))
                m.xy=m.xy[0]+(m.xy-m.xy[0])*target/max(length,1e-9);marks.append(m)
            dense=np.concatenate([resample(m.xy,.2) for m in marks]);candidates.append((key,marks,dense))
            records[key]={'key':key,'pad':pad['key'],'state':state,'touches':n,'retained':False,
                          'reason':'pad-budget','rotation_deg':info[key]['rotation_deg'],'sampled_gap_mm':None}
        cached[pad['key']]=candidates
    # Preserve the current accepted units first, then add physically separated
    # core/shoulder units. Increasing density must not reshuffle the old crown.
    for base_pass in ([True,False] if gain>1 else [False]):
        for pad in ordered:
            cap=caps[pad['state']] if base_pass else targets[pad['key']]
            for key,marks,dense in cached[pad['key']]:
                if key in selected:continue
                distance=float(index.query(dense)[0].min()) if index is not None else None
                reason='pad-budget' if counts[pad['key']]>=cap else 'physical-gap' if distance is not None and distance<width+gap+.2 else 'kept'
                records[key].update(reason=reason,sampled_gap_mm=distance)
                if reason!='kept':continue
                selected.add(key);records[key]['retained']=True;accepted+=marks;counts[pad['key']]+=1
                sampled.append(dense);index=cKDTree(np.concatenate(sampled))
    pads=[{'key':p['key'],'state':p['state'],'base_cap':caps[p['state']],
           'unit_cap':targets[p['key']],'retained_units':counts[p['key']]} for p in ordered]
    records=list(records.values())
    kept=[u for u in records if u['retained']]
    return accepted,{'form':form,'source_units':len(by_unit),'source_foliage_paths':sum(map(len,by_unit.values())),
                     'retained_units':len(kept),'retained_foliage_paths':len(accepted),
                     'unit_touch_histogram':dict(Counter(u['touches'] for u in kept)),
                     'density_gain_requested':gain,'pads':pads,'units':records,'design_width_mm':width,
                     'clear_gap_mm':gap,'minimum_leaf_length_mm':minimum,
                     'physical_plotting_validated':False,'cross_tree_spacing':'not guaranteed'}


def hanging_body(source,width):
    members={k:np.asarray(p) for k,p in source.structure['members'].items()}
    axis=np.vstack([p if i==0 else p[1:] for i,(k,p) in enumerate((x for x in members.items() if x[0].startswith('axis/')))])
    radius=source.height*.014;origins=[p[0] for k,p in members.items() if k.startswith('arm-')]
    marks,audit,envelope=physical.safe_contours(axis,radius,'axis',source.seed,width,origins);audits={'axis':audit}
    for key,p in members.items():
        if key.startswith('arm-'):
            mm,audit,_=physical.safe_contours(p,radius*.4,key,source.seed,width,branch=True);audits[key]=audit
            for m in mm:
                for j,q in enumerate(split_at_gate(m.xy,physical.outside_stem(m.xy,envelope),2)):
                    marks.append(old.Mark(m.key+f'/outside-{j}',q,m.width,m.part,m.parent,source.identity))
        elif key.startswith('pendant-') and old.length(p)>=2.8:
            marks.append(old.Mark(key,p,.22,'branch-contour','arm-'+key.split('-')[1],source.identity))
    s=deepcopy(source.structure);s.update(contour_audit=audits,body_grammar='Thin constructed carrier, arched arms, unequal hanging secondaries')
    for m in marks:m.owner=source.identity
    return marks,s


def make_tree(form='B',root=(110,180),height=95,seed=20261017,identity='tree-0',posture='auto',
              accent='none',profile='candidate',growth_controls=None,architecture='base',design_width_mm=.8,clear_gap_mm=.5):
    if form not in FORMS or profile not in ('current','candidate'):raise ValueError('unknown form/profile')
    if form=='W' and accent!='none':raise ValueError('W is a structural prototype; damage operators are not calibrated')
    if form=='W' and (profile!='candidate' or architecture!='base'):raise ValueError('W has no previous control or terminal-only mode')
    if not .2<=design_width_mm<=1.7 or not np.isfinite(design_width_mm) or not .2<=clear_gap_mm<=5:raise ValueError('invalid physical design')
    controls=growth_controls or GrowthControls();controls.validate()
    if architecture not in ('base','terminal-droop'):raise ValueError('unknown architecture control')
    if profile=='current' and form!='W':
        if controls!=GrowthControls() or architecture!='base' or design_width_mm!=.8 or clear_gap_mm!=.5:raise ValueError('current control must remain exact')
        return previous.make_tree(FORMS[form],root,height,'spring',seed,accent,identity,posture)
    source=rhythm.make_tree(FORMS[form],root,height,'spring',seed,accent,identity,
                            'near' if height>=70 else 'middle',posture=posture)
    source=stem_layout(source,controls.stem_ratio)
    if form=='W':source=hanging_source(source)
    elif architecture=='terminal-droop':source=terminal_droop(source)
    gain=density_gain(form,height)*controls.vigor
    foliage,diagnostics=thin(source,form,gain,design_width_mm,clear_gap_mm)
    marks,structure=hanging_body(source,design_width_mm) if form=='W' else previous.family_body(source,design_width_mm)
    marks+=foliage
    structure.update(catalog_form=form,catalog_profile='v09-calibration',growth_controls={'stem_ratio':controls.stem_ratio,'vigor':controls.vigor},
                     architecture=structure.get('architecture','base'),density_gain_requested=gain)
    for m in marks:m.owner=identity
    return growth.GrowthTree(identity,FORMS[form],'scale-calibrated-units','spring',int(seed),np.asarray(root,float),float(height),
                             marks,deepcopy(source.lobes),accent,structure,diagnostics)


def vector_records(marks,trees):
    result=[];lookup={t.identity:t for t in trees}
    for m in marks:
        t=lookup[m.owner]
        if t.canopy!='scale-calibrated-units':rr=previous.vector_records([m],[t])
        else:
            rr=old.vector_records([m],[t])
            for r in rr:
                r['id']=r['id'].replace('catalog-v02/','catalog-v09/',1);r['catalog_version']='0.9'
                r['catalog_form']=t.structure['catalog_form'];r['growth_controls']=t.structure['growth_controls']
                r['physical_design_assumption_mm']=t.canopy_diagnostics['design_width_mm'];r['physical_plotting_validated']=False
        for r in rr:r['draw_order']=len(result);result.append(r)
    return result
