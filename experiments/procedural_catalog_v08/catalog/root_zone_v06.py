"""Keep regional foliage and wood cues while reducing small marks at the perimeter."""
from dataclasses import replace

from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union

from .canopy_area_v04 import localize_color,regional_canopy
from .canopy_v03 import CanopyField
from .color_v03 import vegetation_color
from .ground_bands_v05 import bands
from .occlusion_v04 import hide_behind_rock
from .refined_vegetation import specimen
from .rock_families_v06 import V06

ROOT_POLICY=V06["root_canopy"]


def collective_root_zone(key,planting,solid,seed):
    """Build v04 shared canopy on the same trees used for the comparison."""
    old=[]
    logs=[]
    pads=[]
    for i,(family,x,y,height) in enumerate(planting):
        owner=f"{key}/T{i}"
        paths,area,meta=specimen(owner,family,height,(x,y),lod="mid",seed=seed+29*i,
                                 season="summer",seasonal=True)
        old.extend(paths)
        logs.append(meta)
        pads.extend((*p,owner) for p in area)
    field=CanopyField(pads,logs)
    ink,region=regional_canopy(key,old,field,seed)
    color=localize_color(vegetation_color(key,field,"summer","mid",seed),field,region["regions"])
    shown,occlusion=hide_behind_rock(ink+color,logs,solid)
    common=unary_union([Polygon(r["outer"],r["holes"]) for r in region["regions"]])
    kept=[]
    removed=[]
    for p in shown:
        small=p.role=="canopy" and p.length<=ROOT_POLICY["max_individual_mm"]
        at_edge=small and LineString(p.xy).distance(common)<=ROOT_POLICY["shared_proximity_mm"]
        fragment=small and p.length<ROOT_POLICY["far_fragment_mm"]
        (removed if at_edge or fragment else kept).append(p)
    meta=dict(specimens=logs,occ=occlusion,removed_individual=len(removed),
              removed_individual_mm=round(sum(p.length for p in removed),3),
              shared_visible=sum(p.role=="canopy_area" for p in kept),**region)
    return shown,kept,field,meta


def supported_bands(key,anchors,terrain,kind,seed,solid=None):
    reach=V06["ground"]["reach_factor"]
    return bands(key,[replace(a,reach=a.reach*reach) for a in anchors],terrain,kind,seed,solid)
