"""Regenerate foliage within common crown areas, independently of tree-to-tree links."""

import numpy as np
from dataclasses import replace
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
import shapely
from shapely.geometry import Polygon,box
from shapely.ops import unary_union

from .canopy_v03 import phase_schedule
from .color_v03 import project_clip,tint
from .geometry import length,resample,rng,stroke
from .rock_mass_v04 import V04

AREA=V04["canopy_area"]


def crown_regions(field):
    if len(field.owners)<2:
        return []
    second=np.partition(field.owner_fields,-2,axis=0)[-2]
    active=gaussian_filter(second,.64)>=AREA["second_owner_level"]
    step=field.step
    origin=field.origin
    strips=[]
    for iy,row in enumerate(active):
        bounds=np.flatnonzero(np.diff(np.r_[False,row,False].astype(np.int8)))
        y=origin[1]+iy*step
        strips.extend(box(origin[0]+(a-.5)*step,y-step/2,origin[0]+(b-.5)*step,y+step/2)
                      for a,b in zip(bounds[::2],bounds[1::2]))
    if not strips:
        return []
    raw=unary_union(strips).buffer(.66).buffer(-.66).simplify(.26,preserve_topology=True)
    parts=[raw] if raw.geom_type=="Polygon" else list(raw.geoms)
    return sorted((p for p in parts if p.area>=AREA["min_region_mm2"]),key=lambda p:(p.bounds[0],p.bounds[1]))


def foliage_arc(center,xspan,lean,family,hand,r):
    """Short B arch, W droop, P shelf and U upswept lobe, locally oriented."""
    t=np.linspace(-1,1,19)
    x=t*xspan/2
    ripple=r.uniform(.24,.72)*np.sin(np.pi*t+ .39)
    if family=="B":
        y=r.uniform(.74,1.40)*(t*t-.34)+ripple*.55
    elif family=="W":
        y=r.uniform(.74,1.30)*np.maximum(0,t*hand+.3)**1.55-ripple*.36
    elif family=="P":
        y=ripple*.85+.27*(t*t-.24)
    else:
        y=.51*(t*t-.2)-r.uniform(.36,.78)*t*hand+ripple*.40
    return center+np.c_[x,y+lean*x]


def generate_region(key,i,field,region,seed):
    r=rng("area leaf placement v04",key,seed,i)
    x0,y0,x1,y1=region.bounds
    prior=[]
    occupied={}
    result=[]
    # Use depth-local spacing at each slot. The envelope follows the crown, not owner pairs.
    midpoint=np.asarray(region.representative_point().coords[0])
    center_weights=[field.read(m,[midpoint])[0] for m in field.owner_fields]
    center_lod=field.logs[field.owners[int(np.argmax(center_weights))]]["lod"]
    dx,dy=AREA["slot_mm"][center_lod]
    degree=field.read(field.overlap,[midpoint])[0]
    low_density,high_density=AREA["target_ink_mm_per_mm2"]
    density=np.interp(degree,[2.,3.1],[low_density,high_density])
    target=region.area*density
    drawn=0.
    for pass_index in (0,1):
        slots=[]
        for row,y in enumerate(np.arange(y0+dy*(.39+.48*pass_index),y1+.35,dy)):
            for col,x in enumerate(np.arange(x0+dx*(.34+.27*(row%2)+.26*pass_index),x1+.37,dx)):
                center=np.array([x+r.uniform(-.77,.77),y+r.uniform(-.75,.75)])
                if shapely.contains_xy(region,center[0],center[1]):
                    slots.append((row,col,center))
        if pass_index:
            slots.sort(key=lambda item: occupied.get(tuple(np.floor(item[2]/4.5).astype(int)),0.))
        for row,col,center in slots:
            if pass_index and drawn>=target:
                break
            weights=np.asarray([field.read(m,[center])[0] for m in field.owner_fields])
            if weights.max()<=0:
                continue
            idx=int(r.choice(len(weights),p=weights**2/np.square(weights).sum()))
            m=field.logs[field.owners[idx]]
            family=m["family"]
            hand=m["growth"]["handedness"]
            lod=m["lod"]
            lo,hi=AREA["ink_length_mm"][lod]
            span=r.uniform(lo,hi)*.96
            lean=.55*field.flow([center])[0]+(.15*hand if family=="W" else r.uniform(-.16,.16))
            q=foliage_arc(center,span,lean,family,hand,r)
            s=stroke(f"{key}/leaf/{i}.{pass_index}.{row}.{col}",q,"canopy_area",key,key,
                     layer=(row+col+pass_index)%2,features={"region":i,"family":family,"lod":lod})
            strength=r.uniform(.71,.91)*(.84 if pass_index else 1.)
            for p in project_clip(tint(s,strength),region,lo-.28,"region_edge",inside=True):
                if p.length>hi+.6:
                    continue
                sample=resample(p.xy,.85)
                if prior and np.mean(cKDTree(np.vstack(prior)).query(sample)[0]<AREA["spacing_mm"])>.34:
                    continue
                totals={}
                for aa,bb in zip(sample[:-1],sample[1:]):
                    cell=tuple(np.floor((aa+bb)*.5/4.5).astype(int))
                    totals[cell]=totals.get(cell,0.)+float(np.linalg.norm(aa-bb))
                if any(occupied.get(c,0.)+mm>AREA["regional_grid_cap_mm"] for c,mm in totals.items()):
                    continue
                for c,mm in totals.items():
                    occupied[c]=occupied.get(c,0.)+mm
                prior.append(sample)
                result.append(p)
                drawn+=p.length
    return result


