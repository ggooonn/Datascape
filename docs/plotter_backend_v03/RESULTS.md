# Executed v0.3 results — automatic A/D workflow correction

The update remains on Draft PR #27, following `3202f875b02fa454248a64c4d62529b2885d66e4`.
No Spring geometry, pressure, S3a order, physical calibration curve, station
primitive, controller configuration or earlier PR is changed. No hardware runs.

## Software and source verification

- **63 tests passed**, one legacy environment-gated full-scene unittest skipped.
  The focused correction adds nine behavioral tests, while retaining earlier
  regression and air/calibration/painting gate tests. Full Spring verification
  is separately executed below; the skipped unittest is not counted as a pass.
- Accepted binding validates **14,951 original strokes / 240,974 samples**.
- **D is the preferred first printing mode:** two jobs, `SHARED_INK` (3,345 paths)
  and `SHARED_COLOR` (11,606 paths). Full preparation and actual compressed-plan
  read-back verify every original point/pressure sample, original direction,
  segment provenance and G54 transformation. There are **14,951 unsplit paths /
  240,974 samples**, with complete source partition.
- All **50 original X=300 crossing sources / 616 crossing pressure samples**
  remain continuous in D. Each has one original drawing run with no seam lift,
  reload, pause, extra vertex or fragment boundary. D's full-plan digest is
  `8b4804f561f0eaab28753ae1790ce3b0f5b9ab8ba9a4a2ffe1e4daecbe2596bd`.
- A retains four jobs at the same independently mounted G54 paper origin:
  P1 ink/color **1,494 / 5,684**, P2 ink/color **1,851 / 5,972** fragments;
  **15,001 fragments / 241,074 samples**. The previously verified A source-plan
  digest remains `c9380e0b7c3967d1a8622dfa83974a568e2d1b2a67987dba479f348a66d9e074`.
- Full A/D recalculation validates both serialized plans and every actual
  trajectory pressure sample. Synthetic A/D examples exercise successful
  serialization, delivered-file read-back, exact final park/M2 and zero M0.
  Real Spring G-code is never serialized using the synthetic cost profile.
- A continuous sheet or tightly adjacent sheets are supported by D. Actual
  adjacent sheets require explicit assembly selection, pre-run confirmation and
  current `continuous_seam` physical contact/clearance evidence. B/C physical
  serialization stays blocked; their existing planning support remains intact.

## Exact material counts at ink 1,000 mm / color 800 mm

Reloads exclude the initial load of each material/color job. Active distance
resets on fresh load/change/wash/restart. Threshold overruns finish the complete
original source and reload before the next source; no same-material wash occurs.
Different colors wash automatically; startup and final cleanup are not counted
because the operator confirms a prepared brush and default end_cleanup is false.

| Layout/job | Ink reloads | Color reloads | Total loads incl. initial | Color changes / full washes | PURGE contacts | M0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P1_COLOR | 0 | 52 | 64 | 11 | 11 | 0 |
| P1_INK | 40 | 0 | 41 | 0 | 0 | 0 |
| P2_COLOR | 0 | 56 | 68 | 11 | 11 | 0 |
| P2_INK | 44 | 0 | 45 | 0 | 0 | 0 |
| **A total** | **84** | **108** | **218** | **22** | **22** | **0** |
| SHARED_COLOR | 0 | 114 | 126 | 11 | 11 | 0 |
| SHARED_INK | 83 | 0 | 84 | 0 | 0 | 0 |
| **D total** | **83** | **114** | **210** | **11** | **11** | **0** |

A has slightly fewer same-color reloads despite two more ink/color sessions:
independent panel/color batch endings discard residual load distance. This does
not mean less pigment consumption. D has fewer washes, load starts and transfers,
while preserving the uninterrupted original cross-seam strokes.

## Conditional station travel and time — not measured physical duration

`cost_scenario.synthetic.json` is deliberately a synthetic fixture. It assumes
the old `tool_coordinates.yaml` XY frame is G54, retains nominal PURGE X840 Y137.5,
and invents +/-15-mm stone withdrawal offsets around nominal centers. All Z,
immersion, brush curve, dwell, contact and dynamic values remain unit-fixture
assumptions, not measured or recommended hardware settings. The nominal XY file
SHA256 is `eb781167ed386d8b6a5f8aae9cb652b776ee152e389aa39b8025356d63f194ec`.

Station transfer includes paper-to-station, inter-station, station-to-paper and
station-to-park travel, including associated clearance/hover changes; station
contact/loading/retraction is separately recorded. Actual physical station travel
and full job duration remain **null** until measurements exist.

