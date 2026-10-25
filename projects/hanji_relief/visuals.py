"""Source-preserving artwork, refill-boundary and nominal machine projections."""
from html import escape
from pathlib import Path
import gzip,importlib.util,json,math
from .data import PROJECT,PANEL_MAP,COLOR_ORDER,load_json,load_dots

PALETTE=load_json(PROJECT/'input/palette_and_order.json')['original_palette_hex']


def xy_svg(plan,numbered=False):
    rows=plan['dots'];size=600 if plan['coordinate_mode']=='global' else 200
    xs=[float(r['artwork_x_mm']) for r in rows];ys=[float(r['artwork_y_mm']) for r in rows]
    if numbered:x0,y0,x1,y1=min(xs)-10,min(ys)-9,max(xs)+10,max(ys)+12
    else:x0,y0,x1,y1=-10,-10,size+10,size+10
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {-y1} {x1-x0} {y1-y0}" role="img" aria-label="Artwork XY; Y up"><rect x="0" y="{-size}" width="{size}" height="{size}" fill="#fbf8ed" stroke="#c4cbc1" stroke-width="0.5"/>']
    if size==600:
        for v in (200,400):s.append(f'<path d="M{v} 0 V-600 M0 {-v} H600" stroke="#c0c9c1" stroke-width="0.5"/>')
    if numbered:
        for a,b in zip(rows,rows[1:]):
            color='#d78b22' if b['service_before']=='same_color_reload' else '#909b91'
            s.append(f'<path d="M{a["artwork_x_mm"]} {-float(a["artwork_y_mm"])} L{b["artwork_x_mm"]} {-float(b["artwork_y_mm"])}" stroke="{color}" stroke-width="0.35" fill="none"/>')
    starts={}
    for r in rows:
        x,y=float(r['artwork_x_mm']),float(r['artwork_y_mm']);seq=r['execution_sequence'];c=r['color_id'];starts.setdefault(c,(x,y))
        s.append(f'<circle class="dot" cx="{x}" cy="{-y}" r="1.4" fill="{PALETTE[c]}"><title>{seq}: ID {r["study_dot_id"]}; {c}; batch {r["load_batch"]} / contact {r["contact_in_batch"]}; designZ {r["z_design_mm"]}</title></circle>')
        if numbered:
            if seq in (plan['config']['refill_every_contacts'],plan['config']['refill_every_contacts']+1):s.append(f'<circle cx="{x}" cy="{-y}" r="2.4" fill="none" stroke="#d78b22" stroke-width="0.55"/>')
            s.append(f'<text x="{x+1.7}" y="{-y-1.3}" font-size="2.7" font-family="sans-serif" fill="#253b38">{seq}</text>')
    if not numbered:
        for c,(x,y) in starts.items():s.append(f'<circle cx="{x}" cy="{-y}" r="3" fill="none" stroke="{PALETTE[c]}" stroke-width="0.7"/><text x="{x+4}" y="{-y}" font-size="{7 if size==600 else 3.5}" font-family="sans-serif">{c} start</text>')
    if size==600:
        for n,pid in PANEL_MAP.items():
            x=((pid-1)%3)*200+5;y=((pid-1)//3+1)*200-14
            s.append(f'<rect x="{x-2}" y="{-y-10}" width="91" height="16" rx="2" fill="#fffdf5" fill-opacity="0.9"/><text x="{x}" y="{-y+1}" font-size="11" font-family="sans-serif">P{n} / source P{pid:02d}</text>')
    s.append('</svg>');return ''.join(s)


def machine_projection(rows,commands,axis='X'):
    idx=0 if axis=='X' else 1;span=860 if axis=='X' else 900
    def px(x):return 50+x/span*900
    def pz(z):return 255-(z+11)/46*210
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300" role="img" aria-label="Nominal machine projection"><rect width="1000" height="300" fill="white"/>']
    for z in (-10,0,10,20,30,35):s.append(f'<path d="M50 {pz(z)} H950" stroke="#e1e8e3"/><text x="10" y="{pz(z)+4}" font-size="11">{z}</text>')
    points=[]
    for c in commands:
        if c['kind']=='move':
            point=f'{px(c["xyz"][idx]):.2f},{pz(c["xyz"][2]):.2f}'
            if not points or points[-1]!=point:points.append(point)
    s.append('<polyline points="'+' '.join(points)+'" stroke="#7c8983" stroke-opacity="0.12" fill="none" stroke-width="0.7"/>')
    for r in rows:
        x=float(r['g54_x_mm' if idx==0 else 'g54_y_mm']);touch=float(r['review_first_touch_z_mm']);press=float(r['review_press_z_mm'])
        s.append(f'<path d="M{px(x)} {pz(touch)} V{pz(press)}" stroke="#bf674a" stroke-opacity="0.55" stroke-width="0.65"/><circle cx="{px(x)}" cy="{pz(touch)}" r="1.5" fill="#3f7891"/>')
    hover=float(rows[0]['fixed_hover_g54_z_mm'])
    s.append(f'<path d="M50 {pz(hover)} H950" stroke="#c68e23" stroke-dasharray="7 4"/><text x="55" y="{pz(hover)-9}" font-size="12">fixed hover {hover:g}; machine Z upper reference35</text>')
    s.append(f'<text x="50" y="285" font-family="sans-serif" font-size="12">{axis} mm → / Z mm ↑. Blue=nominal first touch; red=3mm press; gray=all station/travel segments.</text></svg>');return ''.join(s)


def surface_review(out):
    spec=importlib.util.spec_from_file_location('hanji_panel_v101_gh',PROJECT/'input/hanji_panel_v101_gh.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);config=module.check_config(module.DEFAULTS)
    maxima={n:0. for n in range(1,10)};rows=['global_x_mm,global_y_mm,z_design_mm\n']
    for y in range(0,601,2):
        for x in range(0,601,2):
            z=module.height(x,y,config);pid=min(2,y//200)*3+min(2,x//200)+1
            maxima[pid]=max(maxima[pid],z);rows.append(f'{x},{y},{z:.6f}\n')
    (out/'nominal_surface_2mm.csv.gz').write_bytes(gzip.compress(''.join(rows).encode(),mtime=0))
    result=dict(sample_step_mm=2,sample_count=90601,panel_sampled_maxima_mm=maxima,analytic_global_upper_bound_mm=20,upper_bound_basis='source height=min(relief_max20,...) followed by convex blend toward discZ6; valid over whole artwork, not only selected dots',sampled_extrema_not_certified_panel_suprema=True,full_tool_or_fixture_clearance_verified=False)
    (out/'surface_clearance_review.json').write_text(json.dumps(result,indent=2)+'\n');return result


def write_previews(out,report,scenario,config):
    out=Path(out);surface=surface_review(out);views={}
    for name,j in report['jobs'].items():
        if j['air']:continue
        plan=load_json(out/(name+'.plan.json'));import csv
        with (out/(name+'.mapping.csv')).open(newline='') as f:rows=list(csv.DictReader(f))
        numbered=name=='hanji_panel_04_C4_first40'
        xy=xy_svg(plan,numbered);(out/(name+'.xy.svg')).write_text(xy)
        views[name]=dict(xy=xy,dots=plan['dot_count'],colors=j['used_color_order'],loads=j['loads'],minutes=j['timing']['acceleration_sensitive_seconds']/60)
        if plan['physical_panel_id']==4 or plan['physical_panel_id'] is None:
            ir=out/(name+'.trajectory.json.gz')
            if ir.exists():cmds=json.loads(gzip.decompress(ir.read_bytes()))
            else:
                from .motion import build_paint
                from dataclasses import asdict
                _,commands,_,_=build_paint(plan,scenario);cmds=[asdict(c) for c in commands]
            views[name]['xz']=machine_projection(rows,cmds,'X');views[name]['yz']=machine_projection(rows,cmds,'Y')
            for a in ['xz','yz']:(out/(name+'.'+a+'.svg')).write_text(views[name][a])
    options=''.join(f'<option value="{name}">{name} · {v["dots"]}点</option>' for name,v in views.items())
    table=''.join(f'<tr><td>{name}</td><td>{j["readback"]["planned_dots"]}</td><td>{len(j["colors"])}</td><td>{j["loads"]}</td><td>{j["same_color_reloads"]}</td><td>{j["color_changes"]}</td><td>{j["timing"]["acceleration_sensitive_seconds"]/60:.2f}</td></tr>' for name,j in report['jobs'].items())
    selected=report['jobs']['hanji_panel_04_local']['timing']['acceleration_sensitive_seconds_by_category']
    # User-facing review is Korean; public repository reports remain English in README/CSV.
    labels={'initial_load':'최초 공급·이송','paper_xy':'작품 위 XY 이동','paper_z_noncontact':'비접촉 Z 접근·복귀','paper_contact':'제어된 접촉·눌림·이탈','dot_dwell':'깊이 도달 후 정지','same_color_service':'동일색 보충·왕복','color_change_service':'색 교체 세척·공급·왕복','end_cleanup':'종료 세척·주차'}
    maximum=max(selected.values());bars=''.join(f'<div class="bar"><span>{labels[k]}</span><div><i style="width:{v/maximum*100:.2f}%"></i></div><b>{v/60:.2f}분</b></div>' for k,v in selected.items() if k in labels)
    data=json.dumps(views,separators=(',',':')).replace('</',r'<\/')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>한지 C안 · PR32 점묘 검토</title><style>
*{box-sizing:border-box}body{background:#f2f1e9;color:#263e38;margin:0;font:15px/1.7 system-ui,sans-serif}main{max-width:1220px;margin:auto;padding:38px 28px 70px}h1{font-size:34px;line-height:1.3;letter-spacing:-1px}h2{font-size:23px;margin:0 0 12px}h3{font-size:17px}p{margin:8px 0 14px}.eyebrow{font-size:12px;letter-spacing:2px;color:#68796f}.banner{padding:18px 22px;border-left:5px solid #b88327;background:#f6e5bf;margin:24px 0}.card{background:#fffef9;padding:24px;border:1px solid #d5dfd5;border-radius:14px;margin:24px 0;overflow:hidden}.grid{display:grid;grid-template-columns:1.15fr 1fr;gap:24px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{border-top:2px solid #62836f;padding:12px 0}.metric b{font-size:28px;display:block}svg{width:100%;height:auto;max-height:800px}select{max-width:100%;padding:8px;font:inherit;background:white;border:1px solid #a6b8a9;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{text-align:left;border-bottom:1px solid #dce3db;padding:8px}td:first-child{overflow-wrap:anywhere}.scroll{overflow-x:auto}code{font:13px ui-monospace,monospace;background:#edf1e9;padding:2px 4px;overflow-wrap:anywhere}.muted{color:#667970}ul,ol{padding-left:22px}.formula{padding:18px;background:#edf2e9;border-radius:7px}.bar{display:grid;grid-template-columns:180px 1fr 65px;gap:12px;align-items:center;margin:10px 0;font-size:13px}.bar div{height:13px;background:#e7ede5}.bar i{display:block;background:#67876b;height:100%}.hidden{display:none}@media(max-width:760px){main{padding:23px 14px}.grid{grid-template-columns:1fr}.metrics{grid-template-columns:1fr 1fr}.card{padding:16px}.bar{grid-template-columns:140px 1fr 55px}}@media print{.card{break-inside:avoid}body{background:white}}</style><main>
<div class="eyebrow">HANJI C · PR32 / OFFLINE v01 / 2026.10.25</div><h1>3 mm 눌림, 깊이에서 1초,<br>20점 뒤 같은 색 보충</h1><p class="muted">일월오봉도 모티브의 독립적인 입체 한지 회화 · 기존 Spring 작품과 별도</p>
<div class="banner"><b>실제 명령이 포함된 수치 검토 파일입니다. 장비 실행 승인이나 실측 등록 완료를 뜻하지 않습니다.</b><br>현재 미리보기는 명목 오프셋0 / 작품 XY=0,0 / G54 호버35 시나리오입니다. 실제 한지 장착 XY·최초 접촉 Z·고정물/붓 여유는 아직 미확정입니다.</div>
<div class="metrics"><div class="metric"><b>6,200점</b>C 원본 전체</div><div class="metric"><b>890점</b>실물4 / P04</div><div class="metric"><b>47회 / 313회</b>4번 / 전체 공급</div><div class="metric"><b>40점</b>C4 보충 경계 시험</div></div>
<section class="card"><h2>원본 위치·색·패널과 실행 순서</h2><p>색 순서 <code>C2 → A4 → A3 → D4 → C4 → B1 → C5 → B2</code>. 사용된 색만 남기며, 4번은 <code>C2 → A3 → D4 → C4 → B1 → C5</code>. 각 색은 아래→위, 첫 유효 행 오른쪽 시작, 행마다 X 방향 왕복입니다.</p><p><select id="job">OPTIONS</select> <span id="info"></span></p><div class="grid"><div id="xy"></div><div><h3>전체 배치</h3>FULLSVG<p>실물 번호는 위에서1·2·3 /4·5·6 /7·8·9. 좌표는 좌하단 원점, X 오른쪽·Y 위쪽을 유지합니다. 개별 원점은 명목 외곽 좌하단이며 첫 점/최저 Z를 빼지 않습니다.</p></div></div><p class="muted">표시 지름2.8mm는 과거 렌더링 가정입니다. 3mm·1초·대형 백운모의 실측 점 크기가 아니며 실제 점이 더 크거나 겹칠 수 있습니다. 원본 점을 줄이거나 이동하지 않았습니다.</p></section>
<section class="card"><h2>C4 첫40점: 20 → 21</h2>FIRST40<p>번호1–20: 최초 공급. <b>21번을 찍기 전 같은 C4를 한 번 보충</b>. 40번 뒤에는 추가 공급하지 않습니다. 1–5 /16–20 /21–25 /36–40의 크기·농도·번짐을 기록하세요. 서로 다른 지형/지지의 영향을 물감 고갈로 단정하지 않습니다.</p><p>40점은 전체890점과 겹칩니다. 같은 작품에서 성공한40점을 완료로 채택하려면 실제 완료 ID·조건·등록을 확인한 기록을 입력해850점 이어찍기를 생성합니다. 현재는 아무 점도 완료 처리하지 않았습니다.</p></section>
<section class="card"><h2>고정 호버와 위치별 최초 접촉</h2><div class="formula"><code>Z_first_touch = z_design + hanji_surface_offset_z + local_surface_correction</code><br><code>Z_press = Z_first_touch − 3 mm</code><br>목표 깊이에 도달 → G4 P1.000000000 → 제어된 이탈 → 고정 호버 복귀.</div><p>기존 평면 first-touch10을 무조건 더하지 않습니다. 붓·기준 종이·패널 뒷면 장착을 포함한 오프셋을 실제 접촉으로 정해야 합니다. 예상1–2mm는 측정 보정값이 아닙니다. 비어 있는 실제 측정 필드는 그대로 유지했습니다.</p><div id="xz"></div><div id="yz"></div><p class="muted">파랑: 명목 최초 접촉 점. 빨강: 그 위치의 추가3mm 눌림. 회색: 실제 명령의 공급·세척·이동 경로. 보정맵이 없어 현재 명목 표면과 검토 접촉면이 겹칩니다. 실제 건조 표면을 측정한 그림이 아닙니다.</p><table><thead><tr><th>가정한 표면 오프셋</th><th>전체 최고 최초 접촉 Z</th><th>호버30 여유</th><th>호버35 여유</th></tr></thead><tbody><tr><td>0 mm</td><td>20</td><td>10 mm</td><td>15 mm</td></tr><tr><td>+5 mm</td><td>25</td><td>5 mm</td><td>10 mm</td></tr><tr><td>+10 mm</td><td>30</td><td>0 mm</td><td>5 mm</td></tr></tbody></table><p>명목 전체 표면의 설계 상한은20mm입니다. 호버35에서10mm 여유를 확보하려면 보정 후 최고 최초 접촉 Z가25 이하이어야 합니다. 오프셋+10이라면10mm 목표에5mm 부족합니다. 한계/원점 변경으로 이 여유가 생긴다고 취급하지 않습니다.</p><p>4번 점 최고 Z16.921mm만으로 이동 구간을 증명하지 않았습니다. 변경 없는 높이 함수를2mm 간격90,601개 위치에서 별도로 평가했고, 패널별 샘플 최고값을 저장했습니다. 고정물과 붓/홀더 전체 폭의 검토는 추가로 필요합니다.</p></section>
<section class="card"><h2>4번 시간 구성 · 계산값</h2>BARS<p>가속도1500/1500/1000mm/s²는 설정 참조값, JD0.01은 가정입니다. 충분한 lookahead와 끊김 없는 스트리밍을 전제로 한 모델이며 실측 시간이 아닙니다. 1초 정지만4번14분50초, 전체1시간43분20초입니다.</p><div class="scroll"><table><thead><tr><th>작업</th><th>점</th><th>색</th><th>공급</th><th>동색 보충</th><th>색 교체</th><th>계산 분</th></tr></thead><tbody>TABLE</tbody></table></div></section>
<section class="card"><h2>공통 동작과 한지 전용 처리</h2><ul><li>PR32의 공급·세척·스펀지·립 및 종료 세척을 가져옵니다. 스테이션은 고정 G54 좌표이며 한지 오프셋을 더하지 않습니다.</li><li>점을 가짜0길이 획이나 짧은 XY선으로 만들지 않았습니다. XY를 고정한 접촉·압축·정지·이탈 이벤트를 사용하고, 거리0에서도 사용 후 귀환 상태를 접촉 횟수로 유지합니다.</li><li>20회 완료 뒤 다음 점이 있을 때 보충합니다. 색이 바뀌면 이전 색의 추가 보충을 생략하고 기존 세척·퍼지·재습윤·새 색 공급을 실행합니다. 루틴M0는 없습니다.</li><li>완전한 작업은 각각 X0 Y900 Z35에서 시작 조건을 확인합니다. 끝에서 X800 Y800 Z35로 주차한 뒤 종료 세척을 한 번 붙이고 주차/M2. 물3회×10초/각3회 교반, 스펀지2회×4초, 마지막 재습윤·물감 공급 없음.</li><li>AIR는 같은 예정 점·서비스 XY를 Z35에서 확인합니다. 실제 눌림·담금·정지와 소비/완료 접촉 카운터는0입니다. 계획된47회 공급이 실제47회 물감 소비를 뜻하지 않습니다.</li></ul></section>
<section class="card"><h2>실행 수치 확정에 남은 등록값</h2><ol><li>작품/개별 패널의 실제 외곽 좌하단 G54 XY. 기본 검토의0,0은 위치 가정입니다.</li><li>기준점의 실제 최초 접촉 G54 Z와 해당 설계 Z로 구하는 <code>hanji_surface_offset_z_mm</code>. 패널/전체 장착 높이가 다르면 각각 기록합니다.</li><li>국소 편차와 고정물 최고점·붓/홀더 범위를 확인한 Z30/35 이동 여유. 패널 평균만으로 내부 편차가 해결되었다고 보지 않습니다.</li></ol><p>기존 펌웨어·물감통 질문을 다시 요구하지 않습니다. 실제 붓/장착이 변경되었다면 기존 스테이션 접촉 높이와 분리해 차이를 기록해야 합니다.3mm·1초·20점은 벤치마크 기본값이며 실제 크기와20점 유지성은 시험에서 확인합니다.</p><p class="muted">기준 PR32 / eda6069b12c8785d458a0e8a567a9a86980bc394 · 기존 Spring/기계 설정 변경 없음 · 장비 연결/전송/구동 없음</p></section>
</main><script>const views=DATA;const select=document.getElementById('job');function show(){const v=views[select.value];document.getElementById('xy').innerHTML=v.xy;document.getElementById('xz').innerHTML=v.xz||'';document.getElementById('yz').innerHTML=v.yz||'';document.getElementById('info').textContent=v.dots+'점 / 공급'+v.loads+'회 / 계산'+v.minutes.toFixed(2)+'분'}select.value='hanji_panel_04_local';select.addEventListener('change',show);show();</script></html>'''
    for k,v in {'OPTIONS':options,'FULLSVG':views['hanji_full_600x600']['xy'],'FIRST40':views['hanji_panel_04_C4_first40']['xy'],'BARS':bars,'TABLE':table,'DATA':data}.items():html=html.replace(k,v)
    english = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hanji C point-contact review</title><style>body{font:15px/1.65 system-ui;background:#f3f2e9;color:#253d35;margin:0}main{max-width:1160px;padding:32px 24px;margin:auto}section{background:#fffef8;border:1px solid #d8dfd4;border-radius:12px;padding:23px;margin:23px 0}svg{width:100%;height:auto;max-height:750px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:7px;border-bottom:1px solid #dce2d8;text-align:left}td:first-child{overflow-wrap:anywhere}select{padding:8px;max-width:100%}.warning{background:#f6e2b8;padding:18px;border-left:5px solid #bc8730}.scroll{overflow:auto}code{overflow-wrap:anywhere}h1{line-height:1.2}</style><main><h1>Hanji C: constant3mm /1s /20contacts</h1><p>Independent Ilwolobongdo-inspired hanji relief, sharing Datascape plotter technology.</p><p class="warning"><b>Real numeric motion commands; offline review only, NOT authorized to run.</b> Nominal scenario: artwork XY at0/0, surface offset0, fixed G54 hover35. Actual mounting and dry-paper first touch are not measured. No passed collision evidence or hardware operation is inferred.</p><section><h2>Artwork and planned order</h2><p>6200 source dots; physical panel4/P04 has890. Preserve bottom-left XY/Z, eight colors and IDs. Color order C2→A4→A3→D4→C4→B1→C5→B2, skipping unused colors. Each color proceeds by ascending Y, right-first serpentine occupied rows. Preview diameter2.8mm is an unmeasured rendering assumption.</p><select id="job">OPTIONS</select><span id="info"></span><div id="xy"></div><div id="xz"></div><div id="yz"></div><p>Blue: nominal first-touch dots. Red:3mm compression. Gray: station and travel projection. No measured surface map is implied.</p></section><section><h2>C4 first40: reload before21</h2>FIRST40<p>One initial load and one same-color reload before21; no load after40. Compare1–5,16–20,21–25,36–40 using the observation CSV. The40 dots overlap the full890-dot job. No completion is inferred. A confirmed same-condition physical completion ledger can produce the remaining850-dot job.</p></section><section><h2>Registration and clearance</h2><p>First touch = design Z + measured surface offset + local correction. Press Z = first touch −3. Full1s dwell starts after reaching depth; no XY dither or artificial stroke. Stations receive no artwork offset.</p><table><tr><th>Assumed offset</th><th>Full highest touch</th><th>Hover30 gap</th><th>Hover35 gap</th></tr><tr><td>0</td><td>20</td><td>10</td><td>15</td></tr><tr><td>+5</td><td>25</td><td>5</td><td>10</td></tr><tr><td>+10</td><td>30</td><td>0</td><td>5</td></tr></table><p>At Z35, a10mm gap requires the actual highest touch to be≤25. An offset+10 leaves5mm, short of the target by5mm. Original design20 is an analytic global ceiling; dot maxima alone are not used to prove transit clearance. A2mm nominal surface sample is included. Full brush/holder and fixtures still need review. Record actual outer-corner G54 XY, first touch at a known design point, local deviations and fixture/tool clearance. Do not raise limits or shift G54 to claim new physical clearance.</p></section><section><h2>Schedules and modeled time</h2><div class="scroll"><table><tr><th>Job</th><th>Dots</th><th>Colors</th><th>Loads</th><th>Same-color</th><th>Changes</th><th>Modeled min</th></tr>TABLE</table></div><p>Common planner model: configuration-reference acceleration1500/1500/1000mm/s², assumed JD0.01, full lookahead and uninterrupted streaming. These are calculations, not measured durations. Dwell alone:40s /890s /6200s. AIR simulates the planned service schedule at Z35 with zero contact, immersion or material-consumption completion.</p></section><section><h2>Start, finish and reuse</h2><p>Each independent job expects G54 X0Y900Z35 and finishes X800Y800Z35/M2. PR32 material primitives are reused. Same-color reload has no wash; color change uses the original wash/purge/rewet/load. Terminal cleanup occurs once: three water visits10s/three agitations each, sponge twice4s, no final rewet/load. No routine M0, homing or coordinate writes. The10 main files are alternative full/global and nine local-panel workflows, not a concatenated run.</p><p>Details, mapping CSVs, immutable inputs, regeneration commands, test records and unchanged official export gates are documented in the project README. No Spring artwork, pressure intent or source order is changed.</p></section></main><script>const views=DATA;const select=document.getElementById('job');function show(){const v=views[select.value];document.getElementById('xy').innerHTML=v.xy;document.getElementById('xz').innerHTML=v.xz||'';document.getElementById('yz').innerHTML=v.yz||'';document.getElementById('info').textContent=' '+v.dots+' dots / '+v.loads+' loads / '+v.minutes.toFixed(2)+' modeled min'}select.value='hanji_panel_04_local';select.addEventListener('change',show);show();</script></html>"""
    n=config['refill_every_contacts']
    english=english.replace('constant3mm /1s /20contacts', f'constant3mm /1s /{n}contacts')
    english=english.replace('physical panel4/P04', 'physical P4 (archived source P04)')
    english=english.replace('C4 first40: reload before21', f'Physical P4 / color C4 first40: reload before{n+1}')
    english=english.replace('one same-color reload before21', f'one same-color reload before{n+1}')
    english=english.replace('Compare1–5,16–20,21–25,36–40', f'Compare1–5,{n-4}–{n},{n+1}–{min(n+5,40)},36–40')
    english=english.replace('Preserve bottom-left XY/Z', 'Physical labels P1–P9 run top-left to bottom-right; C2/C4 are colors. Preserve bottom-left XY/Z')
    for k,v in {'OPTIONS':options.replace('点',' dots'),'FIRST40':views['hanji_panel_04_C4_first40']['xy'],'TABLE':table,'DATA':data}.items():english=english.replace(k,v)
    (out/'Hanji_C_Review.html').write_text(english)
    return html
