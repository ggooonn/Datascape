"""Generate a self-contained Korean review from the exported catalog measurements."""
from base64 import b64encode
from collections import Counter
from html import escape
import gzip
import json

from .geometry import ROOT

SECTIONS = [
    ("01_BW", "B/W 고립 표본", "두 시드에서 모두 B의 완만한 활꼴과 W의 내려앉는 끝을 구분했다. 골격과 폭 비교 조건은 같다."),
    ("02_BW_LOD", "B/W 근·중·원경", "같은 10 mm 축척을 썼다. 거리 단계가 멀어질수록 가지와 수관선 수를 줄였다."),
    ("03_BW_MIX", "같은 배치의 B/W 혼합군", "위치, 크기, 골격과 가림 조건을 고정했다. 의도적으로 비운 수관 부분과 획 사이 간격을 비교할 수 있다."),
    ("04_CLUSTERS", "X/Y 군집과 깊이", "아래 점은 뿌리 위치와 상대 크기다. 집중안은 포켓 내부가 짙고 성긴안은 열린 통로가 넓다. 전후안은 뒤층과 앞층의 줄기 위치와 크기가 가장 잘 구분된다."),
    ("05_ROCK_FORMS", "암괴 실루엣 8종", "같은 기준 폭 45 mm의 여덟 외곽이다. 직립·뾰족형은 높이에서, 층상·기반암은 단차와 바닥 노출에서 차이가 난다. 내부 층리, 절리, 풍화 곡선은 면에 따라 나뉜다."),
    ("06_ROCK_GROUPS", "주암과 종속암", "층상 주암과 작은 지지암은 무게중심이 분명하다. 직립군은 수직 대비에, 노출 기반암군은 낮고 넓은 바닥에 적합하다."),
    ("07_ROCK_FORMATION", "10개 암괴군", "39개 암괴에 공통 층리 방향을 주고, 군의 크기와 높이, 지지암 조합과 사이의 빈 구역을 바꿨다."),
    ("08_MASK", "수관 아래 지형 가림", "세 코어의 같은 위치를 비교했다. 녹색은 연결 코어, 색 선은 통과 지형선이다. 경계 밖에서는 선폭으로 상대 감쇠를 표시했다."),
    ("09_SAME_SITE", "동일 개체의 계절 변화", "봄의 새순, 여름의 연결된 수관과 하층, 가을의 분리된 잎 덩이와 마른 초본을 비교한다. 겨울은 줄기 외에 노출 잔가지, P 잔잎, 드러난 바닥이 형태를 만든다."),
    ("10_COMMUNITIES", "계절별 독립 군집", "봄·여름·가을·겨울에 다른 개체 조합과 위치를 사용했다. 여름 포켓은 서로 겹치고, 겨울은 상록 역할 P와 열린 바닥을 남겼다."),
    ("11_ROCK_LOD", "암괴 근·중·원경", "층상 주암과 같은 지지암 조합을 82·52·29 mm에서 비교했다. 원경에서는 작은 절리와 면선 수를 줄였다."),
]


