"""V0.2 offline motion IR. No controller, executable exporter or live backend.

Separate artistic samples, desired brush behavior, optional calibrated work Z,
illustrative preview trajectory and physical machine trajectory at every event.
"""
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from .models import Stroke
from .clipping import clip_stroke
from .layout import Layout
from .calibration import BrushCalibration


class Action(str,Enum):
    LIFT='lift'
    TRAVEL='travel'
    APPROACH='approach'
    CONTACT='initial_contact'
    PRESSURE='pressure_variation'
    DRAW='draw'
    RELEASE='release'
    TOOL='color_tool_request'
    WASH='wash_request'
    RELOAD='reload_request'
    MANUAL='manual_intervention'
    PAUSE='pause_checkpoint'
    RESUME='resume_preparation'


@dataclass(frozen=True)
class MotionSettings:
    profile: BrushCalibration | None = None
    mode: str = 'variable'
    constant_z_mm: float | None = None
    hover_z_mm: float = 3
    approach_z_mm: float = 1

    def __post_init__(self):
        if self.mode not in ('variable','constant'):
            raise ValueError('unknown interpretation mode')
        if not all(isfinite(v) for v in (self.hover_z_mm,self.approach_z_mm)) or not 0<self.approach_z_mm<=self.hover_z_mm:
            raise ValueError('invalid illustrative hover/approach')
        if self.mode == 'constant' and (self.constant_z_mm is None or not isfinite(self.constant_z_mm) or self.constant_z_mm>0):
            raise ValueError('constant preview depth must be explicit and nonpositive')
        if self.mode == 'variable' and self.constant_z_mm is not None:
            raise ValueError('constant depth supplied for variable mode')

    def depth(self, pressure):
        if self.mode == 'constant': return self.constant_z_mm
        return None if self.profile is None else self.profile.z_for(pressure)


@dataclass(frozen=True)
class Fragment:
    stroke: Stroke
    panel: str
    setup: str
    work_xy: tuple[tuple[float,float], ...]

    @property
    def stream(self): return f'{self.panel}_{self.stroke.medium}'


def fragments(strokes, layout: Layout):
    """Stable source order in each setup; no path reversal or nearest-neighbor.

    A is two independent jobs, each a projection of frozen source order.
    B/C share a job, interleaving panel fragments in original source order.
    """
    groups = [(p,) for p in layout.panels] if layout.mode=='A' else [layout.panels]
    for panels in groups:
        for stroke in strokes:
            pieces=[(piece,panel) for panel in panels for piece in clip_stroke(stroke,panel)]
            # A right-to-left crossing must visit P2 then P1 in a shared setup.
            # Panel names must not override original within-stroke traversal.
            pieces.sort(key=lambda pair: pair[0].source_locations[0].arc_mm)
            for piece,panel in pieces:
                yield Fragment(piece,panel.name,layout.setup(panel),
                               tuple(layout.work_xy(panel,p.x,p.y) for p in piece.points))


@dataclass(frozen=True)
class MotionEvent:
    action: Action
    setup: str
    panel: str
    medium: str
    color_slot: str
    fragment_id: str
    source_id: str
    sequence: int
    order_group: int
    work_xy: tuple[float,float] | None
    artistic_pressure: float | None
    desired_behavior: str
    preview_z_mm: float | None
    calibrated_z_mm: float | None = None
    machine_xyz: tuple[float,float,float] | None = None
    source_vertex: int | None = None
    pressure_sidecar_sha256: str | None = None


def stroke_events(fragment: Fragment, settings=MotionSettings()):
    s=fragment.stroke
    def event(action, vertex, pressure, behavior, z, calibrated=None):
        return MotionEvent(action,fragment.setup,fragment.panel,s.medium,s.color_slot,
                           s.stroke_id,s.origin_id,s.sequence,s.order_group,
                           None if vertex is None else fragment.work_xy[vertex],pressure,
                           behavior,z,calibrated,None,vertex,s.pressure_sidecar_sha256)
    first=s.points[0]
    yield event(Action.LIFT,None,None,'clear_surface',settings.hover_z_mm)
    yield event(Action.TRAVEL,0,None,'clear_surface',settings.hover_z_mm)
    yield event(Action.APPROACH,0,None,'approach_contact',settings.approach_z_mm)
    yield event(Action.CONTACT,0,None,'first_contact',0)
    for i,p in enumerate(s.points):
        z=settings.depth(p.pressure)
        calibrated=(z if settings.mode=='variable' and settings.profile is not None
                    and settings.profile.status=='measured' else None)
        yield event(Action.PRESSURE if i==0 else Action.DRAW,i,p.pressure,
                    'constant_contact_depth' if settings.mode=='constant' else 'pressure_intent_pending_brush_validation',z,calibrated)
    # Physical entry/release is separate, does not replace artistic endpoint intent.
    yield event(Action.RELEASE,len(s.points)-1,None,'release_to_contact',0)
    yield event(Action.LIFT,len(s.points)-1,None,'clear_surface',settings.hover_z_mm)


def require_output_level(level):
    if level != 1:
        raise ValueError('only offline Level 1 is implemented; Air Run/painting disabled')


def commented_preview(events):
    # Comment EVERY line, including metadata; never output an executable token.
    yield '; DATASCAPE v0.2 OFFLINE ONLY; ILLUSTRATIVE G54 WORK FRAME; NO MACHINE TRAJECTORY\n'
    for e in events:
        xy='' if e.work_xy is None else f' X{e.work_xy[0]:.6f} Y{e.work_xy[1]:.6f}'
        z=' Z_UNRESOLVED' if e.preview_z_mm is None else f' Z{e.preview_z_mm:.6f}'
        yield f'; {e.action.value} {e.fragment_id} {e.panel}/{e.medium}/{e.color_slot}{xy}{z}\n'
