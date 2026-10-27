# Spring P2 Color Execution v01

Complete numerical color experiment for the **existing PR35 ink P2**. This is a physically reviewable candidate, not a measured color calibration or a machine-clearance certificate. No ink, Spring source geometry, earlier PR, FluidNC YAML or installed machine configuration is modified.

## Read and download

- [Matched P2 comparison](review/P2_comparison.png), [actual pigment sequence](review/P2_sequence.png), [D4 comparison](review/P2_D4_comparison.png).
- Full contact job: [SPRING_P2_COLOR_PR35_COMPLETE_REVIEW.gcode.gz](review/SPRING_P2_COLOR_PR35_COMPLETE_REVIEW.gcode.gz).
- Matching full AIR: [SPRING_P2_AIR_PR35_COMPLETE_REVIEW.gcode.gz](review/SPRING_P2_AIR_PR35_COMPLETE_REVIEW.gcode.gz).
- All committed G-code is lossless gzip: **decompress before opening in UGS**. The Work download package contains ordinary complete G-code, seven COLOR/AIR pairs, the self-contained Review.html, layered SVG, full numeric IR, original unmodified color/ink vectors, all source decisions and reports.
- The four numbered stage pairs, station-only pair and spare-sheet response-coupon pair are also in review/. Run COMPLETE **or** the four numbered stages, not both.

## Exact references

| Purpose | Checkpoint |
| --- | --- |
| Physical ink already on the first P2 | PR35 c2464d65e2b2203f2e4b5912377eb33097987dbc |
| Development branch base; inherited backend | PR41 172601cbe9e19d013d159b9dc9cd64b985c1ae1f |
| Published later dual-brush compatibility | PR42, spring/p2-a-brush-hierarchy-v01, cf010e6f41de36baee83ed7a04cacbc3f0931e23, recommended B |
| Artistic roles, original Spring vectors/palette | PR40 cd3c61ae3a19bbb50d73a8c11bf82e5547e29a74 |
| Numerical color geometry and artistic pressure | Existing PR32 complete canonical plan and accepted Pressure Intent v01, checked by their existing hashes |

PR42 was verified during this Work. Its B allocation is985 main +224 fine +642 color-deferred. The current allocation comes from review_role: inherited variant_B fields still describe PR39 and incorrectly give1007/202 if used as the latest accounting. All1851 original P2 ink IDs and XY are matched. The642 deferred IDs already exist in ink on the first PR35 sheet; **zero are added** to this color program. The future manifest lists12 selective A and10 terrain-support fine transfers explicitly.

## Result and actual pigments

Of5972 canonical color sources intersecting P2,3947 are selected,2025 omitted, with40.017m drawing versus49.960m original. Original vectors, source IDs, direction, widths, artistic pressure and X300 clipping provenance remain intact. No new artwork stroke, gap connector, resampling or plotter dot is introduced. Whole short terrain episodes are omitted; the remaining longer original terrain flows remain continuous. RSU vegetation bodies retain their longest complete rays across existing branches, at near/middle/far caps4/3/2. This is a documented physical selection, not canonical artwork editing.

117 selected sources receive a separate0.65 execution-compression factor in crowded PR35 ink display-footprint proxies. This does not change their original pressure intent, simulate physical spreading, or reinterpret display alpha as pigment dose. The full source_selection ledger records every retained/omitted/weakening decision and original source/width/pressure hash.

| Order | Slot | Intended role | Sources | Drawing m | Loads |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | A2, light gray | Pale terrain/mineral base, far neutral | 1548 | 18.585 | 31 |
| 2 | A4, warm/apricot gray | Warm pale ground/rock support; earth replacement | 599 | 7.816 | 13 |
| 3 | C1, pale yellow-green | Underlying vegetation atmosphere | 407 | 2.604 | 5 |
| 4 | A5, green-gray | Muted vegetation/mineral grouping and celadon support | 787 | 6.604 | 11 |
| 5 | C3, jade green | Selected group cores | 102 | 0.677 | 2 |
| 6 | C2, yellow-green | Fresh group structure346 sources and protruding accents158 | 504 | 3.732 | 7 |

