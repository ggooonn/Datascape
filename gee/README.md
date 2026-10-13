# Google Earth Engine

- [서울 북부 v0.2](seoul_north_v02.js): 받은 스크립트 원문 보존. MASTER 30m 13밴드와 VEG 10m 8밴드.
- [데이터 명세](../docs/datasets/seoul_north_v02.json): 실제 TIFF를 받기 전 값은 예상 명세이며 검증 완료가 아님.
- [초기 추출 코드](archive/geedata_extraction.js): 기존 저장소 파일을 원문 그대로 이동. 과거 작품의 실제 입력과 정확히 대응하는지는 별도 확인.

원본 TIFF는 로컬 보관한다. 실제 CRS·격자·mask·값 범위·관측 수는 Python에서 검증한다. 재표본화로 원본 DEM보다 세부 정보가 증가했다고 설명하지 않는다. 겨울은 여러 해의 12~2월 합성이다.