def regional_canopy(key, old, field, seed):
    regions=crown_regions(field)
    ink=[s for s in old if s.medium!="COLOR"]
    if not regions:
        return ink,dict(regions=[],regional_count=0,area_mm2=0.)
    common=unary_union(regions)
    woody=[]
    foliage=[]
    for s in ink:
        if s.role!="canopy":
            woody.append(s)
        else:
            # Preserve the original outline strokes outside the interior overlap.
            foliage.extend(project_clip(s,common,5.15,"periphery"))
    for i,region in enumerate(regions):
        foliage.extend(generate_region(key,i,field,region,seed))
    order=phase_schedule(foliage,field)
    paths=[s for phase in ("INK_1","INK_2","INK_3","INK_4") for items in (woody,order) for s in items if s.phase==phase]
    return paths,dict(regions=[dict(outer=list(p.exterior.coords),
                                   holes=[list(r.coords) for r in p.interiors])
                               for p in regions],
                      regional_count=sum(s.role=="canopy_area" for s in foliage),
                      area_mm2=common.area)


def localize_color(paths, field, region_records):
    """Keep the v03 palette, but localize color near actual crown areas and openings."""
    if not region_records:
        return paths
    common=unary_union([Polygon(r["outer"],r["holes"]) for r in region_records])
    result=[]
    for s in paths:
        q=resample(s.xy,.72)
        local=shapely.contains_xy(common,q[:,0],q[:,1])
        dominant=np.max([field.read(m,q) for m in field.owner_fields],axis=0)
        keep=local | (dominant>=.57)
        if np.all(keep) and (not np.any(local) or s.length<=AREA["shared_color_max_mm"]):
            result.append(s)
            continue
        d=np.linspace(0,s.length,len(q))
        source=np.r_[0,np.cumsum(np.linalg.norm(np.diff(s.xy,axis=0),axis=1))]
        ends=np.flatnonzero(np.diff(np.r_[False,keep,False].astype(np.int8)))
        for block,(a,b) in enumerate(zip(ends[::2],ends[1::2])):
            limit=AREA["shared_color_max_mm"] if np.any(local[a:b]) else np.inf
            pieces=[(a,b)]
            if d[b-1]-d[a]>limit:
                # Use similar lengths inside a lobe and leave small gaps between the pieces.
                count=int(np.ceil((d[b-1]-d[a])/limit))
                cuts=np.linspace(a,b,count+1).astype(int)
                pieces=[(start+(1 if i else 0),end-(1 if i<count-1 else 0))
                        for i,(start,end) in enumerate(zip(cuts,cuts[1:]))]
            for i,(start,end) in enumerate(pieces):
                sub=q[start:end]
                if len(sub)<2 or length(sub)<6.2:
                    continue
                phase=np.linspace(0,1,len(sub))
                factor=.68+.32*np.minimum(1.,np.minimum(phase,1.-phase)*9.)
                pressure=(np.interp(d[start:end],source,s.pressure_mm)*factor).round(6).tolist()
                result.append(replace(s,id=f"{s.id}/lobe/{block}.{i}",xy=sub.tolist(),pressure_mm=pressure,
                                      features=dict(s.features,local_canopy=bool(np.any(local[start:end])))))
    return result
