"""Check catalog geometry and exported vectors without interacting with a plotter."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import gzip
import hashlib
import json

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Polygon

from .catalog_v02 import compact, individual_svg, metrics, plate
from .geometry import CFG, ROOT
from .refined_vegetation import REF, WOODY, specimen
from .rock_v02 import rock
from .sheets_v02 import assemble


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_by_role(card, roles):
    return {s.id: (s.xy, s.pressure_mm, s.phase, s.owner) for s in card.paths if s.role in roles}


def verify(root=ROOT):
    manifest=json.loads((root/"baseline/V01_MANIFEST_SHA256.json").read_text())
    retained=[f"catalog/{name}.py" for name in ("__init__","geometry","vegetation","context","ground","render")]
    retained += ["config/catalog.json","requirements.txt"]
    assert all(digest(root/name)==manifest[name] for name in retained)
    assert digest(root/"baseline/V01_CHECKPOINT_KO.md")==manifest["CHECKPOINT_KO.md"]
    references=("FROZEN_WASH_PROFILE.json","checkpoint_v02_cleaning.json","execution_settings.json")
    assert all(digest(root/"baseline"/name)==manifest[f"baseline/spring_context/{name}"] for name in references)

    preserved_v01=root.parent/"Datascape_Procedural_Catalog_v01"
    if preserved_v01.is_dir():
        assert all(digest(preserved_v01/name)==sha for name,sha in manifest.items())

    sheets={s.id:s for s in assemble()}
    inventory=json.loads((root/"audit/vector_hashes.json").read_text())
    exported_metrics=json.loads((root/"audit/metrics.json").read_text())
    measured=[]
    strokes=0
    for name,s in sheets.items():
        assert (root/"review"/f"{name}.svg").read_text()==plate(s),name
        preview=root/"review"/f"{name}.png"
        if preview.exists():
            with Image.open(preview) as im:
                assert im.width==1600
                im.verify()
        for i,card in enumerate(s.cards,1):
            key=f"{name}__{i:02}"
            json_path=root/"vectors"/f"{key}.json.gz"
            assert digest(json_path)==inventory[key]
            expected=dict(sheet=name,example=i,label=card.label,notes=card.subtitle,metadata=card.meta,
                          strokes=[asdict(p) for p in card.paths])
            assert gzip.decompress(json_path.read_bytes())==compact(expected),key
            svg_path=root/"vectors"/f"{key}.svg"
            assert svg_path.read_text()==individual_svg(card.paths,key),key
            measured.append(dict(key=key,label=card.label,**metrics(card)))
            ids=set()
            for p in expected["strokes"]:
                xy=np.asarray(p["xy"])
                pressure=np.asarray(p["pressure_mm"])
                assert p["id"] not in ids,(key,p["id"])
                ids.add(p["id"])
                assert len(xy)==len(pressure) and len(xy)>1
                assert np.isfinite(xy).all() and np.isfinite(pressure).all()
                assert (np.linalg.norm(np.diff(xy,axis=0),axis=1)>1e-6).all()
                assert (xy.min(axis=0)>=0).all() and (xy.max(axis=0)<=np.array(s.cell)-[3,2]).all(),key
                prefix={"LIGHT_INK":{"INK_1","INK_2"},"MEDIUM_INK":{"INK_3","INK_4"},"COLOR":{"COLOR"}}
                assert p["phase"] in prefix[p["medium"]],(key,p["id"])
                cap={"LIGHT_INK":"light_mm","MEDIUM_INK":"medium_mm","COLOR":"color_mm"}[p["medium"]]
                assert pressure.min()>0 and pressure.max()<=CFG["plot_intent"][cap][1]
                strokes+=1
    assert measured==exported_metrics and len(inventory)==len(measured)
    assert not any(p.suffix.lower() in {".gcode",".ngc",".nc",".tap"} for p in root.rglob("*"))

    bw=sheets["01_BW"].cards
    mix=sheets["03_BW_MIX"].cards
    for before,after in [*zip(bw[::2],bw[1::2]),tuple(mix)]:
        assert rows_by_role(before,WOODY)==rows_by_role(after,WOODY)
        a,b=metrics(before),metrics(after)
        assert a["canopy_count"]>b["canopy_count"] and a["median_canopy_mm"]<b["median_canopy_mm"]
        assert a["canopy_p95_turn_deg"]>b["canopy_p95_turn_deg"]
        assert a["canopy_pairs_crossing"]>b["canopy_pairs_crossing"]
    for family in ("P","U"):
        assert specimen("retained",family,47,(50,60),seed=22)==specimen(
            "retained",family,47,(50,60),seed=22,variant="v01")

    row,*clusters=sheets["04_CLUSTERS"].cards
    for card in clusters:
        m=metrics(card)
        assert m["root_y_span_mm"]>4*metrics(row)["root_y_span_mm"]
        assert m["root_nearest_min_mm"]>=REF["placement"][card.meta["layout"]]["min_spacing_mm"]
    depth=clusters[-1]
    assert {s["lod"] for s in depth.meta["specimens"]}=={"near","mid","far"}
    assert metrics(depth)["depth_masked_canopy"]>0

    forms=sheets["05_ROCK_FORMS"].cards
    assert len({c.meta["morphology"] for c in forms})==len(forms)==8
    for c in forms:
        m=c.meta
        a,shape,_=rock(m["id"],m["morphology"],m["base_mm"],m["width_mm"],m["seed"],texture="weathered")
        assert shape.equals(Polygon(m["silhouette"])) and shape.is_valid
        originals=[p for p in c.paths if p.role=="silhouette"]
        assert [p.xy for p in a if p.role=="silhouette"]==[p.xy for p in originals]
        for p in c.paths:
            if p.role in {"bedding","cross_joint","erosion","mineral_color"}:
                assert shape.buffer(1e-6).covers(LineString(p.xy)),p.id
    formation=sheets["07_ROCK_FORMATION"].cards[0].meta
    groups=formation["groups"]
    assert formation["group_count"]==len(groups)==10
    assert len({tuple(g["base_mm"]) for g in groups})==10
    components=[c for g in groups for c in g["components"]]
    ratios=[c["width_mm"]/g["width_mm"] for g in groups for c in g["components"][1:]]
    assert max(ratios)<=.44 and min(ratios)>=.14
    assert len({tuple(map(tuple,c["silhouette"])) for c in components})==len(components)
    rock_lod=[len(c.paths) for c in sheets["11_ROCK_LOD"].cards]
    assert rock_lod[0]>rock_lod[1]>rock_lod[2]

    raw,old,new,diagram=sheets["08_MASK"].cards
    assert [s for s in raw.paths if s.role!="terrain_A"]==[s for s in new.paths if s.role!="terrain_A"]
    assert diagram.paths==[s for s in new.paths if s.role=="terrain_A"]
    terrain_audits=[]
    for card in [new,*sheets["09_SAME_SITE"].cards,*sheets["10_COMMUNITIES"].cards]:
        a=card.meta["terrain"]
        terrain=[(s,LineString(s.xy)) for s in card.paths if s.role=="terrain_A"]
        assert all(ls.length>=REF["core"]["min_segment_mm"]-1e-6 for _,ls in terrain)
        for r in a["cores"]:
            area=Polygon(r["polygon"],r["holes"])
            found=[s for s,ls in terrain if ls.intersection(area).length>1e-5]
            assert len(found)<=1 and all(s.medium=="LIGHT_INK" for s in found)
            assert [s.id for s in found]==r["kept"]
        terrain_audits.append([sum(len(r["kept"]) for r in a["cores"]),a["core_count"]])
    assert terrain_audits[0][0]>0

    same=sheets["09_SAME_SITE"].cards
    communities=sheets["10_COMMUNITIES"].cards
    wood=rows_by_role(same[0],WOODY)
    same_poses=lambda c: [(s["id"],s["base_xy"],s["height_mm"],s["family"],s["lod"]) for s in c.meta["specimens"]]
    assert len(same_poses(same[0]))==11
    assert all(rows_by_role(c,WOODY)==wood and same_poses(c)==same_poses(same[0]) for c in same)
    assert [len(c.meta["specimens"]) for c in communities]==[10,15,9,7]
    assert len({tuple(tuple(s["base_xy"]) for s in c.meta["specimens"]) for c in communities})==4
    winter_counts=Counter(p.role for p in same[-1].paths)
    assert winter_counts["winter_twig"]>0 and winter_counts["canopy"]<=4

    result=dict(sheet_count=len(sheets),states=len(measured),strokes=strokes,
                v01_original_files_checked=len(manifest) if preserved_v01.is_dir() else None,
                retained_reference_count=len(retained)+len(references)+1,
                formation_rock_count=len(components),support_width_ratio=[min(ratios),max(ratios)],
                rock_lod_path_count=rock_lod,mask_kept_and_core_counts=terrain_audits,
                same_site_woody_paths=len(wood),winter_twig_count=winter_counts["winter_twig"])
    (root/"audit"/"verification.json").write_bytes(compact(result))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    verify()
