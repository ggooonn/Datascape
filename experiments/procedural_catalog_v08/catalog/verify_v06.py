"""Check deterministic v06 exports, related rock families, depth and root-zone controls."""
from dataclasses import asdict
import gzip
from hashlib import sha256
import json

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .catalog_v02 import compact
from .catalog_v03 import plate,selected
from .catalog_v06 import measurements
from .geometry import CFG,ROOT
from .refined_vegetation import WOODY
from .render import individual_svg
from .rock_overlap_v05 import V05, projected_mask
from .rock_families_v06 import FAMILIES, V06
from .sheets_v06 import assemble


def preserved():
    manifest=json.loads((ROOT/"baseline"/"V05_MANIFEST_SHA256.json").read_text())
    files=[k for k in manifest if k=="requirements.txt" or k.startswith(("catalog/","config/","baseline/"))]
    digest=lambda p: sha256(p.read_bytes()).hexdigest()
    assert all(digest(ROOT/k)==manifest[k] for k in files)
    assert digest(ROOT/"baseline"/"V05_CHECKPOINT_KO.md")==manifest["docs/CHECKPOINT_KO.md"]
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v05"
    if source.is_dir():
        assert all(digest(source/k)==d for k,d in manifest.items())
    return len(manifest) if source.is_dir() else None


def check_exports(sheets):
    data=json.loads((ROOT/"audit"/"metrics.json").read_text())
    hashes=json.loads((ROOT/"audit"/"vector_hashes.json").read_text())
    row=0
    total=0
    for sheet in sheets:
        assert (ROOT/"review"/f"{sheet.key}.svg").read_text()==plate(sheet)
        preview=ROOT/"review"/f"{sheet.key}.png"
        if preview.exists():
            with Image.open(preview) as im:
                assert im.width==1600
                im.verify()
        for i,c in enumerate(sheet.cards,1):
            key=f"{sheet.key}__{i:02}"
            paths=selected(c)
            raw=compact(dict(key=c.key,title=c.title,mode=c.mode,detail_crop_mm=c.crop,
                             metadata=c.meta,strokes=[asdict(p) for p in paths]))
            assert gzip.decompress((ROOT/"vectors"/f"{key}.json.gz").read_bytes())==raw,key
            assert sha256(raw).hexdigest()==hashes[key],key
            assert (ROOT/"vectors"/f"{key}.svg").read_text()==individual_svg(paths,key),key
            assert len({s.id for s in paths})==len(paths),key
            assert data[row]==dict(id=key,key=c.key,**measurements(c,paths)),key
            for s in paths:
                coords=np.asarray(s.xy)
                pressure=np.asarray(s.pressure_mm)
                assert len(coords)==len(pressure)>1
                assert np.isfinite(coords).all() and np.isfinite(pressure).all()
                assert (np.linalg.norm(np.diff(coords,axis=0),axis=1)>1e-7).all(),s.id
                if c.crop is None:
                    assert (coords.min(axis=0)>=0).all() and (coords.max(axis=0)<=np.array(sheet.cell)-[3,1.5]).all(),(key,s.id)
                cap={"LIGHT_INK":"light_mm","MEDIUM_INK":"medium_mm","COLOR":"color_mm"}[s.medium]
                assert pressure.min()>0 and pressure.max()<=CFG["plot_intent"][cap][1]
                allowed={"LIGHT_INK":{"INK_1","INK_2"},"MEDIUM_INK":{"INK_3","INK_4"},"COLOR":{"COLOR"}}
                assert s.phase in allowed[s.medium]
                assert (s.medium=="COLOR")==bool(s.pigment)
                total+=1
            row+=1
    assert row==len(hashes)==len(data)
    return row,total


def shape(rock):
    return Polygon(rock["outline"])


def check_masks(card):
    records=card.meta["rocks"]
    assert [i["id"] for i in records]==card.meta["order_back_to_front"]
    assert len({r["depth"] for r in records})==len(records)
    masks={r["id"]:projected_mask(records,r["depth"]) for r in records}
    outlines={r["id"]:shape(r) for r in records}
    for p in card.paths:
        if p.owner not in masks:
            continue
        line=LineString(p.xy)
        assert line.intersection(masks[p.owner]).length<1e-5,(card.key,p.id)
        assert outlines[p.owner].buffer(1e-6).covers(line),p.id
        assert not p.role.startswith(("rock_join","connected_"))
    return round(sum(r["hidden_line_mm"] for r in card.meta["mask_audit"].values()),2)


def covered(meta):
    values=list(meta["mask_audit"].values())
    total=sum(q["outline_covered_mm2"] for q in values)
    surfaces=sum(q["outline_covered_mm2"]+q["visible_area_mm2"] for q in values)
    return dict(pairs=len(meta["overlapping_pairs"]),mean_percent=round(total/surfaces*100,2),
                max_percent=round(max(q["outline_covered_mm2"]/(q["outline_covered_mm2"]+q["visible_area_mm2"])
                for q in values)*100,2))


def check_family(s):
    result={}
    control=s.cards[0].meta["rocks"]
    assert len(s.cards)==len(FAMILIES)
    for card in s.cards:
        family=card.meta["family"]
        cfg=FAMILIES[family]
        rocks=card.meta["rocks"]
        assert [(r["base"],r["depth"],r["width"]) for r in rocks]==[(r["base"],r["depth"],r["width"]) for r in control]
        assert {r["family"] for r in rocks}=={family} and {r["style"] for r in rocks}=={cfg["style"]}
        assert {r["shape"] for r in rocks}==set(cfg["profiles"])
        front=[round(float(np.rad2deg(np.arctan2(f["u_axis"][1],f["u_axis"][0]))),4) for r in rocks
               for f in r["frames"] if f["role"]=="front"]
        assert len(front)==len(rocks) and max(abs(x-cfg["front_deg"]) for x in front)<7
        if family=="jointed":
            joints=[q for q in card.paths if q.role=="rock_fracture"]
            assert joints and {p.features["shared_lean"] for p in joints}=={cfg["joint_lean"]}
        asym=[tuple(map(tuple,np.round((np.asarray(r["outline"])-r["base"])/r["width"],5))) for r in rocks]
        assert len(set(asym))==len(rocks)
        check_masks(card)
        result[family]=dict(front_min=round(min(front),2),front_max=round(max(front),2))
    return result


