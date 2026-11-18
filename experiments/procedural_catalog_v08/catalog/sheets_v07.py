"""Korean ground-color comparisons with frozen v06 site geometry."""

import gzip
import json

from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union

from .ground_attachment_v07 import TerrainFrame,ground_patches,rock_contacts,root_contacts
from .geometry import ROOT,Stroke
from .rock_overlap_v05 import RockObject
from .sheets_v03 import Card,Sheet
from .terrain_v03 import terrain_fixture

GROUND_ROLES={"rock_ground_band","root_ground_band"}
SITE_BOX=(7,85,247,127)


def marker_data(contacts):
    return [{"xy":list(c.xy),"visible":c.visible,"kind":c.kind} for c in contacts]


def v06_fixture(name):
    with gzip.open(ROOT/"baseline"/"v06_layouts"/f"{name}.json.gz","rt",encoding="utf-8") as handle:
        source=json.load(handle)
    meta=source["metadata"]
    paths=[Stroke(**p) for p in source["strokes"]]
    outlines=[RockObject([],Polygon(r["outline"]),r,r["depth"]) for r in meta["rocks"]]
    return paths,outlines,unary_union([r.outline for r in outlines]),meta


def matched_site(frame):
    original,rocks,solid,meta=v06_fixture("04_ROOT_GROUND__03")
    fixed=[p for p in original if p.role not in GROUND_ROLES]
    roots=root_contacts(meta["specimens"],solid,frame)
    feet=rock_contacts(rocks,frame)
    new,draft,clipped,audit=ground_patches("site_v07",roots+feet,frame,solid,1170)
    return original,fixed,new,draft,clipped,roots,feet,solid,dict(meta,ground=audit)


def assemble():
    frame=TerrainFrame.from_lines(terrain_fixture("site/ground",SITE_BOX,376),SITE_BOX)
    original,fixed,new,draft,clipped,roots,feet,solid,meta=matched_site(frame)
    final=fixed+new
    overview=Sheet("01_COMPARISON","그룹 아래 색 띠에서 개체별 접지색으로",
        "v06 암괴·식생·A선과 채색 경로를 고정했다. 바뀐 지면색만 같은 배치에서 비교한다.",
        (257,110),1,[
            Card("v06 · 그룹 하단 기준","암괴와 식생 포켓 아래에 길게 모인 색 띠",original,
                 "site_v06","combined",meta,(5,45,244,90)),
            Card("v07 · 개체별 접지 기준","뿌리와 바위 발치의 위치에 따라 짧은 획이 층을 이룸",final,
                 "site_v07","combined",meta,(5,45,244,90)),
        ])
    vegetation=[]
    for zone,crop in [("왼쪽",(17,79,61,50)),("오른쪽",(170,79,70,50))]:
        for paths,label,note in [(original,"v06","점은 나무별 뿌리 위치"),(final,"v07","각 뿌리 바로 아래에서 색 띠가 시작")]:
            vegetation.append(Card(f"{zone} 식생 · {label}",note,paths,f"roots_{zone}_{label}","combined",
                                   dict(meta,preview_contacts=marker_data(roots)),crop))
    vegetation_sheet=Sheet("02_ROOTS","앞뒤로 놓인 뿌리의 지면색",
        "원 표시는 v06에서 보존한 나무별 뿌리점이다. 같은 포켓 안에서도 네 뿌리의 화면 Y가 다르다.",
        (157,99),2,vegetation)

    rock_paths,large,large_solid,large_meta=v06_fixture("02_MASSING__04")
    large_feet=rock_contacts(large,frame)
    large_bands,_,_,large_audit=ground_patches("formation_v07",large_feet,frame,large_solid,571)
    rock_meta=dict(large_meta,ground=large_audit)
    rock_sheet=Sheet("03_ROCKS","앞뒤로 겹친 암괴의 접지색",
        "v06의 열한 암괴 배치를 재현했다. 각 암괴의 하단 발치에서 가시 부분에 선을 놓았다.",
        (238,98),1,[
            Card("v06 · 같은 암괴군","암괴면과 깊이 가림의 기준",rock_paths,"formation_v06","combined",
                 rock_meta,(16,44,215,92)),
            Card("v07 · 보이는 발치의 색","앞 열과 뒤 열의 암괴가 서로 다른 위치에 붙는다",rock_paths+large_bands,
                 "formation_v07","combined",rock_meta,(16,44,215,92)),
        ])
    merged=[p for p in new if "merged_from" in p.features]
    if not merged:
        raise ValueError("The review fixture must include a compatible merged ground pass")
    joined=next((p for p in merged if p.role=="root_ground_band"),merged[0])
    x0,y0,x1,y1=LineString(joined.xy).bounds
    merge_crop=((x0+x1)/2-25,(y0+y1)/2-16,50,30)
    blocked=max(draft,key=lambda p:LineString(p.xy).intersection(solid).length)
    x0,y0,x1,y1=LineString(blocked.xy).bounds
    mask_crop=((x0+x1)/2-28,(y0+y1)/2-19,56,34)
    details=Sheet("04_DETAILS","겹친 색 띠와 가림 경계",
        "위는 이웃 색 띠의 합치기 전후다. 아래의 열린 원은 가시 접지점, ×는 뒤에 가려진 발치다.",
        (163,95),2,[
            Card("개별 색 띠","가림 뒤, 접지점별 획을 합치기 전",fixed+clipped,"merge_before","combined",meta,merge_crop),
            Card("한 획으로 정리한 색 띠","높이와 색이 맞는 짧은 겹침 구간만 이음",final,"merge_after","combined",meta,merge_crop),
            Card("가림 적용 전 후보","암괴 외곽 안으로 들어가는 후보도 함께 표시",fixed+draft,
                 "mask_before","combined",dict(meta,preview_contacts=marker_data(feet)),mask_crop),
            Card("가림 적용 후","바위에 덮인 발치와 선분은 색 띠에서 빠짐",final,
                 "mask_after","combined",dict(meta,preview_contacts=marker_data(feet)),mask_crop),
        ])
    return [overview,vegetation_sheet,rock_sheet,details]
