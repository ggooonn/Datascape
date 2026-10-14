"""Three separate terrain path families on the unchanged visible F2 surface."""
import numpy as np
import rasterio
import contourpy
from scipy.ndimage import binary_dilation
from scipy.interpolate import CubicSpline
from datascape.data.quality import read_valid_band
from datascape.composition.fields import sample_finite, smooth_supported
from datascape.strokes.vector import sample, resample, split_at_gate


def contours(value, occupied, levels):
    h,w=value.shape
    cg=contourpy.contour_generator(x=np.arange(w)+.5,y=np.arange(h)+.5,
                                  z=np.ma.array(value,mask=~occupied),corner_mask=False)
    for level in levels:
        for p in cg.lines(float(level)):
            if len(p)>3:yield float(level),p


def continuity_mask(base):
    """A source-surface discontinuity guard, not an omission/mist field."""
    if '_stroke_continuity' in base:return base['_stroke_continuity']
    xyz=base['xyz'];occ=base['occupied'];bad=np.zeros_like(occ)
    for axis in [0,1]:
        a=[slice(None),slice(None)];b=a.copy();a[axis]=slice(1,None);b[axis]=slice(None,-1)
        a=tuple(a);b=tuple(b)
        jump=occ[a]&occ[b]&(np.linalg.norm(xyz[a][:,:,:2]-xyz[b][:,:,:2],axis=2)>120)
        bad[a]|=jump;bad[b]|=jump
    base['_stroke_continuity']=occ&~binary_dilation(bad,iterations=1)
    return base['_stroke_continuity']


def valid_runs(path, base, expected_q=None, jump_m=100):
    """Reject projected occlusion bridges using source XY, not shade edges."""
    p=resample(path,.65)
    if len(p)<2:return []
    xyz=np.column_stack([sample(np.nan_to_num(base['xyz'][:,:,i]),p) for i in range(3)])
    valid=sample(continuity_mask(base),p,order=0)>.5
    distance=np.linalg.norm(np.diff(xyz[:,:2],axis=0),axis=1)
    jumps=distance>jump_m
    valid[:-1]&=~jumps;valid[1:]&=~jumps
    if expected_q is not None:valid&=np.abs(sample(base['depth_m'],p)-expected_q)<35
    return split_at_gate(p,np.where(valid,1.,-1.),1.5)


def taebaek_rows(base, config):
    """Camera-transverse source rows, curved by raw relief in fixed F2.

    This adapts the archived horizontal-row principle. Visibility comes from
    the existing final mapped surface, without historical horizon resets.
    A chord-length cubic spline is checked after interpolation and omission.
    """
    q=base['depth_m'];occ=base['occupied'];paths=[]
    levels=np.arange(config['first_depth_m'],np.max(q[occ]),config['depth_pitch_m'])
    for level,p in contours(q,occ,levels):
        for run in valid_runs(p,base,expected_q=level):
            coarse=resample(run,config['spline_knot_mm'])
            if len(coarse)>=4:
                t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(coarse,axis=0),axis=1))]
                at=np.linspace(0,t[-1],max(2,int(t[-1]/.5)+1))
                curve=CubicSpline(t,coarse,axis=0,bc_type='natural')(at)
                paths.extend(valid_runs(curve,base,expected_q=level))
            else:paths.append(run)
    return paths


def terrain_derivatives(master, base, config):
    """Derivatives in projected meters; Gaussian DEM is a feature only."""
    with rasterio.open(master) as ds:
        z=read_valid_band(ds,ds.descriptions.index('DEM')+1).filled(np.nan)
        smooth=smooth_supported(z,np.isfinite(z),config['derivative_sigma_m']/ds.res[0])
        # Array rows run southward: convert all derivatives to east/north.
        gy,gx=np.gradient(smooth,-ds.res[1],ds.res[0])
        hxy,hxx=np.gradient(gx,-ds.res[1],ds.res[0])
        hyy,hyx=np.gradient(gy,-ds.res[1],ds.res[0])
        xyz=base['xyz'];out={}
        for name,a in [('gx',gx),('gy',gy),('hxx',hxx),('hxy',(hxy+hyx)/2),('hyy',hyy)]:
            out[name],_=sample_finite(a,ds.transform,xyz[:,:,0],xyz[:,:,1])
    return {k:np.nan_to_num(v) for k,v in out.items()}


