"""Terrain-driven transverse spacing and depth-specific directional grain.

All calculations read the selected F2 surface. Density is a geometry policy;
the existing retention field remains an independent omission policy.
"""
from copy import deepcopy
import hashlib,json
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import CubicSpline
from scipy.ndimage import binary_erosion
from datascape.projection.composition import smoothstep
from datascape.strokes.vector import sample,resample,split_at_gate,finalize,phase
from datascape.strokes.generators import contours,valid_runs,direction_field,flow_lines,continuity_mask
from datascape.strokes.grammar import transfer_mist


def layer_digest(strokes,layer):
    """Ignore only the absolute list index when comparing frozen layers."""
    items=[{k:v for k,v in s.items() if k!='draw_order'} for s in strokes if s['layer']==layer]
    return hashlib.sha256(json.dumps(items,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def normalized(values):
    lo,hi=np.percentile(values,[10,90])
    return np.clip((values-lo)/max(hi-lo,1e-9),0,1)


def integrated_phase(q,pitch):
    """Strictly increasing row phase; spacing changes without a scene warp."""
    q=np.asarray(q,dtype=float);pitch=np.asarray(pitch,dtype=float)
    if np.any(np.diff(q)<=0) or np.any(pitch<=0):raise ValueError('Positive pitch and increasing depth required')
    return np.r_[0,np.cumsum(np.diff(q)*(.5/pitch[:-1]+.5/pitch[1:]))]


def density_profile(fixed,config):
    """Adapt the historical row-peak inverse-quadratic gap to visible F2.

    Local macro-relative relief avoids equating low foreground elevation with
    unimportant ground. Depth aggregation follows source meters, not y bands.
    """
    b=fixed['base'];o=b['occupied'];q=b['depth_m'];z=fixed['_grammar_xyz'][:,:,2];c=config['A']
    grid=np.arange(40,float(q[o].max())+c['profile_bin_m'],c['profile_bin_m'])
    top=[];relief=[];ridge=[];slope=[];counts=[];weights=[]
    f=fixed['features'];macro=f['macros'][0]
    qy,qx=np.gradient(q);coarea=np.hypot(qx,qy)
    safe=continuity_mask(b)&binary_erosion(o)
    coarea=np.minimum(coarea,np.percentile(coarea[safe],95))
    # A single global gain normalization uses expected retained path length.
    # Local omission remains entirely the original field/transfer algorithm.
    r=fixed['retention'];survival=r*np.where(r>.82,1.,(10+110*r)/120)
    for center in grid:
        m=o&(np.abs(q-center)<c['profile_window_m']/2);counts.append(int(m.sum()))
        weights.append(float(np.sum(coarea[m&safe]*survival[m&safe])))
        for target,a,p in [(top,z,95),(relief,np.nan_to_num(z-macro),90),(ridge,f['ridge'],70),(slope,np.nan_to_num(b['slope_deg']),70)]:
            target.append(float(np.percentile(a[m],p)) if m.any() else np.nan)
    def smooth(a):
        a=np.array(a);good=np.isfinite(a)
        return gaussian_filter1d(np.interp(grid,grid[good],a[good]),c['smoothing_m']/c['profile_bin_m'])
    top,relief,ridge,slope=map(smooth,[top,relief,ridge,slope])
    # Broad local height differences are structural rhythm, not a sinusoid.
    height=top-gaussian_filter1d(top,c['macro_window_m']/c['profile_bin_m'])
    signal=.50*normalized(height)+.25*normalized(relief)+.15*normalized(ridge)+.10*normalized(slope)
    raw=c['widest_pitch_m']-(c['widest_pitch_m']-c['tightest_pitch_m'])*signal**2
    weights=np.maximum(np.array(weights),1e-6)
    density_shape=(c['reference_pitch_m']/raw)**c.get('contrast_exponent',2.)
    low=c['reference_pitch_m']/c['maximum_pitch_m'];high=c['reference_pitch_m']/c['minimum_pitch_m']
    if not low<c['density_gain']<high:raise ValueError('Density gain must lie inside pitch bounds')
    left,right=0.,100.
    for _ in range(64):
        scale=(left+right)/2
        if np.average(np.clip(density_shape*scale,low,high),weights=weights)<c['density_gain']:left=scale
        else:right=scale
    pitch=c['reference_pitch_m']/np.clip(density_shape*(left+right)/2,low,high)
    phi=integrated_phase(grid,pitch)
    phase_field=np.interp(q,grid,phi);density=np.interp(q,grid,c['reference_pitch_m']/pitch)
    density[~o]=0
    return {'q_m':grid,'peak_elevation_m':top,'local_peak_residual_m':height,'signal':signal,'pitch_m':pitch,
            'row_phase':phi,'density':density,'phase_field':phase_field}


def a_proposals(fixed,profile,config,gain=1):
    """Keep the transverse family; redistribute source rows monotonically."""
    b=fixed['base'];q=b['depth_m'];phase_field=profile['phase_field']*gain
    paths=[];levels=np.arange(.5,float(np.max(phase_field[b['occupied']])),1)
    for level,p in contours(phase_field,b['occupied'],levels):
        expected=float(np.interp(level/gain,profile['row_phase'],profile['q_m']))
        for run in valid_runs(p,b,expected_q=expected):
            coarse=resample(run,config['A']['spline_knot_mm'])
            if len(coarse)>=4:
                t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(coarse,axis=0),axis=1))]
                at=np.linspace(0,t[-1],max(2,int(t[-1]/.5)+1))
                curve=CubicSpline(t,coarse,axis=0,bc_type='natural')(at)
                paths.extend(valid_runs(curve,b,expected_q=expected))
            else:paths.append(run)
    return [{'id':f'A-rhythm-{i:06d}','xy_mm':p.tolist(),'width_mm':.32,'layer':'A','preview_opacity':.82,
             'expression':{'intensity':.6,'pressure_calibrated':False}} for i,p in enumerate(paths)]


