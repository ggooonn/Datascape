# Spring P2 Color — Hybrid Reload Revision v02

Continue exactly from PR43 commit 8f7b1bb0ec2cd0b9fee639f370afe3b0518fa92b. The preferred first test uses **600 mm OR 15 actual paper contacts**, with replenishment only after completing the current source.

This is a focused material-handling revision. All 3,947 selected sources, 40.017 m of drawing, six pigments, A2 → A4 → C1 → A5 → C3 → C2 order, source geometry/direction, artistic pressure, explicit compression factors, layer dependencies and original numerical paper XYZ/feed blocks remain unchanged. It remains the color overprint for the existing PR35 ink P2; no deferred ink detail is added. PR43 and all previous PRs are unmodified and unmerged.

## Primary programs

- [Complete HYBRID15 COLOR](review/SPRING_P2_COLOR_PR35_HYBRID15_COMPLETE_REVIEW.gcode.gz).
- [Matching HYBRID15 AIR](review/SPRING_P2_AIR_PR35_HYBRID15_COMPLETE_REVIEW.gcode.gz).
- [Reload/runtime comparison](review/reload_comparison.png), [contact-budget diagnostic](review/contact_budget.png), [source-preservation proof](review/PR43_preservation.json).
- Committed programs are lossless gzip; decompress before opening in UGS. The download package supplies ordinary numerical G-code, all numeric IR/material audits, Review.html and comparison CSV/JSON.
- Four numbered HYBRID15 COLOR/AIR pairs remain reference alternatives. Choose COMPLETE or stages01–04, not both on the same sheet. The inherited PR43 distance-only stage files remain untouched in their original directory.
- PR43's separate spare-hanji color-response coupon and station-only COLOR/AIR programs are included **byte-identically**.

## Actual contacts and counter behavior

A contact is one emitted initial_contact engagement with the paper. It is not a pressure vertex, source ID, palette dip, water visit or PURGE touch. A fragmented source can produce several contacts; this P2 workload has 3,947 actual contacts.

Both distance and contact counters reset to zero after every load, including the initial load, a same-pigment replenishment and an actual pigment change. Before starting the next source, reload if distance is at least 600 mm **or** contacts reach the configured limit. If a threshold is reached partway through a source, finish all of that source's fragments first. Both simultaneous triggers create one load. Atomic distance/contact overruns are explicit diagnostics.

Same-pigment replenishment uses only the existing target-palette loading/lip route; it does not wash, touch PURGE or rewet unnecessarily. A true pigment change retains one wash → PURGE → controlled rewet → target load. Existing terminal three-water/two-PURGE cleanup and park are unchanged and reported separately from pigment-change washing.

The generator's former distance-only assertion now accepts either None for the frozen legacy control or a positive integer contact limit. The v02 policy pins 15 as preferred and compares 20 and 30.

## Same-composition numerical comparison

| Policy | Total loads | Same-pigment replenishments | Pigment changes / washes | Maximum contacts since load | Maximum distance since load, mm | Modeled COLOR minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PR43 distance only | 69 | 63 | 5 | 110 | 626.828 | 84.713 |
| 600 mm OR 15 contacts, preferred | 266 | 260 | 5 | 15 | 395.395 | 120.316 |
| 600 mm OR 20 contacts | 201 | 195 | 5 | 20 | 515.217 | 108.553 |
| 600 mm OR 30 contacts | 134 | 128 | 5 | 30 | 609.744 | 96.570 |

Total loads include the initial load and five loads associated with pigment changes. For 15 and 20, all same-pigment replenishments are contact-triggered. For 30, 127 are contact-triggered and one is distance-triggered; finishing the intact source produces a 9.744 mm atomic distance overrun. Preferred 15 has zero distance or contact overrun in this workload. No source is cut to satisfy a threshold.

The conservative 15 candidate adds 197 load visits and 35.603 modeled minutes over PR43. This increase is material handling, with no extra artwork stroke, pigment change or concentration change.

| Slot, fixed physical order | 15-contact loads | 20-contact loads | 30-contact loads |
| --- | ---: | ---: | ---: |
| A2 | 104 | 78 | 52 |
| A4 | 40 | 30 | 20 |
| C1 | 28 | 21 | 14 |
| A5 | 53 | 40 | 27 |
| C3 | 7 | 6 | 4 |
| C2 | 34 | 26 | 17 |

