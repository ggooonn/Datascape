"""Separate global reserves from source-depth local omission on fixed F2."""
import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter,maximum_filter,minimum_filter
from datascape.data.quality import read_valid_band
from datascape.composition.fields import sample_finite,smooth_supported
from datascape.projection.composition import smoothstep


def depth_roles(q,config):
    a,b=config['near_middle_m'];c,d=config['middle_far_m']
    if not 0<=a<b<=c<d:raise ValueError('Use ordered source-distance transitions.')
    near=1-smoothstep((q-a)/(b-a));far=smoothstep((q-c)/(d-c))
    return {'near':near,'middle':1-near-far,'far':far}


def source_features(master_path,base,config):
    """Native DEM feature blurs and noise; never alter the rendered geometry."""
    xyz=base['xyz'];occupied=base['occupied'];z=xyz[:,:,2];q=base['depth_m'];h,w=q.shape
    macros=[]
    with rasterio.open(master_path) as ds:
        dem=read_valid_band(ds,ds.descriptions.index('DEM')+1).filled(np.nan);valid=np.isfinite(dem)
        for sigma in config['macro_sigma_m']:
            macro=smooth_supported(dem,valid,sigma/ds.res[0])
            value,_=sample_finite(macro,ds.transform,xyz[:,:,0],xyz[:,:,1]);macros.append(value)
        size=2*int(np.ceil(config['relief_window_radius_m']/ds.res[0]))+1
        local_high=maximum_filter(np.where(valid,dem,-np.inf),size=size,mode='nearest')
        local_low=minimum_filter(np.where(valid,dem,np.inf),size=size,mode='nearest')
        high,_=sample_finite(np.where(np.isfinite(local_high),local_high,np.nan),ds.transform,xyz[:,:,0],xyz[:,:,1])
        low,_=sample_finite(np.where(np.isfinite(local_low),local_low,np.nan),ds.transform,xyz[:,:,0],xyz[:,:,1])
        local_height=(z-low)/np.maximum(high-low,10)
        foot=(1-smoothstep((np.nan_to_num(local_height,nan=1)-.15)/.5))*occupied
        rng=np.random.default_rng(np.random.SeedSequence([config['seed'],401]))
        raw=gaussian_filter(rng.normal(size=dem.shape),config['noise_sigma_m']/ds.res[0])
        lo,hi=np.percentile(raw[valid],[5,95]);raw=np.clip((raw-lo)/max(hi-lo,1e-9),0,1)
        noise,_=sample_finite(raw,ds.transform,xyz[:,:,0],xyz[:,:,1])
    a,b=config['valley_relief_m'];r0,r1=config['ridge_relief_m']
    valley=[smoothstep((np.nan_to_num(m-z,nan=0)-a)/(b-a))*occupied for m in macros]
    mound=smoothstep((np.nan_to_num(z-macros[0],nan=0)-.2)/5)*occupied
    ridge=smoothstep((np.nan_to_num(z-macros[1],nan=0)-r0)/(r1-r0))*occupied
    yy,xx=np.mgrid[:h,:w];first=np.min(np.where(occupied,yy,h),axis=0)
    silhouette=(1-smoothstep((yy-first[None,:])/config['silhouette_protection_mm']*(900/h)))*occupied
    # Source-depth discontinuities: retain the farther side as a foot/overlap cue.
    jump=np.zeros_like(q)
    for dy,dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
        other=np.roll(q,(dy,dx),(0,1));both=occupied&np.roll(occupied,(dy,dx),(0,1))
        if dy==1:both[0]=False
        if dy==-1:both[-1]=False
        if dx==1:both[:,0]=False
        if dx==-1:both[:,-1]=False
        jump=np.maximum(jump,np.where(both,np.maximum(q-other,0),0))
    j0,j1=config['occlusion_jump_m'];behind=smoothstep((jump-j0)/(j1-j0))
    behind=maximum_filter(behind,size=3)
    behind=smooth_supported(behind,occupied,config['occlusion_feather_mm']*w/600)*occupied
    behind/=max(behind.max(),1e-9)
    return {'valley_small':valley[0],'valley_medium':valley[1],'valley_large':valley[2],
            'mound':mound,'ridge':ridge,'silhouette':silhouette,'behind_edge':behind,
            'noise':np.nan_to_num(noise,nan=.5)*occupied,'relative_foot':foot,'macros':macros}


