"""Korean v07 comparison report with fixed v06 geometry and contact diagnostics."""
from base64 import b64encode
from html import escape
import json

from .geometry import ROOT
from .report_v03 import table

PLATES=[
    ("01_COMPARISON","같은 장면의 지면색 전후",
     "두 장면의 암괴, 식생과 A선은 v06의 같은 벡터다. v07에서는 뿌리와 바위 발치가 닿는 곳에 짧은 획을 놓아 서로 다른 깊이가 드러나도록 했다."),
    ("02_ROOTS","나무별 뿌리 위치와 색 띠",
     "원은 줄기가 땅에 닿는 지점이다. 왼쪽과 오른쪽 포켓 안에서 각각 앞뒤로 놓인 네 뿌리의 화면 Y가 다르다. 뿌리마다 첫 색 띠의 높이도 달라진다."),
    ("03_ROCKS","겹친 암괴의 가시 발치",
     "열한 암괴의 원래 외곽을 보존했다. 각 암괴 하단에서 앞 암괴에 가려진 구간을 제외한 뒤, 드러난 발치에만 색선을 배치했다."),
    ("04_DETAILS","짧은 겹침과 가림 확대",
     "위는 높이와 색이 가까운 두 획을 한 획으로 정리한 전후다. 아래는 가림을 적용하기 전 후보와 최종 경로다. 열린 원은 가시 접지점, ×는 가려진 발치다."),
]


def measures():
    v=json.loads((ROOT/"audit/verification.json").read_text())
    old=v["baseline_ground"]
    site=v["site"]
    rock=v["formation"]
    return v,{
        "01_COMPARISON":table(["조건","지면색 획","합산 길이 (mm)"],[
            ["v06",old["strokes"],f"{old['length_mm']:.2f}"],
            ["v07",site["strokes"],f"{site['length_mm']:.2f}"],
          ])+f"<p class='note'>지면색을 제외한 {v['unchanged_site_strokes']}획은 v06 원본과 일치한다.</p>",
        "02_ROOTS":f"<p class='note'>앞뒤 뿌리 {site['roots']}곳을 개별로 처리했다. 접지점의 높이는 v06의 합성 A선을 따라 보간한 상대 높이다. 이 깊이·높이 좌표를 도면 XY로 투영하고, 가까운 A선 기울기를 약하게 반영했다.</p>",
        "03_ROCKS":table(["시편","지면색이 있는 암괴","가려지거나 좁은 발치에서 제외한 후보"],[
            ["뿌리·발치 장면",site["painted_rock_objects"],site["candidate_bands_rejected"]],
            ["열한 암괴",rock["painted_rock_objects"],rock["candidate_bands_rejected"]],
          ]),
        "04_DETAILS":f"<p class='note'>뿌리 사이에서 두 획을 하나로 이었다. 새 지면색의 최대 국소 기울기는 {site['maximum_slope_deg']:.2f}°이며, 가림 뒤에는 암괴 안을 지나가는 지면색을 검증 허용오차 안에서 0 mm로 확인했다.</p>",
    }


def build():
    audit,metrics=measures()
    parts=[]
    links=[]
    for file,title,note in PLATES:
        tag="s"+file[:2]
        png=b64encode((ROOT/"review"/f"{file}.png").read_bytes()).decode()
        links.append(f"<a href='#{tag}'>{escape(title)}</a>")
        parts.append(f"<section id='{tag}'><h2>{escape(title)}</h2><p>{escape(note)}</p>"
                     f"<img loading='lazy' alt='{escape(title,quote=True)} 도판' src='data:image/png;base64,{png}'>"
                     f"{metrics.get(file,'')}</section>")
    style="""
    :root{--paper:#faf7ed;--ink:#27372e;--muted:#52665b;--border:#d8d7c9}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
      font:16px/1.66 'Noto Sans CJK KR','Apple SD Gothic Neo',sans-serif}
    main{max-width:1050px;margin:auto;padding:37px 21px 67px}
    h1{font-size:clamp(34px,6vw,54px);line-height:1.15;letter-spacing:-.06em;margin:6px 0 14px}
    h2{line-height:1.30;letter-spacing:-.04em;margin:0 0 7px}
    p{max-width:80ch;margin:0 0 12px}
    .date,.note,footer{color:var(--muted);font-size:14px}.note{margin:12px 0}
    nav{display:flex;gap:8px 18px;flex-wrap:wrap;border-block:1px solid var(--border);
      margin:23px 0 27px;padding:10px 0}
    a{color:#335f4a;text-underline-offset:3px}
    section{padding-bottom:23px;margin-bottom:23px;border-bottom:1px solid var(--border);scroll-margin-top:10px}
    img{width:100%;display:block;border:1px solid var(--border)}
    table{border-collapse:collapse;width:100%;font-size:14px;margin:13px 0 4px}
    td,th{text-align:left;border-bottom:1px solid var(--border);padding:6px 8px}
    th{background:#efede1}.table{overflow:auto}
    @media(max-width:600px){main{padding:24px 12px 42px}td,th{font-size:12px;padding:5px 4px}}
    """
    intro="""
    <header><div class='date'>DATASCAPE · 2026-11-19</div>
    <h1>프로시저럴 카탈로그 v07</h1>
    <p>나무마다 뿌리점 아래에, 암괴마다 보이는 발치에 짧은 지면색을 붙였다. v06의 같은 배치를 고정해 색 띠만 옮겼을 때의 차이를 볼 수 있다.</p>
    <p><strong>확인 순서</strong>는 전체 전후 비교, 앞뒤 뿌리의 확대, 암괴 발치, 겹침과 가림 세부 순이다.</p></header>
    """
    text=("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' "
          "content='width=device-width, initial-scale=1'><title>Datascape 프로시저럴 카탈로그 v07</title>"
          f"<style>{style}</style><main>{intro}<nav aria-label='도판'>{''.join(links)}</nav>"
          f"{''.join(parts)}<footer>벡터 검증 · 도판 {audit['sheets']}장 · 예시 {audit['cards']}종. "
          "안료 발색과 붓 접촉은 실물 시편 검토 항목이다.</footer></main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v07_REVIEW_KO.html").write_text(text,encoding="utf-8")


if __name__=="__main__":
    build()
