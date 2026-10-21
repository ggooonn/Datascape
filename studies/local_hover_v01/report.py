"""Build the requested Korean report from reproducible numeric study results."""
import argparse,json,html
from pathlib import Path


def table(headers,rows):
    esc=lambda v:html.escape(str(v))
    return '<table><thead><tr>'+''.join('<th>'+esc(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def generate(root):
    from .examples import generate as examples
    examples(root)
    root=Path(root);p=json.loads((root/'study_results.json').read_text());D=p['layouts']['D']['preloads'];A=p['layouts']['A']['preloads']
    def hours(case,model='partial_DEV_model',kind='acceleration_sensitive_seconds'):return case[model][kind]/3600
    def cases(name,preload='2',layout='D'):return p['layouts'][layout]['preloads'][preload][name]['cases']
    rows=[]
    for job in ('SHARED_INK','SHARED_COLOR'):
        c=cases(job);b=c['H10_DNone']
        for h,d in [(10,None)]+[(h,d) for h in (5,3) for d in (5,10,20,30)]:
            s=c[f'H{h}_D{d}'];rows.append([job,h,'—' if d is None else d,s['conditional_local_transitions'],f"{s['local_XY_mm']/1000:.2f}",f"{s['reduced_Z_mm']/1000:.2f}",f"{hours(s,kind='commanded_feed_seconds'):.3f}",f"{hours(s,'partial_commanded_feed_and_low_model'):.3f}",f"{hours(s):.3f}",f"{(hours(b)-hours(s))*60:.1f}"])
    hover=table(['작업','hover mm','거리 ≤mm','조건부 전환 수','전환 XY m','Z 절감 m','명령 h','저가속 h','DEV h','DEV 절감 분'],rows)
    category=[]
    for job in ('SHARED_INK','SHARED_COLOR'):
        c=cases(job)['H5_D10']
        for name,label in [('drawing','동기 XYZ 그리기'),('paper_engagement','접근·접촉·압축·해제·후퇴'),('non_drawing_travel','비도색 XY/Z'),('station_transfer','명목 스테이션 왕복'),('station_handling','스테이션 접촉·재료 처리')]:
            vals=[c[m][k][name] for m,k in [('partial_DEV_model','commanded_feed_seconds_by_category'),('partial_commanded_feed_and_low_model','acceleration_sensitive_seconds_by_category'),('partial_DEV_model','acceleration_sensitive_seconds_by_category')]]
            category.append([job,label,*['미정 U' if v is None else f'{v/3600:.3f}' for v in vals]])
        category.append([job,'계산 가능 소계',f"{hours(c,kind='commanded_feed_seconds'):.3f}",f"{hours(c,'partial_commanded_feed_and_low_model'):.3f}",f'{hours(c):.3f}'])
    depth=[]
    for layout in ('D','A'):
        names=('SHARED_INK','SHARED_COLOR') if layout=='D' else ('P1_INK','P1_COLOR','P2_INK','P2_COLOR')
        for job in names:
            for preload in ('2','3'):
                r=p['layouts'][layout]['preloads'][preload][job];c=r['cases']['H5_D10']
                depth.append([layout,job,'−'+preload,f"{hours(c,kind='commanded_feed_seconds'):.3f}",f"{hours(c,'partial_commanded_feed_and_low_model'):.3f}",f'{hours(c):.3f}',r['reloads'],r['full_washes']])
    low=p['model_assumptions']['synthetic_low'];dev=p['model_assumptions']['unverified_DEV']
    station=json.loads((root/'profile.provisional.json').read_text())['stations'];station_rows=[]
    for role,s in station.items():
        if role=='sponge':action='표면 Z 미정 − 2 mm; 수직 1회';reference='표면 미측정'
        elif role in ('ink','water'):reference='+15';action='+10 (5 mm 침지)'+('; rewet +12' if role=='water' else '')
        else:reference='+10';action='+7 (3 mm 침지)'
        station_rows.append([role,', '.join(str(v) for v in s['center_xy']),reference,action])
    r=p['S3a_routing'];savings=100*(1-r['S3a_total_XY_mm']/r['grouped_original_total_XY_mm'])
    details=[]
    for stage,label in [('air','Air Run'),('calibration','작은 교정'),('painting','최종 도색')]:
        details.append('<details><summary>'+label+' 현재 프로파일의 정확한 차단 목록</summary><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in p['blockers'][stage])+'</ul></details>')
    body=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Datascape Local Hover v01</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 24px;color:#17242c;line-height:1.65}}h1{{font-size:28px}}h2{{font-size:21px;margin-top:32px}}p{{max-width:1000px}}table{{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}}th,td{{border-bottom:1px solid #d8dfe3;padding:7px;text-align:left}}th{{background:#edf1f2}}.note{{border-left:4px solid #aa6b26;padding:12px 18px;background:#fff7eb}}code{{background:#edf1f2;padding:2px 5px}}summary{{cursor:pointer;font-weight:600}}a{{color:#176980}}img,svg{{width:100%;max-width:1000px;height:auto}}@media print{{body{{margin:10px}}table{{font-size:11px}}h2{{break-after:avoid}}}}</style>
<h1>Datascape — Local Hover & G-code 준비 v01</h1>
<p>기준: Draft PR #27 <code>12b28bd5b7ad575b1438ed5af61618746c7effe9</code>. 별도 연구 브랜치. 원화·Pressure Intent·S3a 순서·기존 PR은 변경하지 않았으며 하드웨어 동작은 수행하지 않았습니다.</p>
<p class="note"><b>권장 시험 후보: Z+5 mm, 같은 재료의 연속 원본 스트로크 사이 거리 ≤10 mm.</b> 실제 프로파일에서는 local hover가 꺼져 있습니다. 모든 결과는 조건부이며 승인된 도색 깊이·속도·충돌 안전성·실제 인쇄 시간이 아닙니다. 스테이션 실측 형상이 없어 <b>전체 실행 시간 = 아래 계산 가능 소계 + 미정 스테이션 처리 시간 U</b>입니다. 명목 스테이션 이송 경로도 실측 후 바뀔 수 있습니다.</p>
<h2>1. S3a 경로 확인</h2>
<p>색은 단순 묶음이 아닙니다. 기존 소스의 <code>schedule(... route=True)</code>가 같은 색의 의존성이 풀린 후보 중 이전 끝점→다음 시작점 거리로 선택합니다. 원본 방향을 유지하는 최근접 휴리스틱이며 전역 최적 경로를 보장하지 않습니다. 먹은 원래 순서를 유지하며 동일한 기하 경로 최적화를 적용하지 않았습니다. 본 연구는 이 순서를 그대로 사용했습니다.</p>
<p>색 묶음 내부 직선 전환 거리: 원본 순서대로 색만 묶으면 {r['grouped_original_total_XY_mm']/1000:.2f} m, 기존 S3a는 {r['S3a_total_XY_mm']/1000:.2f} m ({savings:.1f}% 감소). 이는 재보급 왕복을 제외한 진단 수치입니다. 선택적 같은 객체 분석은 별도 읽기 전용으로 진행했습니다. 반복 소유자·재료 그룹 1,924개 중 994개에는 다른 스트로크가 끼어 있으며, 모든 원본의 reorderable은 false입니다. 객체가 같다는 이유만으로 합성 독립성을 가정하거나 순서를 다시 바꾸지 않았습니다.</p>
<h2>2. Local hover 비교</h2>
<p>같은 setup·panel·먹/색·pigment, 실행상 연속인 서로 다른 원본 스트로크, 끝점→시작점 거리 제한, 다음 스트로크 전 재보급·세척 없음이 조건입니다. 도색 종료→Z0 해제→측정 접근 경계→선택 hover로 후퇴하고, 그 높이에서만 XY 이송 후 다음 접근을 시작합니다. Z+10으로 왕복하지 않습니다. 접촉 상태의 횡이동·서로 다른 스트로크 연결은 없습니다.</p>
<p>물리 실행에서는 측정된 swept-tool 안전 경로와 <code>local_hover_clearance</code> 증거가 추가로 필요합니다. 낮은 경로가 충돌하면 기존 정상 hover 경로를 검사하여 사용합니다. Air Run은 local hover를 사용하지 않고 Z+10 이상을 유지합니다. 아래 전환 수는 <b>기하·재료상 후보 수</b>이며 물리 승인 수는 0입니다. 압력 .2→−2 mm 기준, 시간 단위 h.</p>
{hover}
<p>Z+3·10 mm는 Z+5·10 mm보다 색에서 DEV 약 {(hours(cases('SHARED_COLOR')['H5_D10'])-hours(cases('SHARED_COLOR')['H3_D10']))*60:.1f}분을 추가 절약하지만 여유 높이가 작습니다. Z+5의 거리 제한을 20 mm로 늘려 얻는 추가 이득은 색 약 {(hours(cases('SHARED_COLOR')['H5_D10'])-hours(cases('SHARED_COLOR')['H5_D20']))*60:.1f}분입니다. 첫 시험은 5 mm·10 mm로 제한하고, 종이 들뜸·경계 고정물·젖은 붓 처짐·복원·안료 흘림을 확인한 뒤 확장하는 편이 적절합니다.</p>
<img src="comparison.svg" alt="Pressure curves and partial modeled runtimes">
<h2>3. 압력→Z 후보</h2>
<p>기존 다중 knot 선형 보간을 사용합니다. 각 예술 구간은 독립 조절 가능하며 외삽하지 않습니다. 아래 중간 knot는 이전 3영역 연구의 남은 깊이 예산 비율 8%/24%/85%를 유지한 설계 후보입니다. 압력 원본을 수정하거나 수학 곡선에서 실제 획 폭을 추정하지 않았습니다.</p>
{table(['Pressure Intent','이번 .2→−2 후보 Z mm','이전 .2→−3 후보 Z mm'],[(0,0,0),(.2,-2,-3),(.4,-2.64,-3.56),(.6,-3.92,-4.68),(.93,-8.8,-8.95),(1,-10,-10)])}
<p>0–.2는 초기 접촉 영역, .2–.4 / .4–.6 / .6–.93은 조절 영역, .93–1도 단조 증가 압축입니다. Spring의 최대 약 .93은 최대 −10 mm에 강제로 대응하지 않습니다. .2→−2는 .2→−3에 비해 권장 hover에서 DEV 먹 약 {(hours(cases('SHARED_INK','3')['H5_D10'])-hours(cases('SHARED_INK')['H5_D10']))*60:.1f}분, 색 약 {(hours(cases('SHARED_COLOR','3')['H5_D10'])-hours(cases('SHARED_COLOR')['H5_D10']))*60:.1f}분을 줄이지만, 물리 품질 우위를 의미하지는 않습니다.</p>
<h2>4. G54·스테이션 후보</h2>
<p>G54 Z0은 장착 붓이 종이에 처음 간신히 닿는 위치입니다. 목재 상면 −3, 팔레트 바닥 약 −1, 일반 hover +10, local +5/+3, 스테이션 clearance +32, 최대 압축 후보 −10 mm입니다. 브러시의 음수 Z는 유연한 털의 압축 기준이므로 목재의 −3과 곧바로 강체 충돌로 해석할 수 없습니다. 실제 털·붓대·장착부 외형은 별도 검증해야 합니다. G54는 홈 이후 CONTROL에서 종이 원점으로 이동하여 수동 설정하며 홈/YAML/기계 오프셋은 변경하지 않습니다.</p>
{table(['역할','명목 중심 XY mm','액면/표면 Z mm','행동 Z 후보'],station_rows)}
<p>위 XY는 과거 <code>tool_coordinates.yaml</code>의 참고값입니다. WELL_1/2 중심은 과거 Y 범위의 중간점이며 깊은/얕은 경사 기준점이 아닙니다. 모든 스테이션 coordinate_frame은 null로 남겼습니다. PURGE는 (840,137.5), 1회 수직 dab, XY 문지름 없음, 실제 표면 Z·접촉 feed·흡수 dwell은 null입니다. 약 70×70 mm 면적을 실제 허용 접촉 부피로 대신하지 않았습니다.</p>
<p>팔레트 Z+7과 명목 바닥 −1의 간격은 8 mm입니다. 현재 후보의 bottom-gap 2 mm 규칙은 <code>dip_z ≥ bottom_z + gap</code>이므로 최소 Z+1, 명목 여유 6 mm로 수치상 통과합니다. 액면·바닥·용기 형상·좌표 오차와 붓 외형을 실측한 통과가 아닙니다. 팔레트 로딩 패턴과 잉크스톤 점진적 경사 인출 문법은 유지하되 미측정 반경·횟수·경사점·출구·접촉 부피는 null로 남겼습니다.</p>
<h2>5. 시간 재계산</h2>
<p>그리기 XY 5,000 / 일반 XY 12,000 / 일반 Z 6,000 / 비접촉 접근 5,000 / 접촉·해제 및 압력 Z 상한 2,000 / 젖은 이동 3,000→9,000→3,000 mm/min. 액체 스테이션 feed에는 종이 접촉 feed를 적용하지 않았습니다. 시간 모델에만 접근 경계 +1 mm, 젖은 출발·도착 거리 각각 10 mm, 명목 park에서 시작을 사용했습니다. 실제 프로파일의 접근 경계·거리·시작 위치는 미측정 null입니다.</p>
<p>저가속 축 한계 rate={low['axis_max_rate_mm_min']} mm/min, acceleration={low['axis_acceleration_mm_s2']} mm/s²는 합성 가정입니다. DEV rate={dev['axis_max_rate_mm_min']}, acceleration={dev['axis_acceleration_mm_s2']}는 <code>config_DEV_2026-10-10_UNVERIFIED.yaml</code> 참고값으로 설치 장비에서 확인하지 않았습니다. 두 모델의 junction deviation 0.01 mm도 합성 가정입니다. 축 투영 한계·접합 각도·앞/뒤 가감속 계산을 사용하며 순간 가속을 가정하지 않습니다. 미측정 상태별 wet XY/contact Z 가속 제한은 추가하지 않은 축 한계 시나리오이므로, 실제 붓 제한을 적용하면 더 느려질 수 있습니다. 유한 버퍼·통신·스텝 양자화·붓 복원은 포함하지 않습니다. 목표를 맞추기 위한 가속 증가는 없습니다.</p>
{table(['Layout D 권장 후보','주요 동작','명령 h','저가속 h','DEV h'],category)}
<p>색은 종이 진입·접촉·해제·후퇴가 가장 크고 다음은 비도색 이송입니다. 미정 스테이션 처리를 포함한 실제 총시간은 산출할 수 없습니다. 참고로 이전 연구의 고정 스테이션 가정(이번 형상과 다름)인 먹 0.643 h / 색 0.923 h를 DEV 소계에 단순 추가하면 먹 2.337 h / 색 4.182 h입니다. 이는 <b>현재 스테이션 재계산 결과나 검증된 총시간이 아닙니다</b>. 현재 DEV 소계에서 색이 5 h 안에 들려면 U가 약 1.74 h 이하여야 합니다. 저가속 시나리오의 색 소계만 12.837 h이므로 4–5 h 달성을 보장할 수 없습니다.</p>
{table(['레이아웃','작업','p=.2 Z mm','명령 소계 h','저가속 소계 h','DEV 소계 h','추가 재보급','색 변경 세척'],depth)}
<p>A는 각 패널을 같은 G54에 개별 설치하는 4개 작업입니다. 패널 클리핑으로 15,001개 fragment / 241,074개 표본(경계 보간 포함)이 되며 원본 14,951개·240,974개는 별도로 보존합니다. D는 추가 경계점 없이 14,951개 원본·240,974개 표본 그대로입니다. 먹 1,000 mm / 색 800 mm 누적 도달 이후 다음 허용 원본 경계에서 자동 재보급합니다. 같은 재료 재보급에는 세척이 없고, D 색 변경 세척·수직 PURGE는 각 11회입니다. 시작은 수동 준비 상태에서 직접 로딩, 끝은 cleanup 없이 park·M2이며 정기 M0은 먹/색 모두 0개입니다.</p>
<h2>6. 검토 패키지와 검증</h2>
<p><code>D.plan.json.gz</code>, <code>A.plan.json.gz</code>, 두 D 작업의 <code>*.trajectory.jsonl.gz</code>, <code>*.transitions.json.gz</code>, <code>*.preview.txt.gz</code>, 작은 예시, 프로파일, 수치 결과, read-back, SHA256 목록을 제공합니다. 전체 preview는 모든 줄이 세미콜론 주석인 텍스트이며 실제 .nc가 아닙니다. 종이 XYZ·기존 압력·원본/vertex 출처는 전부 기록했고, 스테이션 접촉은 <code>UNRESOLVED</code>로 남겼습니다. 이 항목을 무시하거나 주석을 제거하여 실행하면 안 됩니다.</p>
<p>독립 파일 read-back: 먹 69,101 + 색 171,873 압력 표본, 총 240,974개 일치. 원본 순서·work 변환·XYZ pressure mapping 확인, D의 X=300 교차 50개 연속 확인, 전부 주석·0 M0·명목 최종 X800 Y900 Z32·주석 M2 확인. 미정 스테이션 동작은 먹 84개·색 159개 그대로 보존했습니다. 자동화 회귀 검증은 85개 중 84개 통과·기존 1개 skip입니다. 물리 reachability나 충돌 검증 통과를 뜻하지 않습니다.</p>
<h2>7. 실제 .nc 생성까지 남은 입력</h2>
<ol><li><b>무접촉 Air Run:</b> 장착 붓/장비/기판 ID, 설치 firmware/config hash, 실제 G54→machine 변환과 시작점, 사용 가능 축 범위·rate·acceleration·steps/mm·junction 설정, 털/붓대 포함 tool margin·전체 swept free/keepout, 종이 평탄도·+10 hover·+32 이송·park 도달성 증거. 기존 공통 검증에서 요구하는 접근/스테이션 feed·젖은 출발/도착 거리·상태별 가속 제한도 채워야 합니다. 홈/limit/E-stop 및 등록/운동/clearance/park evidence와 job·plan·profile에 결합된 air 사전 승인이 필요합니다. Air에서는 붓 접촉과 local hover를 사용하지 않습니다.</li><li><b>작은 calibration:</b> 위 조건과 Air Run 통과 증거, 제한된 XY/깊이/속도의 교정 요청, 해당 접촉 구역의 실제 안전 부피, 단계별 승인. station 시험을 넣는 경우 그 station의 G54·접촉 문법 인자·feed/dwell도 측정해야 합니다. 최종 붓 곡선을 이미 측정했다고 꾸미지 않고 작은 압축부터 점진적으로 시험합니다. 별도 교정 프로그램의 의도적인 검사 M0는 기존 기능대로 유지되며, 생산 먹/색 작업의 0 M0와 구분합니다.</li><li><b>최종 SHARED_INK/COLOR:</b> 매체·붓·종이에 맞춘 각 knot의 깊이와 폭/연속성/로딩 관찰, 실제 종이 접촉 범위, 모든 사용 station의 액면·바닥·침지·경사 깊은/얕은 기준점·점진 인출·출구·허용 부피·feed·dwell·세척 횟수·PURGE 표면, 오염/세척·먹→색 수동 점검·microsegment·등록 반복 증거가 필요합니다. D는 continuous_sheet 또는 adjacent_panels 선언과 해당 조립/이음매 안전 검증을 요구합니다. local을 켜려면 젖은 붓 이격/복원·선택 높이/거리의 local_hover_clearance 증거를 추가해야 합니다. 최종 profile/plan/job별 도색 사전 승인에는 좌표/시작·종이/이격·tool/controller·깨끗한 붓·재료/물 준비, 색 작업의 먹 건조/등록 및 D 조립/이음매 확인이 필요합니다. 파일 read-back도 그대로 필수입니다.</li></ol>
<p>실측 이후 기존 v0.3의 <code>readiness → export --stage air → verify → calibration → export --stage painting → verify</code>를 사용합니다. 별도 백엔드 재설계는 필요하지 않습니다. evidence/profile hash가 바뀌면 영향받은 증거와 승인을 다시 결합해야 합니다. 자세한 현재 차단 메시지는 아래에 그대로 제공합니다.</p>
{''.join(details)}
<p>첫 물리 시험 권장: 안전한 작은 교정 영역에서 현재 +10 hover로 얕은 압축부터 확인하고, .2→−2 곡선의 낮은 압력 획과 복원을 관찰합니다. 그 다음 같은 재료의 짧은 전환에서 +5/10 mm를 시험합니다. −10 mm 및 +3 mm는 측정 근거 없이 첫 단계에서 실행하지 않습니다.</p>
</html>'''
    (root/'Datascape_Local_Hover_v01.ko.html').write_text(body,encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt']='datascape.local-hover.v01'
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,3.6),layout='constrained')
    for preload,label in [('2','p0.2 = -2 mm'),('3','p0.2 = -3 mm')]:
        knots=D[preload]['SHARED_COLOR']['curve_knots'];axes[0].plot([a for a,b in knots],[-b for a,b in knots],'o-',label=label)
    axes[0].set(xlabel='Accepted Pressure Intent',ylabel='Candidate compression (mm)',title='Unmeasured multi-knot candidates');axes[0].legend();axes[0].grid(alpha=.2)
    for h in (5,3):
        axes[1].plot([5,10,20,30],[hours(cases('SHARED_COLOR')[f'H{h}_D{d}']) for d in (5,10,20,30)],'o-',label=f'Local +{h} mm')
    axes[1].axhline(hours(cases('SHARED_COLOR')['H10_DNone']),linestyle='--',color='gray',label='Normal +10 mm')
    axes[1].set(xlabel='Maximum endpoint/start distance (mm)',ylabel='Partial DEV runtime (h)',title='SHARED_COLOR / station handling excluded');axes[1].legend();axes[1].grid(alpha=.2)
    fig.savefig(root/'comparison.svg',metadata={'Date':None});plt.close(fig)
    svg='\n'.join(line.rstrip() for line in (root/'comparison.svg').read_text().splitlines())+'\n'
    (root/'comparison.svg').write_text(svg)
    svg=svg[svg.index('<svg'):]
    body=body.replace('<img src="comparison.svg" alt="Pressure curves and partial modeled runtimes">',svg)
    (root/'Datascape_Local_Hover_v01.ko.html').write_text(body,encoding='utf-8')


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--package',required=True,type=Path);generate(a.parse_args().package)
