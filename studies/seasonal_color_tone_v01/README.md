# Seasonal color and tone study v01

This additive study uses the complete provisional eight-panel PR38 baseline at `6e331beb7e405cff55feb0ea9f3982808976f907`. Canonical terrain, vegetation, rocks, Spring geometry and machine pressure profiles remain unchanged.

- Config: `configs/experiments/seasonal_color_tone_v01.json`.
- Entry point: `python3 studies/seasonal_color_tone_v01/generate.py`.
- Frozen source/style model and continuous OKLab palette: `model.py`.
- Matched preview renderer: `render.py`.
- Existing-scene identity audit and unapplied foreground proposals: `audit.py`.
- Framework, review and P2 execution handoff: `notes.py`.
- Independent source/arc/sidecar checks: `verify.py`.
- Tests: `python3 -m pytest -q tests/test_seasonal_color_tone_v01.py`.
- Review: `docs/experiments/seasonal_color_tone_v01/Review.html`.

Dependencies: Python 3.11+, NumPy, SciPy, Matplotlib, Pillow; Shapely and pytest for checks. Source inputs, exact hashes, output statistics and verification results are documented in the output directory. Generation uses existing vectors/depth fields; it does not rerun terrain or plant geometry generation.

The review-only supplemental color guides after Spring are exact existing ink-source subarcs with a display envelope. They are neither canonical color vectors nor executable brush paths. The style sidecars reference original IDs and carry no physical pigment assignment. No production G-code is emitted.
