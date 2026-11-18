"""Terrain support, directional ground paths and group-aware mask operations."""
from dataclasses import replace
import numpy as np
from shapely.geometry import Point
from .geometry import CFG, rng, stroke, curve, length, resample

class Cover:
    def __init__(self, pads):
        self.pads=np.asarray([p[:4] for p in pads],float).reshape(-1,4)
        self.owners=np.array([p[4] for p in pads])

    def at(self, xy, exclude=None):
        coords=np.asarray(xy,float)
        possible=self.pads if exclude is None else self.pads[self.owners!=exclude]
        if not len(possible):return np.zeros(len(coords))
        d=(coords[:,None,:]-possible[None,:,:2])/possible[None,:,2:]
        energy=np.exp(-.5*np.sum(d*d,axis=2))
        return np.clip((energy.sum(axis=1)-.20)/2.05,0,1)

def terrain(key, box, seed):
    x0,y0,x1,y1=box
    r=rng("terrain",seed,key)
    plan=[]
    for i,y in enumerate(np.linspace(y0,y1,23)):
        u=np.linspace(x0,x1,105)
        wav=2.8*np.sin(u*.040+i*.17)+1.7*np.sin(u*.019-1.2)
        q=np.c_[u,y+wav+((u-x0)/(x1-x0)-.5)*4.4]
        # Real drawable gaps preserve a rhythm in the comparison fixture itself.
        ranges=[(0,105)] if i%4!=2 else [(0,43),(49,105)]
        for j,(a,b) in enumerate(ranges):
            p=q[a:b]
            plan.append(stroke(f"{key}/A/{i:02}/{j}",p,"terrain_A",key,key,False,i%2,
                               features=dict(line_index=i,source="synthetic terrain test vector")))
    return plan

def soil_support(key, roots, rocks, season="spring"):
    result=[]
    for i,(x,y) in enumerate(roots):
        for j in range(2):
            sign=(-1)**j
            q=curve([[x,y],[x+sign*4.2,y+1.5],[x+sign*(8+j*3),y+4.1],
                     [x+sign*(14+j*4),y+6.1]])
            result.append(stroke(f"{key}/root/{i}/{j}",q,"root_soil",key,key,False,j))
        if i%2==0:
            q=curve([[x-11,y+5.0],[x-4,y+6],[x+6,y+5.7],[x+15,y+5.9]])
            result.append(stroke(f"{key}/support_color/{i}",q,"soil_color",key,key,pigment=CFG["palette"]["soil"][i%2]))
    if rocks and not rocks.is_empty:
        x0,y0,x1,y1=rocks.bounds
        for i in range(4):
            x=x0+(x1-x0)*(.12+.19*i)
            y=y1+i*.71
            p=curve([[x-10,y+3.3],[x-3,y+3.],[x+5,y+3.6],[x+12,y+4.4]])
            result.append(stroke(f"{key}/foot/{i}",p,"rock_soil_contact",key,key,False,i%2))
    return result

def terrain_mask(paths, canopy, rocks=None, weak=False):
    result=[]
    before=sum(s.length for s in paths)
    total=0.
    for s in paths:
        q=resample(s.xy,1.1)
        field=canopy.at(q)
        if rocks is not None:
            d=np.array([rocks.distance(Point(z)) for z in q])
            field=np.maximum(field,np.exp(-.5*(d/2.1)**2)*.94)
        cfg=CFG["community"]
        skip_stride=cfg["terrain_core_keep_stride"]
        mask_threshold=.76 if not weak else .97
        removed=(field>mask_threshold)&(s.features.get("line_index",0)%skip_stride!=0)
        bounds=np.flatnonzero(np.diff(np.r_[False,~removed,False].astype(int)))
        for k,(a,b) in enumerate(zip(bounds[::2],bounds[1::2])):
            p=q[a:b]
            if len(p)<2 or length(p)<5.2:continue
            pressure=np.asarray(stroke(s.id,p,s.role,s.group,s.owner).pressure_mm)
            atten=(.30 if weak else cfg["terrain_core_attenuation"])*field[a:b]
            ident=f"{s.id}/visible{k}"
            result.append(replace(s,id=ident,xy=p.tolist(),pressure_mm=(pressure*(1-atten)).round(6).tolist(),
                                   features=dict(s.features,mask_mean=float(np.mean(field[a:b])),source_path=s.id)))
            total+=length(p)
    return result,dict(original_terrain_mm=before,retained_terrain_mm=total,
                       geometric_omission_mm=before-total,remaining_pressure_feather=True)

def vegetation_masks(paths,pads_by_group,depth_order):
    """Weak intra-community attenuation and selective nearer-layer occlusion."""
    cfg=CFG["community"]
    covers={g:Cover(pads) for g,pads in pads_by_group.items()}
    order={g:i for i,g in enumerate(depth_order)}
    result=[]
    for s in paths:
        if s.role!="canopy":
            result.append(s)
            continue
        value=covers[s.group].at(s.xy,exclude=s.owner) if s.group in covers else np.zeros(len(s.xy))
        f=1-cfg["same_community_attenuation"]*value
        for g,i in order.items():
            if i>order.get(s.group,-1):
                # Only overlap with the concentrated nearer core modifies rear foliage.
                core=np.clip((covers[g].at(s.xy)-.42)/.58,0,1)
                f*=1-cfg["distinct_front_attenuation"]*core
        result.append(replace(s,pressure_mm=(np.asarray(s.pressure_mm)*f).round(6).tolist(),
                       features=dict(s.features,mutual_mask_max_attenuation=float(1-f.min()))))
    return result
