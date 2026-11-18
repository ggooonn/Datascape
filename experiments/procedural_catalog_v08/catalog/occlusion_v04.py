"""Explicit projected root placement and front-rock clipping."""
from shapely.geometry import LineString, Point

from .color_v03 import project_clip
from .rock_mass_v04 import V04,vertical_slice

DEPTH=V04["occlusion"]


def placement(root,body):
    x,y=root
    local=vertical_slice(body,x)
    if local:
        return "behind" if y<=local[1]+DEPTH["root_behind_margin_mm"] else "ambiguous_foreground"
    return "beside" if body.distance(Point(root))>=DEPTH["beside_margin_mm"] else "behind_edge"


def hide_behind_rock(vegetation,logs,body):
    """Clip behind and side specimens against the rock. Validate placement before sharing foliage."""
    owners={m["id"]:placement(m["base_xy"],body) for m in logs}
    ambiguous=[key for key,value in owners.items() if value=="ambiguous_foreground"]
    if ambiguous:
        raise ValueError(f"Re-site these roots beside or behind the rock before canopy generation: {ambiguous}")
    visible=[]
    for s in vegetation:
        minimum=DEPTH["color_min_mm"] if s.medium=="COLOR" else DEPTH["ink_min_mm"]
        visible.extend(project_clip(s,body,minimum,"rock_occluded"))
    inside=lambda paths:sum(LineString(s.xy).intersection(body).length for s in paths)
    return visible,dict(placement=owners,inside_mm_before=inside(vegetation),
                        inside_mm_after=inside(visible),
                        original_count=len(vegetation),visible_count=len(visible))
