"""Short, near-horizontal ground color paths supported by local A-line tangents."""
from dataclasses import dataclass
import math

import numpy as np
from shapely.geometry import Polygon

from .color_v03 import project_clip, tint
from .geometry import rng,stroke
from .rock_mass_v04 import vertical_slice
from .rock_overlap_v05 import V05

G=V05["ground"]


@dataclass(frozen=True)
class Anchor:
    x: float
    y: float
    reach: float


def a_slopes(lines,anchors):
    """Read the nearest actual A segments within the local radius."""
    pieces=[np.asarray(p.xy) for p in lines if p.role=="terrain_A"]
    if not pieces:
        return [0.]*len(anchors)
    starts=np.vstack([p[:-1] for p in pieces])
    v=np.vstack([np.diff(p,axis=0) for p in pieces])
    norm2=np.einsum("ij,ij->i",v,v)
    slopes=[]
    for a in anchors:
        distance=np.array([a.x,a.y])-starts
        t=np.clip(np.einsum("ij,ij->i",distance,v)/np.maximum(1e-9,norm2),0.,1.)
        angular=(np.abs(v[:,0])>1e-7)
        metric=np.where(angular,np.linalg.norm(distance-t[:,None]*v,axis=1),np.inf)
        i=int(np.argmin(metric))
        slopes.append(float(v[i,1]/v[i,0]) if metric[i]<=G["a_radius_mm"] else 0.)
    return slopes


def rock_anchors(objects,mask,front_ids):
    result=[]
    for o in objects:
        if o.record["id"] not in front_ids:
            continue
        x,y=o.record["base"]
        section=vertical_slice(mask,x)
        if section is not None:
            y=max(y,section[1])
        result.append(Anchor(x,y,float(np.clip(o.record["width"]*.72,19,48))))
    return result


def root_anchors(specimens):
    if not specimens:
        return []
    rows=sorted(specimens,key=lambda m:m["base_xy"][0])
    groups=[[rows[0]]]
    for left,right in zip(rows,rows[1:]):
        if right["base_xy"][0]-left["base_xy"][0]>24:
            groups.append([])
        groups[-1].append(right)
    result=[]
    for group in groups:
        a=np.asarray([x["base_xy"] for x in group])
        heights=np.asarray([x["height_mm"] for x in group])
        # The band is read at the foremost visible roots of each pocket.
        front=(a[:,1]-a[:,1].min())/max(1.,np.ptp(a[:,1]))
        weight=heights*(.35+.65*front)
        result.append(Anchor(float(np.average(a[:,0],weights=weight)),float(np.percentile(a[:,1],89)),
                           float(np.clip(np.ptp(a[:,0])*.92+13,21,45))))
    return result


def bands(key,anchors,terrain,kind,seed,mask=None):
    """Place sparse pigment bands close to object bases."""
    black=mask.buffer(.28) if mask is not None and not mask.is_empty else Polygon()
    random=rng("restrained bands v05",key,seed)
    out=[]
    limit=math.tan(math.radians(G["max_tangent_deg"]))
    base_limit=math.tan(math.radians(G["base_slope_limit_deg"]))
    for i,(a,a_slope) in enumerate(zip(anchors,a_slopes(terrain,anchors))):
        bias=float(np.clip(G["a_weight"]*a_slope,-base_limit,base_limit))
        for j,(height,gain) in enumerate(zip(G["row_offsets_mm"],[1.,.86,.65,.40])):
            width=a.reach*gain*random.uniform(.91,1.08)
            shift=a.reach*random.uniform(-.12,.12)
            x=np.linspace(a.x-width/2+shift,a.x+width/2+shift,max(18,int(width/.60)))
            gentle=random.uniform(.9,1.2)*.025*np.cos((x[:-1]-a.x)*.20+j*.69)
            slope=np.clip(bias+gentle,-limit,limit)
            y=np.r_[0,np.cumsum(slope*np.diff(x))]
            d=random.uniform(-.25,.33)
            y+=a.y+height+d-y[len(y)//2]
            pigment=G["colors"][kind][1 if j in (1,3) else 0]
            s=stroke(f"{key}/band/{i}.{j}",np.c_[x,y],f"{kind}_ground_band",key,key,pigment=pigment,
                      features={"a_slope":round(a_slope,8),"a_weight":G["a_weight"],
                                "base_slope":round(bias,8),"anchor":[a.x,a.y],"row":j})
            s=tint(s,.70-.084*j)
            out.extend(project_clip(s,black,G["min_path_mm"],"toe"))
    return out
