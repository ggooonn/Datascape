"""Export scoped comparison plates, native vectors, and objective measures."""
from collections import Counter
from dataclasses import asdict
from html import escape
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json

import numpy as np
from shapely.geometry import LineString
from shapely.strtree import STRtree

from .geometry import ROOT, resample
from .refined_vegetation import WOODY
from .render import FONT,PAPER,INK,PALE,LINE,txt,path_tag,individual_svg,export_png
from .sheets_v02 import assemble

FAMILY_COLOR={"B":"#466e5a","P":"#8c7858","U":"#8c9f72","W":"#606a91"}


def poly_tag(xy,fill,outline,opacity=.72):
    s=" ".join(f"{x:.4f},{y:.4f}" for x,y in xy)
    return f'<polygon points="{s}" fill="{fill}" stroke="{outline}" stroke-width=".29" opacity="{opacity}"/>'


def terrain_preview(s, color=INK):
    """Preview relative attenuation at each vertex of a continuous terrain path."""
    xy=np.asarray(s.xy)
    tangent=np.gradient(xy,axis=0)
    unit=tangent/np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-10)
    normal=np.c_[-unit[:,1],unit[:,0]]
    half_width=(.035+.20*np.asarray(s.pressure_mm))[:,None]/2
    ribbon=np.vstack([xy+normal*half_width,(xy-normal*half_width)[::-1]])
    return poly_tag(ribbon,color,"none",.72)


