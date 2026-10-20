"""Liang-Barsky clipping, original segment provenance and explicit seam ownership."""
from math import hypot
from .models import Point, Stroke, Panel, SourceLocation, SourceSpan

EPS = 1e-9


def _mix(a, b, t):
    # Keep original endpoint floats exact rather than round-trip interpolation.
    if t == 0: return a
    if t == 1: return b
    return Point(a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t,
                 a.pressure+(b.pressure-a.pressure)*t)


def _parameters(a, b, panel):
    # Boundary-only segments belong to the left panel. Crossing endpoints remain
    # on BOTH physical panel edges, with no duplicated positive-length seam path.
    if panel.excluded_boundary_x is not None and a.x == b.x == panel.excluded_boundary_x:
        return None
    dx, dy = b.x-a.x, b.y-a.y
    t0, t1 = 0.0, 1.0
    for q, r in ((-dx, a.x-panel.x_min), (dx, panel.x_max-a.x),
                 (-dy, a.y-panel.y_min), (dy, panel.y_max-a.y)):
        if q == 0:
            if r < 0: return None
            continue
        t = r/q
        if q < 0: t0 = max(t0, t)
        else: t1 = min(t1, t)
        if t0 >= t1: return None
    return t0, t1


def _segment(a, b, panel):
    cut = _parameters(a, b, panel)
    return None if cut is None else (_mix(a,b,cut[0]), _mix(a,b,cut[1]))


def _same(a, b):
    return a == b


def clip_stroke(stroke: Stroke, panel: Panel) -> tuple[Stroke, ...]:
    """Retain direction, all positive-length intervals and original parameters.

    No simplification, profile renormalization, minimum-length filter or welding
    across an omitted interval. Input must be an original, unclipped stroke.
    """
    if stroke.source_locations:
        raise ValueError('clip original strokes only; refusing ambiguous re-clipping')
    fragments, points, locations, spans = [], [], [], []
    arc = 0.0

    def flush():
        nonlocal points, locations, spans
        if len(points) >= 2 and any(a.x != b.x or a.y != b.y for a,b in zip(points,points[1:])):
            fragments.append((tuple(points), tuple(locations), tuple(spans)))
        points, locations, spans = [], [], []

    for index, (a,b) in enumerate(zip(stroke.points,stroke.points[1:])):
        length = hypot(b.x-a.x,b.y-a.y)
        cut = _parameters(a,b,panel)
        if cut is None:
            flush()
        else:
            lo, hi = cut
            c, d = _mix(a,b,lo), _mix(a,b,hi)
            # Continuity is a SOURCE-parameter decision, not only XY proximity.
            if points and (spans[-1].segment != index-1 or spans[-1].t_end != 1 or lo != 0):
                flush()
            if not points:
                points.append(c); locations.append(SourceLocation(index,lo,arc+lo*length))
            points.append(d); locations.append(SourceLocation(index,hi,arc+hi*length))
            spans.append(SourceSpan(index,lo,hi,arc+lo*length,arc+hi*length))
            if hi < 1: flush()
        arc += length
    flush()
    return tuple(Stroke(
        stroke_id=f'{stroke.stroke_id}__{panel.name}__{i:03d}',
        source_id=stroke.origin_id, points=pts, layer=stroke.layer,
        color_slot=stroke.color_slot, medium=stroke.medium,
        order_group=stroke.order_group, sequence=stroke.sequence,
        reorderable=stroke.reorderable, reversible=stroke.reversible,
        source_locations=loc, source_spans=span,
        pressure_sidecar_sha256=stroke.pressure_sidecar_sha256,
    ) for i,(pts,loc,span) in enumerate(fragments,1))


def clip_all(strokes, panel: Panel):
    return tuple(part for stroke in strokes for part in clip_stroke(stroke,panel))
