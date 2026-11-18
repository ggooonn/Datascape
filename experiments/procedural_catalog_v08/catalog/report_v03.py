"""Create a standalone Korean catalog review using the vector-derived previews."""
from base64 import b64encode
from html import escape
import json

from .geometry import ROOT


SECTIONS=[
    ("01_CANOPY","식생 겹침 전후","B와 W의 고립 상태에서는 원래 수관을 그대로 썼다. 부분 겹침에는 연결이 필요한 곳만 잇고, 밀집 군집에서는 획 길이 상한과 생략을 적용했다."),
    ("02_VEGETATION_COLOR","식생의 공유 색 영역","색과 먹을 분리해 보면 개별 줄기를 넘어 이어지는 색의 덩어리가 드러난다. 좁은 연결부 위아래에는 빈 공간이 남고, 보조층은 겹침이 강한 구역에만 들어간다."),
    ("03_SURFACES","암괴 외곽과 면별 준법","v02 외곽 8종을 사용했다. 긴 구조선은 면 방향을 따라가고, 절리와 국부 표면선은 다른 방향이나 짧은 간격으로 한쪽에 모인다. 면마다 색이 비어 있는 부분이 남는다."),
    ("04_SURFACE_CONTROL","같은 외곽의 먹선 전후","직립형은 세로 결이 면의 높이를 드러내고, 둥근형은 완만한 휨이 표면을 묶는다. 층상형은 길이와 간격이 달라지면서 얇은 면과 덩어리의 차이가 생긴다."),
    ("05_FORMATIONS","암괴군 네 가지 구성","연속 주암에서는 네 큰 덩어리의 교대가 보인다. 큰 주암 안에서는 작은 파편을 외곽에 두고, 중간 크기군은 비슷한 크기의 앞뒤 겹침을 강조했다. 넓은 형성체는 열 개 군이 바닥선을 공유한다."),
    ("06_ROCK_COLOR","암괴 면과 바닥의 색","면 먹선과 같은 좌표에서 회색·황토·갈색·회녹을 놓았다. 색은 면 테두리 전체를 균일하게 채우지 않고, 발치와 이웃 암괴 사이로 부분적으로 이어진다."),
    ("07_MASK","식생·암괴와 지형의 가림","수관 코어에는 필요한 연묵 통과선만 남겼다. 암괴 외곽에서는 뒤쪽 지형선을 잘라내고 경계 바깥에서 점별 압력을 회복시켰다."),
    ("08_VECTOR_DETAIL","수관과 암괴 접점의 확대","녹색 먹선은 공유 획을 식별하기 위한 표시다. 첫 행은 교차와 간격, 둘째 행은 수관과 바위 뒤로 지형이 사라졌다가 다시 이어지는 부분을 같은 크기로 비교한다."),
    ("09_DISTANCE","근·중·원경에 따른 획 예산","기존 골격의 거리별 차이와 새로운 색선의 간격을 함께 확인한다. 원경에서는 잎 덩어리 사이의 가는 간격이 더 넓어지고 보조 색층이 줄어든다."),
]


def table(header, rows):
    labels="".join(f"<th scope='col'>{escape(label)}</th>" for label in header)
    items="".join("<tr>"+"".join(f"<td>{escape(str(v))}</td>" for v in row)+"</tr>" for row in rows)
    return f"<div class='table'><table><thead><tr>{labels}</tr></thead><tbody>{items}</tbody></table></div>"


