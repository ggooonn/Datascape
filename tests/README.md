# Tests

새 알고리즘이 구현될 때 다음 동작을 검사한다: NoData/유효 음수 구별, CRS·격자 정렬, 지리→화면→panel 좌표 변환, 양 끝점이 밖에 있는 경계 교차, 압력 보간, 패널 간격, 방향·순서 보존. G-code 테스트는 calibration과 도구 접근·Z·중단/복귀 검증을 포함한다.

현재 구조 변경에는 엔진 동작 테스트를 추가하지 않았다. 원본 바이트·checksum, Python/JSON/YAML 문법, editable package import와 새 notebook 실행, 문서 링크를 검증한다. 이 검사는 실지형 재현과 하드웨어 검증을 대신하지 않는다.