def foreground_a(candidates,fixed,keep):
    """Thin near-role geometry with low-discrepancy whole-source thresholds.

    The threshold controls actual paths; it never edits the retention field.
    Important ridge/foothold structure has a modest protection floor.
    """
    if keep==1:return deepcopy(candidates)
    result=[]
    for i,s in enumerate(candidates):
        p=resample(s['xy_mm'],.5);near=sample(fixed['old']['depth_roles']['near'],p)
        if np.max(near)<1e-8:
            result.append(deepcopy(s));continue
        protect=np.maximum(sample(fixed['features']['ridge'],p),.6*sample(fixed['features']['mound'],p))
        probability=1-near*(1-keep)*(1-.25*protect)
        # Fixed low-discrepancy thresholds avoid spatially random spacing.
        threshold=((i+.5)*.6180339887498949)%1
        for j,run in enumerate(split_at_gate(p,probability-threshold,3.5)):
            # Retain the source identity so mist sampling does not change in
            # an unaffected middle/far part when foreground keep changes.
            result.append({**s,'xy_mm':run.tolist()})
    return result


def c_proposals(fixed,derivative,projection,config):
    """One shared direction family; depth changes expression, not just scale."""
    c=config['C'];field=direction_field(fixed['base'],derivative,projection)
    raw=flow_lines(fixed['base'],field,c['integration'],config['seed'])
    result=[]
    for i,line in enumerate(raw):
        p=resample(line,.5);q=sample(fixed['base']['depth_m'],p)
        near=1-smoothstep((q-1100)/700);far=smoothstep((q-3000)/1200);middle=np.clip(1-near-far,0,1)
        target=near*c['length_mm']['near']+middle*c['length_mm']['middle']+far*c['length_mm']['far']
        gap=near*c['gap_mm']['near']+middle*c['gap_mm']['middle']+far*c['gap_mm']['far']
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        # Non-overlapping windows, shorter directional grain as depth increases.
        cycle=target+gap;position=(arc+phase(str(i),config['seed'])*cycle)%cycle
        for j,run in enumerate(split_at_gate(p,(target-position)/cycle,c['minimum_path_mm'])):
            result.append({'id':f'C-grain-{i:06d}-{j}','source_family':f'C-flow-{i:06d}',
                'xy_mm':run.tolist(),'width_mm':.16,'layer':'C','preview_opacity':.32,
                'expression':{'intensity':.25,'pressure_calibrated':False}})
    return result,{'integrated_parent_paths':len(raw),'depth_window_candidates':len(result)}