def measures():
    a={d["key"]:d for d in json.loads((ROOT/"audit/path_metrics.json").read_text())}
    verified=json.loads((ROOT/"audit/verification.json").read_text())
    crowns=[]
    steps=[]
    for label,key in [("부분 겹침","partial"),("밀집 혼합","dense")]:
        old,new=[a[f"{key}_{v}"] for v in ("v02","v03")]
        x,y=old["canopy"],new["canopy"]
        crowns.append([label,f"{x['canopy_paths']} → {y['canopy_paths']}",
                       f"{x['canopy_mm']:,.0f} → {y['canopy_mm']:,.0f}",
                       f"{x['crossing_pairs']} → {y['crossing_pairs']}",
                       f"{x['overlap_cell_max_mm']:.2f} → {y['overlap_cell_max_mm']:.2f}",
                       y["shared_paths"]])
        steps.append([label,y["baseline_y_near_pairs"],y["scheduled_near_pairs"],
                      f"{old['interpath_air_mm']:,.0f} → {new['interpath_air_mm']:,.0f}"])
    sections={
        "01_CANOPY": table(["조건","수관 먹선 (획)","수관 먹선 길이 (mm)","교차 (쌍)",
                            "4.5 mm 겹침 셀의 최대 먹선 (mm)","v03 공유 획"],crowns)
        +table(["v03 순서 비교","Y순의 근접 연속쌍","후보 순서의 근접 연속쌍",
                "v02 → v03 같은 먹 단계 내 붓 든 거리 (mm)"],steps)
        +"<p class='small'>근접 연속쌍은 같은 먹 단계의 인접 두 수관선이 모두 겹침 영역을 지나고 두 중심선 사이가 3.2 mm 미만인 경우다. 붓 든 거리는 단계와 색별 순서를 유지해 획 끝과 다음 획 시작 사이의 직선을 합했다.</p>",
        "02_VEGETATION_COLOR":
            f"<p class='small'>밀집 색선 {a['vegetation_color']['paths']}획 · 총 {a['vegetation_color']['mm']:,.0f} mm. "
            f"{a['vegetation_color']['canopy']['shared_color_paths']}획은 길이 샘플의 30% 이상이 여러 수관의 겹침 영역에 놓인다.</p>",
    }
    formations=[]
    for key,label,width in [("serial","연속 주암","주요 암괴 31–44 mm"),("anchor","큰 주암+파편","66 mm / 7.5–13 mm"),
                            ("medium","중간 크기군","22–31 mm"),("field","넓은 형성체","10개 군 · 총 34개")]:
        m=a[key]
        formations.append([label,width,m["paths"],f"{m['mm']:,.0f}",m["short_under_6mm"]])
    sections["05_FORMATIONS"]=table(["구성","크기 관계","먹+색 (획)","총 길이 (mm)","6 mm 미만 (획)"],formations)
    rows=[]
    for key,label in [("vegetation","밀집 수관 색"),("rock","층상 암괴와 바닥 색")]:
        m=a[f"{key}_color"]
        rows.append([label,m["paths"],f"{m['mm']:,.0f}",m["middle_mm"],len(m["materials"]["COLOR"]["pigments"])])
    sections["06_ROCK_COLOR"]=table(["색선 시편","획","길이 (mm)","획 길이 중앙값 (mm)","표시색 수"],rows)
    sections["07_MASK"]=table(["처리","지형선 (획)","지형선 길이 (mm)","중심부 통과"],[
        ["가림 전",25,"4,526","그대로 통과"],
        ["가림 후",37,"4,191","연묵 1/0 · 중묵 0"],
    ])+"<p class='small'>가림 이후 총 길이는 줄었지만 지형 조각이 늘었다. 실제 접촉 횟수와 재보충·세척 시간은 플로터에서 별도 검증한다.</p>"
    vals=verified["season_smoke_test"]
    sections["09_DISTANCE"]=table(["계절","같은 위치의 먹선 (획)","수관 색선 (획)"],[
        [label,vals[season]["ink"],vals[season]["color"]]
        for season,label in [("spring","봄"),("summer","여름"),("autumn","가을"),("winter","겨울")]
    ])+"<p class='small'>표는 동일 개체의 사계절 재사용 검증 시편이다. 겨울에는 잔잎에만 낮은 강도의 한 겹을 사용했다.</p>"
    return sections, verified


