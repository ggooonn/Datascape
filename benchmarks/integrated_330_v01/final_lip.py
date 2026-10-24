"""Final operator-measured lip integration; numeric review, no device I/O."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import difflib
import hashlib
import json
import yaml

from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import _atomic_output, _serialize, save_json
from . import y900_lip as previous
from .high_speed import build_benchmark, elevated_air
from .numeric_review import BANNER, STATUS, xy_route

PIN='54904b78bfb039ac0a27b083759bc972769d9d92'
BASE='benchmarks/integrated_330_v01/review_y900_lip'
STEM='BENCHMARK_330_FINAL_LIP_'


def yaml_candidate(root):
    source=(root/BASE/'config.X860.Y900.high_speed.candidate.yaml').read_bytes()
    # Keep the complete configuration body verbatim except the descriptive name.
    body=source.decode()[source.decode().index('board:'):]
    body=body.replace('name: DATASCAPE_HOME_FRAME_X0_Y898_Z35_261022',
                      'name: DATASCAPE_HOME_FRAME_X0_Y900_Z35_261024')
    header='''# DATASCAPE X860 / Y900 HIGH-SPEED COMMISSIONING CANDIDATE
# Not installed or read back by this software. Back up the active YAML first.
# Physical lower Y0 and all paper/station work coordinates remain unchanged.
# Only the upper mechanical assembly/travel extends from 898 to 900 mm.
# Expected home MPos AND G54 WPos: X0 Y900 Z35 with existing zero G54/G92/TLO.
# Inspect actual offsets and registration; do not set a global +2 mm correction.
# X/Y: max rate 20000 mm/min, acceleration 1500 mm/s^2; X travel 860, Y travel 900.
# Z/motors/pins/directions/steps/pull-offs/homing cycles unchanged from prior Y900 candidate.
# Nominal Z envelope -11..35; contact/holder clearances and stopping require physical checks.
# No homing or offset-setting command is supplied in these comments.
'''
    raw=(header+body).encode();old=yaml.safe_load(source);new=yaml.safe_load(raw)
    expected=deepcopy(old);expected['name']='DATASCAPE_HOME_FRAME_X0_Y900_Z35_261024'
    if new!=expected:raise ValueError('configuration values other than descriptive name changed')
    diff=''.join(difflib.unified_diff(source.decode().splitlines(True),raw.decode().splitlines(True),
        fromfile='PR31/review_y900_lip/config.X860.Y900.high_speed.candidate.yaml',
        tofile='config.X860.Y900.final_lip.candidate.yaml'))
    return raw,diff,dict(source_sha256=hashlib.sha256(source).hexdigest(),candidate_sha256=hashlib.sha256(raw).hexdigest(),
        configuration_change='descriptive name only; outdated historical header replaced',
        all_motion_motor_homing_values_preserved=True,physical_Y0_unchanged=True,
        installed=False,read_back=False,physical_range_verified=False)


def profile(root,wet=12000):
    d=deepcopy(previous.frame_profile(root,wet).data)
    d['profile_id']=f'FINAL-MEASURED-LIP-Y900-WET{wet}-REVIEW'
    d['machine']['target_config_sha256']=yaml_candidate(root)[2]['candidate_sha256']
    for role,y in [('ink',458),('water',298)]:
        # Do not turn a reported contact coordinate into a full-tool clearance certificate.
        d['stations'][role]['lip_stripping']=dict(enabled=True,primitive='measured_linear_x_v1',
            coordinate_source='operator_measured_confirmed',measured_contact_xyz=[815,y,20],
            relative_x_mm=-20,contact_feed_mm_min=300,contact_feed_cap_mm_min=300,
            safe_retract_z=35,operator_requested_generation=True,
            physical_new_sequence_passed=False,holder_swept_clearance_certified=False)
    d['notes']='Operator-confirmed lip starts; requested X815->795/F300 after ONE20mm wipe and lift35. Numeric review generation authorized; machine execution/installed-Y900 readback not inferred. Existing Spring Z-8 and 40 explicit depth trials unchanged.'
    return Profile.from_dict(d)


def jobs(root,p):
    plan,paint=build_benchmark(root,p)
    return plan,dict(AIR=elevated_air(paint,p),WATER_ONLY=paint,INK_GOUACHE=paint)


def render(commands,p,plan,name):
    return BANNER+'; OPERATOR-MEASURED LIP STARTS; NEW COMPLETE SEQUENCE NOT PHYSICALLY PASSED\n'+_serialize(commands,p,digest(plan),STEM+name+'_REVIEW','offline_review')


def readback(text,commands,p,name):
    air=name=='AIR'
    result=previous.readback(text,commands,p,'ONE_WIPE_330_'+name)
    moves=[c for c in commands if c.kind=='move'];strips=[]
    expected=[458,458,298]
    for i,c in enumerate(moves):
        if c.travel_phase!='lip_strip':continue
        before=moves[i-3:i];after=moves[i+1:i+2];y=expected[len(strips)]
        height=35 if air else 20
        if (len(before)!=3 or before[0].xyz!=(840,465 if y==458 else 315,35) or
            before[1].xyz!=(815,y,35) or before[1].travel_phase!='lip_approach' or
            before[1].feed_mm_min!=3000 or before[2].xyz!=(815,y,height) or
            before[2].travel_phase!='lip_contact' or before[2].feed_mm_min!=1000 or
            c.xyz!=(795,y,height) or c.feed_mm_min!=300 or
            not after or after[0].xyz!=(795,y,35) or after[0].travel_phase!='lip_retract' or
            after[0].feed_mm_min!=7000):
            raise ValueError('lip lift/approach/vertical contact/relative-X strip/retract ordering or feed mismatch')
        strips.append(dict(start=[815,y,height],end=list(c.xyz),relative_x_mm=-20,feed_mm_min=300))
    if len(strips)!=3:raise ValueError('expected two ink lip strips and one water lip strip')
    for c in commands:
        if c.kind=='move' and c.time_category=='station_handling' and air and c.xyz[2]!=35:
            raise ValueError('matched Air station operation below Z35')
    base=previous.frame_profile(Path(__file__).resolve().parents[2]);_,old=previous.jobs(Path(__file__).resolve().parents[2],base)
    draw=lambda rows:[(c.source_id,c.xyz[:2],c.feed_mm_min) for c in rows if c.action=='draw']
    if draw(commands)!=draw(old['ONE_WIPE_330_WATER_ONLY']):raise ValueError('original 40 XY/source/order/feed changed')
    if not air and [(c.source_id,c.xyz) for c in commands if c.action=='draw']!=[(c.source_id,c.xyz) for c in old['ONE_WIPE_330_WATER_ONLY'] if c.action=='draw']:
        raise ValueError('explicit constant-Z benchmark depths changed')
    result.update(lip_contact_emitted=not air,lip_Z20_descent_emitted=not air,
        lip_strips=strips,lip_contact_strokes=0 if air else len(strips),
        matched_lip_simulation_strokes=len(strips) if air else 0,
        measured_contact_coordinate_source='operator report in final lip integration request',
        physical_new_sequence_verified=False,authorized=False)
    return result


def export(root,output,machine=None,provenance=None):
    p=profile(root);plan,programs=jobs(root,p)
    def write(out):
        raw,diff,controller=yaml_candidate(root)
        (out/'config.X860.Y900.final_lip.candidate.yaml').write_bytes(raw)
        (out/'config.X860.Y900.final_lip.diff').write_text(diff)
        save_json(out/'controller.json',controller)
        save_json(out/'profile.final_lip.wet12000.json',p.data)
        save_json(out/'profile.final_lip.wet15000.json',profile(root,15000).data)
        save_json(out/'benchmark40.plan.json',plan)
        save_json(out/'reconciliation.TO_COMPLETE.json',previous.reconciliation_template())
        report=dict(schema='datascape.final_measured_lip_review.v01',base_commit=PIN,status=STATUS,
            authorized=False,hardware_operated=False,old_candidates_preserved=True,jobs={})
        for name,commands in programs.items():
            file=STEM+name+'_REVIEW';text=render(commands,p,plan,name)
            (out/(file+'.gcode')).write_text(text)
            result=readback((out/(file+'.gcode')).read_text(),commands,p,name)
            save_json(out/(file+'.readback.json'),result);report['jobs'][name]=result
        if xy_route(programs['AIR'])!=xy_route(programs['WATER_ONLY']):raise ValueError('matched Air XY differs')
        if machine is not None and provenance is not None:
            save_json(out/'spring_coordinate_dependencies.json',previous.spring_dependencies(root,{'FINAL_LIP':p},machine,provenance))
        save_json(out/'verification.json',report)
        (out/'README.md').write_text(README);(out/'RUN_SHEET.ko.md').write_text(RUN_SHEET)
        return report
    return _atomic_output(output,write)


def verify(root,output):
    out=Path(output);manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    if set(manifest)!={x.name for x in out.iterdir() if x.is_file() and x.name!='MANIFEST_SHA256.json'}:raise ValueError('manifest coverage')
    for name,sha in manifest.items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=sha:raise ValueError('SHA256 mismatch '+name)
    raw,diff,controller=yaml_candidate(root)
    if raw!=(out/'config.X860.Y900.final_lip.candidate.yaml').read_bytes() or diff!=(out/'config.X860.Y900.final_lip.diff').read_text():raise ValueError('YAML regeneration')
    if controller!=json.loads((out/'controller.json').read_text()):raise ValueError('controller record mismatch')
    for wet in (12000,15000):
        if Profile.load(out/f'profile.final_lip.wet{wet}.json').data!=profile(root,wet).data:raise ValueError('profile regeneration')
    p=profile(root);plan,programs=jobs(root,p)
    if plan!=json.loads((out/'benchmark40.plan.json').read_text()):raise ValueError('source plan mismatch')
    report=json.loads((out/'verification.json').read_text())
    for name,commands in programs.items():
        file=STEM+name+'_REVIEW';text=(out/(file+'.gcode')).read_text()
        if text!=render(commands,p,plan,name):raise ValueError('G-code regeneration')
        checked=readback(text,commands,p,name)
        if checked!=json.loads((out/(file+'.readback.json')).read_text()) or checked!=report['jobs'][name]:raise ValueError('readback regeneration')
    return dict(numeric_review_files_regenerated=3,all_SHA256_verified=True,readback_verified=True,M0_count=0,authorized=False)


README='''# Final measured lip-stripping benchmark

Three complete numeric review files share the original 40-stroke plan, explicit
constant-Z -1..-10 trials, exact material visit sequence, and accepted high-speed
profile. Existing old candidates are preserved. No hardware I/O or official
machine-authorization bypass occurs. Review generation is requested; physical
clearance/installation/new-sequence success is not fabricated.

For each ink/water visit: immersion/X agitation -> original slope -> ONE pressed
20mm Y+ wipe at Z7.5 -> vertical release Z9 -> vertical lift Z35 -> XY815/458
(ink) or815/298 (water) at Z35/F3000 -> vertical Z20/F1000 -> X795/F300
(relative X-20) -> vertical Z35/F7000. Both measured starts are operator-confirmed.
No second wipe or X-10 re-entry remains. Lip coordinates are independent of
slope and shallow-surface models. Displacement, feed/cap, start and retract are
separate profile fields. The shared production emitter validates the grammar;
official station validation additionally requires the calibrated contact volume
and all existing full-tool path, evidence and stage authorization checks.

Matched AIR retains every XY path and station visit, with all station handling
at Z35 and paper simulation at Z15; it does NOT descend to the lip at Z20.
WATER_ONLY/INK_GOUACHE numeric bodies are identical, differing only in contents.
Start after manual home: G54 X0 Y900 Z35; zero G54/G92/TLO expected. End:
X800 Y800 Z35/M2, M0=0. No homing/offset-setting commands embedded.

Dry/depleted15000, wet12000 (separate optional15000 profile), drawing6000,
noncontactZ7000, pressure/contact/release2000, paper15/localoff, station35,
ink1200/color800 reload candidates remain unchanged. Other station feeds,
dwells, purge1.5/4s, palette5/radius5, twelve Spring colors/Z-8 remain unchanged.

YAML: motion/motor/homing scalar values equal the previous completed Y900
candidate. Only descriptive name and obsolete comments change. It remains a
separate candidate, NOT installed/read back here. Physical lowerY0 and all
station/paper work coordinates remain unchanged; no global+2 translation.
Expected home MPos=WPos0/900/35; actual configuration/home/range/stopping and
full-tool clearance verification remain physical execution prerequisites.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.final_lip --output NEW_DIR
Verify: same command with existing output and --verify. Optional canonical
--machine /path/spring.machine.json --provenance /path/spring.provenance.json.
After operator feedback: select/calibrate brush, then existing Spring AIR and
separate SHARED_INK/SHARED_COLOR export workflow. No production Spring files
are exported before those results/physical profiles/authorization exist.
'''

RUN_SHEET='''# 최종 립 스트리핑 벤치마크

이 파일은 실제 G1/G4/M2 명령을 포함한 검토용입니다. 파일 생성·소프트웨어 검증과
기계 실행 승인은 구분됩니다. 새 립 동작의 실행 성공이나 YAML 설치를 기록하지 않았습니다.

1. 실제 설치 YAML과 Y900 홈/이동 범위를 확인하고 ?, $G, $#로 MPos/WPos 및
   G54/G92/TLO를 확인합니다. 예상 시작은 X0 Y900 Z35, 오프셋 0입니다.
   기존 Y0·스테이션·종이 좌표는 유지하며 +2 이동/오프셋을 설정하지 않습니다.
2. 공구 전체 간섭 여유와 사용 가능한 정지 수단을 확인한 뒤 AIR를 먼저 실행합니다.
   모든 스테이션 동작은 Z35, 종이 모사는 Z15입니다. AIR는 Z20 접촉을 검증하지 않습니다.
3. WATER_ONLY는 WELL_2와 A2에도 물을 준비합니다. INK_GOUACHE는 WELL_2에 잉크,
   A2에 과슈, WELL_1에 깨끗한 물을 준비합니다. 두 파일의 수치 경로는 같습니다.
4. 각 프로그램 시작 전 다시 홈을 실행해 시작 좌표를 맞춥니다. 이전 주차 위치에서
   그대로 시작하지 않습니다. 기존 40개 깊이 시험(-1~-10)은 그대로입니다.
5. 잉크 두 번/물 한 번 방문마다: 침지·교반 → 경사 인출 → Z7.5에서 Y+20mm 한 번
   와이핑 → 수직 Z9/Z35 → 잉크(815,458)/물(815,298) → 수직 Z20 →
   X815→795/F300 → 수직 Z35입니다. 액체 제거량·물방울·붓/홀더 간섭을 기록합니다.
6. M0는 0개이므로 자동 검사 대기는 없습니다. 간섭·탈조·통신 이상 시 확인한 정지
   수단으로 즉시 중단하고, 위치를 확인하기 전 재개하지 않습니다.

주요 피드: 일반/복귀 F15000, 젖은 붓 F12000, 그리기 F6000,
비접촉 Z F7000, 종이 접촉/해제 F2000, 립 하강 F1000, 립 X 이동 F300.
종이 hover15, 로컬 hover 비활성, 전역35. 종료 X800 Y800 Z35, M2.

이 벤치마크 결과 확인 후 벤치마크 개발을 종료합니다. 다음은 붓 선택·압력 교정 후
동일한 백엔드로 Spring AIR → SHARED_INK → SHARED_COLOR입니다.
Spring 작품·Pressure Intent·S3a·Z-8 후보는 바꾸지 않았습니다.
'''

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--machine',type=Path);ap.add_argument('--provenance',type=Path)
    a=ap.parse_args();root=Path(__file__).resolve().parents[2]
    if a.verify:print(json.dumps(verify(root,a.output)))
    else:export(root,a.output,a.machine,a.provenance)
