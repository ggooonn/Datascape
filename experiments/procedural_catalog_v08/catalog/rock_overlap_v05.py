"""Rock objects retain their own silhouettes and face coordinates under depth masking."""
from dataclasses import dataclass
import json

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .color_v03 import project_clip
from .geometry import ROOT
from .rock_surface_v03 import R, rock

V05=json.loads((ROOT/"config/catalog_v05.json").read_text())
EPS=V05["rock_mask"]["epsilon_mm"]


@dataclass(frozen=True)
class Placement:
    id: str
    shape: str
    x: float
    y: float
    width: float
    depth: int
    seed: int
    bedding: float=-.12
    lod: str="near"


@dataclass(frozen=True)
class RockObject:
    paths: list
    outline: Polygon
    record: dict
    depth: int


def make_rocks(placements):
    objects=[]
    for item in placements:
        paths,outline,record=rock(item.id,item.shape,(item.x,item.y),item.width,item.seed,
                                  lod=item.lod,bedding=item.bedding)
        paths=[p for p in paths if p.role!="rock_ground_color"]
        objects.append(RockObject(paths,outline,record,item.depth))
    return objects


def compose(objects):
    """Project the stack from near to far, returning only the visible line segments."""
    objects=sorted(objects,key=lambda r:r.depth)
    if len({r.depth for r in objects})!=len(objects):
        raise ValueError("Every rock in an overlapping study needs a distinct depth rank")
    if len({r.record["id"] for r in objects})!=len(objects):
        raise ValueError("Rock identifiers must be distinct")
    visible={}
    audit={}
    mask=Polygon()
    for obj in reversed(objects):
        keep=[]
        hidden=0.
        trimmed=0
        for s in obj.paths:
            line=LineString(s.xy)
            cut=line.intersection(mask).length if not mask.is_empty else 0.
            if cut<=EPS:
                keep.append(s)
                continue
            min_key="color_min_mm" if s.medium=="COLOR" else "ink_min_mm"
            pieces=project_clip(s,mask,R[min_key][obj.record["lod"]],"rock_masked")
            keep.extend(pieces)
            hidden+=cut
            trimmed+=1
        visible[obj.record["id"]]=keep
        audit[obj.record["id"]]={
            "depth":obj.depth,"source_paths":len(obj.paths),"visible_paths":len(keep),
            "trimmed_source_paths":trimmed,"hidden_line_mm":round(hidden,4),
            "outline_covered_mm2":round(obj.outline.intersection(mask).area,4),
            "visible_area_mm2":round(obj.outline.difference(mask).area,4),
        }
        mask=mask.union(obj.outline)
    shown=[p for o in objects for p in visible[o.record["id"]]]
    record={
        "rocks":[dict(o.record,depth=o.depth) for o in objects],
        "mask_audit":audit,
        "order_back_to_front":[o.record["id"] for o in objects],
        "overlapping_pairs":[[a.record["id"],b.record["id"]] for i,a in enumerate(objects) for b in objects[i+1:]
                             if a.outline.intersection(b.outline).area>EPS],
    }
    return shown,mask,record


def projected_mask(records,depth):
    """Use outlines solely as an occlusion mask for the requested depth."""
    return unary_union([Polygon(r["outline"]) for r in records if r["depth"]>depth])