def select_anchors(base,features,config):
    """Select measured low-ground patches; labels do not establish objects."""
    occ=base['occupied'];h,w=occ.shape;yy,xx=np.mgrid[:h,:w];v=(yy+.5)/h
    slope=base['slope_deg'];q=base['depth_m'];z=base['xyz'][:,:,2]
    eligible=occ&np.isfinite(slope)&(slope<=12)&(q<450)&(z<120)&(v>.95)
    gentleness=1-smoothstep((np.nan_to_num(slope,nan=90)-2)/10)
    score=.45*features['mound']+.35*gentleness+.20*features['noise']
    anchors=[];field=np.zeros_like(q)
    for center in config['anchor_search_x_fraction'][:config['anchor_count']]:
        distance=(xx+.5-center*w)/(config['anchor_search_half_width_mm']*w/600)
        candidates=eligible&(np.abs(distance)<1)
        if not candidates.any():continue
        preference=score-.15*distance**2-.15*np.abs(v-.975)/.025
        row,col=np.unravel_index(np.argmax(np.where(candidates,preference,-np.inf)),occ.shape)
        sx,sy=config['anchor_sigma_mm'];sx*=1+config['anchor_width_variation']*(2*features['noise'][row,col]-1)
        gaussian=np.exp(-.5*(((xx-col)/(sx*w/600))**2+((yy-row)/(sy*h/900))**2))
        field=np.maximum(field,gaussian)
        anchors.append({'pixel_xy':[float(col+.5),float(row+.5)],'source_xyz_m':base['xyz'][row,col].tolist(),
            'forward_depth_m':float(q[row,col]),'slope_deg':float(slope[row,col]),'sigma_mm':[float(sx),float(sy)],'kind':'Selected terrain legibility patch, not an observed rock, path or tree.'})
    return field*occ,anchors


def omission_retention(field,soft_strength,core_threshold,allow_core):
    """Broad continuous ink fading; exact zero only in declared cores."""
    field=np.clip(field,0,1)
    full=1-.25*(1-core_threshold)
    core=smoothstep((field-core_threshold)/(full-core_threshold)) if allow_core else np.zeros_like(field)
    retention=(1-soft_strength*field)*(1-core)
    if allow_core:retention[field>=full]=0
    return retention


def build_reserves(base,features,config):
    occ=base['occupied'];h,w=occ.shape;yy,xx=np.mgrid[:h,:w];u=(xx+.5)/w;v=(yy+.5)/h
    q=base['depth_m'];z=np.nan_to_num(base['xyz'][:,:,2],nan=0)
    roles=depth_roles(q,config['depth']);anchor,anchors=select_anchors(base,features,config['global'])
    small,medium,large=[features['valley_'+x] for x in ['small','medium','large']]
    noise=features['noise'];ridge=features['ridge'];silhouette=features['silhouette'];behind=features['behind_edge']
    low=1-smoothstep((z-80)/160)
    protect=np.maximum(silhouette,config['local']['ridge_protection_strength']*ridge)
    wn=config['local']['near_weights'];wm=config['local']['middle_weights'];wf=config['local']['far_weights']
    n0,n1=config['local']['noise_weight_range'];irregular=n0+(n1-n0)*noise
    scores={'near':roles['near']*(wn[0]*small+wn[1]*medium+wn[2]*noise+wn[3]*low)*(1-.82*anchor),
            'middle':roles['middle']*(wm[0]*medium+wm[1]*large+wm[2]*behind)*irregular*(1-protect),
            'far':roles['far']*(wf[0]*features['relative_foot']+wf[1]*medium+wf[2]*behind+wf[3]*large)*irregular*(1-protect)}
    local={}
    for name,sigma in zip(['near','middle','far'],config['local']['feather_mm']):
        value=smooth_supported(scores[name],occ,sigma*w/600)
        lo,hi=config['local']['score_transition'][name]
        # Silhouette protection is re-applied after feathering to avoid leaks.
        local[name]=smoothstep((value-lo)/(hi-lo))*(1-silhouette)*occ
    combined=1-np.prod([1-local[name] for name in local],axis=0)
    g=config['global'];t0,t1=g['top_target_fraction']
    top=1-smoothstep((v-t0)/(t1-t0));b0,b1=g['bottom_extent_fraction']
    extent=b0+(b1-b0)*(.65*noise+.35*small)
    bottom=smoothstep((v-(1-extent))/(extent*g['bottom_feather_fraction']))*(1-g['anchor_strength']*anchor)
    inscription=np.zeros_like(q);ic=g['inscription']
    if ic['enabled']:
        x0,y0,x1,y1=ic['bounds_mm'];f=ic['feather_mm']
        inscription=smoothstep((xx*600/w-x0+f)/f)*smoothstep((x1+f-xx*600/w)/f)*smoothstep((yy*900/h-y0+f)/f)*smoothstep((y1+f-yy*900/h)/f)
    global_field=1-(1-top)*(1-bottom)*(1-inscription)
    global_retention=omission_retention(global_field,.99,.94,True)
    soft=omission_retention(combined,config['local']['soft_strength'],config['local']['core_threshold'],False)
    core=omission_retention(combined,config['local']['soft_strength'],config['local']['core_threshold'],True)
    return {'near':local['near'],'middle':local['middle'],'far':local['far'],'local':combined,
        'global_top':np.broadcast_to(top,q.shape).copy(),'global_bottom':bottom,'global':global_field,
        'global_retention':global_retention,'local_soft_retention':soft,'local_core_retention':core,
        'terrain_soft_retention':soft*global_retention,'terrain_retention':core*global_retention,
        'anchors':anchor,'anchor_records':anchors,'depth_roles':roles,'features':features,
        'top_target_intersects_terrain':bool(((top>0)&occ).any())}
