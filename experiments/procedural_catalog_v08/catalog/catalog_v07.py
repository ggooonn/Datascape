"""Export reproducible v07 review plates and mm vector records."""
import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import gzip
from xml.etree import ElementTree as ET

from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union

from .audit_v03 import path_audit
from .catalog_v02 import compact
from .catalog_v03 import plate as base_plate, selected
from .geometry import ROOT
from .render import export_png, individual_svg
from .sheets_v07 import assemble


SVG="http://www.w3.org/2000/svg"
ET.register_namespace("",SVG)


def plate(sheet):
    svg=base_plate(sheet)
    if not any(c.meta.get("preview_contacts") for c in sheet.cards):
        return svg
    root=ET.fromstring(svg)
    name=lambda t:f"{{{SVG}}}{t}"
    for group,card in zip(root.findall(name("g")),sheet.cards):
        contacts=card.meta.get("preview_contacts",[])
        if not contacts:
            continue
        layer=group.findall(name("g"))[-1]
        if card.crop:
            layer=layer.find(name("g"))
        marks=ET.SubElement(layer,name("g"),{"id":f"contacts_{card.key}","fill":"none","stroke-width":".32"})
        for contact in contacts:
            x,y=contact["xy"]
            if contact["visible"]:
                ET.SubElement(marks,name("circle"),{"cx":f"{x:.3f}","cy":f"{y:.3f}","r":".86",
                               "stroke":"#577872","fill":"#fbf8ee"})
            else:
                ET.SubElement(marks,name("path"),{"d":f"M{x-.67:.3f},{y-.67:.3f}l1.34,1.34 M{x-.67:.3f},{y+.67:.3f}l1.34,-1.34",
                               "stroke":"#9e5547"})
    return ET.tostring(root,encoding="unicode")


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
    for name in ("review","vectors","audit"):
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
