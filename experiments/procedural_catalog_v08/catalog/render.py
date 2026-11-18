"""SVG catalog masters and PNGs built directly from vector records."""
from pathlib import Path
from html import escape
from subprocess import run
import numpy as np
from .geometry import ROOT
from .context import Cover

FONT="Noto Sans CJK KR, Noto Sans KR, sans-serif"
PAPER="#faf7ed"
INK="#2d3731"
PALE="#6c7666"
LINE="#d7d6c9"

def txt(x,y,data,size=3.4,color=INK,weight=400):
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(data))}</text>'

def is_visible(s,mode):
    if mode.startswith("ink_"):
        return s.medium!="COLOR" and int(s.phase[-1])<=int(mode[-1])
    if mode=="ink":
        return s.medium!="COLOR"
    if mode=="mask":
        return s.role in {"trunk","branch","canopy","silhouette","face_boundary"}
    return True

def path_tag(s):
    xy=" ".join(f"{x:.4f},{y:.4f}" for x,y in s.xy)
    color=s.pigment or INK
    level=np.mean(s.pressure_mm)
    width=.35+.08*level if s.medium=="COLOR" else .105+.22*level
    opacity=.68 if s.medium=="COLOR" else .45+.29*min(1,level)
    return (f'<polyline points="{xy}" fill="none" stroke="{color}" stroke-width="{width:.3f}" '
            f'stroke-opacity="{opacity:.3f}" stroke-linecap="round" stroke-linejoin="round" '
            f'data-path="{escape(s.id,quote=True)}" data-owner="{escape(s.owner,quote=True)}" data-phase="{s.phase}"/>')

def svg_sheet(sheet):
    w,h=sheet.cell
    rows=(len(sheet.cards)+sheet.cols-1)//sheet.cols
    W=sheet.cols*w+22
    H=rows*(h+15)+31
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',txt(11,10,sheet.title,7.1,INK,600),
         txt(11,17,sheet.note,3.45,PALE),txt(W-49,10,"DATASCAPE / "+sheet.id[:2],3.1,PALE)]
    for i,c in enumerate(sheet.cards):
        x=11+(i%sheet.cols)*w
        y=22+(i//sheet.cols)*(h+15)
        svg+=[f'<g transform="translate({x} {y})">',
              f'<rect width="{w-3}" height="{h+11}" rx="1.0" fill="#fdfaf1" stroke="{LINE}" stroke-width=".25"/>',
              txt(3,6,c.label,4,INK,600),txt(3,10.7,c.subtitle,2.75,PALE)]
        svg.append(f'<g transform="translate(0 13)">')
        if c.mode=="mask":
            cover=Cover(c.field_pads)
            grid=np.array([[xx,yy] for yy in range(0,int(h)-4,3) for xx in range(4,int(w)-6,3)])
            for (xx,yy),val in zip(grid,cover.at(grid)):
                if val<.055:continue
                svg.append(f'<rect x="{xx-1.5}" y="{yy-1.5}" width="3" height="3" fill="#658b64" opacity="{.65*val:.3f}"/>')
        for s in c.paths:
            if is_visible(s,c.mode):
                svg.append(path_tag(s))
        svg.append(f'<path d="M {w-17} {h-5} h 10" stroke="{INK}" stroke-width=".42"/>'+txt(w-17,h-1.7,'10 mm',2.35,PALE))
        svg.append('</g></g>')
    return '\n'.join(svg+['</svg>'])

def individual_svg(paths,key):
    flat=np.vstack([s.xy for s in paths])
    xmin,ymin=flat.min(axis=0)-2.5
    xmax,ymax=flat.max(axis=0)+2.5
    w,h=xmax-xmin,ymax-ymin
    return '\n'.join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" height="{h:.3f}mm" viewBox="{xmin:.3f} {ymin:.3f} {w:.3f} {h:.3f}">',
         f'<title>{escape(key)}</title>',*[path_tag(s) for s in paths],'</svg>'])

def export_png(svg_file, png_file):
    run(["inkscape",str(svg_file),"--export-type=png",
         f"--export-filename={png_file}","--export-width=1600"],check=True,capture_output=True)
