# Accepted diagnostic limitations

These findings are deliberately preserved as review/calibration items. Publication does not silently modify the accepted parameters.

- **3,277 strokes** have some family-bound clipping: 3,154 middle/far vegetation, 121 branch/foliage and 2 D. There are 8,444 clipped vertices. Most vegetation clipping occurs at entry/exit; five middle/far strokes have clipping in the middle half of arclength, and two have an exact-bound plateau over half their path length. These are statistical phases, not semantic canopy/trunk occupancy or physical contact duration.
- **507 nearly flat profiles** have pressure span below 0.01. They include 28 paths at least 2 mm long with relative source-width span above 0.10. None is exactly flat at the study threshold of 1e-6.
- **D hierarchy is estimated.** Eleven original support-event cohorts and preserved source-world height/local relief approximate mountain masses and within-mass peak hierarchy. They are not authoritative authored mountain-mass IDs. Valley semantics and local terrain attachment are also estimates; see `context_audit.json`.
- Distant vegetation at **0.22** may not make a distinct mark with every physical brush. Preserve the artistic value for subsequent brush/medium calibration; do not assume a linear conversion to compression or Z.
- Physical width, pigment darkness/concentration, wetting, feedrate, contact response and Z depth are **uncalibrated**. Display opacity is not physical pigment concentration. The proposed 12 mm compression from older Backend previews is not an approved limit or mapping.
- One adjacent pressure delta is greater than 0.12 (0.120137 over 8.302 mm, gradient 0.014471/mm). No delta above 0.08 occurs within a segment at most 1 mm long, and no gradient exceeds 0.10/mm. Use continuous interpolation, not a pressure step or dwell. This is a geometric audit, not a physical time/acceleration check.
- The frozen vector baseline still carries its existing sub-mm and expressive-width paths. Pressure does not resolve brush-specific execution of width/taper. No new contact/dot primitive, dwell or hardware behavior is invented.

The 675 historical normalized profiles remain unchanged in PR #24 for provenance. All are recomputed in this sidecar. Their median within-stroke span changes from 0.848129 to 0.154262; none of the 675 new profiles is identical to its historical experimental profile. Numerical equality of an occasional sample to 0.5 is not evidence of fallback; profile origin and complete ID/vertex binding determine provenance.
