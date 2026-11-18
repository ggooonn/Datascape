"""Matched rock and vegetation comparisons for the overlap study."""
from dataclasses import replace

from .canopy_area_v04 import localize_color, regional_canopy
from .canopy_v03 import CanopyField
from .color_v03 import project_clip,tint,vegetation_color
from .ground_bands_v05 import bands,rock_anchors,root_anchors
from .refined_vegetation import specimen
from .rock_mass_v04 import connected_formation
from .rock_overlap_v05 import Placement,compose,make_rocks
from .sheets_v03 import Card,Sheet,studies
from .sheets_v04 import ROCKS,canopy_comparison
from .terrain_v03 import terrain_fixture


def material_comparison():
    empty_layout=make_rocks([
        Placement(f"link_study/R{i:02}",r.shape,r.x,r.y,r.width,i,517+i*31,r.bedding)
        for i,r in enumerate(ROCKS)
    ])
    separate,_,a=compose(empty_layout)
    fused,_,b=connected_formation("link_study",ROCKS,[0,2],517)
    overlap=make_rocks([
        Placement(f"link_study/R{i:02}",r.shape,x,y,r.width,z,517+i*31,r.bedding)
        for i,(r,x,y,z) in enumerate(zip(ROCKS,(60,96,144,181),(81,98,88,100),(1,3,0,2)))
    ])
    visible,_,c=compose(overlap)
    return Sheet("01_ROCK_GROUP","분리암·부분 접합·앞뒤 겹침",
        "같은 네 암괴의 형상, 폭, 면 시드. 겹침 시편에서는 배치를 바꾸고 앞뒤 순서를 지정했다.",
        (270,112),1,[
            Card("분리된 암괴","각진형 · 층상형 · 직립형 · 둥근형",separate,"isolated","ink",a),
            Card("v04 부분 접합","어깨와 층리로 양쪽 형상을 이었던 종전 시편",fused,"partial_fusion","ink",b),
            Card("v05 겹침 배치","앞 층상암과 둥근암의 외곽에서 뒤쪽 구조선이 가려짐",visible,"overlap_four","ink",c)])


def pair_comparison():
    pair=make_rocks([
        Placement("pair/rear","angular",66,83,73,0,268,-.08),
        Placement("pair/front","layered",110,96,74,1,316,-.22),
    ])
    plan,_,m=compose(pair)
    raw=[p for o in pair for p in o.paths]
    reverse,_,rev=compose([replace(o,depth=1-o.depth) for o in pair])
    return Sheet("02_DEPTH","같은 두 암괴의 가림 순서",
        "윤곽과 면의 먹선·색선을 같은 좌표에 놓고, 가림 적용과 앞뒤 반전을 비교했다.",
        (169,111),2,[
            Card("겹침 대조","두 암괴의 전체 선을 표시",raw,"pair_raw","combined",m),
            Card("층상암이 앞","층상암을 그대로 두고 각진암의 가려진 선을 자름",plan,"pair_layered_front","combined",m),
            Card("각진암이 앞","같은 배치에서 깊이 순서만 반전",reverse,"pair_angular_front","combined",rev),
            Card("경계 확대","앞 암괴의 윗면 윤곽에서 뒤쪽 면선과 색선이 끊김",plan,
                 "pair_zoom","combined",m,(71,52,51,43))])


def ledge_rocks():
    return make_rocks([
        Placement("ledge/pillar","vertical",78,78,45,0,351,-.10),
        Placement("ledge/peak","pointed",142,84,55,1,492,-.12),
        Placement("ledge/edge","angular",47,91,64,2,613,-.15),
        Placement("ledge/round","rounded",167,88,44,3,541,-.12),
        Placement("ledge/bench","layered",106,100,68,4,493,-.19),
        Placement("ledge/foot","blocky",140,106,40,5,618,-.16),
    ])


