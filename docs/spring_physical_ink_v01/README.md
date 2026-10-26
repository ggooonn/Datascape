# Spring Physical Ink Refinement v01

Complete numerical Spring INK/AIR review output, based directly on PR32 commit
`eda6069b12c8785d458a0e8a567a9a86980bc394`. Keep Draft; do not merge. Existing PRs,
source artwork, approved Pressure Intent, configuration/YAML and old jobs remain
unchanged. No controller operation or physical validation was performed.

## Confirmed mounting versus unresolved calibration

Small Baegunmo is mounted on operator-confirmed3mm wooden-backed paper with G54
first-touch10, approach15, hover20. No additional3mm offset is introduced. PR32's
pressure/compression knots remain0:0,.20:1,.40:3.5,.60:5.8,.80:8.2,.93:10.2,1:12mm.
Original ink pressures are unchanged; maximum mapped compression10.2mm reaches
Z-0.2. This is the inherited NUMERICAL comparison, not a measured safe range for
the small brush. Per-source calibration audit flags the missing range. No
clamping, resampling, depth normalization or invented passed observations.

Each contact-capable review program has one initial M0 before any movement.
This is a calibration/review gate, NOT a safety interlock or permission to resume.
Verify actual safe small-brush compression and new-container/holder connecting
clearance before considering contact. AIR has no contact or M0 and all moves are
Z35; inspect its elevated swept envelope, actual registration and machine state
before running it. A program cannot recover lost steps or an unknown G54 state.

## Complete files

Committed `review/*.gcode.gz` are lossless complete numeric programs. Decompress
before inspection or use; do not send gzip bytes to a controller. The downloadable
review package also contains ordinary `.gcode`, full numeric IR, all reports and
previews. No color program is generated.

1. `STATIONS_AIR_FIRST_REVIEW`: standalone elevated water/cloth/well/lip validation.
2. `SPRING_INK_FULL_AIR_REVIEW`: complete XY/dwell correspondence to selective
   layered INK, projected entirely atZ35 and re-capped for projected axis feeds.
3. `SPRING_INK_SINGLE_PASS_REVIEW`: all3345 original ink paths, same execution
   refinements, no added overprints; recommended first ink comparison after gates.
4. `SPRING_INK_SELECTIVE_LAYERED_REVIEW`: complete3345 originals plus34 explicit
   light repeats (11 middle/23 far); no near repeats, no dark doubles.
5. `TERRAIN`, `TREES`, `ROCKS` `INK_CROP_REVIEW` and `AIR_CROP_REVIEW`:30 intact
   original paths each, at ORIGINAL G54 coordinates. Not translated/scaled to
   a330mm sheet. Do not run crop/full jobs on the same artwork unintentionally.

Full programs independently expect G54 start(0,900,35) and end(800,800,35)/M2.
No homing, G54/G92 change, negative-X overtravel or configuration write occurs.
Do not chain files from an unknown start or assume the previous park is their
initial location. Registration/clean brush/material preparations are required.
Separate all-light/all-dark complete stages are omitted: filtering them into
successive programs would break protected mixed-concentration precedence.

## Material and path policy

- Original allocation:2341 light /1004 dark (69.985/30.015% by source);61,793.174mm
  light /26,489.690mm dark (69.995/30.005% by drawing length). A remains70.07%
  light by count and75.08% light by length. All14 D accents use dark ink.
  Allocation is contextual elevation/curvature/structural ranking plus count/
  length balancing, not alternating dark/light stripes. Family details are in
  `brush_path_audit.json`; changes are material assignment only.
-800mm OR12 actual PAPER engagements, independent LIGHT/DARK budgets, reset both
  counters after loading. A source or joined gesture is atomic; X300 never causes
  a source split. Record distance overruns rather than interrupting a stroke.
  Selected layered job:303 total loads =1 initial +280 same-concentration
  replenishments +22 concentration changes. Max12 contacts; maximum atomic
  distance overrun194.745mm (994.745mm accumulated). Single pass:301 loads and
  maximum355.902mm overrun.15-contact comparison is separately logged, not adopted.
