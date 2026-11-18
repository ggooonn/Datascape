"""Repeatable matched catalog fixtures. Each card retains native millimetres."""
from dataclasses import dataclass, field
from .geometry import CFG, move
from .vegetation import specimen, community
from .ground import rock, formation
from .context import Cover, soil_support, terrain, terrain_mask, vegetation_masks
import numpy as np

@dataclass
class Card:
    label: str
    subtitle: str
    paths: list
    metadata: dict
    mode: str = "composite"
    field_pads: list = field(default_factory=list)

@dataclass
class Sheet:
    id: str
    title: str
    note: str
    cols: int
    cell: tuple
    cards: list

def single_tree(key,family,h,base,lod,seed,season="spring"):
    p,_,m=specimen(key+"/T00",family,h,base,lod,season,seed=seed)
    return p,m

def group(key,family,width,height,base,seed,count=7,lod="near",mixed=(),mode="refined",season="spring"):
    p,coords,m=community(key, family,base,width,height,seed,count,lod,season,mixed=mixed,mode=mode)
    return p,coords,m

def group_card(key,family,width,height,base,seed,count=7,lod="near",mixed=(),mode="refined",season="spring"):
    p,pads,m=group(key,family,width,height,base,seed,count,lod,mixed,mode,season)
    return vegetation_masks(p,{key:pads},[key]),pads,m

def support_scene(key="SITE",masked=True,season="spring",weak=False):
    # A synthetic slope to test stems/roots/contours at physical plotting scale.
    p,cp,cm=group(key+"/P","P",72,42,(51,57),277,5,"mid",(),season=season)
    v,vp,vm=group(key+"/B","B",64,36,(104,74),483,5,"mid",("U",),season=season)
    rocks,shape,rm=formation(key+"/rock",(94,88),64,23,283,"mid","B","jointed")
    roots=[m["base_xy"] for m in cm["specimens"]+vm["specimens"]]
    mats=soil_support(key+"/soil",roots[::2],shape)
    mats=[s for s in mats if min(x for x,y in s.xy)>=4]
    horizontal=terrain(key+"/terrain",(5,12,147,96),223)
    cover=Cover(cp+vp)
    if masked:
        terrain_paths,mask_metrics=terrain_mask(horizontal,cover,shape,weak)
        plants=vegetation_masks(p+v,{cm["group"]:cp,vm["group"]:vp},[cm["group"],vm["group"]])
    else:
        terrain_paths=horizontal;plants=p+v
        before=sum(s.length for s in horizontal)
        mask_metrics=dict(original_terrain_mm=before,retained_terrain_mm=before,geometric_omission_mm=0)
    return (move(terrain_paths+rocks+mats+plants,8,0),
            [(x+8,y,w,h,owner) for x,y,w,h,owner in cp+vp],
            dict(communities=[cm,vm],formation=rm,mask=mask_metrics,
                 geometry_fixture="synthetic",output_translation_mm=[8,0]))

