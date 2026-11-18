"""Matched plates for the five scoped refinements."""
from dataclasses import dataclass, field, replace
import numpy as np

from .geometry import CFG, curve, stroke
from .context import Cover, terrain, terrain_mask
from .vegetation import community as v01_community
from .ground import formation as v01_formation
from .refined_vegetation import REF, community, specimen, undergrowth
from .rock_v02 import PROFILES, NAMES, group, rock, large_formation
from .masking_v02 import core_one, core_audit


@dataclass
class Card:
    label: str
    subtitle: str
    paths: list
    meta: dict = field(default_factory=dict)
    overlay: str = ""


@dataclass
class Sheet:
    id: str
    title: str
    note: str
    cols: int
    cell: tuple
    cards: list


def comparison_canopy():
    cards=[]
    for seed, family in [(17,"B"),(17,"W"),(121,"B"),(121,"W")]:
        for variant in ("v01","v02"):
            p,_,m=specimen(f"study/{family}-{seed}",family,57,(49,70),"near",seed=seed,variant=variant)
            cards.append(Card(f"{family} · {variant}",f"동일 골격 · 높이 57 mm · seed {seed}",p,m))
    return Sheet("01_BW","B의 완만한 수관, W의 처짐",
                 "왼쪽 각 쌍이 v01, 오른쪽이 v02. 같은 줄기와 크기에 수관 획만 비교했다.",4,(98,82),cards)


def lod_sheet():
    cards=[]
    for family in ("B","W"):
        for lod,height,title in [("near",61,"근경"),("mid",38,"중경"),("far",21,"원경")]:
            p,_,m=specimen(f"lod/{family}",family,height,(53,74),lod,seed=29)
            cards.append(Card(f"{family} · {title}",f"높이 {height} mm · 가지와 밴드 수를 단계별로 축소",p,m))
    return Sheet("02_BW_LOD","근·중·원경의 골격과 획 예산","거리 단계에 따라 선의 개수와 굴곡을 단순화했다. 각 판은 동일한 mm 좌표다.",3,(107,87),cards)


def mixed_sheet():
    cards=[]
    for variant in ("v01","v02"):
        p,_,m=community("BW_mixed",(105,87),173,58,58,108,"BWBWWBBWBBW",layout="depth",
                        lod="mid",variant=variant,vegetation_mask=False)
        cards.append(Card("v01 수관 규칙" if variant=="v01" else "v02 수관 규칙",
                          "같은 X/Y·수종 역할·크기·방향 · 수관만 비교",p,m))
    return Sheet("03_BW_MIX","같은 혼합 군집의 수관 전후","B와 W가 섞인 상태에서 길이와 밀도를 비교했다. 가림 보정도 동일하게 배제했다.",2,(209,127),cards)


def distribution_sheet():
    presets=[("dense","집중 군집","BBWBUBWBBUWBUB"),("sparse","성긴 군집","BPWUBUBP"),
             ("depth","전후 군집","BBWBUBUBWWBP")]
    p,_,m=v01_community("row_control","B",(117,114),177,54,179,12,"mid",mixed=("W","U"))
    cards=[Card("v01 · X축 대조","기존 열 배치 · 12개체",p,m,"bases")]
    for layout,title,families in presets:
        seed = 201 if layout == "depth" else 179
        p,_,m=community(f"distribution_{layout}",(117,109),177,65,54,seed,families,layout=layout)
        cards.append(Card(title,f"{len(families)}개체 · 하단 배치도는 X/Y 위치와 포켓",p,m,"bases"))
    return Sheet("04_CLUSTERS","X/Y 군집과 열림","판의 왼쪽·오른쪽 포켓 밀도와 앞뒤 위치를 함께 다르게 배치했다.",2,(231,188),cards)


def silhouette_sheet():
    cards=[]
    for i,(key,label) in enumerate(NAMES.items()):
        p,_,m=rock(f"forms/{key}",key,(42,79),45,157+i*7)
        cards.append(Card(label,f"기준 폭 45 mm · 높이 {m['height_mm']:.0f} mm · {m['texture']}",p,m))
    return Sheet("05_ROCK_FORMS","8종 암괴 실루엣",
                 "같은 기준 폭에서 꼭짓점, 직립면, 둥근 몸체, 단차, 파편과 암반 노출을 구분했다.",4,(86,92),cards)


def grouping_sheet():
    p,_,m=v01_formation("rocks_v01",(85,79),105,43,43,"near","B","layered")
    variants=[Card("v01 연결 암괴","비교 기준 · 종속암의 덩어리가 상대적으로 큼",p,m)]
    for i,(form,title,width,subs) in enumerate([
        ("vertical","직립 주암 + 응집 파편",53,("fragmented","blocky","rounded","fragmented")),
        ("layered","층상 주암 + 바닥 지지",67,("angular","rounded","bedrock","fragmented","blocky")),
        ("bedrock","노출 기반암 + 성긴 지지",79,("rounded","pointed")),
    ]):
        p,_,m=group(f"group_{i}",(85,82),width,43+i*53,"near",form,subs,bedding=-.16)
        variants.append(Card(title,f"주암 {width} mm · 종속암 {len(subs)}개",p,m))
    return Sheet("06_ROCK_GROUPS","주암과 종속암의 크기 비",
                 "주암 주변에 더 낮고 작은 받침을 불규칙하게 배치했다. 뒤쪽 경로는 앞 암괴 면에서 끊었다.",2,(172,110),variants)


