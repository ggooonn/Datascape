"""Terrain-evidenced, oblique middle-distance release without a cut band."""
from shared import *

def valley_path(f,anchors,width_mm=45):
    """Dynamic path follows valley evidence within a broad authored gaze prior.

    The prior selects a compositional territory. Actual valley/ridge evidence
    selects the route inside it. Neither camera nor source terrain is warped.
    """
    b=f['base'];feat=f['features'];height,width=b['occupied'].shape
    xx=np.arange(12,width-12,3,dtype=int)
    yy=np.arange(280,min(800,height-2),5,dtype=int)
    valley=np.maximum(feat['valley_small'],.72*feat['valley_medium'])
    valley=gaussian_filter(np.nan_to_num(valley),3)
    ridge=gaussian_filter(np.nan_to_num(feat['ridge']),2)
    prior_x=np.interp(yy,np.asarray(anchors)[:,1],np.asarray(anchors)[:,0])
    cost=np.zeros((len(yy),len(xx)));parents=np.zeros_like(cost,dtype=int)
    for j,y in enumerate(yy):
        valid=b['occupied'][y,xx]
        local=.85*((xx-prior_x[j])/95)**2+1.2*ridge[y,xx]-1.7*valley[y,xx]+3*(~valid)
        if j==0:cost[j]=local;continue
        choices=[]
        for shift in range(-4,5):
            ids=np.arange(len(xx))+shift
            choices.append(np.where((ids>=0)&(ids<len(xx)),cost[j-1,np.clip(ids,0,len(xx)-1)]+.065*shift*shift,np.inf))
        choices=np.asarray(choices);best=choices.argmin(axis=0)
        parents[j]=np.arange(len(xx))+best-4
        cost[j]=local+choices[best,np.arange(len(xx))]
    k=int(cost[-1].argmin());indices=[k]
    for j in range(len(yy)-1,0,-1):k=int(parents[j,k]);indices.append(k)
    xs=gaussian_filter1d(xx[np.asarray(indices[::-1])].astype(float),1.25)
    points=np.c_[xs+.5,yy+.5]
    mask=np.zeros((height,width),bool)
    mask[np.clip(yy,0,height-1),np.clip(np.round(xs).astype(int),0,width-1)]=True
    # Fill the five-mm sampling intervals before measuring ribbon distance.
    for a,z in zip(points[:-1],points[1:]):
        p=np.linspace(a,z,12).astype(int);mask[p[:,1],p[:,0]]=True
    distance=distance_transform_edt(~mask)
    ribbon=np.exp(-.5*(distance/width_mm)**2)
    ribbon*=.80+.20*valley
    ribbon*=1-.36*ridge
    return points,np.clip(ribbon,0,1),valley,ridge

def release(f,recipe):
    original=f['retention'];b=f['base'];q=b['depth_m'];yy,xx=np.mgrid[:original.shape[0],:original.shape[1]]
    points,ribbon,valley,ridge=valley_path(f,recipe['anchors_mm'],recipe['width_mm'])
    scope=smoothstep((q-1050)/400)*(1-smoothstep((q-3000)/600))
    scope*=smoothstep((yy-230)/90)*(1-smoothstep((yy-735)/65))*b['occupied']
    # The inherited horizontal near/middle core is replaced only inside this
    # depth-local envelope. Global top/bottom reserves remain unconditional.
    local=np.clip(recipe.get('retained_floor',.84)+.14*ridge-.18*valley,0,1)
    local*=1-recipe.get('release_strength',.97)*ribbon
    target=f['refined']['global_retention']*local*b['occupied']
    new=(1-scope)*original+scope*target
    new*=b['occupied'];new=np.minimum(new,f['refined']['global_retention'])
    result={**f,'retention':new,'_grammar_safe':distance_transform_edt((new>0)&b['occupied'])}
    result['refined']={**f['refined']}
    evidence=[]
    for p in points[::4]:
        x,y=p;ix,iy=int(x),int(y)
        if b['occupied'][iy,ix]:
            evidence.append(dict(xy_mm=p.tolist(),source_xyz_utm_m=b['xyz'][iy,ix].tolist(),source_forward_m=float(q[iy,ix]),valley_score=float(valley[iy,ix]),ridge_score=float(ridge[iy,ix])))
    active=scope>.15
    metrics={}
    for side,mask in [('left',xx<300),('right',xx>=300)]:
        m=mask&active
        metrics[side]=dict(pixels=int(m.sum()),mean_retention=float(new[m].mean()) if m.any() else None)
    record=dict(recipe=recipe,route_source_evidence=evidence,scope='Source-depth envelope 1050–3600 m; no camera/DEM warp',
        left_right=metrics,global_reserve_override_pixels=int((new>f['refined']['global_retention']+1e-12).sum()),
        route_x_span_mm=float(np.ptp(points[:,0])),mean_abs_change=float(np.abs(new-original)[active].mean()) if active.any() else 0.)
    return result,dict(ribbon=ribbon,scope=scope,original=original,new=new,points=points,valley=valley,ridge=ridge),record

