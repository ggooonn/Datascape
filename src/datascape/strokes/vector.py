"""Machine-independent finalized polylines, exact panel clipping and omission."""
import gzip
import hashlib
import json
import numpy as np
from scipy.ndimage import map_coordinates


def sample(image, xy, order=1, outside=0):
    """Sample the fixed one-mm pixel-center field in continuous canvas mm."""
    p = np.asarray(xy)
    image=np.asarray(image,dtype=float)
    values=map_coordinates(image,[p[:,1]-.5,p[:,0]-.5],order=order,
                           mode='nearest',prefilter=False)
    # Pixel values extend to their actual half-cell image boundaries.
    valid=(p[:,0]>=0)&(p[:,0]<image.shape[1])&(p[:,1]>=0)&(p[:,1]<image.shape[0])
    return np.where(valid,values,outside)


def resample(path, step=.4):
    p = np.asarray(path, dtype=float)
    length = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    keep = np.r_[True, np.diff(length)>1e-8]
    p, length = p[keep], length[keep]
    if len(p)<2:return p
    at = np.linspace(0,length[-1],max(2,int(np.ceil(length[-1]/step))+1))
    return np.column_stack([np.interp(at,length,p[:,i]) for i in range(2)])


def split_at_gate(path, gate, minimum_length=0):
    """Intersect zero crossings linearly; never bridge a rejected interval."""
    p=np.asarray(path);g=np.asarray(gate);result=[];current=[]
    def finish():
        if len(current)>1:
            a=np.asarray(current)
            if np.linalg.norm(np.diff(a,axis=0),axis=1).sum()>=minimum_length:result.append(a)
    for a,b,ga,gb in zip(p[:-1],p[1:],g[:-1],g[1:]):
        if ga>0 and not current:current=[a]
        if ga>0 and gb>0:current.append(b)
        elif ga>0>=gb:
            current.append(a+(b-a)*ga/(ga-gb));finish();current=[]
        elif ga<=0<gb:
            current=[a+(b-a)*(-ga)/(gb-ga),b]
    finish()
    return result


def clip_polyline(path, bounds):
    """Liang-Barsky intersections, including outside-to-outside crossings."""
    xmin,ymin,xmax,ymax=bounds;result=[];current=[]
    for a,b in zip(np.asarray(path)[:-1],np.asarray(path)[1:]):
        d=b-a;lo,hi=0.,1.;valid=True
        for p,q in [(-d[0],a[0]-xmin),(d[0],xmax-a[0]),(-d[1],a[1]-ymin),(d[1],ymax-a[1])]:
            if abs(p)<1e-14:
                if q<0:valid=False;break
            elif p<0:lo=max(lo,q/p)
            else:hi=min(hi,q/p)
        if not valid or lo>hi:
            if len(current)>1:result.append(np.asarray(current))
            current=[];continue
        start,end=a+lo*d,a+hi*d
        if current and np.linalg.norm(current[-1]-start)<1e-7:current.append(end)
        else:
            if len(current)>1:result.append(np.asarray(current))
            current=[start,end]
        if hi<1:
            if len(current)>1:result.append(np.asarray(current))
            current=[]
    if len(current)>1:result.append(np.asarray(current))
    return result


def phase(identity, seed):
    return int(hashlib.sha256(f'{seed}:{identity}'.encode()).hexdigest()[:12],16)/16**12


def omit_path(path, probability, safe_distance, identity, seed, width, minimum_length):
    """Convert retained coverage to path occupancy and length, with opaque ink.

    A low-frequency deterministic threshold creates long surviving runs. Zero
    cores and the global guard take precedence over every protection weight.
    Safety distance includes the line footprint and a sampling collar.
    """
    p=resample(path)
    if len(p)<2:return []
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    u=phase(identity,seed)
    threshold=.035+.93*(.5+.5*np.sin(2*np.pi*u+arc/13+.45*np.sin(arc/29+u*11)))
    density=sample(probability,p)-threshold
    # A >1 mm collar covers the one-mm mask cell's diagonal, segment
    # sampling interval and round cap; it is not a new composition field.
    safe=sample(safe_distance,p,order=0)-width/2-1.4
    edge=np.minimum.reduce([p[:,0]-width/2,600-width/2-p[:,0],
                            p[:,1]-width/2,898-width/2-.002-p[:,1]])
    gate=np.minimum.reduce([density,safe,edge])
    return split_at_gate(p,gate,minimum_length)


