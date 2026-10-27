# Datascape — Seasonal Color Framework & Tone Review v01

Open **[Review.html](Review.html)** after extracting the complete package. The study continues PR38 at `6e331beb7e405cff55feb0ea9f3982808976f907`. It adds display studies and source-ID sidecars while preserving every baseline file. It does not redesign scenes or produce G-code.

## Review first

1. [Eight-panel stronger theme](P1_P8_theme.png), [ink-led option](P1_P8_ink_led.png), [matched-renderer before/after](P1_P8_before_after.png).
2. [Role and tone framework](framework_ribbon.png), [ink only](P1_P8_ink_tone.png), [color only](P1_P8_color_only.png).
3. [P2 D4 options](P2_D4_comparison.png), [foreground scaffold evidence](foreground_scaffold_review.png), [existing source views](source_view_evidence.png).
4. `P1.png` through `P8.png`; each season folder also contains pair, separated ink/color, control, quieter and provisional material-context images.

Read [FRAMEWORK.md](FRAMEWORK.md), [DISTINCTIVENESS_REVIEW.md](DISTINCTIVENESS_REVIEW.md), [FOREGROUND_RECOMMENDATIONS.md](FOREGROUND_RECOMMENDATIONS.md) and [SPRING_P2_HANDOFF.md](SPRING_P2_HANDOFF.md).

## Completion versus acceptance

**Technically completed:** all eight display-intent studies, continuous three-role palette, seven transition rules, tone cohorts, D4 comparison, source audits, source-ID sidecars, read-only identity review and P2 handoff. All canonical scenes and approved Spring geometry remain frozen. Supplemental color-territory guides after Spring are review-only exact source subarcs, not production color geometry.

**Provisional:** color anchors, display gains, ink-tone targets, unmeasured material backgrounds, artistic seasonal distinctiveness and the proposed foreground adjustments. No physical pigment schedule, concentration, calibrated dose, production path assignment or G-code is delivered. Foreground form changes are **proposed, not applied**.

## Reproduce

In the full repository checked out at the study commit, install `numpy scipy matplotlib pillow shapely pytest`. Run:

```bash
OPENBLAS_NUM_THREADS=1 python3 studies/seasonal_color_tone_v01/generate.py
python3 -m pytest -q tests/test_seasonal_color_tone_v01.py
python3 studies/seasonal_color_tone_v01/verify.py
```

For one season use `--scene spring|summer|autumn|winter`; after all four use `--finalize`. Source vectors and saved depth fields come from PR38, not from a regenerated DEM or new viewpoint search. `reproducibility_manifest.json` pins all used inputs, including config, camera/placement, depth fields, palette, skyline and archived reference. `verification.json` records independent checks. PNG bytes may vary with renderer/font versions; style and guide JSON are deterministic. The extracted review package is self-contained for visual review; full regeneration additionally requires the pinned repository inputs.

Canonical input paths: `artworks/spring_v13/visible_{ink,color}.json.gz` and `docs/experiments/{summer_composition_v03,autumn_composition_v01,winter_composition_v01}/{ink,color_intent}.json.gz`. The new output folder contains style references, not replacements for those canonical vectors.

All public documentation, comments and commit messages are English. No earlier PR is merged or changed by this additive study.
