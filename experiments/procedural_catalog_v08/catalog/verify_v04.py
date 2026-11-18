"""Check vector reproducibility, lithic continuity, contact patches and crown invariants."""
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
from .catalog_v04 import measurements
from .geometry import CFG,ROOT
from .occlusion_v04 import hide_behind_rock
from .refined_vegetation import WOODY
from .render import individual_svg
from .rock_mass_v04 import component_count, V04
from .sheets_v04 import assemble


def preserved():
    manifest=json.loads((ROOT/"baseline"/"V03_MANIFEST_SHA256.json").read_text())
    files=[k for k in manifest if k=="requirements.txt" or k.startswith(("catalog/","config/","baseline/"))]
    digest=lambda p: sha256(p.read_bytes()).hexdigest()
    assert all(digest(ROOT/k)==manifest[k] for k in files)
    assert digest(ROOT/"baseline"/"V03_CHECKPOINT_KO.md")==manifest["docs/CHECKPOINT_KO.md"]
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v03"
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


def mass_body(metadata):
    return unary_union([Polygon(m["outline"]) for m in metadata["rocks"]]
              +[Polygon(c["polygon"]) for c in metadata["contacts"]])


def check_rocks(rocks):
    results=[]
    assert [c.meta["components"] for c in rocks.cards]==[4,2,1]
    for c in rocks.cards:
        assert c.meta["rocks"]==rocks.cards[0].meta["rocks"]
        body=mass_body(c.meta)
        assert body.is_valid and component_count(body)==c.meta["components"]
        for contact in c.meta["contacts"]:
            a,b=contact["pair"]
            left,right=(Polygon(c.meta["rocks"][i]["outline"]) for i in (a,b))
            printline=[LineString(s.xy) for s in c.paths if s.role=="rock_join_uv" and s.features["neighbors"]==[a,b]]
            assert any(l.intersection(left).length>1 and l.intersection(right).length>1 for l in printline)
            assert all(p>0 for p in contact["entry_overlap_mm2"])
            assert all(body.buffer(1e-6).covers(line) for line in printline)
        results.append(c.meta["components"])
    return results


def check_ground(s):
    a,b,c,d=s.cards
    plain=[x for x in a.paths if x.role!="rock_ground_color"]
    assert plain==[x for x in b.paths if x.role!="rock_ground_patch"]
    assert c.paths==[x for x in d.paths if x.role!="vegetation_ground_patch"]
    solid=mass_body(b.meta)
    lengths={}
    for sample,role in [(a,"rock_ground_color"),(b,"rock_ground_patch"),(d,"vegetation_ground_patch")]:
        ground=[x for x in sample.paths if x.role==role]
        assert ground and all(x.medium=="COLOR" for x in ground)
        if sample is b:
            assert all(LineString(x.xy).intersection(solid).length<1e-5 for x in ground)
        if sample is not a:
            assert {x.features["layer"] for x in ground}=={0,1}
        lengths[role]=round(sum(x.length for x in ground),2)
    assert lengths["rock_ground_patch"]>=2*lengths["rock_ground_color"]
    return lengths


def check_depth(s):
    before,after=s.cards
    solid=mass_body(after.meta)
    cand=[x for x in after.paths if x.id.startswith("occlusion/trees/")]
    ini=[x for x in before.paths if x.id.startswith("occlusion/trees/")]
    assert [x for x in before.paths if x not in ini]==[x for x in after.paths if x not in cand]
    assert {x.medium for x in cand}=={"LIGHT_INK","MEDIUM_INK","COLOR"}
    assert all(LineString(x.xy).intersection(solid).length<1e-5 for x in cand)
    assert any(LineString(x.xy).intersection(solid).length>4 for x in ini)
    assert set(after.meta["occlusion"]["placement"].values())=={"beside","behind"}
    # Geometry with a root at the front of a rock fails placement explicitly.
    x,_,_,y=solid.bounds
    near=after.meta["rocks"][0]["base"][0]
    try:
        hide_behind_rock([], [{"id":"front_test","base_xy":[near,y+10]}],solid)
    except ValueError:
        pass
    else:
        raise AssertionError("Ambiguous foreground allowed")
    return after.meta["occlusion"]


def check_canopy(s):
    comparisons=[]
    for before,after in zip(s.cards[::2],s.cards[1::2]):
        assert {x.id:x for x in before.paths if x.role in WOODY}=={x.id:x for x in after.paths if x.role in WOODY}
        assert before.meta["specimens"]==after.meta["specimens"]
        candidates=[x for x in after.paths if x.role=="canopy_area"]
        regions=[Polygon(r["outer"],r["holes"]) for r in after.meta["regions"]]
        assert candidates and not any(x.role=="shared_canopy" for x in after.paths)
        before_mm=measurements(before,before.paths)["crown"]["ink_in_region_mm"]
        after_mm=measurements(after,after.paths)["crown"]["ink_in_region_mm"]
        assert .89<=after_mm/before_mm<=1.14
        assert all(regions[x.features["region"]].buffer(1e-6).covers(LineString(x.xy)) for x in candidates)
        maximum=max(x.length for x in candidates)
        assert maximum<=max(t[1] for t in V04["canopy_area"]["ink_length_mm"].values())+.6
        comparisons.append(dict(key=after.key,leaf_count=len(candidates),max_leaf_mm=round(maximum,2),
                        total_in_area_before_mm=before_mm,total_in_area_after_mm=after_mm,
                        ink_paths_before=len(before.paths),ink_paths_after=len(after.paths)))
    return comparisons


def verify():
    source_files=preserved()
    sheets=assemble()
    cards,paths=check_exports(sheets)
    assert not any(p.suffix.lower() in {".nc",".tap",".ngc",".gcode"} for p in ROOT.rglob("*"))
    result=dict(sheets=len(sheets),cards=cards,path_records=paths,source_v03_unchanged_files=source_files,
                rock_components=check_rocks(sheets[0]),ground=check_ground(sheets[1]),
                occlusion=check_depth(sheets[2]),canopy=check_canopy(sheets[3]))
    (ROOT/"audit"/"verification.json").write_bytes(compact(result))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    verify()