def simplify(path,tolerance=.025):
    """Bounded Ramer-Douglas-Peucker storage reduction in canvas mm."""
    p=np.asarray(path);keep={0,len(p)-1};stack=[(0,len(p)-1)]
    while stack:
        a,b=stack.pop()
        if b-a<2:continue
        d=p[b]-p[a];delta=p[a+1:b]-p[a];denom=d@d
        t=np.clip(delta@d/denom,0,1) if denom>1e-16 else np.zeros(len(delta))
        error=np.linalg.norm(delta-t[:,None]*d,axis=1);k=int(np.argmax(error))
        if error[k]>tolerance:
            index=a+1+k;keep.add(index);stack.extend([(a,index),(index,b)])
    return p[sorted(keep)]


def thin_parallel_paths(paths,minimum_length=2.4):
    """Remove near-parallel retracing within neighboring half-mm cells.

    Long curves claim space first. Transverse crossings remain possible.
    This is an explicit vector-spacing rule, independent of composition.
    """
    occupied=np.zeros((1800,1200),bool);directions=np.zeros((1800,1200,2))
    lengths=[np.linalg.norm(np.diff(p,axis=0),axis=1).sum() for p in paths]
    result=[]
    for index in np.argsort(-np.asarray(lengths),kind='stable'):
        p=resample(paths[index],.4)
        if len(p)<2:continue
        tangent=np.gradient(p,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-9)
        ij=np.floor(p*2).astype(int);blocked=np.zeros(len(p),bool)
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                x=np.clip(ij[:,0]+dx,0,1199);y=np.clip(ij[:,1]+dy,0,1799)
                blocked|=occupied[y,x]&(np.abs(np.sum(directions[y,x]*tangent,axis=1))>.8660254)
        parts=split_at_gate(p,np.where(blocked,-1.,1.),minimum_length)
        for part in parts:
            result.append(part);dense=resample(part,.3);delta=np.gradient(dense,axis=0)
            delta/=np.maximum(np.linalg.norm(delta,axis=1)[:,None],1e-9)
            xy=np.floor(dense*2).astype(int);x=np.clip(xy[:,0],0,1199);y=np.clip(xy[:,1],0,1799)
            occupied[y,x]=True;directions[y,x]=delta
    return result


def finalize(paths, method, width, metadata=None):
    """Split the continuous drawing at the seam; both backends use this set."""
    result=[];seen=set()
    for parent,path in enumerate(paths):
        for panel,bounds in enumerate([(0,0,300,898-width/2-.002),(300,0,600,898-width/2-.002)],1):
            for part in clip_polyline(path,bounds):
                xy=np.round(simplify(part),3)
                keep=np.r_[True,np.linalg.norm(np.diff(xy,axis=0),axis=1)>1e-6];xy=xy[keep]
                if len(xy)<2:continue
                signature=min(xy.tobytes(),xy[::-1].tobytes())
                if signature in seen:continue
                seen.add(signature)
                result.append({'id':f'{method}-{len(result):06d}','parent_path':parent,'panel':panel,
                    'xy_mm':xy.tolist(),'width_mm':width,'ink':'black','opacity':1,
                    'expression':{'intensity':1.0,'pressure_calibrated':False},
                    'draw_order':len(result),'reversal_allowed':True,**(metadata or {})})
    return result


def save_vectors(path, strokes, provenance):
    payload={'schema':'datascape.vector-strokes/0.1','units':'mm','origin':'upper left; y downward',
             'continuous_mm':[600,900],'panel_width_mm':300,'physical_gap_mm':40,
             'provenance':provenance,'strokes':strokes}
    data=(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n').encode()
    with open(path,'wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as g:g.write(data)


def read_vectors(path):
    with gzip.open(path,'rt') as f:return json.load(f)
