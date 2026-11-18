"""Verify baseline identity, deterministic exports, and geometry invariants."""
from dataclasses import asdict
import gzip
from hashlib import sha256
import json

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .audit_v03 import canopy_audit, path_audit
from .canopy_v03 import C, integrated_cluster
from .catalog_v02 import compact
from .catalog_v03 import plate,selected
from .color_v03 import vegetation_color
from .geometry import CFG,ROOT,stroke
from .refined_vegetation import WOODY
from .render import individual_svg
from .rock_surface_v03 import rock, STYLE
from .sheets_v03 import assemble
from .terrain_v03 import protect_terrain


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def snapshots(strokes,roles=None):
    return {s.id:(s.xy,s.pressure_mm,s.phase,s.owner) for s in strokes
            if roles is None or s.role in roles}


def check_original():
    manifest=json.loads((ROOT/"baseline/V02_MANIFEST_SHA256.json").read_text())
    source=ROOT.parent/"Datascape_Procedural_Catalog_Refinement_v02"
    copied=[name for name in manifest if name.startswith(("catalog/","config/","baseline/"))
            or name=="requirements.txt"]
    assert all(sha(ROOT/name)==manifest[name] for name in copied)
    assert sha(ROOT/"baseline/V02_CHECKPOINT_KO.md")==manifest["docs/CHECKPOINT_KO.md"]
    if source.is_dir():
        assert all(sha(source/name)==checksum for name,checksum in manifest.items())
    return len(copied)+1, len(manifest) if source.is_dir() else None


def exports(sheets):
    source_hashes=json.loads((ROOT/"audit/vector_hashes.json").read_text())
    audits=json.loads((ROOT/"audit/path_metrics.json").read_text())
    i=0
    total=0
    for sheet in sheets:
        path=ROOT/"review"/f"{sheet.key}.svg"
        assert path.read_text()==plate(sheet)
        if path.with_suffix(".png").exists():
            with Image.open(path.with_suffix(".png")) as p:
                assert p.width==1600
                p.verify()
        for number,c in enumerate(sheet.cards,1):
            paths=selected(c)
            name=f"{sheet.key}__{number:02}"
            json_path=ROOT/"vectors"/f"{name}.json.gz"
            payload=dict(key=c.key,title=c.title,mode=c.mode,detail_crop_mm=c.crop,
                         metadata=c.meta,strokes=[asdict(p) for p in paths])
            expected=compact(payload)
            assert expected==gzip.decompress(json_path.read_bytes()),name
            assert sha256(expected).hexdigest()==source_hashes[name],name
            assert (ROOT/"vectors"/f"{name}.svg").read_text()==individual_svg(paths,name),name
            assert len({s.id for s in paths})==len(paths),name
            storage=audits[i]
            view={k:v for k,v in storage.items() if k not in {"id","key","title","crop_mm","canopy"}}
            assert view==path_audit(paths),name
            if c.field is not None:
                assert storage["canopy"]==canopy_audit(paths,c.field),name
            for p in paths:
                xy=np.asarray(p.xy)
                pressure=np.asarray(p.pressure_mm)
                assert len(xy)==len(pressure)>1
                assert np.isfinite(xy).all() and np.isfinite(pressure).all()
                assert np.all(np.linalg.norm(np.diff(xy,axis=0),axis=1)>1e-7),(name,p.id)
                if c.crop is None:
                    assert (xy.min(axis=0)>=0).all() and (xy.max(axis=0)<=np.asarray(sheet.cell)-[3,1.4]).all(),(name,p.id)
                allowed={"LIGHT_INK":("INK_1","INK_2"),"MEDIUM_INK":("INK_3","INK_4"),"COLOR":("COLOR",)}
                assert p.phase in allowed[p.medium]
                assert (p.medium=="COLOR")==bool(p.pigment)
                cap={"LIGHT_INK":"light_mm","MEDIUM_INK":"medium_mm","COLOR":"color_mm"}[p.medium]
                assert (pressure>0).all() and pressure.max()<=CFG["plot_intent"][cap][1]
                total+=1
            i+=1
    assert i==len(audits)==len(source_hashes)
    return i,total


def check_canopy(s):
    isolated,still,partial,mixed,dense,integration=s.cards
    assert snapshots(selected(isolated))==snapshots(selected(still))
    for a,b in ((partial,mixed),(dense,integration)):
        assert snapshots(a.paths,WOODY)==snapshots(b.paths,WOODY)
        raw=canopy_audit(a.paths,a.field)
        new=canopy_audit(b.paths,b.field)
        assert new["shared_paths"]>0
        assert new["overlap_cell_max_mm"]<=C["crowd_length_cap_mm"]
        assert new["overlap_cell_max_mm"]<=raw["overlap_cell_max_mm"]
        assert new["scheduled_near_pairs"]<=new["baseline_y_near_pairs"]
        assert all(len(set(p.features["owners"]))==2 for p in b.paths if p.role=="shared_canopy")
        assert [r["base_xy"] for r in a.meta["specimens"]]==[r["base_xy"] for r in b.meta["specimens"]]
    assert canopy_audit(integration.paths,integration.field)["crossing_pairs"]<canopy_audit(dense.paths,dense.field)["crossing_pairs"]
    return sum(p.role in WOODY for p in integration.paths)


