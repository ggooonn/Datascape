# Executed results and layout comparison

## Full-scene integrity

- 14,951 original strokes: 3,345 ink and 11,606 color.
- 240,974 accepted artistic samples, canonical sidecar and bound payload verified.
- Split layouts: 15,001 fragments, 241,074 fragment samples, 331,080 motion events.
  Fifty source paths cross the seam; boundary samples are interpolated rather
  than synthesized or panel-normalized. D retains 14,951 unsplit paths.
- Original drawing distance: **184.618402 m**; complete segment-parameter partition
  and clipped length agree within floating-point tolerance.
- P1 ink **1,494**, P1 color **5,684**, P2 ink **1,851**, P2 color **5,972** fragments.
- Every original ID, pressure, XY value, direction, material slot and ordering lock
  is bound before clipping. All clipped XY/pressure/arc locations are verified.
  Shared setups additionally preserve original within-stroke traversal.
- Full Backend suite: **20 tests passed**, including the pinned complete Spring
  integration test. Original PR25 adapter suite: **3 tests passed**, including
  malformed/corrupt binding subcases. No GitHub CI or hardware testing is claimed.
- Read-back of actual compressed outputs verified **27 manifest entries**, all
  **15,001 fragments / 331,080 events / 241,074 fragment pressure samples**,
  original-source interpolation, setup-order coverage and **331,084 comment-only
  preview lines**. Physical calibrated-Z/machine-XYZ fields are all absent.

The full pipeline took **32.41 seconds**, with process peak RSS **250.05 MiB**
in this Linux/Python run, including input parsing and selected-layout output.
This is an observed software run, not a performance guarantee. A 32-stroke
subset and explicit constant/unresolved-depth subsets were exercised first.
No artwork or pressure generation was rerun.

## Simulated layout comparison

Nominal zero-offset registration examples below are for software comparison,
**not confirmed starting positions or available physical work areas**. All modes
preserve the continuous 600 × 900 mm composition. No 40-mm exhibition gap enters
painting coordinates. Registration offsets and rotation remain configurable.

| Mode | Paper footprint (mm), excluding margins/fixtures | Non-drawing XY (m) | Nominal feed model (h) | Stop-each-segment model (h) | Logical washes |
| --- | --- | ---: | ---: | ---: | ---: |
| A | 300 × 900 per setup | 412.909 | 6.37 | 20.00 | 8,881 |
| B | 600 × 900 shared | 541.118 | 6.73 | 20.36 | 8,827 |
| C | 650 × 900 shared (50-mm gap) | 603.827 | 6.90 | 20.57 | 8,827 |
| D | 600 × 900 one piece | 541.118 | 6.72 | 20.34 | 8,827 |

All modes draw the same 184.618 m. Times exclude stations, first positioning,
manual checks/refills, drying and setup changes. Feed assumptions: drawing1,200,
XY travel6,000 and Z600 mm/min; XY/Z acceleration100/50 mm/s². These are assumed
inputs, not nominal YAML max rates or measured operating settings. Z uses the
invented nonlinear preview curve and hover; the two time models are neither
proven bounds nor calibrated machine job durations. Estimated station travel is
**null**, not zero.

| Mode | Transform without rotation | Operational benefit / cost | Critical unresolved measurements |
| --- | --- | --- | --- |
| A — provisional software default | P1 x=x_art; P2 x=x_art−300; y=900−y_art | Small per-setup footprint; independent registration and station access studies. Paper swap and registration repeatability are extra work. | True panel placement, margins, head/fixture and station clearance; two-setup repeatability and swap time. |
| B — adjacent shared setup | x=x_art; y=900−y_art; panel membership retained | One setup and common seam registration. Source-order traversal crosses between panels; no implied route improvement. | Full 600-mm span, independent paper edges, seam accuracy, usable Y, head/fixture clearance, station accessibility. |
| C — shared physical gap | P1 x=x_art; P2 x=x_art+gap; y=900−y_art | Leaves a configurable mounting channel. Preserves source seam geometry; adds lifted inter-panel travel. | Full 650-mm span for gap50, gap/fixture height, right-hand station travel, paper/brush overhang and safe lift. |
| D — one-piece substrate | x=x_art; y=900−y_art, no panel clipping | No physical seam or duplicate seam contacts. Requires a different single substrate/fixture. | One-piece availability, flatness, mounting and 600-mm head/fixture/station access. |

A remains the software default because it retains the original independent
panel workflow while allowing measured configuration later. B/C/D remain
available; none is physically validated. Nominal X900/Y960 and stations near
X840–847 do not establish actual panel starting X, collision-free travel or safe
station access. Brush footprints and fixture/edge overlap are not inferred from
centerline clipping.

## Main operational finding: source-locked color transitions

The shared-order simulation makes **8,827 logical material changes/washes**
(8,826 color-to-color changes plus ink-to-color). Two independent panel projections
make **8,881**. The candidate wash→wipe→rewet→load policy, with invented
20+4+2+4-second durations, yields roughly **73.64 h** of operations in B/C/D and
**74.09 h** in A, excluding station travel and manual work. This is a stress-test
of a naive policy, **not a prediction of actual painting time**.

It identifies an important future material-handling constraint. No color grouping,
reordering, reversal, palette reassignment or multi-brush change is performed.
Resolve artistic sequencing permission and experimentally measured contamination/
wash requirements in a later Work before claiming a practical job schedule.
Same-color load intervals are placeholders and do not split long original strokes.

## Preserved review assets and remaining limits

Interactive actual-fragment 3D review, four full centerline SVGs (gzip), the
machine-readable report, tests/read-back report, 19 calibration patterns and
structured recording/station templates are in `review/`. Preview color is only
ink-versus-color distinction; original palette slots remain authoritative in
records. Complete event/provenance streams regenerate with REPRODUCE.md rather
than duplicating large derived archives in this PR.

No physical Z range/curve, contact dynamics, feed/acceleration, wetting, brush
footprint, station coordinate frame/well mapping or safe restart is calibrated.
Air Run and painting stay blocked. See HANDOFF.md for the next measurements and
PR25's accepted pressure limitations; they are not silently corrected here.