def table(headers, values):
    head = "".join(f"<th scope='col'>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in values)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def compare(a, b, field, n=None):
    if n is None:
        return f"{a[field]} → {b[field]}"
    return f"{a[field]:.{n}f} → {b[field]:.{n}f}"


def build():
    rows = {r["key"]: r for r in json.loads((ROOT/"audit/metrics.json").read_text())}
    verified = json.loads((ROOT/"audit/verification.json").read_text())

    bw = []
    for series, i, label in [("01_BW",1,"B · seed 17"),("01_BW",3,"W · seed 17"),
                              ("01_BW",5,"B · seed 121"),("01_BW",7,"W · seed 121"),
                              ("03_BW_MIX",1,"B/W 혼합 · seed 108")]:
        a,b = (rows[f"{series}__{j:02}"] for j in (i,i+1))
        bw.append([label,compare(a,b,"canopy_count"),compare(a,b,"median_canopy_mm",2),
                    compare(a,b,"canopy_p95_turn_deg",2),compare(a,b,"canopy_pairs_crossing")])
    details = {
        "01_BW": table(["조건","수관선 (획)","길이 중앙값 (mm)","방향 변화 95백분위 (°)","교차 (쌍)"],bw)
                 + "<p class='note'>수관선을 0.9 mm 간격으로 다시 표본화하여 연속 선분의 방향 변화량을 계산했다. 교차는 서로 교차하는 중심선 쌍이며 실제 종이 위에서 번지는 면적과 다르다.</p>",
        "04_CLUSTERS": table(["배치","뿌리 Y 폭 (mm)","개체별 최근접 거리 범위 (mm)","깊이 감쇠가 확인된 수관선"],[
            [r["label"],r["root_y_span_mm"],f"{r['root_nearest_min_mm']:.2f}–{r['root_nearest_max_mm']:.2f}",r["depth_masked_canopy"]]
            for r in rows.values() if r["key"].startswith("04_")]),
    }
    mask=[]
    for i in (1,2,3):
        with gzip.open(ROOT/"vectors"/f"08_MASK__{i:02}.json.gz","rt") as f:
            data=json.load(f)
        t=data["metadata"]["terrain"]
        by_core = [f"{r['LIGHT']} / {r['MEDIUM']}" for r in t] if isinstance(t,list) else [
            f"{len(r['kept'])} / 0" for r in t["cores"]]
        terrain = [s for s in data["strokes"] if s["role"] == "terrain_A"]
        mask.append([data["label"],*by_core,len(terrain)])
    details["08_MASK"]=table(["처리","코어 1 LIGHT / MEDIUM","코어 2 LIGHT / MEDIUM",
                              "코어 3 LIGHT / MEDIUM","도판 전체 지형 경로 (개)"],mask) + (
        "<p class='note'>v02는 도판의 세 코어에 각각 연묵 1획을 남겼다. 지형 길이는 "
        f"{t['input_length_mm']:,.0f} → {t['output_length_mm']:,.0f} mm로 줄었으나 바깥쪽 조각이 늘었다. "
        "5.2 mm 미만 조각은 제거했다. 같은 깊이대에서 식생끼리 겹치는 부분은 약하게 감쇠하며 자르지 않는다.</p>"
    )
    for k in ("09_SAME_SITE","10_COMMUNITIES"):
        season_rows=[]
        for i in range(1,5):
            key=f"{k}__{i:02}"
            with gzip.open(ROOT/"vectors"/f"{key}.json.gz","rt") as f:
                v=json.load(f)
            c=Counter(s["role"] for s in v["strokes"])
            season_rows.append([v["label"],len(v["metadata"]["specimens"]),c["canopy"],
                                v["metadata"]["understory_count"],c["winter_twig"],c["terrain_A"]])
        details[k]=table(["계절","개체","수관선","하층선","노출 잔가지","지형 경로"],season_rows)

    sections=[]
    links=[]
    for key,title,caption in SECTIONS:
        data=b64encode((ROOT/"review"/f"{key}.png").read_bytes()).decode()
        sec=key[:2]
        links.append(f"<a href='#s{sec}'>{escape(title)}</a>")
        sections.append(f"<section id='s{sec}'><h2>{escape(title)}</h2><p>{escape(caption)}</p>"
                        f"<figure><img loading='lazy' alt='{escape(title,quote=True)} 비교 도판' "
                        f"src='data:image/png;base64,{data}'></figure>{details.get(key,'')}</section>")
    style = """
    :root {--paper:#faf7ed;--ink:#28372d;--muted:#596a5d;--rule:#d6d6c9;--accent:#335e4c}
    body {margin:0;background:var(--paper);color:var(--ink);
          font:16px/1.65 'Noto Sans CJK KR','Apple SD Gothic Neo',sans-serif}
    main {max-width:1170px;box-sizing:border-box;padding:42px 22px 72px;margin:auto}
    h1 {font-size:clamp(32px,5vw,56px);line-height:1.15;margin:8px 0 16px;letter-spacing:-.06em}
    h2 {font-size:29px;letter-spacing:-.055em;margin:0 0 6px}
    .kicker {letter-spacing:.14em;text-transform:uppercase;font-size:13px;color:var(--muted)}
    p {margin:6px 0 18px;max-width:82ch} .note {font-size:14px;color:var(--muted);margin:10px 0 0}
    nav {display:flex;gap:8px 17px;flex-wrap:wrap;border-block:1px solid var(--rule);padding:12px 0;margin:27px 0}
    a {color:var(--accent);text-underline-offset:3px}
    section {border-top:1px solid var(--rule);padding:25px 0 35px;scroll-margin-top:16px}
    figure {margin:0} img {width:100%;height:auto;display:block;border:1px solid var(--rule);box-sizing:border-box}
    table {border-collapse:collapse;font-size:14px;width:100%;margin-top:12px}
    td,th {text-align:left;padding:7px 8px;border-bottom:1px solid var(--rule)}
    th {background:#efeee2} footer {color:var(--muted);font-size:14px;border-top:1px solid var(--rule);padding-top:17px}
    @media(max-width:600px) {main{padding:24px 12px 38px} td,th{font-size:12px;padding:5px 4px}}
    """
    header = """
    <header><div class="kicker">Datascape · 2026-11-18</div>
    <h1>프로시저럴 카탈로그 v02</h1>
    <p>완만해진 B/W 수관, 평면의 군집, 여덟 암괴 외곽을 비교했다. 수관 코어의 지형선 상한을 검증하고, 같은 개체의 계절 변화와 계절별 독립 군집을 각각 구성했다.</p>
    <p><strong>권장 조합</strong>은 B/W 혼합 v02, 깊이형 군집, 층상 주암과 작은 지지암, 코어당 연묵 한 획 상한이다. 계절 비교에는 먼저 같은 장소와 같은 개체를 사용한다.</p></header>
    """
    footer = (f"<footer>검증 결과 · 도판 {verified['sheet_count']}장, 벡터 예시 {verified['states']}종, "
              f"획 기록 {verified['strokes']:,}건. 동일 개체의 줄기·가지 {verified['same_site_woody_paths']}획이 "
              "모든 계절에 일치한다. 예시는 합성 자료이며 종이에서의 번짐, 선폭, 가림 후 발색은 실물 확인이 필요하다.</footer>")
    html = ("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width, initial-scale=1'><title>Datascape 프로시저럴 카탈로그 v02</title>"
            f"<style>{style}</style><main>{header}<nav aria-label='도판 목록'>{''.join(links)}</nav>"
            f"{''.join(sections)}{footer}</main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v02_REVIEW_KO.html").write_text(html,encoding="utf-8")


if __name__ == "__main__":
    build()