def check_surfaces(s, pair):
    assert len(s.cards)==8
    for c in s.cards:
        m=c.meta
        assert m["shape"] in STYLE and Polygon(m["outline"]).is_valid
        outer=Polygon(m["outline"]).buffer(1e-6)
        for p in c.paths:
            ls=LineString(p.xy)
            if p.role in {"rock_structure","rock_fracture","rock_surface_secondary","rock_face_color"}:
                assert outer.covers(ls),(p.id,m["shape"])
            if p.role=="rock_ground_color":
                assert ls.intersection(Polygon(m["outline"])).length<1e-5,p.id
        for face in m["frames"]:
            assert abs(np.dot(face["u_axis"],face["v_axis"]))<1e-8
            assert abs(np.linalg.norm(face["u_axis"])-1.)<1e-8
    for old,new in zip(pair.cards[::2],pair.cards[1::2]):
        assert Polygon(old.meta["silhouette"]).equals(Polygon(new.meta["outline"]))
        assert [s.xy for s in old.paths if s.role=="silhouette"]==[s.xy for s in new.paths if s.role=="silhouette"]
    _,a,m=rock("test_same", "rounded", (49,96), 47, 17,style="weathered")
    _,b,n=rock("test_same", "rounded", (49,96), 47, 17,style="laminated")
    assert a.equals(b) and m["frames"]!=n["frames"]


def check_masks(s):
    _,masked=s.cards
    data=masked.meta
    outer=unary_union([Polygon(r["outline"]) for r in data["rocks"]])
    terrain=[(s,LineString(s.xy)) for s in masked.paths if s.role=="terrain_A"]
    assert all(ls.intersection(outer).length<1e-5 for _,ls in terrain)
    assert all(ln.length>=5.2-1e-6 for _,ln in terrain)
    counts=[]
    for bounds in data["core_polygons"]:
        poly=Polygon(bounds["outer"],bounds["holes"])
        hits=[s.medium for s,line in terrain if line.intersection(poly).length>1e-5]
        assert len(hits)<=1 and all(m=="LIGHT_INK" for m in hits)
        counts.append(len(hits))
    assert counts==data["mask"]["core_passes_after_rock"]
    # A centered rock separates one originally retained LIGHT pass through a synthetic core.
    from .canopy_v03 import CanopyField
    logs=[{"id":"t","family":"B","growth":{"handedness":1}}]
    field=CanopyField([(50.,50.,14.,9.,"t")]*5,logs)
    p=stroke("a",[(0.,50.),(100.,50.)],"terrain_A","test","test")
    q,cores,metrics=protect_terrain([p],field,box(48,42,52,58),(0,0,100,100))
    assert len(cores)==1 and metrics["core_passes_after_rock"]==[1] and len(q)>=2
    return counts


def check_colors(s, rock_sheet):
    for subject in (s,rock_sheet):
        ink,color,combined=(selected(c) for c in subject.cards)
        assert {p.medium for p in color}=={"COLOR"}
        assert len(color)>1 and len({p.pigment for p in color})>=2
        assert snapshots(ink+color)==snapshots(combined)


def check_season_reuse():
    oldwood=None
    season_counts={}
    for season in ("spring","summer","autumn","winter"):
        old,ink,field,m=integrated_cluster("season_test",(97,89),140,42,54,404,"BBWPUBWBBUP",
             layout="depth",season=season,seasonal=True)
        wood=snapshots(ink,WOODY)
        assert wood==snapshots(old,WOODY)
        if oldwood is not None:
            assert wood==oldwood
        oldwood=wood
        color=vegetation_color("season_test",field,season,m["lod"],404)
        season_counts[season]=dict(ink=len(ink),color=len(color))
        assert len(color)>0 or season=="winter"
    return season_counts


def verify():
    retained, original=check_original()
    sheets=assemble()
    states,count=exports(sheets)
    mapping={s.key:s for s in sheets}
    wood_count=check_canopy(mapping["01_CANOPY"])
    check_surfaces(mapping["03_SURFACES"],mapping["04_SURFACE_CONTROL"])
    check_colors(mapping["02_VEGETATION_COLOR"],mapping["06_ROCK_COLOR"])
    cores=check_masks(mapping["07_MASK"])
    f=mapping["05_FORMATIONS"].cards
    assert [len(card.meta["rocks"]) for card in f]==[5,6,6,34] and len(f[-1].meta["groups"])==10
    assert not any(p.suffix.lower() in {".gcode",".ngc",".nc",".tap"} for p in ROOT.rglob("*"))
    reused=check_season_reuse()
    result=dict(sheets=len(sheets),states=states,stroke_records=count,unchanged_v02_files=original,
                retained_v02_files=retained,dense_unchanged_wood=wood_count,
                integration_light_per_core=cores,season_smoke_test=reused)
    (ROOT/"audit"/"verification.json").write_bytes(compact(result))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    verify()
