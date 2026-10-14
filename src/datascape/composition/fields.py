"""Geographic sampling and explicit vegetation/reserve fields on fixed F2."""
import numpy as np
from scipy.ndimage import gaussian_filter,gaussian_filter1d,map_coordinates
from rasterio.windows import from_bounds,Window

from datascape.data.quality import read_valid_band
from datascape.projection.composition import smoothstep


def mapped_source_coordinates(terrain):
    """Recover source triangle-interpolated XYZ at visible F2 pixel centers.

    Use the final mapped triangle's barycentric rule, not array-index pairing
    of differently georeferenced rasters or an invented 10 m terrain surface.
    """
    owner=terrain['owners'];valid=owner>=0;h,w=owner.shape
    yy,xx=np.mgrid[:h,:w]
    face=terrain['faces'][np.maximum(owner,0)]
    p=terrain['pixel'][face]
    # p has [row, column, triangle vertex, XY] axes.
    e1=p[:,:,1,:]-p[:,:,0,:];e2=p[:,:,2,:]-p[:,:,0,:]
    denom=e1[:,:,0]*e2[:,:,1]-e1[:,:,1]*e2[:,:,0]
    dx=xx+.5-p[:,:,0,0];dy=yy+.5-p[:,:,0,1]
    safe=np.where(valid & (np.abs(denom)>1e-12),denom,1)
    b1=(dx*e2[:,:,1]-dy*e2[:,:,0])/safe
    b2=(e1[:,:,0]*dy-e1[:,:,1]*dx)/safe
    weights=np.stack([1-b1-b2,b1,b2],axis=2)
    xyz=np.sum(terrain['xyz'][face]*weights[:,:,:,None],axis=2)
    xyz[~valid]=np.nan
    return xyz,valid


def sample_finite(values,transform,x,y,minimum_support=.999):
    """Bilinear sample at native pixel centers; reject insufficient support.

    Nodata is never interpreted as a numeric zero. Return values and the
    interpolated finite support fraction for explicit diagnostic recording.
    """
    if transform.b != 0 or transform.d != 0:
        raise ValueError('This sampler requires a north-up raster; reproject rotated grids explicitly.')
    values=np.asarray(values,dtype=float);finite=np.isfinite(values)
    col=(x-transform.c)/transform.a-.5
    row=(y-transform.f)/transform.e-.5
    coords=[np.nan_to_num(row,nan=-10),np.nan_to_num(col,nan=-10)]
    numerator=map_coordinates(np.where(finite,values,0),coords,order=1,mode='constant',cval=0,prefilter=False)
    support=map_coordinates(finite.astype(float),coords,order=1,mode='constant',cval=0,prefilter=False)
    result=np.divide(numerator,support,out=np.full_like(numerator,np.nan),where=support>=minimum_support)
    result[~np.isfinite(x)|~np.isfinite(y)]=np.nan
    return result,support


def sample_window_band(dataset,index,bounds,xyz):
    """Crop the existing finite-mask loader, preserving the real transform."""
    w=from_bounds(*bounds,transform=dataset.transform).round_offsets().round_lengths()
    left=max(0,int(w.col_off)-2);top=max(0,int(w.row_off)-2)
    right=min(dataset.width,int(w.col_off+w.width)+2);bottom=min(dataset.height,int(w.row_off+w.height)+2)
    window=Window(left,top,right-left,bottom-top)
    data=read_valid_band(dataset,index)[window.toslices()].filled(np.nan).copy()
    return sample_finite(data,dataset.window_transform(window),xyz[:,:,0],xyz[:,:,1])


def smooth_supported(values,valid,sigma):
    denominator=gaussian_filter(valid.astype(float),sigma,mode='nearest')
    numerator=gaussian_filter(np.where(valid,values,0),sigma,mode='nearest')
    return np.divide(numerator,denominator,out=np.zeros_like(numerator),where=denominator>1e-9)


