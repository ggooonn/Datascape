"""Small F2 composition refinements with an unconditional bottom contract."""
from copy import deepcopy
import hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt
from datascape.projection.composition import smoothstep
from datascape.composition.fields import smooth_supported
from datascape.composition.multidepth import omission_retention
from datascape.vegetation.multidepth import glyph


def boundary_retention(y_mm,canvas_height_mm=900,hard_bottom_guard_mm=2,collar_mm=18):
    """Continuous final gate for terrain, vegetation, vector and color layers.

    Coordinates increase downward. The exact canvas bottom and the optional
    narrow guard are zero; no anchor, object depth or positive form overrides
    this rule. Collar width is separate from the irregular 5-15% transition.
    Raster callers evaluate each pixel's lower edge conservatively, including
    the exact canvas bottom even when the optional guard is zero.
    """
    if canvas_height_mm<=0 or not 0<=hard_bottom_guard_mm<canvas_height_mm or collar_mm<=0:
        raise ValueError('Use a positive canvas/collar and a valid nonnegative guard.')
    y=np.asarray(y_mm,dtype=float)
    r=smoothstep((canvas_height_mm-hard_bottom_guard_mm-y)/collar_mm)
    return np.where(y>=canvas_height_mm-hard_bottom_guard_mm,0,r)


def apply_boundary(contributions,y_mm,**config):
    """Apply the same final gate to scalar coverage or multi-channel layers."""
    values=np.asarray(contributions);retention=boundary_retention(y_mm,**config)
    while retention.ndim<values.ndim:retention=retention[...,None]
    return values*retention


def source_patch(base,center_xy,radius_m):
    """A footprint in real source XY, without moving its surface coordinates."""
    xyz=base['xyz'];rx,ry=radius_m
    return np.nan_to_num(np.exp(-.5*(((xyz[:,:,0]-center_xy[0])/rx)**2+((xyz[:,:,1]-center_xy[1])/ry)**2)),nan=0)*base['occupied']


def positive_forms(base,features,small_marks,config):
    """Rank DEM-supported forms globally; no prescribed X positions."""
    h,w=base['occupied'].shape;yy,xx=np.mgrid[:h,:w];v=(yy+.5)/h
    q=base['depth_m'];slope=base['slope_deg'];z=base['xyz'][:,:,2]
    a,b=config['depth_range_m'];v0,v1=config['screen_y_range_fraction']
    valid=base['occupied']&np.isfinite(slope)&(slope<=config['maximum_slope_deg'])&(q>=a)&(q<=b)&(v>=v0)&(v<=v1)
    valid&=features['mound']>=config['minimum_mound_proxy']
    gentle=1-smoothstep((np.nan_to_num(slope,nan=90)-2)/config['maximum_slope_deg'])
    relief=smoothstep(np.nan_to_num(np.abs(z-features['macros'][0]),nan=0)/20)
    score=.60*features['mound']+.25*gentle+.15*relief
    remaining=np.where(valid&(score>=config['minimum_score']),score,0)
    centers=[];field=np.zeros((h,w));spacing=config['minimum_spacing_mm']*w/600
    for _ in range(config['maximum_count']):
        row,col=np.unravel_index(np.argmax(remaining),remaining.shape)
        if remaining[row,col]<=0:break
        xyz=base['xyz'][row,col]
        patch=source_patch(base,xyz[:2],config['source_radius_m'])
        shape=.35+.65*features['mound'];patch*=shape*(.55+.45*gentle)
        field=np.maximum(field,patch)
        centers.append({'pixel_xy':[float(col+.5),float(row+.5)],'source_xyz_m':xyz.tolist(),
            'score':float(score[row,col]),'slope_deg':float(slope[row,col]),'forward_depth_m':float(q[row,col]),
            'relative_height_above_120m_blur_m':float(z[row,col]-features['macros'][0][row,col]),
            'interpretation':'DEM-supported terrain legibility selection; not an identified rock or path.'})
        distance=np.hypot(xx-col,yy-row)
        remaining[distance<spacing]=0
        # Composition balance rewards uncovered locations without target X bins.
        remaining*=np.clip(distance/(spacing*2),.5,1)
    forms=smooth_supported(field,base['occupied'],config['field_feather_mm']*w/600)*base['occupied']
    roots=np.zeros((h,w))
    for mark in small_marks:
        if mark['kind']=='near':roots=np.maximum(roots,source_patch(base,mark['source_xyz_m'][:2],[config['root_support_radius_m']]*2))
    roots*=config['root_support_strength']
    return np.maximum(forms,roots),forms,roots,centers


