"""Verify frozen v06 artwork and local placement, masking and merging in v07."""
from dataclasses import asdict
import gzip
from hashlib import sha256
import json

import numpy as np
from PIL import Image
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union

from .catalog_v02 import compact
from .catalog_v03 import selected
from .catalog_v07 import measurements,plate
from .geometry import CFG,ROOT
from .render import individual_svg
from .ground_attachment_v07 import G,TerrainFrame
from .sheets_v07 import GROUND_ROLES,SITE_BOX,assemble
from .terrain_v03 import terrain_fixture


def preserved():
    manifest=json.loads((ROOT/"baseline"/"V06_MANIFEST_SHA256.json").read_text())
    files=[k for k in manifest if k=="requirements.txt" or k.startswith(("catalog/","config/","baseline/"))]
    digest=lambda p: sha256(p.read_bytes()).hexdigest()
    assert all(digest(ROOT/k)==manifest[k] for k in files)
    assert digest(ROOT/"baseline"/"V06_CHECKPOINT_KO.md")==manifest["docs/CHECKPOINT_KO.md"]
    for example in ("04_ROOT_GROUND__03","02_MASSING__04"):
        file=f"{example}.json.gz"
        assert digest(ROOT/"baseline"/"v06_layouts"/file)==manifest[f"vectors/{file}"]
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v06"
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


def v06_snapshot(example):
    file=ROOT/"baseline"/"v06_layouts"/f"{example}.json.gz"
    return json.loads(gzip.decompress(file.read_bytes()))["strokes"]


def bands(paths):
    return [p for p in paths if p.role in GROUND_ROLES]


def check_site(old,new):
    older=v06_snapshot("04_ROOT_GROUND__03")
    assert [asdict(p) for p in old.paths]==older
    fixed=lambda paths:[p for p in paths if p.role not in GROUND_ROLES]
    assert fixed(old.paths)==fixed(new.paths)
    assert all(p.phase=="COLOR" for p in bands(new.paths))
    return len(fixed(new.paths))


def check_patch_geometry(card,frame):
    model=card.meta["ground"]
    contacts={q["key"]:q for q in model["contacts"]}
    bodies={r["id"]:Polygon(r["outline"]) for r in card.meta["rocks"]}
    solid=unary_union(list(bodies.values()))
    marks=bands(card.paths)
    assert marks
    for c in contacts.values():
        x,y=c["xy"]
        east,depth,z=c["xyz"]
        assert np.allclose((x,y),frame.project_xy(east,depth)) and np.isclose(z,depth-y)
        if c["kind"]=="rock":
            assert bodies[c["owner"]].boundary.distance(Point(x,y))<1e-6
    slopes=[]
    for s in marks:
        assert s.pigment in G["colors"]["root" if s.role=="root_ground_band" else "rock"]
        assert all(contacts[a]["visible"] for a in s.features["anchors"])
        assert LineString(s.xy).intersection(solid).length<1e-6
        assert G["min_path_mm"]-1e-8<=s.length<=30.1
        deriv=np.diff(s.xy,axis=0)
        assert (deriv[:,0]>0).all()
        slopes.extend(np.abs(np.rad2deg(np.arctan2(deriv[:,1],deriv[:,0]))))
    assert max(slopes)<=G["max_tangent_deg"]+1e-6
    for q in contacts.values():
        if q["kind"]=="root" and q["visible"]:
            match=[p for p in marks if q["key"] in p.features["anchors"]]
            assert match and min(LineString(p.xy).distance(Point(q["xy"])) for p in match)<=1.7
    return dict(strokes=len(marks),length_mm=round(sum(s.length for s in marks),2),
                maximum_slope_deg=round(float(max(slopes)),2),
                painted_rock_objects=len({o for p in marks if p.role=="rock_ground_band" for o in p.features["owners"]}),
                roots=len({o for p in marks if p.role=="root_ground_band" for o in p.features["owners"]}),
                hidden_contacts=model["not_painted_contacts"],candidate_bands_rejected=model["rejected_hidden_bands"],
                merged_passes=model["joined"],clip_removed_mm=model["clip_length_mm"])


def check_details(sheet):
    first,after,before,masked=sheet.cards
    unjoined={p.id:p for p in bands(first.paths)}
    joined=[p for p in bands(after.paths) if p.features.get("merged_from")]
    assert joined and all(len(p.features["owners"])>1 for p in joined)
    for p in joined:
        source=[unjoined[k] for k in p.features["merged_from"]]
        assert len({q.pigment for q in source})==1
        assert p.length<sum(q.length for q in source)
    body=unary_union([Polygon(r["outline"]) for r in masked.meta["rocks"]])
    assert max(LineString(p.xy).intersection(body).length for p in bands(before.paths))>10
    assert max(LineString(p.xy).intersection(body).length for p in bands(masked.paths))<1e-6


def verify():
    prior=preserved()
    sheets=assemble()
    cards,total=check_exports(sheets)
    a,b=sheets[0].cards
    count=check_site(a,b)
    baseline=bands(a.paths)
    frame=TerrainFrame.from_lines(terrain_fixture("site/ground",SITE_BOX,376),SITE_BOX)
    site=check_patch_geometry(b,frame)
    rock,rock_new=sheets[2].cards
    canonical=v06_snapshot("02_MASSING__04")
    assert [asdict(p) for p in rock.paths]==canonical
    assert rock.paths==[p for p in rock_new.paths if p.role not in GROUND_ROLES]
    formation=check_patch_geometry(rock_new,frame)
    check_details(sheets[3])
    assert not any(p.suffix.lower() in {".nc",".tap",".ngc",".gcode"} for p in ROOT.rglob("*"))
    data=dict(sheets=len(sheets),cards=cards,stroke_records=total,source_v06_files_checked=prior,
              unchanged_site_strokes=count,site=site,formation=formation,
              baseline_ground=dict(strokes=len(baseline),length_mm=round(sum(p.length for p in baseline),2)))
    (ROOT/"audit"/"verification.json").write_bytes(compact(data))
    print(json.dumps(data,ensure_ascii=False))


if __name__=="__main__":
    verify()