There are6 initial pigment visits,5 actual changes/washes,63 same-pigment replenishments and69 total loads. Replenishment uses inherited600mm distance-only policy at complete-source boundaries, not the fine ink450mm/10-contact policy. Maximum atomic distance overrun is26.828mm. No arbitrary contact cap or per-color change quota is introduced. Same-pigment replenishment never performs a full wash.

Primary D4 and D5 use are both zero. Retained D4 source groups map to A2/A4/A5 according to terrain/mineral/vegetation role and depth; the actual source-to-slot CSV/JSON is authoritative. D1/D2 terrain warmth is consolidated into A4; far A3 terrain becomes A2; strong C4 vegetation is moderated to A5. Original source swatches are retained for comparison. A separate offline D4 candidate restores only12 long near rock/ground paths,164.723mm, for a specific structural role. It is not included in the primary job and not an18-percent dilution interpretation. The standard six-slot coupon includes the candidate pale replacements; test a D4 sample separately before adopting it.

## Layering and material behavior

11619 local dependencies protect pale supports before muted cores, jade before fresh tips, and original within-slot overlapping/owner order. They use authored width envelopes plus0.25mm display guard, not measured wet footprints or a complete source2.5D occlusion certificate. The new artistic graph intentionally replaces the old purely S3a order for this experiment. No all-ink source order is changed.

The chosen C1/A5 authored group is moved toward the end/start of its two batches where protected order permits. Its related-pigment overlap is a **hypothesis**. Across all C1/A5 overlap edges, commanded-feed lags range57–1058s; no drying or pigment-wetness threshold is calibrated. C2 excursion candidates blocked by protected predecessors are not forced. Dry-over-dry is an inspection target; washing cleans the brush, not the paper. Stage files allow intentional inspection/drying without routine M0 inside a job.

## Physical numerical assumptions

The inherited mechanical reference is touch10 / approach15 / hover20, global travel35, G54 start0/900/35, end800/800/35/M2, XY X0–860/Y0–900; P2 artwork remains globalX300–600. Touch10 already includes the backing; no extra3mm offset. Verify the current homing/registration readback, especially after the reported axis problems. No YAML change is made.

Motion remains the PR35/41 profile: ordinary/return15000, loaded12000, draw6000, noncontact Z7000, contact/release and pressure Z cap2000mm/min, existing segmented departure/arrival policies. The older12000/9000 values are not silently restored.

A **separate unmeasured color curve** uses artistic pressure→compression:
0→0, .2→.3, .4→.7, .6→1.2, .8→1.8,1→2.4mm. It does not copy ink's12mm curve. Selected actual pressures are.22–.716768, giving paper Z8.449697–9.779, including explicit local factors. These are numerical trial targets, not measured stroke widths or proven pigment delivery. Change the color configuration and regenerate after spare-sheet observation if needed. Fine-brush color remains an offline candidate list; no unmeasured fine contact program is generated.

Palette XY, circle radius5, liquid6/dip5/floor1/exit8 are inherited nominal G54 references. Palette lip paths are the PR34 **record-only** X811→796 for A/C or X850→835 for B/D, at each slotY/Z28. This Work generates them as unverified review motions, first releasing to global35, traveling above the lip, then descending vertically. Holder/rim/bottom/immersion and connecting swept clearance require direct inspection; numeric envelope checks are insufficient.

Water uses the distinct container840/45/contact20/approach25, vertical20↔22 agitation, global35 before the790→775/Y45/Z25 lip. On an actual pigment change: wash→PURGE840/137.5/contact1.5→controlled rewet→target palette. Terminal cleanup is3 water visits,10s/3 vertical cycles each, PURGE twice4s, no final rewet, park/M2. The station-only contact/AIR pair isolates these routes for inspection.

## First print