def rock_lod_sheet():
    cards=[]
    for lod,w,label in [("near",82,"근경"),("mid",52,"중경"),("far",29,"원경")]:
        p,_,m=group("scale_rock",(67,80),w,733,lod,"layered",("angular","rounded","fragmented"),bedding=-.16)
        cards.append(Card(label,f"기준 폭 {w} mm · 같은 시드와 몸체 유형",p,m))
    return Sheet("11_ROCK_LOD","같은 암괴군의 거리 단계",
                 "층상 주암과 같은 계열의 종속암을 비교한다. 원경은 옆면과 미세 절리의 예산이 작다.",
                 3,(137,110),cards)


def formation_sheet():
    p,_,m=large_formation(seed=410)
    return Sheet("07_ROCK_FORMATION","같은 지형 방향을 공유하는 10개 암괴군",
                 "세로와 가로 노출면을 섞고, 사이의 빈 구간을 유지한 넓은 형성체.",1,(370,176),
                 [Card("10개 그룹 · seed 410","그룹마다 우세 암괴와 서로 다른 종속암",p,m,"rocks")])


def mixed_terrain(key):
    original=terrain(key,(8,16,186,111),551)
    work=[]
    for i,s in enumerate(original):
        if s.features["line_index"]%4==1:
            work.append(stroke(s.id,s.xy,s.role,s.group,s.owner,True,i%2,features=s.features))
        else:
            work.append(s)
    return work


def mask_sheet():
    p,pads,m=community("mask-site",(99,82),151,48,53,311,"BBBBUBWBBBBU",
                       layout="dense",lod="mid",vegetation_mask=True,season="summer",seasonal=True)
    terra=mixed_terrain("mask-terrain")
    old,old_meta=terrain_mask(terra,Cover(pads))
    revised,cores,metrics=core_one(terra,pads,(4,4,189,110))
    cards=[Card("마스크 전","LIGHT와 MEDIUM 지형선",terra+p,dict(m,terrain=core_audit(terra,cores))),
           Card("v01 단계 감쇠","위치 동일 · 이전 감쇠와 생략 규칙",old+p,dict(m,terrain=core_audit(old,cores))),
           Card("v02 · 중심부 한 획","연결 코어 안에 LIGHT 최대 1, MEDIUM 0",revised+p,dict(m,terrain=metrics)),
           Card("코어·남은 지형선","녹색은 코어 경계 · 지형 경로만 표시",revised,dict(m,terrain=metrics),"core")]
    return Sheet("08_MASK","수관 아래 지형선 한 획",
                 "같은 군집·지형의 무처리, v01, v02 비교. 지형선만 위상별 색으로 구분했다.",2,(197,124),cards)


SEASON_NAMES={"spring":"봄","summer":"여름","autumn":"가을","winter":"겨울"}
ASPECTS={"spring":"새순과 열린 군집 경계","summer":"수관이 닿는 두터운 그늘·하층","autumn":"분리된 잎 덩이·마른 초본","winter":"노출 잔가지·P 잔잎·바닥 드러남"}


def season_sheet(same):
    cards=[]
    for season,label in SEASON_NAMES.items():
        rule=REF["season_compositions"][season]
        if same:
            key="same-season-site"
            w,d,h=155,51,44
            seed,families,layout=404,"BBWPUBWBBUP","depth"
        else:
            key=f"composition/{season}"
            w,d=rule["footprint"]
            h=rule["height"]
            seed,families,layout=622,rule["families"],rule["layout"]
            assert rule["count"]==len(families)
        p,pads,m=community(key,(107,93),w,d,h,seed,families,layout,season=season,seasonal=True)
        ground=mixed_terrain("season-terrain")
        exposed=round(5*REF["same_site_seasons"][season]["exposure"])
        ground=[s for s in ground if s.features["line_index"]>=16-exposed]
        masked,_,mask=core_one(ground,pads,(5,12,190,114))
        weeds=undergrowth(f"{key}/cover",m["specimens"],season)
        c=Card(label,ASPECTS[season],masked+weeds+p,
               dict(m,same_site=same,understory_count=len(weeds),terrain=mask,
                    canopy_pattern=REF["same_site_seasons"][season]["pad_pattern"]))
        cards.append(c)
    return Sheet("09_SAME_SITE" if same else "10_COMMUNITIES",
                 "동일 장소와 개체의 계절 변화" if same else "계절별 식생 구성",
                 "줄기·가지, 종별 역할, 위치를 고정했다. 계절별 수관·잔가지·하층과 지형 노출을 비교했다." if same
                 else "같은 도판 조건에 계절별 포켓, 가족 조합, 개체 수와 하층 비율을 별도로 설계했다.",
                 2,(213,130),cards)


def assemble():
    return [comparison_canopy(),lod_sheet(),mixed_sheet(),distribution_sheet(),silhouette_sheet(),
            grouping_sheet(),formation_sheet(),mask_sheet(),season_sheet(True),season_sheet(False),rock_lod_sheet()]