def build():
    details,audit=measures()
    navigation=[]
    sections=[]
    for key,title,note in SECTIONS:
        anchor=f"s{key[:2]}"
        img=b64encode((ROOT/"review"/f"{key}.png").read_bytes()).decode()
        navigation.append(f"<a href='#{anchor}'>{escape(title)}</a>")
        sections.append(f"<section id='{anchor}'><h2>{escape(title)}</h2><p>{escape(note)}</p>"
                        f"<figure><img loading='lazy' alt='{escape(title,quote=True)} 비교 도판' "
                        f"src='data:image/png;base64,{img}'></figure>{details.get(key,'')}</section>")
    css="""
    :root{--paper:#faf7ed;--ink:#27372e;--mute:#55675c;--line:#d7d6c9;--warm:#efede1}
    *{box-sizing:border-box}
    body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.67 'Noto Sans CJK KR','Apple SD Gothic Neo',sans-serif}
    main{max-width:1260px;margin:auto;padding:42px 26px 68px}
    h1{margin:7px 0 15px;font-size:clamp(32px,5vw,56px);line-height:1.15;letter-spacing:-.07em}
    h2{font-size:27px;letter-spacing:-.055em;margin:0 0 8px}
    p{margin:0 0 14px;max-width:84ch}
    .date{font-size:13px;color:var(--mute);letter-spacing:.1em}
    .small{font-size:14px;color:var(--mute);margin:10px 0 0}
    a{color:#355d4b;text-underline-offset:3px}
    nav{display:flex;flex-wrap:wrap;gap:8px 18px;border-block:1px solid var(--line);padding:13px 0;margin:29px 0}
    section{border-bottom:1px solid var(--line);padding:6px 0 27px;margin-bottom:23px;scroll-margin-top:16px}
    figure{margin:0}
    img{border:1px solid var(--line);display:block;width:100%;height:auto}
    .table{overflow:auto}
    table{border-collapse:collapse;width:100%;font-size:14px;margin-top:12px}
    td,th{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
    th{background:var(--warm)}
    footer{color:var(--mute);font-size:14px}
    @media(max-width:650px){main{padding:25px 12px 40px}td,th{font-size:12px;padding:5px}}
    """
    header="""
    <header><div class='date'>DATASCAPE · 2026-11-18</div>
    <h1>프로시저럴 카탈로그 v03</h1>
    <p>수관은 줄기와 가지 위에서 여러 개체가 한 덩어리로 연결되고, 암괴는 같은 외곽 안에서 면마다 다른 결을 얻는다. 색선은 먹선과 같은 수관·면 좌표에서 생성했다.</p>
    <p>참고 이미지의 세 화면에서 지면과 종이색, 서로 이어지는 잎 덩어리, 직립 암벽의 세로 결, 회녹이 도는 원경을 관찰했다. 이를 공유 수관색, 면을 따르는 먹선·색선, 열어 둔 바닥에 반영했다.</p>
    <p><strong>추천 시편</strong>은 밀집 혼합 INK + COLOR와 층상 주암·작은 파편이다. 밀집 수관의 색선 간격과 암괴 발치의 색이 종이에서 어떻게 이어지는지가 후속 검토의 기준이다.</p></header>
    """
    footer=(f"<footer>재현 검증 · 도판 {audit['sheets']}장 · 벡터 예시 {audit['states']}종 · 획 기록 "
            f"{audit['stroke_records']:,}개. 시편 색상과 선폭은 화면 비교용이다. 물리 발색, "
            "먹 번짐, 마른 뒤의 겹침 정도는 실물 시편에서 검증한다.</footer>")
    html=("<!doctype html><html lang='ko'><meta charset='utf-8'>"
          "<meta name='viewport' content='width=device-width, initial-scale=1'>"
          "<title>Datascape 프로시저럴 카탈로그 v03</title>"
          f"<style>{css}</style><main>{header}<nav aria-label='도판 목록'>{''.join(navigation)}</nav>"
          f"{''.join(sections)}{footer}</main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v03_REVIEW_KO.html").write_text(html,encoding="utf-8")


if __name__=="__main__":
    build()
