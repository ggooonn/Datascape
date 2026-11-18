"""A portable Korean review of the v06 related-rock studies."""
from base64 import b64encode
from html import escape
import json

from .geometry import ROOT
from .report_v03 import table

PLATES=[
    ("01_FAMILIES","같은 배치에서 보는 세 계열",
     "여섯 자리와 폭을 고정했다. 층상군의 낮은 단차, 절리군의 기울어진 면, 풍화형의 둥근 외곽에 맞춰 결을 정했다. 같은 계열에서도 각 면과 바깥 윤곽에는 개체 차이가 남는다."),
    ("02_MASSING","같은 층상 계열의 네 가지 구성",
     "큰 주암과 작은 받침암, 큰 암괴가 이어지는 배치, 비슷한 폭의 중간 암괴군, 여러 층이 포개진 열한 암괴를 비교했다. 다층형은 깊이가 뚜렷하고, 일부 뒤 암괴의 가시 면적은 크게 줄었다."),
    ("03_OVERLAP","절리군의 느슨한 겹침과 강한 겹침",
     "폭과 시드, 깊이의 순서를 고정하고 좌우 간격만 좁혔다. 아래 확대에서는 앞 암괴의 외곽을 경계로 뒤쪽 먹선과 색선이 사라지는 지점이 보인다."),
    ("04_ROOT_GROUND","발치색과 공유 수관",
     "같은 장면에서 첫 비교는 색 띠의 폭만 늘린다. 두 번째 비교는 색 띠가 넓어진 상태에서 공유 영역 둘레의 짧은 개별 잎을 줄인다. 오른쪽 아래에 발치와 뿌리 수관을 확대했다."),
]


def measures():
    v=json.loads((ROOT/"audit/verification.json").read_text())
    mass=v["masses"]
    oc=v["overlap"]
    roots=v["root_ground"]
    axis=v["families"]
    return v,{
        "01_FAMILIES":table(["계열","앞면 U축의 측정 범위"],[
           [label,f"{axis[key]['front_min']:.2f}° ~ {axis[key]['front_max']:.2f}°"]
           for key,label in [("strata","층상군"),("jointed","절리군"),("weathered","풍화형")]])
           +"<p class='note'>면에서 결이 이어지는 기본 방향을 화면 수평을 기준으로 쟀다. 열거한 종류는 카탈로그에서 사용하는 조형 계열이다.</p>",
        "02_MASSING":table(["구성","암괴 수","폭 범위 (mm)","개별 최대 가림 면적"],
          [[label,mass[k]["n"],f"{mass[k]['width_min']:.0f}–{mass[k]['width_max']:.0f}",
          f"{mass[k]['max_percent']:.1f}%"] for k,label in [("anchor","주암과 받침암"),
            ("sequence","큰 암괴의 연속"),("medium","중간 암괴군"),("formation","다층 암반")]]),
        "03_OVERLAP":table(["배치","겹치는 쌍","개별 최대 가림 면적","가려진 먹선·색선 (mm)"],[
          [label,d["pairs"],f"{d['max_percent']:.1f}%",f"{d['hidden_mm']:.1f}"]
          for label,d in [("느슨한 배치",oc["loose"]),("집중된 배치",oc["strong"])]])
          +"<p class='note'>최대 가림 면적은 개별 암괴 중 가장 많이 가려진 비율이다. 밀집 시편의 가림을 푼 도판에서도 각 암괴의 원래 외곽이 확인된다.</p>",
        "04_ROOT_GROUND":
          f"<p class='note'>색 띠 {roots['bands']}획 · 길이 {roots['base_mm']:.1f}→{roots['v06_mm']:.1f} mm · "
          f"최대 기울기 {roots['max_degrees']:.2f}°. 공유 잎 획 {roots['shared_area_strokes']}개와 줄기·가지 "
          f"{roots['visible_woody_strokes']}획을 유지했다. 개별 잎은 {roots['short_owned_before']}→{roots['short_owned_after']}획이다.</p>",
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
    <h1>프로시저럴 카탈로그 v06</h1>
    <p>암괴군마다 비슷한 외곽과 면의 결을 공유한다. 같은 계열의 암괴를 여러 크기와 깊이로 놓고, 앞뒤 겹침의 정도를 비교했다.</p>
    <p><strong>우선 검토</strong>는 층상 주암과 받침암, 집중된 절리군이다. 두 시편에서 뒤쪽 윗면이 얼마나 드러나는지 본 뒤 발치색과 수관 둘레를 판단한다.</p></header>
    """
    text=("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' "
          "content='width=device-width, initial-scale=1'><title>Datascape 프로시저럴 카탈로그 v06</title>"
          f"<style>{style}</style><main>{intro}<nav aria-label='도판'>{''.join(links)}</nav>"
          f"{''.join(parts)}<footer>벡터 검증 · 도판 {audit['sheets']}장 · 예시 {audit['cards']}종. "
          "안료 발색과 붓 접촉은 실물 시편 검토 항목이다.</footer></main></html>")
    (ROOT/"docs"/"Datascape_Procedural_Catalog_Refinement_v06_REVIEW_KO.html").write_text(text,encoding="utf-8")


if __name__=="__main__":
    build()
