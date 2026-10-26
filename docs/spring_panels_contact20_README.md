# Spring P1/P2 contact20 review

Based on PR34 commit9665b92a7ab78ce44a135c191eb6c259a3cb03f6. INK only,
single pass. Original artwork, pressure, widths, source order and material
allocation remain frozen. No controller, YAML, feed, acceleration, station or
G54 changes. Keep Draft; do not merge.

Selected budget800mm OR20 actual paper contacts, independent light/dark counters,
reset on load, original sources atomic. Comparisons12/15/distance-only are
numerical controls; distance-only is not recommended physically.

P1 globalX0–300, P2 globalX300–600; no translation or exhibition gap. P2 paper
must physically occupy globalX300–600. Each program assumes prepared brush/inks,
registered G54 start0/900/35, terminal800/800/35/M2. No startup homing or offset
write. Never apply both panel and combined programs to the same paper by accident.

Boundary audit:3345 original ink sources,69101 pressures; P11494/32553,
P21851/36548. No original strictX300 crossings;270 sources touch the boundary.
Three approved D joins connect separate source endpoints onX300. Combined keeps
all three; independent panels separate contact ONLY at those existing endpoints.
No canonical path is split or changed.352 cross-panel temporal footprint edges
cannot be enforced between independent jobs. Internal protected precedence and
restricted PR34 order remain. No new joins, optional repeats or artistic changes.

Complete numeric G-code is committed losslessly as gzip. Decompress before review;
never send compressed bytes to a controller. Full downloadable package includes
ordinary G-code, numeric IR, station/reload manifests, SHA256 and previews.

P2 loads/time:12 contacts168/109.745min;15 contacts142/101.739min;
20 contacts116/93.655min;distance-only70/79.510min. All retain22 concentration
changes/full washes plus3 terminal water visits. P120:100loads/84.368min;
combined20:207loads/173.875min versus PR34 full12:301loads/204.226min.
Timing uses unchanged acceleration reference and assumedJD0.01/full lookahead,
includes stations/dwells but excludes manual M0 wait, drying and real controller
uncertainty. Detailed modeled categories and atomic overruns are in RUNTIME.md
and P2_reload_runtime_comparison.json. No station routines were removed for speed.

Confirmed small Baegunmo touch10/approach15/hover20, no extra3mm backing offset.
Pressure mapping unchanged and unclamped: max10.2mm compression/Z-0.2, safe
small-brush range still unmeasured. Water840/45/Z20, existing cloth/wells/lips
unchanged. Container bottom/holder/agitation/lip/connecting swept clearance and
registration remain to verify. Contact jobs begin M0 before movement; this is
NOT a safety interlock or machine authorization. AIR allZ35 is not a collision
certificate.20-contact depletion/width requires the next physical P2 benchmark.

## Reproduce

Use the same Python dependencies as docs/spring_physical_ink_v01/README.md.
From repository root, with fresh absolute directories:

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_panels_contact20 --context /absolute/context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_panels_contact20 --context /absolute/context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_panels_contact20 --verify --context /absolute/context --output /absolute/review-a --independent /absolute/review-b
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

Frozen rich ink/F2 context is recovered by hash-bound git objects. No artwork
regeneration. PR34 SELECTIVE_LAYERED code/config remain inherited, optional and
unchanged; supplied jobs contain no repeats.236 tests pass,2 existing conditional
fixture tests skipped. PR34 full12 numeric program reproduces byte-for-byte.