def build_fields(terrain,grid,slope,aspect,macro_screen,ndvi,counts,camera,config):
    """Combine measured proxies and declared composition weights.

    Mist is an omission field, not weather. No field writes source heights,
    pigment slots, hardware coordinates or calibrated brush pressure.
    """
    xyz,occupied=mapped_source_coordinates(terrain)
    h,w=occupied.shape;yy,xx=np.mgrid[:h,:w];u=(xx+.5)/w;v=(yy+.5)/h
    valid_xyz=np.nan_to_num(xyz,nan=0).reshape(-1,3)
    _,q=camera.horizontal_coordinates(valid_xyz);q=q.reshape(h,w)
    z=np.nan_to_num(xyz[:,:,2],nan=0)
    relative=np.nan_to_num(macro_screen-z,nan=0)
    valley=smoothstep((relative-config['valley_low_m'])/(config['valley_high_m']-config['valley_low_m']))*occupied
    low=1-smoothstep((z-80)/140)
    depth_role=np.exp(-.5*((q-config['mist_depth_center_m'])/config['mist_depth_sigma_m'])**2)*smoothstep((q-350)/450)
    rest=np.exp(-.5*((v-config['rest_y_fraction'])/config['rest_y_sigma'])**2)
    peak_protection=1-smoothstep((z-350)/200)
    upper_protection=smoothstep((v-.38)/.12)
    score=depth_role*(.65*valley+.20*low+.15*rest)*peak_protection*upper_protection*occupied
    score=smooth_supported(score,occupied,config['field_feather_mm']*w/600)
    mist=config['mist_max']*smoothstep((score-config['mist_score_low'])/(config['mist_score_high']-config['mist_score_low']))*occupied
    # A data-weighted, softly centered low-ground passage; no path is asserted.
    bias=config['corridor_screen_center_fraction'];bias_sigma=config['corridor_screen_sigma_fraction']
    row_weight=(.15*low+valley)*occupied*np.exp(-.5*((u-bias)/bias_sigma)**2)
    row_total=row_weight.sum(axis=1)
    center=np.divide((row_weight*u).sum(axis=1),row_total,out=np.full(h,bias),where=row_total>1e-9)
    center=gaussian_filter1d(center,config['corridor_center_smoothing_mm']*w/600)
    corridor=np.exp(-.5*((u-center[:,None])/(config['corridor_width_mm']/600))**2)
    corridor*=smoothstep((v-.58)/.12)*(1-smoothstep((v-.92)/.08))*(1-smoothstep((q-1400)/1000))*low*occupied
    reserve_core=smoothstep((mist-config['reserve_mist_low'])/(config['reserve_mist_high']-config['reserve_mist_low']))
    whitespace=np.maximum(reserve_core,config['corridor_strength']*corridor)*occupied
    reserve=(whitespace>=config['hard_reserve_threshold'])&occupied
    retention=(1-config['terrain_mist_attenuation']*mist)*(1-whitespace)**config['whitespace_power']
    retention=np.clip(retention,0,1)*occupied;retention[reserve]=0
    season=config['season'];current=ndvi[season]
    evidence=np.isfinite(current)&np.isfinite(counts[season])&(counts[season]>=config['minimum_observations'])&occupied
    confidence=smoothstep((np.nan_to_num(counts[season],nan=0)-config['minimum_observations'])/(config['full_support_observations']-config['minimum_observations']))
    vigor=smoothstep((np.nan_to_num(current,nan=-1)-config['ndvi_low'])/(config['ndvi_high']-config['ndvi_low']))
    seasonal=np.full((h,w),.9)
    seasonal_valid=np.isfinite(ndvi['WINTER'])&np.isfinite(ndvi['SUMMER'])&(counts['WINTER']>=config['minimum_observations'])&(counts['SUMMER']>=config['minimum_observations'])
    relative_season=np.clip((current-ndvi['WINTER'])/np.maximum(ndvi['SUMMER']-ndvi['WINTER'],.08),0,1)
    seasonal[seasonal_valid]=.8+.2*np.nan_to_num(relative_season[seasonal_valid],nan=.5)
    gentle=.30+.70*(1-smoothstep((np.nan_to_num(slope,nan=90)-5)/20))
    height_weight=1-.60*smoothstep((z-120)/230)
    aspect_weight=.9+.1*np.cos(np.deg2rad(np.nan_to_num(aspect,nan=config['aspect_preference_deg'])-config['aspect_preference_deg']))
    aspect_weight[np.nan_to_num(slope,nan=0)<=1]=1
    near_role=1-smoothstep((q-config['near_full_m'])/(config['near_end_m']-config['near_full_m']))
    lower_role=smoothstep((v-config['vegetation_y_start'])/.08)
    edge_balance=config['center_density_floor']+(1-config['center_density_floor'])*smoothstep(np.abs(u-.5)/.40)
    rng=np.random.default_rng(np.random.SeedSequence([config['seed'],101]))
    noise=gaussian_filter(rng.normal(size=(h,w)),config['spatial_noise_mm']*w/600)
    noise=(noise-noise.min())/max(noise.max()-noise.min(),1e-9)
    noise_weight=.70+.30*noise
    vegetation=vigor*confidence*seasonal*gentle*height_weight*aspect_weight*near_role*lower_role*edge_balance*noise_weight*evidence
    vegetation=np.clip(vegetation,0,1)
    vegetation_retention=(1-config['vegetation_mist_attenuation']*mist)*(1-whitespace)
    vegetation_retention=np.clip(vegetation_retention,0,1)*occupied;vegetation_retention[reserve]=0
    vegetation_after=vegetation*vegetation_retention
    return {'xyz':xyz,'occupied':occupied,'depth_m':q,'valley':valley,'mist':mist,'whitespace':whitespace,
            'reserve':reserve,'terrain_retention':retention,'vegetation_before':vegetation,
            'vegetation_after':vegetation_after,'vegetation_retention':vegetation_retention,
            'evidence_valid':evidence,'current_ndvi':current,'current_observations':counts[season],
            'slope_deg':slope,'aspect_deg':aspect,'seasonal_support_valid':seasonal_valid,
            'corridor_center_x_fraction':center}
