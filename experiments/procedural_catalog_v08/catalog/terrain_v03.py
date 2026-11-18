"""Keep terrain behind foliage and rock, reusing the v02 core pass cap."""
import numpy as np
import shapely
from shapely.geometry import LineString

from .canopy_v03 import C,V03
from .color_v03 import project_clip,tint
from .geometry import stroke
from .masking_v02 import core_one


def terrain_fixture(key, box, seed, variant="terrace"):
    """Open horizontal sections alternate with short descending contour runs."""
    from .context import terrain
    plan = terrain(key,box,seed)
    result = []
    for j,s in enumerate(plan):
        i=s.features["line_index"]
        if i%6==1:
            continue
        q=np.asarray(s.xy)
        if variant=="terrace":
            weight=np.sin(q[:,0]*.081+i*.14)
            q[:,1]+= 1.25*weight
        if i%6==0:
            result.append(stroke(s.id,q,s.role,s.group,s.owner,True,j%2,features=s.features))
        else:
            result.append(stroke(s.id,q,s.role,s.group,s.owner,False,j%2,features=s.features))
    return result


def protect_terrain(paths, field, rocks, box):
    cfg=V03["rock"]
    pads = [(x,y,w*C["mask_pad_mix"],h*C["mask_pad_mix"],owner) for x,y,w,h,owner in field.pads]
    terrain,cores,stats=core_one(paths,pads,box)
    if rocks is None or rocks.is_empty:
        return terrain,cores,stats
    out=[]
    feather=cfg["ground_feather_mm"]
    for s in terrain:
        for p in project_clip(s,rocks,cfg["ground_min_segment_mm"],"behind_rock"):
            xy=np.asarray(p.xy)
            distance=shapely.distance(shapely.points(xy),rocks)
            t=np.clip(distance/feather,0,1)
            gain=.26+.74*t*t*(3-2*t)
            out.append(tint(p,gain))
    # A rock can split the previously selected LIGHT pass. Reassert the pass cap.
    for core in cores:
        inside=[(LineString(s.xy).intersection(core).length,i) for i,s in enumerate(out)]
        hits=[(mm,i) for mm,i in inside if mm>1e-5]
        if len(hits)>1:
            kept=max(hits)[1]
            trim={i for _,i in hits if i!=kept}
            out=[part for i,s in enumerate(out) for part in
                 (project_clip(s,core,cfg["ground_min_segment_mm"],"single_core_pass") if i in trim else [s])]
    stats["terrain_paths_after_rock"]=len(out)
    stats["terrain_mm_after_rock"]=sum(s.length for s in out)
    stats["core_passes_after_rock"]=[
        sum(LineString(s.xy).intersection(region).length>1e-5 for s in out) for region in cores
    ]
    return out,cores,stats


def attenuate_rear_rock(rocks, field, rock_records):
    """Tone down only rock paths under sufficiently dense nearer crowns."""
    front_depth = {m["id"]:m["base"][1] for m in rock_records}
    out=[]
    for s in rocks:
        owner=front_depth.get(s.owner)
        if owner is None:
            out.append(s)
            continue
        ahead=[field.owner_fields[field.index[k]] for k,log in field.logs.items()
               if k in field.index and log["base_xy"][1]>owner+8]
        if not ahead:
            out.append(s)
            continue
        e=field.read(np.sum(ahead,axis=0),s.xy)
        fade=np.clip((e-.58)/1.04,0,1)
        gain=1-fade*(.24 if s.medium=="COLOR" else .42)
        out.append(tint(s,gain))
    return out
