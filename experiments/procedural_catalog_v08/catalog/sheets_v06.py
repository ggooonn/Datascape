"""Comparative Korean plates for related rock families and supporting root zones."""
from .color_v03 import project_clip,tint
from .ground_bands_v05 import bands,rock_anchors,root_anchors
from .rock_families_v06 import rock_family
from .root_zone_v06 import collective_root_zone,supported_bands
from .sheets_v03 import Card,Sheet
from .terrain_v03 import terrain_fixture

FAMILY_LABELS={"strata":"층상군","jointed":"절리군","weathered":"풍화형"}


def family_study():
    descriptions={
        "strata":"완만히 눕는 앞면 층리 · 단차가 있는 외곽",
        "jointed":"기울어진 면의 결 · 같은 방향의 절리",
        "weathered":"낮고 둥근 외곽 · 휘어진 면의 결",
    }
    cards=[]
    for i,(family,label) in enumerate(FAMILY_LABELS.items()):
        _,paths,_,m=rock_family(f"specimen/{family}",family,"medium",333+17*i)
        cards.append(Card(label,descriptions[family],paths,f"family_{family}","combined",m,(18,47,192,75)))
    return Sheet("01_FAMILIES","같은 배치에서 보는 암괴군 세 계열",
        "중간 암괴 여섯 개의 위치와 폭을 고정했다. 계열마다 외곽, 높이 비, 면 방향과 결을 바꿨다.",
        (222,92),1,cards)


def composition_study():
    choices=[
        ("anchor","주암과 받침암","폭이 큰 주암을 앞의 작은 외곽들이 받침"),
        ("sequence","큰 암괴의 연속","네 큰 단면과 두 작은 받침암 · 비대칭 높이"),
        ("medium","중간 암괴군","크기 차이를 좁히고 앞뒤 간격으로 층을 냄"),
        ("formation","여러 층으로 포갠 암반","열한 암괴가 앞·중간·뒤에서 서로 다른 폭으로 드러남"),
    ]
    cards=[]
    for i,(layout,label,note) in enumerate(choices):
        _,paths,_,m=rock_family(f"composition/{layout}","strata",layout,587+i*47)
        cards.append(Card(label,note,paths,f"layout_{layout}","combined",m,(13,38,215,93)))
    return Sheet("02_MASSING","같은 층상 계열의 네 가지 덩어리",
        "높이와 폭, 간격을 바꾸었다. 앞 암괴가 뒤쪽 외곽과 표면선을 가리는 v05 규칙을 사용했다.",
        (235,112),2,cards)


def overlap_study():
    key="same_rocks"
    _,loose,_,m0=rock_family(key,"jointed","medium",472,spread=1.38,origin=(8,2))
    rocks,strong,_,m1=rock_family(key,"jointed","medium",472,spread=.73,origin=(8,2))
    raw=[s for item in rocks for s in item.paths]
    return Sheet("03_OVERLAP","같은 절리군의 겹침 강도",
        "같은 암괴와 시드, 축척 및 깊이 순서. 가로 간격을 좁혔을 때 앞 외곽이 뒤쪽 선을 어디서 가리는지 비교했다.",
        (254,100),2,[
            Card("느슨한 배치","완만한 겹침 · 암괴 사이의 간격이 넓음",loose,"loose","combined",m0,(3,45,236,78)),
            Card("집중된 배치","가로 간격을 좁힘 · 앞 암괴가 뒤쪽을 깊게 가림",strong,"strong","combined",m1,(3,45,236,78)),
            Card("집중 배치의 전체 경로","가림 적용 전 같은 위치의 면선·색선",raw,"strong_raw","combined",m1,(3,45,236,78)),
            Card("가림 경계 확대","앞쪽 외곽 위에서 뒤쪽의 결이 끊김",strong,"strong_detail","combined",m1,(103,72,68,49)),
        ])


def root_study():
    key="site"
    objects,rock,solid,meta=rock_family(key,"strata","anchor",667,scale=.82,origin=(51,15))
    trees=[("B",32,107,33),("W",42,111,37),("U",52,114,35),("B",61,118,30),
           ("U",188,101,35),("B",198,105,39),("W",209,111,31),("B",220,116,30)]
    base,new,field,veg=collective_root_zone("root_zone",trees,solid,831)
    terrain=[p for p in terrain_fixture("site/ground",(7,85,247,127),376)
             if p.features["line_index"] in (7,12,16,20,22)]
    trace=[tint(q,.46) for p in terrain for q in project_clip(p,solid,6.2,"occupied")]
    rock_zones=rock_anchors(objects,solid,{f"{key}/R00",f"{key}/R02"})
    roots=root_anchors(veg["specimens"])
    normal=bands("site/color",rock_zones,terrain,"rock",818,solid)+bands("root/color",roots,terrain,"root",819,solid)
    wide=supported_bands("site/color",rock_zones,terrain,"rock",818,solid)+supported_bands("root/color",roots,terrain,"root",819,solid)
    common=trace+rock
    m=dict(meta,**veg)
    return Sheet("04_ROOT_GROUND","발치색과 뿌리 수관",
        "같은 배치에서 지면색의 가로 폭만 먼저 늘렸다. 이어서 공유 수관 둘레의 짧은 개별 잎을 덜어내었다.",
        (257,116),2,[
            Card("기준","v05 폭의 지면색 · v04 공유 수관",common+normal+base,"roots_base","combined",m,(5,45,244,90),field),
            Card("지면색을 조금 넓힘","같은 획 수 · 가로 폭 +16% 입력",common+wide+base,"roots_wide","combined",m,(5,45,244,90),field),
            Card("뿌리 수관 정리","공유 영역을 살리고 가장자리의 짧은 개별 잎 감소",common+wide+new,"roots_collective","combined",m,(5,45,244,90),field),
            Card("발치와 수관 확대","공유 잎·가지와 뿌리 아래 얕은 띠",common+wide+new,"roots_detail","combined",m,(21,73,86,59),field),
        ])


def assemble():
    return [family_study(),composition_study(),overlap_study(),root_study()]
