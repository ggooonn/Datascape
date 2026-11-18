"""Full v08 checkpoint plates with frozen reference and new seasonal applications."""
from dataclasses import asdict

from .canopy_area_v04 import localize_color,regional_canopy
from .canopy_v03 import CanopyField
from .color_v03 import project_clip,tint,vegetation_color
from .ground_attachment_v07 import TerrainFrame,rock_contacts,root_contacts
from .ground_enrichment_v08 import V08,enrich
from .occlusion_v04 import hide_behind_rock
from .refined_vegetation import specimen
from .rock_families_v06 import rock_family
from .sheets_v03 import Card,Sheet
from .sheets_v07 import GROUND_ROLES,SITE_BOX,v06_fixture
from .terrain_v03 import protect_terrain,terrain_fixture


def ground_compare():
    site,objects,solid,meta=v06_fixture("04_ROOT_GROUND__03")
    frozen=[p for p in site if p.role not in GROUND_ROLES]
    frame=TerrainFrame.from_lines(terrain_fixture("site/ground",SITE_BOX,376),SITE_BOX)
    contacts=root_contacts(meta["specimens"],solid,frame)+rock_contacts(objects,frame)
    from .ground_attachment_v07 import ground_patches
    original,_,_,audit=ground_patches("site_v07",contacts,frame,solid,1170)
    cards=[Card("v07 접지 기준","뿌리와 발치마다 짧은 지면색",frozen+original,"site_v07","combined",
                dict(meta,ground=audit),(5,45,244,90))]
    for preset,title,note in [
        ("light","v08 절제안","길이 입력 1.22배 · 획 수 상한 1.5배"),
        ("checkpoint","v08 체크포인트안","길이 입력 1.30배 · 획 수 상한 2배"),
    ]:
        bands,meta_ground=enrich("site_v07",contacts,frame,solid,1170,preset)
        cards.append(Card(title,note,frozen+bands,f"site_{preset}","combined",dict(meta,ground=meta_ground),(5,45,244,90)))
    return Sheet("01_GROUND","지면색 길이와 밀도 비교",
                 "v07의 같은 접지점에서 가로 길이와 간격을 비교했다. 마지막 시편을 조합 예시의 기준으로 사용했다.",
                 (257,110),1,cards)


def vegetation_for(example,solid):
    key=example["key"]
    seed=example["seed"]
    raw=[]
    logs=[]
    pads=[]
    for i,(family,x,y,height) in enumerate(example["plants"]):
        owner=f"combinations/{key}/T{i:02}"
        level="near" if height>45 else "mid" if height>=30 else "far"
        paths,area,info=specimen(owner,family,height,(x,y),lod=level,seed=seed+29*i,
                                 season=key,seasonal=True)
        raw.extend(paths)
        logs.append(info)
        pads.extend((*p,owner) for p in area)
    field=CanopyField(pads,logs)
    ink,region=regional_canopy(f"combinations/{key}/crown",raw,field,seed)
    color=localize_color(vegetation_color(f"combinations/{key}/crown",field,key,"mid",seed),field,region["regions"])
    parts,hide=hide_behind_rock(ink+color,logs,solid)
    return parts,field,dict(specimens=logs,vegetation_occlusion=hide,**region)


def combination(example):
    key=example["key"]
    ident=f"combinations/{key}"
    objects,rock,solid,data=rock_family(ident,example["family"],example["arrangement"],
                                     example["seed"],scale=example["scale"],origin=tuple(example["origin"]))
    plants,field,meta=vegetation_for(example,solid)
    box=(8,79,249,139)
    a=terrain_fixture(f"{ident}/terrain",box,example["seed"])
    frame=TerrainFrame.from_lines(a,box)
    contacts=root_contacts(meta["specimens"],solid,frame)+rock_contacts(objects,frame)
    color,audit=enrich(ident,contacts,frame,solid,example["seed"])
    terrain=[p for p in a if p.features["line_index"] in (6,10,15,18,20,22)]
    support,_,terrain_audit=protect_terrain(terrain,field,solid,(6,75,251,145))
    support=[tint(p,.54) for p in support]
    return Card(example["title"],example["note"],support+rock+plants+color,key,"combined",
                 dict(data,**meta,ground=audit,terrain_audit=terrain_audit,preset=example),(7,40,244,104))


def combination_sheets():
    cards=[combination(example) for example in V08["layouts"]]
    note="독립 연구 시편. 암괴군, 수관·가지, 접지색을 계절별 다른 배치로 함께 적용했다."
    return [Sheet("02_COMPOSITIONS_A","봄과 여름의 조합",note,(255,116),1,cards[:2]),
            Sheet("03_COMPOSITIONS_B","가을과 겨울의 조합",note,(255,116),1,cards[2:])]


def assemble():
    return [ground_compare(),*combination_sheets()]