def select_c_role(candidates,fixed,weights,seed):
    """Nested parent decisions before panel division; fixed field and seed."""
    result=[]
    for s in candidates:
        p=resample(s['xy_mm'],1);roles=fixed['old']['depth_roles']
        probability=sum(sample(roles[k],p)*v for k,v in weights.items())
        threshold=phase(s.get('source_family',s['id']),seed)
        for j,run in enumerate(split_at_gate(p,probability-threshold,2.4)):
            result.append({**s,'id':s['id']+f'-role-{j}','xy_mm':run.tolist()})
    return result


def transfer(candidates,fixed,parent_config):
    """Use the published mist algorithm and unchanged scalar fields."""
    result=transfer_mist(candidates,fixed,'combined',parent_config)
    sources={s['id']:s for s in candidates}
    for s in result:
        s['id']=s['layer']+'-rhythm-'+s['id']
        source=sources[s['source_stroke_id']]
        if 'source_family' in source:s['source_family']=source['source_family']
    return result


def assign_material(strokes,assignment='light_ink'):
    """Material intent is metadata; assigning color must not move a vertex."""
    if assignment not in ['light_ink','color_support','ink_and_color']:raise ValueError(assignment)
    return [{**deepcopy(s),'material_intent':assignment,'geometry_family':'terrain_direction_field'} for s in strokes]


def build_sets(parent,fixed,derivative,projection,config,parent_config):
    profile=density_profile(fixed,config);a_raw=a_proposals(fixed,profile,config)
    c_raw,c_record=c_proposals(fixed,derivative,projection,config)
    frozen={k:[s for s in parent if s['layer']==k] for k in ['A','B','C','D','V']}
    sets={'baseline':parent};isolation={};pre_mist={}
    for name,preset in config['presets'].items():
        aa=a_proposals(fixed,profile,config,preset['A_gain']) if preset['A_gain']!=1 else deepcopy(a_raw)
        aa=foreground_a(aa,fixed,preset['foreground_A_keep'])
        cc=select_c_role(c_raw,fixed,preset['C_keep'],config['seed']+91)
        a=transfer(aa,fixed,parent_config);c=assign_material(transfer(cc,fixed,parent_config),'light_ink')
        # The existing B/D/V records are frozen, not regenerated against new A.
        groups=[c,a,frozen['B'],frozen['V'],frozen['D']]
        sets[name]=[{**s,'draw_order':i} for i,s in enumerate(s for g in groups for s in g)]
        isolation[name]={k:layer_digest(sets[name],k)==layer_digest(parent,k) for k in ['B','D','V']}
        pre_mist[name]={'A':aa,'C':cc}
    # Isolate A rhythm from the new C grammar as a separate control.
    control_a=[s for s in sets['A_dominant'] if s['layer']=='A']
    groups=[frozen['C'],control_a,frozen['B'],frozen['V'],frozen['D']]
    sets['A_density_only']=[{**s,'draw_order':i} for i,s in enumerate(s for g in groups for s in g)]
    isolation['A_density_only']={k:layer_digest(sets['A_density_only'],k)==layer_digest(parent,k) for k in ['B','C','D','V']}
    return sets,profile,{'C':c_record,'frozen_layer_equality':isolation,'raw_A_candidates':len(a_raw)},pre_mist