| Layout | Scenario station transfer | Scenario all non-drawing 3D | Commanded-feed model | Stop-each-segment model |
| --- | ---: | ---: | ---: | ---: |
| A | 338.345 m | 1,016.998 m | 28.397 h | 47.732 h |
| D | 259.644 m | 976.938 m | 27.955 h | 47.193 h |

These two models are not verified physical bounds. In particular the inherited
synthetic contact feed of 120 mm/min also governs the 10-to-1-mm paper approach,
contributing about 18.7 h by itself. Do not interpret the roughly 28-h subtotal
as the expected calibrated painting duration. Measured approach/contact dynamics
and station data must replace those assumptions before a physical time claim.
Drawing feed is 5,000, ordinary travel 12,000 and wet travel 9,000 mm/min in this
scenario, with the existing synchronized-XYZ axis caps. Manual preparation,
between-program review/drying and fixture changes remain unestimated.

The focused A/D preparation, read-back and material/cost run took **77.39 s** in
this Python run, without G-code serialization, a scheduling search, artwork
regeneration or pressure recomputation. See `review/A_D_cost_recalculation.json`
for per-job counts, overruns, time categories and continuous-source diagnostics.

## M0 accounting

**Every standard A and D ink/color job: 0 M0, reasons [].** Air also has zero
routine M0. Pre-run confirmations replace startup verification pauses; color
begins with its first pigment load from a manually confirmed clean/prepared state.
No forced initial cleaning or mandatory end cleaning remains. Final motion is
exact configured park, followed by M2. Optional end_cleanup=true adds washing,
not a final pause.

Periodic manual water/refill checks default to null (disabled). An explicit
positive interval opts in after completed operations; its actual count and every
reason appear in metrics and independent read-back. No routine pause is hidden
in same-color reload, full wash, PURGE or next-pigment loading.

Small explicitly requested calibration programs keep `2 + 2R + L` intentional
M0 commands: startup verification, pre/post station inspection (R roles), pre-line
brush preparation (L lines), and final recording. The retained one-role/one-line
calibration test has **5** M0 with these exact reasons. These are not production
painting programs.

## Actual pressure distribution and calibration implication

The accepted sidecar's explicit family labels were checked against every bound
ID/sample. Selected distributions below use original vertices, not clipped seam
samples; complete 15-family values are in
`review/pressure_distribution_by_accepted_family.json`.

| Medium / accepted family | Samples | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Ink A | 43,938 | 0.387 | 0.540 | 0.605 |
| Ink B | 1,839 | 0.392 | 0.542 | 0.625 |
| Ink D | 1,545 | 0.614 | 0.812 | 0.930 |
| Ink rock | 3,209 | 0.619 | 0.642 | 0.745 |
| Ink trunk | 3,248 | 0.440 | 0.580 | 0.684 |
| Ink branch-foliage | 4,610 | 0.251 | 0.382 | 0.471 |
| Color A-color | 64,374 | 0.266 | 0.423 | 0.492 |
| Color rock | 2,783 | 0.568 | 0.643 | 0.717 |
| Color mid-far-vegetation | 90,285 | 0.220 | 0.291 | 0.407 |

These data support testing a gentle low-intent region, expressive ordinary A
response and a separately observed stronger D/rock response. They do not determine
physical depths. Preserve .4 and .6 as provisional comparison markers; measure
low vegetation around .27–.35, ordinary ink A around .49–.58 and ink D around
.67–.87 before choosing finer knot positions. The accepted largest intent .93
need not use the maximum physical compression. A multi-knot curve can separate
these responses without changing any original pressure. Final Z knots await
width/continuity/recovery measurements on the intended mounted paper.

## Remaining physical inputs and version boundary

All existing calibrated-pressure domain/context, collision-envelope, acceleration,
Z/XYZ rate, profile/evidence and stage authorization gates remain active. Pre-run
operator confirmations are now required before starting, including coordinates,
starting position, paper/clearance, controller/tool state, prepared clean brush,
adequate pigment/water, ink drying/registration before color, and the D substrate
or seam decision. The software never observes those conditions automatically.

The supplied profile remains unverified. Missing installed controller/XYZ/G54
measurements, safe paper/station Z, physical brush knots/observations, station
contact parameters, clearance/park tests and current hardware evidence still
block real Spring export. PURGE X840 Y137.5 and its 70x70-mm nominal area do not
approve G54 registration or gentle compression Z. No -12-mm or liquid-level
fallback is introduced. Materials may be prepared/replenished externally without
a routine machine wait; no automatic liquid sensing exists.

Coordinates, reload intervals (including a later color 1,000-mm trial), station
compression/dwell overrides, physical pigment order, brush knots and measured
motion parameters remain v0.3 configuration. Optional new sensing/feedback,
kinematics/dialect, station primitives or evidence-driven PCHIP need focused code
work only if requested. This correction does not start a v0.4 project.
