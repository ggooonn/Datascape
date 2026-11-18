"""Generate native vector records, focused SVG plates, PNGs, and audit tables."""
import argparse
import csv
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path
import gzip

import numpy as np

from .audit_v03 import canopy_audit,path_audit
from .catalog_v02 import compact
from .geometry import ROOT
from .render import FONT,INK,LINE,PAPER,PALE,export_png,individual_svg,txt
from .sheets_v03 import assemble


def selected(card):
    if card.mode in {"ink","shared"}:
        return [p for p in card.paths if p.medium!="COLOR"]
    if card.mode=="color":
        return [p for p in card.paths if p.medium=="COLOR"]
    return card.paths


def ribbon(path, emphasis=False):
    """Render continuous vectors as tapered lines for review."""
    xy=np.asarray(path.xy)
    tangent=np.gradient(xy,axis=0)
    norm=np.linalg.norm(tangent,axis=1)
    across=np.c_[-tangent[:,1],tangent[:,0]]/np.maximum(norm[:,None],1e-10)
    p=np.asarray(path.pressure_mm)
    if path.medium=="COLOR":
        color=path.pigment
        width=.14+.99*p
        opacity=.73
    elif path.role=="terrain_A":
        color="#5a6154"
        width=.026+.39*p
        opacity=.62
    else:
        color="#395d49" if emphasis and path.role=="shared_canopy" else "#2e3830"
        width=.069+.45*p
        opacity=.84 if path.medium=="MEDIUM_INK" else .75
        if emphasis and path.role=="shared_canopy":
            width*=1.59
            opacity=.93
    shape=np.vstack([xy+across*width[:,None]/2,(xy-across*width[:,None]/2)[::-1]])
    pts=" ".join(f"{x:.4f},{y:.4f}" for x,y in shape)
    return f'<polygon points="{pts}" fill="{color}" opacity="{opacity}" data-id="{escape(path.id,quote=True)}"/>'


def plate(sheet):
    w,h=sheet.cell
    width=sheet.cols*w+22
    n=(len(sheet.cards)+sheet.cols-1)//sheet.cols
    height=n*(h+17)+28
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
         f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
         f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
         txt(11,10,sheet.title,7.3,INK,650),txt(11,17,sheet.note,3.4,PALE),
         txt(width-45,9,"DATASCAPE / "+sheet.key[:2],3.15,PALE)]
    for i,card in enumerate(sheet.cards):
        x=11+w*(i%sheet.cols)
        y=22+(h+17)*(i//sheet.cols)
        out+=[f'<g transform="translate({x} {y})">',
              f'<rect width="{w-3}" height="{h+12}" rx="1" fill="#fdfaf1" stroke="{LINE}" stroke-width=".29"/>',
              txt(4,6,card.title,4.25,INK,650),txt(4,11,card.note,2.82,PALE)]
        if card.crop:
            cx,cy,cw,ch=card.crop
            bar_scale=min((w-13)/cw,(h-9)/ch)
            clip_id=f"crop_{sheet.key}_{i}"
            dx=5+((w-13)-cw*bar_scale)/2
            dy=14+((h-9)-ch*bar_scale)/2
            out += [f'<clipPath id="{clip_id}" clipPathUnits="userSpaceOnUse">'
                    f'<rect x="{dx}" y="{dy}" width="{cw*bar_scale}" height="{ch*bar_scale}"/></clipPath>',
                    f'<g clip-path="url(#{clip_id})">',
                    f'<g transform="translate({dx} {dy}) scale({bar_scale}) translate({-cx} {-cy})">']
        else:
            out.append('<g transform="translate(0 13)">')
            bar_scale=1.
        # Review colors sit underneath the structural ink. The data retains material phases.
        paths=selected(card)
        for path in sorted(paths,key=lambda p: 0 if p.medium=="COLOR" else 1):
            out.append(ribbon(path,card.mode=="shared"))
        out.append('</g></g>' if card.crop else '</g>')
        a=5 if card.crop else 10
        out += [f'<path d="M {w-10-a*bar_scale:.2f} {h+5.7} h {a*bar_scale:.2f}" stroke="{INK}" stroke-width=".42"/>',
                txt(w-10-a*bar_scale,h+9.2,f"{a} mm",2.65,PALE),'</g>']
    return "\n".join(out+["</svg>"])


def generate(destination=ROOT, no_png=False):
    for name in ("review","vectors","audit"):
        (destination/name).mkdir(parents=True,exist_ok=True)
    inventory = {}
    data_rows = []
    for sheet in assemble():
        svg_file=destination/"review"/f"{sheet.key}.svg"
        svg_file.write_text(plate(sheet),encoding="utf-8")
        if not no_png:
            export_png(svg_file,svg_file.with_suffix(".png"))
        for i,c in enumerate(sheet.cards,1):
            paths=selected(c)
            name=f"{sheet.key}__{i:02}"
            plan=dict(key=c.key,title=c.title,mode=c.mode,detail_crop_mm=c.crop,
                      metadata=c.meta,strokes=[asdict(p) for p in paths])
            raw=compact(plan)
            (destination/"vectors"/f"{name}.svg").write_text(individual_svg(paths,name),encoding="utf-8")
            (destination/"vectors"/f"{name}.json.gz").write_bytes(gzip.compress(raw,mtime=0))
            inventory[name]=sha256(raw).hexdigest()
            stats=path_audit(paths)
            if c.field is not None:
                stats["canopy"]=canopy_audit(paths,c.field)
            data_rows.append(dict(id=name,key=c.key,title=c.title,crop_mm=c.crop,**stats))
        print(sheet.key,len(sheet.cards),"states",flush=True)
    (destination/"audit"/"path_metrics.json").write_bytes(compact(data_rows))
    (destination/"audit"/"vector_hashes.json").write_bytes(compact(inventory))
    with (destination/"audit"/"path_metrics.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        fields=["id","key","title","paths","mm","short_under_6mm","middle_mm","vertices","turn_p95_deg",
                "interpath_air_mm","same_phase_neighbor_pairs","ink_paths","color_paths","ink_mm","color_mm"]
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for m in data_rows:
            t=m["materials"]
            writer.writerow(dict({k:m[k] for k in fields if k in m},
                                 ink_paths=t["LIGHT_INK"]["paths"]+t["MEDIUM_INK"]["paths"],
                                 ink_mm=round(t["LIGHT_INK"]["mm"]+t["MEDIUM_INK"]["mm"],2),
                                 color_paths=t["COLOR"]["paths"],color_mm=t["COLOR"]["mm"]))
    return data_rows


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--no-png",action="store_true")
    opts=parser.parse_args()
    generate(opts.output,opts.no_png)
