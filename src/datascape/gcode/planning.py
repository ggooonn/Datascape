"""Offline plans; XY transforms, calibrated force and FluidNC I/O excluded."""
from dataclasses import dataclass
from .models import Stroke, Panel
from .clipping import clip_all
from .scheduling import schedule


@dataclass(frozen=True)
class Motion:
    action: str  # lift, travel, touch, draw
    x: float | None
    y: float | None
    z: float
    stroke_id: str | None = None
    color_slot: str | None = None


@dataclass(frozen=True)
class PreviewProfile:
    hover_z: float = 5.0
    draw_min_z: float = -12.0

    def __post_init__(self):
        if self.hover_z <= 0 or self.draw_min_z > 0:
            raise ValueError('invalid preview Z conventions')

    def intent_to_z(self, pressure: float) -> float:
        # Illustrative linear intent mapping ONLY; NOT calibrated pressure/width.
        return self.draw_min_z*pressure


def plan(strokes: tuple[Stroke,...],panel:Panel,profile=PreviewProfile(),medium=None):
    if medium not in (None,'ink','color'):
        raise ValueError('unknown medium')
    selected=tuple(s for s in strokes if medium is None or s.medium==medium)
    ordered=schedule(clip_all(selected,panel))
    motions=[]
    for stroke in ordered:
        first=stroke.points[0]
        motions.extend((Motion('lift',None,None,profile.hover_z,stroke.stroke_id),
                        Motion('travel',first.x,first.y,profile.hover_z,stroke.stroke_id),
                        Motion('touch',first.x,first.y,profile.intent_to_z(first.pressure),stroke.stroke_id,stroke.color_slot)))
        for p in stroke.points[1:]:
            motions.append(Motion('draw',p.x,p.y,profile.intent_to_z(p.pressure),stroke.stroke_id,stroke.color_slot))
        motions.append(Motion('lift',None,None,profile.hover_z,stroke.stroke_id))
    return tuple(motions),ordered