- A light/light parity uses a nearest-contour spanning forest and protected
  dependencies.659 adjacency pairs: median execution rank separation7→17.
  No guarantee of drying. Original parent-contour fragments retain their order.
  Near-to-far is a preference among eligible nodes, never a hard override of
  protected source/occlusion order. The footprint DAG is conservative authored-
  width evidence, not a complete calibrated wet-brush compositing model.
-34 repeated light paths are independently controlled by middle/far fractions;
  predecessors finish before repeats, repeats before protected later originals.
  Set both fractions to0 for no repeats. Dark doubles/near extra passes remain
  reserved experimental settings and are not enabled in supplied jobs.
- Three exact shared-endpoint D joins reduce three engagements, add ZERO XY and
  preserve every original pressure vertex. No tree/rock/foliage/Soil gaps are
  filled.445 endpoint pairs within1mm were audited; proximity alone is not a
  junction. Sharp original turns are not split automatically. A positive-gap
  connector would require explicit shared-junction provenance and containment in
  existing display support, and would be a labeled execution-only depth link;
  none is admitted in this Spring output.

## New water / retained ink and cloth

WELL_1 is LIGHT_INK; WELL_2 is DARK_INK. Their own PR32 well geometry, withdrawal,
shallow wipe and lip remain the numerical baseline. The former water role is
replaced entirely by a distinct container implementation, not a sloped primitive.
Selected water center840/45/contact20, approach25. Provisional vertical20↔22
agitation stays at/above selected depth, with no lateral submerged sweep. Its
clearance/effectiveness is NOT certified. Withdraw25→35, approach lip at35,
descend at790/45/25, strip to775/45/25 at1500, lift35. Never use Z15 for immersion.

On concentration change: container wash→existing cloth/PURGE840/137.5 at1.5→
controlled rewet in NEW container→target ink well. Terminal cleanup: three water
visits,10s/three vertical cycles each; cloth twice4s, no final rewet; park/M2.
Check bottom, vessel rim/liquid, holder, tip, lip and ALL connecting swept paths.
Washing does not dry the artwork. Future A/C X811→796 and B/D X850→835 atZ28/
individual slot Y are recorded in `future_color_lips.RECORD_ONLY.json` only.

## Numerical verification and runtime

All3345 original ink sources/69101 artistic pressure samples and original order
within every source are bound to PR32's complete canonical plan SHA. All14951
original medium strokes remain in the unchanged inherited plan. Repeats carry
original IDs plus separate occurrence IDs; no canonical source is duplicated.
Full numeric parser validates every XYZ/feed/dwell against IR, envelope/projected
axis caps, pressure interpolation without clamp, contact/approach/hover, station
transfers at35, source atomicity, terminal park/M2 and initial gate. Full AIR has
identical XY and all moves at35. Altered gate and AIR descent mutations fail.
Independent complete generation is byte-identical for programs and core data.

226 tests passed;2 existing conditional tests were skipped because their separate
legacy review/bound-machine fixtures were not supplied. All11 new tests pass;
this complete new output receives its own full delivered-byte/IR readback.
Runtime uses inherited config-reference accelerations[1500,1500,1000] and ASSUMED
JD.01/full lookahead:single204.23min,selected layered206.21min,full AIR146.42min;
station AIR0.80min. These include programmed stations/dwells, exclude manual M0,
drying and actual controller/brush dynamics, and are not measured job durations.

## Reproduce

Python3.12, numpy2.3.5, scipy1.17.0, shapely2.1.2, matplotlib3.10.8, Pillow12.3.0;
pytest8.3.5 for tests. From this repository root, with fresh absolute destinations:

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_physical_ink \
  --context /absolute/cache/spring-context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_physical_ink \
  --context /absolute/cache/spring-context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_physical_ink_audit \
  --context /absolute/cache/spring-context --output /absolute/review-a --independent /absolute/review-b
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

Context recovery reads pinned PR25 rich ink and preserved F2 fields via `git show`
and verifies hashes. It never executes old source or regenerates geometry.
`--measured-max-compression-mm VALUE` can flag an operator-supplied measured
ceiling; it NEVER changes pressure or clamps Z, and does not by itself authorize
execution. New output directories are required. No existing PR32 files are
rewritten. Output manifests contain complete SHA256s; verify after decompression.
