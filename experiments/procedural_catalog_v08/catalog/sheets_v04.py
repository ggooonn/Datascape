"""Four v04 comparisons reusing matched v03 geometry and materials."""
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .canopy_area_v04 import localize_color, regional_canopy
from .canopy_v03 import CanopyField
from .color_v03 import project_clip, vegetation_color
from .ground_v04 import basal_anchors,ground_patch,root_anchors
from .occlusion_v04 import hide_behind_rock
from .refined_vegetation import specimen
from .rock_mass_v04 import RockSpec,connected_formation
from .terrain_v03 import protect_terrain,terrain_fixture
from .sheets_v03 import Card,Sheet,studies

ROCKS=[RockSpec("angular",41,84,53),RockSpec("layered",106,98,60,-.18),
       RockSpec("vertical",171,86,60),RockSpec("rounded",232,102,55,-.07)]


def rock_links():
    cards=[]
    for idx,(title,notes,connect) in enumerate([
        ("분리된 암괴","같은 위치와 외곽 · 암괴 사이에 틈이 열린 상태",[]),
        ("부분 접합","양쪽 어깨 두 곳은 연결 · 가운데 통로는 열림",[0,2]),
        ("연속 암반","세 접합부의 층리와 어깨가 한 몸체로 이어짐",[0,1,2]),
    ]):
        p,_,m=connected_formation("link_study",ROCKS,connect)
        ink=[s for s in p if s.medium!="COLOR"]
        cards.append(Card(title,notes,ink,f"rock_link_{idx}","ink",m))
    return Sheet("01_CONNECTED","분리암에서 연속 암반까지",
                 "같은 네 암괴에서 접합부만 바꾸었다. v03 암괴 면의 구조선을 유지하며, 접합부에는 별도의 면좌표를 썼다.",
                 (275,122),1,cards)


def ground_comparison(dense):
    old,_,_,field,veg_m=dense
    plant,new_m=regional_canopy("canopy_dense",old,field,311)
    color=vegetation_color("canopy_dense",field,"summer",veg_m["lod"],311)
    color=localize_color(color,field,new_m["regions"])
    rocks=[RockSpec("angular",48,71,42),RockSpec("layered",101,79,58,-.18),RockSpec("rounded",160,82,41)]
    v03,_,_=connected_formation("ground_rock",rocks,[],567)
    support0=[s for s in v03 if s.role=="rock_ground_color"]
    stable,body,meta=connected_formation("ground_rock",rocks,[0,1],567)
    footprint=basal_anchors(meta["rocks"],body)
    # Carry the original short v03 ground traces into the matched connected geometry.
    short=[p for s in support0 for p in project_clip(s,body.buffer(.34),6.2,"matched")]
    strong=ground_patch("ground_rock",footprint,"rock",489,body)
    green=ground_patch("ground_veg",root_anchors(veg_m["specimens"]),"vegetation",311)
    m=dict(veg_m,**new_m)
    cards=[Card("암괴 · 짧은 발치선","v03 선을 같은 연속 암반 아래에 배치",stable+short,"rock_ground_base",meta=meta),
           Card("암괴 · 연결된 지면색","같은 암반 · 발치에서 퍼지는 여러 층의 색선",stable+strong,"rock_ground_patch",meta=meta),
           Card("식생 · 수관색 기준","같은 수관색 · 뿌리 아래는 종이색",plant+color,"veg_ground_base",meta=m,field=field),
           Card("식생 · 뿌리 지면색","같은 수관 · 뿌리 위치에 따라 색이 모이고 풀림",plant+color+green,"veg_ground_patch",meta=m,field=field)]
    return Sheet("02_GROUND","같은 대상 아래의 지면색 비교",
                 "암괴와 식생을 고정했다. 지면색은 뿌리 위치와 암괴 발치에서 시작하는 실제 벡터 획이다.",
                 (198,124),2,cards)


def placed_vegetation():
    key="occlusion/trees"
    placed=[("U",11.5,92,42),("B",68,78,47),("W",111,83,56),("B",146,70,49),
            ("P",203,77,44),("W",252,83,45)]
    original=[];pads=[];logs=[]
    for i,(family,x,y,h) in enumerate(placed):
        owner=f"{key}/T{i}"
        p,q,m=specimen(owner,family,h,(x+15,y+7),lod="mid",seed=491+29*i,season="spring",seasonal=False)
        original.extend(p)
        pads.extend([(*pad,owner) for pad in q])
        logs.append(m)
    field=CanopyField(pads,logs)
    ink,meta=regional_canopy(key,original,field,491)
    color=vegetation_color(key,field,"spring","mid",491)
    color=localize_color(color,field,meta["regions"])
    return ink+color,field,logs,meta


