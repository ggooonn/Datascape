# Decisions

## 2026-10-14 — 저장소 재구축

- 기준 main: `4e27f59805a79b3147f287f9d503adbf9bda7d14`.
- 사용자가 제안한 `data/`, `tool_coordinates.yaml`, `configs/rendering/`과 세 실험 notebook 이름을 채택.
- 이전 README를 별도 문서로 복사하지 않고 최소 소개로 교체.
- README는 이번 첨부 `output.png`의 금강산 디지털 렌더를 임시 사용.
- 초기 Python과 GEE 파일은 바이트 보존 이동. 작품 노트북은 바이트 보존 복사.
- 원본 노트북의 코드 셀만 추출한 `source.py`는 리뷰용 파생본으로 manifest에 명시.
- 실물 제작 3작품은 독립 관리. 원본 데이터와 최종 제작 파일의 연결 확인은 남음.
- 새 엔진은 namespace·패키지 기반만 구성. 알고리즘과 최종 제작 G-code는 후속 PR.
- FluidNC 원본값은 변경하지 않음. 예제·도구 좌표·바탕재 색은 검증 수준을 명시.
- 원본 TIFF·대량 G-code·캐시·비밀 설정은 로컬 보관.
- 변경은 별도 브랜치와 PR에서 검토하고 main 병합은 사용자 결정 뒤 진행.