def refine_reserves(base,old,small_marks,config,old_config):
    """Keep old near/middle fields and replace only far/bottom application."""
    occ=base['occupied'];h,w=occ.shape;yy,xx=np.mgrid[:h,:w];y=(yy+.5)*900/h;f=old['features']
    positive,forms,roots,centers=positive_forms(base,f,small_marks,config['positive_forms'])
    fc=config['far'];role=old['depth_roles']['far'];a,b,c=fc['weights']
    expanded=smooth_supported(old['far'],occ,(fc['feather_mm_xy'][1]*h/900,fc['feather_mm_xy'][0]*w/600))
    # Foot rank supplies directional fading; the crest and silhouette remain.
    far_score=(a*expanded+b*role*f['relative_foot']+c*role*f['valley_medium'])*(1-fc['ridge_protection']*f['ridge'])*(1-f['silhouette'])*occ
    far_omission=np.clip(far_score,0,1)
    old_core=(old['far']>=fc['core_source_threshold'])&occ
    distance=distance_transform_edt(old_core,sampling=(900/h,600/w))
    core_gate=smoothstep((distance-fc['core_erosion_mm'])/fc['core_feather_mm'])*(1-f['silhouette'])
    far_retention=(1-fc['soft_strength']*far_omission)*(1-core_gate)
    mid=omission_retention(old['middle'],old_config['local']['soft_strength'],old_config['local']['core_threshold'],True)
    near=omission_retention(old['near'],old_config['local']['soft_strength'],old_config['local']['core_threshold'],True)
    legacy_local=near*mid*far_retention
    pc=config['positive_forms'];positive_r=pc['paper_floor_retention']+(1-pc['paper_floor_retention'])*positive
    near_role=old['depth_roles']['near']
    near_middle=(1-near_role+near_role*positive_r*(.75+.25*near))*mid
    selective_local=near_middle*far_retention
    tr=config['bottom_transition'];lo,hi=tr['extent_fraction']
    extent=900*(lo+(hi-lo)*(.65*f['noise']+.35*f['valley_small']))
    transition=smoothstep((y-(900-extent))/extent)*(1-tr['positive_protection']*positive)
    irregular_retention=1-tr['strength']*transition
    boundary=boundary_retention((yy+1)*900/h,**config['boundary'])
    global_r=irregular_retention*boundary
    result={**old,'far':far_omission,'far_core_gate':core_gate,'far_retention':far_retention,
        'local_core_retention':selective_local,'global_retention':global_r,
        'terrain_retention':selective_local*global_r,'legacy_terrain_retention':legacy_local*global_r,
        'positive':positive,'positive_forms':forms,'root_support':roots,'positive_records':centers,
        'boundary_retention':boundary,'bottom_extent_mm':extent,'bottom_transition':transition,
        'irregular_retention':irregular_retention,'legacy_local_retention':legacy_local,'near_middle_retention':near_middle}
    return result


def representative_trees(small_marks,base,reserves,config,seed):
    """Add a few symbolic canopy-scale probes rooted at existing source sites."""
    h,w=base['occupied'].shape;candidates=[x for x in small_marks if x['kind']=='near'];ranked=[]
    for mark in candidates:
        x,y=mark['root_pixel_xy'];row=min(h-1,max(0,int(y)));col=min(w-1,max(0,int(x)))
        x_mm=x*600/w
        if abs(x_mm-300)<config['minimum_trunk_seam_distance_mm'] or min(x_mm,600-x_mm)<config['minimum_trunk_frame_distance_mm']:continue
        root_retention=float(reserves['terrain_retention'][row,col])
        if mark['ndvi']<config['minimum_ndvi'] or root_retention<config['minimum_root_retention']:continue
        count=int(sum(np.linalg.norm(np.array(mark['root_pixel_xy'])-np.array(other['root_pixel_xy']))*600/w<=config['cluster_radius_mm'] for other in candidates))
        if count<config['minimum_cluster_count']:continue
        probe=max(0,int(y-config['backdrop_probe_height_mm']*h/900))
        behind=float(base['depth_m'][probe,col]-mark['forward_depth_m'])
        backdrop=(1-reserves['local_core_retention'][probe,col])*smoothstep((behind-200)/700)
        score=(.40+.60*reserves['positive'][row,col])*(.40+.60*smoothstep((mark['ndvi']-.1)/.55))*(.50+.50*backdrop)
        ranked.append((float(score),mark,count,float(backdrop)))
    chosen=[];rng=np.random.default_rng(np.random.SeedSequence([seed,603]))
    for score,mark,count,backdrop in sorted(ranked,key=lambda x:x[0],reverse=True):
        if any(np.linalg.norm(np.array(mark['root_pixel_xy'])-np.array(other['root_pixel_xy']))*600/w<config['minimum_spacing_mm'] for other in chosen):continue
        tree=deepcopy(mark);height=float(rng.uniform(*config['height_mm']))
        tree.update({'id':hashlib.sha256((str(seed)+':representative:'+mark['id']).encode()).hexdigest()[:16],
            'parent_small_mark_id':mark['id'],'representative':True,'height_mm':height,'selection_score':score,
            'cluster_small_mark_count':count,'backdrop_opportunity':backdrop,
            'root_retention':float(reserves['terrain_retention'][int(mark['root_pixel_xy'][1]),int(mark['root_pixel_xy'][0])]),
            'polylines_pixel_xy':glyph(np.array(mark['root_pixel_xy']),'near',height*h/900,rng)})
        chosen.append(tree)
        if len(chosen)>=config['count']:break
    return chosen