def occlusion_comparison():
    specs=[RockSpec(s.shape,s.x+15,s.y+7,s.width,s.bedding) for s in ROCKS]
    p,solid,rocks=connected_formation("link_study",specs,[0,1,2],517)
    vegetation,field,trees,canopy=placed_vegetation()
    visible,rule=hide_behind_rock(vegetation,trees,solid)
    soil=ground_patch("occlusion/rock",basal_anchors(rocks["rocks"],solid),"rock",451,solid)
    background=terrain_fixture("occlusion/terrace",(6,38,286,124),448)
    background=[s for s in background if s.features["line_index"] in (2,5,9,12,15,19,22)]
    ground,_,_=protect_terrain(background,field,solid,(6,4,289,133))
    common=ground+soil+p
    meta=dict(rocks,roots=trees,occlusion=rule,**canopy)
    cards=[Card("대조 · 바위 위로 겹치는 나무","배치와 암반선을 고정한 채 겹치는 획을 모두 표시",
                common+vegetation,"occlusion_raw",meta=meta,field=field),
           Card("후보 · 암반이 나무를 가림","뒤쪽 수관만 위로 드러남 · 옆 개체는 독립적으로 읽힘",
                common+visible,"occlusion_clipped",meta=meta,field=field)]
    return Sheet("03_DEPTH","암반과 나무의 깊이 순서",
                 "암반 면 안에서 식생의 먹선과 색선을 함께 가렸다. 옆으로 열린 자리에서는 뿌리와 줄기가 보인다.",
                 (298,138),1,cards)


def canopy_comparison(partial,dense):
    cards=[]
    for key,title,item,seed in [("partial","부분 겹침",partial,174),("dense","밀집 혼합",dense,311)]:
        before,v03,_,field,m=item
        outline,geom=regional_canopy(f"canopy_{key}",before,field,seed)
        m=dict(m,**geom)
        cards += [Card(f"v03 · {title}", "개체 사이 연결 획을 녹색으로 표시",v03,f"{key}_v03",
                       "shared",m,field=field),
                  Card(f"v04 · {title}", "공유 영역에 새 잎 획을 배치 · 개별 줄기 유지",outline,f"{key}_v04",
                       "ink",m,field=field)]
    return Sheet("04_CANOPY","연결 획에서 공유 수관 영역으로",
                 "같은 B/W/P/U 개체의 먹선 비교. 부분·밀집 겹침에서 영역 안의 짧은 잎 획이 덩어리를 형성한다.",
                 (198,115),2,cards)


def detail_sheet(rock_page,canopy_page):
    _,b,c=rock_page.cards
    d,e=canopy_page.cards[-2:]
    rock_crop=(114,55,71,54)
    crowns=unary_union([Polygon(r["outer"],r["holes"]) for r in e.meta["regions"]])
    shape=max(crowns.geoms,key=lambda p:p.area) if crowns.geom_type=="MultiPolygon" else crowns
    x,y=shape.representative_point().coords[0]
    leaves=(x-33,y-18,66,41)
    return Sheet("05_DETAILS","접합부와 수관 겹침 확대",
                 "표시 크기를 고정해, 암반의 새 어깨 위를 지나는 층리와 수관 안에 흩어진 잎 획을 비교한다.",
                 (150,105),2,[
                  Card("암반 · 가운데 틈","부분 접합",b.paths,"detail_rock_gap","ink",b.meta,rock_crop),
                  Card("암반 · 어깨와 층리","연속 암반",c.paths,"detail_rock_join","ink",c.meta,rock_crop),
                  Card("수관 · v03 연결 획","부분 확대 · 녹색 표시선은 기존 연결 획",d.paths,"detail_canopy_v03","shared",d.meta,leaves,d.field),
                  Card("수관 · v04 영역 안의 잎","부분 확대 · 개별 줄기와 가지는 같은 위치",e.paths,"detail_canopy_v04","ink",e.meta,leaves,e.field)])


def assemble():
    partial,dense=studies()
    rock=rock_links()
    canopy=canopy_comparison(partial,dense)
    return [rock,ground_comparison(dense),occlusion_comparison(),canopy,detail_sheet(rock,canopy)]
