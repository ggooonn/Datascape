# Verification record

- `python3 -m pytest -q tests/test_seasonal_color_tone_v01.py`: **10 passed**.
- `OPENBLAS_NUM_THREADS=1 python3 studies/seasonal_color_tone_v01/verify.py`: **545 checks passed**; **47 PNGs decoded**.
- All used canonical source vectors, camera/config/placement, depth fields, Spring palette and PR38 skyline/reference match the pinned Git blobs.
- All source-ID style sidecars and 436 supplemental guide records rebuild deterministically. Spring has zero supplemental guides.
- Supplemental guide arcs independently checked with Shapely: maximum source-arc error **1.14e-13 mm**.
- All seven display-role transitions are continuous within 1e-6; eight panel crops are 600 × 1800 and the horizontal comparison is 5360 × 1880.
- All 352 canonical Spring D4 source paths remain unchanged. No physical D4 station is assigned by the study.

See `verification.json` and `reproducibility_manifest.json` for individual checks and exact source hashes. This verifies the additive display study; it does not certify artistic acceptance, physical pigment strength or foreground printing. No earlier geometry is changed, and no G-code is generated.