def structure_lines(base, derivatives, config, azimuth_deg):
    """Cross-view ridge/valley axes plus slope-weighted elevation contours.

    Axes are zero lateral-gradient loci with signed cross curvature. These
    are scale-dependent landform proxies, not mapped streams or rock edges.
    """
    occ=base['occupied'];az=np.deg2rad(azimuth_deg);rx,ry=np.cos(az),-np.sin(az)
    d=derivatives;lateral=d['gx']*rx+d['gy']*ry
    bend=d['hxx']*rx*rx+2*d['hxy']*rx*ry+d['hyy']*ry*ry
    paths=[];kind_counts={'ridge_axes':0,'valley_axes':0,'slope_contours':0}
    for _,p in contours(lateral,occ,[0]):
        c=sample(bend,p);signal=np.abs(c)-config['minimum_cross_curvature_per_m']
        for run in split_at_gate(p,signal,config['axis_minimum_mm']):
            for visible in valid_runs(run,base):
                paths.append(visible)
                key='ridge_axes' if np.median(sample(bend,visible))<0 else 'valley_axes'
                kind_counts[key]+=1
    z=base['xyz'][:,:,2];step=config['elevation_pitch_m']
    for _,p in contours(np.nan_to_num(z),occ,np.arange(step,np.nanmax(z),step)):
        # Keep broad low-ground bends and increasingly steep slope structure.
        for run in valid_runs(p,base):
            slope=sample(np.nan_to_num(base['slope_deg']),run)
            near=1-np.clip((sample(base['depth_m'],run)-600)/1000,0,1)
            salience=np.maximum(slope/30,.7*near)-.18
            for part in split_at_gate(run,salience,2):
                paths.append(part);kind_counts['slope_contours']+=1
    return paths,kind_counts


def direction_field(base, d, projection):
    """Project a terrain tangent combining aspect and the Hessian frame."""
    gx,gy=d['gx'],d['gy'];hxx,hxy,hyy=d['hxx'],d['hxy'],d['hyy']
    norm=np.maximum(np.hypot(gx,gy),1e-8);ux,uy=-gx/norm,-gy/norm
    theta=.5*np.arctan2(2*hxy,hxx-hyy)
    ex,ey=np.cos(theta),np.sin(theta)
    sign=np.where(ex*ux+ey*uy>=0,1.,-1.);ex*=sign;ey*=sign
    anis=np.sqrt((hxx-hyy)**2+4*hxy*hxy)/(np.abs(hxx)+np.abs(hyy)+1e-6)
    weight=.22*np.clip(anis,0,1)
    vx=(1-weight)*ux+weight*ex;vy=(1-weight)*uy+weight*ey
    # Gentle low ground uses the contour tangent instead of unstable aspect.
    gentle=np.clip((.06-norm)/.06,0,1)*.7
    vx,vy=(1-gentle)*vx+gentle*(-uy),(1-gentle)*vy+gentle*ux
    length=np.maximum(np.hypot(vx,vy),1e-8);vx/=length;vy/=length
    xyz=np.nan_to_num(base['xyz']).reshape(-1,3)
    tangent=np.column_stack([vx.ravel(),vy.ravel(),(gx*vx+gy*vy).ravel()])
    before,_=projection.project(xyz,600,900);after,_=projection.project(xyz+5*tangent,600,900)
    delta=(after-before).reshape(*gx.shape,2);norm2=np.maximum(np.linalg.norm(delta,axis=2),1e-8)
    field=np.nan_to_num(delta/norm2[:,:,None]);field[~base['occupied']]=0
    return field


def flow_lines(base, field, config, seed):
    """Bidirectional midpoint integration with source-jump and spacing stops."""
    h,w=base['occupied'].shape;rng=np.random.default_rng(seed);spacing=config['seed_spacing_mm']
    seeds=np.array([(x,y) for y in np.arange(spacing/2,h,spacing) for x in np.arange(spacing/2,w,spacing)])
    seeds+=rng.uniform(-.2,.2,seeds.shape)*spacing
    # A deterministic random proposal order avoids systematic horizontal rows.
    rng.shuffle(seeds);used=np.zeros((h,w),bool);paths=[];step=config['integration_step_mm']
    radius=max(1,int(config['separation_mm']));max_steps=int(config['maximum_half_length_mm']/step)
    xyz=base['xyz'];occ=continuity_mask(base)
    def get(p):
        x,y=np.floor(p).astype(int)
        if not 0<=x<w or not 0<=y<h or not occ[y,x]:return None
        return field[y,x],xyz[y,x],x,y
    for seed_xy in seeds:
        start=get(seed_xy)
        if start is None or used[start[3],start[2]]:continue
        branches=[]
        for direction in [-1,1]:
            p=seed_xy.copy();last=direction*start[0];points=[];visited=set();previous_xyz=start[1]
            for _ in range(max_steps):
                a=get(p)
                if a is None or used[a[3],a[2]]:break
                v=a[0].copy()
                if v@last<0:v=-v
                mid=get(p+.5*step*v)
                if mid is None:break
                v2=mid[0].copy()
                if v2@v<0:v2=-v2
                new=p+step*v2;b=get(new)
                if b is None or np.linalg.norm(b[1][:2]-previous_xyz[:2])>100:break
                key=(int(new[0]/3),int(new[1]/3))
                if len(points)>12 and key in visited and key!=(int(p[0]/3),int(p[1]/3)):break
                visited.add(key);points.append(new.copy());p=new;last=v2;previous_xyz=b[1]
            branches.append(points)
        path=np.array(branches[0][::-1]+[seed_xy]+branches[1])
        if len(path)<5:continue
        paths.append(path)
        for x,y in np.floor(resample(path,.8)).astype(int):
            used[max(0,y-radius):min(h,y+radius+1),max(0,x-radius):min(w,x+radius+1)]=True
    return paths