Preferred COLOR time is 120.316 min; matching AIR is 73.282 min. COLOR breakdown: drawing10.748 min, paper engagement37.566, paper travel20.053, station handling27.654, station transfer24.294. Reference alternatives:01 mineral65.555 min,02 pale growth13.046,03 grouped cores27.427,04 fresh tips16.213; total122.242 min because each independent file cleans/parks.

All models retain PR43's recorded acceleration reference, assumed JD0.01/full lookahead, motion feeds and station primitives. Programmed station motions, dwells and cleanup are included; manual positioning/conditioning, paper drying, real streaming and brush dynamics are excluded. These are not measured durations.

## Preservation and physical scope

The revision checks the pinned PR43 selection index, full compressed source geometry/pressure record, source-to-slot assignments, source/pigment schedule, dependency graph and complete physical profile. Every numerical paper-pressure/XY/feed block matches PR43. A reconstructed distance-only control reproduces PR43's **entire complete COLOR G-code byte-for-byte**, validating the inherited path and station implementation.

The provisional color compression curve is unchanged: artistic pressure → compression0→0, .2→.3, .4→.7, .6→1.2, .8→1.8, 1→2.4 mm. It remains an unmeasured physical candidate. Its independent response coupon is preserved for spare backed hanji. No ink pressure curve is substituted.

Keep global P2 X300–600 and the same G54 registration, touch10 / approach15 / hover20, global transfers35, known start0/900/35 and park800/800/35/M2. No additional mounting/backing offset, machine/YAML/feed/station-reference change, routine M0 or fine-brush color stage is introduced. PR43's physical station/holder/lip and color-delivery uncertainties remain unchanged.

Additional loads can change the time between pigments, even though the protected color order is identical. Updated C1/A5 and other overlap lag diagnostics are included. They do not assert measured wet-on-wet mixing or paper drying.

For the first print, retain PR43 registration and the separate color-response coupon procedure, then use the complete HYBRID15 COLOR/AIR pair. The four-stage set is optional for inspection. Record dry tails before replenishment, excess liquid immediately after loading, color contamination, actual duration and any changed overlap appearance before considering 20 or 30 for a later test.

## Reproduce and verify

From the repository root, with pinned PR40/42/43 objects available and fresh output directories:

~~~sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_color_hybrid \
  --context /absolute/cache/color-context --output /absolute/hybrid-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_color_hybrid \
  --context /absolute/cache/color-context --output /absolute/hybrid-b
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_color_hybrid \
  --verify --context /absolute/cache/color-context --output /absolute/hybrid-a \
  --independent /absolute/hybrid-b --report /absolute/hybrid_audit.json
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 \
  DATASCAPE_COLOR_CONTEXT=/absolute/cache/color-context \
  DATASCAPE_COLOR_HYBRID_REVIEW=/absolute/hybrid-a \
  python -m pytest tests/test_gcode*.py -q
~~~

Executed validation:277 tests pass,2 inherited conditional fixtures skip, with both old PR43 and new hybrid delivered-program integration fixtures enabled. The old fixture additionally uses DATASCAPE_COLOR_REVIEW pointing to the original complete PR43 output directory. All85 generated files independently reproduce byte-for-byte.

Seven delivered COLOR/AIR pairs are read back against original source arcs, artistic pressure and fixed physical profile. An independent streaming audit counts initial_contact IR motions and actual XY drawing distance, validates every before/after/reset budget, both/individual triggers, complete-source service boundaries, no same-pigment wash, actual pigment washing and terminal cleanup/park. All four comparison workloads are independently rebuilt and retimed. Synthetic cases cover multi-fragment contact overruns, many vertices in one contact, distance-first and simultaneous triggers, a pigment change exactly at the limit, audit mutation, omitted replenishment and AIR correspondence.

The compact Git projection retains complete compressed programs, diagnostics and material audits. The download package also contains ordinary G-code, full IR/source records and the visual HTML review. Offline verification is numerical and does not certify physical machine clearance.
