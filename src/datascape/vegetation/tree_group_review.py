"""v08: family-specific physical budgets; the default v07 pine is immutable.

These controls describe catalog objects, not terrain placement or hardware.
Budget and occupancy are independent inputs but their visible effects interact
with physical spacing, candidate supply and later object overlap.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict,dataclass
import math
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_growth as growth
from datascape.vegetation import tree_rhythm as source_grammar
from datascape.vegetation import tree_plot_scale as pine
from datascape.strokes.vector import resample

STATES=('dense','light','open','remnant')
FAMILY_CAPS={
    'broadleaf':{'large':(24,13,3,1),'medium':(10,5,1,1),'small':(4,2,0,0)},
    'understory':{'large':(18,10,2,1),'medium':(7,4,1,1),'small':(3,2,0,0)}}
TOUCH_PROBABILITIES={
    'broadleaf':{'large':(.40,.50,.10),'medium':(.52,.43,.05),'small':(.80,.20,0)},
    'understory':{'large':(.60,.37,.03),'medium':(.70,.28,.02),'small':(.90,.10,0)}}


@dataclass(frozen=True)
class FoliageControls:
    """Small exposed B/U input surface; no continuous growth controls yet.

    Occupancy multipliers correspond to dense/light/open/remnant pad states.
    They scale caps, not a physical percentage of occupied paper. A leaf length
    multiplier stops at the width-dependent physical floor and 6.2 mm ceiling.
    Touch probabilities are explicit only when supplied, otherwise size/family
    defaults apply. Rotation is one rigid motion per original directional unit.
    """
    unit_budget_scale:float=1.0
    pad_occupancy:tuple=(1.0,1.0,1.0,1.0)
    leaf_length_scale:float=1.0
    touch_probabilities:tuple|None=None
    rotation_limit_deg:float=8.0
    design_width_mm:float=.8
    clear_gap_mm:float=.5

    def validate(self):
        def bounded(x,a,b):return np.isfinite(x) and a<=x<=b
        if not bounded(self.unit_budget_scale,0,3):raise ValueError('unit budget scale must be 0–3')
        if len(self.pad_occupancy)!=4 or not all(bounded(x,0,2) for x in self.pad_occupancy):
            raise ValueError('four occupancy multipliers in 0–2 required')
        if not bounded(self.leaf_length_scale,.5,1.5):raise ValueError('leaf length scale must be 0.5–1.5')
        if not bounded(self.rotation_limit_deg,0,10):raise ValueError('rotation must be 0–10 degrees')
        if not bounded(self.design_width_mm,.2,1.7):raise ValueError('design width must be 0.2–1.7 mm')
        if not bounded(self.clear_gap_mm,.2,5):raise ValueError('clear gap must be 0.2–5 mm')
        if self.touch_probabilities is not None:
            p=self.touch_probabilities
            if len(p)!=3 or not all(bounded(x,0,1) for x in p) or not math.isclose(sum(p),1,abs_tol=1e-9):
                raise ValueError('three nonnegative touch probabilities must sum to one')


def family_foliage(source,controls):
    controls.validate();cls=pine.size_class(source.height)
    caps=dict(zip(STATES,FAMILY_CAPS[source.family][cls]))
    probabilities=controls.touch_probabilities or TOUCH_PROBABILITIES[source.family][cls]
    multipliers=dict(zip(STATES,controls.pad_occupancy))
    units=defaultdict(list)
    for m in source.marks:
        if m.part=='foliage-field':units[m.key.rsplit('-',1)[0]].append(m)
    info={u['key']:u for u in source.canopy_diagnostics['units'] if u['retained']}
    grouped=defaultdict(list)
    for key,marks in units.items():grouped[info[key]['owner_pad']].append((key,marks))
    leaf_floor=max(2.8,3.5*controls.design_width_mm)
    separation=controls.design_width_mm+controls.clear_gap_mm
    accepted=[];sampled=[];index=None;records=[];pad_records=[]
    for pad in sorted(source.canopy_diagnostics['pads'],key=lambda p:(STATES.index(p['state']),p['key'])):
        state=pad['state'];target=int(math.floor(caps[state]*controls.unit_budget_scale*multipliers[state]+.5))
        candidates=grouped[pad['key']];count=0
        for key,available in sorted(candidates,key=lambda x:(info[x[0]]['radius_fraction'],x[0])):
            rng=old.rng_for(source.seed,key+'/physical-unit')
            n=min(int(rng.choice([1,2,3],p=probabilities)),len(available))
            slots=[len(available)//2] if n==1 else np.round(np.linspace(0,len(available)-1,n)).astype(int)
            selected=[]
            for slot in slots:
                m=deepcopy(available[slot]);length=old.length(m.xy)
                goal=max(leaf_floor,min(6.2,length*controls.leaf_length_scale))
                m.xy=m.xy[0]+(m.xy-m.xy[0])*goal/max(length,1e-9);selected.append(m)
            dense=np.concatenate([resample(m.xy,.2) for m in selected])
            gap=float(index.query(dense)[0].min()) if index is not None else None
            reason='pad-budget' if count>=target else 'physical-gap' if gap is not None and gap<separation+.2 else 'kept'
            records.append({'key':key,'pad':pad['key'],'state':state,'source_touches':len(available),
                            'touches':n,'retained':reason=='kept','reason':reason,
                            'rotation_deg':info[key]['rotation_deg'],'sampled_gap_to_previous_mm':gap})
            if reason!='kept':continue
            accepted+=selected;count+=1;sampled.append(dense);index=cKDTree(np.concatenate(sampled))
        pad_records.append({'key':pad['key'],'state':state,'available_units':len(candidates),
                            'base_cap':caps[state],'unit_cap':target,'retained_units':count})
    kept=[u for u in records if u['retained']]
    settings={k:list(v) if isinstance(v,tuple) else v for k,v in asdict(controls).items()}
    return accepted,{'source_version':'v06 R2 / V02 directional candidates','family_policy_version':'0.8',
                     'size_class':cls,'controls':settings,'source_units':len(units),
                     'source_foliage_paths':sum(map(len,units.values())),'retained_units':len(kept),
                     'retained_foliage_paths':len(accepted),'unit_touch_histogram':dict(Counter(u['touches'] for u in kept)),
                     'minimum_leaf_length_mm':leaf_floor,'design_width_mm':controls.design_width_mm,
                     'clear_gap_mm':controls.clear_gap_mm,'minimum_between_unit_centerline_gap_mm':separation,
                     'touch_probabilities':probabilities,'pads':pad_records,'units':records,
                     'within_unit_merging':'Intentional glyph; individual touch impressions need not separate',
                     'across_tree_spacing':'Not guaranteed','physical_plotting_validated':False}


def family_body(source,width):
    marks,structure=pine.safe_body(source,width)
    if source.family=='understory':
        # The former basal pairs were copied at every size. Apply the same
        # paired-to-single physical rule to these two supporting stems as well.
        marks=[m for m in marks if not m.key.startswith('basal-')]
        for key,p in structure['members'].items():
            if not key.startswith('basal-'):continue
            mm,audit,_=pine.safe_contours(np.asarray(p),source.height*.012*.65,key,source.seed,width)
            for m in mm:m.parent='axis';m.owner=source.identity
            marks+=mm;structure['contour_audit'][key]=audit
        structure['basal_stem_policy']='Same physical pair-to-single rule; retain three-stem role'
    return marks,structure


def make_tree(family='broadleaf',root=(90,155),height=95,season='spring',seed=20261017,
              accent='none',identity='tree-0',posture='auto',controls=None):
    if family=='hero-pine':
        if controls is not None:raise ValueError('Pine is frozen at v07 P-L; controls in this pass apply to B/U only')
        return pine.make_tree(family,root,height,season,seed,accent,identity,posture)
    if family not in FAMILY_CAPS:raise ValueError('unknown role family')
    controls=FoliageControls() if controls is None else controls;controls.validate()
    depth='near' if height>=70 else 'middle'
    source=source_grammar.make_tree(family,root,height,season,seed,accent,identity,depth,
                                    posture=posture,rotation_limit_deg=controls.rotation_limit_deg)
    foliage,diagnostics=family_foliage(source,controls)
    marks,structure=family_body(source,controls.design_width_mm);marks+=foliage
    for m in marks:m.owner=identity
    structure.update(density_profile='family-scale-budget',catalog_review_version='0.8')
    return growth.GrowthTree(identity,family,'family-physical-units',season,int(seed),np.asarray(root,float),float(height),
                             marks,deepcopy(source.lobes),accent,structure,diagnostics)


def vector_records(marks,trees):
    result=[];by_id={t.identity:t for t in trees}
    for mark in marks:
        t=by_id[mark.owner]
        if t.canopy!='family-physical-units':
            rr=pine.vector_records([mark],[t])
        else:
            rr=old.vector_records([mark],[t])
            for r in rr:
                r['id']=r['id'].replace('catalog-v02/','catalog-v08/',1);r['catalog_version']='0.8'
                r['physical_design_assumption_mm']=t.canopy_diagnostics['design_width_mm'];r['physical_plotting_validated']=False
                r['foliage_controls']=t.canopy_diagnostics['controls']
        for r in rr:r['draw_order']=len(result);result.append(r)
    return result
