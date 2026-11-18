"""A portable Korean review of the v04 comparison plates."""
from base64 import b64encode
from html import escape
import json

from .geometry import ROOT
from .report_v03 import table

PLATES=[
    ("01_CONNECTED","암괴가 이어지는 방식","같은 암괴 네 개를 고정하고 분리, 부분 접합, 완전 연결을 비교했다. 어깨가 새로 생긴 곳에서는 묻히는 바깥선을 덜어내고, 양쪽 면의 방향을 받아 하나의 층리선을 통과시켰다. 아래쪽에는 끊긴 결이나 짧은 절리를 남겨 접합이 반복되는 느낌을 줄였다."),
    ("02_GROUND","암괴 발치와 뿌리 아래의 색","암반의 노출 면과 식생의 수관을 고정하고 바닥색의 차이만 비교했다. 암반에서는 발치 아래 색의 폭을 늘리고, 식생에서는 뿌리가 모인 곳에만 바닥색을 두었다. 두 포켓 사이는 종이색이 드러난다."),
    ("03_DEPTH","암반에 가려지는 나무","암반 앞에 선이 겹치는 대조와 암반 뒤쪽의 잎·가지·색을 가린 후보를 같은 배치로 비교했다. 다섯 개체의 수관은 암반 위와 틈으로 드러나고, 왼쪽 개체는 암반 옆에서 뿌리와 줄기가 보인다."),
    ("04_CANOPY","긴 연결 획과 공유 수관 영역","v03의 연결 획을 녹색으로 표시했다. v04에서는 두 개체 이상이 만나는 영역 안에 짧은 잎 획을 따로 배치하고, 개별 줄기와 가지를 유지했다. 수관색은 해당 영역에서 짧게 나누어 이어지는 녹색 띠를 줄였다."),
    ("05_DETAILS","접합과 수관의 확대","윗줄에서 층리 전후의 돌출부와 이어진 안쪽 면을 비교했다. 아랫줄에서는 같은 줄기·가지 위에 v03의 연결 획과 v04의 짧은 잎이 어떻게 달리 놓이는지 볼 수 있다."),
]


def measures():
    v=json.loads((ROOT/"audit/verification.json").read_text())
    g=v["ground"]
    occ=v["occlusion"]
    return v,{
        "01_CONNECTED": table(["시편","접합부","분리된 암반 성분"],[
            [n,l,c] for n,l,c in zip(["분리","부분 접합","완전 연결"],[0,2,3],v["rock_components"])]),
        "02_GROUND":table(["지면색 시편","기준 (mm)","후보 (mm)"],[
            ["암괴 발치",f"{g['rock_ground_color']:,.0f}",f"{g['rock_ground_patch']:,.0f}"],
            ["식생 뿌리","0",f"{g['vegetation_ground_patch']:,.0f}"],
        ]),
        "03_DEPTH":f"<p class='note'>암반 안을 지나던 식생 먹선·색선 {occ['inside_mm_before']:.0f} mm가 가림 뒤 {occ['inside_mm_after']:.0f} mm가 되었다. 암반과 바닥선은 두 장에서 같다.</p>",
        "04_CANOPY":table(["겹침","영역 안 먹선 길이 (mm)","전체 먹선 수","새 잎 획의 최장 길이 (mm)"],[
            [n,f"{d['total_in_area_before_mm']:,.0f} → {d['total_in_area_after_mm']:,.0f}",
             f"{d['ink_paths_before']} → {d['ink_paths_after']}",d["max_leaf_mm"]]
            for n,d in zip(["부분","밀집"],v["canopy"])
        ])+"<p class='note'>밀집 영역의 먹선 길이 밀도는 v03과 비슷하다. 짧은 잎으로 바꾸면서 전체 먹선이 늘었다. 종이 위에서는 짧은 획의 번짐과 반복 접촉도 함께 확인해야 한다.</p>"
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
    <h1>프로시저럴 카탈로그 v04</h1>
    <p>암반 사이에 층리와 접합면을 만들고, 발치와 뿌리 아래 색을 보강했다. 뒤쪽 나무는 암반에 가려지며, 겹친 수관은 짧은 잎 획이 모인 영역으로 처리했다.</p>
    <p><strong>추천</strong>은 지형을 이루는 연속 암반, 통로를 남기는 부분 접합, 암반 뒤 또는 옆 수관이다. 앞뒤가 읽히는 곳에서 뿌리색의 위치와 잎 획의 간격을 비교한다.</p></header>
    """
    text=("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' "
          "content='width=device-width, initial-scale=1'><title>Datascape 프로시저럴 카탈로그 v04</title>"
          f"<style>{style}</style><main>{intro}<nav aria-label='도판'>{''.join(links)}</nav>"
          f"{''.join(parts)}<footer>재현 검증 · 도판 {audit['sheets']}장 · 벡터 예시 {audit['cards']}종. "
          "안료 발색과 실제 붓 접촉은 실물 시편 검토 항목이다.</footer></main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v04_REVIEW_KO.html").write_text(text,encoding="utf-8")


if __name__=="__main__":
    build()