def assemble():
    sheets=[]
    cards=[]
    for seed in [17,29,121]:
        for f in ["P","B","U","W"]:
            key=f"T{f}-{seed}"
            p,m=single_tree(key,f,48,(42,68),"near",seed)
            cards.append(Card(f"{f} · {CFG['families'][f]['label']}",f"기준 높이 48 mm  /  seed {seed}",p,m))
    sheets.append(Sheet("01_tree_families","식생의 기본 형태","같은 높이에서 줄기·분지·수관의 골격 비교  /  10 mm 축척자",4,(84,79),cards))

    cards=[]
    for f,seed in [("P",174),("B",248),("U",253),("W",555)]:
        p,pads,m=group_card(f"Group-{f}",f,123,58,(90,87),seed,7)
        cards.append(Card(f"{f} · 동족 군집","7개체  /  우점목·중간목·하층목",p,m))
    sheets.append(Sheet("02_related_communities","같은 계열, 서로 다른 생장","같은 군집의 공통 형질과 개체 간 변화  /  10 mm 축척자",2,(180,108),cards))

    upper,up,um=group("ADJ/P","P",60,44,(44,68),94,4,"mid")
    lower,lp,lm=group("ADJ/B","B",63,40,(112,83),327,5,"mid")
    o=vegetation_masks(upper+lower,{um["group"]:up,lm["group"]:lp},[um["group"],lm["group"]])
    p,_,m=group_card("MIX","B",130,48,(82,81),191,8,"near",("P","U"))
    cards=[Card("인접 군집 · P와 B","상단 P / 하단 B  /  먼 층 수관만 선택적으로 감쇠",o,dict(communities=[um,lm])),
           Card("혼합 군집 · B 중심","P·U가 일부 섞이는 한 군집",p,m)]
    sheets.append(Sheet("03_mixed_communities","군집의 경계와 혼합","가까운 두 군집과 하나의 혼합 군집  /  10 mm 축척자",2,(164,103),cards))

    cards=[]
    for f in ["P","B","U","W"]:
        for lod,h in [("near",58),("mid",36),("far",20)]:
            p,m=single_tree(f"LOD-{f}",f,h,(53,78),lod,114)
            cards.append(Card(f"{f} · {dict(near='근경',mid='중경',far='원경')[lod]}",
                              f"기준 높이 {h} mm  /  seed 114",p,m))
    sheets.append(Sheet("04_vegetation_scale","거리에 따른 식생 표현","같은 형질·시드에서 실제 mm와 분지·수관 구조를 함께 변화  /  10 mm 축척자",3,(107,88),cards))

    cards=[]
    for f,seed in [("angular",165),("compact",210),("rounded",432),("buried",67),("bedrock",421)]:
        p,_,m=rock(f"M-{f}/R0",(56,58),83,53,f,seed,dip=-.18)
        name=dict(angular="각진 암괴",compact="응축형",rounded="풍화형",buried="부분 매몰형",bedrock="노출 기반암")[f]
        cards.append(Card(name,f"폭 83 mm  /  seed {seed}",p,m))
    p,_,m=rock("M-compact-alt/R0",(56,59),83,52,"compact",411,regime="jointed",dip=.12)
    cards.append(Card("응축형 · 절리 위주","같은 형식에 절리와 방향 변형",p,m))
    sheets.append(Sheet("05_rock_masses","암괴의 몸체와 노출 정도","형상·매몰·면 구성의 조합  /  10 mm 축척자",3,(111,72),cards))

    cards=[]
    for policy in ["A","B"]:
        for t in ["layered","jointed","weathered"]:
            p,_,m=formation(f"F-{policy}",(65,68),101,49,520,"near",policy,t)
            subtitle=dict(layered="층리 방향",jointed="교차 절리",weathered="완만한 풍화 결")[t]
            cards.append(Card(f"{policy}형 · {subtitle}","같은 폭과 시드   /  seed 520",p,m))
    sheets.append(Sheet("06_formations","연결 방식과 면의 결","A는 노출 단일 기반암, B는 공유 방향과 앞뒤 관계를 갖는 다중 암괴",3,(124,81),cards))

    cards=[]
    for regime in ["layered","jointed","weathered"]:
        for lod,w,h in [("near",105,52),("mid",72,32),("far",37,19)]:
            p,_,m=formation(f"RockLOD-{regime}",(62,69),w,h,71,lod,"B",regime)
            cards.append(Card(dict(layered="층리",jointed="교차 절리",weathered="풍화")[regime]+
                              " · "+dict(near="근경",mid="중경",far="원경")[lod],f"폭 {w} mm  /  seed 71",p,m))
    sheets.append(Sheet("07_rock_scale","암반의 크기와 세부 위계","원경에서 미세 결과 일부 암괴를 생략하고 주면 구조를 유지  /  10 mm 축척자",3,(124,82),cards))

    cards=[]
    for mode in ["independent","refined"]:
        p,_,m=group_card("ITER-P","P",124,56,(87,81),162,7,"near",mode=mode)
        cards.append(Card("개체 독립 변이 대조" if mode=="independent" else "공통 형질과 개체 차등",
                          "동일 가족·시드·배치 생성 조건",p,m))
    for mode in ["regular","refined"]:
        p,_,m=formation("ITER-ROCK",(76,72),110,49,378,"near","B","layered",mode)
        cards.append(Card("균등 내부선 대조" if mode=="regular" else "면별 방향·열린 간격",
                          "동일 형상·시드·재료",p,m))
    sheets.append(Sheet("08_iteration","변이 규칙 전후 비교","실험 대조군과 수정안  /  차이는 개체 관계와 면 내부 구성에서 확인",2,(174,100),cards))

    unmasked,p,m=support_scene(masked=False)
    masked,q,n=support_scene()
    weak,w,t=support_scene(weak=True)
    cards=[Card("마스크 전","같은 지형 A와 식생·암반 벡터",unmasked,m,"ink"),
           Card("약한 대조","보조선 대부분 유지, 압력 감쇠 최대 30%",weak,t,"ink"),
           Card("군집 아래 선택 감쇠","중심부 일부 생략 + 가장자리 완화",masked,n,"ink"),
           Card("식생 점유 강도","녹색 농도는 지형 감쇠에 사용한 공간 변수",masked,n,"mask",q)]
    sheets.append(Sheet("09_context_masks","지형·식생·암괴의 접점","앞뒤 군집은 겹치되, 지형선이 수관과 암면을 덮어 버리지 않게 조정",2,(168,106),cards))

    cards=[Card("누적 1 · 연묵 전반","1단계까지",masked,n,"ink_1"),
           Card("누적 2 · 연묵 후반","2단계까지",masked,n,"ink_2"),
           Card("누적 3 · 중묵 전반","3단계까지",masked,n,"ink_3"),
           Card("누적 4 · 중묵 후반","연묵·중묵 4단계 전체",masked,n,"ink"),
           Card("채색 포함","먹 + 수관·암면·흙의 독립 색 경로",masked,n,"composite")]
    sheets.append(Sheet("10_ink_color","먹선 누적과 채색 적합성","동일 벡터의 표시 단계 비교  /  색과 선폭은 화면 시안",2,(168,106),cards))

    cards=[]
    for code,label in [("spring","봄"),("summer","여름"),("autumn","가을"),("winter","겨울")]:
        p,_,m=group_card("SEASON","B",125,52,(75,73),344,7,"mid",("P","U"),season=code)
        cards.append(Card(label+" · 동일 골격","고정 시드 344  /  수관 밀도·개방도·색 제안",p,m))
    sheets.append(Sheet("11_season_parameters","계절 파라미터의 범위","네 가지 계절 가설의 동일 군집 비교  /  계절별 작품과 분리된 예제",2,(155,87),cards))
    return sheets
