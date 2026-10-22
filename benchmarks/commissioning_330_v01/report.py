"""Generate the requested Korean commissioning report, outside public docs."""
import argparse,json,html
from pathlib import Path


def table(headers,rows):
    esc=lambda x:html.escape(str(x))
    return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table>'


def generate(root):
    root=Path(root);s=json.loads((root/'summary.json').read_text());m=json.loads((root/'measurements.json').read_text())
    labels={'A_SHORT':'무접촉 사각 경로 1회','A_STABILITY':'사각 4회 + 301점 sweep 2개','A_STATION_OPTIONAL':'선택적 스테이션 무접촉 접근',
      'B_DEPTH_1':'수동 먹, 60 mm 선 / Z−1','B_DEPTH_2':'수동 먹, 60 mm 선 / Z−2','B_DEPTH_3':'수동 먹, 60 mm 선 / Z−3',
      'C_LOW':'120 mm 가변선 / .2→.35→.45→.35→.2','C_EXTENDED_LATER':'후속 180 mm / .93까지, 최대 −8.8',
      'D_HOVER':'20 mm 획 3개씩 / +10 대 +5, 간격 5·10',
      'E_INK':'WELL_2 단독 로딩·경사 인출','E_WATER':'WELL_1 단독 물 동작·경사 인출',
      'E_CLOTH_OPTIONAL':'선택적 천 PURGE / 수직 0.5 mm 후보','E_INK_REAPPLY':'개별 물·먹 시험 통과 뒤 먹 로딩+60 mm 선'}
    order=['A_SHORT','A_STABILITY','A_STATION_OPTIONAL','B_DEPTH_1','B_DEPTH_2','B_DEPTH_3','C_LOW','D_HOVER','E_INK','E_WATER','E_CLOTH_OPTIONAL','E_INK_REAPPLY','C_EXTENDED_LATER']
    rows=[[k,labels[k],s['stages'][k]['readback']['M0_count'],'실행 차단 / 주석형 preview 준비'] for k in order]
    details=[]
    for name in order:
        r=s['stages'][name]
        details.append('<details><summary>'+name+' — 현재 차단 조건·M0 사유</summary><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in r['blockers'])+'</ul><p>별도로 profile/plan/job 결합 사전 승인이 필요합니다.</p><ol>'+''.join('<li>'+html.escape(x)+'</li>' for x in r['readback']['M0_reasons'])+'</ol></details>')
    audit=m['controller_file_audit'];axes=audit['axes']
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Datascape 330 mm Commissioning v01</title>
<style>body{font-family:system-ui,sans-serif;line-height:1.7;color:#1c2d35;max-width:1080px;margin:36px auto;padding:0 22px}h1{font-size:27px}h2{font-size:20px;margin-top:28px}table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}th,td{padding:8px;border-bottom:1px solid #d6dfe3;text-align:left}th{background:#edf2f3}.note{border-left:4px solid #a66a24;background:#fff5e6;padding:12px 18px}summary{font-weight:600;cursor:pointer}code{background:#edf2f3;padding:2px 4px}svg{width:100%;height:auto}p{max-width:1020px}</style>
<h1>Datascape — 330×330 mm 커미셔닝 v01</h1>
<p>사용자 보고 기준 2026-10-22. Backend <code>12b28bd5b7ad575b1438ed5af61618746c7effe9</code>, Local Hover <code>0eeff5d0d874b9b869c3f274d06bf524ac18282a</code>를 실제 코드·문서로 확인하여 별도 개발 브랜치에서 확장했습니다. 기존 Draft PR과 Spring 원화·Pressure Intent·S3a 순서는 변경하지 않았습니다. 하드웨어 통신·동작은 수행하지 않았습니다.</p>
<p class="note"><b>현재 전달 단계는 오프라인 준비입니다.</b> 13개 독립 계획·궤적·주석형 미리보기·검토 결과·미승인 양식을 준비했습니다. 실제 미완성 프로파일과 승인 false를 기존 exporter에 전달하면 모든 실행 export가 차단되고 부분 출력도 남지 않습니다. 실행용 .nc 0개, 자동으로 통과 처리한 물리 증거 0개입니다. 아래 계획에 대한 소프트웨어 검증은 물리 실행 승인이 아닙니다.</p>
<h2>1. 반영한 실측·보고와 남은 불확실성</h2>
'''
    body+=table(['항목','현재 기록','해석'],[
      ['장비','MKS DLC32 V2.2 / FluidNC / Cartesian XYZ','사용자 보고. 설치 firmware/config 식별은 별도 필요'],
      ['방향·limit·홈','XYZ 방향 보정, $Limits 응답, 반복 홈 성공','이미 보고한 결과는 보존. E-stop·설치 상태와 증거 결합은 미완료'],
      ['홈 직후 WPos','X0 Y898 Z35','확인된 WORK 좌표로 시작 후보에 그대로 반영. MPos/G54를 역산하지 않음'],
      ['종이 첫 접촉','G54 Z0','장착 붓 기준. 명목 종이 두께로 대체하지 않음'],
      ['시험지','약 330×330 / 명목 bed+1, 실제 두께는 조금 작음','실제 설치 XY·평탄도·표면 높이는 미입력'],
      ['박','X800 Y800 Z32','요청값 사용. 전체 접근 경로·도달성은 미검증'],
      ['이격','일반 +10 / local +5 / 스테이션 +32','후보. production local hover는 꺼짐'],
      ['USB','포트 변경 후 안정적으로 보임','장시간 streaming 통과 증거로 처리하지 않음']])
    body+='<p><b>좌표 확인이 우선입니다.</b> 저장된 <code>config(2).yaml</code> SHA256 <code>'+audit['sha256']+'</code>는 읽기 전용으로 감사했습니다. 이 파일에는 X pull-off 2 mm, travel 900/960/50 mm, homing MPos 0/960/50이 있습니다. 현재 보고된 X pull-off 약 5 mm 및 실사용 X850–860/Y898/Z하강 약46과 다릅니다. 이 자료를 실제 설치 파일로 확정하지 않았고, 방향·홈·YAML·G54를 수정하지 않았습니다.</p>'
    body+='<p>G92/TLO가 0인 상태에서 실제 MPos와 WPos의 차이를 확인해 프로파일의 G54→machine 변환을 기록해야 합니다. 현재 펌웨어·설치 YAML·soft limit·junction 설정도 필요합니다. 저장 YAML의 rate 15000/15000/8000, acceleration 1200/1200/1000은 붓에 승인된 값이 아닙니다. 낮은 F를 지정해도 전역 가속도가 낮아지는 것은 아니므로 기존 가속 한도 검증을 유지했습니다.</p>'
    body+='''<h2>2. 시험 설계와 순서</h2><p>종이 원점이 현재 G54 XY(0,0)에 등록된다는 <b>배치 후보</b>입니다. 실제 설치를 확인한 뒤 승인해야 합니다. Air의 사각은 X15–315/Y15–315의 300×300 mm이고, 모든 접촉 중심선은 X10–320/Y10–320 안에 있습니다. 실제 획 폭·털 처짐·고정물 여유는 tool envelope/측정 안전 부피로 따로 확인합니다.</p>'''
    body+=table(['계획','내용','예상 M0 수','현재 상태'],rows)
    body+='''<p>권장 순서: A_SHORT → 결과 확인 → A_STABILITY → B −1 → 검사 → B −2 → 검사 → B −3 → C_LOW → D_HOVER → 각 E 단독 시험 → E_INK_REAPPLY. C_EXTENDED_LATER는 초기 시험에서 제외합니다. 모든 파일은 독립 실행입니다. 각 프로그램 종료 후 park에서 다음 파일의 기록된 시작 WPos로 복귀하는 과정도 수동 검증이 필요합니다. 현재 시작값은 (0,898,35)이며, 이전 park (800,800,32)에서 다음 파일을 그대로 시작하면 안 됩니다.</p>
<p>M0는 startup 1개, 각 station 전·후 2개, 각 상수선·가변선·hover 그룹 전 1개, 최종 기록 1개입니다. startup 이외의 검사 pause는 기존 기능대로 먼저 park합니다. D 그룹 내부에는 M0가 없으며 서로 다른 획은 각각 접촉·해제합니다. 기존 Spring 생산 작업의 정기 M0 0개 정책은 유지됩니다.</p>
<FIGURE>
<h2>3. 압력·Local Hover 시험</h2><p>커미셔닝용 후보 feed는 그리기 상한 600, 일반 XY 1200, 젖은 이송 300→600→300, 일반 Z/비접촉 접근 300, 종이 접촉·해제 60, 압력 Z 상한 120 mm/min입니다. 출발/도착 거리·접근 경계와 허용 가속은 아직 null이며 실제 승인값이 아닙니다. 잉크스톤·천 접촉 feed/dwell은 별도로 미정입니다. Spring 생산 프로파일의 기존 속도 정책을 바꾸지 않았습니다.</p>'''
    body+=table(['Pressure','0','.2','.4','.6','.93','1'],[['후보 Z mm',0,-2,-2.64,-3.92,-8.8,-10]])
    body+='''<p>다중 knot 선형 보간을 그대로 사용하며 샘플 XY·순서·정규화 값은 바꾸지 않습니다. C_LOW는 .2/.35/.45/.35/.2로 Z−2/−2.48/−2.96/−2.48/−2를 시험합니다. C_EXTENDED_LATER는 .93에서 −8.8까지 가므로 초기 −3 mm 허용 범위로 export할 수 없습니다. 선의 600 mm/min은 후보 상한이며, 프로파일의 승인 draw 한도·축/Z 한도가 더 낮으면 명령 속도도 낮춥니다. 이 범위 자체도 아직 승인되지 않아 현재 프로파일은 null입니다. Z35에서 약46 mm 하강 보고를 단순 계산하면 하단 약−11, 최대 후보−10의 여유는 약1 mm뿐입니다. 기계 가동 범위와 적합한 붓 압축은 구분하여 작은 깊이부터 진행합니다.</p>
<p>D_HOVER는 Z−2의 20 mm 선 3개씩, 끝점→다음 시작 간격 5/10 mm를 +10과 +5에서 비교합니다. 이전 획이 선택 높이까지만 후퇴하고 그 높이에서 다음 획으로 이동합니다. +5에서 젖은 털이 완전히 떨어지는지·회복 지연·끌림/안료 자국·종이 들뜸을 관찰합니다. 기존 air/기본 증거·측정된 시험 부피·별도 calibration 승인이 필요하고, 앞선 B 결과의 paper_contact도 요구합니다. 이 시험이 만드는 결과를 사전에 local_hover_clearance 통과로 간주하지 않습니다. 생산 local을 켜려면 실제 결과를 기록하고 기존 증거 게이트를 별도로 통과해야 합니다.</p>
<h2>4. 물·먹·천·팔레트</h2>'''
    body+=table(['항목','bed 기준','명목 G54 (종이 1 mm 가정)','실행 전 필요한 값'],[
      ['우물 림','+18','+17','접근 전체 tool 이격·허용 접촉 부피'],['깊은 바닥','+6','+5','각 WELL의 정확한 deep XYZ'],
      ['얕은 바닥','+10','+9','각 WELL의 정확한 shallow XYZ·경사 방향'],['액면','+10..+11','+9..+10','시험 직전 실제 액면 하나의 Z'],
      ['초기 침지','액면에서 2 mm','+7..+8','gap·feed/dwell·안전 출구 높이'],['천 표면','약+3..+5','약+2..+4','접고 고정한 실제 표면 Z·접촉 부피'],
      ['천 접촉','압축 후보 0.5 mm, 이후 1','실측 표면−압축','수직 1회만. XY 문지름 없음'],['팔레트','림+29 / 바닥+2','림약+28 / 바닥약+1','첫 시험 비활성']])
    body+='''<p>정확한 변환은 <code>Zwork = hbed − Hactual-paper</code>입니다. 실제 H가 아직 없으므로 프로파일 액면과 deep/shallow XYZ는 null로 유지했습니다. +15 액면이나 4.5–5 mm 침지 기본값은 사용하지 않습니다. 보고된 액면/바닥의 명목 간격은 깊은 부분에서 4–5 mm이므로 2 mm 침지 시 바닥 간격 2–3 mm, 3 mm 침지 시 1–2 mm입니다. 오차를 포함한 실제 최소 gap을 정한 뒤 3 mm를 검토해야 합니다.</p>
<p>WELL_1은 물, WELL_2는 먹으로 고정했습니다. X840/Y220–285, X840/Y370–435는 확인된 <b>영역</b>이며 정확한 경사 두 끝점은 아닙니다. 내부 길이105/평탄60/경사45/높이차4 mm만으로 XY 방향·끝점을 만들지 않았습니다. 기존 2점 검사는 두 기준점 사이 바닥이 선형이라는 전제입니다. 45 mm 경사와 60 mm 평탄부를 합친 전체 105 mm를 하나의 경사로 취급하면 안 됩니다. 기준점은 실제 선형 경사 구간을 대표하도록 확인하고, 평탄부를 포함한다면 인출 경로 전체의 바닥 간격을 따로 검증해야 합니다. 기존 sloped_inkstone은 깊은 지점 침지→정지/제한된 로딩→얕은 지점으로 점진 상승→+32 후퇴 문법을 유지합니다. 실제 feed/dwell/gap/출구/허용 부피는 측정 전 미정입니다. 바닥을 긁거나 누르는 동작은 허용하지 않습니다.</p>
<p>PURGE는 X840 Y137.5 참고 위치, 천 압축 0.5 mm 후보로 별도 E_CLOTH_OPTIONAL에만 있습니다. 실제 천 표면을 모르면 실행하지 않으며 A·수동 로딩 B/C/D를 막지 않습니다. E_INK_REAPPLY는 개별 물·먹 trial 증거를 추가 요구하고, 천이나 색 팔레트를 자동 호출하지 않습니다.</p>
<p>팔레트 X847에서 반경7이면 X854까지 갑니다. 실제 Xmax850이면 tool margin을 빼기 전 허용 반경도 최대3 mm이고, Xmax860인 경우도 실제 soft limit와 tool 외형을 확인해야 합니다. +32와 명목 팔레트 림+28의 차이4 mm도 안전 통과 증거가 아닙니다. holder가 bed+40보다 높다는 보고는 보존하되 브러시 전체 swept 경로 검증을 대체하지 않습니다.</p>
<h2>5. 준비 완료·검증 범위</h2>
<p>기존 prepare/readiness/export --stage air/calibration/verify 흐름을 재사용했습니다. 독립 Air 요청을 받는 --benchmark-plan 어댑터, 가변 압력선, 명시적 Local Hover 교정 그룹만 추가했습니다. 교정 전달 파일은 승인 요청에서 IR을 재생성하여 대조합니다. profile·stage·plan·job 승인, 축 속도/가속, 전체 선분 충돌/기계 경계, 압력 domain과 깊이 한도는 유지합니다. 새 기능 때문에 일반 안전 게이트를 완화하지 않았습니다.</p>
<p>회귀 테스트: 99개 실행, 98개 통과, 기존 조건부 1개 skip. 임시 합성 unit fixture에서만 승인 export·독립 read-back을 시험했습니다. 실제 후보 프로파일에는 가짜 MPos/G54/free box나 passed 증거를 넣지 않았습니다. 13개 실제 후보 export 차단, 모든 preview의 수치/출처·M0 사유·park/M2·미정 항목을 확인했습니다. 하드웨어 도달성·종이/붓 품질·실제 streaming 통과를 의미하지 않습니다.</p>
<h2>6. 다음 입력 — 단계별로만 해제</h2>
<ol><li><b>Air 우선:</b> 실제 설치 YAML 원본·firmware 식별, 홈 직후 MPos/WPos/WCO와 저장 G54/G92/TLO·override 상태를 제공해야 합니다. +35 시작, 종이 위치/평탄도/+10 hover, +32 이송, (800,800,32) 전체 park 경로, 실사용 machine bounds·tool margin·free/keepout·축 rate/acceleration/steps·junction을 실제 기록과 결합해야 합니다. 기존 공통 게이트가 요구하는 approach 경계·wet 거리·상태별 가속 한도·station contact ceiling도 임의 승인하지 않고 채워야 합니다. 짧은 통신 시험 자체는 장시간 통과를 미리 요구하지 않지만 현재 연결/정지 절차 확인이 필요합니다. job별 사전 승인 양식은 현재 false입니다.</li>
<li><b>B/C/D:</b> Air 결과와 현재 증거, 실제 종이 첫 접촉·비접촉 경계·시험 부피·처음 허용할 깊이/속도/가속 범위 및 별도 calibration 승인이 필요합니다. C/D는 B 결과의 paper_contact가 추가 필요합니다. −10 후보를 승인 깊이로 사용하지 않습니다.</li>
<li><b>E:</b> 실제 종이 높이와 각 WELL의 deep/shallow XYZ·액면·gap·출구·접촉 부피·feed/dwell, 물의 제한 동작 설정이 필요합니다. 천은 고정한 실제 표면과 별도 접촉 승인 후에만 시험합니다. 미완성 E는 초기 수동 먹 선 시험을 차단하지 않습니다.</li></ol>
<p>측정 기록은 <code>observations.TO_FILL.json</code>에 남기십시오. 각 선의 폭(초/중/끝), 연속성, 먹 전달 분포, 종이 손상/번짐, 붓 복원 시간/끌림, 물·먹 로딩 조건과 실제 feed/depth를 적습니다. 무접촉 기준 위치 오차·USB 지속시간·alarm/disconnect도 기록합니다. 포트 변경과 짧은 성공은 수 시간 신뢰성 증거가 아닙니다. 연결 유실/위치 불확실 시 정지·중단 후 좌표/상태를 재확인하며 임의 G-code 줄에서 재개하지 않습니다.</p>
<p>다음 측정 후에는 기존 v0.3 workflow로 해당 단계만 승인·export·verify할 수 있습니다. 전체 Spring은 이 작은 시험 결과와 생산용 붓·station·등록·동역학 증거를 검토한 다음 준비합니다. 별도 v0.4 재설계는 필요하지 않습니다.</p>'''
    body+=''.join(details)+'</html>'
    import matplotlib
    matplotlib.use('Agg');matplotlib.rcParams['svg.hashsalt']='datascape-commissioning-330-v01'
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,6),layout='constrained')
    ax.plot([0,330,330,0,0],[0,0,330,330,0],color='#263b45',lw=1.5)
    ax.plot([15,315,315,15,15],[15,15,315,315,15],linestyle='--',color='#a5afb3',label='A air square (+10 or above)')
    colors={'B_DEPTH_1':'#334d61','B_DEPTH_2':'#334d61','B_DEPTH_3':'#334d61','C_LOW':'#ae6a2f','C_EXTENDED_LATER':'#bd9a78','D_HOVER':'#366e55','E_INK_REAPPLY':'#536d9a'}
    for name,color in colors.items():
        request=json.loads((root/'plans'/(name+'.json')).read_text())
        if name=='D_HOVER':
            for group in request['hover_groups']:
                for i,l in enumerate(group['strokes']):ax.plot([l['start_xy'][0],l['end_xy'][0]],[l['start_xy'][1],l['end_xy'][1]],color=color,lw=2)
                ax.text(120,group['strokes'][0]['start_xy'][1],f"D hover +{group['hover_mm']}",va='center',fontsize=9)
        elif name.startswith('C_'):
            samples=request['pressure_lines'][0]['samples'];xy=[s['xy'] for s in samples];ax.plot(*zip(*xy),color=color,lw=2)
            ax.text(xy[-1][0]+5,xy[-1][1], 'C low' if name=='C_LOW' else 'C extended: LATER',va='center',fontsize=9)
        else:
            l=request['brush_lines'][0];ax.plot([l['start_xy'][0],l['end_xy'][0]],[l['start_xy'][1],l['end_xy'][1]],color=color,lw=2)
            ax.text(l['end_xy'][0]+5,l['end_xy'][1],name.replace('B_DEPTH_','B depth -').replace('E_INK_REAPPLY','E reapply'),va='center',fontsize=9)
    ax.set(xlim=(-8,338),ylim=(-8,338),xlabel='G54 work X (mm)',ylabel='G54 work Y (mm)',title='330 mm benchmark — candidate placement')
    ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(loc='upper right',fontsize=8)
    path=root/'benchmark_layout.svg';fig.savefig(path,metadata={'Date':None});plt.close(fig)
    svg='\n'.join(l.rstrip() for l in path.read_text().splitlines())+'\n';path.write_text(svg)
    body=body.replace('<FIGURE>',svg[svg.index('<svg'):]);(root/'Datascape_Commissioning_330_v01.ko.html').write_text(body)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--package',required=True,type=Path);generate(a.parse_args().package)
