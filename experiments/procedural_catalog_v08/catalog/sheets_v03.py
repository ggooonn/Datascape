"""Matched specimens and independent vector review sheets."""
from dataclasses import dataclass, field
import numpy as np

from .canopy_v03 import integrated_cluster, integrated_specimen
from .color_v03 import vegetation_color
from .rock_surface_v03 import rock, formation
from .rock_v02 import rock as old_rock, NAMES
from .terrain_v03 import terrain_fixture, protect_terrain, attenuate_rear_rock


@dataclass
class Card:
    title: str
    note: str
    paths: list
    key: str
    mode: str = "combined"
    meta: dict = field(default_factory=dict)
    crop: tuple | None = None
    field: object = None


@dataclass
class Sheet:
    key: str
    title: str
    note: str
    cell: tuple
    cols: int
    cards: list


def cluster(key, **kwargs):
    old,new,field,meta=integrated_cluster(key,**kwargs)
    color=vegetation_color(key,field,meta["season"],meta["lod"],kwargs["seed"])
    return old,new,color,field,meta


def studies():
    partial = cluster("canopy_partial",base=(100,88),width=117,depth=41,height=52,
                      seed=174,families="BWBUPWB",layout="depth",season="summer",seasonal=True)
    dense = cluster("canopy_dense",base=(100,88),width=144,depth=46,height=64,
                    seed=311,families="BBWBUBWBBUWBUB",layout="dense",season="summer",seasonal=True)
    return partial,dense


def canopy_comparison(partial,dense):
    cards=[]
    iso=[integrated_specimen(f"study/isolated/{family}",family,57,(x,82),17)
         for x,family in [(53,"B"),(138,"W")]]
    old=[s for a,_,_,_ in iso for s in a]
    new=[s for _,b,_,_ in iso for s in b]
    meta={"specimens":[m["specimens"][0] for *_,m in iso]}
    cards += [Card("v02 · B와 W 고립 표본","같은 줄기와 가지 · 왼쪽 B, 오른쪽 W",old,"isolated_v02","ink",meta),
              Card("v03 · 고립부 보존","겹침이 없으므로 수관과 골격을 그대로 사용",new,"isolated_v03","ink",meta)]
    for key,title,(old,new,_,field,m) in [("partial","부분 겹침",partial),("dense","밀집 혼합",dense)]:
        cards += [Card(f"v02 · {title}","같은 배치와 가지 · 개체별 수관선",old,f"{key}_v02","ink",m,field=field),
                  Card(f"v03 · {title}","공유 획 · 밀집 길이 상한 · 빈 구간",new,f"{key}_v03","ink",m,field=field)]
    return Sheet("01_CANOPY","식생 겹침 전후",
                 "같은 개체와 축척. 독립 수관에서 부분 겹침과 밀집 포켓으로 이어지는 세 조건의 먹선 비교.",(198,122),2,cards)


MODES=[("INK","ink"),("COLOR","color"),("INK + COLOR","combined")]


def vegetation_color_sheet(dense):
    _,ink,c,field,m=dense
    return Sheet("02_VEGETATION_COLOR","식생의 공유 색 영역",
                 "같은 밀집 군집. 잎의 성장 방향을 따라 색선을 굽히고, 열린 통로를 유지했다.",(198,122),3,
                 [Card(label,"먹선·색선과 개체 위치가 같은 비교",ink+c,f"vegetation_{mode}",mode,m,field=field)
                  for label,mode in MODES])


def rock_surfaces():
    cards=[]
    for i,(shape,title) in enumerate(NAMES.items()):
        ink_combo,_,meta=rock(f"surface/{shape}",shape,(41,90),47,773+13*i,bedding=-.14)
        cards.append(Card(title,f"{meta['style']} · 기준 폭 47 mm",ink_combo,f"surface_{shape}","combined",meta))
    return Sheet("03_SURFACES","암괴의 외곽과 면별 준법",
                 "같은 폭에 보존된 8종 외곽. 면축을 따라 세로 결, 절리, 층리, 풍화곡선, 열린 면을 달리했다.",(83,109),4,cards)


def surface_control():
    sections=[("vertical","직립형"),("rounded","둥근형"),("layered","층상형")]
    cards=[]
    for i,(shape,title) in enumerate(sections):
        owner=f"surface_match/{shape}"
        base=(42,85)
        old,p,m=old_rock(owner,shape,base,48,681+i*41,bedding=-.15)
        proposed,q,m3=rock(owner,shape,base,48,681+i*41,bedding=-.15)
        assert p.equals(q)
        cards.extend([Card(f"v02 · {title}","같은 바깥선과 시드",old,f"old_{shape}","ink",m),
                      Card(f"v03 · {title}","동일 외곽 · 새 면 좌표",proposed,f"new_{shape}","ink",m3)])
    return Sheet("04_SURFACE_CONTROL","동일 암괴의 내부 구조 전후",
                 "직립형의 세로 방향, 둥근형의 휜 표면, 층상형의 길고 짧은 층리를 비교했다.",(86,103),2,cards)


