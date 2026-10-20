# Plotter Backend v0.2 — pressure-aware offline integration

Level 1 only. Extends PR #23 without merging any artwork or pressure PR. All
Spring XY, widths, IDs, vertex directions, ordering, colors/slots and accepted
pressure remain frozen. No controller connection, runnable machine job, active
FluidNC configuration change, homing, station contact motion or physical test.

- [Source audit](AUDIT.md)
- [Reproduce](REPRODUCE.md)
- [Executed results and layout comparison](RESULTS.md)
- [Calibration and future hardware handoff](HANDOFF.md)
- [Full machine-readable report](review/full_scene_summary.json)
- [Actual Spring 3D trajectory review](review/spring_3d_review.html)
- [Calibration patterns](review/calibration/benchmarks.svg)
- [Calibration trajectory review](review/calibration/benchmarks_3d.html)

## Separation of responsibilities

| Representation | Authority / meaning |
| --- | --- |
| Frozen artwork | PR #24; top-left, X-right, Y-down, 600 × 900 mm |
| Artistic pressure | PR #25 sidecar; normalized intent, unchanged |
| Bound vectors | PR #25's existing adapter, verified before clipping |
| Source fragment | Original segment/fraction/arc provenance, never panel-normalized |
| Desired brush behavior | Approach, first contact, pressure interpretation, release, lift |
| Preview work trajectory | G54 frame, optionally **invented** nonlinear Z for visualization |
| Calibrated work Z | Absent in Spring review; future brush-specific measured profile |
| Machine trajectory | Absent; no verified G54-to-machine offset/envelope |
| Controller output | Unimplemented; Levels 2 and 3 explicitly rejected |

`artistic_pressure`, `desired_behavior`, `preview_z_mm`, `calibrated_z_mm`, and
`machine_xyz` are separate event fields. No physical force, actual width,
pigment concentration or safe compression is inferred from artistic pressure.
Absent calibration produces unresolved draw Z, never a generic pressure fallback.
The optional synthetic visualization uses an invented 0..-1 mm curve, not the
legacy v0.1 -12 mm illustration and not an approved hardware range.

## Modules and extension points

- Existing `models`, Liang-Barsky `clipping`, strict `io` and opt-in `scheduling`
  are extended. The legacy v0.1 preview API remains available for regression;
  it is not used by v0.2 and still has its explicitly uncalibrated old mapping.
- `binding`: Spring-specific pinned checks and invocation of the existing PR25
  adapter in a separate source checkout. No copied pressure synthesis/adapter.
- `layout`: artwork → panel local → configurable G54 work frame. Optional
  registration translations/rotations and separate measured machine offset.
- `motion`: reusable fragments, events and physical contact/release interpretation.
  Default source traversal never calls nearest-neighbor scheduling or reversal.
- `calibration`: brush identity/context, observations and nonlinear curve knots.
- `stations`: non-spatial logical operations, brush-state simulation and deferred
  reload thresholds; station contact remains disabled even with measured data.
- `estimation`: distances, contacts, Z travel and two explicit time models.
- `validation`: complete original-segment partition and pressure/XY/arc checks.
- `review` / `offline`: benchmarks, review assets and reproducible integration CLI.

General modules accept `Stroke` records and `Layout`/`MotionSettings` objects;
Spring hashes/counts are confined to the binding/validation entry point. Future
seasonal generators can provide the same strict vector contract with explicit
pressure and their own verified provenance boundary.

## Seam, fragment order and output streams

Positive-length paths lying exactly at X=300 belong to **P1**. P2 excludes only
segments exactly on that boundary. A true crossing has an endpoint on each
physical edge; its positive-length source intervals are partitioned exactly
once. There is no epsilon-width seam deletion, minimum-length filter, smoothing,
pressure renormalization or reconnection across omitted intervals.

Each fragment carries canonical source ID, unique fragment ID, original
sequence/order group, medium/slot, accepted sidecar SHA, per-vertex original
segment index/fraction/arclength and per-segment spans. Frozen rich widths/source
records remain referenced by the canonical binding provenance; they are not
reinterpreted into a physical brush footprint. Interpolated boundary pressure
uses the exact same original segment parameter as XY.

Layout A consists of independent P1 and P2 setups. Each setup is a projection of
the original source order (P1 ink/color, then P2 ink/color); there is no meaningful
global single-machine sequence spanning a paper replacement. B/C have one setup:
original stroke sequence and original within-stroke fragment traversal are both
preserved, including right-to-left crossings. D retains unsplit full-width paths.

For A/B/C, four independently identified streams are written: `P1_ink`,
`P1_color`, `P2_ink`, `P2_color`. Each has compressed fragment records, full
motion events, commented preview text and a work-frame SVG. `setup_order.jsonl.gz`
is the authoritative fragment interleaving manifest; **do not concatenate all
P1 records before P2 in a shared job**. Each fragment's events must run contiguously.
D produces `FULL_ink`/`FULL_color`. Logical station operations reference the next
fragment separately and never silently move the brush.

All inter-fragment travel follows a release and illustrative lift, including
travel across a physical gap. No drawing segment spans the gap. Centerline
containment is proven; actual brush footprint, mounting edges and hover clearance
remain unmeasured and are not physically validated by this preview.

SVG transforms work Y-up to display Y-down exactly once. Review green denotes
color-medium centerlines, not a re-rendering of the frozen 20-color painting or
an ink/gouache deposition prediction. Slot assignments remain exact in records.
