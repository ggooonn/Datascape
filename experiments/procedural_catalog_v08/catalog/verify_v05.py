"""Check deterministic v05 exports, depth, canopy and ground geometry."""
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
from .catalog_v05 import measurements
from .geometry import CFG,ROOT
from .refined_vegetation import WOODY
from .render import individual_svg
from .rock_overlap_v05 import V05, projected_mask
from .sheets_v05 import assemble


def preserved():
    manifest=json.loads((ROOT/"baseline"/"V04_MANIFEST_SHA256.json").read_text())
    files=[k for k in manifest if k=="requirements.txt" or k.startswith(("catalog/","config/","baseline/"))]
    digest=lambda p: sha256(p.read_bytes()).hexdigest()
    assert all(digest(ROOT/k)==manifest[k] for k in files)
    assert digest(ROOT/"baseline"/"V04_CHECKPOINT_KO.md")==manifest["docs/CHECKPOINT_KO.md"]
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v04"
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


def check_groups(sheet):
    separated,fused,group=sheet.cards
    assert not separated.meta["overlapping_pairs"]
    assert fused.meta["contact_links"]==[0,2] and any(s.role=="rock_join_uv" for s in fused.paths)
    assert len(group.meta["overlapping_pairs"])>=3 and len(group.meta["rocks"])==4
    source={r["id"]:r for r in separated.meta["rocks"]}
    for r in group.meta["rocks"]:
        before=source[r["id"]]
        assert (r["shape"],r["width"],r["seed"],r["style"])==(before["shape"],before["width"],before["seed"],before["style"])
        assert np.allclose(np.asarray(r["outline"])-r["base"],np.asarray(before["outline"])-before["base"])
    return check_masks(group)


def check_pair(sheet):
    raw,normal,reverse,crop=sheet.cards
    census={}
    for card in (normal,reverse):
        assert card.meta["overlapping_pairs"] and len(card.meta["rocks"])==2
        assert {(r["id"],tuple(map(tuple,r["outline"]))) for r in raw.meta["rocks"]}=={
            (r["id"],tuple(map(tuple,r["outline"]))) for r in card.meta["rocks"]}
        front=card.meta["order_back_to_front"][-1]
        assert {p.id:p for p in card.paths if p.owner==front}=={p.id:p for p in raw.paths if p.owner==front}
        sources={p.id:p for p in raw.paths}
        for p in card.paths:
            old=sources.get(p.features.get("source",p.id),sources.get(p.id))
            assert old is not None and old.owner==p.owner and old.medium==p.medium and old.phase==p.phase
            if old!=p:
                assert LineString(old.xy).buffer(1e-6).covers(LineString(p.xy)),p.id
        back=card.meta["order_back_to_front"][0]
        rear=[r for r in raw.paths if r.owner==back]
        by_source=[p.id.split("/rock_masked/")[0] for p in card.paths if p.owner==back]
        hidden=check_masks(card)
        assert hidden>10
        census[card.key]=dict(front=front,hidden_mm=hidden,
             hidden_whole=sum(s.id not in by_source for s in rear),
             split_paths=sum(by_source.count(s.id)>1 for s in rear),
             clipped=len([p for p in card.paths if "/rock_masked/" in p.id]))
    assert normal.paths==crop.paths and census[normal.key]["front"]!=census[reverse.key]["front"]
    return census


def check_ground(sheet):
    ledge,ground,root,root_ground=sheet.cards
    body=unary_union([shape(r) for r in ground.meta["rocks"]])
    max_slope=V05["ground"]["max_tangent_deg"]
    totals={}
    for old,new,role in [(ledge,ground,"rock_ground_band"),(root,root_ground,"root_ground_band")]:
        assert old.paths==[s for s in new.paths if s.role!=role]
        added=[s for s in new.paths if s.role==role]
        assert added and all(s.medium=="COLOR" for s in added)
        assert any(abs(s.features["a_slope"])>1e-3 for s in added)
        for s in added:
            f=s.features
            assert f["a_weight"]==.17
            assert abs(f["base_slope"])<=abs(f["a_slope"])*.17+1e-7
            assert LineString(s.xy).intersection(body).length<1e-6 or role=="root_ground_band"
            assert s.length>=V05["ground"]["min_path_mm"]
        deriv=np.vstack([np.diff(s.xy,axis=0) for s in added])
        max_deg=float(np.max(np.abs(np.rad2deg(np.arctan2(deriv[:,1],deriv[:,0])))))
        assert max_deg<=max_slope+1e-6
        totals[role]=dict(paths=len(added),length_mm=round(sum(s.length for s in added),2),
                          max_deg=round(max_deg,2))
    assert len(ledge.meta["rocks"])==6 and len(ledge.meta["overlapping_pairs"])>=6
    totals["ledge_hidden_mm"]=check_masks(ledge)
    return totals


def check_canopy(sheet):
    old,area,preserved,crop=sheet.cards
    assert {p.id:p for p in old.paths if p.role in WOODY}=={p.id:p for p in area.paths if p.role in WOODY}
    assert old.meta["specimens"]==area.meta["specimens"] and len(area.meta["specimens"])==3
    assert not any(p.role=="shared_canopy" for c in (area,preserved) for p in c.paths)
    assert preserved.paths==crop.paths
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v04"/"vectors"/"04_CANOPY__04.json.gz"
    if source.exists():
        with gzip.open(source,"rt") as handle:
            bare=json.load(handle)["strokes"]
        assert [asdict(s) for s in preserved.paths]==bare
    pre=measurements(old,selected(old))["crown"]["ink_in_region_mm"]
    post=measurements(area,selected(area))["crown"]["ink_in_region_mm"]
    assert .92<=post/pre<=1.12
    regional=[p for p in area.paths if p.role=="canopy_area"]
    assert regional and max(p.length for p in regional)<13.1
    return dict(three_stems=len(area.meta["specimens"]),short_area_strokes=len(regional),
                shared_mm_before=pre,shared_mm_after=post,preserved_v04_strokes=len(preserved.paths),
                v04_vector_snapshot_checked=source.exists())


def verify():
    originals=preserved()
    sheets=assemble()
    cards,paths=check_exports(sheets)
    assert not any(p.suffix.lower() in {".nc",".tap",".ngc",".gcode"} for p in ROOT.rglob("*"))
    data=dict(sheets=len(sheets),cards=cards,path_records=paths,source_v04_files_checked=originals,
              group_hidden_mm=check_groups(sheets[0]),pair=check_pair(sheets[1]),
              ground=check_ground(sheets[2]),canopy=check_canopy(sheets[3]))
    (ROOT/"audit"/"verification.json").write_bytes(compact(data))
    print(json.dumps(data,ensure_ascii=False))


if __name__=="__main__":
    verify()
