# FluidNC — 미검증 개발 설정

- [개발 원본](config_DEV_2026-10-10_UNVERIFIED.yaml)은 받은 바이트 그대로 보존했다.
- [예제](config.example.yaml)는 원본 수치에 미검증 안내 주석만 추가했다. 검증된 설정이 아니다.
- 실제 컨트롤러: 사용자 확인 MKS DLC32 V2.2. 원본 `board` 라벨: V2.1. 라벨을 임의 수정하지 않았다.
- [도구 좌표](tool_coordinates.yaml)는 사용자 제공 XY를 기록한 것이며 좌표계·WELL 물/먹 매핑·Z는 미확정이다.
- [실기 검증 기록](calibration/README.md).

원점·축 방향·limit 핀/배선·MPos·work offset·안전 Z·도구 접근을 먼저 확인한다. 그리기 영역 약 800×900mm와 도구 접근 영역은 별도다. X=847mm 도달 여부와 헤드 간섭을 값만으로 판단하지 않는다.

옛 노트북의 음수 X/Z와 새 설정을 직접 결합하지 않는다. 이 PR에서는 핀·속도·가속·호밍·리미트 설정을 변경하지 않았다. 실제 `config.yaml`과 네트워크 인증값은 Git에 넣지 않는다.