def rock_formations():
    variations=[("serial","여러 주암의 연속","직립·각진·뾰족·블록형 주암의 높낮이"),
               ("anchor","큰 주암과 작은 파편","층상 주암 1개 · 지지암 5개"),
               ("medium","중간 크기의 암괴군","22–31 mm 암괴가 앞뒤로 맞물림"),
               ("field","같은 지질 축의 넓은 형성체","10개 군, 지지암을 포함해 34개 암괴")]
    return Sheet("05_FORMATIONS","암괴군 구성 네 가지",
                 "주암의 개수와 비율, 군 사이 간격, 앞뒤 겹침을 바꿨다.",(203,128),2,
                 [Card(title,note,p,variant,"combined",m)
                  for variant,title,note in variations
                  for p,_,m in [formation(f"formation/{variant}",variant)]])


def rock_color_sheet():
    p,_,m=formation("formation_color","anchor",seed=228)
    return Sheet("06_ROCK_COLOR","암괴 면과 바닥의 색",
                 "같은 층상 암괴군. 색선은 면축을 따르며 암괴 발치에서 바닥으로 약하게 이어진다.",(201,126),3,
                 [Card(label,"회색·황토·갈색·회녹 후보",p,f"rock_{mode}",mode,m) for label,mode in MODES])


def context_study():
    key="joint_study"
    stone,rocks,rock_data=formation(key+"_rock","medium",base=(162,103),seed=690,scale=1.03)
    old,ink,color,field,meta=cluster(key+"_veg",base=(86,113),width=125,depth=39,height=58,
                                   seed=322,families="BPWBUBBWU",layout="dense",season="spring",seasonal=True)
    terrain=terrain_fixture(key+"_terrain",(8,22,250,147),777)
    fore,cores,stats=protect_terrain(terrain,field,rocks,(5,8,253,151))
    shaped_rocks=attenuate_rear_rock(stone,field,rock_data["rocks"])
    meta=dict(meta,rocks=rock_data["rocks"],mask=stats,
              core_polygons=[dict(outer=list(p.exterior.coords),
                                  holes=[list(h.coords) for h in p.interiors]) for p in cores])
    compare=terrain+stone+ink+color
    refined=fore+shaped_rocks+ink+color
    return compare,refined,meta,field


def mask_sheet(context):
    a,b,m,field=context
    return Sheet("07_MASK","식생·암괴 뒤의 지형 가림",
                 "같은 물체와 같은 지형. 수관 중심부의 통과선 상한과 암괴 외곽의 경계 감쇠를 함께 본다.",(261,160),2,
                 [Card("가림 적용 전","수관과 바위 뒤로 지형선이 관통",a,"terrain_raw","combined",m,field=field),
                  Card("가림 적용 후","연묵 통과선 일부 유지 · 암괴 경계 밖으로 선폭이 회복",b,"terrain_protected","combined",m,field=field)])


def details(dense,context):
    old,new,c,field,m=dense
    a,b,mx,fx=context
    binary=field.overlap>=2.
    weights=field.energy*binary
    yy,xx=np.unravel_index(np.argmax(weights),weights.shape)
    x,y=field.origin+[xx*field.step,yy*field.step]
    crown=(x-26,y-14,52,27)
    touch=(93,59,71,36)
    return Sheet("08_VECTOR_DETAIL","수관·바위 접점의 벡터 확대",
                 "실제 mm 경로의 동일 영역 확대. 첫 행은 수관 겹침, 둘째 행은 암괴·식생·지형의 경계.",(150,81),2,
                 [Card("v02 · 밀집 수관","확대 2.7× · 교차와 가까운 평행 획",old,"dense_crop_v02","ink",m,crown,field),
                  Card("v03 · 공유 획","확대 2.7× · 녹색은 두 개체를 잇는 실제 획",new,"dense_crop_v03","shared",m,crown,field),
                  Card("가림 전 · 경계","확대 2× · 바위와 수관을 관통하는 지형선",a,"terrain_crop_raw","combined",mx,touch,fx),
                  Card("가림 후 · 경계","확대 2× · 남긴 획과 열린 암괴 면",b,"terrain_crop_v03","combined",mx,touch,fx)])


def lod_sheet():
    cards=[]
    for size,lod,title in [(58,"near","근경"),(39,"mid","중경"),(22,"far","원경")]:
        for family in ("B","W"):
            key=f"depth_study/{family}"
            _,ink,field,m=integrated_specimen(key,family,size,(46,79),17,lod)
            color=vegetation_color(key,field,"spring",lod,183)
            cards.append(Card(f"{title} · {family}",f"개체 높이 {size} mm",ink+color,f"lod_{lod}_{family}","combined",m,field=field))
    return Sheet("09_DISTANCE","근·중·원경에 따른 획 예산",
                 "같은 축척에서 기존의 거리별 골격과 새로운 색선 간격을 비교한다.",(90,92),2,cards)


def assemble():
    partial,dense=studies()
    context=context_study()
    return [canopy_comparison(partial,dense),vegetation_color_sheet(dense),rock_surfaces(),
            surface_control(),rock_formations(),rock_color_sheet(),mask_sheet(context),
            details(dense,context),lod_sheet()]