1. Preserve the PR35 panel position; verify current G54, zero G92/TLO, mounted small brush and known start at0/900/35. Do not translate P2 toX0 or add backing thickness.
2. Inspect the Z35 holder/brush envelope, then run station-only AIR and complete AIR. AIR has every corresponding XYZ command flattened toZ35 and does not verify low immersion/lip clearance.
3. Inspect station contact traces and test COLOR_RESPONSE_COUPON_SPARE_ONLY on a **separate300×330mm backed hanji sheet** at globalX300–600/Y570–900. It supplies24 pressure lines plus a C1/A5 interaction pair. Never run this coupon on the existing artwork. Record touch, width, taper, delivery and wet/dry color; regenerate for a revised color curve when required.
4. Choose COMPLETE, or numbered stages01–04 with manual inspection/drying. Every separated stage starts with a clean conditioned brush, loads its own pigment, cleans/parks at the end and preserves the same artwork registration. Restore the known start pose atZ35 before the next file.
5. Record pale-ground strength, celadon/yellow-green hierarchy, lost ink, merges/dry tails, wash contamination,600mm replenishment behavior and actual duration. Use the first result to revise the future PR42-B sheet's color responsibilities.

## Runtime and S3a attribution

| Reconstructed workload, same trial mechanics | Sources | Drawing m | Changes | Loads | Modeled minutes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full original S3a / legacy slots | 5972 | 49.960 | 11 | 89 | 117.023 |
| Selected content / legacy slots | 3947 | 40.017 | 11 | 72 | 86.248 |
| Selected mapped slots / S3a ordering | 3947 | 40.017 | 5 | 69 | 84.523 |
| Proposed protected order | 3947 | 40.017 | 5 | 69 | 84.713 |

Content selection saves30.774min; slot consolidation saves1.726min; the protected order/local overlap arrangement costs0.190min. The improvement is mainly fewer short engagements, not just switching. These controlled reconstructions are not historical byte replays: all use this color curve and current container/palette/lip/cleanup mechanics.

Primary timing breakdown: drawing10.748min, paper engagement37.816, non-drawing paper travel20.531, station handling8.891, station transfer6.726. Full AIR is44.037min under the same reference model. Independent stages total86.639min because each cleans/parks:01 mineral47.914,02 pale growth8.817,03 grouped cores18.973,04 tips10.935.

Times use configuration-reference accelerations1500/1500/1000mm/s², assumed JD.01/full lookahead, programmed dwells and stations included. Manual positioning/conditioning/drying, finite streaming effects and real brush dynamics are excluded. They are not measured physical durations.

## Reproduce and verify

Use a full clone containing the pinned PR40 and PR42 objects. No device connection is made.

~~~sh
git fetch origin study/seasonal-color-tone-v01 spring/p2-a-brush-hierarchy-v01
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_color_execution \
  --context /absolute/cache/color-context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_color_execution \
  --context /absolute/cache/color-context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_color_verify \
  --context /absolute/cache/color-context --output /absolute/review-a \
  --independent /absolute/review-b --report /absolute/delivered_audit.json
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 \
  DATASCAPE_COLOR_REVIEW=/absolute/review-a DATASCAPE_COLOR_CONTEXT=/absolute/cache/color-context \
  python -m pytest tests/test_gcode*.py -q
~~~

260 tests pass;2 inherited conditional fixture tests skip. Seven COLOR/AIR program pairs independently parse every XYZ/feed/dwell, original-segment XY/pressure interpolation, source coverage/direction, registration, Z/feed bounds, material changes/reloads and terminal cleaning/park. Stage IDs concatenate to exactly the complete order with no duplicates or omissions. All117 generated artifacts reproduce byte-for-byte in a separate run;39 PNGs decode. Numeric mutation tests reject altered coordinates, AIR descent and extra pauses. The delivered audit records actual image count and manifest hashes.

Git retains compact ledgers/previews, all14 complete compressed programs and readbacks. Full IR, all original-source selection geometry, original vectors, layered SVG and self-contained HTML are in the Work package and regenerated by the commands above. Inherited files remain byte-identical; no earlier PR is merged or modified.