def plate(sheet):
    w,h=sheet.cell
    W=sheet.cols*w+22
    H=((len(sheet.cards)+sheet.cols-1)//sheet.cols)*(h+15)+31
    elements=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
              f'viewBox="0 0 {W} {H}" font-family="{FONT}">',
              f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',txt(11,10,sheet.title,7.1,INK,600),
              txt(11,17,sheet.note,3.32,PALE),txt(W-46,10,"DATASCAPE / "+sheet.id[:2],3.1,PALE)]
    for i,c in enumerate(sheet.cards):
        x=11+(i%sheet.cols)*w
        y=22+(i//sheet.cols)*(h+15)
        elements+=[f'<g transform="translate({x} {y})">',
                   f'<rect width="{w-3}" height="{h+11}" rx="1" fill="#fdfaf2" stroke="{LINE}" stroke-width=".25"/>',
                   txt(4,6,c.label,4.18,INK,650),txt(4,11,c.subtitle,2.85,PALE),
                   '<g transform="translate(0 13)">']
        if c.overlay=="core":
            elements.extend(poly_tag(r["polygon"],"#d2e1c9","#67966e") for r in c.meta["terrain"]["cores"])
        for s in c.paths:
            if s.role=="terrain_A" and sheet.id in {"08_MASK","09_SAME_SITE","10_COMMUNITIES"}:
                color=INK
                if c.overlay=="core":
                    color="#a35e46" if s.medium=="MEDIUM_INK" else "#365d4c"
                elements.append(terrain_preview(s,color))
            else:
                elements.append(path_tag(s))
        if c.overlay=="bases":
            base=np.array([s["base_xy"] for s in c.meta["specimens"]])
            elements.append(f'<rect x="8" y="{h-42}" width="{w-22}" height="35" fill="#f3f0e4" stroke="{LINE}" stroke-width=".24"/>')
            elements.append(txt(10,h-36,"뒤쪽 ↑",2.8,PALE))
            elements.append(txt(10,h-9,"앞쪽 ↓",2.8,PALE))
            elements.append(txt(w-46,h-36,"B · W · P · U",2.75,PALE))
            for j,s in enumerate(c.meta["specimens"]):
                xx=base[j,0]
                yy=h-24+(base[j,1]-109)*.46
                rr=max(1.35,min(2.8,s["height_mm"]/25))
                c0=FAMILY_COLOR[s["family"]]
                elements.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="{rr:.2f}" fill="{c0}" opacity=".78"/>')
        if c.overlay=="rocks":
            # Keep the formation drawing untouched; label group widths in the white band below.
            for j,g in enumerate(c.meta["groups"]):
                xx=g["base_mm"][0]
                yy=h-17+(j%2)*5
                elements.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="2.8" fill="#e8ddc5"/>')
                elements.append(txt(xx-1.9,yy+.9,f"{j+1:02}",2.6,INK))
        elements.append(f'<path d="M {w-19} {h-5} h 10" stroke="{INK}" stroke-width=".42"/>'+
                        txt(w-19,h-1.55,"10 mm",2.55,PALE))
        elements.append('</g></g>')
    return "\n".join(elements+["</svg>"])


def compact(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def turn_degrees(s):
    p=resample(s.xy,.9)
    v=np.diff(p,axis=0)
    u=v/np.maximum(np.linalg.norm(v,axis=1)[:,None],1e-10)
    return np.rad2deg(np.arccos(np.clip(np.einsum("ij,ij->i",u[:-1],u[1:]),-1,1)))


def cross_count(paths):
    lines=[LineString(s.xy) for s in paths]
    if not lines:
        return 0
    pair=STRtree(lines).query(lines,predicate="crosses")
    return int(np.sum(pair[0]<pair[1]))


def metrics(card):
    ink=[s for s in card.paths if s.medium!="COLOR"]
    foliage=[s for s in ink if s.role=="canopy"]
    color=[s for s in card.paths if s.medium=="COLOR"]
    ang=np.concatenate([turn_degrees(s) for s in foliage]) if foliage else []
    base=np.asarray([s["base_xy"] for s in card.meta.get("specimens",[])])
    nearest=[]
    if len(base)>1:
        ds=np.linalg.norm(base[:,None,:]-base[None,:,:],axis=2)
        np.fill_diagonal(ds,np.inf)
        nearest=np.min(ds,axis=0)
    return dict(ink_paths=len(ink),ink_mm=round(sum(s.length for s in ink),3),
                color_paths=len(color),canopy_count=len(foliage),
                median_canopy_mm=round(float(np.median([s.length for s in foliage])),3) if foliage else 0,
                canopy_p95_turn_deg=round(float(np.percentile(ang,95)),3) if len(ang) else 0,
                canopy_pairs_crossing=cross_count(foliage),
                structural_count=sum(s.role in WOODY for s in ink),
                ink_under_5p2mm=sum(s.length<5.2 for s in ink),
                root_x_span_mm=round(float(np.ptp(base[:,0])),2) if len(base) else 0,
                root_y_span_mm=round(float(np.ptp(base[:,1])),2) if len(base) else 0,
                root_nearest_min_mm=round(float(min(nearest)),3) if len(nearest) else None,
                root_nearest_max_mm=round(float(max(nearest)),3) if len(nearest) else None,
                depth_masked_canopy=sum(s.features.get("depth_mask_peak",0)>.01 for s in foliage),
                phases=dict(sorted(Counter(s.phase for s in card.paths).items())))


def build(dst=ROOT,no_png=False):
    for name in ("review","vectors","audit"):
        (dst/name).mkdir(parents=True,exist_ok=True)
    rows=[]
    inventory={}
    for s in assemble():
        p=dst/"review"/(s.id+".svg")
        p.write_text(plate(s),encoding="utf-8")
        if not no_png:
            export_png(p,p.with_suffix(".png"))
        for i,c in enumerate(s.cards,1):
            key=f"{s.id}__{i:02}"
            data=dict(sheet=s.id,example=i,label=c.label,notes=c.subtitle,metadata=c.meta,
                      strokes=[asdict(p) for p in c.paths])
            vector_file=dst/"vectors"/(key+".json.gz")
            vector_file.write_bytes(gzip.compress(compact(data),mtime=0))
            (dst/"vectors"/(key+".svg")).write_text(individual_svg(c.paths,key),encoding="utf-8")
            inventory[key]=hashlib.sha256(vector_file.read_bytes()).hexdigest()
            rows.append(dict(key=key,label=c.label,**metrics(c)))
        print(s.id,len(s.cards),"comparison states",flush=True)
    (dst/"audit"/"metrics.json").write_bytes(compact(rows))
    (dst/"audit"/"vector_hashes.json").write_bytes(compact(inventory))
    with (dst/"audit"/"metrics.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--no-png",action="store_true")
    args=parser.parse_args()
    build(args.output,args.no_png)