def check_mass(s):
    result={}
    assert [len(c.meta["rocks"]) for c in s.cards]==[5,6,6,11]
    for card in s.cards:
        rocks=card.meta["rocks"]
        widths=[r["width"] for r in rocks]
        assert all(r["family"]=="strata" for r in rocks)
        check_masks(card)
        result[card.meta["arrangement"]]=dict(n=len(widths),width_min=min(widths),width_max=max(widths),**covered(card.meta))
    assert result["anchor"]["width_max"]/result["anchor"]["width_min"]>4
    assert result["medium"]["width_max"]/result["medium"]["width_min"]<1.5
    assert result["formation"]["pairs"]>=12 and result["formation"]["max_percent"]>75
    return result


def check_depth(s):
    loose,strong,raw,crop=s.cards
    assert strong.paths==crop.paths
    assert [r["id"] for r in loose.meta["rocks"]]==[r["id"] for r in strong.meta["rocks"]]
    for a,b in zip(loose.meta["rocks"],strong.meta["rocks"]):
        assert [a[k] for k in ("shape","depth","width","seed")]==[b[k] for k in ("shape","depth","width","seed")]
        assert np.allclose(np.asarray(a["outline"])-a["base"],np.asarray(b["outline"])-b["base"])
    stats={}
    staged={p.id:p for p in raw.paths}
    for p in strong.paths:
        original=staged[p.features.get("source",p.id)]
        assert p.owner==original.owner and p.medium==original.medium
        assert LineString(original.xy).buffer(1e-6).covers(LineString(p.xy))
    front=strong.meta["order_back_to_front"][-1]
    assert [p for p in strong.paths if p.owner==front]==[p for p in raw.paths if p.owner==front]
    for card in (loose,strong):
        stats[card.key]=dict(hidden_mm=check_masks(card),**covered(card.meta))
    assert stats["strong"]["max_percent"]>30 and stats["strong"]["pairs"]>stats["loose"]["pairs"]
    return stats


def check_root(s):
    a,b,c,d=s.cards
    assert c.paths==d.paths
    role={"root_ground_band","rock_ground_band"}
    nonband=lambda card:[p for p in card.paths if p.role not in role]
    assert nonband(a)==nonband(b)
    body=unary_union([shape(r) for r in c.meta["rocks"]])
    base=[p for p in a.paths if p.role in role]
    wide=[p for p in b.paths if p.role in role]
    assert len(base)==len(wide)
    assert [(p.id,p.phase,p.pigment,p.features["base_slope"],p.features["anchor"]) for p in base]==[
             (p.id,p.phase,p.pigment,p.features["base_slope"],p.features["anchor"]) for p in wide]
    ratio=sum(p.length for p in wide)/sum(p.length for p in base)
    assert 1.12<ratio<1.20
    assert all(LineString(p.xy).intersection(body).length<1e-5 for p in wide)
    derive=np.vstack([np.diff(p.xy,axis=0) for p in wide])
    max_deg=float(np.max(np.abs(np.rad2deg(np.arctan2(derive[:,1],derive[:,0])))))
    assert max_deg<=V05["ground"]["max_tangent_deg"]
    without=lambda card:[p for p in card.paths if p.role!="canopy"]
    assert without(b)==without(c)
    removed={p.id for p in b.paths}-{p.id for p in c.paths}
    assert len(removed)==c.meta["removed_individual"]>0
    assert all(p.role=="canopy" and p.length<=V06["root_canopy"]["max_individual_mm"]
               for p in b.paths if p.id in removed)
    vegetation=[p for p in c.paths if p.id.startswith("root_zone/")]
    assert all(LineString(p.xy).intersection(body).length<1e-5 for p in vegetation)
    assert any(p.role in WOODY for p in vegetation) and all(p.role!="shared_canopy" for p in vegetation)
    preserved_area=sum(p.role=="canopy_area" for p in vegetation)
    assert preserved_area==c.meta["shared_visible"] and preserved_area>0
    check_masks(c)
    return dict(bands=len(wide),base_mm=round(sum(p.length for p in base),2),v06_mm=round(sum(p.length for p in wide),2),
                length_increase_percent=round((ratio-1)*100,1),max_degrees=round(max_deg,2),
                shared_area_strokes=preserved_area,
                short_owned_removed=len(removed),short_owned_before=sum(p.role=="canopy" for p in b.paths),
                short_owned_after=sum(p.role=="canopy" for p in c.paths),
                visible_woody_strokes=sum(p.role in WOODY for p in vegetation))


def verify():
    prior=preserved()
    items=assemble()
    cards,n=check_exports(items)
    assert not any(p.suffix.lower() in {".nc",".tap",".ngc",".gcode"} for p in ROOT.rglob("*"))
    numbers=dict(sheets=len(items),cards=cards,stroke_records=n,source_v05_files_checked=prior,
                 families=check_family(items[0]),masses=check_mass(items[1]),overlap=check_depth(items[2]),
                 root_ground=check_root(items[3]))
    (ROOT/"audit"/"verification.json").write_bytes(compact(numbers))
    print(json.dumps(numbers,ensure_ascii=False))


if __name__=="__main__":
    verify()
