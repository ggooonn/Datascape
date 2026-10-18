"""Exact centerline segment clipping (Liang-Barsky) with attribute interpolation."""
from .models import Point, Stroke, Panel

EPS = 1e-9


def _mix(a: Point, b: Point, t: float) -> Point:
    return Point(a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t, a.pressure+(b.pressure-a.pressure)*t)


def _segment(a: Point, b: Point, p: Panel):
    dx, dy = b.x-a.x, b.y-a.y
    t0, t1 = 0.0, 1.0
    for q, r in ((-dx, a.x-p.x_min), (dx, p.x_max-a.x), (-dy, a.y-p.y_min), (dy, p.y_max-a.y)):
        if abs(q) <= EPS:
            if r < -EPS:
                return None
            continue
        t = r/q
        if q < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1 + EPS:
            return None
    if t1-t0 <= EPS:
        return None
    return _mix(a,b,t0),_mix(a,b,t1)


def _same(a: Point, b: Point) -> bool:
    return abs(a.x-b.x)<EPS and abs(a.y-b.y)<EPS and abs(a.pressure-b.pressure)<EPS


def clip_stroke(stroke: Stroke, panel: Panel) -> tuple[Stroke, ...]:
    """Retain all intersections, including outside-to-outside crossings.

    Panel XY remains in original artwork coordinates, not panel-local XY.
    X=300 seam ownership is unresolved; shared-boundary lines occur on both panels.
    """
    fragments, current = [], []
    def flush():
        nonlocal current
        if len(current)>=2:
            fragments.append(tuple(current))
        current=[]
    for a,b in zip(stroke.points,stroke.points[1:]):
        cut=_segment(a,b,panel)
        if cut is None:
            flush()
            continue
        c,d=cut
        if current and not _same(current[-1],c):
            flush()
        if not current:
            current=[c]
        if not _same(current[-1],d):
            current.append(d)
        if not _same(d,b):
            flush()
    flush()
    return tuple(Stroke(
        stroke_id=f'{stroke.stroke_id}__{panel.name}__{i:03d}',
        source_id=stroke.origin_id, points=pts, layer=stroke.layer,
        color_slot=stroke.color_slot, medium=stroke.medium,
        order_group=stroke.order_group, sequence=stroke.sequence,
        reorderable=stroke.reorderable, reversible=stroke.reversible,
    ) for i,pts in enumerate(fragments,1))


def clip_all(strokes, panel: Panel):
    return tuple(part for stroke in strokes for part in clip_stroke(stroke,panel))
