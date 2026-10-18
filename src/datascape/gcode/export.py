"""Generate NON-EXECUTABLE commented G-code previews only.

Hardware validation is pending. No runnable machine G-code is exported.
"""
from .models import Panel
from .planning import Motion


def preview_gcode(motions: tuple[Motion,...],panel: Panel) -> str:
    rows=['(DATASCAPE v0.1 - OFFLINE PREVIEW ONLY)',
          '(NOT EXECUTABLE - NO CALIBRATED MACHINE TRANSFORM OR Z LIMITS)',
          '(All motion lines commented out. DO NOT SEND TO FLUIDNC.)',
          '(XY REMAINS IN ORIGINAL ARTWORK COORDINATES)',
          f'(PANEL {panel.name}: X{panel.x_min:g}..{panel.x_max:g}, Y{panel.y_min:g}..{panel.y_max:g})',
          '(G21 mm, G90 absolute - informational only)']
    for m in motions:
        cmd='G0' if m.action in ('lift','travel') else 'G1'
        axes=[]
        if m.x is not None: axes.append(f'X{m.x:.3f}')
        if m.y is not None: axes.append(f'Y{m.y:.3f}')
        axes.append(f'Z{m.z:.3f}')
        rows.append(f'(ACTION {m.action}; ID={m.stroke_id}; SLOT={m.color_slot})')
        rows.append('; '+cmd+' '+' '.join(axes))
    rows.append('(END PREVIEW)')
    return '\n'.join(rows)+'\n'


def preview_svg(strokes,panel:Panel) -> str:
    # Illustrative centerline only; no brush footprint.
    import html
    head=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{panel.x_min:g} {panel.y_min:g} {panel.x_max-panel.x_min:g} {panel.y_max-panel.y_min:g}" width="300" height="900">',
          '<rect width="100%" height="100%" fill="white"/>']
    for s in strokes:
        p=' '.join(f'{point.x:.3f},{point.y:.3f}' for point in s.points)
        head.append(f'<polyline points="{p}" fill="none" stroke="#222" stroke-width="0.6"><title>{html.escape(s.stroke_id)}</title></polyline>')
    return '\n'.join(head+['</svg>'])+'\n'