def ground_study(dense):
    rocks=ledge_rocks()
    visible,solid,rmeta=compose(rocks)
    a=[p for p in terrain_fixture("ledge/lines",(7,61,201,125),423)
       if p.features["line_index"] in (5,8,11,15,18,21)]
    visible_a=[tint(t,.56) for s in a for t in project_clip(s,solid,6.2,"ledge")]
    stone=visible_a+visible
    stone_ground=bands("ledge",rock_anchors(rocks,solid,{"ledge/edge","ledge/bench","ledge/foot"}),
                      a,"rock",782,solid)
    original,_,_,field,m=dense
    ink,region=regional_canopy("canopy_dense",original,field,311)
    coal=vegetation_color("canopy_dense",field,"summer",m["lod"],311)
    foliage=localize_color(coal,field,region["regions"])
    a=[p for p in terrain_fixture("root/lines",(7,74,201,122),426)
       if p.features["line_index"] in (8,13,18,21)]
    forest=[tint(p,.53) for p in a]+ink+foliage
    root=bands("root",root_anchors(m["specimens"]),a,"root",493)
    vmeta=dict(m,**region)
    return Sheet("03_GROUND","겹친 암괴와 뿌리의 수평 지면색",
        "같은 합성에서 짧은 지면색만 더했다. 옅은 먹선은 지면색이 참고한 A선이다.",
        (210,139),2,[
            Card("여섯 암괴 · 기본","앞쪽 층상암과 블록암이 뒤쪽 면을 가림",stone,"ledge_plain","combined",rmeta),
            Card("여섯 암괴 · 발치색","가시 발치 세 곳에 낮고 짧은 색 띠",stone+stone_ground,"ledge_bands","combined",rmeta),
            Card("식생 · 기본","v04의 공유 잎과 수관색",forest,"root_plain","combined",vmeta),
            Card("식생 · 뿌리색","두 뿌리 포켓 사이의 종이색을 살림",forest+root,"root_bands","combined",vmeta)])


def three_trees():
    old=[]
    logs=[]
    pads=[]
    key="trio"
    for i,(fam,x,y,h) in enumerate([("B",61,82,50),("W",70,91,56),("U",79,91,46)]):
        owner=f"{key}/T{i}"
        raw,env,m=specimen(owner,fam,h,(x,y),lod="mid",seed=619+i*29,season="summer",seasonal=True)
        logs.append(m)
        old.extend(raw)
        pads.extend([(*p,owner) for p in env])
    field=CanopyField(pads,logs)
    new,region=regional_canopy(key,old,field,619)
    return old,new,field,dict(specimens=logs,**region)


def canopy_study(partial,dense):
    raw,area,field,m=three_trees()
    study=canopy_comparison(partial,dense)
    preserved=study.cards[-1]
    return Sheet("04_CANOPY","v04 공유 수관과 강한 세 그루 겹침",
        "줄기와 주요 가지를 보존하고, 겹침 영역 안에 두루 보이는 짧은 잎 획을 배치했다.",
        (198,115),2,[
            Card("세 그루 · 개별 수관","B/W/U 개체의 원래 잎을 같은 자리에 표시",raw,"trio_raw","ink",m,field=field),
            Card("세 그루 · 공유 영역","강한 겹침을 v04 영역 규칙으로 재구성",area,"trio_area","ink",m,field=field),
            Card("v04 밀집 시편 · 재현","같은 B/W/P/U 혼합, 좌표와 압력까지 재현",preserved.paths,
                 "canopy_v04","ink",preserved.meta,field=preserved.field),
            Card("밀집 수관 확대","개별 줄기가 보이고 짧은 획들이 빈 곳을 나누어 채움",preserved.paths,
                 "canopy_detail","ink",preserved.meta,(31,42,65,48),preserved.field)])


def assemble():
    partial,dense=studies()
    return [material_comparison(),pair_comparison(),ground_study(dense),canopy_study(partial,dense)]
