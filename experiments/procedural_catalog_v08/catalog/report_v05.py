"""A portable Korean review of the v05 overlap comparisons."""
from base64 import b64encode
from html import escape
import json

from .geometry import ROOT
from .report_v03 import table

PLATES=[
    ("01_ROCK_GROUP","같은 네 암괴의 구성 비교",
     "분리암과 v04 부분 접합을 기준으로, v05에서는 각진암·층상암·직립암·둥근암을 앞뒤로 포갰다. 뒤쪽 구조선은 앞 암괴의 외곽에서 끊긴다."),
    ("02_DEPTH","앞뒤를 뒤집어 본 같은 두 암괴",
     "같은 좌표에서 층상암이 앞일 때와 각진암이 앞일 때를 비교했다. 확대 도판에서 뒤쪽 사면의 먹선과 색선이 앞쪽 경계에 닿아 끝나는 지점을 볼 수 있다."),
    ("03_GROUND","발치와 뿌리의 짧은 지면색",
     "여섯 암괴의 앞쪽 발치와 식생의 가까운 뿌리만 받쳤다. 옅은 A선의 기울기 일부를 참고해 지면색을 거의 수평으로 놓고, 뿌리 사이의 빈 공간을 열어 두었다."),
    ("04_CANOPY","v04 공유 수관과 세 그루 겹침",
     "원래 줄기와 가지 위에 공유 영역의 짧은 잎 획을 놓았다. 세 그루 시편은 같은 위치에서 전후를 비교했다. 기존 좌표와 압력을 재현한 밀집 시편은 겹침 부위를 확대했다."),
]


def measures():
    v=json.loads((ROOT/"audit/verification.json").read_text())
    pair=v["pair"]
    ground=v["ground"]
    crown=v["canopy"]
    return v,{
        "01_ROCK_GROUP":f"<p class='note'>네 암괴가 겹친 시편에서 가려진 뒤쪽 선의 총 길이는 {v['group_hidden_mm']:.2f} mm다.</p>",
        "02_DEPTH":table(["앞 암괴","가려진 뒤쪽 선 (mm)","완전히 가려진 뒤쪽 획"],
           [[name,record["hidden_mm"],record["hidden_whole"]] for name,record in
            [("층상암",pair["pair_layered_front"]),("각진암",pair["pair_angular_front"])]])
           +"<p class='note'>앞 암괴의 경로는 두 경우 모두 원래 좌표를 유지했다. 가림 때문에 짧은 조각이 사라지거나, 한 획의 앞뒤가 두 구간으로 나눠 보일 수 있다.</p>",
        "03_GROUND":table(["색 띠","획","경로 길이 (mm)","최대 국소 기울기"],
           [[name,d["paths"],f"{d['length_mm']:.1f}",f"{d['max_deg']:.2f}°"] for name,d in
            [("암괴 발치",ground["rock_ground_band"]),("식생 뿌리",ground["root_ground_band"])]])
           +"<p class='note'>가까운 A선 기울기의 17%를 기준에 반영했다. 실제 색의 농도와 번짐은 이 도판의 선 길이로 판단할 수 없다.</p>",
        "04_CANOPY":f"<p class='note'>세 그루의 겹침 영역 안에서 먹선은 {crown['shared_mm_before']:.0f}→{crown['shared_mm_after']:.0f} mm였다. v04 밀집 시편 327획은 좌표와 압력까지 그대로 재현했다.</p>",
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
    <header><div class='date'>DATASCAPE · 2026-11-18</div>
    <h1>프로시저럴 카탈로그 v05</h1>
    <p>앞 암괴의 외곽이 뒤 암괴의 표면을 가린다. 개별 암괴는 제 형상과 면의 결을 유지하고, 겹쳐 놓인 배치가 암괴군의 덩어리를 만든다.</p>
    <p><strong>검토 순서</strong>는 두 암괴의 동일 배치 가림 비교, 여섯 암괴의 전체 구성, 지면색 순이다. 지면색은 발치와 뿌리를 받치는 얕은 띠로 배치했다.</p></header>
    """
    text=("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' "
          "content='width=device-width, initial-scale=1'><title>Datascape 프로시저럴 카탈로그 v05</title>"
          f"<style>{style}</style><main>{intro}<nav aria-label='도판'>{''.join(links)}</nav>"
          f"{''.join(parts)}<footer>벡터 검증 · 도판 {audit['sheets']}장 · 예시 {audit['cards']}종. "
          "안료 발색과 붓 접촉은 실물 시편 검토 항목이다.</footer></main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v05_REVIEW_KO.html").write_text(text,encoding="utf-8")


if __name__=="__main__":
    build()
