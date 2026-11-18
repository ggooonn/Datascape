"""Export reproducible v08 review plates and mm vector records."""
import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import gzip
from html import escape

import numpy as np

from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union

from .audit_v03 import path_audit
from .catalog_v02 import compact
from .catalog_v03 import plate as base_plate, selected
from .geometry import ROOT
from .render import export_png, individual_svg, path_tag
from .sheets_v08 import assemble


plate=base_plate


def aligned_svgs(folder,key,paths):
    xy=np.vstack([p.xy for p in paths])
    lo=xy.min(axis=0)-2.5
    width,height=xy.max(axis=0)+2.5-lo
    view=" ".join(f"{v:.5f}" for v in (*lo,width,height))
    head=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.5f}mm" height="{height:.5f}mm" viewBox="{view}">'
    for name,selected_paths in (
        ("INK",[p for p in paths if p.medium!="COLOR"]),
        ("COLOR",[p for p in paths if p.medium=="COLOR"]),
        ("COMBINED",sorted(paths,key=lambda p:p.medium!="COLOR")),
    ):
        svg="\n".join([head,f"<title>{escape(key)} {name}</title>",*(path_tag(p) for p in selected_paths),"</svg>"])
        (folder/f"{key}_{name}.svg").write_text(svg,encoding="utf-8")


def measurements(card,paths):
    census=Counter(p.role for p in paths)
    row=dict(path_audit(paths), by_role=dict(census),role_mm={
        role:round(sum(p.length for p in paths if p.role==role),2) for role in sorted(census)
    })
    crown=card.meta.get("regions")
    if crown:
        shape=unary_union([Polygon(r["outer"],r["holes"]) for r in crown])
        inside=sum(LineString(s.xy).intersection(shape).length
                   for s in paths if s.role in {"canopy","shared_canopy","canopy_area"})
        row["crown"]={"count":len(crown),"area_mm2":round(shape.area,2),
                      "ink_in_region_mm":round(inside,2),"ink_mm_per_mm2":round(inside/shape.area,4)}
    if "components" in card.meta:
        row["rock_components"]=card.meta["components"]
    return row


def generate(dst=ROOT,no_png=False):
    for name in ("review","vectors","audit","compositions"):
        (dst/name).mkdir(parents=True,exist_ok=True)
    hashes={}
    audit=[]
    for sheet in assemble():
        image=dst/"review"/f"{sheet.key}.svg"
        image.write_text(plate(sheet),encoding="utf-8")
        if not no_png:
            export_png(image,image.with_suffix(".png"))
        for i,card in enumerate(sheet.cards,1):
            paths=selected(card)
            name=f"{sheet.key}__{i:02}"
            data=dict(key=card.key,title=card.title,mode=card.mode,detail_crop_mm=card.crop,
                      metadata=card.meta,strokes=[asdict(p) for p in paths])
            encoded=compact(data)
            (dst/"vectors"/f"{name}.json.gz").write_bytes(gzip.compress(encoded,mtime=0))
            (dst/"vectors"/f"{name}.svg").write_text(individual_svg(paths,name),encoding="utf-8")
            hashes[name]=sha256(encoded).hexdigest()
            if sheet.key.startswith(("02_", "03_")):
                aligned_svgs(dst/"compositions",card.key,paths)
            audit.append(dict(id=name,key=card.key,**measurements(card,paths)))
        print(sheet.key,len(sheet.cards),"states",flush=True)
    (dst/"audit"/"metrics.json").write_bytes(compact(audit))
    (dst/"audit"/"vector_hashes.json").write_bytes(compact(hashes))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--no-png",action="store_true")
    args=parser.parse_args()
    generate(args.output,args.no_png)
