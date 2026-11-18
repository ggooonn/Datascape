"""Explicit connected canopy cores with a measurable single LIGHT-pass cap."""
from dataclasses import replace

import numpy as np
from shapely.geometry import LineString, Point, box
from shapely.ops import linemerge, unary_union

from .geometry import resample, poly_parts, length, stroke
from .refined_vegetation import REF
from .context import Cover


def connected_cores(pads, footprint):
    cfg=REF["core"]
    step=cfg["grid_step_mm"]
    x0,y0,x1,y1=footprint
    xs=np.arange(x0+step/2,x1,step)
    ys=np.arange(y0+step/2,y1,step)
    xx,yy=np.meshgrid(xs,ys)
    field=Cover(pads)
    values=field.at(np.c_[xx.ravel(),yy.ravel()]).reshape(xx.shape)
    # Coalesce contiguous active cells along each row before polygon union.
    stripes=[]
    for y,row in zip(ys,values):
        active=row>=cfg["threshold"]
        bounds=np.flatnonzero(np.diff(np.r_[False,active,False].astype(int)))
        stripes.extend(box(xs[a]-step/2,y-step/2,xs[b-1]+step/2,y+step/2) for a,b in zip(bounds[::2],bounds[1::2]))
    if not stripes:
        return [],field
    shapes=unary_union(stripes).buffer(-.21).buffer(.21)
    geoms=[shapes] if shapes.geom_type=="Polygon" else list(shapes.geoms)
    cores=sorted((p for p in geoms if p.area>=cfg["min_area_mm2"]),key=lambda p:(p.centroid.x,p.centroid.y))
    return cores,field


def core_one(paths,pads,footprint):
    """Retain the longest contiguous segment of one LIGHT source in each core."""
    cfg=REF["core"]
    cores,field=connected_cores(pads,footprint)
    lines=[LineString(s.xy) for s in paths]
    selections=[]
    for p in cores:
        candidates=[]
        for i,(s,line) in enumerate(zip(paths,lines)):
            if s.medium!="LIGHT_INK" or not line.intersects(p):
                continue
            for part in poly_parts(line.intersection(p),cfg["min_kept_pass_mm"]):
                m=LineString(part)
                # Prefer a longer naturally crossing pass, with only a slight centroid penalty.
                candidates.append((m.length-.12*m.distance(p.centroid),i,m))
        selections.append(max(candidates,key=lambda c:(c[0],-c[1]))[1:] if candidates else None)
    result=[]
    core_union=unary_union(cores)
    for i,(s,line) in enumerate(zip(paths,lines)):
        # Only the exact selected contiguous segment is added back before extracting connected parts.
        chosen=[seg for choice in selections if choice is not None for j,seg in [choice] if i==j]
        if core_union.is_empty or not core_union.intersects(line):
            portions=[np.asarray(s.xy)]
        else:
            outside=line.difference(core_union)
            combined=unary_union([outside,*chosen])
            # Merge at snapped cut endpoints. Both halves keep their original direction and provenance.
            if combined.geom_type=="MultiLineString":
                combined=linemerge(combined)
            portions=poly_parts(combined,cfg["min_segment_mm"])
        for j,part in enumerate(portions):
            rr=resample(part,.95)
            # Keep source vertices so sampling across a cut does not sneak back into a core.
            t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(part,axis=0),axis=1))]
            tt=np.unique(np.r_[t,np.linspace(0,t[-1],len(rr))])
            q=np.c_[np.interp(tt,t,part[:,0]),np.interp(tt,t,part[:,1])]
            line_new=LineString(q)
            if line_new.length<cfg["min_segment_mm"]:
                continue
            if line.project(Point(q[0]))>line.project(Point(q[-1])):
                q=q[::-1]
            if cores:
                dist=np.array([core_union.distance(Point(x)) for x in q])
                edge=np.clip(1-dist/cfg["feather_mm"],0,1)
                edge=edge*edge*(3-2*edge)
            else:
                edge=np.zeros(len(q))
            shade=np.maximum(.76*edge,.38*field.at(q))
            medium=s.medium=="MEDIUM_INK"
            p=stroke(f"{s.id}/core_one/{j}",q,s.role,s.group,s.owner,medium,int(s.phase[-1])%2,
                     features=dict(s.features,parent=s.id))
            pressure=(np.asarray(p.pressure_mm)*(1-shade)).round(6).tolist()
            result.append(replace(p,pressure_mm=pressure,phase=s.phase))
    records=[]
    for i,p in enumerate(cores):
        active=[s for s in result if LineString(s.xy).intersection(p).length>1e-5]
        assert len(active)<=1 and all(s.medium=="LIGHT_INK" for s in active),(i,[s.id for s in active])
        records.append(dict(core=i,area_mm2=p.area,kept=[s.id for s in active],
                            kept_len_mm=sum(LineString(s.xy).intersection(p).length for s in active),
                            selected_source=None if selections[i] is None else paths[selections[i][0]].id,
                            polygon=p.exterior.coords[:],holes=[r.coords[:] for r in p.interiors]))
    return result,cores,dict(core_count=len(cores),cores=records,original_path_count=len(paths),
                             retained_path_count=len(result),input_length_mm=sum(s.length for s in paths),
                             output_length_mm=sum(s.length for s in result),footprint_mm=list(footprint))


def core_audit(paths,cores):
    return [{"core":i,"LIGHT":sum(LineString(s.xy).intersection(p).length>1e-5 for s in paths if s.medium=="LIGHT_INK"),
             "MEDIUM":sum(LineString(s.xy).intersection(p).length>1e-5 for s in paths if s.medium=="MEDIUM_INK")}
            for i,p in enumerate(cores)]
